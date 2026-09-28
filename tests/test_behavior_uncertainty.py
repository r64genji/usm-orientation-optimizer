"""Tests for BV-02: Behavior uncertainty resolution, keyed reproducibility, and policy validation."""

from __future__ import annotations

import copy
import pytest

from usm_sim import (
    SimulationError,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    compare_policies,
    resolve_behavior_bands,
    resolve_case,
    validate_policy_information,
)
from usm_sim.behavior import (
    ALL_PHENOMENON_FAMILIES,
    validate_behavior_spec,
    verify_behavior_conservation,
)
from usm_sim.uncertainty import (
    FORBIDDEN_POLICY_INFORMATION,
    RANGE_COVERAGE_NOTE,
    UNCERTAINTY_BANDS,
)


def _valid_phenomena_dict() -> dict[str, dict]:
    return {fam: {} for fam in ALL_PHENOMENON_FAMILIES}


def _make_scenario_with_unit(unit_id: str = "su_1", pop: int = 20) -> tuple[dict, dict]:
    scenario, policy = build_artificial_single_server_case()
    scenario["source_units"] = [
        {
            "id": unit_id,
            "hostel_id": "h_1",
            "declared_population": pop,
            "resolved_attendance": pop,
            "required_reporting_s": 0,
            "actual_reporting_s": 0,
            "readiness_s": 0,
            "late_assembly_s": 0,
            "non_attendance": 0,
            "withdrawn": 0,
        }
    ]
    members = [
        {"student_key": f"{unit_id}:{i:04d}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "h_1"}
        for i in range(pop)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": f"part_{unit_id}",
            "group_id": f"group_{unit_id}",
            "source_unit_id": unit_id,
            "members": members,
            "student_count": pop,
        }
    ]
    return scenario, policy


def test_1_same_seed_identical_selected_counts():
    """1. Same seed produces identical selected no-show and late counts; different seeds vary."""
    scenario, _ = _make_scenario_with_unit("su_1", pop=20)
    case_spec = {
        "case_id": "repeatable_behavior",
        "behavior": {
            "version": "1.0",
            "case_id": "repeatable_behavior",
            "mode": "resolved_band",
            "phenomena": _valid_phenomena_dict(),
            "source_unit_splits": {
                "su_1": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count_band": {"lower": 1, "base": 2, "upper": 4},
                        "evidence": {"category": "assumed", "note": "test no-show band"},
                    },
                    {
                        "cohort_id": "c_late",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "count_draw": {
                            "selection_rule": "keyed_int",
                            "bounds": [2, 5],
                            "units": "students",
                        },
                        "late_assembly_band": {"lower": 60, "base": 180, "upper": 360},
                        "evidence": {"category": "assumed", "note": "test late draw and band"},
                    },
                    {
                        "cohort_id": "c_ontime",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "assumed", "note": "test on-time remainder"},
                    },
                ]
            },
        },
    }

    res1 = resolve_case(scenario, case_spec, seed=42)
    res2 = resolve_case(scenario, case_spec, seed=42)

    # Inputs and metadata reproduce identically
    assert res1["random_seed"] == res2["random_seed"] == 42
    assert res1["source_units"] == res2["source_units"]
    assert res1["case_metadata"]["resolved_inputs"]["keys"] == res2["case_metadata"]["resolved_inputs"]["keys"]
    assert (
        res1["case_metadata"]["resolved_inputs"]["selected_values"]
        == res2["case_metadata"]["resolved_inputs"]["selected_values"]
    )

    u1 = res1["source_units"][0]
    u2 = res2["source_units"][0]
    assert u1["non_attendance"] == u2["non_attendance"]
    assert u1["attending"] == u2["attending"]
    assert u1["resolved_attendance"] == u2["resolved_attendance"]

    c1_late = next(c for c in u1["cohorts"] if c["cohort_id"] == "c_late")
    c2_late = next(c for c in u2["cohorts"] if c["cohort_id"] == "c_late")
    assert c1_late["count"] == c2_late["count"]
    assert c1_late["late_assembly_s"] == c2_late["late_assembly_s"]

    # Attending student keys preserved identically
    keys1 = [m["student_key"] for m in res1["initial_state"]["students"][0]["members"]]
    keys2 = [m["student_key"] for m in res2["initial_state"]["students"][0]["members"]]
    assert keys1 == keys2

    # Different seed can produce different keyed draw
    res_diff = resolve_case(scenario, case_spec, seed=999)
    assert res_diff["random_seed"] == 999
    # Key strings differ by seed
    assert res_diff["case_metadata"]["resolved_inputs"]["keys"] != res1["case_metadata"]["resolved_inputs"]["keys"]


