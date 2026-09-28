"""Unit tests for USM campus routing, timing, and bottleneck scaffolding.
"""

import json
import os
import pytest

from usm_sim.routing import (
    CAMPUS_ROUTES,
    RouteSegment,
    audit_route_bottlenecks,
    calculate_route_timing,
    export_scaffolding_database,
    generate_campus_routing_matrix,
    get_route_profile,
    get_route_summary,
)


def test_all_eight_hostels_registered():
    """Verify that all 8 campus hostels have valid topological route profiles."""
    expected_hostels = {
        "restu",
        "tekun",
        "saujana",
        "indah_kembara",
        "aman_damai",
        "bakti_fajar_permai",
        "cahaya_gemilang",
        "fajar_harapan",
    }
    registered = {hid for (hid, var) in CAMPUS_ROUTES.keys()}
    assert expected_hostels.issubset(registered)


def test_route_timing_physics_consistency():
    """Verify that timings obey physical invariants (free < column < congested)."""
    for (hid, var), route in CAMPUS_ROUTES.items():
        timings = route.calculate_timings()
        assert timings["free_flow_s"] > 0
        assert timings["supervised_column_s"] > timings["free_flow_s"]
        assert timings["congested_s"] >= timings["supervised_column_s"]

        # Window checks
        w_min, w_max = timings["recommended_window_s"]
        assert w_min < w_max
        assert w_min <= timings["supervised_column_s"] <= w_max


def test_bottleneck_detection_and_capacities():
    """Verify choke points are accurately detected and flow-rated."""
    # Restu must have single-file choke point
    rst_b = audit_route_bottlenecks("restu", "standard")
    assert rst_b["choke_point_count"] >= 2
    assert rst_b["critical_flow_capacity_pax_min"] == 45.0
    assert any(b["bottleneck_type"] == "single_file" for b in rst_b["bottlenecks"])

    # Fajar Harapan must have stair choke point
    fh_b = audit_route_bottlenecks("fajar_harapan", "standard")
    assert any(b["bottleneck_type"] == "staircase" for b in fh_b["bottlenecks"])

    # Aman Damai accessible variant has higher throughput than standard stairs
    ad_std = audit_route_bottlenecks("aman_damai", "standard")
    ad_acc = audit_route_bottlenecks("aman_damai", "accessible_step_free")
    assert ad_acc["critical_flow_capacity_pax_min"] >= ad_std["critical_flow_capacity_pax_min"]


def test_route_summary_contract():
    """Verify comprehensive route summary schema for AI consumption."""
    summary = get_route_summary("bakti_fajar_permai", "standard")
    assert summary["hostel_id"] == "bakti_fajar_permai"
    assert summary["destination_id"] == "dtsp_north_plaza"
    assert summary["metrics"]["total_distance_m"] > 0
    assert summary["metrics"]["shaded_percentage"] > 50.0  # High shaded corridor
    assert len(summary["segments"]) == summary["metrics"]["segment_count"]
    assert "timings" in summary
    assert "bottlenecks" in summary


def test_campus_routing_matrix_generation():
    """Verify campus matrix covers all routes with deterministic sorting."""
    matrix = generate_campus_routing_matrix()
    assert len(matrix) >= 9  # 8 standard + 1 accessible
    for row in matrix:
        assert row["distance_m"] > 0
        assert row["column_walk_min"] > 0
        assert row["critical_capacity_pax_min"] > 0


def test_database_export(tmp_path):
    """Verify offline JSON export works cleanly."""
    out_file = str(tmp_path / "test_routes.json")
    res_path = export_scaffolding_database(out_file)
    assert os.path.exists(res_path)

    with open(res_path) as f:
        data = json.load(f)
    assert "matrix" in data
    assert "routes" in data
    assert len(data["routes"]) >= 9


def test_cli_routes_command():
    """Verify usm-sim routes command integration."""
    from usm_sim.cli import build_parser, run_command

    parser = build_parser()
    args_matrix = parser.parse_args(["routes", "--matrix"])
    res_m, code_m = run_command("routes", args_matrix)
    assert code_m == 0
    assert "matrix" in res_m
    assert len(res_m["matrix"]) >= 9

    args_hostel = parser.parse_args(["routes", "--hostel", "restu"])
    res_h, code_h = run_command("routes", args_hostel)
    assert code_h == 0
    assert res_h["hostel_id"] == "restu"
    assert res_h["origin_coords"]["lat"] == 5.356461
    assert res_h["origin_coords"]["lon"] == 100.289265

