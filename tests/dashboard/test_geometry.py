from __future__ import annotations

from operator_dashboard.geometry import campus_coordinate, project_map
from usm_sim.campus import HOSTEL_REGISTRY


def test_hostel_registry_coordinates_on_map():
    payload = project_map("r", {"event_trace": []}, {"places": [], "route_legs": []}, output_mode="full")
    by_id = {row["id"]: row for row in payload["hostels"]}
    restu = next(row for row in HOSTEL_REGISTRY if row["id"] == "restu")
    assert by_id["restu"]["latitude_deg"] == restu["latitude_deg"]
    assert by_id["restu"]["longitude_deg"] == restu["longitude_deg"]
    assert by_id["restu"]["rst"] is True


def test_zero_zero_is_unknown_geometry():
    scenario = {
        "places": [
            {
                "id": "origin",
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "meaning": "artificial origin",
            }
        ],
        "route_legs": [
            {
                "id": "walk_1",
                "from_place_id": "origin",
                "to_place_id": "entrance",
                "mode": "walk",
            }
        ],
    }
    payload = project_map("r", {"event_trace": []}, scenario, output_mode="full")
    unknown_ids = {row["id"] for row in payload["unknown_places"]}
    assert "origin" in unknown_ids
    assert campus_coordinate(0, 0) is False
    origin_links = [link for link in payload["planned_links"] if link["id"] == "walk_1"]
    assert origin_links
    assert origin_links[0]["on_map"] is False
    assert origin_links[0]["label"] == "Route link, not exact road path"


def test_dtsp_places_are_on_map():
    payload = project_map("r", {"event_trace": []}, {"places": [], "route_legs": []}, output_mode="full")
    ids = {row["id"] for row in payload["places"]}
    assert "dtsp_seating" in ids
    assert "dtsp_foyer" in ids
    labels = {row["id"] for row in payload["diagram"]}
    assert labels == {"boarding_berth", "road_reservoir", "foyer", "seats"}


def test_compact_used_routes_missing(artificial_compact):
    payload = project_map("c", artificial_compact["result"], None, output_mode="compact")
    assert payload["detailed_routes_available"] is False
    assert payload["missing"]


def test_real_routes_density_and_coverage():
    from operator_dashboard.geometry import LEG_WAYPOINTS, _load_real_routes, campus_coordinate
    routes = _load_real_routes()
    assert len(routes) >= 18
    for leg_id, pts in routes.items():
        assert len(pts) >= 2, f"Leg {leg_id} has fewer than 2 points"
        for lat, lon in pts:
            assert campus_coordinate(lat, lon), f"Point [{lat}, {lon}] in leg {leg_id} outside campus bounds"

    # Check dense waypoints for major corridors
    assert len(routes["leg_transit"]) >= 40
    assert len(routes["leg_walk_indah_kembara"]) >= 40
    assert len(routes["leg_walk_aman_damai"]) >= 35
    assert len(routes["leg_approach_restu"]) >= 30
    assert len(routes["leg_approach_saujana"]) >= 20
    assert len(routes["leg_approach_tekun"]) >= 20
    assert len(routes["leg_walk_bakti_fajar_permai"]) >= 25
    assert len(routes["leg_walk_cahaya_gemilang"]) >= 25
    assert len(routes["leg_walk_fajar_harapan"]) >= 25

def test_door_approach_legs_metadata():
    from operator_dashboard.geometry import LEG_COLORS, LEG_LABELS, LEG_HOSTEL_MAP
    assert "leg_hall_to_door_a" in LEG_COLORS
    assert "leg_hall_to_door_b" in LEG_COLORS
    assert "leg_hall_to_door_a" in LEG_LABELS
    assert "leg_hall_to_door_b" in LEG_LABELS
    assert "leg_hall_to_door_a" in LEG_HOSTEL_MAP
    assert "leg_hall_to_door_b" in LEG_HOSTEL_MAP
    assert "restu" in LEG_HOSTEL_MAP["leg_hall_to_door_a"]
    assert "indah_kembara" in LEG_HOSTEL_MAP["leg_hall_to_door_b"]

