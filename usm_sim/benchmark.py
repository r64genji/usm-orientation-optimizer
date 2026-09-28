"""Benchmark evaluation and calibration reporting for USM orientation simulator.

Runs human-written reference policies and recorded replays through simulate().
Emits tests/fixtures/benchmark_report.json with signed errors and pass/fail states.
No LLM, no AI loop, no numerical search.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME
from usm_sim.errors import SimulationError
from usm_sim.gps import RAINY_PLACE_WINDOWS, collect_window_stats
from usm_sim.scenarios import (
    COACH_RIDE_RANGE_S,
    COACH_SPEED_RAIN_M_S,
    RESTU_ALIGHTING_SERVICE_S,
    RESTU_BOARDING_SERVICE_S,
    _record,
    _unbounded_place,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_rst_shared_fleet,
    build_rst_shared_fleet_case,
    build_ticket02_bus_case,
    coach_duration_s,
    place_latlon,
    travel_duration_s,
)
from usm_sim.campus import (
    FREE_WALK_M_S,
    SLOWER_WALK_M_S,
    build_whole_campus_origins_case,
    build_whole_campus_full_cohort_case,
)
from usm_sim.metrics_cases import build_two_hostel_wait_case
from usm_sim.simulate import simulate
from usm_sim.spillback_cases import (
    build_changing_conditions_case,
    build_delayed_report_case,
    build_door_reopen_case,
    build_no_waiting_space_case,
    build_time_limit_incomplete_case,
)
from usm_sim.workers import build_exclusive_duty_case

# 18 September rainy record timing offsets in seconds from 06:19:03 Asia/Kuala_Lumpur
RAINY_18SEP_OFFSETS_S = {
    "recording_start": 0,
    "shelter_release": 7409,  # 08:22:32 imposed release from cafeteria rain shelter
    "bus_queue_arrival": 8056,  # 08:33:19 arrival at bus wait
    "bus_departure": 8162,  # 08:35:05 departure from boarding area
    "dtsp_side_arrival": 8345,  # 08:38:08 arrival at DTSP alighting area
    "recording_end_arrival": 8690,  # 08:43:53 arrival at hall area; recording ends NOT seated
}
RAINY_COACH_RIDE_S = 183  # observed 08:35:05 to 08:38:08; not a travel input

RAINY_GPS_RELATIVE = Path("tests/fixtures/gps/session_3_2026-09-18_morning_M01_Rainy_to_DTSP_Location.csv")


def default_rainy_gps_path(repo_root: Path) -> Path:
    return repo_root / RAINY_GPS_RELATIVE


def build_restu_18sep_rainy_replay(repo_root: Path | None = None) -> tuple[dict, dict]:
    """Resolved 18 September Restu rainy journey from committed fixtures.

    Supports cafeteria-area shelter hold, release at ~08:22:32, bus wait at ~08:33:19,
    departure at ~08:35:05, and DTSP-side arrival at ~08:38:08.
    Recording ends at 08:43:53 during final approach; full seating is NOT confirmed.
    """
    root = repo_root or Path(__file__).resolve().parent.parent
    gps_path = default_rainy_gps_path(root)
    if not gps_path.is_file():
        raise SimulationError(
            "missing_input",
            f"Missing GPS file for 18 Sep rainy replay: {gps_path}",
            field="tests.fixtures.gps.session_3_2026-09-18_morning_M01_Rainy_to_DTSP_Location.csv",
        )

    gps_stats = collect_window_stats(gps_path, event_date="2026-09-18", windows=RAINY_PLACE_WINDOWS)
    for place_id in RAINY_PLACE_WINDOWS:
        stats = gps_stats.get(place_id) or {}
        if int(stats.get("sample_count") or 0) < 1:
            raise SimulationError(
                "missing_input",
                f"No filtered GPS samples for {place_id} in {gps_path}",
                field=f"gps_observation.{place_id}",
            )

    members = [
        {"student_key": f"rain_{index:04d}", "queue_tie_key": f"{index:04d}"}
        for index in range(40)
    ]

    places = [
        _unbounded_place(
            "rst_rain_shelter",
            5.356461,
            100.289265,
            "Rain shelter at cafeteria area",
            {
                "observation_window": "2026-09-18 06:24-08:18",
                "coordinate_method": "median of filtered GPS",
                "estimated_capacity_students": 120,
                "estimated_capacity_note": "sourced estimate, not GPS scatter",
            },
        ),
        _unbounded_place(
            "rst_bus_wait",
            5.356043,
            100.293918,
            "Rainy morning bus wait area",
            {
                "observation_window": "2026-09-18 08:33:30-08:34:40",
                "coordinate_method": "median of filtered GPS",
                "estimated_capacity_students": 80,
                "estimated_capacity_note": "sourced estimate, not GPS scatter",
            },
        ),
        _unbounded_place(
            "rst_boarding_approach",
            5.356012,
            100.293748,
            "Boarding approach area",
            {
                "coordinate_method": "boarding-approach candidate",
                "estimated_capacity_students": 40,
            },
        ),
        _unbounded_place(
            "dtsp_alighting_area",
            5.357364,
            100.301470,
            "DTSP bus alighting area",
            {
                "observation_window": "2026-09-18 08:38:00-08:39:00",
                "coordinate_method": "median of filtered GPS",
                "estimated_capacity_students": 60,
            },
        ),
        _unbounded_place(
            "dtsp_hall_reference",
            5.35695,
            100.30311,
            "DTSP hall map pin, distinct from alighting area",
            {
                "coordinate_method": "DTSP map pin from project context",
            },
        ),
    ]

    for place in places:
        gps = gps_stats.get(place["id"])
        if gps:
            place["gps_observation"] = gps
            if "median_latitude_deg" in gps:
                place["latitude_deg"] = float(gps["median_latitude_deg"])
            if "median_longitude_deg" in gps:
                place["longitude_deg"] = float(gps["median_longitude_deg"])
            place["location_uncertainty"] = {
                "median_horizontal_accuracy_m": gps.get("median_horizontal_accuracy_m"),
                "sample_count": gps.get("sample_count"),
                "note": gps.get("note"),
            }

    d_shelter_walk = travel_duration_s(
        *place_latlon(places, "rst_rain_shelter"),
        *place_latlon(places, "rst_bus_wait"),
        SLOWER_WALK_M_S,
    )
    d_board_walk = travel_duration_s(
        *place_latlon(places, "rst_bus_wait"),
        *place_latlon(places, "rst_boarding_approach"),
        SLOWER_WALK_M_S,
    )
    d_coach = coach_duration_s(
        *place_latlon(places, "rst_boarding_approach"),
        *place_latlon(places, "dtsp_alighting_area"),
        COACH_SPEED_RAIN_M_S,
    )
    d_final = travel_duration_s(
        *place_latlon(places, "dtsp_alighting_area"),
        *place_latlon(places, "dtsp_hall_reference"),
        FREE_WALK_M_S,
    )

    observation_ref = "spec.md#19-accuracy-target-and-evidence-limits"
    gps_ref_str = str(RAINY_GPS_RELATIVE).replace("\\", "/")

    fleet_info = build_rst_shared_fleet(
        weather="rain",
        available_time_s=0,
        places=places,
    )

    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-12-rainy-18sep-v1",
        "scenario_id": "restu_18sep_rainy_replay",
        "uncertainty_case_id": "rainy_18sep_calibration",
        "event_date": "2026-09-18",
        "start_time_local": "06:19:03",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 9000,
        "simulation_end_s": 10800,
        "max_events_per_run": 1000000,
        "source_units": [
            {
                "id": "su_restu_rain",
                "hostel_id": "restu",
                "estimated_attendance": 40,
                "resolved_attendance": 40,
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "actual_reporting": "present_at_recording_start",
                "readiness": "ready_at_shelter",
            }
        ],
        "places": places,
        "route_legs": [
            {
                "id": "leg_rain_walk_to_bus",
                "from_place_id": "rst_rain_shelter",
                "to_place_id": "rst_bus_wait",
                "duration_s": d_shelter_walk,
                "mode": "walk",
                "stage_id": "shelter_to_bus",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_to_boarding_rain",
                "from_place_id": "rst_bus_wait",
                "to_place_id": "rst_boarding_approach",
                "duration_s": d_board_walk,
                "mode": "walk",
                "stage_id": "boarding_approach",
                "shared_resource_ids": ["rst_boarding_berth"],
            },
            {
                "id": "leg_rain_coach_transit",
                "from_place_id": "rst_boarding_approach",
                "to_place_id": "dtsp_alighting_area",
                "duration_s": d_coach,
                "mode": "coach",
                "stage_id": "transit",
                "shared_resource_ids": ["rst_fleet"],
            },
            {
                "id": "leg_rain_final_approach",
                "from_place_id": "dtsp_alighting_area",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": d_final,
                "mode": "walk",
                "stage_id": "final_approach",
                "shared_resource_ids": [],
            },
        ],
        "route_stages": [
            {
                "id": "shelter_hold",
                "kind": "hold",
                "place_id": "rst_rain_shelter",
                "until": {"calendar_id": "rain_shelter_release"},
            },
            {
                "id": "shelter_to_bus",
                "kind": "travel",
                "leg_id": "leg_rain_walk_to_bus",
            },
            {
                "id": "bus_waiting",
                "kind": "hold",
                "place_id": "rst_bus_wait",
                "until": {"fleet_available": "rst_fleet"},
            },
            {
                "id": "boarding_walk",
                "kind": "travel",
                "leg_id": "leg_to_boarding_rain",
            },
            {
                "id": "boarding",
                "kind": "batch_service",
                "place_id": "rst_boarding_approach",
                "fleet_id": "rst_fleet",
                "action": "board",
                "duration_s": RESTU_BOARDING_SERVICE_S,
            },
            {
                "id": "transit",
                "kind": "vehicle_travel",
                "leg_id": "leg_rain_coach_transit",
            },
            {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "dtsp_alighting_area",
                "fleet_id": "rst_fleet",
                "action": "alight",
                "duration_s": RESTU_ALIGHTING_SERVICE_S,
            },
            {
                "id": "final_approach",
                "kind": "travel",
                "leg_id": "leg_rain_final_approach",
                "completion_event": "hall_area_arrival",
            },
        ],
        "shared_resource_ids": ["rst_fleet", "rst_boarding_berth"],
        "vehicle_types": fleet_info["vehicle_types"],
        "fleets": fleet_info["fleets"],
        "calendars": [
            {
                "id": "rain_shelter_release",
                "kind": "release",
                "place_id": "rst_rain_shelter",
                "open_time_s": RAINY_18SEP_OFFSETS_S["shelter_release"],
                "imposed": True,
                "label": "imposed_rain_shelter_release",
            },
        ],
        "initial_state": {
            "students": [
                {
                    "part_id": "part_restu_rain",
                    "group_id": "g_restu_rain",
                    "source_unit_id": "su_restu_rain",
                    "place_id": "rst_rain_shelter",
                    "hostel_id": "restu",
                    "hostel_composition": {"restu": 40},
                    "members": members,
                }
            ],
            "queues": [],
            "workers": [],
            "vehicles": fleet_info["vehicles"],
            "hall_occupancy_students": 0,
        },
        "operating_rules": {
            "required_endpoint": "hall_area_arrival",
            "route_id": "rst_rain_bus_chain",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "seating_modeled": False,
            "weather_condition": "rain",
        },
        "measured_facts": [
            {
                "id": "recording_start",
                "value": "2026-09-18T06:19:03+08:00",
                "category": "measured",
                "observation_ref": gps_ref_str,
            },
            {
                "id": "rainy_place_coordinates",
                "category": "measured",
                "observation_ref": gps_ref_str,
            },
        ],
        "uncertain_assumptions": [
            {
                "id": "shelter_hold_classification",
                "value": "rain_shelter_wait",
                "category": "assumed",
                "note": "classification of the ~2 hour rain shelter hold during heavy weather",
            },
            {
                "id": "workers_unconstrained",
                "value": [],
                "category": "assumed",
                "note": "worker constraints not enforced in single-replay calibration",
            },
            {
                "id": "coach_present_at_boarding",
                "value": 0,
                "unit": "s",
                "category": "assumed",
                "note": "coach is present at boarding from the start; not scheduled at the GPS bus-wait clock",
            },
            {
                "id": "walk_and_service_durations",
                "category": "assumed",
                "note": "geodesic distance at declared walk/coach speeds; not GPS clock intervals",
            },
            {
                "id": "place_capacity_unbounded",
                "category": "assumed",
                "note": "unbounded assumption; GPS scatter is not a capacity estimate",
            },
        ] + fleet_info["uncertain_assumptions"],
        "decisions": [
            {
                "id": "required_endpoint",
                "value": "hall_area_arrival",
                "category": "decision",
                "note": "seated completion is unverified as recording ends at 08:43:53",
            },
            {
                "id": "rainy_bus_chain",
                "category": "decision",
                "note": "bus transit chain under rain conditions",
            },
        ],
        "source_records": [
            _record(
                "places.rst_rain_shelter.latitude_deg",
                5.356461,
                "deg",
                "2026-09-18",
                "median of filtered GPS in 06:24-08:18",
                "medium",
                f"{gps_ref_str}#06:24-08:18",
                "measured",
            ),
            _record(
                "places.rst_bus_wait.latitude_deg",
                5.356043,
                "deg",
                "2026-09-18",
                "median of filtered GPS in 08:33:30-08:34:40",
                "medium",
                f"{gps_ref_str}#08:33:30-08:34:40",
                "measured",
            ),
            _record(
                "places.dtsp_alighting_area.latitude_deg",
                5.357364,
                "deg",
                "2026-09-18",
                "median of filtered GPS in 08:38:00-08:39:00",
                "medium",
                f"{gps_ref_str}#08:38:00-08:39:00",
                "measured",
            ),
            _record(
                "calendars.rain_shelter_release.open_time_s",
                RAINY_18SEP_OFFSETS_S["shelter_release"],
                "s",
                "2026-09-18",
                "imposed release timestamp at 08:22:32",
                "high",
                observation_ref,
                "decision",
            ),
            _record(
                "route_legs.leg_rain_walk_to_bus.duration_s",
                d_shelter_walk,
                "s",
                "2026-09-18",
                f"geodesic walk at {SLOWER_WALK_M_S} m/s; not the 08:22:32-08:33:19 clock interval",
                "medium",
                observation_ref,
                "assumed",
            ),
            _record(
                "route_legs.leg_rain_coach_transit.duration_s",
                d_coach,
                "s",
                "2026-09-18",
                f"geodesic coach travel at {COACH_SPEED_RAIN_M_S:.3f} m/s; not the 08:35:05-08:38:08 GPS clock",
                "medium",
                observation_ref,
                "assumed",
            ),
        ] + fleet_info["source_records"],
        "accuracy_references": [
            {
                "id": "shelter_release",
                "role": "imposed_input",
                "imposed_input": True,
                "event_match": {"event_type": "calendar_open", "calendar_id": "rain_shelter_release"},
                "observed_s": RAINY_18SEP_OFFSETS_S["shelter_release"],
                "observed_local": "08:22:32",
                "limit_s": 600,
                "endpoint_definition": "imposed release from cafeteria rain shelter",
                "observation_ref": observation_ref,
            },
            {
                "id": "bus_queue_arrival",
                "role": "predicted",
                "event_match": {"event_type": "arrival", "place_id": "rst_bus_wait"},
                "observed_s": RAINY_18SEP_OFFSETS_S["bus_queue_arrival"],
                "observed_local": "08:33:19",
                "limit_s": 600,
                "endpoint_definition": "arrival at rst_bus_wait area",
                "observation_ref": observation_ref,
            },
            {
                "id": "bus_departure",
                "role": "predicted",
                "event_match": {"event_type": "departure", "leg_id": "leg_rain_coach_transit"},
                "observed_s": RAINY_18SEP_OFFSETS_S["bus_departure"],
                "observed_local": "08:35:05",
                "limit_s": 600,
                "endpoint_definition": "coach departure from boarding area",
                "observation_ref": observation_ref,
            },
            {
                "id": "dtsp_side_arrival",
                "role": "predicted",
                "event_match": {"event_type": "arrival", "place_id": "dtsp_alighting_area"},
                "observed_s": RAINY_18SEP_OFFSETS_S["dtsp_side_arrival"],
                "observed_local": "08:38:08",
                "limit_s": 600,
                "endpoint_definition": "arrival at dtsp_alighting_area",
                "observation_ref": observation_ref,
            },
            {
                "id": "coach_ride",
                "role": "predicted_duration",
                "start_match": {"event_type": "departure", "leg_id": "leg_rain_coach_transit"},
                "end_match": {"event_type": "arrival", "place_id": "dtsp_alighting_area"},
                "allowed_range_s": list(COACH_RIDE_RANGE_S),
                "endpoint_definition": "coach ride duration under rainy conditions",
                "observation_ref": observation_ref,
            },
            {
                "id": "total_journey_duration",
                "role": "predicted_duration",
                "start_match": {
                    "event_type": "calendar_open",
                    "calendar_id": "rain_shelter_release",
                },
                "end_match": {"event_type": "arrival", "place_id": "dtsp_alighting_area"},
                "observed_s": RAINY_18SEP_OFFSETS_S["dtsp_side_arrival"] - RAINY_18SEP_OFFSETS_S["shelter_release"],
                "limit_s": 600,
                "endpoint_definition": "total journey duration from shelter release to dtsp arrival",
                "observation_ref": observation_ref,
            },
            {
                "id": "recording_end_arrival",
                "role": "evidence_boundary",
                "event_match": {"event_type": "hall_area_arrival"},
                "observed_s": RAINY_18SEP_OFFSETS_S["recording_end_arrival"],
                "observed_local": "08:43:53",
                "limit_s": 600,
                "endpoint_definition": "arrival at hall area where recording ends at 08:43:53; evidence boundary / unverified endpoint, not seated completion",
                "observation_ref": observation_ref,
            },
            {
                "id": "seated_completion",
                "role": "unverified",
                "hostel_id": "restu",
                "note": "Full seating completion is not confirmed; recording ends at 08:43:53 during approach.",
                "endpoint_definition": "seated in hall",
                "observation_ref": observation_ref,
            },
        ],
    }

    policy = {
        "policy_id": "restu_18sep_rainy_replay",
        "policy_version": "1",
        "grouping": {"mode": "single_contingent"},
        "required_endpoint": "hall_area_arrival",
        "release_rule": {"type": "follow_imposed_calendar", "calendar_id": "rain_shelter_release"},
        "vehicle_dispatch_rule": {"type": "shared_fleet", "fleet_id": "rst_fleet"},
        "destination_rule": {"type": "immediate"},
        "random_seed": 0,
    }
    return scenario, policy


# ---------------------------------------------------------------------------
# Reference Policies
# ---------------------------------------------------------------------------


def build_current_operation_policy(base_policy: Mapping[str, Any] | None = None) -> dict:
    """Current-operation reference: immediate release, uncoordinated bus dispatch, unconstrained approach."""
    pol = copy.deepcopy(dict(base_policy or {}))
    pol["policy_id"] = "reference_current_operation"
    pol["policy_version"] = "1"
    pol.setdefault("required_endpoint", "hall_area_arrival")
    pol["release_rule"] = {"type": "immediate"}
    pol["destination_space_rule"] = "allow_approach_wait"
    pol["coordination_delay_s"] = 0.0
    return pol


def build_fixed_release_policy(
    base_policy: Mapping[str, Any] | None = None,
    interval_s: float = 300.0,
) -> dict:
    """Fixed-release reference: simple fixed release schedule across groups."""
    pol = copy.deepcopy(dict(base_policy or {}))
    pol["policy_id"] = "reference_fixed_release"
    pol["policy_version"] = "1"
    pol.setdefault("required_endpoint", "hall_area_arrival")
    pol["release_rule"] = {"type": "fixed_interval", "interval_s": float(interval_s)}
    pol["destination_space_rule"] = "allow_approach_wait"
    pol["coordination_delay_s"] = 0.0
    return pol


def build_queue_based_policy(
    base_policy: Mapping[str, Any] | None = None,
    hold_threshold: int = 40,
    resume_threshold: int = 20,
) -> dict:
    """Queue-based reference: reserve space before departure / hold upstream on downstream queue."""
    pol = copy.deepcopy(dict(base_policy or {}))
    pol["policy_id"] = "reference_queue_based"
    pol["policy_version"] = "1"
    pol.setdefault("required_endpoint", "hall_area_arrival")
    pol["release_rule"] = {"type": "queue_based"}
    pol["destination_space_rule"] = "reserve_before_departure"
    pol["coordination_delay_s"] = 0.0
    pol["space_control"] = {
        "destination_place_id": "dtsp_hall_reference",
        "hold_threshold_students": int(hold_threshold),
        "resume_threshold_students": int(resume_threshold),
    }
    return pol


# ---------------------------------------------------------------------------
# Benchmark Suite Execution
def _extract_full_campus_milestones(trace: list[dict], scenario: dict | None = None) -> dict[str, Any]:
    def _find_first(event_type: str, **kw: Any) -> dict | None:
        for e in trace:
            if e.get("event_type") != event_type:
                continue
            if all(e.get(k) == v for k, v in kw.items()):
                return e
        return None

    def _find_last(event_type: str, **kw: Any) -> dict | None:
        for e in reversed(trace):
            if e.get("event_type") != event_type:
                continue
            if all(e.get(k) == v for k, v in kw.items()):
                return e
        return None

    first_exterior = _find_first("arrival", place_id="dtsp_exterior_gathering")
    first_seated = _find_first("seated_completion")
    last_seated = _find_last("seated_completion")

    restu_events = [e for e in trace if e.get("hostel_composition", {}).get("restu")]
    r_first_bus_wait = next((e for e in restu_events if e.get("event_type") == "arrival" and e.get("place_id") == "rst_bus_wait"), None)
    r_first_board = next((e for e in restu_events if e.get("event_type") == "departure" and e.get("leg_id") == "leg_transit"), None)
    r_first_alight = next((e for e in restu_events if e.get("event_type") == "arrival" and e.get("place_id") == "dtsp_alighting_area"), None)
    r_first_exterior = next((e for e in restu_events if e.get("event_type") == "arrival" and e.get("place_id") == "dtsp_exterior_gathering"), None)
    r_cafe_hold_end = next((e for e in restu_events if e.get("event_type") == "hold_end" and e.get("primary_cause") == "imposed_sequencing_wait"), None)
    r_seated_events = [e for e in restu_events if e.get("event_type") == "seated_completion"]
    r_first_seated = r_seated_events[0] if r_seated_events else None
    r_last_seated = r_seated_events[-1] if r_seated_events else None

    hostel_dep_s = 0.0
    if scenario and scenario.get("start_time_local"):
        from usm_sim.timeutil import parse_start, local_iso
        start_dt = parse_start(
            scenario.get("event_date", "2026-09-17"),
            scenario["start_time_local"],
            scenario.get("timezone", TIMEZONE_NAME),
        )
        hostel_dep_local = local_iso(start_dt, 0)
    else:
        t0_event = next((e for e in trace if e.get("time_ms") == 0 and e.get("time_local")), None)
        hostel_dep_local = t0_event["time_local"] if t0_event else "2026-09-17T06:30:00+08:00"
    all_seated_s = last_seated["time_ms"] / 1000.0 if last_seated else None
    r_first_seated_s = r_first_seated["time_ms"] / 1000.0 if r_first_seated else None
    r_last_seated_s = r_last_seated["time_ms"] / 1000.0 if r_last_seated else None

    return {
        "hostel_departure_s": hostel_dep_s,
        "hostel_departure_local": hostel_dep_local,
        "first_exterior_arrival_s": first_exterior["time_ms"] / 1000.0 if first_exterior else None,
        "first_exterior_arrival_local": first_exterior["time_local"] if first_exterior else None,
        "first_student_seated_s": first_seated["time_ms"] / 1000.0 if first_seated else None,
        "first_student_seated_local": first_seated["time_local"] if first_seated else None,
        "restu_cafe_release_s": r_cafe_hold_end["time_ms"] / 1000.0 if r_cafe_hold_end else None,
        "restu_cafe_release_local": r_cafe_hold_end["time_local"] if r_cafe_hold_end else None,
        "restu_bus_queue_arrival_s": r_first_bus_wait["time_ms"] / 1000.0 if r_first_bus_wait else None,
        "restu_bus_queue_arrival_local": r_first_bus_wait["time_local"] if r_first_bus_wait else None,
        "restu_first_coach_departure_s": r_first_board["time_ms"] / 1000.0 if r_first_board else None,
        "restu_first_coach_departure_local": r_first_board["time_local"] if r_first_board else None,
        "restu_first_alighting_s": r_first_alight["time_ms"] / 1000.0 if r_first_alight else None,
        "restu_first_alighting_local": r_first_alight["time_local"] if r_first_alight else None,
        "restu_first_exterior_arrival_s": r_first_exterior["time_ms"] / 1000.0 if r_first_exterior else None,
        "restu_first_exterior_arrival_local": r_first_exterior["time_local"] if r_first_exterior else None,
        "restu_first_seated_s": r_first_seated_s,
        "restu_first_seated_local": r_first_seated["time_local"] if r_first_seated else None,
        "restu_last_seated_s": r_last_seated_s,
        "restu_last_seated_local": r_last_seated["time_local"] if r_last_seated else None,
        "all_seated_completion_s": all_seated_s,
        "all_seated_completion_local": last_seated["time_local"] if last_seated else None,
        "total_journey_duration_s": (all_seated_s - hostel_dep_s) if all_seated_s is not None else None,
        "total_journey_duration_min": round((all_seated_s - hostel_dep_s) / 60.0, 2) if all_seated_s is not None else None,
        "restu_first_journey_duration_s": (r_first_seated_s - hostel_dep_s) if r_first_seated_s is not None else None,
        "restu_last_journey_duration_s": (r_last_seated_s - hostel_dep_s) if r_last_seated_s is not None else None,
    }


# ---------------------------------------------------------------------------


def run_benchmark(repo_root: Path | None = None) -> dict:
    """Run streamlined full campus full cohort benchmark and return report dict."""
    # Official 2026 full campus cohort (3,543 students across all 8 hostels)
    full_campus_sc, full_campus_pol = build_whole_campus_full_cohort_case()
    full_campus_res = simulate(full_campus_sc, full_campus_pol)

    completed_students = int(full_campus_res["measures"].get("completed_students", 0))
    total_students = sum(int(unit["resolved_attendance"]) for unit in full_campus_sc["source_units"])
    hostel_outcomes = full_campus_res["outcomes"].get("per_hostel", [])
    dtsp_seated = sum(
        e.get("student_count", 1)
        for e in full_campus_res["event_trace"]
        if e.get("event_type") == "seated_completion" and e.get("place_id") == "dtsp_seating"
    )
    g03_seated = sum(
        e.get("student_count", 1)
        for e in full_campus_res["event_trace"]
        if e.get("event_type") == "seated_completion" and e.get("place_id") == "g03_seating"
    )
    venue_allocation = {
        "dtsp_seated": dtsp_seated,
        "g03_seated": g03_seated,
        "total_seated": dtsp_seated + g03_seated,
        "cohort_coverage_pct": round(100.0 * (dtsp_seated + g03_seated) / total_students, 2) if total_students else 0.0,
    }

    door_counts: dict[str, int] = {}
    door_time_ranges: dict[str, list[float]] = {}
    rst_hostel_doors: dict[str, set[str]] = {h: set() for h in ("tekun", "saujana", "restu")}
    for e in full_campus_res["event_trace"]:
        if e.get("event_type") == "entrance_completion":
            place = e.get("place_id")
            if place:
                door_counts[place] = door_counts.get(place, 0) + e.get("student_count", 1)
                t_s = e.get("time_ms", 0) / 1000.0
                if place not in door_time_ranges:
                    door_time_ranges[place] = [t_s, t_s]
                else:
                    door_time_ranges[place][0] = min(door_time_ranges[place][0], t_s)
                    door_time_ranges[place][1] = max(door_time_ranges[place][1], t_s)
            for hid in e.get("hostel_composition", {}):
                if hid in rst_hostel_doors and place:
                    rst_hostel_doors[hid].add(place)

    rst_doors_pairwise_distinct = (
        len(rst_hostel_doors["tekun"]) == 1
        and len(rst_hostel_doors["saujana"]) == 1
        and len(rst_hostel_doors["restu"]) == 1
        and rst_hostel_doors["tekun"].isdisjoint(rst_hostel_doors["saujana"])
        and rst_hostel_doors["tekun"].isdisjoint(rst_hostel_doors["restu"])
        and rst_hostel_doors["saujana"].isdisjoint(rst_hostel_doors["restu"])
    )

    status_ok = (
        full_campus_res["status"] == "completed"
        and completed_students == 3543
        and (dtsp_seated + g03_seated) == 3543
        and len(hostel_outcomes) == 8
        and rst_doors_pairwise_distinct
    )

    by_hostel_wait = {
        h["hostel_id"]: {
            "student_count": h["student_count"],
            "completed_students": h["completed_students"],
            "mean_wait_s": h["mean_wait_s"],
            "total_waiting_student_s": h["total_waiting_student_s"],
            "p95_wait_s": h.get("p95_wait_s"),
        }
        for h in hostel_outcomes
    }

    wait_times = {
        "total_waiting_student_s": full_campus_res["measures"]["total_student_waiting_student_s"],
        "mean_wait_s": full_campus_res["measures"]["mean_wait_s"],
        "p95_wait_s": full_campus_res["measures"].get("p95_wait_s"),
        "max_hostel_mean_wait_s": full_campus_res["measures"]["max_hostel_mean_wait_s"],
        "outdoor_waiting_student_s": full_campus_res["measures"].get("outdoor_waiting_student_s", 0.0),
        "by_hostel": by_hostel_wait,
        "imposed_sequencing_waiting_student_s": full_campus_res["measures"].get("imposed_sequencing_wait_student_s", 0.0),
        "restu_cafe_waiting_student_s": full_campus_res["measures"].get("restu_cafe_wait_student_s", 0.0),
    }

    doors_concurrent = False
    if "dtsp_door_a" in door_time_ranges and "dtsp_door_d" in door_time_ranges:
        s_a, e_a = door_time_ranges["dtsp_door_a"]
        s_d, e_d = door_time_ranges["dtsp_door_d"]
        doors_concurrent = max(0.0, min(e_a, e_d) - max(s_a, s_d)) > 0

    door_operations = {
        "doors_configured": [d["id"] for d in full_campus_sc["destination"].get("doors", [])],
        "door_counts": door_counts,
        "door_time_ranges_s": door_time_ranges,
        "concurrent_doors": doors_concurrent,
        "rst_hostel_doors": {h: sorted(list(doors)) for h, doors in rst_hostel_doors.items()},
        "rst_doors_pairwise_distinct": rst_doors_pairwise_distinct,
        "physical_mapping_status": "parameterized_channel_labels_assumed_not_observed",
    }
    carpark_tiers = full_campus_sc["destination"].get("carpark_tiers", {})
    seating_model = {
        "type": "direct_block_directed_flow",
        "single_server_bottleneck": False,
        "waiting_for_server_s": full_campus_res["measures"].get("waiting_student_s_by_cause", {}).get("waiting_for_server", 0.0),
    }

    milestones = _extract_full_campus_milestones(full_campus_res["event_trace"], full_campus_sc)

    report = {
        "benchmark_version": "1.0.0",
        "status": "passed" if status_ok else "failed",
        "scenario_id": full_campus_sc["scenario_id"],
        "total_students": total_students,
        "completed_students": completed_students,
        "full_campus_cohort": {
            "scenario_id": full_campus_sc["scenario_id"],
            "status": full_campus_res["status"],
            "total_students": total_students,
            "completed_students": completed_students,
            "wait_times": wait_times,
            "milestone_predictions": milestones,
            "venue_allocation": venue_allocation,
            "door_operations": door_operations,
            "carpark_tiers": carpark_tiers,
            "seating_model": seating_model,
        },
        "wait_times": wait_times,
        "milestone_predictions": milestones,
        "venue_allocation": venue_allocation,
        "door_operations": door_operations,
        "carpark_tiers": carpark_tiers,
        "seating_model": seating_model,
    }
    return report


def emit_benchmark_report(
    repo_root: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    """Run benchmark suite and write JSON report to tests/fixtures/benchmark_report.json."""
    root = repo_root or Path(__file__).resolve().parent.parent
    dest = output_path or (root / "tests" / "fixtures" / "benchmark_report.json")
    report = run_benchmark(root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    return dest


if __name__ == "__main__":
    out = emit_benchmark_report()
    print(f"Emitted benchmark report to {out}")