def test_2_grouping_change_does_not_resample_members():
    """2. Changing grouping basis must not change sampled behavior draws or member allocation."""
    scenario, policy_floor = build_artificial_120_hostel_case(grouping_basis="floor")
    _, policy_wing = build_artificial_120_hostel_case(grouping_basis="wing")

    case_spec = {
        "case_id": "grouping_test",
        "behavior": {
            "version": "1.0",
            "case_id": "grouping_test",
            "mode": "resolved_band",
            "phenomena": {
                **_valid_phenomena_dict(),
                "no_show": {
                    "count_band": {"lower": 1, "base": 2, "upper": 3},
                    "evidence": {"category": "abraham", "note": "abraham estimate"},
                },
                "late_reporting": {
                    "count_band": {"lower": 2, "base": 3, "upper": 4},
                    "late_assembly_band": {"lower": 100, "base": 200, "upper": 300},
                    "evidence": {"category": "abraham", "note": "abraham estimate"},
                },
            },
        },
    }

    seed = 777
    res_floor = resolve_case(scenario, case_spec, seed=seed, grouping_basis="floor")
    res_wing = resolve_case(scenario, case_spec, seed=seed, grouping_basis="wing")

    # Grouping metadata differs
    assert res_floor["case_metadata"]["search_choice_grouping_basis"] == "floor"
    assert res_wing["case_metadata"]["search_choice_grouping_basis"] == "wing"

    # But behavior resolution is strictly identical across all source units
    b_floor = res_floor["case_metadata"]["resolved_inputs"]["behavior"]
    b_wing = res_wing["case_metadata"]["resolved_inputs"]["behavior"]
    assert b_floor["selected_values"] == b_wing["selected_values"]
    assert b_floor["keys"] == b_wing["keys"]

    for u_f, u_w in zip(res_floor["source_units"], res_wing["source_units"]):
        assert u_f["non_attendance"] == u_w["non_attendance"]
        assert u_f["attending"] == u_w["attending"]
        assert u_f["resolved_attendance"] == u_w["resolved_attendance"]
        assert u_f["cohorts"] == u_w["cohorts"]


def test_3_compare_policies_shares_identical_behavior_members():
    """3. Two policies compared in compare_policies receive the exact same resolved behavior members."""
    scenario, policy1 = _make_scenario_with_unit("su_1", pop=10)
    policy2 = copy.deepcopy(policy1)
    policy2["policy_id"] = "policy_alt"

    case_spec = {
        "case_id": "policy_compare_behavior",
        "behavior": {
            "version": "1.0",
            "case_id": "policy_compare_behavior",
            "mode": "resolved_band",
            "phenomena": _valid_phenomena_dict(),
            "source_unit_splits": {
                "su_1": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count_band": {"lower": 1, "base": 2, "upper": 3},
                        "evidence": {"category": "assumed", "note": "test no-show"},
                    },
                    {
                        "cohort_id": "c_late",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "count_band": {"lower": 1, "base": 2, "upper": 3},
                        "late_assembly_band": {"lower": 30, "base": 60, "upper": 90},
                        "evidence": {"category": "assumed", "note": "test late"},
                    },
                    {
                        "cohort_id": "c_ontime",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "assumed", "note": "test on-time remainder"},
                    },
                ]
            },
        },
    }

    comp = compare_policies(
        policies=[policy1, policy2],
        cases=[case_spec],
        base_scenario=scenario,
    )

    p1_id = policy1.get("policy_id", "policy_0")
    p1_out = comp["policies"][p1_id]["simulation_outputs"]["policy_compare_behavior"]
    p2_out = comp["policies"]["policy_alt"]["simulation_outputs"]["policy_compare_behavior"]
    # Both policies ran against the identical scenario snapshot
    snap1 = p1_out["input_snapshot"]["scenario"]
    snap2 = p2_out["input_snapshot"]["scenario"]

    assert snap1["source_units"] == snap2["source_units"]
    assert snap1["initial_state"]["students"] == snap2["initial_state"]["students"]
    assert (
        snap1["case_metadata"]["resolved_inputs"]["selected_values"]
        == snap2["case_metadata"]["resolved_inputs"]["selected_values"]
    )


