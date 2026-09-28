"""Acceptance tests for ticket 11: AI proposal, search, and simulation loop."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from usm_sim import (
    SimulationError,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_current_operation_policy,
    build_fixed_release_policy,
    build_loop_proposal,
    build_queue_based_policy,
    build_restu_17sep_replay,
    build_restu_18sep_rainy_replay,
    build_rst_shared_fleet_case,
    build_two_hostel_wait_case,
    check_proposal,
    partition_accuracy_checks,
    replay_loop,
    resolve_case,
    run_loop,
    simulate,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_two_cases(scenario: dict) -> list[dict]:
    """Create a 2-case scenario set (base case and stress case) for small evaluation budget."""
    case_base = resolve_case(
        scenario,
        {"case_id": "case_base", "case_type": "typical", "rain": False},
        seed=42,
    )
    case_stress = resolve_case(
        scenario,
        {"case_id": "case_stress", "case_type": "stress", "rain": True, "rain_factor": 1.4},
        seed=42,
    )
    return [case_base, case_stress]


def test_loop_accepts_inputs_and_round_budget():
    """Loop accepts campus facts, fixed rules, permitted changes, development cases, and round budget."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy, grouping_basis="floor")

    result = run_loop(
        campus_facts=scenario,
        fixed_rules={"min_station_staff": 1},
        permitted_changes={"grouping.basis": ["floor", "wing"]},
        development_cases=dev_cases,
        round_budget=2,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )

    assert result["claim"] == "best choices found within the search"
    assert result["status"] == "completed"
    assert result["feasible_plan_found"] is True
    assert result["best_plan"] is not None
    assert result["budgets"]["round_budget"] == 2
    assert result["budgets"]["rounds_executed"] == 1
    assert result["dispatch_mode"] == "simulation_only"
    assert result["live_radio_performed"] is False
    assert result["production_dispatch_performed"] is False


def test_proposals_can_vary_grouping_and_operating_choices():
    """Human/fixture can propose floor/wing/building/target-size/mixed grouping plus operating choices."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    p_floor = build_loop_proposal(policy, proposal_id="prop_floor", grouping_basis="floor")
    p_wing = build_loop_proposal(policy, proposal_id="prop_wing", grouping_basis="wing")

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=2,
        proposals=[p_floor, p_wing],
        evaluation_limits={"max_candidates": 3, "max_cases_per_candidate": 2},
    )

    assert len(result["rounds"]) == 2
    assert result["rounds"][0]["status"] == "evaluated"
    assert result["rounds"][1]["status"] == "evaluated"
    assert result["rounds"][0]["proposal"]["grouping"]["basis"] == "floor"
    assert result["rounds"][1]["proposal"]["grouping"]["basis"] == "wing"
    assert result["feasible_plan_found"] is True


def test_occupancy_cannot_be_altered_by_proposals():
    """Occupancy is planning input. Cannot change attendance or physical limits to look better."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    # Attempt to change resident occupancy
    p_bad_occ = build_loop_proposal(policy, proposal_id="bad_occ")
    p_bad_occ["fixed_choices"]["resident_occupancy"] = 10

    res_occ = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[p_bad_occ],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert res_occ["feasible_plan_found"] is False
    assert res_occ["rounds"][0]["accepted"] is False
    assert res_occ["rounds"][0]["status"] == "rejected_at_check"
    assert res_occ["rounds"][0]["search_performed"] is False
    assert any(
        err.get("category") == "fixed_rule_violation" for err in res_occ["rounds"][0]["validation_errors"]
    )

    # Attempt to change physical capacity
    p_bad_cap = build_loop_proposal(policy, proposal_id="bad_cap")
    p_bad_cap["fixed_choices"]["physical_capacity_students"] = 9999

    res_cap = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[p_bad_cap],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert res_cap["feasible_plan_found"] is False
    assert res_cap["rounds"][0]["accepted"] is False
    assert res_cap["rounds"][0]["search_performed"] is False


