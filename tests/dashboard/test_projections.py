from __future__ import annotations

from operator_dashboard.projections import (
    clock_context,
    conservation,
    project_bottlenecks,
    project_legs,
    project_optimizer,
    project_overview,
    project_replay,
)


def test_conservation_matches_accounted(artificial_full):
    overview = project_overview(
        "r",
        artificial_full,
        case="artificial",
        seed=42,
        output_mode="full",
        scenario=artificial_full["result"]["input_snapshot"]["scenario"],
    )
    completed = overview["completed_students"]
    withdrawn = overview["withdrawn_students"]
    unfinished = overview["unfinished_students"]
    assert completed + withdrawn + unfinished == overview["accounted_students"]
    assert overview["conservation_ok"] is True
    assert overview["mean_wait_s"] == artificial_full["result"]["measures"]["mean_wait_s"]
    assert overview["p95_wait_s"] == artificial_full["result"]["measures"]["p95_wait_s"]
    assert overview["wait_denominator_students"] == 4
    assert overview["fleet"]["n_buses"] == 8


def test_unfinished_conservation_and_place(artificial_unfinished):
    overview = project_overview(
        "u",
        artificial_unfinished,
        case="artificial",
        seed=42,
        output_mode="full",
    )
    assert overview["completed_students"] + overview["withdrawn_students"] + overview["unfinished_students"] == overview["accounted_students"]
    assert overview["unfinished_students"] == 3
    bottlenecks = project_bottlenecks("u", artificial_unfinished, output_mode="full")
    places = {row["place_id"] for row in bottlenecks["unfinished"]}
    assert "entrance" in places
    assert sum(int(row["student_count"]) for row in bottlenecks["unfinished"]) == 3


def test_compact_marks_detailed_legs_unavailable(artificial_compact):
    legs = project_legs("c", artificial_compact, scenario=None, output_mode="compact")
    assert legs["detailed_legs_available"] is False
    assert "unavailable" in (legs["missing"] or "").lower() or "full detail" in (legs["missing"] or "").lower()


def test_full_legs_available(artificial_full):
    scenario = artificial_full["result"]["input_snapshot"]["scenario"]
    legs = project_legs("f", artificial_full, scenario, output_mode="full")
    assert legs["detailed_legs_available"] is True
    assert legs["groups"]


def test_split_groups_do_not_double_count(artificial_unfinished):
    leftover = artificial_unfinished["result"]["unfinished_demand"]
    counts = [int(row["student_count"]) for row in leftover]
    assert counts == [1, 1, 1]
    parents = {row.get("parent_part_id") for row in leftover}
    assert "part_origin" in parents


def test_synthetic_clock_has_no_09_comparison(artificial_full):
    scenario = artificial_full["result"]["input_snapshot"]["scenario"]
    ctx = clock_context(scenario)
    assert ctx["has_origin"] is True
    assert ctx["after_09_available"] is False
    overview = project_overview(
        "r",
        artificial_full,
        case="artificial",
        seed=42,
        output_mode="full",
        scenario=scenario,
    )
    assert overview["hall_clock"]["after_09_available"] is False
    assert overview["hall_clock"]["count_after_09"] is None


def test_campus_morning_clock_can_compare_09():
    ctx = clock_context(
        {
            "event_date": "2026-09-17",
            "start_time_local": "07:00:00",
            "timezone": "Asia/Kuala_Lumpur",
            "deadline_s": 7200,
        }
    )
    assert ctx["after_09_available"] is True
    assert ctx["deadline_matches_09"] is True
    ctx_restu = clock_context(
        {
            "event_date": "2026-09-17",
            "start_time_local": "06:47:12",
            "timezone": "Asia/Kuala_Lumpur",
            "deadline_s": 7068,
        }
    )
    assert ctx_restu["after_09_available"] is True
    assert ctx_restu["deadline_matches_09"] is False


def test_conservation_mismatch_is_error():
    row = conservation(
        {
            "completed_students": 1,
            "withdrawn_students": 0,
            "unfinished_students": 1,
            "accounted_students": 3,
            "attending_students": 3,
        }
    )
    assert row["ok"] is False
    assert row["error"]


