"""Focused acceptance test for optimized whole-campus full-cohort operational plan."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

pytestmark = pytest.mark.benchmark
from usm_sim.benchmark import run_benchmark
from usm_sim.campus import build_whole_campus_full_cohort_case
from usm_sim.simulate import simulate

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_optimized_full_cohort_benchmark_plan_improves_metrics():
    """Verify that the operational plan evaluated by run_benchmark achieves material improvement.

    The plan must preserve all invariants while materially reducing waiting time,
    eliminating lateness past the 09:00:00 event start deadline, and improving
    service fairness across hostels.
    """
    report = run_benchmark(REPO_ROOT)
    assert report["status"] == "passed"
    assert report["total_students"] == 3543
    assert report["completed_students"] == 3543

    # Check venue allocation
    venue = report["venue_allocation"]
    assert venue["cohort_coverage_pct"] == 100.0
    assert venue["dtsp_seated"] == 3000
    assert venue["g03_seated"] == 543
    assert venue["total_seated"] == 3543

    # Check invariants: Tekun and Saujana priority, Restu dispatched last
    sc, pol = build_whole_campus_full_cohort_case()
    res = simulate(sc, pol)
    trace = res["event_trace"]
    tekun_deps = [
        e["time_ms"] / 1000.0
        for e in trace
        if e.get("event_type") == "departure"
        and e.get("hostel_composition", {}).get("tekun")
        and e.get("leg_id") == "leg_transit"
    ]
    saujana_deps = [
        e["time_ms"] / 1000.0
        for e in trace
        if e.get("event_type") == "departure"
        and e.get("hostel_composition", {}).get("saujana")
        and e.get("leg_id") == "leg_transit"
    ]
    restu_deps = [
        e["time_ms"] / 1000.0
        for e in trace
        if e.get("event_type") == "departure"
        and e.get("hostel_composition", {}).get("restu")
        and e.get("leg_id") == "leg_transit"
    ]

    assert tekun_deps and saujana_deps and restu_deps
    assert min(tekun_deps) < min(restu_deps)
    assert min(saujana_deps) < min(restu_deps)
    assert max(tekun_deps) < min(restu_deps)
    assert max(saujana_deps) < min(restu_deps)
    assert max(restu_deps) > max(tekun_deps)
    assert max(restu_deps) > max(saujana_deps)

    # Material optimization thresholds (invariant baseline: total=11.89M s, mean=3356.7 s, p95=5409.0 s, max_hostel=5000.3 s)
    wait = report["wait_times"]
    assert wait["total_waiting_student_s"] <= 11_000_000.0, (
        f"total_waiting_student_s {wait['total_waiting_student_s']} exceeds 11M s target"
    )
    assert wait["mean_wait_s"] <= 3100.0, (
        f"mean_wait_s {wait['mean_wait_s']} exceeds 3100s target"
    )
    assert wait["p95_wait_s"] <= 5600.0, (
        f"p95_wait_s {wait['p95_wait_s']} exceeds 5600s target"
    )
    assert wait["max_hostel_mean_wait_s"] <= 6500.0, (
        f"max_hostel_mean_wait_s {wait['max_hostel_mean_wait_s']} exceeds 6500s target"
    )

    # Milestone optimization thresholds
    ms = report["milestone_predictions"]
    # All seated must complete before the 09:00:00 event start deadline (baseline was 7690.0s / 08:38:10)
    assert ms["all_seated_completion_s"] <= 9000.0, (
        f"all_seated_completion_s {ms['all_seated_completion_s']} exceeds 09:00:00 event start deadline (9000s)"
    )
    # Restu release from cafe must be accelerated (baseline was 2897.0s)
    assert ms["restu_cafe_release_s"] <= 2000.0, (
        f"restu_cafe_release_s {ms['restu_cafe_release_s']} exceeds 2000s target"
    )