def test_invalid_proposals_stop_at_check_no_search():
    """Invalid proposals stop at Check with field-specific errors, without starting search."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    # Proposal with missing required grouping block
    bad_proposal = {
        "proposal_id": "missing_grouping",
        "release_rule": {"type": "immediate"},
    }

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[bad_proposal],
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )

    assert result["status"] == "no_feasible_plan"
    assert result["feasible_plan_found"] is False
    assert len(result["rounds"]) == 1
    round_0 = result["rounds"][0]
    assert round_0["accepted"] is False
    assert round_0["status"] == "rejected_at_check"
    assert round_0["search_performed"] is False
    assert round_0["evaluated_choices"] == []
    assert any("grouping" in (err.get("field") or "") or "proposal" in (err.get("field") or "") for err in round_0["validation_errors"])

def test_every_performance_value_comes_from_simulation_untrusted_ai_claims_ignored():
    """AI-supplied queue times or success claims are not trusted output fields."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    proposal = build_loop_proposal(policy, proposal_id="ai_claim_proposal")
    # AI provides fake performance numbers
    proposal["ai_queue_time_s"] = 0.0
    proposal["predicted_success"] = True
    proposal["claimed_waiting_time_s"] = 1.0

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert result["feasible_plan_found"] is True
    best = result["best_plan"]
    assert best is not None

    # Verify that the untrusted fields were stripped and not adopted as measures
    assert "ai_queue_time_s" in result["rounds"][0]["untrusted_ai_fields_ignored"]
    assert "predicted_success" in result["rounds"][0]["untrusted_ai_fields_ignored"]

    measures = best["measures"]
    assert "ai_queue_time_s" not in measures
    assert "predicted_success" not in measures
    # Measures come strictly from simulator
    assert measures["total_student_waiting_student_s"] >= 0.0
    assert "mean_wait_s" in measures
    assert "max_hostel_mean_wait_s" in measures


def test_proposals_cannot_use_future_or_hidden_information():
    """Loop rejects policies referencing actual future conditions or hidden state."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    p_hidden = build_loop_proposal(policy, proposal_id="prop_hidden")
    p_hidden["release_rule"]["information_source"] = "actual_future_events"

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[p_hidden],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert result["feasible_plan_found"] is False
    assert result["rounds"][0]["accepted"] is False
    assert result["rounds"][0]["search_performed"] is False
    assert any(err.get("category") == "unsupported_policy" for err in result["rounds"][0]["validation_errors"])


def test_required_counts_stay_scenario_owned_no_fictional_headcount():
    """Group formation does not add fictional headcounts."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy, grouping_basis="wing")

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert result["feasible_plan_found"] is True
    # Initial scenario student count matches completed student count
    total_students = sum(u["estimated_attendance"] for u in scenario["source_units"])
    for plan in result["evaluated_choices"]:
        for c_id, sim_res in plan["simulation_outputs"].items():
            assert sim_res["measures"]["completed_students"] == total_students


def test_all_proposals_in_comparison_share_reference_policies_and_externals():
    """All proposals in comparison share reference policies, attendance, budget, cases, and externals."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy, grouping_basis="floor")

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    ref_comp = result["reference_comparisons"]
    assert ref_comp is not None
    policies = ref_comp["policies"]
    assert "reference_current_operation" in policies
    assert "reference_fixed_release" in policies
    assert "reference_queue_based" in policies
    # All policies were simulated against the exact same case IDs
    case_ids = ref_comp["shared_case_ids"]
    assert len(case_ids) == 2
    for p_id, p_info in policies.items():
        assert set(p_info["simulation_outputs"].keys()) == set(case_ids)


def test_distinguish_evidence_supported_checks_from_unverified_predictions():
    """Loop partitions evidence-supported +-10 min checks from unverified unmeasured predictions."""
    sample_checks = [
        {
            "id": "restu_supervised_movement",
            "role": "calibrated",
            "milestone_error_s": 120.0,
            "milestone_error_le_600s": True,
            "accuracy_status": "pass",
            "verified": True,
        },
        {
            "id": "unmeasured_hostel_walk",
            "role": "unmeasured",
            "accuracy_status": "not_demonstrated",
            "verified": False,
            "unmeasured": True,
        },
    ]

    partitioned = partition_accuracy_checks(sample_checks)
    assert len(partitioned["evidence_supported_checks"]) == 1
    assert partitioned["evidence_supported_checks"][0]["id"] == "restu_supervised_movement"
    assert len(partitioned["unverified_predictions"]) == 1
    assert partitioned["unverified_predictions"][0]["id"] == "unmeasured_hostel_walk"


def test_development_feedback_excludes_final_independent_holdouts():
    """Development cases cannot include final independent holdouts (restu_17sep_replay / rainy_replay)."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)

    # Attempt to feed holdout scenario into development loop
    bad_case = {"case_metadata": {"case_id": "restu_17sep_replay", "dataset_role": "final_independent"}}
    with pytest.raises(SimulationError) as exc_info:
        run_loop(
            campus_facts=scenario,
            development_cases=[bad_case],
            round_budget=1,
            proposals=[proposal],
        )
    assert exc_info.value.category == "fixed_rule_violation"