def test_optimizer_empty_state():
    payload = project_optimizer([])
    assert payload["message"] == "No saved result"
    assert "simulator" in payload["explain"].lower()


def test_overview_does_not_expose_student_keys(artificial_full):
    overview = project_overview(
        "r",
        artificial_full,
        case="artificial",
        seed=42,
        output_mode="full",
    )
    blob = str(overview)
    assert "s1" not in blob or "student_key" not in blob


def test_replay_projection_full_and_compact(artificial_full, artificial_compact):
    scenario = artificial_full["result"]["input_snapshot"]["scenario"]
    replay_full = project_replay("r_full", artificial_full, scenario, output_mode="full")
    assert replay_full["has_trace"] is True
    assert replay_full["output_mode"] == "full"
    assert len(replay_full["sectors"]) >= 18
    assert "time_bounds" in replay_full
    assert replay_full["time_bounds"]["start_ms"] == 0
    assert replay_full["student_trajectories"]
    assert replay_full["sector_stats_timeline"]

    replay_compact = project_replay("r_compact", artificial_compact, None, output_mode="compact")
    assert replay_compact["has_trace"] is False
    assert replay_compact["output_mode"] == "compact"

    replay_forced_compact = project_replay("r_forced", artificial_full, scenario, output_mode="compact")
    assert replay_forced_compact["has_trace"] is False
    assert replay_forced_compact["output_mode"] == "compact"
    assert replay_compact["student_trajectories"] == []
    assert replay_compact["sector_stats_timeline"] == []
    assert len(replay_compact["sectors"]) >= 18


def test_trajectories_start_at_hostel_origin_at_zero(artificial_full):
    scenario = artificial_full["result"]["input_snapshot"]["scenario"]
    replay = project_replay("r_full", artificial_full, scenario, output_mode="full")
    assert replay["has_trace"] is True
    trajectories = replay["student_trajectories"]
    assert len(trajectories) > 0
    for t in trajectories:
        assert len(t["segments"]) > 0
        first_seg = t["segments"][0]
        assert first_seg["start_ms"] == 0, f"Trajectory {t['id']} does not start at start_ms: 0"
        hid = t["hostel_id"]
        if first_seg["type"] == "wait":
            assert first_seg.get("place_id") == f"{hid}_origin", (
                f"Waiting trajectory {t['id']} starts at {first_seg.get('place_id')}, expected {hid}_origin"
            )


def test_event_sorting_preserves_approach_legs():
    synthetic_trace = [
        {"time_ms": 0, "event_type": "part_ready", "place_id": "restu_origin", "affected_group_id": "g_r1", "hostel_composition": {"restu": 20}},
        {"time_ms": 0, "event_type": "departure", "leg_id": "leg_approach_restu", "place_id": "restu_origin", "affected_group_id": "g_r1"},
        {"time_ms": 8000, "event_type": "arrival", "leg_id": "leg_approach_restu", "place_id": "rst_bus_wait", "affected_group_id": "g_r1"},
        {"time_ms": 8000, "event_type": "departure", "leg_id": "leg_to_boarding", "place_id": "rst_bus_wait", "affected_group_id": "g_r1"},
        {"time_ms": 13000, "event_type": "arrival", "leg_id": "leg_to_boarding", "place_id": "rst_boarding_approach", "affected_group_id": "g_r1"},
    ]
    envelope = {"result": {"event_trace": synthetic_trace, "student_time_intervals": []}}
    replay = project_replay("r_synth", envelope, {}, output_mode="full")
    trajectories = replay["student_trajectories"]
    assert len(trajectories) == 1
    t = trajectories[0]
    assert t["segments"][0]["type"] == "transit"
    assert t["segments"][0]["leg_id"] == "leg_approach_restu"
    assert t["segments"][0]["start_ms"] == 0
    assert t["segments"][0]["end_ms"] == 8000
    assert t["segments"][1]["type"] == "transit"
    assert t["segments"][1]["leg_id"] == "leg_to_boarding"
    assert t["segments"][1]["start_ms"] == 8000
    assert t["segments"][1]["end_ms"] == 13000


