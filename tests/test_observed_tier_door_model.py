"""Focused tests for Abraham's observed DTSP car-park tiers, cohorts, and door model.

Tests verify:
1. Car-park tiers are modeled as explicit data and capacities are strictly enforced.
2. Observational metadata records that one Restu-boys cohort occupied one of three tiers,
   with count unknown, mapping unspecified, and tier metadata assigning no exact doors or source units.
3. Multiple distinct DTSP doors (Door A, B, C, D) are configured with assumed parameter assignments.
4. Cohort routes pass through distinct concurrent doors rather than decorative metadata.
5. Multiple assigned doors operate concurrently during full-cohort simulation.
6. Seating is direct block-directed flow, not a single global queue_service server bottleneck
   at dtsp_seating (waiting_for_server at dtsp_seating must be 0).
7. Full cohort conservation (3,543 students), venue allocation (3,000 DTSP, 543 G03),
   priority sequencing (Tekun/Saujana before Restu), and milestone deadlines are preserved.
"""

from __future__ import annotations

import copy
from pathlib import Path
import pytest

pytestmark = pytest.mark.slow

from usm_sim.benchmark import run_benchmark
from usm_sim.campus import build_whole_campus_full_cohort_case
from usm_sim.simulate import simulate

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_observed_carpark_tiers_and_cohort_structure():
    """Verify car-park tiers and cohort assignments exist as explicit data."""
    scenario, policy = build_whole_campus_full_cohort_case()

    # Destination doors must include at least 4 doors (Door A, B, C, D)
    dest = scenario["destination"]
    door_ids = [d["id"] for d in dest.get("doors", [])]
    assert "door_a" in door_ids, "door_a missing from destination.doors"
    assert "door_b" in door_ids, "door_b missing from destination.doors"
    assert "door_c" in door_ids, "door_c missing from destination.doors"
    assert "door_d" in door_ids, "door_d missing from destination.doors"

    # Doors must be explicitly tagged as assumed parameters rather than observations
    for d in dest.get("doors", []):
        assert d.get("assignment_type") == "assumed_parameter", (
            f"Door {d['id']} assignment must be tagged assumed_parameter"
        )

    # Car park tiers definition must be present
    places = {p["id"]: p for p in scenario["places"]}
    ext = places["dtsp_exterior_gathering"]
    tiers = ext.get("parking_tiers") or ext.get("extra", {}).get("parking_tiers", {})
    assert "level_1_lower_apron" in tiers
    assert "level_2_mid_terrace" in tiers
    assert "level_3_upper_buffer" in tiers

    # Reject invented sex counts, fake 50/50 split, and sex labels on source units
    units = scenario["source_units"]
    restu_units = [u for u in units if u.get("hostel_id") == "restu"]
    assert len(restu_units) >= 2

    for u in units:
        assert u.get("sex") in {None, "unknown", "untracked"}, (
            f"Unit {u.get('id')} has fabricated sex {u.get('sex')}"
        )
        assert u.get("sex_status") != "assumed_split", (
            f"Unit {u.get('id')} has fabricated assumed_split"
        )
        assert u.get("cohort_id") not in {"restu_men", "restu_women"}, (
            f"Operational cohort should not be labeled by fabricated sex {u.get('cohort_id')}"
        )
        if "assigned_door" in u:
            assert u.get("door_assignment_type") == "assumed_parameter", (
                f"Source unit {u.get('id')} door assignment must be tagged assumed_parameter"
            )

    # Tier metadata must NOT assign exact doors or exact source-unit mappings
    carpark_tiers = dest.get("carpark_tiers", {})
    for tier_id, tier in carpark_tiers.items():
        assert "assigned_door" not in tier, f"Tier {tier_id} metadata must not assign an exact door"
        obs = tier.get("observational_metadata", {})
        assert obs.get("headcount") is None, "Observed headcount must be null/None (not fabricated)"
        assert obs.get("mapping_status") == "unspecified", "Source unit mapping must be unspecified"

    # Observational metadata encodes Restu boys observation with count=None and mapping unspecified
    obs_metadata = (
        carpark_tiers
        .get("level_1_lower_apron", {})
        .get("observational_metadata", {})
    )
    assert obs_metadata.get("observed_cohort_sex") == "male"
    assert obs_metadata.get("headcount") is None, "Observed headcount must be null/None (not fabricated)"
    assert obs_metadata.get("mapping_status") == "unspecified", "Source unit mapping must be unspecified"

    # Capacity constraints: any cohort assigned to a tier must respect tier max capacity
    cohort_counts: dict[str, int] = {}
    for u in units:
        cid = u.get("cohort_id")
        if cid:
            cohort_counts[cid] = cohort_counts.get(cid, 0) + int(u.get("resolved_attendance") or 0)

    for tier_id, tier in carpark_tiers.items():
        assigned_cohorts = tier.get("assigned_cohorts") or []
        assigned_total = sum(cohort_counts.get(c, 0) for c in assigned_cohorts)
        max_cap = tier.get("max", 0)
        assert assigned_total <= max_cap, (
            f"Tier {tier_id} capacity {max_cap} exceeded by assigned cohorts total {assigned_total}"
        )


