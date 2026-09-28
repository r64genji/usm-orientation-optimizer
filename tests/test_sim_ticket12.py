"""Acceptance tests for ticket 12: General simulator benchmark and calibration."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.benchmark
from usm_sim import (
    SimulationError,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_current_operation_policy,
    build_fixed_release_policy,
    build_queue_based_policy,
    build_restu_17sep_replay,
    build_restu_18sep_rainy_replay,
    build_rst_shared_fleet_case,
    build_ticket02_bus_case,
    build_two_hostel_wait_case,
    build_whole_campus_origins_case,
    build_whole_campus_full_cohort_case,
    OFFICIAL_2026_HOSTEL_COUNTS,
    emit_benchmark_report,
    run_benchmark,
    simulate,
)
from usm_sim.benchmark import (
    RAINY_18SEP_OFFSETS_S,
    RAINY_COACH_RIDE_S,
    default_rainy_gps_path,
)
from usm_sim.campus import HOSTEL_IDS, WALK_HOSTEL_IDS
from usm_sim.accuracy import evaluate_accuracy
from usm_sim.gps import RAINY_PLACE_WINDOWS, collect_window_stats, default_gps_path
from usm_sim.scenarios import (
    COACH_RIDE_RANGE_S,
    EXTERIOR_HOLD_OBSERVED_S,
    RESTU_OFFSETS_S,
    coach_duration_s,
    place_latlon,
)
from usm_sim.spillback_cases import build_shared_congestion_bus_case
from usm_sim.workers import build_exclusive_duty_case

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_whole_campus_baseline_real_life_policies():
    """Verify official baseline simulation with full campus cohort and realistic operational policies."""
    report = run_benchmark(REPO_ROOT)
    assert report["status"] == "passed"
    assert report["total_students"] == 3543
    assert report["completed_students"] == 3543

    # Realistic policies: 100% seated, no artificial door checks, DTSP 3000 cap + G03 overflow
    venue = report["venue_allocation"]
    assert venue["cohort_coverage_pct"] == 100.0
    assert venue["dtsp_seated"] == 3000
    assert venue["g03_seated"] == 543
    assert venue["total_seated"] == 3543

    # Check venue seating capacities
    full_sc, _ = build_whole_campus_full_cohort_case()
    places_map = {p["id"]: p for p in full_sc["places"]}
    assert venue["dtsp_seated"] <= places_map["dtsp_seating"]["capacity_students"]
    assert venue["g03_seated"] <= places_map["g03_seating"]["capacity_students"]
    assert places_map["g03_seating"]["capacity_students"] == 600
    assert places_map["g03_seating"]["operating_limit_students"] == 600

    # All 8 hostels accounted for
    wait = report["wait_times"]
    assert len(wait["by_hostel"]) == 8
    for hid, count in OFFICIAL_2026_HOSTEL_COUNTS.items():
        assert hid in wait["by_hostel"]
        assert wait["by_hostel"][hid]["completed_students"] == count

    # Fleet operations: Restu completes before 09:00:00 event start deadline
    ms = report["milestone_predictions"]
    assert ms["restu_last_seated_s"] <= 9000  # 09:00:00 deadline
    assert "06:30:00" in ms["hostel_departure_local"]

    # Tekun and Saujana depart first, Restu departs last
    sc, pol = build_whole_campus_full_cohort_case()
    res = simulate(sc, pol)
    trace = res["event_trace"]
    tekun_deps = [e["time_ms"] / 1000.0 for e in trace if e.get("event_type") == "departure" and e.get("hostel_composition", {}).get("tekun") and e.get("leg_id") == "leg_transit"]
    saujana_deps = [e["time_ms"] / 1000.0 for e in trace if e.get("event_type") == "departure" and e.get("hostel_composition", {}).get("saujana") and e.get("leg_id") == "leg_transit"]
    restu_deps = [e["time_ms"] / 1000.0 for e in trace if e.get("event_type") == "departure" and e.get("hostel_composition", {}).get("restu") and e.get("leg_id") == "leg_transit"]

    assert tekun_deps and saujana_deps and restu_deps
    assert min(tekun_deps) < min(restu_deps)
    assert min(saujana_deps) < min(restu_deps)
    assert max(tekun_deps) < min(restu_deps)
    assert max(saujana_deps) < min(restu_deps)
    assert max(restu_deps) > max(tekun_deps)
    assert max(restu_deps) > max(saujana_deps)


def test_restu_18sep_rainy_milestones_and_tolerances():
    """18 Sep rainy calibration: cafeteria shelter hold, release ~08:22:32, bus wait ~08:33:19, DTSP ~08:38:08, recording ends 08:43:53 NOT seated."""
    scenario, policy = build_restu_18sep_rainy_replay(REPO_ROOT)
    result = simulate(scenario, policy)

    assert result["status"] == "completed"
    assert scenario["start_time_local"] == "06:19:03"
    assert scenario["event_date"] == "2026-09-18"

    checks_by_id = {c["id"]: c for c in result["accuracy_checks"]}

    # 1. Cafeteria rain shelter release ~08:22:32 imposed
    shelter_rel = checks_by_id["shelter_release"]
    assert shelter_rel["imposed_input"] is True
    assert shelter_rel["counted_as_predicted_success"] is False
    assert shelter_rel["observed_local"] == "08:22:32"
    assert shelter_rel["observed_s"] == RAINY_18SEP_OFFSETS_S["shelter_release"]
    assert shelter_rel["predicted_s"] == 7409.0
    assert shelter_rel["signed_error_s"] == 0.0

    # 2. Bus wait ~08:33:19 predicted from engine travel, not copied GPS
    bus_wait = checks_by_id["bus_queue_arrival"]
    assert bus_wait["role"] == "predicted"
    assert bus_wait["observed_local"] == "08:33:19"
    assert bus_wait["observed_s"] == RAINY_18SEP_OFFSETS_S["bus_queue_arrival"]
    assert bus_wait["predicted_s"] != bus_wait["observed_s"]
    assert bus_wait["signed_error_s"] != 0.0
    assert bus_wait["abs_error_s"] <= 600.0
    assert bus_wait["passed"] is True

    # 3. Departure ~08:35:05 predicted
    dep = checks_by_id["bus_departure"]
    assert dep["role"] == "predicted"
    assert dep["observed_local"] == "08:35:05"
    assert dep["observed_s"] == RAINY_18SEP_OFFSETS_S["bus_departure"]
    assert dep["predicted_s"] != dep["observed_s"]
    assert dep["signed_error_s"] != 0.0
    assert dep["abs_error_s"] <= 600.0
    assert dep["passed"] is True

    # 4. DTSP ~08:38:08 predicted
    dtsp = checks_by_id["dtsp_side_arrival"]
    assert dtsp["role"] == "predicted"
    assert dtsp["observed_local"] == "08:38:08"
    assert dtsp["observed_s"] == RAINY_18SEP_OFFSETS_S["dtsp_side_arrival"]
    assert dtsp["predicted_s"] != dtsp["observed_s"]
    assert dtsp["signed_error_s"] != 0.0
    assert dtsp["abs_error_s"] <= 600.0
    assert dtsp["passed"] is True

    # 5. Coach ride in 120-270 s from engine travel, not the GPS 183 s interval
    coach = checks_by_id["coach_ride"]
    assert coach["role"] == "predicted_duration"
    assert COACH_RIDE_RANGE_S[0] <= coach["predicted_s"] <= COACH_RIDE_RANGE_S[1]
    assert coach["predicted_s"] != RAINY_COACH_RIDE_S
    assert coach["passed"] is True
    rain_coach_rec = next(
        row
        for row in scenario["source_records"]
        if row["field"] == "route_legs.leg_rain_coach_transit.duration_s"
    )
    assert "clamped" not in rain_coach_rec["method"]

    # 6. Recording ends 08:43:53 NOT seated
    rec_end = checks_by_id["recording_end_arrival"]
    assert rec_end["role"] in ("evidence_boundary", "unverified_endpoint")
    assert rec_end["observed_local"] == "08:43:53"
    assert rec_end["observed_s"] == RAINY_18SEP_OFFSETS_S["recording_end_arrival"]
    assert rec_end["predicted_s"] != rec_end["observed_s"]
    assert rec_end["signed_error_s"] != 0.0
    assert rec_end["abs_error_s"] <= 600.0
    assert rec_end["measured_accuracy_pass"] is False
    assert rec_end["counted_as_predicted_success"] is False
    assert rec_end["passed"] is False
    seated = checks_by_id["seated_completion"]
    assert seated["role"] == "unverified"
    assert seated["verified"] is False
    assert seated["counted_as_predicted_success"] is False
    assert "not confirmed" in seated["note"].lower()


def test_predicted_clocks_move_when_travel_duration_changes():
    """Predictions come from engine travel. Copying GPS into duration_s is forbidden."""
    scenario, policy = build_restu_18sep_rainy_replay(REPO_ROOT)
    base = simulate(copy.deepcopy(scenario), policy)
    base_checks = {c["id"]: c for c in base["accuracy_checks"]}

    for leg in scenario["route_legs"]:
        if leg["id"] == "leg_rain_walk_to_bus":
            leg["duration_s"] = int(leg["duration_s"]) + 90
    moved = simulate(scenario, policy)
    moved_checks = {c["id"]: c for c in moved["accuracy_checks"]}

    assert moved_checks["bus_queue_arrival"]["predicted_s"] != base_checks["bus_queue_arrival"]["predicted_s"]
    assert moved_checks["bus_queue_arrival"]["signed_error_s"] != base_checks["bus_queue_arrival"]["signed_error_s"]
    assert moved_checks["shelter_release"]["signed_error_s"] == 0.0


def test_restu_18sep_rainy_missing_gps_fails_clearly(tmp_path: Path):
    """When the 18 Sep GPS fixture file is missing, build_restu_18sep_rainy_replay raises SimulationError."""
    with pytest.raises(SimulationError) as caught:
        build_restu_18sep_rainy_replay(tmp_path)
    assert caught.value.category == "missing_input"
    assert "Location.csv" in caught.value.message


def test_hand_cases_calculations_hold():
    """Hand cases: one queue, one service, one bus cycle, one worker, two origins sharing a resource."""
    # 1. One queue & one service (4 students: 70, 80, 90, 100 s)
    ss_scenario, ss_policy = build_artificial_single_server_case()
    ss_result = simulate(ss_scenario, ss_policy)
    assert ss_result["status"] == "completed"

    completions = [r["completion_time_s"] for r in ss_result["outcomes"]["student_completions"]]
    assert completions == [70.0, 80.0, 90.0, 100.0]
    assert ss_result["measures"]["total_queue_waiting_student_s"] == pytest.approx(60.0)
    assert ss_result["measures"]["total_service_student_s"] == pytest.approx(40.0)
    assert ss_result["measures"]["late_students"] == 1
    late_student = [r for r in ss_result["outcomes"]["student_completions"] if r["late_s"] > 0][0]
    assert late_student["student_key"] == "s4"
    assert late_student["late_s"] == pytest.approx(5.0)

    # 2. One bus cycle
    bus_scenario, bus_policy = build_ticket02_bus_case(
        grouping_basis="wing", split_policy="keep_units_whole"
    )
    bus_result = simulate(bus_scenario, bus_policy)
    assert bus_result["status"] == "completed"
    assert bus_result["measures"]["completed_students"] == 120

    # 3. One worker exclusive duty
    w_scenario, w_policy = build_exclusive_duty_case()
    w_result = simulate(w_scenario, w_policy)
    assert w_result["status"] == "completed"
    assert w_result["measures"]["completed_students"] == 2

    # 4. Two origins sharing a resource
    two_scenario, two_policy = build_two_hostel_wait_case()
    two_result = simulate(two_scenario, two_policy)
    assert two_result["status"] == "completed"
    assert two_result["measures"]["total_student_waiting_student_s"] == pytest.approx(240.0)


def test_grouping_floors_wings_and_all_eight_hostels_unverified():
    """Grouping floors/wings/target sizes/remainders, all eight hostels, unmeasured hostels remain unverified."""
    # 1. Floor grouping: 3 groups of 40
    floor_sc, floor_pol = build_artificial_120_hostel_case("floor")
    floor_res = simulate(floor_sc, floor_pol)
    assert floor_res["status"] == "completed"
    assert len(floor_res["grouping"]["groups"]) == 3
    assert all(g["student_count"] == 40 for g in floor_res["grouping"]["groups"])

    # 2. Wing grouping: 2 groups of 60
    wing_sc, wing_pol = build_artificial_120_hostel_case("wing")
    wing_res = simulate(wing_sc, wing_pol)
    assert wing_res["status"] == "completed"
    assert len(wing_res["grouping"]["groups"]) == 2
    assert all(g["student_count"] == 60 for g in wing_res["grouping"]["groups"])

    # 3. Floor-and-wing grouping: 6 groups of 20
    fw_sc, fw_pol = build_artificial_120_hostel_case("floor_wing")
    fw_res = simulate(fw_sc, fw_pol)
    assert fw_res["status"] == "completed"
    assert len(fw_res["grouping"]["groups"]) == 6
    assert all(g["student_count"] == 20 for g in fw_res["grouping"]["groups"])

    # 4. Target size grouping with remainder: 50 + 50 + 20
    target_sc, target_pol = build_artificial_120_hostel_case(
        "floor",
        grouping_updates={
            "basis": "target_size",
            "target_students": 50,
            "split_policy": "permit_supervised_split",
        },
    )
    target_res = simulate(target_sc, target_pol)
    assert target_res["status"] == "completed"
    assert sorted(g["student_count"] for g in target_res["grouping"]["groups"]) == [20, 50, 50]

    # 5. All eight hostels
    campus_sc, campus_pol = build_whole_campus_origins_case()
    campus_res = simulate(campus_sc, campus_pol)
    assert campus_res["status"] == "completed"
    assert {row["hostel_id"] for row in campus_res["outcomes"]["per_hostel"]} == set(HOSTEL_IDS)
    assert len(campus_res["outcomes"]["per_hostel"]) == 8

    # 6. Unmeasured hostels unverified: do not claim campus-wide ±10 min from Restu alone
    unverified = [
        c
        for c in campus_res["accuracy_checks"]
        if c.get("role") in ("unverified", "unmeasured") or c.get("label") == "unverified"
    ]
    unverified_hostels = {c["hostel_id"] for c in unverified if "hostel_id" in c}
    assert set(WALK_HOSTEL_IDS) <= unverified_hostels
    assert "saujana" in unverified_hostels
    assert "tekun" in unverified_hostels
    for check in unverified:
        assert check["verified"] is False
        assert check["counted_as_predicted_success"] is False
        assert check["measured_accuracy_pass"] is False
        assert "Restu replay" in (check.get("note") or "")


def test_three_reference_policies_same_conditions_and_intervention_tradeoffs():
    """Three reference policies (current-operation, fixed-release, queue-based) evaluate same inputs without forced winner."""
    base_scenario, base_policy = build_rst_shared_fleet_case(n_buses=1)

    curr_policy = build_current_operation_policy(base_policy)
    fixed_policy = build_fixed_release_policy(base_policy, interval_s=120.0)
    queue_policy = build_queue_based_policy(base_policy, hold_threshold=40, resume_threshold=20)

    # Identical demand, budgets, deadlines, and externals
    res_curr = simulate(copy.deepcopy(base_scenario), curr_policy)
    res_fixed = simulate(copy.deepcopy(base_scenario), fixed_policy)
    res_queue = simulate(copy.deepcopy(base_scenario), queue_policy)

    assert res_curr["status"] == "completed"
    assert res_fixed["status"] == "completed"
    assert res_queue["status"] == "completed"

    assert res_curr["measures"]["completed_students"] == 60
    assert res_fixed["measures"]["completed_students"] == 60
    assert res_queue["measures"]["completed_students"] == 60
    assert (
        res_fixed["measures"]["total_student_waiting_student_s"]
        != res_curr["measures"]["total_student_waiting_student_s"]
    )
    assert base_scenario["deadline_s"] == copy.deepcopy(base_scenario)["deadline_s"]
    assert curr_policy["policy_id"] != fixed_policy["policy_id"] != queue_policy["policy_id"]

    # Test under a congested shared bottleneck: favored intervention need not win
    # More buses reduce pure bus waiting when fleet is limiting:
    sc_2bus, pol_2bus = build_rst_shared_fleet_case(n_buses=2)
    res_2bus = simulate(sc_2bus, pol_2bus)
    assert res_2bus["measures"]["total_student_waiting_student_s"] < res_curr["measures"]["total_student_waiting_student_s"]
    assert res_2bus["measures"]["total_student_waiting_student_s"] == 1940.0

    # But when downstream hall is the bottleneck, more buses dump into congestion and increase waiting:
    cong_1bus_sc, cong_1bus_pol = build_shared_congestion_bus_case(n_buses=1)
    cong_2bus_sc, cong_2bus_pol = build_shared_congestion_bus_case(n_buses=2)
    res_cong_1 = simulate(cong_1bus_sc, cong_1bus_pol)
    res_cong_2 = simulate(cong_2bus_sc, cong_2bus_pol)
    assert res_cong_2["measures"]["total_student_waiting_student_s"] > res_cong_1["measures"]["total_student_waiting_student_s"]


def test_determinism_and_student_accounting():
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)

    first = simulate(copy.deepcopy(scenario), policy)
    second = simulate(copy.deepcopy(scenario), policy)

    assert first["status"] == second["status"] == "completed"
    assert first["measures"] == second["measures"]
    assert len(first["event_trace"]) == len(second["event_trace"])

    # Verify student accounting: completed + withdrawn + unfinished == total resolved attendance
    total_resolved = sum(su["resolved_attendance"] for su in scenario["source_units"])
    completed_count = first["measures"]["completed_students"]
    unfinished_count = first["measures"]["unfinished_students"]
    withdrawn_count = len(first["outcomes"].get("withdrawn_students") or [])

    assert completed_count + unfinished_count + withdrawn_count == total_resolved
    assert completed_count == 40
    assert unfinished_count == 0


def test_benchmark_report_emission_and_content():
    """Benchmark report emitted to tests/fixtures/benchmark_report.json for full campus cohort."""
    report_path = emit_benchmark_report(REPO_ROOT)
    assert report_path.is_file()

    with report_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert data["benchmark_version"] == "1.0.0"
    assert data["status"] == "passed"
    assert data["completed_students"] == 3543
    assert data["total_students"] == 3543

    assert "full_campus_cohort" in data
    fc = data["full_campus_cohort"]
    assert fc["status"] == "completed"
    assert fc["total_students"] == 3543
    assert fc["completed_students"] == 3543

    wait = fc["wait_times"]
    assert wait["total_waiting_student_s"] > 0
    assert wait["mean_wait_s"] > 0
    assert wait["p95_wait_s"] is not None
    assert wait["max_hostel_mean_wait_s"] > 0
    assert len(wait["by_hostel"]) == 8
    for hid, count in OFFICIAL_2026_HOSTEL_COUNTS.items():
        assert hid in wait["by_hostel"]
        assert wait["by_hostel"][hid]["completed_students"] == count

    ms = fc["milestone_predictions"]
    assert ms["hostel_departure_s"] == 0.0
    assert "06:30:00" in ms["hostel_departure_local"]
    assert ms["first_exterior_arrival_s"] is not None
    assert ms["first_student_seated_s"] is not None
    assert ms["restu_bus_queue_arrival_s"] is not None
    assert ms["restu_first_coach_departure_s"] is not None
    assert ms["restu_first_alighting_s"] is not None
    assert ms["restu_first_exterior_arrival_s"] is not None
    assert ms["restu_first_seated_s"] is not None
    assert ms["restu_last_seated_s"] is not None
    assert ms["all_seated_completion_s"] is not None
    assert ms["total_journey_duration_s"] is not None

def test_coach_speed_very_low_fails_accuracy_check_not_clamped(monkeypatch):
    """F11: declared coach speed very low -> ride check fails instead of a clamped pass."""
    import usm_sim.scenarios as scenarios_mod

    low_speed = 1.0  # 1 m/s -> ~860s duration > 270s
    monkeypatch.setattr(scenarios_mod, "COACH_SPEED_DRY_M_S", low_speed)
    scenario, policy = scenarios_mod.build_restu_17sep_replay(REPO_ROOT)
    p1 = place_latlon(scenario["places"], "rst_boarding_approach")
    p2 = place_latlon(scenario["places"], "dtsp_alighting_area")
    d_slow = coach_duration_s(*p1, *p2, low_speed)
    assert d_slow > 270
    leg = next(row for row in scenario["route_legs"] if row["id"] == "leg_coach_transit")
    assert leg["duration_s"] == d_slow
    result = simulate(scenario, policy)
    checks_by_id = {c["id"]: c for c in result["accuracy_checks"]}
    coach_check = checks_by_id["coach_ride"]
    assert coach_check["predicted_s"] == float(d_slow)
    assert coach_check["passed"] is False
    assert coach_check["measured_accuracy_pass"] is False
    assert coach_check["counted_as_predicted_success"] is False


def test_opposite_endpoint_errors_cannot_hide_duration_error():
    """F13: Opposite endpoint errors cannot hide a duration error > 600 s when a total-duration check exists."""
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    # Synthetic trace with opposite endpoint errors:
    # observed: start=2748s, end=6468s, duration=3720s
    # predicted: start=2348s (error=-400s <= 600s), end=6868s (error=+400s <= 600s)
    # predicted duration = 6868 - 2348 = 4520s, duration error = 4520 - 3720 = 800s (> 600s)
    synthetic_trace = [
        {"event_type": "calendar_open", "calendar_id": "restu_release", "time_ms": 2348000, "event_id": "e_start"},
        {"event_type": "arrival", "place_id": "rst_bus_wait", "time_ms": 3708000, "event_id": "e_wait"},
        {"event_type": "departure", "leg_id": "leg_coach_transit", "time_ms": 4248000, "event_id": "e_dep"},
        {"event_type": "arrival", "place_id": "dtsp_alighting_area", "time_ms": 4458000, "event_id": "e_dtsp"},
        {"event_type": "calendar_open", "calendar_id": "hall_open", "time_ms": 6288000, "event_id": "e_hopen"},
        {"event_type": "arrival", "place_id": "dtsp_exterior_gathering", "time_ms": 4500000, "event_id": "e_ext"},
        {"event_type": "hall_area_arrival", "time_ms": 6868000, "event_id": "e_end"},
    ]
    checks = evaluate_accuracy(scenario, synthetic_trace)
    by_id = {c["id"]: c for c in checks}
    assert by_id["supervised_release"]["abs_error_s"] == 400.0 <= 600.0
    assert by_id["hall_area_arrival"]["abs_error_s"] == 400.0 <= 600.0
    assert by_id["hall_area_arrival"]["passed"] is True
    dur_check = by_id["total_journey_duration"]
    assert dur_check["predicted_s"] == 4520.0
    assert dur_check["observed_s"] == 3720.0
    assert dur_check["signed_error_s"] == 800.0
    assert dur_check["abs_error_s"] == 800.0 > 600.0
    assert dur_check["passed"] is False
    assert dur_check["measured_accuracy_pass"] is False


def test_imposed_duration_does_not_count_as_predicted_success():
    """F13: Imposed duration must not count as a predicted success."""
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    # Add an imposed duration check
    scenario["accuracy_references"].append({
        "id": "imposed_test_duration",
        "role": "predicted_duration",
        "imposed_input": True,
        "start_match": {"event_type": "calendar_open", "calendar_id": "restu_release"},
        "end_match": {"event_type": "hall_area_arrival"},
        "observed_s": 3720.0,
        "limit_s": 600.0,
    })
    result = simulate(scenario, policy)
    checks_by_id = {c["id"]: c for c in result["accuracy_checks"]}
    imp_check = checks_by_id["imposed_test_duration"]
    assert imp_check["imposed_input"] is True
    assert imp_check["counted_as_predicted_success"] is False
    assert imp_check["measured_accuracy_pass"] is False


def test_benchmark_fails_when_cohort_incomplete(monkeypatch):
    """Benchmark fails when the full campus cohort simulation is incomplete."""
    from usm_sim import benchmark
    orig_cohort = benchmark.build_whole_campus_full_cohort_case
    def failing_cohort():
        sc, pol = orig_cohort()
        sc["simulation_end_s"] = 100  # incomplete run
        return sc, pol
    monkeypatch.setattr(benchmark, "build_whole_campus_full_cohort_case", failing_cohort)
    report = benchmark.run_benchmark(REPO_ROOT)
    assert report["status"] == "failed"


def test_benchmark_fails_when_student_count_mismatch(monkeypatch):
    """Benchmark fails when completed students does not match the 3,543 cohort."""
    from usm_sim import benchmark
    orig_cohort = benchmark.build_whole_campus_full_cohort_case
    def modified_cohort():
        sc, pol = orig_cohort()
        sc["destination"]["available_seats"] = 1000  # seats cap causes incomplete seating
        return sc, pol
    monkeypatch.setattr(benchmark, "build_whole_campus_full_cohort_case", modified_cohort)
    report = benchmark.run_benchmark(REPO_ROOT)
    assert report["status"] == "failed"

def test_collect_window_stats_records_actual_gps_path():
    """F13: collect_window_stats records actual GPS file path used."""
    rain_path = default_rainy_gps_path(REPO_ROOT)
    rain_stats = collect_window_stats(rain_path, event_date="2026-09-18", windows=RAINY_PLACE_WINDOWS)
    assert rain_stats
    rain_sample = next(iter(rain_stats.values()))
    assert "session_3_2026-09-18_morning_M01_Rainy_to_DTSP_Location.csv" in rain_sample["source_path"]

    generic_path = default_gps_path(REPO_ROOT)
    generic_stats = collect_window_stats(generic_path, event_date="2026-09-17")
    assert generic_stats
    generic_sample = next(iter(generic_stats.values()))
    assert (
        "raw_data/sensor_logger/Location.csv" in generic_sample["source_path"]
        or "session_1_2026-09-17_morning_M08_to_DTSP_Location.csv" in generic_sample["source_path"]
    )

def test_17sep_perturb_walk_moves_signed_error():
    """Perturbing walk duration on 17 Sep changes predicted arrival and signed error."""
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    base = simulate(copy.deepcopy(scenario), policy)
    base_checks = {c["id"]: c for c in base["accuracy_checks"]}
    for leg in scenario["route_legs"]:
        if leg["id"] == "leg_supervised_approach":
            leg["duration_s"] = int(leg["duration_s"]) + 60
    moved = simulate(scenario, policy)
    moved_checks = {c["id"]: c for c in moved["accuracy_checks"]}
    assert moved_checks["bus_queue_arrival"]["predicted_s"] != base_checks["bus_queue_arrival"]["predicted_s"]
    assert moved_checks["bus_queue_arrival"]["signed_error_s"] != base_checks["bus_queue_arrival"]["signed_error_s"]
    assert moved_checks["supervised_release"]["signed_error_s"] == 0.0


def test_engine_version_identifies_software_revision_and_data_identity():
    from usm_sim.constants import ENGINE_VERSION, SOFTWARE_REVISION, FORMAT_VERSION
    assert ENGINE_VERSION != "0.6.0-ticket07-09"
    assert "ticket07-09" not in ENGINE_VERSION
    assert SOFTWARE_REVISION in ENGINE_VERSION
    assert SOFTWARE_REVISION != FORMAT_VERSION
    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    res = simulate(scenario, policy)
    versions = res["versions"]
    assert versions["engine_version"] == ENGINE_VERSION
    assert versions["software_revision"] == SOFTWARE_REVISION
    assert versions["data_version"] == scenario["data_version"]
    assert versions["format_version"] == scenario["format_version"]
    assert versions["software_revision"] != versions["format_version"]


def test_fleet_8_bus_mix_and_capacities():
    """Campus/RST fleet has 8 vehicles, 5+3 mix, both door counts 1, electric capacity != coach capacity."""
    campus_sc, campus_pol = build_whole_campus_origins_case()
    vehicles = campus_sc["initial_state"]["vehicles"]
    assert len(vehicles) == 8
    coaches = [v for v in vehicles if v["type"] == "coach"]
    electrics = [v for v in vehicles if v["type"] == "electric"]
    assert len(coaches) == 5
    assert len(electrics) == 3
    assert [v["id"] for v in coaches] == [f"coach_{i}" for i in range(1, 6)]
    assert [v["id"] for v in electrics] == [f"electric_{i}" for i in range(1, 4)]

    types_by_id = {vt["id"]: vt for vt in campus_sc["vehicle_types"]}
    assert "coach" in types_by_id
    assert "electric" in types_by_id

    coach_type = types_by_id["coach"]
    electric_type = types_by_id["electric"]

    assert coach_type["usable_doors"] == 1
    assert electric_type["usable_doors"] == 1

    assert electric_type["capacity_students"] != coach_type["capacity_students"]
    assert coach_type["capacity_students"] == 80
    assert coach_type["seated_capacity_students"] == 40
    assert electric_type["capacity_students"] == 40
    assert electric_type["seated_capacity_students"] == 28

    rst_sc, rst_pol = build_rst_shared_fleet_case()
    assert len(rst_sc["initial_state"]["vehicles"]) == 8
    rst_types = {vt["id"]: vt for vt in rst_sc["vehicle_types"]}
    assert rst_types["coach"]["usable_doors"] == 1
    assert rst_types["electric"]["usable_doors"] == 1
    assert rst_types["electric"]["capacity_students"] != rst_types["coach"]["capacity_students"]
    assert rst_sc["fleets"][0]["boarding_berth_capacity"] == 1
    assert rst_sc["fleets"][0]["dropoff_space_capacity"] == 1
    assert rst_pol["vehicle_dispatch_rule"] == {"type": "shared_fleet", "fleet_id": "rst_fleet"}
    rst_res = simulate(rst_sc, rst_pol)
    assert rst_res["status"] == "completed"
    assert rst_res["measures"]["completed_students"] == 60


def test_two_successive_rst_groups_same_bus_returns_and_boards_again():
    """Two successive RST groups: first pulse departs; second group boards a vehicle whose id already completed an earlier outbound+return."""
    sc, pol = build_rst_shared_fleet_case(n_buses=1)
    res = simulate(sc, pol)
    assert res["status"] == "completed"

    events = res["event_trace"]
    coach_events = [e for e in events if "coach_1" in e.get("resource_ids", [])]
    return_events = [e for e in coach_events if e["event_type"] == "vehicle_return_complete"]
    assert len(return_events) >= 1
    first_return = return_events[0]
    first_return_time = first_return["time_ms"]

    departures = [
        e
        for e in coach_events
        if e["event_type"] == "departure" and e.get("leg_id") == "leg_transit"
    ]
    assert len(departures) >= 2
    early_dep = departures[0]
    later_dep = departures[1]
    assert early_dep["time_ms"] < first_return_time
    assert later_dep["time_ms"] > first_return_time

    # Campus simulation: 8 vehicle ids, and at least one vehicle has vehicle_return_complete then a later departure
    campus_sc, campus_pol = build_whole_campus_full_cohort_case()
    assert len(campus_sc["fleets"][0]["vehicle_ids"]) == 8
    campus_res = simulate(campus_sc, campus_pol)
    c_events = campus_res["event_trace"]
    c_returns = [e for e in c_events if e["event_type"] == "vehicle_return_complete"]
    assert len(c_returns) >= 1
    has_looping_bus = False
    for ret in c_returns:
        vid = ret["resource_ids"][0]
        ret_t = ret["time_ms"]
        later = [
            e
            for e in c_events
            if e["event_type"] == "departure"
            and e.get("leg_id") == "leg_transit"
            and vid in e.get("resource_ids", [])
            and e["time_ms"] > ret_t
        ]
        if later:
            has_looping_bus = True
            break
    assert has_looping_bus, "Campus simulation must have at least one vehicle_id with vehicle_return_complete then a later departure"

    # Extra waiting groups exceeding 520-seat fleet capacity force a return+reuse.
    wait_sc, wait_pol = build_rst_shared_fleet_case(units_per_hostel=10)
    wait_res = simulate(wait_sc, wait_pol)
    assert wait_res["status"] == "completed"
    assert wait_res["measures"]["completed_students"] == 600
    wait_events = wait_res["event_trace"]
    wait_returns = [e for e in wait_events if e["event_type"] == "vehicle_return_complete"]
    assert wait_returns
    wait_loop = False
    for ret in wait_returns:
        vid = ret["resource_ids"][0]
        later = [
            e
            for e in wait_events
            if e["event_type"] == "departure"
            and e.get("leg_id") == "leg_transit"
            and vid in e.get("resource_ids", [])
            and e["time_ms"] > ret["time_ms"]
        ]
        if later:
            wait_loop = True
            break
    assert wait_loop, "remaining RST demand must reuse a vehicle after vehicle_return_complete"


def test_electric_boarding_uses_one_door_and_type_field():
    """Electric boarding uses 1 door (changing usable_doors from 1 to 2 would change duration if dual-door)."""
    campus_sc, campus_pol = build_whole_campus_full_cohort_case()
    electric_type = next(vt for vt in campus_sc["vehicle_types"] if vt["id"] == "electric")
    assert electric_type["usable_doors"] == 1
    assert electric_type["id"] == "electric"

    setup = electric_type["boarding_setup_s"]
    per = electric_type["boarding_s_per_passenger_per_door"]
    n_students = 20
    dur_1_door = setup + n_students * per / 1
    dur_2_doors = setup + n_students * per / 2
    assert dur_1_door != dur_2_doors
    assert dur_1_door == 45.0
    assert dur_2_doors == 25.0

    sc1, pol1 = build_ticket02_bus_case(
        n_buses=1, bus_capacity=40, split_policy="permit_supervised_split"
    )
    sc1["vehicle_types"][0]["usable_doors"] = 1
    sc1["initial_state"]["vehicles"][0]["capacity_students"] = 40
    res1 = simulate(copy.deepcopy(sc1), pol1)

    sc2 = copy.deepcopy(sc1)
    sc2["vehicle_types"][0]["usable_doors"] = 2
    res2 = simulate(sc2, pol1)

    start1 = next(e["time_ms"] for e in res1["event_trace"] if e["event_type"] == "batch_start" and e.get("primary_cause") == "board")
    end1 = next(e["time_ms"] for e in res1["event_trace"] if e["event_type"] == "batch_complete" and e.get("primary_cause") == "board")
    dur1 = end1 - start1

    start2 = next(e["time_ms"] for e in res2["event_trace"] if e["event_type"] == "batch_start" and e.get("primary_cause") == "board")
    end2 = next(e["time_ms"] for e in res2["event_trace"] if e["event_type"] == "batch_complete" and e.get("primary_cause") == "board")
    dur2 = end2 - start2

    assert dur1 > dur2
    assert dur1 == 85000
    assert dur2 == 45000

    campus_res = simulate(campus_sc, campus_pol)
    boarded = {
        rid
        for e in campus_res["event_trace"]
        if e["event_type"] == "batch_start" and e.get("primary_cause") == "board"
        for rid in e.get("resource_ids", [])
    }
    assert any(rid.startswith("electric_") for rid in boarded)
    assert any(rid.startswith("coach_") for rid in boarded)


def test_fleet_provenance_and_declared_assumptions():
    """Provenance: every new number has source_records category assumed vs measured."""
    campus_sc, campus_pol = build_whole_campus_origins_case()
    assumptions = {a["id"]: a for a in campus_sc["uncertain_assumptions"]}
    assert "rst_fleet_size_8" in assumptions
    assert assumptions["rst_fleet_size_8"]["category"] == "assumed"
    assert "rst_fleet_mix_5_coach_3_electric" in assumptions
    assert assumptions["rst_fleet_mix_5_coach_3_electric"]["category"] == "assumed"
    assert "coach_capacity_80_seated_40_doors_1" in assumptions
    assert assumptions["coach_capacity_80_seated_40_doors_1"]["category"] == "assumed"
    assert "electric_capacity_40_seated_28_doors_1" in assumptions
    assert assumptions["electric_capacity_40_seated_28_doors_1"]["category"] == "assumed"
    assert "rst_return_travel_geodesic" in assumptions
    assert assumptions["rst_return_travel_geodesic"]["category"] == "assumed"
    assert "rst_origin_turnaround_60s" in assumptions
    assert assumptions["rst_origin_turnaround_60s"]["category"] == "assumed"
    assert "rst_boarding_berth_capacity_1" in assumptions
    assert assumptions["rst_boarding_berth_capacity_1"]["category"] == "assumed"
    assert "rst_dropoff_space_capacity_1" in assumptions
    assert assumptions["rst_dropoff_space_capacity_1"]["category"] == "assumed"

    src_records = {r["field"]: r for r in campus_sc["source_records"]}
    assert "fleets.rst_fleet.n_buses" in src_records
    assert src_records["fleets.rst_fleet.n_buses"]["category"] == "assumed"
    assert src_records["fleets.rst_fleet.n_buses"]["value"] == 8
    assert "vehicle_types.coach.capacity_students" in src_records
    assert src_records["vehicle_types.coach.capacity_students"]["value"] == 80
    assert "vehicle_types.electric.capacity_students" in src_records
    assert src_records["vehicle_types.electric.capacity_students"]["value"] == 40
    assert "vehicle_types.coach.usable_doors" in src_records
    assert src_records["vehicle_types.coach.usable_doors"]["value"] == 1
    assert "vehicle_types.electric.usable_doors" in src_records
    assert src_records["vehicle_types.electric.usable_doors"]["value"] == 1
    assert "vehicle_types.coach.turnaround_s" in src_records
    assert src_records["vehicle_types.coach.turnaround_s"]["value"] == 60.0
    assert "vehicle_types.coach.return_travel_s" in src_records
    assert src_records["vehicle_types.coach.return_travel_s"]["value"] == 155
    assert "fleets.rst_fleet.boarding_berth_capacity" in src_records
    assert src_records["fleets.rst_fleet.boarding_berth_capacity"]["value"] == 1
    assert "fleets.rst_fleet.dropoff_space_capacity" in src_records
    assert src_records["fleets.rst_fleet.dropoff_space_capacity"]["value"] == 1

def test_full_campus_cohort_case_properties():
    """Full campus cohort (3,543 students across all 8 hostels) with realistic doors and calibrated physics."""
    scenario, policy = build_whole_campus_full_cohort_case()

    assert scenario["scenario_id"] == "whole_campus_full_cohort_2026"
    assert scenario["simulation_end_s"] == 30000

    # 1. Total cohort counts
    total_students = sum(int(u["resolved_attendance"]) for u in scenario["source_units"])
    assert total_students == 3543
    assert sum(OFFICIAL_2026_HOSTEL_COUNTS.values()) == 3543

    hostels_by_id = {h["id"]: h for h in scenario["hostels"]}
    for hid, expected_cnt in OFFICIAL_2026_HOSTEL_COUNTS.items():
        h = hostels_by_id[hid]
        assert h["registration"] == expected_cnt
        assert h["expected_event_attendance"] == expected_cnt
        assert h["resolved_attendance"] == expected_cnt

    # 2. Doors open from the start, no artificial calendar barrier
    dest = scenario["destination"]
    assert dest["opening_time_s"] == 0.0
    assert dest["bag_check"] is False
    assert dest["security_service"] is False
    assert dest["available_seats"] == 3050
    places_by_id = {p["id"]: p for p in scenario["places"]}
    assert "g03_foyer_entrance" in places_by_id
    assert "g03_seating" in places_by_id
    assert places_by_id["g03_foyer_entrance"]["latitude_deg"] == pytest.approx(5.357119, abs=1e-6)
    assert places_by_id["g03_foyer_entrance"]["longitude_deg"] == pytest.approx(100.302499, abs=1e-6)
    assert places_by_id["dtsp_exterior_gathering"]["capacity_students"] == 600
    assert places_by_id["dtsp_exterior_gathering"]["operating_limit_students"] == 500

    hall_open_cal = next(c for c in scenario["calendars"] if c["id"] == "hall_open")
    assert hall_open_cal["open_time_s"] == 0.0
    assert policy["destination_rule"] == {"type": "complete_after_stages"}

    # 3. All hostels release at 06:00:00 (t=0.0); Restu dispatched last from Restu cafe
    for u in scenario["source_units"]:
        assert u["readiness_s"] == 0.0
        assert u["actual_reporting_s"] == 0.0
        if u["hostel_id"] == "restu":
            assert u.get("waiting_location") == "Restu cafe"
            assert u.get("queue_priority", 0) > 0
        elif u["hostel_id"] in ("tekun", "saujana"):
            assert u.get("queue_priority", 0) < 0
    # 4. Conservative physics calibration
    legs_by_id = {l["id"]: l for l in scenario["route_legs"]}
    assert legs_by_id["leg_approach_restu"]["duration_s"] == 960

    stages_by_id = {s["id"]: s for s in scenario["route_stages"]}
    assert stages_by_id["boarding"]["duration_s"] == 180
    assert stages_by_id["alighting"]["duration_s"] == 180

    fleet = scenario["fleets"][0]
    assert fleet["dropoff_space_capacity"] == 4


def test_full_campus_benchmark_report_content():
    """Benchmark report contains full campus cohort wait times and milestone predictions."""
    report_path = emit_benchmark_report(REPO_ROOT)
    with report_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert "full_campus_cohort" in data
    fc = data["full_campus_cohort"]
    assert fc["status"] == "completed"
    assert fc["total_students"] == 3543

    wait = fc["wait_times"]
    assert wait["mean_wait_s"] > 0
    assert wait["total_waiting_student_s"] > 0
    assert len(wait["by_hostel"]) == 8
    for hid, count in OFFICIAL_2026_HOSTEL_COUNTS.items():
        assert hid in wait["by_hostel"]
        assert wait["by_hostel"][hid]["completed_students"] == count

    ms = fc["milestone_predictions"]
    assert ms["first_exterior_arrival_s"] is not None
    assert ms["first_student_seated_s"] is not None
    assert ms["restu_bus_queue_arrival_s"] is not None
    assert ms["restu_first_exterior_arrival_s"] is not None
    assert ms["all_seated_completion_s"] is not None

    # Venue allocation: DTSP + G03 account for 100% of the 3,543 cohort
    assert "venue_allocation" in fc
    va = fc["venue_allocation"]
    assert va["dtsp_seated"] + va["g03_seated"] == 3543
    assert va["dtsp_seated"] > 0
    assert va["g03_seated"] > 0
    assert va["dtsp_seated"] <= 3000
    assert va["total_seated"] == 3543
    assert va["cohort_coverage_pct"] == 100.0


def test_restu_walking_physics_calibration():
    """Restu walking from DUD to overpass is strictly single file at ~0.42 m/s matching 07:49 trace."""
    from usm_sim.scenarios import RESTU_COLUMN_WALK_M_S, RESTU_BOARDING_SERVICE_S, RESTU_ALIGHTING_SERVICE_S
    assert RESTU_COLUMN_WALK_M_S == 0.42
    assert RESTU_BOARDING_SERVICE_S == 180
    assert RESTU_ALIGHTING_SERVICE_S == 180

    scenario, policy = build_restu_17sep_replay(REPO_ROOT)
    res = simulate(scenario, policy)
    checks = {c["id"]: c for c in res["accuracy_checks"]}
    bus_queue = checks["bus_queue_arrival"]
    assert bus_queue["passed"] is True
    assert abs(bus_queue["signed_error_s"]) <= 10.0
    assert bus_queue["predicted_local"].startswith("2026-09-17T07:49:")


def test_carpark_headcount_staging_and_g03_overflow():
    """Verify car park headcount staging station, single-file dispatch, and G03 overflow allocation."""
    scenario, policy = build_whole_campus_full_cohort_case()
    places = {p["id"]: p for p in scenario["places"]}
    legs = {l["id"]: l for l in scenario["route_legs"]}
    stages = {s["id"]: s for s in scenario["route_stages"]}
    shared = {r["id"]: r for r in scenario["shared_resources"]}

    # 1. Car park capacity: 500 safe, max 600
    carpark = places["dtsp_exterior_gathering"]
    assert carpark["capacity_students"] == 600
    assert carpark["operating_limit_students"] == 500
    tiers = carpark.get("parking_tiers", {})
    assert tiers.get("total_safe_seated") == 500
    assert tiers.get("max_capacity") == 600

    # 2. Mandatory PPSL headcount staging step at all gathering areas (5 minutes / 300s)
    for h_stage_id in ("carpark_headcount", "north_plaza_headcount", "south_plaza_headcount"):
        assert h_stage_id in stages
        h_stage = stages[h_stage_id]
        assert h_stage["kind"] == "hold"
        assert h_stage["until"]["duration_s"] == 300
        assert h_stage["until"]["cause"] == "headcount_staging"

    # 3. Single-file column egress (one file per gathering area in parallel)
    assert "path_carpark_single_file" in shared
    assert "path_north_plaza_single_file" in shared
    assert "path_south_plaza_single_file" in shared
    sf_res = shared["path_carpark_single_file"]
    assert sf_res.get("continuous_streaming") is True
    assert sf_res.get("capacity_students") is None
    assert sf_res["duration_s"] == 40
    assert "path_carpark_single_file" in legs["leg_hall_approach"]["shared_resource_ids"]
    assert "path_carpark_single_file" in legs["leg_carpark_to_g03"]["shared_resource_ids"]
    assert "path_north_plaza_single_file" in legs["leg_hall_approach_north"]["shared_resource_ids"]
    assert "path_south_plaza_single_file" in legs["leg_hall_approach_south"]["shared_resource_ids"]

    # 4. Bangunan G03 places and leg
    assert "g03_foyer_entrance" in places
    assert places["g03_foyer_entrance"]["latitude_deg"] == pytest.approx(5.357119, abs=1e-6)
    assert places["g03_foyer_entrance"]["longitude_deg"] == pytest.approx(100.302499, abs=1e-6)
    assert "g03_seating" in places
    assert places["g03_seating"]["capacity_students"] >= 400
    assert "leg_carpark_to_g03" in legs
    assert legs["leg_carpark_to_g03"]["distance_m"] >= 118

    # 5. Full cohort simulation and 100% seated accounting
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["completed_students"] == 3543

    trace = res["event_trace"]
    dtsp_seated = sum(e.get("student_count", 1) for e in trace if e.get("event_type") == "seated_completion" and e.get("place_id") == "dtsp_seating")
    g03_seated = sum(e.get("student_count", 1) for e in trace if e.get("event_type") == "seated_completion" and e.get("place_id") == "g03_seating")
    assert dtsp_seated + g03_seated == 3543
    assert dtsp_seated > 0
    assert g03_seated > 0
    assert dtsp_seated <= 3000
def test_dynamic_sequencing_delay_holds_restu_dispatch():
    """If another hostel is delayed, Restu dispatch is held dynamically so Restu still moves last."""
    scenario, policy = build_whole_campus_full_cohort_case()

    # Delay Saujana so its arrival is delayed (e.g. readiness at 1500s)
    for u in scenario["source_units"]:
        if u["hostel_id"] == "saujana":
            u["readiness_s"] = 1500.0
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    trace = res["event_trace"]

    saujana_deps = [e["time_ms"] / 1000.0 for e in trace if e.get("event_type") == "departure" and e.get("hostel_composition", {}).get("saujana") and e.get("leg_id") == "leg_transit"]
    restu_deps = [e["time_ms"] / 1000.0 for e in trace if e.get("event_type") == "departure" and e.get("hostel_composition", {}).get("restu") and e.get("leg_id") == "leg_transit"]

    assert saujana_deps and restu_deps
    # Restu first departure must be after Saujana has departed
    assert min(restu_deps) >= max(saujana_deps)