def test_replaying_recorded_proposals_reproduces_results_without_new_llm():
    """Replaying recorded proposals reproduces identical calculated results."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy, grouping_basis="floor")

    run_1 = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
        seed=123,
    )

    run_2 = replay_loop(
        run_1,
        campus_facts=scenario,
        development_cases=dev_cases,
        seed=123,
    )

    assert run_1["status"] == run_2["status"]
    assert run_1["feasible_plan_found"] == run_2["feasible_plan_found"]
    assert len(run_1["evaluated_choices"]) == len(run_2["evaluated_choices"])
    wait_1 = run_1["best_plan"]["measures"]["total_student_waiting_student_s"]
    wait_2 = run_2["best_plan"]["measures"]["total_student_waiting_student_s"]
    assert abs(wait_1 - wait_2) < 1e-6


def test_returns_no_feasible_plan_with_clear_reasons_does_not_invent_success():
    """When no plan is feasible, loop returns clear reasons and does not invent success."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy)

    # Set impossible hard constraint on max_lateness_s that disqualifies every plan
    impossible_constraints = {"max_lateness_s": -1.0}

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
        hard_constraints=impossible_constraints,
    )

    assert result["status"] == "no_feasible_plan"
    assert result["feasible_plan_found"] is False
    assert result["best_plan"] is None
    assert len(result["reasons"]) >= 1
    assert "failed hard constraints" in result["reasons"][0]


def test_claim_production_dispatch_is_forbidden():
    """Live radio transmission and production dispatch are strictly forbidden."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)

    with pytest.raises(SimulationError) as exc_info:
        run_loop(
            campus_facts=scenario,
            round_budget=1,
            proposals=[proposal],
            claim_production_dispatch=True,
        )
    assert exc_info.value.category in ("fixed_rule_violation", "unsupported_policy")

def test_callable_proposal_generator_uses_feedback_across_rounds():
    """Callable proposal generator receives round number and history to adapt proposals."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    def proposal_gen(round_num: int, history: list[dict]) -> dict | None:
        if round_num == 1:
            return build_loop_proposal(policy, proposal_id="gen_floor", grouping_basis="floor")
        elif round_num == 2:
            assert len(history) == 1
            assert history[0]["status"] == "evaluated"
            return build_loop_proposal(policy, proposal_id="gen_wing", grouping_basis="wing")
        return None

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=2,
        proposals=proposal_gen,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert len(result["rounds"]) == 2
    assert result["rounds"][0]["proposal"]["grouping"]["basis"] == "floor"
    assert result["rounds"][1]["proposal"]["grouping"]["basis"] == "wing"
    assert result["feasible_plan_found"] is True


