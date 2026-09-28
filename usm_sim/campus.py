"""Eight-hostel origin registry and whole-campus scenario data.

Hostel names, coordinates, demand, walking estimates, and shared path IDs live
here. The movement engine does not branch on hostel identity.
"""

from __future__ import annotations

from typing import Any, Mapping
from usm_sim.constants import FORMAT_VERSION, TIMEZONE_NAME
from usm_sim.grouping import allocate_integer_counts

# Free walking, not Restu's congested column speed.
FREE_WALK_M_S = 1.3
SLOWER_WALK_M_S = 0.85
RESTU_COLUMN_WALK_M_S = 0.42
RESTU_BOARDING_SERVICE_S = 180
RESTU_ALIGHTING_SERVICE_S = 180
RESTU_COACH_TRANSIT_S = 210

OFFICIAL_2026_HOSTEL_COUNTS: dict[str, int] = {
    "restu": 1044,
    "saujana": 610,
    "tekun": 508,
    "aman_damai": 410,
    "bakti_fajar_permai": 341,
    "indah_kembara": 244,
    "cahaya_gemilang": 193,
    "fajar_harapan": 193,
}

RST_HOSTEL_IDS = ("restu", "saujana", "tekun")
WALK_HOSTEL_IDS = (
    "indah_kembara",
    "aman_damai",
    "bakti_fajar_permai",
    "cahaya_gemilang",
    "fajar_harapan",
)
NORTH_WALK_HOSTEL_IDS = ("cahaya_gemilang", "bakti_fajar_permai")
SOUTH_WALK_HOSTEL_IDS = ("indah_kembara", "aman_damai", "fajar_harapan")
HOSTEL_IDS = RST_HOSTEL_IDS + WALK_HOSTEL_IDS

SHARED_PATH_JALAN_UNIVERSITI_EAST = "path_jalan_universiti_east"
SHARED_FOYER_PASSAGE = "dtsp_foyer_passage"

