"""Test that arbitrary bookkeeping group size (20 vs 40 vs 80) cannot change physical clocks,
waiting metrics, fairness, or completion when students operate as one continuous supervised stream.
"""

from __future__ import annotations

import copy
import pytest

pytestmark = pytest.mark.slow

from usm_sim.benchmark import _extract_full_campus_milestones
from usm_sim.campus import build_whole_campus_full_cohort_case
from usm_sim.simulate import simulate


def _run_full_cohort_with_target_size(target_size: int, berths: int = 1) -> dict:
    scenario, policy = build_whole_campus_full_cohort_case()
    pol = copy.deepcopy(policy)
    pol["grouping"]["target_students"] = target_size
    pol["vehicle_dispatch_rule"]["simultaneous_boarding_berths"] = berths
    res = simulate(copy.deepcopy(scenario), pol)
    return res


@pytest.mark.parametrize("berths", [1, 4])
def test_group_size_invariance_20_40_80(berths: int):
    """Target sizes 20, 40, and 80 must yield invariant physical results under identical operational policy."""
    scenario, _ = build_whole_campus_full_cohort_case()
    results = {
        size: _run_full_cohort_with_target_size(size, berths=berths)
        for size in (20, 40, 80)
    }

    # 1. Status and conservation
    for size, res in results.items():
        assert res["status"] == "completed", f"Size {size} failed with status {res['status']}"
        m = res["measures"]
        assert m["completed_students"] == 3543, f"Size {size} completed {m['completed_students']} students"
        assert m["unfinished_students"] == 0
        cap_violations = [v for v in res.get("violations", []) if v.get("type") == "physical_capacity"]
        assert cap_violations == [], f"Size {size} had physical capacity violations: {cap_violations}"

    # 2. Venue allocation invariance
    venue_allocs = {}
    for size, res in results.items():
        dtsp_seated = sum(
            e.get("student_count", 1)
            for e in res["event_trace"]
            if e.get("event_type") == "seated_completion" and e.get("place_id") == "dtsp_seating"
        )
        g03_seated = sum(
            e.get("student_count", 1)
            for e in res["event_trace"]
            if e.get("event_type") == "seated_completion" and e.get("place_id") == "g03_seating"
        )
        venue_allocs[size] = (dtsp_seated, g03_seated)
        assert dtsp_seated == 3000, f"Size {size} DTSP seated was {dtsp_seated}, expected 3000"
        assert g03_seated == 543, f"Size {size} G03 seated was {g03_seated}, expected 543"

    assert venue_allocs[20] == venue_allocs[40] == venue_allocs[80]

    # 3. Vehicle load pulses invariance
    pulses = {}
    for size, res in results.items():
        pulse_list = [
            (round(e["time_ms"] / 1000.0, 3), e["resource_ids"][0], e["student_count"])
            for e in res["event_trace"]
            if e.get("event_type") == "departure" and "fleet" in str(e.get("resource_ids") or [])
        ]
        pulses[size] = pulse_list

    assert pulses[20] == pulses[40] == pulses[80], (
        f"Vehicle load pulses differ across group sizes:\n"
        f"  20 first 3: {pulses[20][:3]}, last 3: {pulses[20][-3:]}\n"
        f"  40 first 3: {pulses[40][:3]}, last 3: {pulses[40][-3:]}\n"
        f"  80 first 3: {pulses[80][:3]}, last 3: {pulses[80][-3:]}"
    )

    # 4. Milestone clocks invariance
    milestones = {
        size: _extract_full_campus_milestones(res["event_trace"], scenario)
        for size, res in results.items()
    }
    numeric_keys = [
        "hostel_departure_s",
        "first_exterior_arrival_s",
        "first_student_seated_s",
        "restu_cafe_release_s",
        "restu_bus_queue_arrival_s",
        "restu_first_coach_departure_s",
        "restu_first_alighting_s",
        "restu_first_exterior_arrival_s",
        "restu_first_seated_s",
        "restu_last_seated_s",
        "all_seated_completion_s",
    ]
    for key in numeric_keys:
        val20 = milestones[20].get(key)
        val40 = milestones[40].get(key)
        val80 = milestones[80].get(key)
        assert val20 is not None and val40 is not None and val80 is not None, f"Missing milestone {key}"
        assert abs(val20 - val40) < 1.0, f"Milestone {key} differs between 20 ({val20}) and 40 ({val40})"
        assert abs(val20 - val80) < 1.0, f"Milestone {key} differs between 20 ({val20}) and 80 ({val80})"

    # 5. Global wait metrics invariance (tolerance < 0.1%)
    m20 = results[20]["measures"]
    m40 = results[40]["measures"]
    m80 = results[80]["measures"]

    for metric in ("total_student_waiting_student_s", "mean_wait_s", "p95_wait_s", "max_hostel_mean_wait_s"):
        assert abs(m20[metric] - m40[metric]) <= max(1.0, 0.001 * m20[metric]), (
            f"Metric {metric} differs between 20 ({m20[metric]}) and 40 ({m40[metric]})"
        )
        assert abs(m20[metric] - m80[metric]) <= max(1.0, 0.001 * m20[metric]), (
            f"Metric {metric} differs between 20 ({m20[metric]}) and 80 ({m80[metric]})"
        )

    # 6. Per-hostel wait metrics invariance
    h20 = {h["hostel_id"]: h["mean_wait_s"] for h in m20["by_hostel"]}
    h40 = {h["hostel_id"]: h["mean_wait_s"] for h in m40["by_hostel"]}
    h80 = {h["hostel_id"]: h["mean_wait_s"] for h in m80["by_hostel"]}

    for hid in h20:
        assert abs(h20[hid] - h40[hid]) <= max(1.0, 0.001 * h20[hid]), (
            f"Hostel {hid} mean wait differs between 20 ({h20[hid]}) and 40 ({h40[hid]})"
        )
        assert abs(h20[hid] - h80[hid]) <= max(1.0, 0.001 * h20[hid]), (
            f"Hostel {hid} mean wait differs between 20 ({h20[hid]}) and 80 ({h80[hid]})"
        )


