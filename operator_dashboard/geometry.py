from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from operator_dashboard.contracts import GUIDE_TEXT, dto_base
from usm_sim.campus import HOSTEL_REGISTRY, RST_HOSTEL_IDS

DATA_DIR = Path(__file__).resolve().parent / "data"
MAP_PLACES_PATH = DATA_DIR / "map_places.json"
REAL_ROUTES_PATH = DATA_DIR / "usm_real_routes.json"
CAMPUS_LAT = (5.34, 5.37)
CAMPUS_LON = (100.28, 100.31)


HOSTEL_COLORS = {
    "restu": "#8B5CF6",
    "saujana": "#0EA5E9",
    "tekun": "#F59E0B",
    "indah_kembara": "#10B981",
    "aman_damai": "#EF4444",
    "bakti_fajar_permai": "#06B6D4",
    "cahaya_gemilang": "#D97706",
    "fajar_harapan": "#EC4899",
}

LEG_HOSTEL_MAP: dict[str, list[str]] = {
    "leg_approach_restu": ["restu"],
    "leg_approach_saujana": ["saujana"],
    "leg_approach_tekun": ["tekun"],
    "leg_to_boarding": ["restu", "saujana", "tekun"],
    "leg_transit": ["restu", "saujana", "tekun"],
    "leg_transit_return": ["restu", "saujana", "tekun"],
    "leg_transfer_walk": ["restu", "saujana", "tekun"],
    "leg_walk_indah_kembara": ["indah_kembara"],
    "leg_walk_aman_damai": ["aman_damai"],
    "leg_walk_bakti_fajar_permai": ["bakti_fajar_permai"],
    "leg_walk_cahaya_gemilang": ["cahaya_gemilang"],
    "leg_walk_fajar_harapan": ["fajar_harapan"],
    "leg_walk_to_exterior": ["indah_kembara", "aman_damai", "bakti_fajar_permai", "cahaya_gemilang", "fajar_harapan"],
    "leg_hall_approach": ["restu", "saujana", "tekun"],
    "leg_hall_to_door_a": ["restu", "saujana", "tekun", "cahaya_gemilang", "bakti_fajar_permai"],
    "leg_hall_to_door_b": ["indah_kembara", "aman_damai", "fajar_harapan"],
    "leg_door_a_to_foyer": ["restu", "saujana", "tekun", "cahaya_gemilang", "bakti_fajar_permai"],
    "leg_door_b_to_foyer": ["indah_kembara", "aman_damai", "fajar_harapan"],
    "leg_foyer_to_seating": ["restu", "saujana", "tekun", "indah_kembara", "aman_damai", "bakti_fajar_permai", "cahaya_gemilang", "fajar_harapan"],
    "leg_walk_to_north_plaza": ["cahaya_gemilang", "bakti_fajar_permai"],
    "leg_walk_to_south_plaza": ["indah_kembara", "aman_damai", "fajar_harapan"],
    "leg_hall_approach_north": ["cahaya_gemilang", "bakti_fajar_permai"],
    "leg_hall_approach_south": ["indah_kembara", "aman_damai", "fajar_harapan"],
    "leg_carpark_to_g03": ["restu", "saujana", "tekun"],
    "leg_g03_foyer_to_seating": ["restu", "saujana", "tekun"],
}

