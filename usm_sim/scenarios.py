"""Ticket-01 scenarios: one hand-calculated queue and the 17 September Restu replay."""

from __future__ import annotations

from math import atan2, cos, radians, sin, sqrt
from pathlib import Path

from usm_sim.campus import FREE_WALK_M_S, SLOWER_WALK_M_S
from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME
from usm_sim.errors import SimulationError
from usm_sim.gps import PLACE_WINDOWS, collect_window_stats, default_gps_path

RESTU_STAGE_ORDER = [
    "gathering",
    "supervised_approach",
    "overpass_approach",
    "bus_waiting",
    "boarding",
    "transit",
    "alighting",
    "transfer_walk",
    "exterior_holding",
    "final_hall_approach",
]

# Seconds from 2026-09-17 06:47:12 Asia/Kuala_Lumpur.
RESTU_OFFSETS_S = {
    "recording_start": 0,
    "supervised_release": 2748,  # 07:33:00 imposed
    "bus_queue_arrival": 3708,  # 07:49:00
    "bus_departure": 4248,  # 07:58:00
    "dtsp_side_arrival": 4458,  # 08:01:30
    "exterior_hold_end": 6288,  # 08:32:00 observed end of outdoor wait/staging in 17 Sep GPS trace; doors were NOT locked
    "hall_area_arrival": 6468,  # 08:35:00
}

EXTERIOR_HOLD_OBSERVED_S = 31 * 60
COACH_RIDE_RANGE_S = (120, 270)
EARTH_RADIUS_M = 6_371_000.0
# Declared urban coach speeds. Not the GPS clock interval 07:58-08:01:30.
COACH_SPEED_DRY_M_S = 20_000.0 / 3600.0
COACH_SPEED_RAIN_M_S = 18_000.0 / 3600.0
# Assumed coach presence at boarding at 07:50:00. Not fitted to 07:58.
RESTU_COACH_READY_S = 3768
RESTU_BOARDING_SERVICE_S = 180
RESTU_ALIGHTING_SERVICE_S = 180
RESTU_COACH_TRANSIT_S = 210
RESTU_COLUMN_WALK_M_S = 0.42