def test_final_independent_evaluation_performed_after_selection():
    """Final independent cases are evaluated only after candidate selection is complete."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy, grouping_basis="floor")

    final_case = resolve_case(
        scenario,
        {"case_id": "case_independent_test", "case_type": "stress", "rain": False},
        seed=999,
    )
    final_case["case_metadata"]["dataset_role"] = "final_independent"

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        final_cases=[final_case],
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert result["feasible_plan_found"] is True
    assert result["final_independent_evaluation"] is not None
    final_eval = result["final_independent_evaluation"]
    assert final_eval["dataset_role"] == "final_independent"
    assert "case_independent_test" in final_eval["shared_case_ids"]


def test_structured_delay_explanations_in_loop_output():
    scenario, policy = build_rst_shared_fleet_case()
    proposal = build_loop_proposal(policy, grouping_basis="floor")

    result = run_loop(
        campus_facts=scenario,
        development_cases=[scenario],
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
    )

    assert result["feasible_plan_found"] is True
    assert "delay_explanations" in result
    assert len(result["delay_explanations"]) >= 1
    for delay in result["delay_explanations"]:
        assert "duration_s" in delay
        assert "primary_cause" in delay
        assert "cause" in delay
        assert delay["duration_s"] > 0


def test_previous_results_are_visible_to_proposal_generator():
    """Previous development results are part of the loop input and reach the generator."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    seen: dict = {}

    def proposal_gen(round_num: int, history: list[dict]) -> dict | None:
        seen["ids"] = [row.get("from") or row.get("proposal_id") for row in history]
        if round_num == 1:
            return build_loop_proposal(policy, proposal_id="from_history")
        return None

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        previous_results=[{"round": 0, "status": "evaluated", "from": "previous_run"}],
        round_budget=1,
        proposals=proposal_gen,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert "previous_run" in seen["ids"]
    assert result["previous_results_count"] == 1
    assert result["feasible_plan_found"] is True


def test_ticket12_gps_replays_cannot_be_used_to_select():
    """restu_17sep_replay and restu_18sep_rainy_replay stay out of selection."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)

    for builder in (build_restu_17sep_replay, build_restu_18sep_rainy_replay):
        holdout, holdout_policy = builder(REPO_ROOT)
        with pytest.raises(SimulationError) as campus_exc:
            run_loop(
                campus_facts=holdout,
                round_budget=1,
                proposals=[build_loop_proposal(holdout_policy)],
                evaluation_limits={"max_candidates": 1, "max_cases_per_candidate": 1},
            )
        assert campus_exc.value.category == "fixed_rule_violation"

        with pytest.raises(SimulationError) as dev_exc:
            run_loop(
                campus_facts=scenario,
                development_cases=[holdout],
                round_budget=1,
                proposals=[proposal],
                evaluation_limits={"max_candidates": 1, "max_cases_per_candidate": 1},
            )
        assert dev_exc.value.category == "fixed_rule_violation"

        disguised = copy.deepcopy(holdout)
        disguised["case_metadata"] = {"case_id": "dev_disguise", "dataset_role": "development"}
        with pytest.raises(SimulationError) as hidden_exc:
            run_loop(
                campus_facts=scenario,
                development_cases=[disguised],
                round_budget=1,
                proposals=[proposal],
                evaluation_limits={"max_candidates": 1, "max_cases_per_candidate": 1},
            )
        assert hidden_exc.value.category == "fixed_rule_violation"


def test_gps_final_cases_do_not_select_or_crash():
    """After selection, GPS cases may be evaluated. They cannot pick the plan."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy)
    restu_sc, _restu_pol = build_restu_17sep_replay(REPO_ROOT)

    result = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        final_cases=[restu_sc],
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )

    assert result["feasible_plan_found"] is True
    assert result["best_plan"] is not None
    selected_ids: set[str] = set()
    for plan in result["evaluated_choices"]:
        selected_ids |= set((plan.get("simulation_outputs") or {}).keys())
    assert "restu_17sep_replay" not in selected_ids
    assert set(selected_ids) == {"case_base", "case_stress"}
    final_eval = result["final_independent_evaluation"]
    assert final_eval is not None
    assert final_eval.get("used_for_selection") is False
    assert final_eval.get("dataset_role") == "final_independent"