DESTINATION_TAIL_BUS = (
    "transfer_walk",
    "carpark_headcount",
    "exterior_holding",
    "final_hall_approach",
    "door_approach_a",
    "entrance_door_a",
    "foyer_passage",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_NORTH = (
    "walk_to_north_plaza",
    "north_plaza_headcount",
    "north_plaza_holding",
    "final_hall_approach_north",
    "door_approach_a",
    "entrance_door_a",
    "foyer_passage",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_SOUTH = (
    "walk_to_south_plaza",
    "south_plaza_headcount",
    "south_plaza_holding",
    "final_hall_approach_south",
    "door_approach_b",
    "entrance_door_b",
    "foyer_passage_walk",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_WALK = DESTINATION_TAIL_SOUTH
DESTINATION_TAIL_DOOR_A = (
    "transfer_walk",
    "carpark_headcount",
    "exterior_holding",
    "final_hall_approach",
    "door_approach_a",
    "entrance_door_a",
    "foyer_passage",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_DOOR_B = (
    "transfer_walk",
    "carpark_headcount",
    "exterior_holding",
    "final_hall_approach",
    "door_approach_b",
    "entrance_door_b",
    "foyer_passage_walk",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_DOOR_D = (
    "transfer_walk",
    "carpark_headcount",
    "exterior_holding",
    "final_hall_approach",
    "door_approach_d",
    "entrance_door_d",
    "foyer_passage_d",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_NORTH_DOOR_C = (
    "walk_to_north_plaza",
    "north_plaza_headcount",
    "north_plaza_holding",
    "final_hall_approach_north",
    "door_approach_c",
    "entrance_door_c",
    "foyer_passage_c",
    "foyer_to_seating",
    "seating",
)
DESTINATION_TAIL_SOUTH_DOOR_B = (
    "walk_to_south_plaza",
    "south_plaza_headcount",
    "south_plaza_holding",
    "final_hall_approach_south",
    "door_approach_b",
    "entrance_door_b",
    "foyer_passage_walk",
    "foyer_to_seating",
    "seating",
)


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


def _estimate(lower: int, base: int, upper: int, status: str = "assumed") -> dict:
    return {"lower": lower, "base": base, "upper": upper, "status": status}


# Spec section 5 coordinates and registration. Unknown stays unknown.
HOSTEL_REGISTRY: list[dict] = [
    {
        "id": "restu",
        "name": "Restu",
        "latitude_deg": 5.356461,
        "longitude_deg": 100.289265,
        "registration": None,
        "registration_status": "unknown",
        "bed_capacity": None,
        "bed_capacity_estimate": _estimate(400, 500, 620, "estimated"),
        "resident_occupancy": 36,
        "resident_occupancy_estimate": _estimate(28, 36, 48, "assumed"),
        "expected_event_attendance": 28,
        "expected_event_attendance_estimate": _estimate(22, 28, 36, "assumed"),
        "resolved_attendance": 8,
        "initial_route": "rst_bus",
        "origin_place_id": "restu_origin",
        "waiting_location": "Restu cafe",
        "layout_status": "estimated",
        "coord_source": "gps_session_3_telemetry#M07_cafeteria",
        "coord_date": "2026-09-18",
        "coord_confidence": "high",
    },
    {
        "id": "saujana",
        "name": "Saujana",
        "latitude_deg": 5.35640,
        "longitude_deg": 100.29050,
        "registration": 610,
        "registration_status": "recorded",
        "bed_capacity": 780,
        "bed_capacity_estimate": _estimate(720, 780, 860, "estimated"),
        "resident_occupancy": 572,
        "resident_occupancy_estimate": _estimate(520, 572, 610, "estimated"),
        "expected_event_attendance": 488,
        "expected_event_attendance_estimate": _estimate(430, 488, 540, "estimated"),
        "resolved_attendance": 8,
        "initial_route": "rst_bus",
        "origin_place_id": "saujana_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "tekun",
        "name": "Tekun",
        "latitude_deg": 5.35563,
        "longitude_deg": 100.29129,
        "registration": 508,
        "registration_status": "recorded",
        "bed_capacity": 640,
        "bed_capacity_estimate": _estimate(580, 640, 720, "estimated"),
        "resident_occupancy": 470,
        "resident_occupancy_estimate": _estimate(430, 470, 508, "estimated"),
        "expected_event_attendance": 400,
        "expected_event_attendance_estimate": _estimate(350, 400, 450, "estimated"),
        "resolved_attendance": 8,
        "initial_route": "rst_bus",
        "origin_place_id": "tekun_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "indah_kembara",
        "name": "Indah Kembara",
        "latitude_deg": 5.35603,
        "longitude_deg": 100.29604,
        "registration": 244,
        "registration_status": "recorded",
        "bed_capacity": 320,
        "bed_capacity_estimate": _estimate(280, 320, 380, "estimated"),
        "resident_occupancy": 220,
        "resident_occupancy_estimate": _estimate(200, 220, 244, "estimated"),
        "expected_event_attendance": 180,
        "expected_event_attendance_estimate": _estimate(150, 180, 210, "estimated"),
        "resolved_attendance": 8,
        "initial_route": "walk",
        "origin_place_id": "indah_kembara_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "aman_damai",
        "name": "Aman Damai",
        "latitude_deg": 5.35431,
        "longitude_deg": 100.29615,
        "registration": 410,
        "registration_status": "recorded",
        "bed_capacity": 520,
        "bed_capacity_estimate": _estimate(480, 520, 580, "estimated"),
        "resident_occupancy": 380,
        "resident_occupancy_estimate": _estimate(340, 380, 410, "estimated"),
        "expected_event_attendance": 328,
        "expected_event_attendance_estimate": _estimate(280, 328, 370, "estimated"),
        "resolved_attendance": 8,
        "initial_route": "walk",
        "origin_place_id": "aman_damai_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "bakti_fajar_permai",
        "name": "Bakti Fajar Permai",
        "latitude_deg": 5.35776,
        "longitude_deg": 100.30055,
        "registration": 341,
        "registration_status": "recorded",
        "bed_capacity": 430,
        "bed_capacity_estimate": _estimate(390, 430, 490, "estimated"),
        "resident_occupancy": 310,
        "resident_occupancy_estimate": _estimate(280, 310, 341, "estimated"),
        "expected_event_attendance": 260,
        "expected_event_attendance_estimate": _estimate(220, 260, 300, "estimated"),
        "resolved_attendance": 8,
        "initial_route": "walk",
        "origin_place_id": "bakti_fajar_permai_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "cahaya_gemilang",
        "name": "Cahaya Gemilang",
        "latitude_deg": 5.36046,
        "longitude_deg": 100.30360,
        "registration": None,
        "registration_status": "unknown",
        "bed_capacity": None,
        "bed_capacity_estimate": _estimate(280, 360, 480, "estimated"),
        "resident_occupancy": 48,
        "resident_occupancy_estimate": _estimate(36, 48, 72, "assumed"),
        "expected_event_attendance": 36,
        "expected_event_attendance_estimate": _estimate(24, 36, 52, "assumed"),
        "resolved_attendance": 8,
        "initial_route": "walk",
        "origin_place_id": "cahaya_gemilang_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
    {
        "id": "fajar_harapan",
        "name": "Fajar Harapan",
        "latitude_deg": 5.35500,
        "longitude_deg": 100.29977,
        "registration": None,
        "registration_status": "unknown",
        "bed_capacity": None,
        "bed_capacity_estimate": _estimate(280, 360, 480, "estimated"),
        "resident_occupancy": 52,
        "resident_occupancy_estimate": _estimate(40, 52, 80, "assumed"),
        "expected_event_attendance": 40,
        "expected_event_attendance_estimate": _estimate(28, 40, 60, "assumed"),
        "resolved_attendance": 8,
        "initial_route": "walk",
        "origin_place_id": "fajar_harapan_origin",
        "layout_status": "estimated",
        "coord_source": "spec.md#5-hostel-registry-and-demand",
        "coord_date": "2026-09-19",
        "coord_confidence": "medium",
    },
]


# Map-based walking estimates. Speed is free walking (1.3 m/s), not Restu column speed.
WALKING_ROUTE_REGISTRY: dict[str, dict] = {
    "indah_kembara": {
        "distance_m": 1414,
        "unique_duration_s": 688,
        "duration_range_s": [1020, 1260],
        "access_limits": ["unsignalized_crossing_padang_kawad"],
        "slope": "mostly_flat",
        "stairs": False,
        "crossings": ["padang_kawad_junction", "jalan_universiti"],
        "shared_sections": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        "source": "OSM/campus map estimate from hostel to DTSP along Jalan Indah Kembara and Jalan Universiti",
        "method": "map_estimate",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
        "shelter_access": False,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": None,
    },
    "aman_damai": {
        "distance_m": 1136,
        "unique_duration_s": 474,
        "duration_range_s": [780, 1020],
        "access_limits": ["narrow_residential_walkways"],
        "slope": "gentle",
        "stairs": True,
        "crossings": ["jalan_sungai_dua_exit", "jalan_universiti"],
        "shared_sections": [SHARED_PATH_JALAN_UNIVERSITI_EAST],
        "source": "OSM/campus map estimate from Damai cafeteria to DTSP via Jalan Damai",
        "method": "map_estimate",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
        "shelter_access": False,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": "hostel_exit_steps",
        "accessible_alternative": {
            "distance_m": 1200,
            "duration_s": 1412,
            "duration_range_s": [1320, 1560],
            "walking_speed_m_s": SLOWER_WALK_M_S,
            "stairs": False,
            "lift_restriction": None,
            "note": "slower step-free path; not the default route",
            "method": "map_estimate",
            "source": "explicit accessible-route assumption for Aman Damai",
        },
    },
    "bakti_fajar_permai": {
        "distance_m": 972,
        "unique_duration_s": 748,
        "duration_range_s": [720, 900],
        "access_limits": ["short_stair_flights_chemical_sciences"],
        "slope": "stepped_campus_paths",
        "stairs": True,
        "crossings": ["persiaran_sains"],
        "shared_sections": [],
        "source": "OSM/campus map estimate from H10 through Pusat Sejahtera precinct to DTSP",
        "method": "map_estimate",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
        "shelter_access": True,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": "block_linking_stairs",
        "accessible_alternative": {
            "distance_m": 1050,
            "duration_s": 1235,
            "duration_range_s": [1140, 1380],
            "walking_speed_m_s": SLOWER_WALK_M_S,
            "stairs": False,
            "note": "slower ramp-preferring path",
            "method": "map_estimate",
            "source": "explicit accessible-route assumption for Bakti Fajar Permai",
        },
    },
    "cahaya_gemilang": {
        "distance_m": 784,
        "unique_duration_s": 603,
        "duration_range_s": [600, 720],
        "access_limits": ["dk_complex_pedestrian_merge"],
        "slope": "southbound_descent",
        "stairs": True,
        "crossings": ["jalan_mahasiswa"],
        "shared_sections": [],
        "source": "OSM/campus map estimate from H33-H35 along Jalan Gemilang to DTSP north plaza",
        "method": "map_estimate",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
        "shelter_access": True,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": "dk_descent_steps",
    },
    "fajar_harapan": {
        "distance_m": 680,
        "unique_duration_s": 523,
        "duration_range_s": [480, 600],
        "access_limits": ["lake_edge_narrow_path"],
        "slope": "grade_separation_to_eureka",
        "stairs": True,
        "crossings": ["jalan_universiti_eureka"],
        "shared_sections": [],
        "source": "OSM/campus map estimate from F26/F27 past Eureka and Tasik USM to DTSP south",
        "method": "map_estimate",
        "walking_speed_m_s": FREE_WALK_M_S,
        "not_driving_route": True,
        "not_restu_congested_speed": True,
        "date": "2026-09-19",
        "confidence": "low",
        "shelter_access": False,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": "terrace_to_eureka_steps",
        "accessible_alternative": {
            "distance_m": 760,
            "duration_s": 894,
            "duration_range_s": [840, 1020],
            "walking_speed_m_s": SLOWER_WALK_M_S,
            "stairs": False,
            "note": "slower step-free loop around the lake",
            "method": "map_estimate",
            "source": "explicit accessible-route assumption for Fajar Harapan",
        },
    },
}


def effective_seats(destination: dict) -> int:
    """Seats that remain after initial occupants and reserved seating."""
    available = int(destination["available_seats"])
    initial = int(destination.get("initial_occupants") or 0)
    reserved = int(destination.get("reserved_seating") or 0)
    return available - initial - reserved


def default_destination() -> dict:
    return {
        "id": "dtsp",
        "place_id": "dtsp_hall_reference",
        "seating_place_id": "dtsp_seating",
        "opening_calendar_id": "hall_open",
        "opening_time_s": 600,
        "available_seats": 1500,
        "seating_rate_s_per_person": 2.0,
        "initial_occupants": 20,
        "reserved_seating": 30,
        "exterior_storage_students": 300,
        "foyer_storage_students": 200,
        "shared_internal_path_ids": [SHARED_FOYER_PASSAGE],
        "doors": [
            {
                "id": "door_a",
                "place_id": "dtsp_door_a",
                "approach": "bus_alighting",
                "entrance_rate_s_per_person": 1.0,
            },
            {
                "id": "door_b",
                "place_id": "dtsp_door_b",
                "approach": "walking_plaza",
                "entrance_rate_s_per_person": 1.0,
            },
        ],
        "bag_check": False,
        "security_service": False,
    }


def default_background_demand() -> dict:
    return {
        "pedestrians": 0,
        "road_crossings": 0,
        "other_arrivals": 0,
        "visible_assumption": True,
        "assumption_id": "zero_background_demand",
        "note": "zero background pedestrians, crossings, and other arrivals is an explicit assumption",
    }


def _place(
    place_id: str,
    latitude_deg: float,
    longitude_deg: float,
    meaning: str,
    *,
    unbounded: bool = True,
    capacity_students: int | None = None,
    extra: dict | None = None,
) -> dict:
    place = {
        "id": place_id,
        "latitude_deg": latitude_deg,
        "longitude_deg": longitude_deg,
        "meaning": meaning,
        "capacity_from_gps_scatter": False,
        "shelter_access": None,
        "closures": [],
        "lift_restriction": None,
        "stair_restriction": None,
    }
    if unbounded:
        place["capacity_constraint"] = "unbounded"
        place["capacity_note"] = (
            "explicit unbounded assumption for ticket 05; "
            "ticket 06 may later bind storage"
        )
    else:
        place["capacity_students"] = int(capacity_students)
        place["capacity_constraint"] = "finite"
    if extra:
        place.update(extra)
    return place


def _split_field(total: int | None, unit_ids: list[str]) -> dict[str, int] | None:
    if total is None:
        return None
    weights = [(unit_id, 1.0) for unit_id in unit_ids]
    return allocate_integer_counts(int(total), weights)


def _source_units_for_hostel(hostel: dict) -> list[dict]:
    unit_ids = []
    specs = []
    for floor_id in ("1", "2"):
        for wing_id in ("east", "west"):
            unit_id = f"su_{hostel['id']}_f{floor_id}_{wing_id}"
            unit_ids.append(unit_id)
            specs.append((floor_id, wing_id, unit_id))
    occupancy = _split_field(hostel["resident_occupancy"], unit_ids)
    expected = _split_field(hostel["expected_event_attendance"], unit_ids)
    resolved = _split_field(hostel["resolved_attendance"], unit_ids)
    registration = _split_field(hostel["registration"], unit_ids)
    units = []
    for floor_id, wing_id, unit_id in specs:
        units.append(
            {
                "id": unit_id,
                "hostel_id": hostel["id"],
                "building_id": f"{hostel['id']}_block",
                "floor_id": floor_id,
                "wing_id": wing_id,
                "layout_status": "estimated",
                "layout_labels_estimated": True,
                "registration": None if registration is None else registration[unit_id],
                "resident_occupancy": occupancy[unit_id],
                "expected_event_attendance": expected[unit_id],
                "estimated_attendance": expected[unit_id],
                "resolved_attendance": resolved[unit_id],
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "late_assembly_s": 0,
                "non_attendance": 0,
                "withdrawn": 0,
                "late_assembly_rule": "explicit_event",
                "non_attendance_rule": "explicit",
                "withdrawal_rule": "explicit_event",
                "origin_place_id": hostel["origin_place_id"],
            }
        )
    return units


def _hostel_row(hostel: dict) -> dict:
    return {
        "id": hostel["id"],
        "name": hostel["name"],
        "latitude_deg": hostel["latitude_deg"],
        "longitude_deg": hostel["longitude_deg"],
        "registration": hostel["registration"],
        "registration_status": hostel["registration_status"],
        "bed_capacity": hostel["bed_capacity"],
        "bed_capacity_estimate": hostel.get("bed_capacity_estimate"),
        "resident_occupancy": hostel["resident_occupancy"],
        "resident_occupancy_estimate": hostel.get("resident_occupancy_estimate"),
        "expected_event_attendance": hostel["expected_event_attendance"],
        "expected_event_attendance_estimate": hostel.get(
            "expected_event_attendance_estimate"
        ),
        "resolved_attendance": hostel["resolved_attendance"],
        "initial_route": hostel["initial_route"],
        "origin_place_id": hostel["origin_place_id"],
        "layout_status": hostel["layout_status"],
    }


def _walking_route_row(hostel_id: str, leg_ids: list[str]) -> dict:
    raw = dict(WALKING_ROUTE_REGISTRY[hostel_id])
    shared = list(raw.get("shared_sections") or [])
    duration_s = int(raw["unique_duration_s"])
    if SHARED_PATH_JALAN_UNIVERSITI_EAST in shared:
        duration_s += 400
    raw.update(
        {
            "hostel_id": hostel_id,
            "leg_ids": list(leg_ids),
            "duration_s": duration_s,
            "mode": "walk",
        }
    )
    return raw


def _shared_resources(full_cohort: bool = False) -> list[dict]:
    return [
        {
            "id": SHARED_PATH_JALAN_UNIVERSITI_EAST,
            "kind": "path",
            "capacity_students": None if full_cohort else 80,
            "operating_limit_students": None if full_cohort else 60,
            "continuous_streaming": True if full_cohort else None,
            "duration_s": 400,
            "distance_m": 520,
            "shelter_access": False,
            "closures": [],
            "slope": "gentle_eastbound",
            "stairs": False,
            "crossings": ["padang_kawad_junction"],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "shared Jalan Universiti east sidewalk used by Indah Kembara and Aman Damai",
        },
        {
            "id": SHARED_FOYER_PASSAGE,
            "kind": "internal_passage",
            "capacity_students": 120,
            "operating_limit_students": 100,
            "shelter_access": True,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "one foyer passage; extra doors do not duplicate this resource",
        },
        {
            "id": "path_carpark_single_file",
            "kind": "path",
            "capacity_students": None,
            "operating_limit_students": None,
            "continuous_streaming": True,
            "single_file": True,
            "duration_s": 40,
            "distance_m": 68,
            "shelter_access": True,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "continuous single file column egress from car park (25-35 students/minute nominal spacing)",
        },
        {
            "id": "path_north_plaza_single_file",
            "kind": "path",
            "capacity_students": None,
            "operating_limit_students": None,
            "continuous_streaming": True,
            "single_file": True,
            "duration_s": 40,
            "distance_m": 50,
            "shelter_access": True,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "continuous single file column egress from Dataran Merah north plaza",
        },
        {
            "id": "path_south_plaza_single_file",
            "kind": "path",
            "capacity_students": None,
            "operating_limit_students": None,
            "continuous_streaming": True,
            "single_file": True,
            "duration_s": 40,
            "distance_m": 50,
            "shelter_access": True,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "continuous single file column egress from G28 Siswaniaga grass field south plaza",
        },
        {
            "id": "path_restu_shoulder_single_file",
            "kind": "path",
            "capacity_students": None,
            "operating_limit_students": None,
            "continuous_streaming": True,
            "single_file": True,
            "duration_s": 40,
            "distance_m": 210,
            "shelter_access": False,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "single file road shoulder along curb from Restu cafe to overpass (MASTER.md I8b)",
        },
        {
            "id": "rst_boarding_berth",
            "kind": "berth",
            "capacity_students": 320,
            "operating_limit_students": 320,
            "duration_s": 0,
            "shelter_access": True,
            "closures": [],
            "lift_restriction": None,
            "stair_restriction": None,
            "note": "RST origin bus boarding berths (1 to 4 active simultaneous berths)",
        },
    ]


def _source_records(hostels: list[dict], destination: dict) -> list[dict]:
    records = []
    spec_ref = "spec.md#5-hostel-registry-and-demand"
    walk_ref = "spec.md#8-other-routes-and-shared-places"
    dest_ref = "spec.md#14-destination-and-changing-conditions"
    for hostel in hostels:
        hid = hostel["id"]
        records.append(
            _record(
                f"hostels.{hid}.latitude_deg",
                hostel["latitude_deg"],
                "deg",
                hostel["coord_date"],
                "project hostel table in spec section 5",
                hostel["coord_confidence"],
                hostel["coord_source"],
                "estimated",
            )
        )
        records.append(
            _record(
                f"hostels.{hid}.longitude_deg",
                hostel["longitude_deg"],
                "deg",
                hostel["coord_date"],
                "project hostel table in spec section 5",
                hostel["coord_confidence"],
                hostel["coord_source"],
                "estimated",
            )
        )
        if hostel["registration"] is None:
            records.append(
                _record(
                    f"hostels.{hid}.registration",
                    "unknown",
                    "label",
                    "2026-09-19",
                    "unknown in spec section 5; left unknown",
                    "low",
                    spec_ref,
                    "assumed",
                )
            )
        else:
            records.append(
                _record(
                    f"hostels.{hid}.registration",
                    hostel["registration"],
                    "persons",
                    "2026-09-19",
                    "recorded hostel registration in spec section 5 project context; not an independent event count",
                    "medium",
                    spec_ref,
                    "estimated",
                )
            )
        if hostel["bed_capacity"] is None:
            records.append(
                _record(
                    f"hostels.{hid}.bed_capacity",
                    "unknown",
                    "label",
                    "2026-09-19",
                    "bed capacity unknown; lower/base/upper estimate is on the hostel record",
                    "low",
                    "ticket-05-assumption",
                    "assumed",
                )
            )
        else:
            records.append(
                _record(
                    f"hostels.{hid}.bed_capacity",
                    hostel["bed_capacity"],
                    "persons",
                    "2026-09-19",
                    "assumed bed stock; distinct from registration and attendance",
                    "low",
                    "ticket-05-assumption",
                    "assumed",
                )
            )
        records.append(
            _record(
                f"hostels.{hid}.resident_occupancy",
                hostel["resident_occupancy"],
                "persons",
                "2026-09-19",
                "explicit occupancy distinct from registration and attendance",
                "low",
                "ticket-05-assumption",
                "assumed",
            )
        )
        records.append(
            _record(
                f"hostels.{hid}.expected_event_attendance",
                hostel["expected_event_attendance"],
                "persons",
                "2026-09-19",
                "explicit expected attendance distinct from occupancy",
                "low",
                "ticket-05-assumption",
                "assumed",
            )
        )
        records.append(
            _record(
                f"hostels.{hid}.resolved_attendance",
                hostel["resolved_attendance"],
                "persons",
                "2026-09-19",
                "small runnable attendance; not a claim of actual event size",
                "low",
                "ticket-05-assumption",
                "assumed",
            )
        )
        if hostel["initial_route"] == "walk":
            walk = WALKING_ROUTE_REGISTRY[hid]
            records.append(
                _record(
                    f"walking_routes.{hid}.duration_s",
                    walk["unique_duration_s"]
                    + (400 if SHARED_PATH_JALAN_UNIVERSITI_EAST in walk["shared_sections"] else 0),
                    "s",
                    walk["date"],
                    (
                        f"map estimate at {FREE_WALK_M_S} m/s free walking; "
                        "not Restu congested column speed; not a driving route"
                    ),
                    walk["confidence"],
                    walk_ref,
                    "estimated",
                )
            )
            records.append(
                _record(
                    f"walking_routes.{hid}.distance_m",
                    walk["distance_m"],
                    "m",
                    walk["date"],
                    walk["method"],
                    walk["confidence"],
                    walk["source"],
                    "estimated",
                )
            )
    records.append(
        _record(
            "destination.available_seats",
            destination["available_seats"],
            "persons",
            "2026-09-19",
            "assumed hall seating stock; doors do not create seats",
            "low",
            dest_ref,
            "assumed",
        )
    )
    records.append(
        _record(
            "destination.initial_occupants",
            destination["initial_occupants"],
            "persons",
            "2026-09-19",
            "assumed occupants already in the hall",
            "low",
            dest_ref,
            "assumed",
        )
    )
    records.append(
        _record(
            "destination.reserved_seating",
            destination["reserved_seating"],
            "persons",
            "2026-09-19",
            "assumed reserved seats that reduce available capacity",
            "low",
            dest_ref,
            "assumed",
        )
    )
    records.append(
        _record(
            "shared_resources.path_jalan_universiti_east.duration_s",
            400,
            "s",
            "2026-09-19",
            "shared sidewalk duration used by Indah Kembara and Aman Damai",
            "low",
            walk_ref,
            "estimated",
        )
    )
    records.append(
        _record(
            "background_demand.pedestrians",
            0,
            "persons",
            "2026-09-19",
            "zero background demand is an explicit assumption",
            "low",
            dest_ref,
            "assumed",
        )
    )
    return records


def _accuracy_references() -> list[dict]:
    refs = []
    for hostel_id in WALK_HOSTEL_IDS:
        refs.append(
            {
                "id": f"unmeasured_{hostel_id}",
                "role": "unverified",
                "hostel_id": hostel_id,
                "endpoint_definition": "walking arrival at DTSP",
                "note": (
                    "Unmeasured walking route. Passing the Restu replay does not "
                    "certify this timing."
                ),
            }
        )
    for hostel_id in ("saujana", "tekun"):
        refs.append(
            {
                "id": f"unmeasured_{hostel_id}",
                "role": "unverified",
                "hostel_id": hostel_id,
                "endpoint_definition": "RST bus arrival at DTSP from this origin",
                "note": (
                    "This origin is not a measured Restu replay. Passing the Restu "
                    "replay does not certify this timing."
                ),
            }
        )
    return refs


def build_whole_campus_origins_case(
    full_cohort: bool = False,
    policy: Mapping[str, Any] | None = None,
) -> tuple[dict, dict]:
    """All eight hostels in one shared movement system."""
    from usm_sim.scenarios import (
        COACH_SPEED_DRY_M_S,
        build_rst_shared_fleet,
        coach_duration_s,
        place_latlon,
    )
    destination = default_destination()
    background = default_background_demand()
    if full_cohort:
        destination["opening_time_s"] = 0.0
        destination["bag_check"] = False
        destination["security_service"] = False
        init_occ = int(destination.get("initial_occupants") or 0)
        res_seats = int(destination.get("reserved_seating") or 0)
        destination["available_seats"] = 3000 + init_occ + res_seats
        destination["exterior_storage_students"] = 600
        destination["doors"] = [
            {
                "id": "door_a",
                "place_id": "dtsp_door_a",
                "approach": "bus_alighting",
                "entrance_rate_s_per_person": 1.0,
                "assignment_type": "assumed_parameter",
            },
            {
                "id": "door_b",
                "place_id": "dtsp_door_b",
                "approach": "walking_plaza_south",
                "entrance_rate_s_per_person": 1.0,
                "assignment_type": "assumed_parameter",
            },
            {
                "id": "door_c",
                "place_id": "dtsp_door_c",
                "approach": "walking_plaza_north",
                "entrance_rate_s_per_person": 1.0,
                "assignment_type": "assumed_parameter",
            },
            {
                "id": "door_d",
                "place_id": "dtsp_door_d",
                "approach": "bus_alighting",
                "entrance_rate_s_per_person": 1.0,
                "assignment_type": "assumed_parameter",
            },
        ]
        destination["carpark_tiers"] = {
            "level_1_lower_apron": {
                "name": "Level 1 Lower Apron",
                "safe_seated": 320,
                "max": 380,
                "assigned_cohorts": [],
                "tier_status": "unmapped",
                "observational_metadata": {
                    "observed_cohort": "restu_boys",
                    "observed_cohort_sex": "male",
                    "headcount": None,
                    "mapping_status": "unspecified",
                    "exact_tier_confirmed": False,
                    "observation_ref": "Abraham 2026-09-22: One Restu-boys cohort observed occupying one of three tiers; count unknown, exact tier level unconfirmed, and source-unit mappings not provided",
                },
            },
            "level_2_mid_terrace": {
                "name": "Level 2 Mid Terrace",
                "safe_seated": 120,
                "max": 140,
                "assigned_cohorts": [],
                "tier_status": "unmapped",
                "observational_metadata": {
                    "headcount": None,
                    "mapping_status": "unspecified",
                    "exact_tier_confirmed": False,
                    "observation_ref": "Distinct cohort staging observed, exact cohort mapping and tier level unsupplied",
                },
            },
            "level_3_upper_buffer": {
                "name": "Level 3 Upper Buffer",
                "safe_seated": 60,
                "max": 80,
                "assigned_cohorts": [],
                "tier_status": "unmapped",
                "observational_metadata": {
                    "headcount": None,
                    "mapping_status": "unspecified",
                    "exact_tier_confirmed": False,
                    "observation_ref": "Roadside buffer tier, exact cohort mapping and tier level unsupplied",
                },
            },
        }
        destination["overflow_destination"] = {
            "id": "g03",
            "place_id": "g03_foyer_entrance",
            "seating_place_id": "g03_seating",
            "available_seats": 600,
            "stages": ["carpark_to_g03", "g03_foyer_to_seating", "g03_seating"],
        }

    seats = effective_seats(destination)

    if full_cohort:
        hostels = []
        for row in HOSTEL_REGISTRY:
            h = _hostel_row(row)
            hid = row["id"]
            if hid in OFFICIAL_2026_HOSTEL_COUNTS:
                cnt = OFFICIAL_2026_HOSTEL_COUNTS[hid]
                h["registration"] = cnt
                h["registration_status"] = "recorded"
                h["expected_event_attendance"] = cnt
                h["resolved_attendance"] = cnt
            hostels.append(h)

        source_units: list[dict] = []
        for row in HOSTEL_REGISTRY:
            units = _source_units_for_hostel(row)
            hid = row["id"]
            tot = OFFICIAL_2026_HOSTEL_COUNTS.get(hid, len(units) * 8)
            base = tot // len(units)
            rem = tot % len(units)
            mid_point = len(units) // 2
            for i, u in enumerate(units):
                cnt = base + (1 if i < rem else 0)
                u["registration"] = cnt
                u["expected_event_attendance"] = cnt
                u["estimated_attendance"] = cnt
                u["resolved_attendance"] = cnt
                u["actual_reporting_s"] = 0.0
                u["readiness_s"] = 0.0
                if hid == "restu":
                    u["waiting_location"] = "Restu cafe"
                    u["queue_priority"] = 1
                    u["sex"] = "unknown"
                    u["sex_status"] = "unknown"
                    u["staging_tier"] = "dtsp_exterior_gathering"
                    u["tier_status"] = "unassigned"
                    u["cohort_id"] = "restu"
                    u["assigned_door"] = "door_b"
                    u["door_assignment_type"] = "assumed_parameter"
                    u["channel_label"] = "parameterized_operational_door_channel_b"
                elif hid == "tekun":
                    u["cohort_id"] = "tekun"
                    u["queue_priority"] = -2
                    u["sex"] = "unknown"
                    u["sex_status"] = "unknown"
                    u["staging_tier"] = "dtsp_exterior_gathering"
                    u["tier_status"] = "unassigned"
                    u["assigned_door"] = "door_a"
                    u["door_assignment_type"] = "assumed_parameter"
                    u["channel_label"] = "parameterized_operational_door_channel_a"
                elif hid == "saujana":
                    u["cohort_id"] = "saujana"
                    u["queue_priority"] = -1
                    u["sex"] = "unknown"
                    u["sex_status"] = "unknown"
                    u["staging_tier"] = "dtsp_exterior_gathering"
                    u["tier_status"] = "unassigned"
                    u["assigned_door"] = "door_d"
                    u["door_assignment_type"] = "assumed_parameter"
                    u["channel_label"] = "parameterized_operational_door_channel_d"
                elif hid in NORTH_WALK_HOSTEL_IDS:
                    u["cohort_id"] = hid
                    u["queue_priority"] = 0
                    u["sex"] = "unknown"
                    u["sex_status"] = "unknown"
                    u["staging_tier"] = "dtsp_north_plaza"
                    u["tier_status"] = "observed_gathering"
                    u["assigned_door"] = "door_c"
                    u["door_assignment_type"] = "assumed_parameter"
                else:
                    u["cohort_id"] = hid
                    u["queue_priority"] = 0
                    u["sex"] = "unknown"
                    u["sex_status"] = "unknown"
                    u["staging_tier"] = "dtsp_south_plaza"
                    u["tier_status"] = "observed_gathering"
                    u["assigned_door"] = "door_b"
                    u["door_assignment_type"] = "assumed_parameter"
            source_units.extend(units)
    else:
        hostels = [_hostel_row(row) for row in HOSTEL_REGISTRY]
        source_units: list[dict] = []
        for row in HOSTEL_REGISTRY:
            source_units.extend(_source_units_for_hostel(row))
    places = [
        _place(
            "restu_origin",
            5.356461,
            100.289265,
            "Restu origin (Restu cafe M07, GPS Session 3)",
            extra={"hostel_id": "restu", "location_type": "cafe", "waiting_location": "Restu cafe"},
        ),
        _place("saujana_origin", 5.35640, 100.29050, "Saujana origin"),
        _place("tekun_origin", 5.35563, 100.29129, "Tekun origin"),
        _place("indah_kembara_origin", 5.35603, 100.29604, "Indah Kembara origin"),
        _place("aman_damai_origin", 5.35431, 100.29615, "Aman Damai origin"),
        _place(
            "bakti_fajar_permai_origin",
            5.35776,
            100.30055,
            "Bakti Fajar Permai origin",
        ),
        _place("cahaya_gemilang_origin", 5.36046, 100.30360, "Cahaya Gemilang origin"),
        _place("fajar_harapan_origin", 5.35500, 100.29977, "Fajar Harapan origin"),
        _place(
            "rst_bus_wait",
            5.356036,
            100.293640,
            "shared RST bus wait",
            extra={
                "estimated_capacity_students": 80,
                "estimated_capacity_note": "sourced estimate, not GPS scatter",
                "repeat_observations": [
                    {
                        "id": "rst_rain_bus_wait",
                        "observation_date": "2026-09-18",
                        "note": "same bus-wait area, not extra storage",
                    }
                ],
            },
        ),
        _place(
            "rst_boarding_approach",
            5.356012,
            100.293748,
            "shared RST boarding",
            extra={"estimated_capacity_students": 40},
        ),
        _place(
            "rst_rain_shelter",
            5.356461,
            100.289265,
            "RST rain shelter at the cafeteria area (Restu cafe M07, GPS Session 3)",
            extra={
                "estimated_capacity_students": 120,
                "shelter_access": True,
                "location_type": "cafe",
                "waiting_location": "Restu cafe",
                "osm_way": "275415004",
                "gps_session": "session_3_2026-09-18_morning_M01_Rainy_to_DTSP",
            },
        ),
        _place(
            "dtsp_alighting_area",
            5.357215,
            100.301437,
            "bus alighting at DTSP (straight line road with 4 active berths, holds 8 buses)",
            extra={"estimated_capacity_students": 320 if full_cohort else 60},
        ),
        _place("dtsp_walk_approach", 5.35700, 100.30190, "walking approach to DTSP"),
        _place(
            "dtsp_exterior_gathering",
            5.357153,
            100.301749,
            "3-tier car park waiting area (RST bus alightees hold)",
            unbounded=False,
            capacity_students=destination["exterior_storage_students"],
            extra={
                "shelter_access": True,
                "operating_limit_students": min(
                    500 if full_cohort else 250, int(destination["exterior_storage_students"])
                ),
                "preceding_place_id": "dtsp_alighting_area",
                "estimated_capacity_students": destination["exterior_storage_students"],
                "parking_tiers": {
                    "level_1_lower_apron": {"safe_seated": 320, "max": 380},
                    "level_2_mid_terrace": {"safe_seated": 120, "max": 140},
                    "level_3_upper_buffer": {"safe_seated": 60, "max": 80},
                    "total_safe_seated": 500,
                    "max_capacity": 600,
                },
                "repeat_observations": [
                    {
                        "id": "dtsp_exterior_hold_later_window",
                        "note": "repeat observation of this hold, not extra storage",
                    }
                ],
            },
        ),
        _place(
            "dtsp_north_plaza",
            5.356518,
            100.303214,
            "Dataran Merah with shaded pavilion (north walking plaza)",
            unbounded=False,
            capacity_students=1200,
            extra={
                "shelter_access": True,
                "operating_limit_students": 1200,
                "preceding_place_id": "dtsp_walk_approach",
                "estimated_capacity_students": 1200,
            },
        ),
        _place(
            "dtsp_south_plaza",
            5.356118,
            100.302400,
            "Grass field in front of G28 Siswaniaga (south walking plaza)",
            unbounded=False,
            capacity_students=1000,
            extra={
                "shelter_access": False,
                "operating_limit_students": 1000,
                "preceding_place_id": "dtsp_walk_approach",
                "estimated_capacity_students": 1000,
            },
        ),
        _place(
            "dtsp_door_a",
            5.35700,
            100.30280,
            "DTSP door A, bus approach",
        ),
        _place(
            "dtsp_door_b",
            5.35680,
            100.30300,
            "DTSP door B, walking plaza",
        ),
        _place(
            "dtsp_foyer",
            5.35690,
            100.30305,
            "DTSP foyer / shared internal passage",
            unbounded=False,
            capacity_students=destination["foyer_storage_students"],
            extra={
                "shelter_access": True,
                "operating_limit_students": destination["foyer_storage_students"],
                "preceding_place_id": "dtsp_door_b",
            },
        ),
        _place(
            "dtsp_seating",
            5.35692,
            100.30308,
            "DTSP seating area",
            unbounded=False,
            capacity_students=3000 if full_cohort else seats,
            extra={
                "operating_limit_students": 3000 if full_cohort else seats,
                "preceding_place_id": "dtsp_foyer",
            },
        ),
        _place(
            "dtsp_hall_reference",
            5.35695,
            100.30311,
            "DTSP hall map pin",
        ),
        _place(
            "g03_foyer_entrance",
            5.357119,
            100.302499,
            "Bangunan G03 foyer entrance (DK G & DK H, OSM way 94331153)",
            extra={"osm_way": "94331153", "shelter_access": True},
        ),
        _place(
            "g03_seating",
            5.357119,
            100.302499,
            "Bangunan G03 seating (Dewan Kuliah G & H overflow)",
            unbounded=False,
            capacity_students=600,
            extra={
                "operating_limit_students": 600,
                "preceding_place_id": "g03_foyer_entrance",
            },
        ),
    ]
    if full_cohort:
        places.extend(
            [
                _place(
                    "dtsp_door_c",
                    5.35710,
                    100.30320,
                    "DTSP door C, north walking plaza / Dataran Merah approach",
                ),
                _place(
                    "dtsp_door_d",
                    5.35670,
                    100.30260,
                    "DTSP door D, bus approach / west lateral flank",
                ),
            ]
        )

    legs: list[dict] = []
    stages: list[dict] = []
    routes: dict[str, list[str]] = {}
    walking_routes: list[dict] = []

    for hostel_id, origin, approach_s in (
        ("restu", "restu_origin", 960 if full_cohort else 8),
        ("saujana", "saujana_origin", 12),
        ("tekun", "tekun_origin", 16),
    ):
        leg_id = f"leg_approach_{hostel_id}"
        stage_id = f"approach_{hostel_id}"
        legs.append(
            {
                "id": leg_id,
                "from_place_id": origin,
                "to_place_id": "rst_bus_wait",
                "duration_s": approach_s,
                "mode": "walk",
                "shared_resource_ids": ["path_restu_shoulder_single_file"] if (full_cohort and hostel_id == "restu") else [],
            }
        )
        stages.append({"id": stage_id, "kind": "travel", "leg_id": leg_id})
        if full_cohort and hostel_id == "restu":
            stages.append(
                {
                    "id": "restu_cafe_wait",
                    "kind": "hold",
                    "place_id": "rst_rain_shelter",
                    "until": {
                        "cause": "imposed_sequencing_wait",
                        "hostels_departed": ["tekun", "saujana"],
                    },
                }
            )
            routes["restu"] = ["restu_cafe_wait", stage_id, "bus_waiting", "boarding_walk", "boarding", "transit", "alighting", *DESTINATION_TAIL_DOOR_B]
        elif full_cohort and hostel_id == "tekun":
            routes[hostel_id] = [stage_id, "bus_waiting", "boarding_walk", "boarding", "transit", "alighting", *DESTINATION_TAIL_DOOR_A]
        elif full_cohort and hostel_id == "saujana":
            routes[hostel_id] = [stage_id, "bus_waiting", "boarding_walk", "boarding", "transit", "alighting", *DESTINATION_TAIL_DOOR_D]
        else:
            routes[hostel_id] = [stage_id, "bus_waiting", "boarding_walk", "boarding", "transit", "alighting", *DESTINATION_TAIL_BUS]

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
                "duration_s": RESTU_COACH_TRANSIT_S,
                "mode": "coach",
                "shared_resource_ids": ["rst_fleet"],
            },
            {
                "id": "leg_transfer_walk",
                "from_place_id": "dtsp_alighting_area",
                "to_place_id": "dtsp_exterior_gathering",
                "duration_s": 20,
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
                "duration_s": RESTU_BOARDING_SERVICE_S,
                "service_duration_s": float(RESTU_BOARDING_SERVICE_S),
            } if full_cohort else {
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
                "duration_s": RESTU_ALIGHTING_SERVICE_S,
                "service_duration_s": float(RESTU_ALIGHTING_SERVICE_S),
            } if full_cohort else {
                "id": "alighting",
                "kind": "batch_service",
                "place_id": "dtsp_alighting_area",
                "fleet_id": "rst_fleet",
                "action": "alight",
                "duration_rule": "load_dependent",
            },
            {"id": "transfer_walk", "kind": "travel", "leg_id": "leg_transfer_walk"},
        ]
    )

    for hostel_id in WALK_HOSTEL_IDS:
        walk = WALKING_ROUTE_REGISTRY[hostel_id]
        origin = f"{hostel_id}_origin"
        leg_id = f"leg_walk_{hostel_id}"
        stage_id = f"walk_{hostel_id}"
        shared_ids = list(walk.get("shared_sections") or [])
        legs.append(
            {
                "id": leg_id,
                "from_place_id": origin,
                "to_place_id": "dtsp_walk_approach",
                "duration_s": int(walk["unique_duration_s"]),
                "mode": "walk",
                "distance_m": walk["distance_m"],
                "duration_range_s": list(walk["duration_range_s"]),
                "access_limits": list(walk["access_limits"]),
                "slope": walk["slope"],
                "stairs": walk["stairs"],
                "crossings": list(walk["crossings"]),
                "shared_resource_ids": shared_ids,
                "walking_speed_m_s": walk["walking_speed_m_s"],
                "not_driving_route": True,
                "not_restu_congested_speed": True,
                "shelter_access": walk.get("shelter_access"),
                "closures": list(walk.get("closures") or []),
                "lift_restriction": walk.get("lift_restriction"),
                "stair_restriction": walk.get("stair_restriction"),
            }
        )
        stages.append({"id": stage_id, "kind": "travel", "leg_id": leg_id})
        tail = DESTINATION_TAIL_NORTH if hostel_id in NORTH_WALK_HOSTEL_IDS else DESTINATION_TAIL_SOUTH
        approach_leg = "leg_walk_to_north_plaza" if hostel_id in NORTH_WALK_HOSTEL_IDS else "leg_walk_to_south_plaza"
        routes[hostel_id] = [stage_id, *tail]
        walking_routes.append(_walking_route_row(hostel_id, [leg_id, approach_leg]))

    legs.extend(
        [
            {
                "id": "leg_walk_to_exterior",
                "from_place_id": "dtsp_walk_approach",
                "to_place_id": "dtsp_exterior_gathering",
                "duration_s": 20,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_walk_to_north_plaza",
                "from_place_id": "dtsp_walk_approach",
                "to_place_id": "dtsp_north_plaza",
                "duration_s": 20,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_walk_to_south_plaza",
                "from_place_id": "dtsp_walk_approach",
                "to_place_id": "dtsp_south_plaza",
                "duration_s": 20,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_hall_approach",
                "from_place_id": "dtsp_exterior_gathering",
                "to_place_id": "dtsp_hall_reference",
                "distance_m": 68,
                "duration_s": 40,
                "mode": "walk",
                "shared_resource_ids": ["path_carpark_single_file"],
            },
            {
                "id": "leg_carpark_to_g03",
                "from_place_id": "dtsp_exterior_gathering",
                "to_place_id": "g03_foyer_entrance",
                "distance_m": 120,
                "duration_s": 40,
                "mode": "walk",
                "shared_resource_ids": ["path_carpark_single_file"],
            },
            {
                "id": "leg_g03_foyer_to_seating",
                "from_place_id": "g03_foyer_entrance",
                "to_place_id": "g03_seating",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_hall_approach_north",
                "from_place_id": "dtsp_north_plaza",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": 30,
                "mode": "walk",
                "shared_resource_ids": ["path_north_plaza_single_file"],
            },
            {
                "id": "leg_hall_approach_south",
                "from_place_id": "dtsp_south_plaza",
                "to_place_id": "dtsp_hall_reference",
                "duration_s": 30,
                "mode": "walk",
                "shared_resource_ids": ["path_south_plaza_single_file"],
            },
            {
                "id": "leg_door_a_to_foyer",
                "from_place_id": "dtsp_door_a",
                "to_place_id": "dtsp_foyer",
                "duration_s": 15,
                "mode": "walk",
                "shared_resource_ids": [SHARED_FOYER_PASSAGE],
            },
            {
                "id": "leg_door_b_to_foyer",
                "from_place_id": "dtsp_door_b",
                "to_place_id": "dtsp_foyer",
                "duration_s": 15,
                "mode": "walk",
                "shared_resource_ids": [SHARED_FOYER_PASSAGE],
            },
            {
                "id": "leg_foyer_to_seating",
                "from_place_id": "dtsp_foyer",
                "to_place_id": "dtsp_seating",
                "duration_s": 10,
                "mode": "walk",
                "shared_resource_ids": [SHARED_FOYER_PASSAGE],
            },
            {
                "id": "leg_hall_to_door_a",
                "from_place_id": "dtsp_hall_reference",
                "to_place_id": "dtsp_door_a",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
            {
                "id": "leg_hall_to_door_b",
                "from_place_id": "dtsp_hall_reference",
                "to_place_id": "dtsp_door_b",
                "duration_s": 5,
                "mode": "walk",
                "shared_resource_ids": [],
            },
        ]
    )
    if full_cohort:
        legs.extend(
            [
                {
                    "id": "leg_hall_to_door_c",
                    "from_place_id": "dtsp_hall_reference",
                    "to_place_id": "dtsp_door_c",
                    "duration_s": 5,
                    "mode": "walk",
                    "shared_resource_ids": [],
                },
                {
                    "id": "leg_hall_to_door_d",
                    "from_place_id": "dtsp_hall_reference",
                    "to_place_id": "dtsp_door_d",
                    "duration_s": 5,
                    "mode": "walk",
                    "shared_resource_ids": [],
                },
                {
                    "id": "leg_door_c_to_foyer",
                    "from_place_id": "dtsp_door_c",
                    "to_place_id": "dtsp_foyer",
                    "duration_s": 15,
                    "mode": "walk",
                    "shared_resource_ids": [SHARED_FOYER_PASSAGE],
                },
                {
                    "id": "leg_door_d_to_foyer",
                    "from_place_id": "dtsp_door_d",
                    "to_place_id": "dtsp_foyer",
                    "duration_s": 15,
                    "mode": "walk",
                    "shared_resource_ids": [SHARED_FOYER_PASSAGE],
                },
                {
                    "id": "leg_seating_block",
                    "from_place_id": "dtsp_seating",
                    "to_place_id": "dtsp_seating",
                    "duration_s": 0,
                    "mode": "walk",
                    "shared_resource_ids": [],
                },
                {
                    "id": "leg_g03_seating_block",
                    "from_place_id": "g03_seating",
                    "to_place_id": "g03_seating",
                    "duration_s": 0,
                    "mode": "walk",
                    "shared_resource_ids": [],
                },
            ]
        )
    stages.extend(
        [
            {"id": "walk_to_exterior", "kind": "travel", "leg_id": "leg_walk_to_exterior"},
            {
                "id": "carpark_headcount",
                "kind": "hold",
                "place_id": "dtsp_exterior_gathering",
                "until": {"duration_s": 300, "cause": "headcount_staging"},
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
            {"id": "walk_to_north_plaza", "kind": "travel", "leg_id": "leg_walk_to_north_plaza"},
            {
                "id": "north_plaza_headcount",
                "kind": "hold",
                "place_id": "dtsp_north_plaza",
                "until": {"duration_s": 300, "cause": "headcount_staging"},
            },
            {
                "id": "north_plaza_holding",
                "kind": "hold",
                "place_id": "dtsp_north_plaza",
                "until": {"calendar_id": "hall_open"},
            },
            {
                "id": "final_hall_approach_north",
                "kind": "travel",
                "leg_id": "leg_hall_approach_north",
                "completion_event": "hall_area_arrival",
            },
            {"id": "walk_to_south_plaza", "kind": "travel", "leg_id": "leg_walk_to_south_plaza"},
            {
                "id": "south_plaza_headcount",
                "kind": "hold",
                "place_id": "dtsp_south_plaza",
                "until": {"duration_s": 300, "cause": "headcount_staging"},
            },
            {
                "id": "south_plaza_holding",
                "kind": "hold",
                "place_id": "dtsp_south_plaza",
                "until": {"calendar_id": "hall_open"},
            },
            {
                "id": "final_hall_approach_south",
                "kind": "travel",
                "leg_id": "leg_hall_approach_south",
                "completion_event": "hall_area_arrival",
            },
            {"id": "door_approach_a", "kind": "travel", "leg_id": "leg_hall_to_door_a"},
            {"id": "door_approach_b", "kind": "travel", "leg_id": "leg_hall_to_door_b"},
            {
                "id": "entrance_door_a",
                "kind": "queue_service",
                "place_id": "dtsp_door_a",
                "service_duration_s": 1.0,
                "server_count": 1,
                "queue_discipline": "fcfs",
                "completion_event": "entrance_completion",
            },
            {
                "id": "entrance_door_b",
                "kind": "queue_service",
                "place_id": "dtsp_door_b",
                "service_duration_s": 1.0,
                "server_count": 1,
                "queue_discipline": "fcfs",
                "completion_event": "entrance_completion",
            },
            {
                "id": "foyer_passage",
                "kind": "travel",
                "leg_id": "leg_door_a_to_foyer",
            },
            {
                "id": "foyer_passage_walk",
                "kind": "travel",
                "leg_id": "leg_door_b_to_foyer",
            },
            {
                "id": "foyer_to_seating",
                "kind": "travel",
                "leg_id": "leg_foyer_to_seating",
            },
            {
                "id": "seating",
                "kind": "travel",
                "leg_id": "leg_seating_block",
                "place_id": "dtsp_seating",
                "completion_event": "seated_completion",
            } if full_cohort else {
                "id": "seating",
                "kind": "queue_service",
                "place_id": "dtsp_seating",
                "service_duration_s": destination["seating_rate_s_per_person"],
                "server_count": 1,
                "queue_discipline": "fcfs",
                "completion_event": "seated_completion",
            },
            {
                "id": "carpark_to_g03",
                "kind": "travel",
                "leg_id": "leg_carpark_to_g03",
                "completion_event": "hall_area_arrival",
            },
            {
                "id": "g03_foyer_to_seating",
                "kind": "travel",
                "leg_id": "leg_g03_foyer_to_seating",
            },
            {
                "id": "g03_seating",
                "kind": "travel",
                "leg_id": "leg_g03_seating_block",
                "place_id": "g03_seating",
                "completion_event": "seated_completion",
            } if full_cohort else {
                "id": "g03_seating",
                "kind": "queue_service",
                "place_id": "g03_seating",
                "service_duration_s": destination["seating_rate_s_per_person"],
                "server_count": 1,
                "queue_discipline": "fcfs",
                "completion_event": "seated_completion",
            },
        ]
    )
    if full_cohort:
        stages.extend(
            [
                {"id": "door_approach_c", "kind": "travel", "leg_id": "leg_hall_to_door_c"},
                {"id": "door_approach_d", "kind": "travel", "leg_id": "leg_hall_to_door_d"},
                {
                    "id": "entrance_door_c",
                    "kind": "queue_service",
                    "place_id": "dtsp_door_c",
                    "service_duration_s": 1.0,
                    "server_count": 1,
                    "queue_discipline": "fcfs",
                    "completion_event": "entrance_completion",
                },
                {
                    "id": "entrance_door_d",
                    "kind": "queue_service",
                    "place_id": "dtsp_door_d",
                    "service_duration_s": 1.0,
                    "server_count": 1,
                    "queue_discipline": "fcfs",
                    "completion_event": "entrance_completion",
                },
                {
                    "id": "foyer_passage_c",
                    "kind": "travel",
                    "leg_id": "leg_door_c_to_foyer",
                },
                {
                    "id": "foyer_passage_d",
                    "kind": "travel",
                    "leg_id": "leg_door_d_to_foyer",
                },
            ]
        )
    for hostel_id in WALK_HOSTEL_IDS:
        if full_cohort:
            tail = DESTINATION_TAIL_NORTH_DOOR_C if hostel_id in NORTH_WALK_HOSTEL_IDS else DESTINATION_TAIL_SOUTH_DOOR_B
        else:
            tail = DESTINATION_TAIL_NORTH if hostel_id in NORTH_WALK_HOSTEL_IDS else DESTINATION_TAIL_SOUTH
        routes[hostel_id] = [f"walk_{hostel_id}", *tail]

    fleet_info = build_rst_shared_fleet(
        calendar_id="fleet_service",
        places=places,
        dropoff_space_capacity=4 if full_cohort else 1,
        return_travel_s=float(RESTU_COACH_TRANSIT_S) if full_cohort else None,
    )
    vehicles = fleet_info["vehicles"]

    scenario = {
        "format_version": FORMAT_VERSION,
        "data_version": "ticket-05-campus-v1",
        "scenario_id": "whole_campus_full_cohort_2026" if full_cohort else "whole_campus_origins_v1",
        "profile": "operational" if full_cohort else "origins",
        "operational_profile": True if full_cohort else False,
        "uncertainty_case_id": "ticket05_campus_base",
        "event_date": "2026-09-17",
        "start_time_local": "06:30:00" if full_cohort else "07:00:00",
        "timezone": TIMEZONE_NAME,
        "deadline_s": 9000 if full_cohort else 7200,
        "simulation_end_s": 30000 if full_cohort else 20000,
        "max_events_per_run": 1000000,
        "hostels": hostels,
        "source_units": source_units,
        "places": places,
        "route_legs": legs,
        "route_stages": stages,
        "routes": routes,
        "walking_routes": walking_routes,
        "shared_resources": _shared_resources(full_cohort=full_cohort),
        "destination": destination,
        "background_demand": background,
        "calendars": [
            {
                "id": "hall_open",
                "kind": "opening",
                "place_id": "dtsp_exterior_gathering",
                "open_time_s": 0.0 if full_cohort else destination["opening_time_s"],
                "imposed": not full_cohort,
                "label": "unlocked_hall_opening" if full_cohort else "declared_hall_opening",
            },
            {
                "id": "fleet_service",
                "kind": "service",
                "place_id": "rst_boarding_approach",
                "open_time_s": 0,
            },
        ],
        "vehicle_types": fleet_info["vehicle_types"],
        "fleets": fleet_info["fleets"],
        "initial_state": {
            "students": [
                {
                    "part_id": "placeholder",
                    "group_id": "placeholder",
                    "source_unit_id": "su_restu_f1_east",
                    "place_id": "restu_origin",
                    "hostel_id": "restu",
                    "hostel_composition": {"restu": 1},
                    "members": [{"student_key": "placeholder", "queue_tie_key": "00"}],
                }
            ],
            "queues": [],
            "workers": [],
            "vehicles": vehicles,
            "hall_occupancy_students": destination["initial_occupants"],
        },
        "operating_rules": {
            "profile": "operational" if full_cohort else "origins",
            "ppsl_total_reference": 154,
            "worker_budget": 154,
            "required_endpoint": "hall_area_arrival",
            "route_id": "whole_campus_mixed",
            "direct_walk_permitted": False,
            "bag_check": False,
            "security_service": False,
            "mechanical_clicker": False,
            "qr_scan": False,
            "seating_modeled": True,
            "late_assembly": "explicit_event",
            "non_attendance": "explicit",
            "optional_withdrawal": "explicit_event",
            "reporting_rule": "actual_reporting_s",
            "readiness_rule": "readiness_s",
            "walk_occupancy_rule": {
                "type": "two_band",
                "empty_means": "other_students_on_path",
                "empty_duration_factor": 1.0,
                "congested_duration_factor": FREE_WALK_M_S / SLOWER_WALK_M_S,
                "congested_at": "operating_limit",
                "shared_extra_when": "occupancy_ahead_gt_0",
                "source": "assumed",
                "note": "empty=FREE_WALK_M_S; congested=SLOWER_WALK_M_S; not GPS",
            },
        },
        "measured_facts": [
            {
                "id": "hostel_table_coordinates",
                "category": "estimated",
                "observation_ref": "spec.md#5-hostel-registry-and-demand",
            }
        ],
        "uncertain_assumptions": [
            {
                "id": "zero_background_demand",
                "value": 0,
                "unit": "persons",
                "category": "assumed",
                "note": background["note"],
            },
            {
                "id": "runnable_resolved_attendance",
                "value": 8,
                "unit": "persons_per_hostel",
                "category": "assumed",
                "note": "resolved attendance is a small runnable case, not registration",
            },
            {
                "id": "free_walking_speed_m_s",
                "value": FREE_WALK_M_S,
                "unit": "m/s",
                "category": "assumed",
                "note": "free walking; not Restu congested column speed",
            },
            {
                "id": "unknown_registration_left_unknown",
                "value": None,
                "category": "assumed",
                "note": "Restu, Cahaya Gemilang, and Fajar Harapan registration stay unknown",
            },
            {
                "id": "layouts_estimated",
                "category": "assumed",
                "note": "floor and wing labels are estimated, not a surveyed layout",
            },
            {
                "id": "escorts_declared_not_travel_constrained",
                "value": 1,
                "unit": "escorts_per_group",
                "category": "assumed",
                "note": "ticket 04 worker travel is out of scope; escorts stay declared numbers",
            },
            {
                "id": "late_assembly_none",
                "value": 0,
                "category": "assumed",
                "note": "late assembly is an explicit zero event in this case",
            },
            {
                "id": "non_attendance_none",
                "value": 0,
                "category": "assumed",
                "note": "non-attendance is an explicit zero in this case",
            },
            {
                "id": "optional_withdrawal_none",
                "value": 0,
                "category": "assumed",
                "note": "optional withdrawal is an explicit zero event in this case",
            },
            {
                "id": "place_capacity_origins_unbounded",
                "category": "assumed",
                "note": "named unconstrained origins; destination storage is finite",
            },
        ] + fleet_info["uncertain_assumptions"],
        "decisions": [
            {
                "id": "rst_fixed_bus_chain",
                "category": "decision",
                "note": "Restu, Saujana, and Tekun use the fixed supervised bus chain",
            },
            {
                "id": "other_origins_walk",
                "category": "decision",
                "note": "non-RST origins initially walk",
            },
            {
                "id": "required_endpoint",
                "value": "hall_area_arrival",
                "category": "decision",
            },
        ],
        "source_records": _source_records(HOSTEL_REGISTRY, destination) + fleet_info["source_records"],
        "accuracy_references": _accuracy_references(),
    }
    if policy is not None:
        return scenario, dict(policy)
    if full_cohort:
        policy = {
            "policy_id": "whole_campus_full_cohort_policy_v1",
            "policy_version": "1",
            "grouping": {
                "mode": "from_source_units",
                "basis": "target_size",
                "target_students": 20,
                "split_policy": "permit_supervised_split",
                "mixing_policy": "same_hostel",
                "adaptation_rule": {"type": "fixed"},
                "regroup_policy": {"required": False},
                "escorts_per_group": 1,
            },
            "required_endpoint": "hall_area_arrival",
            "release_rule": {"type": "immediate"},
            "vehicle_dispatch_rule": {
                "type": "shared_fleet",
                "fleet_id": "rst_fleet",
                "simultaneous_boarding_berths": 4,
            },
            "destination_rule": {"type": "complete_after_stages"},
            "random_seed": 0,
            "numerical_rounding_limit_s": 0.001,
        }
    else:
        policy = {
            "policy_id": "whole_campus_hostel_groups_v1",
            "policy_version": "1",
            "grouping": {
                "mode": "from_source_units",
                "basis": "floor_wing",
                "split_policy": "forbid",
                "mixing_policy": "same_hostel",
                "adaptation_rule": {"type": "fixed"},
                "regroup_policy": {"required": False},
                "escorts_per_group": 1,
            },
            "required_endpoint": "hall_area_arrival",
            "release_rule": {"type": "immediate"},
            "vehicle_dispatch_rule": {"type": "shared_fleet", "fleet_id": "rst_fleet"},
            "destination_rule": {"type": "wait_for_imposed_opening", "calendar_id": "hall_open"},
            "random_seed": 0,
            "numerical_rounding_limit_s": 0.001,
        }
    return scenario, policy


def build_whole_campus_full_cohort_case(
    policy: Mapping[str, Any] | None = None,
) -> tuple[dict, dict]:
    """Official 2026 full campus cohort (3,543 students across all 8 hostels)."""
    return build_whole_campus_origins_case(full_cohort=True, policy=policy)

def append_origin(
    scenario: dict,
    *,
    hostel: dict,
    source_units: list[dict],
    place: dict,
    walk_leg: dict,
    walk_stage: dict,
    walking_route: dict,
    source_records: list[dict] | None = None,
) -> dict:
    """Add an origin through data only. No engine branch."""
    scenario["hostels"].append(hostel)
    scenario["source_units"].extend(source_units)
    scenario["places"].append(place)
    scenario["route_legs"].append(walk_leg)
    scenario["route_stages"].append(walk_stage)
    scenario["routes"][hostel["id"]] = [walk_stage["id"], *DESTINATION_TAIL_WALK]
    scenario.setdefault("walking_routes", []).append(walking_route)
    if source_records:
        scenario["source_records"].extend(source_records)
    return scenario