def test_4_demand_band_plus_behavior_valid_and_oversize_rejected():
    """4. Demand band + behavior: counts valid for resolved population; oversize rejected without clipping."""
    # Base scenario has 20 students
    scenario, _ = _make_scenario_with_unit("su_1", pop=20)

    # 4a: Valid remainder allocation under lower demand (0.75 * 20 = 15 students)
    spec_lower = {
        "case_id": "demand_lower",
        "demand": "lower",
        "band": "lower",
        "behavior": {
            "source_unit_splits": {
                "su_1": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count_band": {"lower": 2, "base": 3, "upper": 4},
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                    {
                        "cohort_id": "c_late",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "count_band": {"lower": 3, "base": 4, "upper": 5},
                        "late_assembly_band": {"lower": 60, "base": 120, "upper": 180},
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                    {
                        "cohort_id": "c_ontime",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                ]
            }
        },
    }
    res_low = resolve_case(scenario, spec_lower, seed=42)
    u_low = res_low["source_units"][0]
    # In lower band: no-show=2, late=3 -> total=5; remainder=15-5=10
    assert u_low["declared_population"] == 15
    assert u_low["non_attendance"] == 2
    assert u_low["attending"] == 13
    assert u_low["resolved_attendance"] == 13
    cons = verify_behavior_conservation(res_low)
    assert cons["conserved"] is True

    # 4b: Oversize counts beyond post-demand population rejected (not silently clipped)
    spec_oversize = {
        "case_id": "demand_oversize",
        "demand": "lower",
        "band": "lower",
        "behavior": {
            "source_unit_splits": {
                "su_1": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count": 10,
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                    {
                        "cohort_id": "c_late",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "count": 10,
                        "late_assembly_s": 60,
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                    {
                        "cohort_id": "c_ontime",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "assumed", "note": "n"},
                    },
                ]
            }
        },
    }
    # Sum of fixed counts is 20, but lower demand population is 15 -> must raise SimulationError!
    with pytest.raises(SimulationError) as exc_over:
        resolve_case(scenario, spec_oversize, seed=42)
    assert "exceeds post-demand population" in exc_over.value.message
    assert exc_over.value.category == "invalid_value_or_unit"


def test_5_coverage_metadata_present_and_not_probability():
    """5. Coverage metadata present, range_interpretation = coverage_band, is_probability_distribution = False."""
    scenario, _ = _make_scenario_with_unit("su_1", pop=10)
    spec = {
        "case_id": "coverage_meta_test",
        "behavior": {
            "source_unit_splits": {
                "su_1": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count_band": {"lower": 1, "base": 2, "upper": 3},
                        "evidence": {"category": "abraham", "note": "abraham estimate"},
                    },
                    {
                        "cohort_id": "c_attending",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "measured", "note": "counted at gate", "context": "orientation day 1 gate count"},
                    },
                ]
            }
        },
    }

    res = resolve_case(scenario, spec, seed=123)
    meta = res["case_metadata"]

    assert meta["range_interpretation"] == "coverage_band"
    assert meta["is_probability_distribution"] is False
    assert meta["weights_describe"] == "benchmark_coverage"
    assert meta["coverage_note"] == RANGE_COVERAGE_NOTE

    resolved_inputs = meta["resolved_inputs"]
    assert "raw_bands" in resolved_inputs
    assert "selected_values" in resolved_inputs
    assert "keys" in resolved_inputs
    assert "seed" in resolved_inputs
    assert "provenance" in resolved_inputs

    # Check that keys contain seed, case ID, phenomenon, source-unit ID, cohort ID
    k_noshow = resolved_inputs["keys"]["su_1:c_noshow:count"]
    assert "123:coverage_meta_test:no_show:su_1:c_noshow" in k_noshow

    # Provenance contains validated evidence
    prov = resolved_inputs["provenance"]["su_1:c_noshow:count"]
    assert prov["category"] == "abraham"
    assert prov["note"] == "abraham estimate"

    prov_att = resolved_inputs["provenance"]["su_1:c_attending:count"]
    assert prov_att["category"] == "measured"
    assert prov_att["context"] == "orientation day 1 gate count"

    # Invalid evidence category (e.g. "unverified") must be rejected
    spec_bad_ev = copy.deepcopy(spec)
    spec_bad_ev["behavior"]["source_unit_splits"]["su_1"][0]["evidence"]["category"] = "unverified"
    with pytest.raises(SimulationError) as exc_bad_ev:
        resolve_case(scenario, spec_bad_ev, seed=123)
    assert exc_bad_ev.value.category == "unresolved_assumption"


def test_6_validate_policy_information_forbids_hidden_no_show_and_future_arrivals():
    """6. Policy cannot inspect hidden no-show truth or future arrivals."""
    valid_policy = {
        "policy_id": "valid_reactive",
        "release_rule": {"type": "fixed", "batch_size": 20},
    }
    validate_policy_information(valid_policy)

    # 6a: hidden_no_shows
    bad_noshow = copy.deepcopy(valid_policy)
    bad_noshow["hidden_no_shows"] = ["su_1:0001"]
    with pytest.raises(SimulationError) as exc_ns:
        validate_policy_information(bad_noshow)
    assert exc_ns.value.category == "unsupported_policy"
    assert "hidden_no_shows" in exc_ns.value.message

    # 6b: no_show_truth
    bad_truth = copy.deepcopy(valid_policy)
    bad_truth["assumptions"] = {"no_show_truth": True}
    with pytest.raises(SimulationError) as exc_tr:
        validate_policy_information(bad_truth)
    assert exc_tr.value.category == "unsupported_policy"
    assert "assumptions.no_show_truth" in exc_tr.value.message

    # 6c: future_arrivals
    bad_future = copy.deepcopy(valid_policy)
    bad_future["release_rule"]["future_arrivals"] = True
    with pytest.raises(SimulationError) as exc_fa:
        validate_policy_information(bad_future)
    assert exc_fa.value.category == "unsupported_policy"
    assert "release_rule.future_arrivals" in exc_fa.value.message