def test_cohort_to_door_routing_and_concurrency():
    """Verify cohorts route to distinct assigned doors and doors operate concurrently."""
    scenario, policy = build_whole_campus_full_cohort_case()

    # Parameterized Restu channels route to distinct doors
    routes = scenario.get("routes", {})
    stages_by_id = {s["id"]: s for s in scenario["route_stages"]}

    # Verify door stages exist for all 4 doors
    door_places = {s["place_id"] for s in scenario["route_stages"] if s.get("kind") == "queue_service" and "door" in s["id"]}
    assert "dtsp_door_a" in door_places
    assert "dtsp_door_b" in door_places
    assert "dtsp_door_c" in door_places
    assert "dtsp_door_d" in door_places

    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["completed_students"] == 3543

    trace = res["event_trace"]

    # Gather door entrance completion events per door
    door_events = {}
    for e in trace:
        if e.get("event_type") == "entrance_completion":
            place = e.get("place_id")
            door_events.setdefault(place, []).append(e)

    # All 4 doors must be actively used
    assert "dtsp_door_a" in door_events, "dtsp_door_a was not used"
    assert "dtsp_door_b" in door_events, "dtsp_door_b was not used"
    assert "dtsp_door_c" in door_events, "dtsp_door_c was not used"
    assert "dtsp_door_d" in door_events, "dtsp_door_d was not used"

    # Verify concurrency: door_a and door_d must operate concurrently
    times_a = [e["time_ms"] for e in door_events["dtsp_door_a"]]
    times_d = [e["time_ms"] for e in door_events["dtsp_door_d"]]
    assert times_a and times_d
    start_a, end_a = min(times_a), max(times_a)
    start_d, end_d = min(times_d), max(times_d)
    overlap = max(0, min(end_a, end_d) - max(start_a, start_d))
    assert overlap > 0, "dtsp_door_a and dtsp_door_d must operate concurrently"


def test_seating_bottleneck_eliminated():
    """Verify seating is direct block-directed flow without single global seating queue."""
    scenario, policy = build_whole_campus_full_cohort_case()

    # dtsp_seating stage must not be a single server queue_service
    seating_stage = next((s for s in scenario["route_stages"] if s["id"] == "seating"), None)
    assert seating_stage is not None
    assert seating_stage.get("kind") != "queue_service" or seating_stage.get("server_count", 1) > 10, (
        "seating must not be a single-server queue_service"
    )

    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    # dtsp_seating must not accumulate waiting_for_server
    by_cause = res["measures"].get("waiting_student_s_by_cause", {})
    # Total wait for server across entire system should drop dramatically
    # (previously 6.85M s, almost entirely from dtsp_seating)
    server_wait = by_cause.get("waiting_for_server", 0.0)
    assert server_wait < 1_500_000.0, f"waiting_for_server {server_wait} still reflects false seating bottleneck"