def test_replay_5a6c9a41ad46_all_182_trajectories_start_at_hostel_origin():
    from pathlib import Path
    import json
    import pytest
    run_path = Path.home() / ".local/share/usm-operator-dashboard/jobs/5a6c9a41ad46/result.json"
    if not run_path.exists():
        pytest.skip("Local job 5a6c9a41ad46 result.json not found in ~/.local/share/usm-operator-dashboard")
    with open(run_path, encoding="utf-8") as f:
        envelope = json.load(f)
    scenario = envelope.get("result", {}).get("input_snapshot", {}).get("scenario")
    replay = project_replay("5a6c9a41ad46", envelope, scenario, output_mode="full")
    trajectories = replay["student_trajectories"]
    assert len(trajectories) == 182
    for t in trajectories:
        segs = t["segments"]
        assert len(segs) > 0
        first_seg = segs[0]
        assert first_seg["start_ms"] == 0, f"Trajectory {t['id']} does not start at start_ms: 0"
        hid = t["hostel_id"]
        assert hid in {"restu", "saujana", "tekun", "indah_kembara", "aman_damai", "bakti_fajar_permai", "cahaya_gemilang", "fajar_harapan"}
        if first_seg["type"] == "wait":
            assert first_seg.get("place_id") == f"{hid}_origin"
        else:
            assert first_seg["type"] == "transit"
            # Must start at hostel approach or walking leg
            assert first_seg["leg_id"] in {
                "leg_approach_restu", "leg_approach_saujana", "leg_approach_tekun",
                "leg_walk_indah_kembara", "leg_walk_aman_damai", "leg_walk_bakti_fajar_permai",
                "leg_walk_cahaya_gemilang", "leg_walk_fajar_harapan"
            }

def test_delayed_start_trajectory_prepends_origin_wait():
    synthetic_trace = [
        {"time_ms": 15000, "event_type": "part_ready", "place_id": "saujana_origin", "affected_group_id": "g_s1", "hostel_composition": {"saujana": 20}},
        {"time_ms": 15000, "event_type": "departure", "leg_id": "leg_approach_saujana", "place_id": "saujana_origin", "affected_group_id": "g_s1"},
        {"time_ms": 25000, "event_type": "arrival", "leg_id": "leg_approach_saujana", "place_id": "rst_bus_wait", "affected_group_id": "g_s1"},
    ]
    envelope = {"result": {"event_trace": synthetic_trace, "student_time_intervals": []}}
    replay = project_replay("r_delayed", envelope, {}, output_mode="full")
    trajectories = replay["student_trajectories"]
    assert len(trajectories) == 1
    t = trajectories[0]
    assert len(t["segments"]) >= 2
    assert t["segments"][0]["type"] == "wait"
    assert t["segments"][0]["start_ms"] == 0
    assert t["segments"][0]["end_ms"] == 15000
    assert t["segments"][0]["place_id"] == "saujana_origin"
    assert t["segments"][1]["type"] == "transit"
    assert t["segments"][1]["start_ms"] == 15000
    assert t["segments"][1]["end_ms"] == 25000

def test_venue_allocation_and_g03_replay_trajectories():
    from usm_sim.campus import build_whole_campus_full_cohort_case
    from usm_sim.simulate import simulate
    sc, pol = build_whole_campus_full_cohort_case()
    res = simulate(sc, pol)

    overview = project_overview(
        "run_fc",
        {"result": res},
        case="whole-campus-full-cohort",
        seed=0,
        output_mode="full",
        scenario=sc,
    )
    assert "venue_allocation" in overview
    va = overview["venue_allocation"]
    assert va is not None
    assert va["dtsp_seated"] == 3000
    assert va["g03_seated"] == 543
    assert va["total_seated"] == 3543
    assert va["cohort_coverage_pct"] == 100.0

    replay = project_replay("run_fc", {"result": res}, sc, output_mode="full")
    sector_ids = {s["id"] for s in replay["sectors"]}
    assert "g03_foyer_entrance" in sector_ids
    assert "g03_seating" in sector_ids
    assert "dtsp_north_plaza" in sector_ids
    assert "dtsp_south_plaza" in sector_ids

    trajs = replay["student_trajectories"]
    assert len(trajs) > 0
    total_students = sum(t["student_count"] for t in trajs)
    assert total_students == 3543

    g03_trajs = [t for t in trajs if t["segments"][-1]["place_id"] == "g03_seating"]
    dtsp_trajs = [t for t in trajs if t["segments"][-1]["place_id"] == "dtsp_seating"]
    assert sum(t["student_count"] for t in g03_trajs) == 543
    assert sum(t["student_count"] for t in dtsp_trajs) == 3000

    for t in g03_trajs:
        legs = [s["leg_id"] for s in t["segments"] if s["type"] == "transit"]
        assert "leg_carpark_to_g03" in legs
        assert "leg_g03_foyer_to_seating" in legs
        assert t["segments"][-1]["place_id"] == "g03_seating"