PLACE_STYLES = {
    "rst_overpass": {"color": "#8b5cf6", "badge": "🌉 Jejantas Overpass", "icon": "bridge"},
    "rst_bus_wait": {"color": "#2563eb", "badge": "🚌 RST Bus Wait", "icon": "bus"},
    "rst_boarding_approach": {"color": "#1d4ed8", "badge": "🚏 Boarding Berth", "icon": "berth"},
    "rst_rain_shelter": {"color": "#64748b", "badge": "☔ RST Shelter (Restu Cafe)", "icon": "shelter"},
    "restu_origin": {"color": "#8b5cf6", "badge": "☕ Restu Cafe / Shelter", "icon": "shelter"},
    "dtsp_alighting_area": {"color": "#4f46e5", "badge": "🛑 Bus Drop-off", "icon": "dropoff"},
    "dtsp_walk_approach": {"color": "#059669", "badge": "🚶 Walk Arrival", "icon": "walk"},
    "dtsp_exterior_gathering": {"color": "#dc2626", "badge": "⏳ 3-Tier Car Park Waiting Area", "icon": "hold"},
    "dtsp_north_plaza": {"color": "#d97706", "badge": "🎪 Dataran Merah (Shaded Pavilion)", "icon": "plaza"},
    "dtsp_south_plaza": {"color": "#059669", "badge": "🌱 Grass Field (G28 Siswaniaga)", "icon": "plaza"},
    "dtsp_door_a": {"color": "#475569", "badge": "🚪 Door A (North / Bus)", "icon": "door"},
    "dtsp_door_b": {"color": "#475569", "badge": "🚪 Door B (South / Walk)", "icon": "door"},
    "dtsp_foyer": {"color": "#ca8a04", "badge": "🏢 Foyer Lobby", "icon": "foyer"},
    "dtsp_seating": {"color": "#eab308", "badge": "🏛️ Hall Seats", "icon": "seats"},
    "dtsp_hall_reference": {"color": "#eab308", "badge": "🏛️ DTSP Hall", "icon": "hall"},
    "g03_foyer_entrance": {"color": "#06b6d4", "badge": "🏛️ G03 Foyer Entrance", "icon": "foyer"},
    "g03_seating": {"color": "#3b82f6", "badge": "🪑 G03 Overflow Seating (DK G/H)", "icon": "seats"},
}

LEG_COLORS = {
    "leg_approach_restu": "#8B5CF6",
    "leg_approach_saujana": "#0EA5E9",
    "leg_approach_tekun": "#F59E0B",
    "leg_to_boarding": "#3B82F6",
    "leg_transit": "#1D4ED8",
    "leg_transit_return": "#3B82F6",
    "leg_transfer_walk": "#6366F1",
    "leg_walk_aman_damai": "#EF4444",
    "leg_walk_bakti_fajar_permai": "#06B6D4",
    "leg_walk_cahaya_gemilang": "#D97706",
    "leg_walk_fajar_harapan": "#EC4899",
    "leg_walk_to_exterior": "#10B981",
    "leg_hall_approach": "#F97316",
    "leg_hall_to_door_a": "#EA580C",
    "leg_hall_to_door_b": "#EAB308",
    "leg_door_a_to_foyer": "#EA580C",
    "leg_door_b_to_foyer": "#EAB308",
    "leg_foyer_to_seating": "#CA8A04",
    "leg_walk_to_north_plaza": "#D97706",
    "leg_walk_to_south_plaza": "#10B981",
    "leg_hall_approach_north": "#D97706",
    "leg_hall_approach_south": "#10B981",
    "leg_carpark_to_g03": "#06B6D4",
    "leg_g03_foyer_to_seating": "#3B82F6",
}

LEG_LABELS = {
    "leg_approach_restu": "Restu Overpass Path (Jejantas to Bus Berth)",
    "leg_approach_saujana": "Saujana Overpass Path (Jejantas to Bus Berth)",
    "leg_approach_tekun": "Tekun Overpass Path (Jejantas to Bus Berth)",
    "leg_to_boarding": "Bus Queue to Boarding Berth",
    "leg_transit": "🚌 Orientation Bus Transit (Persiaran Sains / Jln Universiti)",
    "leg_transit_return": "🚌 Empty Bus Return Transit (DTSP to RST Boarding Berth)",
    "leg_transfer_walk": "Drop-off Walk to Road Reservoir (RST Only)",
    "leg_walk_bakti_fajar_permai": "Bakti Fajar Walk (Pusat Sejahtera / Grass to North Plaza)",
    "leg_walk_fajar_harapan": "Fajar Harapan Walk (Tasik USM Grass to South Lawn)",
    "leg_walk_indah_kembara": "Indah Kembara Walk (Padang Kawad / Grass to South Lawn)",
    "leg_walk_aman_damai": "Aman Damai Walk (Jln Damai / Grass to South Lawn)",
    "leg_walk_to_exterior": "South Lawn Waiting Area into Door B (Walkers)",
    "leg_hall_approach": "Road Reservoir (RST) into Door A (Bus)",
    "leg_hall_to_door_a": "Road Reservoir into Door A Intake",
    "leg_hall_to_door_b": "South Lawn Approach into Door B Intake",
    "leg_door_a_to_foyer": "Door A (Bus Intake) into Foyer",
    "leg_door_b_to_foyer": "Door B (Walk Intake) into Foyer",
    "leg_walk_to_north_plaza": "Dataran Merah Approach (North Walkers)",
    "leg_walk_to_south_plaza": "Grass Field Approach (South Walkers)",
    "leg_hall_approach_north": "Dataran Merah to DTSP Door B Intake",
    "leg_hall_approach_south": "Grass Field to DTSP Door B Intake",
    "leg_carpark_to_g03": "3-Tier Car Park to G03 Overflow Diversion",
    "leg_g03_foyer_to_seating": "G03 Foyer Entrance to DK G/H Seating",
}