def test_former_independent_case_used_to_adjust_is_relabelled():
    """A non-GPS final case later used to adjust is development evidence, not independent."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    follow_up = resolve_case(
        scenario,
        {"case_id": "was_independent", "case_type": "typical", "rain": False},
        seed=42,
    )
    follow_up["case_metadata"]["dataset_role"] = "final_independent"

    result = run_loop(
        campus_facts=scenario,
        development_cases=[follow_up],
        previous_results=[{"round": 0, "status": "evaluated", "from": "prior_independent_eval"}],
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
    )

    assert "was_independent" in result["relabelled_to_development"]
    assert result["feasible_plan_found"] is True
    assert result["final_independent_evaluation"] is None


def test_partition_separates_imposed_inputs_from_unmeasured_routes():
    partitioned = partition_accuracy_checks(
        [
            {
                "id": "restu_supervised_movement",
                "role": "calibrated",
                "milestone_error_s": 120.0,
                "milestone_error_le_600s": True,
                "accuracy_status": "pass",
                "verified": True,
            },
            {
                "id": "hall_open",
                "role": "imposed_input",
                "imposed_input": True,
                "measured_accuracy_pass": False,
            },
            {
                "id": "bus_queue_arrival",
                "role": "predicted",
                "measured_accuracy_pass": True,
                "abs_error_s": 12.0,
                "limit_s": 600,
            },
            {
                "id": "unmeasured_hostel_walk",
                "role": "unmeasured",
                "accuracy_status": "not_demonstrated",
                "verified": False,
                "unmeasured": True,
            },
        ]
    )
    evidence_ids = [row["id"] for row in partitioned["evidence_supported_checks"]]
    unverified_ids = [row["id"] for row in partitioned["unverified_predictions"]]
    assert "restu_supervised_movement" in evidence_ids
    assert "bus_queue_arrival" in evidence_ids
    assert "hall_open" not in evidence_ids
    assert "hall_open" not in unverified_ids
    assert "unmeasured_hostel_walk" in unverified_ids

def test_run_loop_strips_prior_final_holdout_results_from_history():
    """F06: run_loop strips prior final/holdout results from proposal-generator history."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)

    seen_history = []

    def generator(round_num, history):
        seen_history.extend(history)
        return build_loop_proposal(policy)

    prior_results = [
        {"round": 0, "status": "evaluated", "from": "regular_dev_run"},
        {"round": 0, "status": "final_evaluation", "dataset_role": "final_independent", "from": "holdout_eval"},
        {"round": 0, "scenario_id": "restu_17sep_replay", "from": "gps_replay_eval"},
    ]

    res = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=generator,
        previous_results=prior_results,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )
    # Generator only sees the sanitized regular development run, NOT holdout or GPS results
    history_sources = [h.get("from") for h in seen_history]
    assert "regular_dev_run" in history_sources
    assert "holdout_eval" not in history_sources
    assert "gps_replay_eval" not in history_sources


def test_loop_forwards_max_events_and_uses_declared_objectives():
    """F09: run_loop forwards max_events_per_run; selection uses declared objectives; global Pareto."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    p1 = build_loop_proposal(policy, proposal_id="p1")
    p2 = build_loop_proposal(policy, proposal_id="p2", release_rule={"type": "fixed_interval", "interval_s": 120.0})

    res = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=2,
        proposals=[p1, p2],
        objectives=["coordination_effort", "reserved_worker_effort"],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2, "max_events_per_run": 50000},
    )
    assert res["feasible_plan_found"] is True
    # Global Pareto across rounds computed
    assert "pareto_set" in res
    assert len(res["pareto_set"]) > 0
    # Selection picked best plan based on declared coordination_effort / reserved_worker_effort
    assert res["best_plan"] is not None


def test_reference_policies_are_frozen():
    """F09: Frozen reference policies."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    dev_cases = _make_two_cases(scenario)
    proposal = build_loop_proposal(policy)

    res = run_loop(
        campus_facts=scenario,
        development_cases=dev_cases,
        round_budget=1,
        proposals=[proposal],
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 2},
    )
    ref_comp = res["reference_comparisons"]
    assert ref_comp is not None
    assert ref_comp.get("reference_policies_frozen") is True
    for pid, p_info in ref_comp["policies"].items():
        if "reference" in pid:
            assert p_info.get("frozen", True) is True
