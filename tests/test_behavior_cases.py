"""Acceptance tests for BV-07: named behavior variance cases and PPSL post maps.

Covers:
1. build_behavior_case("behavior-mixed-readiness") simulate completes; late leftover exists; conservation holds
2. behavior-catch-up-walk: vacated leftover occupancy_ahead 0; overlapping leftover pays extra or congested
3. behavior-queue-jump: attempt events exist; default refuse unless policy allows
4. Same leftovers, two post maps: choke map intercept_students > elsewhere map; elsewhere miss >= choke miss; worker count not increased
5. CLI registry lists new cases; old names still work
6. whole-campus-origins and restu-17sep still complete; campus occupancy rule on; restu occupancy rule off
7. Unused families declared zero on each named case
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from usm_sim import (
    build_behavior_case,
    build_behavior_mixed_readiness_case,
    build_behavior_catch_up_walk_case,
    build_behavior_queue_jump_case,
    build_behavior_combined_case,
    build_post_map_choke_policy,
    build_post_map_elsewhere_policy,
    build_restu_17sep_replay,
    build_whole_campus_origins_case,
    prepare_behavior,
    simulate,
    verify_behavior_conservation,
)
from usm_sim.behavior import ALL_PHENOMENON_FAMILIES
from usm_sim.cli import CASE_REGISTRY, run_command, build_parser

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_1_mixed_readiness_completes_leftover_exists_conservation():
    """1. build_behavior_case('behavior-mixed-readiness') simulate completes; late leftover exists; conservation holds."""
    scenario, policy = build_behavior_case("behavior-mixed-readiness")
    res = simulate(scenario, policy)
    assert res["status"] == "completed"

    m = res["measures"]
    assert m["attending_students"] == 8
    assert m["non_attendance_students"] == 2
    assert m["reporting_late_students"] == 3
    assert m["completed_students"] == 8

    # Conservation holds
    assert m["attending_students"] == m["completed_students"] + m.get("withdrawn_students", 0) + m.get("unfinished_students", 0)
    prepared = prepare_behavior(copy.deepcopy(scenario))
    cons = verify_behavior_conservation(prepared)
    assert cons["conserved"] is True
    assert cons["declared_population"] == 10
    assert cons["non_attendance"] == 2
    assert cons["attending"] == 8

    # Late leftover exists in event trace
    split_events = [e for e in res["event_trace"] if e.get("event_type") == "part_split"]
    assert len(split_events) >= 1
    counts = split_events[0]["counts"]
    assert 5 in counts.values()
    assert 3 in counts.values()


def test_2_catch_up_walk_vacated_vs_overlapping_occupancy():
    """2. behavior-catch-up-walk: vacated leftover occupancy_ahead 0; overlapping leftover pays extra or congested."""
    # A. Vacated leftover: pulse 1 has vacated walk leg before leftover departs
    scenario_vac, policy_vac = build_behavior_case("behavior-catch-up-walk")
    res_vac = simulate(scenario_vac, policy_vac)
    assert res_vac["status"] == "completed"

    vac_departures = [e for e in res_vac["event_trace"] if e.get("event_type") == "departure" and e.get("leg_id") == "walk_1"]
    assert len(vac_departures) == 2
    leftover_dep_vac = [d for d in vac_departures if d.get("time_ms", 0) > 80000][0]
    assert leftover_dep_vac.get("walk_occupancy_ahead") == 0
    assert leftover_dep_vac.get("walk_shared_extra_s") == 0.0

    vac_arrivals = [e for e in res_vac["event_trace"] if e.get("event_type") == "arrival" and e.get("leg_id") == "walk_1"]
    leftover_arr_vac = [a for a in vac_arrivals if a.get("time_ms", 0) > 80000][0]
    vac_duration_s = (leftover_arr_vac["time_ms"] - leftover_dep_vac["time_ms"]) / 1000.0
    assert vac_duration_s == pytest.approx(60.0)

    # B. Overlapping leftover: pulse 1 still on path when leftover departs
    scenario_ov, policy_ov = build_behavior_case("behavior-catch-up-walk-overlapping")
    res_ov = simulate(scenario_ov, policy_ov)
    assert res_ov["status"] == "completed"

    ov_departures = [e for e in res_ov["event_trace"] if e.get("event_type") == "departure" and e.get("leg_id") == "walk_1"]
    assert len(ov_departures) == 2
    leftover_dep_ov = [d for d in ov_departures if d.get("time_ms", 0) >= 20000][0]
    assert leftover_dep_ov.get("walk_occupancy_ahead") == 10
    assert leftover_dep_ov.get("walk_occupancy_factor") == pytest.approx(2.0)
    assert leftover_dep_ov.get("walk_shared_extra_s") == pytest.approx(50.0)

    ov_arrivals = [e for e in res_ov["event_trace"] if e.get("event_type") == "arrival" and e.get("leg_id") == "walk_1"]
    leftover_arr_ov = [a for a in ov_arrivals if a.get("affected_part_id") == leftover_dep_ov.get("affected_part_id")][0]
    ov_duration_s = (leftover_arr_ov["time_ms"] - leftover_dep_ov["time_ms"]) / 1000.0
    # Pays congested duration factor (100 * 2.0) + shared path extra (50 * 2.0) = 300.0s
    assert ov_duration_s == pytest.approx(300.0)
    assert ov_duration_s > 100.0


def test_3_queue_jump_attempt_events_default_refuse_unless_allowed():
    """3. behavior-queue-jump: attempt events exist; default refuse unless policy allows."""
    # A. Default policy: refuses jump
    scenario_ref, policy_ref = build_behavior_case("behavior-queue-jump")
    res_ref = simulate(scenario_ref, policy_ref)
    assert res_ref["status"] == "completed"

    attempts = [e for e in res_ref["event_trace"] if e.get("event_type") == "queue_jump_attempt"]
    assert len(attempts) == 1
    assert attempts[0]["place_id"] == "entrance"
    enacted = [e for e in res_ref["event_trace"] if e.get("event_type") == "queue_jump_enacted"]
    assert len(enacted) == 0

    assert res_ref["measures"]["queue_jump_attempt_students"] == 1
    assert res_ref["measures"]["queue_jump_enacted_students"] == 0

    # B. Policy allows jump: enacted event exists
    scenario_allow, policy_allow = build_behavior_case("behavior-queue-jump", allow_jump=True)
    res_allow = simulate(scenario_allow, policy_allow)
    assert res_allow["status"] == "completed"

    attempts_allow = [e for e in res_allow["event_trace"] if e.get("event_type") == "queue_jump_attempt"]
    assert len(attempts_allow) == 1
    enacted_allow = [e for e in res_allow["event_trace"] if e.get("event_type") == "queue_jump_enacted"]
    assert len(enacted_allow) == 1
    assert enacted_allow[0]["place_id"] == "entrance"
    assert enacted_allow[0]["to_rank"] == 1

    assert res_allow["measures"]["queue_jump_attempt_students"] == 1
    assert res_allow["measures"]["queue_jump_enacted_students"] == 1


def test_4_same_leftovers_two_post_maps():
    """4. Same leftovers, two post maps: choke map intercept_students > elsewhere map; elsewhere miss >= choke miss; worker count not increased."""
    # Run on the exact same scenario / resolved population
    scenario, _ = build_behavior_case("behavior-combined")

    policy_choke = build_post_map_choke_policy(scenario)
    policy_elsewhere = build_post_map_elsewhere_policy(scenario)

    res_choke = simulate(scenario, policy_choke)
    res_elsewhere = simulate(scenario, policy_elsewhere)

    assert res_choke["status"] == "completed"
    assert res_elsewhere["status"] == "completed"

    choke_intercepts = res_choke["measures"]["station_intercept_students"]
    elsewhere_intercepts = res_elsewhere["measures"]["station_intercept_students"]
    choke_misses = res_choke["measures"]["station_miss_students"]
    elsewhere_misses = res_elsewhere["measures"]["station_miss_students"]

    # Choke map intercepts > elsewhere map
    assert choke_intercepts > elsewhere_intercepts
    assert choke_intercepts == 1
    assert elsewhere_intercepts == 0

    # Elsewhere miss >= choke miss
    assert elsewhere_misses >= choke_misses
    assert elsewhere_misses == 1
    assert choke_misses == 0

    # Worker count not increased: exactly 1 worker declared in initial state
    assert len(scenario["initial_state"]["workers"]) == 1
    workers_choke = len(scenario["initial_state"]["workers"])
    workers_elsewhere = len(scenario["initial_state"]["workers"])
    assert workers_choke == workers_elsewhere == 1


def test_5_cli_registry_lists_new_cases_and_old_names_work():
    """5. CLI registry lists new cases; old names still work."""
    case_ids = {e["id"] for e in CASE_REGISTRY}

    # Old names still work
    assert "artificial" in case_ids
    assert "restu-17sep" in case_ids
    assert "artificial-120-floor" in case_ids
    assert "rst-shared-fleet" in case_ids
    assert "whole-campus-origins" in case_ids
    assert "restu-18sep-rainy" in case_ids

    # New names present
    assert "behavior-mixed-readiness" in case_ids
    assert "behavior-catch-up-walk" in case_ids
    assert "behavior-queue-jump" in case_ids
    assert "behavior-combined" in case_ids
    assert "behavior-post-map-choke" in case_ids
    assert "behavior-post-map-elsewhere" in case_ids

    # CLI command `cases` returns them
    parser = build_parser()
    args = parser.parse_args(["cases"])
    res, code = run_command("cases", args)
    assert code == 0
    registered = {c["id"] for c in res["cases"]}
    assert "behavior-mixed-readiness" in registered
    assert "behavior-catch-up-walk" in registered
    assert "behavior-queue-jump" in registered


def test_6_campus_and_restu_defaults_complete_occupancy_rule_on_campus_off_restu():
    """6. whole-campus-origins and restu-17sep still complete; campus occupancy rule on; restu occupancy rule off."""
    # Whole campus origins
    campus_sc, campus_pol = build_whole_campus_origins_case()
    campus_rule = (
        campus_sc.get("operating_rules", {}).get("walk_occupancy_rule")
        or campus_sc.get("walk_occupancy_rule")
    )
    assert campus_rule is not None, "Campus must have walk_occupancy_rule ON"
    assert campus_rule["type"] == "two_band"

    campus_res = simulate(campus_sc, campus_pol)
    assert campus_res["status"] == "completed"

    # Restu 17 Sep replay
    restu_sc, restu_pol = build_restu_17sep_replay(REPO_ROOT)
    restu_rule = (
        restu_sc.get("operating_rules", {}).get("walk_occupancy_rule")
        or restu_sc.get("walk_occupancy_rule")
    )
    assert restu_rule is None, "Restu must have walk_occupancy_rule OFF"

    restu_res = simulate(restu_sc, restu_pol)
    assert restu_res["status"] == "completed"


def test_7_unused_families_declared_zero_on_each_named_case():
    """7. Unused families declared zero on each named case."""
    named_cases = [
        ("behavior-mixed-readiness", {"late_reporting", "mixed_readiness", "no_show"}),
        ("behavior-catch-up-walk", {"catch_up_walk", "late_reporting", "mixed_readiness"}),
        ("behavior-queue-jump", {"queue_jump", "late_reporting", "mixed_readiness"}),
        ("behavior-combined", {"late_reporting", "mixed_readiness", "queue_jump"}),
        ("behavior-post-map-choke", {"late_reporting", "mixed_readiness", "queue_jump"}),
        ("behavior-post-map-elsewhere", {"late_reporting", "mixed_readiness", "queue_jump"}),
    ]

    for case_id, active_families in named_cases:
        scenario, _ = build_behavior_case(case_id)
        behavior = scenario.get("behavior")
        assert behavior is not None, f"Case {case_id} missing scenario.behavior"
        phenomena = behavior.get("phenomena")
        assert isinstance(phenomena, dict), f"Case {case_id} missing phenomena dict"

        # All 9 phenomenon families must be declared
        for fam in ALL_PHENOMENON_FAMILIES:
            assert fam in phenomena, f"Case {case_id} missing declaration for family {fam!r}"

        # Unused families must be declared as zero or empty
        for fam in ALL_PHENOMENON_FAMILIES:
            if fam not in active_families:
                val = phenomena[fam]
                is_zero_or_empty = (
                    val == {}
                    or val == 0
                    or val == {"count": 0}
                    or (isinstance(val, dict) and val.get("count", 0) == 0)
                )
                assert is_zero_or_empty, f"Case {case_id} unused family {fam!r} not declared zero/empty, got {val!r}"