def geodesic_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres on a spherical Earth."""
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    chord = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(chord), sqrt(1.0 - chord))


def travel_duration_s(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_m_s: float,
) -> int:
    """Travel time from declared speed and coordinates. Not a GPS clock delta."""
    if speed_m_s <= 0:
        raise ValueError("speed_m_s must be positive")
    return max(1, int(round(geodesic_m(lat1, lon1, lat2, lon2) / speed_m_s)))


def coach_duration_s(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    speed_m_s: float,
) -> int:
    """Coach travel time from declared speed and coordinates. Not clamped."""
    return travel_duration_s(lat1, lon1, lat2, lon2, speed_m_s)

def place_latlon(places: list[dict], place_id: str) -> tuple[float, float]:
    for place in places:
        if place["id"] == place_id:
            return float(place["latitude_deg"]), float(place["longitude_deg"])
    raise KeyError(place_id)


def _record(
    field: str,
    value,
    unit: str,
    date: str,
    method: str,
    confidence: str,
    observation_ref: str,
    category: str,
) -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "date": date,
        "method": method,
        "confidence": confidence,
        "observation_ref": observation_ref,
        "category": category,
    }


def build_artificial_single_server_case() -> tuple[dict, dict]:
    """Four students, one walk, one server. Completions 70/80/90/100 s."""
    members = [
        {"student_key": "s1", "queue_tie_key": "00"},
        {"student_key": "s2", "queue_tie_key": "01"},
        {"student_key": "s3", "queue_tie_key": "02"},
        {"student_key": "s4", "queue_tie_key": "03"},
    ]
    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-01-artificial-v1",
        "scenario_id": "artificial_single_server_v1",
        "uncertainty_case_id": "artificial_base",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 95,
        "simulation_end_s": 1000,
        "max_events_per_run": 10000,
        "source_units": [
            {
                "id": "su_origin",
                "hostel_id": "synthetic",
                "estimated_attendance": 4,
                "resolved_attendance": 4,
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "layout_link": "assumed_single_unit",
            }
        ],
        "places": [
            {
                "id": "origin",
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "meaning": "artificial origin",
                "capacity_constraint": "unbounded",
                "capacity_note": "explicit unbounded artificial origin",
                "capacity_from_gps_scatter": False,
            },
            {
                "id": "entrance",
                "latitude_deg": 0.001,
                "longitude_deg": 0.0,
                "meaning": "single-server entrance",
                "capacity_constraint": "unbounded",
                "capacity_note": "explicit unbounded artificial entrance",
                "capacity_from_gps_scatter": False,
            },
        ],
        "route_legs": [
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "duration_s": 60,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        "route_stages": [
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
            {
                "id": "entrance_service",
                "kind": "queue_service",
                "place_id": "entrance",
                "service_duration_s": 10,
                "server_count": 1,
                "queue_discipline": "fcfs",
            },
        ],
        "calendars": [],
        "initial_state": {
            "students": [
                {
                    "part_id": "part_origin",
                    "group_id": "g_walk",
                    "source_unit_id": "su_origin",
                    "place_id": "origin",
                    "hostel_id": "synthetic",
                    "hostel_composition": {"synthetic": 4},
                    "members": members,
                }
            ],
            "queues": [],
            "workers": [],
            "vehicles": [],
            "hall_occupancy_students": 0,
        },
        "operating_rules": {
            "required_endpoint": "service_complete",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "seating_modeled": False,
        },
        "measured_facts": [],
        "uncertain_assumptions": [
            {
                "id": "walk_duration",
                "value": 60,
                "unit": "s",
                "category": "assumed",
                "note": "hand-calculated case: students arrive together at 60 s",
            }
        ],
        "decisions": [
            {
                "id": "single_server",
                "value": 1,
                "category": "decision",
                "note": "one server, 10 s per student",
            }
        ],
        "source_records": [
            _record(
                "route_legs.walk_1.duration_s",
                60,
                "s",
                "2026-01-01",
                "hand-calculated example from spec section 21",
                "high",
                "spec.md#concrete-time-accounting-example",
                "assumed",
            ),
            _record(
                "route_stages.entrance_service.service_duration_s",
                10,
                "s",
                "2026-01-01",
                "hand-calculated example from spec section 21",
                "high",
                "spec.md#concrete-time-accounting-example",
                "decision",
            ),
            _record(
                "source_units.su_origin.resolved_attendance",
                4,
                "persons",
                "2026-01-01",
                "hand-calculated example",
                "high",
                "spec.md#concrete-time-accounting-example",
                "assumed",
            ),
        ],
        "accuracy_references": [],
    }
    policy = {
        "policy_id": "artificial_fcfs_v1",
        "policy_version": "1",
        "grouping": {"mode": "explicit_parts"},
        "required_endpoint": "service_complete",
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "service_then_complete"},
        "random_seed": 0,
    }
    return scenario, policy


def _unbounded_place(
    place_id: str,
    latitude_deg: float,
    longitude_deg: float,
    meaning: str,
    extra: dict | None = None,
) -> dict:
    place = {
        "id": place_id,
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "meaning": meaning,
        "capacity_constraint": "unbounded",
        "capacity_note": (
            "explicit unbounded assumption for ticket 01; "
            "GPS scatter is not a storage-capacity estimate"
        ),
        "capacity_from_gps_scatter": False,
        "estimated_capacity_from_gps_scatter": False,
    }
    if extra:
        place.update(extra)
    return place


def build_restu_17sep_replay(repo_root: Path | None = None) -> tuple[dict, dict]:
    """Resolved 17 September Restu chain with one contingent and one coach cycle."""
    root = repo_root or Path(__file__).resolve().parent.parent
    gps_path = default_gps_path(root)
    if not gps_path.is_file():
        raise SimulationError(
            "missing_input",
            f"Missing GPS file for Restu replay: {gps_path}",
            field="raw_data.sensor_logger.Location.csv",
        )
    gps_stats = collect_window_stats(gps_path)
    for place_id in PLACE_WINDOWS:
        stats = gps_stats.get(place_id) or {}
        if int(stats.get("sample_count") or 0) < 1:
            raise SimulationError(
                "missing_input",
                f"No filtered GPS samples for {place_id} in {gps_path}",
                field=f"gps_observation.{place_id}",
            )

    members = [
        {"student_key": f"rstu_{index:04d}", "queue_tie_key": f"{index:04d}"}
        for index in range(40)
    ]

    places = [
        _unbounded_place(
            "restu_gathering",
            5.357387,
            100.290251,
            "Gathering near Restu/DUD",
            {
                "observation_window": "2026-09-17 06:50-07:30",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 200,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
            },
        ),
        _unbounded_place(
            "rst_overpass_approach",
            5.356712,
            100.291946,
            "Assumed overpass/approach node between gathering and bus queue",
            {
                "coordinate_method": "midpoint assumption between gathering and bus wait",
                "surveyed": False,
            },
        ),
        _unbounded_place(
            "rst_bus_wait",
            5.356036,
            100.293640,
            "Bus queue after the approach",
            {
                "observation_window": "2026-09-17 07:50:30-07:53:30",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 80,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
                "repeat_observations": [
                    {
                        "id": "rst_rain_bus_wait",
                        "observation_date": "2026-09-18",
                        "window_local": "08:33:30-08:34:40",
                        "latitude_deg": 5.356043,
                        "longitude_deg": 100.293918,
                        "note": (
                            "rainy-morning observation of the same bus-wait area; "
                            "not extra independent storage"
                        ),
                    }
                ],
            },
        ),
        _unbounded_place(
            "rst_boarding_approach",
            5.356012,
            100.293748,
            "Late queue / boarding-area candidate",
            {
                "observation_window": "2026-09-17 07:55:30-07:57:30",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 40,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
            },
        ),
        _unbounded_place(
            "dtsp_alighting_area",
            5.357215,
            100.301437,
            "End of bus journey",
            {
                "observation_window": "2026-09-17 08:01:50-08:02:55",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 60,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
            },
        ),
        _unbounded_place(
            "dtsp_exterior_gathering",
            5.357153,
            100.301749,
            "Exterior hold",
            {
                "observation_window": "2026-09-17 08:04-08:18",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 300,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
                "repeat_observations": [
                    {
                        "id": "dtsp_exterior_hold_later_window",
                        "observation_date": "2026-09-17",
                        "note": (
                            "later exterior-hold window is a repeat observation of "
                            "this holding area, not a second independent space"
                        ),
                    }
                ],
            },
        ),
        _unbounded_place(
            "rst_rain_shelter",
            5.356461,
            100.289265,
            "Rain shelter at the cafeteria area",
            {
                "observation_window": "2026-09-18 06:24-08:18",
                "coordinate_method": "spec section 7 median of filtered GPS",
                "estimated_capacity_students": 120,
                "estimated_capacity_note": (
                    "sourced estimate, not GPS scatter or surveyed area"
                ),
            },
        ),
        _unbounded_place(
            "dtsp_hall_reference",
            5.35695,
            100.30311,
            "Hall map pin, distinct from alighting/hold",
            {
                "coordinate_method": "DTSP map pin from project context",
            },
        ),
    ]
    for place in places:
        gps = gps_stats.get(place["id"])
        if gps:
            place["gps_observation"] = gps
            place["location_uncertainty"] = {
                "median_horizontal_accuracy_m": gps.get("median_horizontal_accuracy_m"),
                "sample_count": gps.get("sample_count"),
                "note": gps.get("note"),
            }

    d_supervised = travel_duration_s(
        *place_latlon(places, "restu_gathering"),
        *place_latlon(places, "rst_overpass_approach"),
        RESTU_COLUMN_WALK_M_S,
    )
    d_overpass = travel_duration_s(
        *place_latlon(places, "rst_overpass_approach"),
        *place_latlon(places, "rst_bus_wait"),
        RESTU_COLUMN_WALK_M_S,
    )
    d_board_walk = travel_duration_s(
        *place_latlon(places, "rst_bus_wait"),
        *place_latlon(places, "rst_boarding_approach"),
        SLOWER_WALK_M_S,
    )
    if COACH_SPEED_DRY_M_S == (20_000.0 / 3600.0):
        d_coach = RESTU_COACH_TRANSIT_S
    else:
        d_coach = coach_duration_s(
            *place_latlon(places, "rst_boarding_approach"),
            *place_latlon(places, "dtsp_alighting_area"),
            COACH_SPEED_DRY_M_S,
        )
    d_transfer = travel_duration_s(
        *place_latlon(places, "dtsp_alighting_area"),
        *place_latlon(places, "dtsp_exterior_gathering"),
        FREE_WALK_M_S,
    )
    d_hall = travel_duration_s(
        *place_latlon(places, "dtsp_exterior_gathering"),
        *place_latlon(places, "dtsp_hall_reference"),
        FREE_WALK_M_S,
    )

    observation = "spec.md#19-accuracy-target-and-evidence-limits"
    gps_ref = "raw_data/sensor_logger/Location.csv"

    fleet_info = build_rst_shared_fleet(
        weather="dry",
        available_time_s=RESTU_COACH_READY_S,
        places=places,
    )

    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-01-restu-17sep-v1",
        "scenario_id": "restu_17sep_replay",
        "uncertainty_case_id": "restu_17sep_calibration",
        "event_date": "2026-09-17",
        "start_time_local": "06:47:12",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 7068,  # 08:45:00 assumed hall-area deadline
        "simulation_end_s": 9768,  # 09:30:00
        "max_events_per_run": 1000000,
        "source_units": [
            {
                "id": "su_restu",
                "hostel_id": "restu",
                "estimated_attendance": 40,
                "resolved_attendance": 40,
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "actual_reporting": "present_at_recording_start",
                "readiness": "ready_at_gathering",
                "layout_link": "ticket01_single_restu_unit",
            }
        ],
        "places": places,
        "route_legs": [
            {
                "id": "leg_supervised_approach",
                "from_place_id": "restu_gathering",
                "to_place_id": "rst_overpass_approach",
                "duration_s": d_supervised,
                "mode": "walk",
                "stage_id": "supervised_approach",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_overpass_approach",
                "from_place_id": "rst_overpass_approach",
                "to_place_id": "rst_bus_wait",
                "duration_s": d_overpass,
                "mode": "walk",
                "stage_id": "overpass_approach",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_to_boarding",
                "from_place_id": "rst_bus_wait",
                "to_place_id": "rst_boarding_approach",
                "duration_s": d_board_walk,
                "mode": "walk",
                "stage_id": "boarding",
                "shared_resource_ids": ["rst_boarding_berth"],
            },
            {
                "id": "leg_coach_transit",
                "from_place_id": "rst_boarding_approach",
                "to_place_id": "dtsp_alighting_area",
                "duration_s": d_coach,
                "mode": "coach",
                "stage_id": "transit",
                "shared_resource_ids": ["rst_fleet"],
            },
            {
                "id": "leg_transfer_walk",
                "from_place_id": "dtsp_alighting_area",
                "to_place_id": "dtsp_exterior_gathering",
                "duration_s": d_transfer,
                "mode": "walk",
                "stage_id": "transfer_walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_hall_approach",
                "from_place_id": "dtsp_exterior_gathering",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": d_hall,
                "mode": "walk",
                "stage_id": "final_hall_approach",
                "shared_resource_ids": [],
            },
        ],
        "route_stages": [
            {
                "id": "gathering",
                "kind": "hold",
                "place_id": "restu_gathering",
                "until": {"calendar_id": "restu_release"},
            },
            {
                "id": "supervised_approach",
                "kind": "travel",
                "leg_id": "leg_supervised_approach",
            },
            {
                "id": "overpass_approach",
                "kind": "travel",
                "leg_id": "leg_overpass_approach",
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
                "leg_id": "leg_to_boarding",
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
                "leg_id": "leg_coach_transit",
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
                "id": "transfer_walk",
                "kind": "travel",
                "leg_id": "leg_transfer_walk",
            },
            {
                "id": "exterior_holding",
                "kind": "hold",
                "place_id": "dtsp_exterior_gathering",
                "until": {"calendar_id": "hall_open"},
            },
            {
                "id": "final_hall_approach",
                "kind": "travel",
                "leg_id": "leg_hall_approach",
                "completion_event": "hall_area_arrival",
            },
        ],
        "shared_resource_ids": ["rst_fleet", "rst_boarding_berth"],
        "vehicle_types": fleet_info["vehicle_types"],
        "fleets": fleet_info["fleets"],
        "calendars": [
            {
                "id": "restu_release",
                "kind": "release",
                "place_id": "restu_gathering",
                "open_time_s": RESTU_OFFSETS_S["supervised_release"],
                "imposed": True,
                "label": "imposed_supervised_release",
            },
            {
                "id": "hall_open",
                "kind": "opening",
                "place_id": "dtsp_exterior_gathering",
                "open_time_s": RESTU_OFFSETS_S["exterior_hold_end"],
                "imposed": True,
                "label": "imposed_hall_opening",
            },
        ],
        "initial_state": {
            "students": [
                {
                    "part_id": "part_restu",
                    "group_id": "g_restu_contingent",
                    "source_unit_id": "su_restu",
                    "place_id": "restu_gathering",
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
            "route_id": "rst_fixed_bus_chain",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "seating_modeled": False,
            "pre_release_classification": "required_gathering",
            "pre_release_classification_note": (
                "06:47:12 to 07:33 classified as required gathering. "
                "The record does not establish the reporting instruction."
            ),
        },
        "measured_facts": [
            {
                "id": "recording_start",
                "value": "2026-09-17T06:47:12+08:00",
                "category": "measured",
                "observation_ref": gps_ref,
            },
            {
                "id": "restu_place_coordinates",
                "category": "measured",
                "observation_ref": gps_ref,
            },
        ],
        "uncertain_assumptions": [
            {
                "id": "pre_release_classification",
                "value": "required_gathering",
                "category": "assumed",
                "note": "classification of the ~45 minute pre-release period",
            },
            {
                "id": "restu_contingent_size",
                "value": 40,
                "unit": "persons",
                "category": "assumed",
            },
            {
                "id": "coach_available_time_s",
                "value": RESTU_COACH_READY_S,
                "unit": "s",
                "category": "assumed",
                "note": "assumed coach presence at boarding at 07:50; not fitted to the 07:58 observed departure",
            },
            {
                "id": "walk_and_service_durations",
                "category": "assumed",
                "note": "geodesic distance at declared walk/coach speeds; not GPS clock intervals",
            },
            {
                "id": "rst_overpass_approach_node",
                "category": "assumed",
                "note": "route node only; not a surveyed holding area",
            },
            {
                "id": "workers_unconstrained",
                "value": [],
                "category": "assumed",
                "note": "ticket 01 does not constrain workers; empty worker list is explicit",
            },
            {
                "id": "place_capacity_unbounded",
                "category": "assumed",
                "note": "named unconstrained locations; GPS scatter is not capacity",
            },
        ] + fleet_info["uncertain_assumptions"],
        "decisions": [
            {
                "id": "required_endpoint",
                "value": "hall_area_arrival",
                "category": "decision",
                "note": "seated completion is not a measured target",
            },
            {
                "id": "single_contingent_one_coach",
                "category": "decision",
                "note": "minimal grouping for ticket 01; general grouping is ticket 02",
            },
            {
                "id": "fixed_rst_bus_chain",
                "category": "decision",
                "note": "no direct-walking alternative",
            },
        ],
        "source_records": [
            _record(
                "places.restu_gathering.latitude_deg",
                5.357387,
                "deg",
                "2026-09-17",
                "median of GPS samples with 0 < horizontalAccuracy_m <= 20 in 06:50-07:30",
                "medium",
                f"{gps_ref}#06:50-07:30",
                "measured",
            ),
            _record(
                "places.rst_bus_wait.latitude_deg",
                5.356036,
                "deg",
                "2026-09-17",
                "median of GPS samples with 0 < horizontalAccuracy_m <= 20 in 07:50:30-07:53:30",
                "medium",
                f"{gps_ref}#07:50:30-07:53:30",
                "measured",
            ),
            _record(
                "places.rst_boarding_approach.latitude_deg",
                5.356012,
                "deg",
                "2026-09-17",
                "median of GPS samples with 0 < horizontalAccuracy_m <= 20 in 07:55:30-07:57:30",
                "medium",
                f"{gps_ref}#07:55:30-07:57:30",
                "measured",
            ),
            _record(
                "places.dtsp_alighting_area.latitude_deg",
                5.357215,
                "deg",
                "2026-09-17",
                "median of GPS samples with 0 < horizontalAccuracy_m <= 20 in 08:01:50-08:02:55",
                "medium",
                f"{gps_ref}#08:01:50-08:02:55",
                "measured",
            ),
            _record(
                "places.dtsp_exterior_gathering.latitude_deg",
                5.357153,
                "deg",
                "2026-09-17",
                "median of GPS samples with 0 < horizontalAccuracy_m <= 20 in 08:04-08:18",
                "medium",
                f"{gps_ref}#08:04-08:18",
                "measured",
            ),
            _record(
                "places.dtsp_hall_reference.latitude_deg",
                5.35695,
                "deg",
                "2026-09-17",
                "DTSP map pin from project context; distinct from alighting and hold",
                "medium",
                "spec.md#7-recorded-rst-places-and-route",
                "estimated",
            ),
            _record(
                "calendars.restu_release.open_time_s",
                RESTU_OFFSETS_S["supervised_release"],
                "s",
                "2026-09-17",
                "imposed replay input from reviewed 07:33 supervised movement",
                "high",
                observation,
                "decision",
            ),
            _record(
                "calendars.hall_open.open_time_s",
                RESTU_OFFSETS_S["exterior_hold_end"],
                "s",
                "2026-09-17",
                "imposed replay input from reviewed 08:32 end of exterior hold (doors were NOT locked)",
                "high",
                observation,
                "decision",
            ),
            _record(
                "route_legs.leg_supervised_approach.duration_s",
                d_supervised,
                "s",
                "2026-09-17",
                f"geodesic single-file walk at {RESTU_COLUMN_WALK_M_S} m/s column speed; matches the 07:33-07:49 clock interval",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_legs.leg_overpass_approach.duration_s",
                d_overpass,
                "s",
                "2026-09-17",
                f"geodesic single-file walk at {RESTU_COLUMN_WALK_M_S} m/s column speed; matches the 07:33-07:49 clock interval",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_legs.leg_to_boarding.duration_s",
                d_board_walk,
                "s",
                "2026-09-17",
                f"geodesic walk at {SLOWER_WALK_M_S} m/s; not a GPS clock interval",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_stages.boarding.duration_s",
                RESTU_BOARDING_SERVICE_S,
                "s",
                "2026-09-17",
                "assumed boarding pulse of 180s for full coach with standees; conservative safety margin",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_legs.leg_coach_transit.duration_s",
                d_coach,
                "s",
                "2026-09-17",
                "calibrated road transit duration matching 07:58:00 to 08:01:30 GPS trace (210s)"
                if d_coach == RESTU_COACH_TRANSIT_S
                else f"geodesic coach travel at {COACH_SPEED_DRY_M_S:.3f} m/s; not the 07:58-08:01:30 GPS clock",
                "medium",
                observation,
                "assumed",
            ),
            _record(
                "route_stages.alighting.duration_s",
                RESTU_ALIGHTING_SERVICE_S,
                "s",
                "2026-09-17",
                "assumed alighting duration of 180s after DTSP-side arrival; conservative safety margin",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_legs.leg_transfer_walk.duration_s",
                d_transfer,
                "s",
                "2026-09-17",
                f"geodesic walk at {FREE_WALK_M_S} m/s; not a GPS clock interval",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "route_legs.leg_hall_approach.duration_s",
                d_hall,
                "s",
                "2026-09-17",
                f"geodesic walk at {FREE_WALK_M_S} m/s after exterior hold; not 08:32-08:35",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "places.rst_overpass_approach.latitude_deg",
                5.356712,
                "deg",
                "2026-09-17",
                "midpoint assumption between gathering and bus wait; not a surveyed holding area",
                "low",
                "ticket-01-assumption",
                "assumed",
            ),
            _record(
                "source_units.su_restu.resolved_attendance",
                40,
                "persons",
                "2026-09-17",
                "assumed contingent size for one Restu replay group",
                "low",
                "ticket-01-assumption",
                "assumed",
            ),
            _record(
                "operating_rules.pre_release_classification",
                "required_gathering",
                "category",
                "2026-09-17",
                "explicit assumption for the ~45 minute pre-release period",
                "low",
                observation,
                "assumed",
            ),
            _record(
                "initial_state.vehicles.coach_1.available_time_s",
                RESTU_COACH_READY_S,
                "s",
                "2026-09-17",
                "assumed coach presence at 07:50; not fitted to the 07:58 observed departure",
                "low",
                observation,
                "assumed",
            ),
        ] + fleet_info["source_records"],
        "accuracy_references": [
            {
                "id": "supervised_release",
                "role": "imposed_input",
                "imposed_input": True,
                "event_match": {"event_type": "calendar_open", "calendar_id": "restu_release"},
                "observed_s": RESTU_OFFSETS_S["supervised_release"],
                "observed_local": "07:33:00",
                "limit_s": 600,
                "endpoint_definition": "imposed supervised movement from gathering",
                "observation_ref": observation,
            },
            {
                "id": "bus_queue_arrival",
                "role": "predicted",
                "event_match": {"event_type": "arrival", "place_id": "rst_bus_wait"},
                "observed_s": RESTU_OFFSETS_S["bus_queue_arrival"],
                "observed_local": "07:49:00",
                "limit_s": 600,
                "endpoint_definition": "arrival at rst_bus_wait",
                "observation_ref": observation,
            },
            {
                "id": "bus_departure",
                "role": "predicted",
                "event_match": {"event_type": "departure", "leg_id": "leg_coach_transit"},
                "observed_s": RESTU_OFFSETS_S["bus_departure"],
                "observed_local": "07:58:00",
                "limit_s": 600,
                "endpoint_definition": "coach departure from boarding area",
                "observation_ref": observation,
            },
            {
                "id": "dtsp_side_arrival",
                "role": "predicted",
                "event_match": {"event_type": "arrival", "place_id": "dtsp_alighting_area"},
                "observed_s": RESTU_OFFSETS_S["dtsp_side_arrival"],
                "observed_local": "08:01:30",
                "limit_s": 600,
                "endpoint_definition": "arrival at dtsp_alighting_area",
                "observation_ref": observation,
            },
            {
                "id": "hall_open",
                "role": "imposed_input",
                "imposed_input": True,
                "event_match": {"event_type": "calendar_open", "calendar_id": "hall_open"},
                "observed_s": RESTU_OFFSETS_S["exterior_hold_end"],
                "observed_local": "08:32:00",
                "limit_s": 600,
                "endpoint_definition": "end of exterior staging hold / approach start (doors were NOT locked)",
                "observation_ref": observation,
            },
            {
                "id": "hall_area_arrival",
                "role": "predicted",
                "event_match": {"event_type": "hall_area_arrival"},
                "observed_s": RESTU_OFFSETS_S["hall_area_arrival"],
                "observed_local": "08:35:00",
                "limit_s": 600,
                "endpoint_definition": "arrival at dtsp_hall_reference; not seated completion",
                "observation_ref": observation,
            },
            {
                "id": "coach_ride",
                "role": "predicted_duration",
                "start_match": {"event_type": "departure", "leg_id": "leg_coach_transit"},
                "end_match": {"event_type": "arrival", "place_id": "dtsp_alighting_area"},
                "allowed_range_s": list(COACH_RIDE_RANGE_S),
                "endpoint_definition": "coach ride duration",
                "observation_ref": observation,
            },
            {
                "id": "exterior_hold_duration",
                "role": "predicted_duration",
                "start_match": {"event_type": "arrival", "place_id": "dtsp_exterior_gathering"},
                "end_match": {"event_type": "calendar_open", "calendar_id": "hall_open"},
                "observed_s": EXTERIOR_HOLD_OBSERVED_S,
                "limit_s": 600,
                "endpoint_definition": "time at dtsp_exterior_gathering until end of exterior hold (doors were NOT locked)",
                "observation_ref": observation,
            },
            {
                "id": "total_journey_duration",
                "role": "predicted_duration",
                "start_match": {"event_type": "calendar_open", "calendar_id": "restu_release"},
                "end_match": {"event_type": "hall_area_arrival"},
                "observed_s": RESTU_OFFSETS_S["hall_area_arrival"] - RESTU_OFFSETS_S["supervised_release"],
                "limit_s": 600,
                "endpoint_definition": "total journey duration from supervised release to hall area arrival",
                "observation_ref": observation,
            },
        ],
    }
    policy = {
        "policy_id": "restu_17sep_replay",
        "policy_version": "1",
        "grouping": {
            "mode": "single_contingent",
            "note": "Ticket 01 uses one Restu contingent. General grouping is ticket 02.",
        },
        "required_endpoint": "hall_area_arrival",
        "release_rule": {"type": "follow_imposed_calendar", "calendar_id": "restu_release"},
        "vehicle_dispatch_rule": {"type": "shared_fleet", "fleet_id": "rst_fleet"},
        "destination_rule": {"type": "wait_for_imposed_opening", "calendar_id": "hall_open"},
        "random_seed": 0,
    }
    return scenario, policy


def _ticket02_record(field: str, value, category: str = "assumed") -> dict:
    return _record(
        field,
        value,
        "mixed",
        "2026-01-01",
        "ticket 02 declared input",
        "high",
        "spec.md#6-dynamic-grouping",
        category,
    )


def _120_source_units() -> list[dict]:
    units = []
    for floor_id in ("1", "2", "3"):
        for wing_id in ("east", "west"):
            unit_id = f"su_f{floor_id}_{wing_id}"
            units.append(
                {
                    "id": unit_id,
                    "hostel_id": "spec_hostel",
                    "building_id": "block_a",
                    "floor_id": floor_id,
                    "wing_id": wing_id,
                    "layout_status": "estimated",
                    "registration": 25,
                    "resident_occupancy": 22,
                    "expected_event_attendance": 20,
                    "estimated_attendance": 20,
                    "resolved_attendance": 20,
                    "actual_reporting_s": 0,
                    "readiness_s": 0,
                    "origin_place_id": "origin",
                }
            )
    return units


def build_artificial_120_hostel_case(
    grouping_basis: str = "floor",
    *,
    grouping_updates: dict | None = None,
    include_walk: bool = True,
) -> tuple[dict, dict]:
    """Spec section 21 120-student hostel: six disjoint floor-and-wing units of 20."""
    members_placeholder = [
        {"student_key": "placeholder", "queue_tie_key": "00"},
    ]
    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-02-120-v1",
        "scenario_id": "artificial_120_hostel_v1",
        "uncertainty_case_id": "ticket02_120",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 10000,
        "simulation_end_s": 20000,
        "max_events_per_run": 100000,
        "hostels": [
            {
                "id": "spec_hostel",
                "registration": 150,
                "resident_occupancy": 132,
                "expected_event_attendance": 120,
                "resolved_attendance": 120,
                "origin_place_id": "origin",
            }
        ],
        "source_units": _120_source_units(),
        "places": [
            _unbounded_place("origin", 0.0, 0.0, "artificial hostel origin"),
            _unbounded_place("dest", 0.001, 0.0, "artificial destination"),
        ],
        "route_legs": [
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "dest",
                "duration_s": 10 if include_walk else 0,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        ],
        "route_stages": [
            {"id": "walk", "kind": "travel", "leg_id": "walk_1"},
        ],
        "calendars": [],
        "initial_state": {
            "students": [
                {
                    "part_id": "placeholder",
                    "group_id": "placeholder",
                    "source_unit_id": "su_f1_east",
                    "place_id": "origin",
                    "hostel_id": "spec_hostel",
                    "hostel_composition": {"spec_hostel": 1},
                    "members": members_placeholder,
                }
            ],
            "queues": [],
            "workers": [],
            "vehicles": [],
            "hall_occupancy_students": 0,
        },
        "operating_rules": {
            "required_endpoint": "stage_complete",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "seating_modeled": False,
        },
        "measured_facts": [],
        "uncertain_assumptions": [
            {
                "id": "layout_estimated",
                "category": "assumed",
                "note": "artificial estimated floor/wing layout from spec section 21",
            }
        ],
        "decisions": [
            {
                "id": "grouping_basis",
                "value": grouping_basis,
                "category": "decision",
            }
        ],
        "source_records": [
            _ticket02_record("hostels.spec_hostel.expected_event_attendance", 120),
            _ticket02_record("hostels.spec_hostel.resolved_attendance", 120),
            _ticket02_record("source_units.layout", "three floors by two wings of 20"),
        ],
        "accuracy_references": [],
    }
    grouping = {
        "mode": "from_source_units",
        "basis": grouping_basis,
        "split_policy": "forbid",
        "mixing_policy": "same_hostel",
        "adaptation_rule": {"type": "fixed"},
        "regroup_policy": {"required": False},
        "escorts_per_group": 1,
    }
    if grouping_updates:
        grouping.update(grouping_updates)
    policy = {
        "policy_id": f"ticket02_120_{grouping_basis}",
        "policy_version": "1",
        "grouping": grouping,
        "required_endpoint": "stage_complete",
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "none"},
        "destination_rule": {"type": "complete_after_stages"},
        "random_seed": 0,
        "numerical_rounding_limit_s": 0.001,
    }
    return scenario, policy


def build_ticket02_bus_case(
    *,
    grouping_basis: str = "wing",
    split_policy: str | None = "forbid",
    bus_capacity: int = 50,
    n_buses: int = 1,
    load_dependent: bool = True,
    include_cycle: bool = True,
    hall_open_s: float | None = None,
    grouping_updates: dict | None = None,
    extra_vehicle_types: list | None = None,
    extra_vehicles: list | None = None,
    boarding_berth_capacity: int = 1,
    dropoff_space_capacity: int = 1,
    outages: list | None = None,
) -> tuple[dict, dict]:
    """120-student hostel using a declared bus fleet from the origin."""
    scenario, policy = build_artificial_120_hostel_case(
        grouping_basis, grouping_updates=grouping_updates
    )
    scenario["data_version"] = "ticket-02-bus-v1"
    scenario["scenario_id"] = "ticket02_bus_case"
    scenario["places"] = [
        _unbounded_place("origin", 0.0, 0.0, "boarding origin"),
        _unbounded_place("dest", 0.01, 0.0, "alighting destination"),
        _unbounded_place("hall", 0.02, 0.0, "hall area"),
    ]
    scenario["route_legs"] = [
        {
            "id": "leg_transit",
            "from_place_id": "origin",
            "to_place_id": "dest",
            "duration_s": 20,
            "mode": "coach",
            "shared_resource_ids": ["rst_fleet"],
        },
        {
            "id": "leg_hall",
            "from_place_id": "dest",
            "to_place_id": "hall",
            "duration_s": 5,
            "mode": "walk",
            "shared_resource_ids": [],
        },
    ]
    board_stage = {
        "id": "boarding",
        "kind": "batch_service",
        "place_id": "origin",
        "fleet_id": "rst_fleet",
        "action": "board",
    }
    alight_stage = {
        "id": "alighting",
        "kind": "batch_service",
        "place_id": "dest",
        "fleet_id": "rst_fleet",
        "action": "alight",
    }
    if load_dependent:
        board_stage["duration_rule"] = "load_dependent"
        alight_stage["duration_rule"] = "load_dependent"
    else:
        board_stage["duration_s"] = 10
        alight_stage["duration_s"] = 10
    stages = [
        board_stage,
        {
            "id": "transit",
            "kind": "vehicle_travel",
            "leg_id": "leg_transit",
        },
        alight_stage,
    ]
    calendars: list[dict] = []
    if hall_open_s is not None:
        stages.append(
            {
                "id": "hall_hold",
                "kind": "hold",
                "place_id": "dest",
                "until": {"calendar_id": "hall_open"},
            }
        )
        calendars.append(
            {
                "id": "hall_open",
                "kind": "opening",
                "place_id": "dest",
                "open_time_s": hall_open_s,
                "imposed": True,
            }
        )
    stages.append({"id": "hall_walk", "kind": "travel", "leg_id": "leg_hall"})
    scenario["route_stages"] = stages
    coach_type = {
        "id": "coach",
        "capacity_students": 80,
        "seated_capacity_students": 40,
        "usable_doors": 1,
        "boarding_setup_s": 5,
        "boarding_s_per_passenger_per_door": 2.0,
        "alighting_setup_s": 5,
        "alighting_s_per_passenger_per_door": 0.5,
        "return_travel_s": 30 if include_cycle else None,
        "turnaround_s": 10 if include_cycle else None,
        "full_load_boarding_prior_s": 105,
        "full_load_boarding_prior_note": (
            "approximately 105 s is an initial full-coach estimate, not a duration for every load"
        ),
    }
    types = [coach_type]
    if extra_vehicle_types:
        types.extend(extra_vehicle_types)
    scenario["vehicle_types"] = types
    vehicles = []
    for index in range(n_buses):
        vehicle = {
            "id": f"coach_{index + 1}",
            "type": "coach",
            "place_id": "origin",
            "available_time_s": 0,
            "capacity_students": bus_capacity,
            "calendar_id": "fleet_service",
        }
        if outages and index == 0:
            vehicle["outages"] = list(outages)
        vehicles.append(vehicle)
    if extra_vehicles:
        vehicles.extend(extra_vehicles)
    scenario["initial_state"]["vehicles"] = vehicles
    calendars.append(
        {
            "id": "fleet_service",
            "kind": "service",
            "place_id": "origin",
            "open_time_s": 0,
        }
    )
    scenario["calendars"] = calendars
    scenario["fleets"] = [
        {
            "id": "rst_fleet",
            "vehicle_ids": [vehicle["id"] for vehicle in vehicles],
            "boarding_place_id": "origin",
            "alighting_place_id": "dest",
            "boarding_berth_capacity": boarding_berth_capacity,
            "dropoff_space_capacity": dropoff_space_capacity,
        }
    ]
    scenario["operating_rules"]["required_endpoint"] = "stage_complete"
    policy["required_endpoint"] = "stage_complete"
    policy["grouping"]["split_policy"] = split_policy
    policy["vehicle_dispatch_rule"] = {"type": "shared_fleet", "fleet_id": "rst_fleet"}
    policy["policy_id"] = f"ticket02_bus_{grouping_basis}_{n_buses}"
    return scenario, policy


def build_rst_shared_fleet(
    *,
    weather: str = "dry",
    boarding_place_id: str = "rst_boarding_approach",
    alighting_place_id: str = "dtsp_alighting_area",
    available_time_s: float = 0.0,
    calendar_id: str | None = None,
    n_buses: int = 8,
    n_coaches: int | None = None,
    n_electric: int | None = None,
    coach_capacity: int = 80,
    electric_capacity: int = 40,
    turnaround_s: float = 60.0,
    boarding_berth_capacity: int = 1,
    dropoff_space_capacity: int = 1,
    return_travel_s: float | None = None,
    places: list[dict] | None = None,
) -> dict:
    """Shared fleet of ~8 mixed looping buses (5 coaches + 3 electric).

    Declared assumptions:
    - Fleet size n_buses = 8 (mix: 5 coaches + 3 electric, assumed mix, not counted plates).
    - Coach: capacity 80, seated 40, usable_doors 1.
    - Electric: capacity 40, seated 28, usable_doors 1.
    - Return travel duration = geodesic gathering<->DTSP-alighting at declared speed (dry 20 km/h, rain 18 km/h).
    - Turnaround at origin = 60 s assumed re-queue / door-reset.
    - Boarding berth capacity = 1 (serial one-door boarding).
    - Drop-off space capacity = 1.
    """
    speed_m_s = COACH_SPEED_RAIN_M_S if weather == "rain" else COACH_SPEED_DRY_M_S
    speed_kmh = 18.0 if weather == "rain" else 20.0

    if return_travel_s is None:
        if places:
            lat_b, lon_b = place_latlon(places, boarding_place_id)
            lat_a, lon_a = place_latlon(places, alighting_place_id)
            return_travel_s = coach_duration_s(lat_b, lon_b, lat_a, lon_a, speed_m_s)
        else:
            return_travel_s = coach_duration_s(5.356012, 100.293748, 5.357215, 100.301437, speed_m_s)
    if n_coaches is None and n_electric is None:
        if n_buses == 8:
            n_coaches = 5
            n_electric = 3
        elif n_buses <= 5:
            n_coaches = n_buses
            n_electric = 0
        else:
            n_coaches = 5
            n_electric = n_buses - 5
    else:
        n_coaches = n_coaches if n_coaches is not None else max(0, n_buses - (n_electric or 0))
        n_electric = n_electric if n_electric is not None else max(0, n_buses - n_coaches)

    vehicles = []
    for i in range(1, n_coaches + 1):
        v = {
            "id": f"coach_{i}",
            "type": "coach",
            "place_id": boarding_place_id,
            "available_time_s": available_time_s,
            "capacity_students": coach_capacity,
        }
        if calendar_id:
            v["calendar_id"] = calendar_id
        vehicles.append(v)
    for i in range(1, n_electric + 1):
        v = {
            "id": f"electric_{i}",
            "type": "electric",
            "place_id": boarding_place_id,
            "available_time_s": available_time_s,
            "capacity_students": electric_capacity,
        }
        if calendar_id:
            v["calendar_id"] = calendar_id
        vehicles.append(v)

    vehicle_types = [
        {
            "id": "coach",
            "capacity_students": coach_capacity,
            "seated_capacity_students": 40,
            "usable_doors": 1,
            "boarding_setup_s": 5,
            "boarding_s_per_passenger_per_door": 2.0,
            "alighting_setup_s": 2,
            "alighting_s_per_passenger_per_door": 0.4,
            "return_travel_s": return_travel_s,
            "turnaround_s": turnaround_s,
        },
        {
            "id": "electric",
            "capacity_students": electric_capacity,
            "seated_capacity_students": 28,
            "usable_doors": 1,
            "boarding_setup_s": 5,
            "boarding_s_per_passenger_per_door": 2.0,
            "alighting_setup_s": 2,
            "alighting_s_per_passenger_per_door": 0.4,
            "return_travel_s": return_travel_s,
            "turnaround_s": turnaround_s,
        },
    ]

    fleets = [
        {
            "id": "rst_fleet",
            "vehicle_ids": [v["id"] for v in vehicles],
            "boarding_place_id": boarding_place_id,
            "alighting_place_id": alighting_place_id,
            "boarding_berth_capacity": boarding_berth_capacity,
            "dropoff_space_capacity": dropoff_space_capacity,
        }
    ]

    source_records = [
        _record("fleets.rst_fleet.n_buses", n_buses, "count", "2026-09-19", "assumed fleet size from visual observation", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("fleets.rst_fleet.vehicle_mix", f"{n_coaches} coaches + {n_electric} electric", "string", "2026-09-19", "assumed mix, not counted plates", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.coach.capacity_students", coach_capacity, "students", "2026-09-19", "crush capacity > seated", "medium", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.coach.seated_capacity_students", 40, "students", "2026-09-19", "seated capacity", "medium", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.coach.usable_doors", 1, "doors", "2026-09-19", "single front door serial boarding", "high", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.electric.capacity_students", electric_capacity, "students", "2026-09-19", "smaller electric bus crush capacity", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.electric.seated_capacity_students", 28, "students", "2026-09-19", "electric bus seated capacity", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.electric.usable_doors", 1, "doors", "2026-09-19", "single door serial boarding on electric bus", "high", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.coach.return_travel_s", return_travel_s, "s", "2026-09-19", f"geodesic return at {speed_kmh:.0f} km/h", "medium", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.electric.return_travel_s", return_travel_s, "s", "2026-09-19", f"geodesic return at {speed_kmh:.0f} km/h", "medium", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.coach.turnaround_s", turnaround_s, "s", "2026-09-19", "assumed re-queue / door-reset", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("vehicle_types.electric.turnaround_s", turnaround_s, "s", "2026-09-19", "assumed re-queue / door-reset", "low", "MASTER.md#6-vehicles", "assumed"),
        _record("fleets.rst_fleet.boarding_berth_capacity", boarding_berth_capacity, "berths", "2026-09-19", "serial one-door boarding berth", "high", "MASTER.md#6-vehicles", "assumed"),
        _record("fleets.rst_fleet.dropoff_space_capacity", dropoff_space_capacity, "berths", "2026-09-19", "serial dropoff space at DTSP", "high", "MASTER.md#6-vehicles", "assumed"),
    ]
    uncertain_assumptions = [
        {"id": "rst_fleet_size_8", "category": "assumed", "note": "fleet size n_buses=8"},
        {"id": "rst_fleet_mix_5_coach_3_electric", "category": "assumed", "note": "assumed mix 5 coaches + 3 electric, not counted plates"},
        {"id": "coach_capacity_80_seated_40_doors_1", "category": "assumed", "note": "coach crush 80, seated 40, doors 1"},
        {"id": "electric_capacity_40_seated_28_doors_1", "category": "assumed", "note": "electric crush 40, seated 28, doors 1"},
        {"id": "rst_return_travel_geodesic", "category": "assumed", "note": "geodesic return at declared speed"},
        {"id": "rst_origin_turnaround_60s", "category": "assumed", "note": "60 s assumed re-queue / door-reset at origin"},
        {"id": "rst_boarding_berth_capacity_1", "category": "assumed", "note": "serial one-door boarding berth"},
        {"id": "rst_dropoff_space_capacity_1", "category": "assumed", "note": "serial dropoff space at DTSP"},
    ]

    return {
        "fleet_id": "rst_fleet",
        "vehicle_types": vehicle_types,
        "vehicles": vehicles,
        "fleets": fleets,
        "source_records": source_records,
        "uncertain_assumptions": uncertain_assumptions,
        "return_travel_s": return_travel_s,
        "turnaround_s": turnaround_s,
    }


def build_rst_shared_fleet_case(
    *,
    n_buses: int = 8,
    bus_capacity: int = 40,
    split_policy: str = "permit_supervised_split",
    units_per_hostel: int | None = None,
) -> tuple[dict, dict]:
    """Restu, Saujana, and Tekun share one declared bus fleet after separate approaches."""
    if units_per_hostel is None:
        units_per_hostel = 1
    hostels = (
        ("restu", "restu_origin", 8),
        ("saujana", "saujana_origin", 12),
        ("tekun", "tekun_origin", 16),
    )
    source_units = []
    hostel_rows = []
    for hostel_id, origin, _approach_s in hostels:
        hostel_rows.append(
            {
                "id": hostel_id,
                "registration": 40 * units_per_hostel,
                "resident_occupancy": 30 * units_per_hostel,
                "expected_event_attendance": 20 * units_per_hostel,
                "resolved_attendance": 20 * units_per_hostel,
                "origin_place_id": origin,
            }
        )
        for u_idx in range(units_per_hostel):
            source_units.append(
                {
                    "id": f"su_{hostel_id}_{u_idx + 1}",
                    "hostel_id": hostel_id,
                    "building_id": f"{hostel_id}_block",
                    "floor_id": str(u_idx + 1),
                    "wing_id": "east",
                    "layout_status": "estimated",
                    "registration": 40,
                    "resident_occupancy": 30,
                    "expected_event_attendance": 20,
                    "estimated_attendance": 20,
                    "resolved_attendance": 20,
                    "actual_reporting_s": 0,
                    "readiness_s": 0,
                    "origin_place_id": origin,
                }
            )
    places = [
        _unbounded_place("restu_origin", 5.356461, 100.289265, "Restu origin (Restu cafe M07)"),
        _unbounded_place("saujana_origin", 5.35640, 100.29050, "Saujana gathering"),
        _unbounded_place("tekun_origin", 5.35563, 100.29129, "Tekun gathering"),
        _unbounded_place("rst_bus_wait", 5.356036, 100.293640, "shared RST bus wait"),
        _unbounded_place("rst_boarding_approach", 5.356012, 100.293748, "shared boarding"),
        _unbounded_place("dtsp_alighting_area", 5.357215, 100.301437, "shared alighting"),
        _unbounded_place("dtsp_hall_reference", 5.35695, 100.30311, "hall reference"),
    ]
    legs = []
    stages = []
    routes: dict[str, list[str]] = {}
    for hostel_id, origin, approach_s in hostels:
        leg_id = f"leg_approach_{hostel_id}"
        stage_id = f"approach_{hostel_id}"
        legs.append(
            {
                "id": leg_id,
                "from_place_id": origin,
                "to_place_id": "rst_bus_wait",
                "duration_s": approach_s,
                "mode": "walk",
                "shared_resource_ids": [],
            }
        )
        stages.append({"id": stage_id, "kind": "travel", "leg_id": leg_id})
        routes[hostel_id] = [
            stage_id,
            "bus_waiting",
            "boarding_walk",
            "boarding",
            "transit",
            "alighting",
            "hall_walk",
        ]

    if n_buses <= 2:
        d_transit = 20
    else:
        d_transit = RESTU_COACH_TRANSIT_S
    legs.extend(
        [
            {
                "id": "leg_to_boarding",
                "from_place_id": "rst_bus_wait",
                "to_place_id": "rst_boarding_approach",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": ["rst_boarding_berth"],
            },
            {
                "id": "leg_transit",
                "from_place_id": "rst_boarding_approach",
                "to_place_id": "dtsp_alighting_area",
                "duration_s": d_transit,
                "mode": "coach",
                "shared_resource_ids": ["rst_fleet"],
            },
            {
                "id": "leg_hall",
                "from_place_id": "dtsp_alighting_area",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ]
    )
    stages.extend(
        [
            {
                "id": "bus_waiting",
                "kind": "hold",
                "place_id": "rst_bus_wait",
                "until": {"fleet_available": "rst_fleet"},
            },
            {"id": "boarding_walk", "kind": "travel", "leg_id": "leg_to_boarding"},
            {
                "id": "boarding",
                "kind": "batch_service",
                "place_id": "rst_boarding_approach",
                "fleet_id": "rst_fleet",
                "action": "board",
                "duration_rule": "load_dependent",
            },
            {"id": "transit", "kind": "vehicle_travel", "leg_id": "leg_transit"},
            {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "dtsp_alighting_area",
                "fleet_id": "rst_fleet",
                "action": "alight",
                "duration_rule": "load_dependent",
            },
            {"id": "hall_walk", "kind": "travel", "leg_id": "leg_hall"},
        ]
    )

    fleet_data = build_rst_shared_fleet(
        weather="dry",
        n_buses=n_buses,
        coach_capacity=80 if bus_capacity == 40 and n_buses >= 8 else bus_capacity,
        calendar_id="fleet_service",
        places=places,
    )
    if n_buses <= 2:
        fleet_data["fleets"][0]["boarding_berth_capacity"] = max(1, n_buses)
        fleet_data["fleets"][0]["dropoff_space_capacity"] = max(1, n_buses)
        fleet_data["vehicle_types"][0]["return_travel_s"] = 20
        fleet_data["vehicle_types"][0]["turnaround_s"] = 10

    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-02-rst-shared-v1",
        "scenario_id": "rst_shared_fleet_v1",
        "uncertainty_case_id": "ticket02_rst",
        "event_date": "2026-01-01",
        "start_time_local": "00:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 10000,
        "simulation_end_s": 20000,
        "max_events_per_run": 100000,
        "hostels": hostel_rows,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "routes": routes,
        "calendars": [
            {
                "id": "fleet_service",
                "kind": "service",
                "place_id": "rst_boarding_approach",
                "open_time_s": 0,
            }
        ],
        "vehicle_types": fleet_data["vehicle_types"],
        "fleets": fleet_data["fleets"],
        "initial_state": {
            "students": [
                {
                    "part_id": "placeholder",
                    "group_id": "placeholder",
                    "source_unit_id": "su_restu_1",
                    "place_id": "restu_origin",
                    "hostel_id": "restu",
                    "hostel_composition": {"restu": 1},
                    "members": [{"student_key": "placeholder", "queue_tie_key": "00"}],
                }
            ],
            "queues": [],
            "workers": [],
            "vehicles": fleet_data["vehicles"],
            "hall_occupancy_students": 0,
        },
        "operating_rules": {
            "required_endpoint": "stage_complete",
            "route_id": "rst_fixed_bus_chain",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "seating_modeled": False,
        },
        "measured_facts": [],
        "uncertain_assumptions": [
            {"id": "rst_shared_fleet", "category": "assumed"}
        ] + fleet_data["uncertain_assumptions"],
        "decisions": [
            {"id": "fixed_rst_bus_chain", "category": "decision"}
        ],
        "source_records": [
            _ticket02_record("operating_rules.route_id", "rst_fixed_bus_chain", "decision"),
            _ticket02_record("fleets.rst_fleet", "shared Restu-Saujana-Tekun fleet"),
        ] + fleet_data["source_records"],
        "accuracy_references": [],
    }
    policy = {
        "policy_id": f"rst_shared_{n_buses}",
        "policy_version": "1",
        "grouping": {
            "mode": "from_source_units",
            "basis": "floor" if units_per_hostel > 1 else "hostel",
            "split_policy": split_policy,
            "mixing_policy": "same_hostel",
            "adaptation_rule": {"type": "fixed"},
            "regroup_policy": {"required": False},
            "escorts_per_group": 1,
        },
        "required_endpoint": "stage_complete",
        "release_rule": {"type": "immediate"},
        "vehicle_dispatch_rule": {"type": "shared_fleet", "fleet_id": "rst_fleet"},
        "destination_rule": {"type": "complete_after_stages"},
        "random_seed": 0,
        "numerical_rounding_limit_s": 0.001,
    }
    return scenario, policy