def test_bus_fleet_loop_replay_and_holding_locations():
    from usm_sim.campus import build_whole_campus_full_cohort_case
    from usm_sim.simulate import simulate

    sc, pol = build_whole_campus_full_cohort_case()
    res = simulate(sc, pol)
    replay = project_replay("run_bus_test", {"result": res}, sc, output_mode="full")

    # Sectors check
    sector_map = {s["id"]: s for s in replay["sectors"]}
    assert "restu_origin" in sector_map
    assert sector_map["restu_origin"]["coordinates"] == [5.356461, 100.289265]
    assert "rst_rain_shelter" in sector_map
    assert "rst_bus_wait" in sector_map
    assert "rst_boarding_approach" in sector_map
    assert "dtsp_exterior_gathering" in sector_map
    assert "dtsp_north_plaza" in sector_map
    assert "dtsp_south_plaza" in sector_map
    assert "dtsp_door_a" in sector_map
    assert "dtsp_door_b" in sector_map
    assert "dtsp_seating" in sector_map
    assert "g03_seating" in sector_map

    # Restu priority & holding check
    restu_trajs = [t for t in replay["student_trajectories"] if t["hostel_id"] == "restu"]
    saujana_trajs = [t for t in replay["student_trajectories"] if t["hostel_id"] == "saujana"]
    tekun_trajs = [t for t in replay["student_trajectories"] if t["hostel_id"] == "tekun"]
    assert len(restu_trajs) > 0
    assert len(saujana_trajs) > 0
    assert len(tekun_trajs) > 0

    saujana_dep = min(t["segments"][1]["start_ms"] for t in saujana_trajs)
    restu_dep = min(t["segments"][1]["start_ms"] for t in restu_trajs)
    assert saujana_dep < restu_dep
    for t in restu_trajs:
        first_seg = t["segments"][0]
        assert first_seg["type"] == "wait"
        assert first_seg["place_id"] == "restu_origin"
        assert first_seg["start_ms"] == 0
        assert first_seg["end_ms"] >= 1500000

    # Bus trajectories check
    buses = replay["bus_trajectories"]
    assert len(buses) == 8
    coaches = [b for b in buses if b["vehicle_type"] == "coach"]
    electric = [b for b in buses if b["vehicle_type"] == "electric"]
    assert len(coaches) == 5
    assert len(electric) == 3
    for c in coaches:
        assert c["capacity"] == 80
        assert c["seated_capacity"] == 40
        assert c["usable_doors"] == 1
    for el in electric:
        assert el["capacity"] == 40
        assert el["seated_capacity"] == 28
        assert el["usable_doors"] == 1

    for b in buses:
        seg_types = {s["type"] for s in b["segments"]}
        assert "boarding" in seg_types
        assert "transit_loaded" in seg_types
        assert "alighting" in seg_types
        assert "transit_empty_return" in seg_types
        assert "turnaround" in seg_types

        return_segs = [s for s in b["segments"] if s["type"] == "transit_empty_return"]
        assert len(return_segs) >= 1
        for rs in return_segs:
            assert rs["leg_id"] == "leg_transit_return"
            assert len(rs["waypoints"]) >= 10
            assert rs["waypoints"][0] == [5.357215, 100.301437]
            assert rs["waypoints"][-1] == [5.356012, 100.293748]