def test_g03_and_plaza_legs_metadata():
    from operator_dashboard.geometry import LEG_COLORS, LEG_LABELS, LEG_HOSTEL_MAP, PLACE_STYLES, _load_place_catalog
    places = {p["id"]: p for p in _load_place_catalog()}
    assert "g03_foyer_entrance" in places
    assert "g03_seating" in places
    assert places["g03_foyer_entrance"]["latitude_deg"] == 5.357119
    assert places["g03_foyer_entrance"]["longitude_deg"] == 100.302499
    assert places["g03_seating"]["latitude_deg"] == 5.357119
    assert places["g03_seating"]["longitude_deg"] == 100.302499

    assert "g03_foyer_entrance" in PLACE_STYLES
    assert "g03_seating" in PLACE_STYLES

    new_legs = [
        "leg_carpark_to_g03",
        "leg_g03_foyer_to_seating",
        "leg_walk_to_north_plaza",
        "leg_walk_to_south_plaza",
        "leg_hall_approach_north",
        "leg_hall_approach_south",
        "leg_transit_return",
    ]
    for leg in new_legs:
        assert leg in LEG_COLORS, f"Missing color for {leg}"
        assert leg in LEG_LABELS, f"Missing label for {leg}"
        assert leg in LEG_HOSTEL_MAP, f"Missing hostel map for {leg}"


def test_routes_do_not_intersect_building_footprints():
    import json
    from pathlib import Path
    import pytest
    from operator_dashboard.geometry import _load_real_routes

    osm_path = Path("/tmp/usm_central_osm.json")
    if not osm_path.exists():
        pytest.skip("Temporary /tmp/usm_central_osm.json not found")

    with open(osm_path) as f:
        osm_data = json.load(f)

    def _ccw(A, B, C):
        return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

    def _intersect(A, B, C, D):
        return _ccw(A, C, D) != _ccw(B, C, D) and _ccw(A, B, C) != _ccw(A, B, D)

    def _point_in_polygon(pt, poly):
        x, y = pt[0], pt[1]
        inside = False
        n = len(poly)
        for i in range(n):
            p1 = poly[i]
            p2 = poly[(i + 1) % n]
            if min(p1[1], p2[1]) < y <= max(p1[1], p2[1]):
                if p2[1] != p1[1]:
                    x_inters = p1[0] + (y - p1[1]) * (p2[0] - p1[0]) / (p2[1] - p1[1])
                    if x <= x_inters:
                        inside = not inside
        return inside

    def _route_intersects_polygon(route, poly):
        n_poly = len(poly)
        for i in range(len(route) - 1):
            A = route[i]
            B = route[i + 1]
            for j in range(n_poly - 1):
                C = poly[j]
                D = poly[j + 1]
                if _intersect(A, B, C, D):
                    return True
            mid = ((A[0] + B[0]) / 2, (A[1] + B[1]) / 2)
            if _point_in_polygon(mid, poly):
                return True
        for pt in route:
            if _point_in_polygon(pt, poly):
                return True
        return False

    # Central campus buildings to avoid
    target_keywords = ["g03", "g01", "dtsp", "g27", "g28", "g30", "m05", "m06", "h10", "h33", "h12", "l07", "k10", "f27", "palladium"]
    campus_buildings = []
    for el in osm_data.get("elements", []):
        if "building" in el.get("tags", {}) and el.get("geometry") and el["tags"].get("building") != "roof":
            name = el["tags"].get("name") or el["tags"].get("ref") or ""
            combined = f"{el['tags'].get('ref', '')} {name}".lower()
            if any(kw in combined for kw in target_keywords):
                pts = [(p["lat"], p["lon"]) for p in el["geometry"]]
                campus_buildings.append((el["id"], combined, pts))

    routes = _load_real_routes()
    outdoor_legs = [
        "leg_approach_restu",
        "leg_approach_saujana",
        "leg_approach_tekun",
        "leg_to_boarding",
        "leg_transit",
        "leg_transfer_walk",
        "leg_walk_cahaya_gemilang",
        "leg_walk_bakti_fajar_permai",
        "leg_walk_fajar_harapan",
        "leg_walk_indah_kembara",
        "leg_walk_aman_damai",
        "leg_walk_to_exterior",
        "leg_walk_to_north_plaza",
        "leg_walk_to_south_plaza",
        "leg_hall_approach",
        "leg_hall_approach_north",
        "leg_hall_approach_south",
        "leg_hall_to_door_a",
        "leg_hall_to_door_b",
    ]

    for leg_id in outdoor_legs:
        route = routes[leg_id]
        for bid, bname, bpoly in campus_buildings:
            assert not _route_intersects_polygon(route, bpoly), (
                f"Route '{leg_id}' intersects building footprint '{bname}' (id: {bid})"
            )