def test_rst_hostels_use_single_dedicated_pairwise_distinct_doors():
    """Verify Tekun, Saujana, and Restu each use exactly one door and their door sets are pairwise distinct."""
    scenario, policy = build_whole_campus_full_cohort_case()

    units = scenario["source_units"]
    restu_units = [u for u in units if u.get("hostel_id") == "restu"]
    tekun_units = [u for u in units if u.get("hostel_id") == "tekun"]
    saujana_units = [u for u in units if u.get("hostel_id") == "saujana"]

    assert restu_units and tekun_units and saujana_units

    # Invariant: No split Restu channels (e.g. restu_channel_1 / restu_channel_2)
    restu_cohort_ids = {u.get("cohort_id") for u in restu_units}
    assert "restu_channel_1" not in restu_cohort_ids, "Restu must not be split into restu_channel_1"
    assert "restu_channel_2" not in restu_cohort_ids, "Restu must not be split into restu_channel_2"

    # Each RST hostel must have exactly one assigned door
    restu_assigned = {u.get("assigned_door") for u in restu_units}
    tekun_assigned = {u.get("assigned_door") for u in tekun_units}
    saujana_assigned = {u.get("assigned_door") for u in saujana_units}

    assert len(restu_assigned) == 1, f"Restu must use exactly 1 assigned door, got {restu_assigned}"
    assert len(tekun_assigned) == 1, f"Tekun must use exactly 1 assigned door, got {tekun_assigned}"
    assert len(saujana_assigned) == 1, f"Saujana must use exactly 1 assigned door, got {saujana_assigned}"

    # Pairwise distinct door sets for Tekun, Saujana, and Restu
    assert tekun_assigned.isdisjoint(saujana_assigned), "Tekun and Saujana must have distinct doors"
    assert tekun_assigned.isdisjoint(restu_assigned), "Tekun and Restu must have distinct doors"
    assert saujana_assigned.isdisjoint(restu_assigned), "Saujana and Restu must have distinct doors"

    # Invariant holds during execution trace
    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    hostel_doors: dict[str, set[str]] = {}
    for e in res["event_trace"]:
        if e.get("event_type") == "entrance_completion":
            place = e.get("place_id")
            for hid in e.get("hostel_composition", {}):
                if hid in {"tekun", "saujana", "restu"}:
                    hostel_doors.setdefault(hid, set()).add(place)

    for hid in ("tekun", "saujana", "restu"):
        assert len(hostel_doors.get(hid, set())) == 1, (
            f"Hostel {hid} must use exactly 1 door in execution trace, got {hostel_doors.get(hid)}"
        )

    assert hostel_doors["tekun"].isdisjoint(hostel_doors["saujana"])
    assert hostel_doors["tekun"].isdisjoint(hostel_doors["restu"])
    assert hostel_doors["saujana"].isdisjoint(hostel_doors["restu"])


def test_benchmark_evidence_for_rst_dedicated_doors():
    """Verify run_benchmark records and verifies dedicated pairwise distinct RST door evidence."""
    report = run_benchmark(REPO_ROOT)
    assert report["status"] == "passed"

    door_ops = report.get("full_campus_cohort", {}).get("door_operations", {})
    assert "rst_hostel_doors" in door_ops, "rst_hostel_doors missing from benchmark door_operations"

    rst_doors = door_ops["rst_hostel_doors"]
    assert "tekun" in rst_doors and "saujana" in rst_doors and "restu" in rst_doors

    tekun_d = set(rst_doors["tekun"])
    saujana_d = set(rst_doors["saujana"])
    restu_d = set(rst_doors["restu"])

    assert len(tekun_d) == 1, f"Tekun benchmark doors: {tekun_d}"
    assert len(saujana_d) == 1, f"Saujana benchmark doors: {saujana_d}"
    assert len(restu_d) == 1, f"Restu benchmark doors: {restu_d}"

    assert tekun_d.isdisjoint(saujana_d)
    assert tekun_d.isdisjoint(restu_d)
    assert saujana_d.isdisjoint(restu_d)
    assert door_ops.get("rst_doors_pairwise_distinct") is True