def _load_real_routes() -> dict[str, list[list[float]]]:
    if REAL_ROUTES_PATH.exists():
        try:
            return json.loads(REAL_ROUTES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


LEG_WAYPOINTS: dict[str, list[list[float]]] = _load_real_routes()


def _load_place_catalog() -> list[dict[str, Any]]:
    if not MAP_PLACES_PATH.exists():
        return []
    payload = json.loads(MAP_PLACES_PATH.read_text(encoding="utf-8"))
    return list(payload.get("places") or [])


def campus_coordinate(lat: Any, lon: Any) -> bool:
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    return CAMPUS_LAT[0] <= lat_f <= CAMPUS_LAT[1] and CAMPUS_LON[0] <= lon_f <= CAMPUS_LON[1]


def _used_leg_ids(result: dict[str, Any] | None) -> set[str]:
    trace = (result or {}).get("event_trace")
    if not isinstance(trace, list):
        return set()
    used = set()
    for event in trace:
        if not isinstance(event, dict):
            continue
        if event.get("event_type") in {"departure", "arrival"} and event.get("leg_id"):
            used.add(str(event["leg_id"]))
    return used


def _leg_used_by_hostel(result: dict[str, Any] | None, hostel_id: str) -> set[str]:
    trace = (result or {}).get("event_trace")
    if not isinstance(trace, list):
        return set()
    used = set()
    for event in trace:
        if not isinstance(event, dict):
            continue
        composition = event.get("hostel_composition") or {}
        if hostel_id in composition and event.get("leg_id"):
            used.add(str(event["leg_id"]))
    return used


def project_map(
    run_id: str | None,
    result: dict[str, Any] | None,
    scenario: dict[str, Any] | None,
    *,
    output_mode: str,
    overlay_geojson: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scenario = scenario or {}
    result = result or {}
    catalog = {row["id"]: row for row in _load_place_catalog()}
    used_legs = _used_leg_ids(result)
    detailed = isinstance(result.get("event_trace"), list)
    hostels = []
    for row in HOSTEL_REGISTRY:
        hostel_id = row["id"]
        used = bool(_leg_used_by_hostel(result, hostel_id)) if detailed else None
        hostels.append(
            {
                "id": hostel_id,
                "name": row["name"],
                "color": HOSTEL_COLORS.get(hostel_id, "#8B5CF6"),
                "latitude_deg": row["latitude_deg"],
                "longitude_deg": row["longitude_deg"],
                "origin_place_id": row.get("origin_place_id"),
                "initial_route": row.get("initial_route"),
                "rst": hostel_id in RST_HOSTEL_IDS,
                "used_in_run": used,
                "coord_source": row.get("coord_source"),
                "coord_confidence": row.get("coord_confidence"),
            }
        )
    place_rows = []
    unknown_places = []
    coords_by_id: dict[str, tuple[float, float]] = {
        row["id"]: (float(row["latitude_deg"]), float(row["longitude_deg"])) for row in HOSTEL_REGISTRY
    }
    for row in catalog.values():
        coords_by_id[row["id"]] = (float(row["latitude_deg"]), float(row["longitude_deg"]))
        style = PLACE_STYLES.get(row["id"], {})
        place_rows.append(
            {
                "id": row["id"],
                "label": row["label"],
                "badge": style.get("badge", row["label"]),
                "color": style.get("color", "#8a5a12"),
                "icon": style.get("icon", "marker"),
                "role": row.get("role"),
                "latitude_deg": row["latitude_deg"],
                "longitude_deg": row["longitude_deg"],
                "status": row.get("status"),
                "on_map": True,
            }
        )
    for place in scenario.get("places") or []:
        if not isinstance(place, dict) or not place.get("id"):
            continue
        pid = str(place["id"])
        if pid in coords_by_id:
            continue
        lat = place.get("latitude_deg")
        lon = place.get("longitude_deg")
        if campus_coordinate(lat, lon):
            coords_by_id[pid] = (float(lat), float(lon))
            style = PLACE_STYLES.get(pid, {})
            place_rows.append(
                {
                    "id": pid,
                    "label": place.get("meaning") or pid,
                    "badge": style.get("badge", place.get("meaning") or pid),
                    "color": style.get("color", "#8a5a12"),
                    "icon": style.get("icon", "marker"),
                    "role": "scenario",
                    "latitude_deg": float(lat),
                    "longitude_deg": float(lon),
                    "status": "from_scenario",
                    "on_map": True,
                }
            )
        else:
            unknown_places.append(
                {
                    "id": pid,
                    "label": place.get("meaning") or pid,
                    "reason": "Location not yet verified",
                    "on_map": False,
                }
            )
    planned_links = []
    used_links = []
    real_routes = _load_real_routes()
    for leg in scenario.get("route_legs") or []:
        if not isinstance(leg, dict):
            continue
        start_id = leg.get("from_place_id")
        end_id = leg.get("to_place_id")
        start = coords_by_id.get(str(start_id)) if start_id else None
        end = coords_by_id.get(str(end_id)) if end_id else None
        mode = leg.get("mode") or "walk"
        style = "bus-dash" if mode in {"coach", "bus", "electric"} else "walk-dash"
        leg_id = str(leg.get("id"))
        waypoints = real_routes.get(leg_id) or LEG_WAYPOINTS.get(leg_id)
        if not waypoints and start and end:
            waypoints = [[start[0], start[1]], [end[0], end[1]]]
        link = {
            "id": leg.get("id"),
            "leg_name": LEG_LABELS.get(leg_id, leg.get("id")),
            "from_place_id": start_id,
            "to_place_id": end_id,
            "mode": mode,
            "style": style,
            "label": LEG_LABELS.get(leg_id, GUIDE_TEXT["route_link"]),
            "color": LEG_COLORS.get(leg_id, "#1D4ED8" if mode in {"coach", "bus", "electric"} else "#10B981"),
            "weight": 5 if mode in {"coach", "bus", "electric"} else 3,
            "coordinates": waypoints or [],
            "hostel_ids": LEG_HOSTEL_MAP.get(leg_id, []),
            "on_map": bool(waypoints and len(waypoints) >= 2),
            "from": {"latitude_deg": start[0], "longitude_deg": start[1]} if start else None,
            "to": {"latitude_deg": end[0], "longitude_deg": end[1]} if end else None,
            "used": (leg_id in used_legs) if detailed else None,
        }
        planned_links.append(link)
        if detailed and link["used"] and link["on_map"]:
            used_links.append(link)
    diagram = [
        {"id": "boarding_berth", "label": "Boarding berth (bus loading point)"},
        {"id": "road_reservoir", "label": "Road reservoir (outside waiting space)"},
        {"id": "foyer", "label": "Foyer (hall entrance space)"},
        {"id": "seats", "label": "Seats"},
    ]
    overlay = None
    if overlay_geojson:
        overlay = {
            "label": GUIDE_TEXT["restu_overlay"],
            "note": "This track is one phone in one Restu contingent. It is not the selected run's route.",
            "geojson": overlay_geojson,
        }
    missing = None
    if output_mode == "compact" or not detailed:
        missing = "Detailed used-route highlighting needs a full-detail run."
    payload = dto_base(
        run_id,
        units={"latitude": "deg", "longitude": "deg"},
        source_fields=["HOSTEL_REGISTRY", "route_legs", "event_trace", "map_places.json"],
        missing=missing,
    )
    payload.update(
        {
            "hostels": hostels,
            "places": place_rows,
            "unknown_places": unknown_places,
            "planned_links": planned_links,
            "used_links": used_links,
            "diagram": diagram,
            "rst_hostel_ids": list(RST_HOSTEL_IDS),
            "restu_overlay": overlay,
            "tiles": None,
            "detailed_routes_available": detailed,
        }
    )
    return payload


def load_restu_overlay(repo_root: Path) -> dict[str, Any] | None:
    path = Path(repo_root) / "processed" / "route_track.geojson"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data