def test_fleet_dispatch_scheduled_flag_resets_preventing_starvation():
    """Verify that _fleet_dispatch_scheduled is cleared when check_fleet_dispatch fires,
    ensuring subsequent batch arrivals at later times can trigger vehicle dispatch."""
    from usm_sim.campus import build_whole_campus_full_cohort_case
    from usm_sim.simulate import validate_inputs, apply_grouping, _apply_release_rule
    from usm_sim.engine import Engine
    import heapq

    scenario, policy = build_whole_campus_full_cohort_case()
    sc_d = copy.deepcopy(scenario)
    pol_d = copy.deepcopy(policy)
    _apply_release_rule(sc_d, pol_d)
    apply_grouping(sc_d, pol_d)
    sc_d, pol_d = validate_inputs(sc_d, pol_d)
    eng = Engine(sc_d, pol_d)

    part = list(eng.parts.values())[0]
    stage = {"fleet_id": "rst_fleet"}
    # Temporarily remove available vehicles to simulate all vehicles busy
    orig_vids = list(eng.fleets["rst_fleet"]["vehicle_ids"])
    eng.fleets["rst_fleet"]["vehicle_ids"] = []

    eng._enqueue_batch(part, stage)
    assert eng._fleet_dispatch_scheduled.get("rst_fleet") is True

    # Pop and process check_fleet_dispatch event from heap
    item = heapq.heappop(eng.heap)
    assert item[3] == "check_fleet_dispatch"
    eng.now = item[0]
    eng._dispatch(item[3], item[4], item[5])

    # With the bug fixed, _fleet_dispatch_scheduled must be False even though no vehicle departed
    assert eng._fleet_dispatch_scheduled.get("rst_fleet") is False

    # Restore vehicles and enqueue next batch
    eng.fleets["rst_fleet"]["vehicle_ids"] = orig_vids
    part2 = list(eng.parts.values())[1]
    eng._enqueue_batch(part2, stage)

    # check_fleet_dispatch must be scheduled for the new batch
    has_check_event = any(it[3] == "check_fleet_dispatch" for it in eng.heap)
    assert has_check_event is True
