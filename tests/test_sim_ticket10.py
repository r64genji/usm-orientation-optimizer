"""Acceptance tests for ticket 10: bounded search across grouping and operating choices."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from usm_sim import (
    SimulationError,
    bounded_search,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_restu_18sep_rainy_replay,
    build_rst_shared_fleet_case,
    build_two_hostel_wait_case,
    check_proposal,
    compute_pareto_set,
    resolve_case,
    search,
    simulate,
)
from usm_sim.search import generate_candidates

REPO_ROOT = Path(__file__).resolve().parent.parent


def _make_proposal(policy: dict, **overrides) -> dict:
    """Build a compliant human-written operating proposal from a base policy."""
    grouping = copy.deepcopy(policy.get("grouping") or {})
    regroup = copy.deepcopy(grouping.get("regroup_policy") or {"required": False})
    counting = copy.deepcopy(policy.get("counting") or {})
    if not isinstance(counting, dict):
        counting = {}
    counting.setdefault("assignments", {})
    counting.setdefault("placement", "none")
    counting.setdefault("method", None)

    proposal = {
        "proposal_id": policy.get("policy_id") or "human_search_proposal",
        "grouping": grouping,
        "regroup_policy": regroup,
        "release_rule": copy.deepcopy(
            policy.get("release_rule") or {"type": "immediate"}
        ),
        "counting": counting,
        "worker_allocation": {"assignments": [], "count": 0},
        "vehicle_dispatch_rule": copy.deepcopy(
            policy.get("vehicle_dispatch_rule") or {"type": "none"}
        ),
        "destination_rule": copy.deepcopy(
            policy.get("destination_rule") or {"type": "complete_after_stages"}
        ),
        "fixed_choices": {
            "required_endpoint": policy.get("required_endpoint"),
        },
        "tunable": {
            "grouping.basis": {
                "allowed": [
                    "floor",
                    "wing",
                    "building",
                    "target_size",
                    "mixed",
                ]
            },
            "grouping.units_per_group": {"lower": 1, "upper": 4, "unit": "units"},
            "grouping.maximum_assembly_wait_s": {"lower": 0, "upper": 300, "unit": "s"},
            "release_rule.interval_s": {"lower": 0, "upper": 120, "unit": "s"},
        },
        "assumptions": [
            {
                "id": "bounded_search_test_assumption",
                "label": "Bounded search test assumption",
                "kind": "grouping_choice",
                "status": "stated",
            }
        ],
    }
    proposal.update(overrides)
    return proposal


def _make_test_scenarios(scenario: dict) -> list[dict]:
    """Create a 2-case scenario set (base case and stress case) for tiny budget tests."""
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


def test_search_accepts_only_checked_proposals():
    """Invalid or unchecked proposals failing rules are rejected with structured SimulationError."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)

    # Missing proposal
    with pytest.raises(SimulationError) as exc_info:
        search(None, scenarios, base_scenario=scenario)
    assert exc_info.value.category in ("missing_input", "unsupported_policy")

    # Proposal with invalid structure (missing grouping)
    bad_proposal = {"proposal_id": "bad", "tunable": {}}
    with pytest.raises(SimulationError) as exc_info:
        search(bad_proposal, scenarios, base_scenario=scenario)
    assert exc_info.value.category in ("missing_input", "unsupported_policy")

    # Checked valid proposal works
    good_proposal = _make_proposal(policy)
    checked = check_proposal(good_proposal, scenario)
    assert checked["accepted"] is True

    res = search(
        checked,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )
    assert res["search_method"] == "bounded_search"
    assert len(res["evaluated_plans"]) > 0


def test_search_varies_grouping_and_operating_choices():
    """Bounded search varies floor, wing, building, target-size, mixed, assembly wait, and release interval."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 8, "max_cases_per_candidate": 2},
    )

    coverage = res["search_coverage"]
    assert coverage["candidates_evaluated"] <= 8
    assert len(coverage["grouping_bases_evaluated"]) >= 2
    assert "floor" in coverage["grouping_bases_evaluated"]
    assert any(
        b in coverage["grouping_bases_evaluated"]
        for b in ("wing", "building", "target_size", "mixed")
    )
    assert any("grouping.basis" in p for p in coverage["parameters_varied"])
    assert res["bounds"]["grouping.units_per_group"]["lower"] == 1
    assert res["bounds"]["grouping.units_per_group"]["upper"] == 4


def test_search_cannot_alter_fixed_facts_or_rst_route():
    """Search cannot alter attendance, physical limits, required counts, or RST route."""
    scenario, policy = build_rst_shared_fleet_case()
    scenarios = [resolve_case(scenario, {"case_id": "base"})]
    proposal = _make_proposal(policy)

    # Attempt to alter fixed attendance
    proposal_bad_att = copy.deepcopy(proposal)
    proposal_bad_att["fixed_choices"]["resolved_attendance"] = 999
    with pytest.raises(SimulationError):
        search(proposal_bad_att, scenarios, base_scenario=scenario)

    # Attempt to alter physical capacity
    proposal_bad_cap = copy.deepcopy(proposal)
    proposal_bad_cap["fixed_choices"]["physical_capacity_students"] = 1000
    with pytest.raises(SimulationError):
        search(proposal_bad_cap, scenarios, base_scenario=scenario)

    # Attempt to alter RST route
    proposal_bad_route = copy.deepcopy(proposal)
    proposal_bad_route["fixed_choices"]["route_id"] = "walk_all_the_way"
    with pytest.raises(SimulationError):
        search(proposal_bad_route, scenarios, base_scenario=scenario)


def test_candidates_evaluated_with_same_public_simulator_and_same_externals():
    """Every candidate is evaluated through simulate() with identical scenario demand and externals."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )

    # Every evaluated plan has simulation outputs for all required scenarios
    for plan in res["evaluated_plans"]:
        outputs = plan["simulation_outputs"]
        assert "case_base" in outputs
        assert "case_stress" in outputs
        for cid, sim_res in outputs.items():
            assert sim_res["status"] in ("completed", "incomplete", "infeasible")
            assert sim_res["scenario_id"] == scenario["scenario_id"]
            # Same demand
            assert sim_res["input_snapshot"]["scenario"]["hostels"] == scenario["hostels"]


def test_reactive_rules_use_delivered_reports_only_no_hidden_future():
    """Policies attempting to read hidden future information are rejected."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    # Inject forbidden future information
    bad_proposal = copy.deepcopy(proposal)
    bad_proposal["release_rule"]["hidden_future"] = "cheat_code"

    with pytest.raises(SimulationError) as exc_info:
        search(bad_proposal, scenarios, base_scenario=scenario)
    assert exc_info.value.category == "unsupported_policy"


def test_infeasible_or_incomplete_runs_stay_in_failure_records_not_feasible_set():
    """A hard stress failure disqualifies a plan from the feasible set, visible in failure records."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    # Base case and an extreme stress case with strict deadline constraint
    case_base = resolve_case(scenario, {"case_id": "base", "case_type": "typical"})
    case_stress = resolve_case(scenario, {"case_id": "stress", "case_type": "stress", "rain": True, "rain_factor": 2.0})

    proposal = _make_proposal(policy)

    # Enforce strict lateness: max_lateness_s == 0
    res = search(
        proposal,
        [case_base, case_stress],
        base_scenario=scenario,
        hard_constraints={"max_lateness_s": 0.0},
        evaluation_limits={"max_candidates": 5, "max_cases_per_candidate": 2},
    )

    # Any candidate that exceeded lateness in either case is excluded from feasible_plans
    for plan in res["evaluated_plans"]:
        if not plan["is_feasible"]:
            assert plan["policy_id"] not in res["feasible_policies"]
            assert plan["policy_id"] not in res["pareto_policies"]
            assert plan["policy_id"] in [f["policy_id"] for f in res["failure_records"]]
            assert len(plan["failed_cases"]) > 0


def test_five_objectives_reported_with_base_and_worst_case():
    """Comparison includes student waiting, lateness, worker effort, coordination effort, max hostel wait."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )

    expected_objectives = {
        "total_student_waiting",
        "lateness",
        "late_students",
        "reserved_worker_effort",
        "coordination_effort",
        "max_hostel_mean_wait",
    }

    assert len(res["feasible_plans"]) > 0
    sample_plan = res["feasible_plans"][0]
    obj_vals = sample_plan["objective_values"]

    for obj_name in expected_objectives:
        assert obj_name in obj_vals
        assert "base" in obj_vals[obj_name]
        assert "worst_case" in obj_vals[obj_name]
        assert isinstance(obj_vals[obj_name]["base"], (int, float))
        assert isinstance(obj_vals[obj_name]["worst_case"], (int, float))

    # Visible auxiliary metrics remain exposed
    visible = sample_plan["visible_metrics"]
    assert "outdoor_waiting_student_s" in visible
    assert "total_required_journey_student_s" in visible
    assert "operating_limit_exceedance" in visible
    assert "headcount_actions" in visible
    assert "vehicles" in visible


def test_pareto_set_retained_and_equivalent_policies_linked():
    """Pareto frontier retains tradeoffs, links equivalent policies, and is independent of input order."""
    # Test Pareto logic directly on known vectors
    objectives = [
        {"name": "wait", "field": "wait", "aggregation": "worst_case", "direction": "min"},
        {"name": "cost", "field": "cost", "aggregation": "worst_case", "direction": "min"},
    ]

    plan1 = {
        "policy_id": "P1",
        "objective_values": {"wait": {"worst_case": 100.0}, "cost": {"worst_case": 50.0}},
    }
    plan2 = {
        "policy_id": "P2",
        "objective_values": {"wait": {"worst_case": 80.0}, "cost": {"worst_case": 70.0}},
    }
    plan3_dominated = {
        "policy_id": "P3",
        "objective_values": {"wait": {"worst_case": 120.0}, "cost": {"worst_case": 80.0}},
    }
    plan4_equiv_p1 = {
        "policy_id": "P4",
        "objective_values": {"wait": {"worst_case": 100.0}, "cost": {"worst_case": 50.0}},
    }

    plans_forward = [plan1, plan2, plan3_dominated, plan4_equiv_p1]
    pareto_f, equiv_f = compute_pareto_set(plans_forward, objectives)

    pareto_ids_f = {p["policy_id"] for p in pareto_f}
    assert "P1" in pareto_ids_f
    assert "P2" in pareto_ids_f
    assert "P4" in pareto_ids_f
    assert "P3" not in pareto_ids_f  # P3 is strictly dominated by P1 and P2

    # Equivalence linking
    assert "P4" in equiv_f["P1"]
    assert "P1" in equiv_f["P4"]

    # Input order independence
    plans_reversed = [plan4_equiv_p1, plan3_dominated, plan2, plan1]
    pareto_r, equiv_r = compute_pareto_set(plans_reversed, objectives)
    pareto_ids_r = {p["policy_id"] for p in pareto_r}
    assert pareto_ids_f == pareto_ids_r


def test_search_repeatable_with_transparent_order_and_bounds():
    """Same proposals, versions, cases, and seeds produce the exact same candidate order and result."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)
    limits = {"max_candidates": 6, "max_cases_per_candidate": 2}

    run1 = search(copy.deepcopy(proposal), scenarios, base_scenario=scenario, evaluation_limits=limits, seed=99)
    run2 = search(copy.deepcopy(proposal), scenarios, base_scenario=scenario, evaluation_limits=limits, seed=99)

    assert run1["candidate_order"] == run2["candidate_order"]
    assert run1["candidates_attempted"] == run2["candidates_attempted"] == 6
    assert run1["stopping_reason"] == run2["stopping_reason"] == "evaluation_budget_reached"
    assert run1["feasible_policies"] == run2["feasible_policies"]
    assert run1["pareto_policies"] == run2["pareto_policies"]
    assert run1["bounds"] == run2["bounds"]

    # Compare objective values
    for p1, p2 in zip(run1["evaluated_plans"], run2["evaluated_plans"]):
        assert p1["policy_id"] == p2["policy_id"]
        assert p1["objective_values"] == p2["objective_values"]


def test_requested_cases_not_silently_dropped():
    """Search rejects requests where cases exceed max_cases_per_candidate rather than silently dropping."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = [
        resolve_case(scenario, {"case_id": f"c_{i}"}) for i in range(5)
    ]
    proposal = _make_proposal(policy)

    # Budget allows only 3 cases, but 5 requested
    with pytest.raises(SimulationError) as exc_info:
        search(
            proposal,
            scenarios,
            base_scenario=scenario,
            evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 3},
        )
    assert exc_info.value.category == "invalid_value_or_unit"
    assert "silently dropped" in str(exc_info.value)


def test_claims_best_plans_found_within_stated_search_no_final_independent():
    """Result claims 'best plans found within the stated search' and disallows final_independent dataset role."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 3, "max_cases_per_candidate": 2},
    )
    assert res["claim"] == "best plans found within the stated search"
    assert "best plans found within the stated search" in res["claims"]

    # Reject dataset_role == 'final_independent'
    with pytest.raises(SimulationError) as exc_info:
        search(
            proposal,
            scenarios,
            base_scenario=scenario,
            dataset_role="final_independent",
        )
    assert exc_info.value.category == "fixed_rule_violation"


def test_time_or_event_limit_remains_incomplete_not_cheap_completed():
    """A run that hits event limits remains incomplete and is disqualified from feasible recommendation."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)

    # Set tiny event limit so runs terminate as incomplete
    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={
            "max_candidates": 3,
            "max_cases_per_candidate": 2,
            "max_events_per_run": 5,  # Artificially low event limit
        },
    )

    # All plans must be disqualified due to incomplete status
    assert len(res["feasible_plans"]) == 0
    assert len(res["disqualified_plans"]) > 0
    for dq in res["disqualified_plans"]:
        reasons = " ".join(dq.get("reasons", []) + sum(dq.get("failure_reasons", {}).values(), []))
        assert "incomplete" in reasons or "Simulation status was" in reasons


def test_search_does_not_raise_scenario_event_limit():
    """Search must not raise a case's own max_events_per_run to the 1e6 default."""
    scenario, policy = build_rst_shared_fleet_case()
    original_limit = scenario["max_events_per_run"]
    assert original_limit < 1_000_000
    proposal = _make_proposal(policy)
    before_places = copy.deepcopy(scenario["places"])
    before_units = copy.deepcopy(scenario["source_units"])

    res = search(
        proposal,
        [resolve_case(scenario, {"case_id": "base"})],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
    )

    assert scenario["max_events_per_run"] == original_limit
    assert scenario["places"] == before_places
    assert scenario["source_units"] == before_units
    for plan in res["evaluated_plans"]:
        for sim_res in plan["simulation_outputs"].values():
            used = sim_res["input_snapshot"]["scenario"]["max_events_per_run"]
            assert used == original_limit


def test_search_rejects_ticket12_gps_holdout_cases():
    """Ticket-12 Restu GPS replays cannot be used to select a plan."""
    for builder in (build_restu_17sep_replay, build_restu_18sep_rainy_replay):
        scenario, policy = builder(REPO_ROOT)
        proposal = _make_proposal(policy)
        with pytest.raises(SimulationError) as exc_info:
            search(
                proposal,
                [scenario],
                base_scenario=scenario,
                evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
            )
        assert exc_info.value.category == "fixed_rule_violation"
        assert "GPS holdout" in str(exc_info.value) or "final_independent" in str(exc_info.value)


def test_search_evaluates_target_size_and_mixed_when_listed():
    """Listed grouping methods must actually run, not fail the proposal check for missing companions."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)
    attendance_before = copy.deepcopy(scenario["hostels"])

    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 8, "max_cases_per_candidate": 2},
    )

    bases = set(res["search_coverage"]["grouping_bases_evaluated"])
    assert "floor" in bases
    assert "target_size" in bases
    assert "mixed" in bases
    assert scenario["hostels"] == attendance_before
    for plan in res["evaluated_plans"]:
        assert set(plan["simulation_outputs"]) == {"case_base", "case_stress"}


def test_fairness_limit_disqualifies_from_feasible_set():
    """A fairness limit set before search removes plans that disadvantage a hostel past the limit."""
    scenario, policy = build_two_hostel_wait_case()
    proposal = _make_proposal(policy)
    proposal["fairness_limit"] = {"max_hostel_increase_vs_campus_s": 15}

    res = search(
        proposal,
        [resolve_case(scenario, {"case_id": "base"})],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 3, "max_cases_per_candidate": 1},
    )

    assert len(res["evaluated_plans"]) > 0
    sample = res["evaluated_plans"][0]
    fairness = sample["visible_metrics"]["fairness"]
    assert fairness["limit_configured"] is True
    assert fairness["disadvantaged_hostels"]
    if fairness["passed"] is False:
        assert sample["policy_id"] not in res["feasible_policies"]
        assert sample["policy_id"] not in res["pareto_policies"]
        assert sample["policy_id"] in [row["policy_id"] for row in res["failure_records"]]


def test_explicit_candidates_show_real_waiting_cost_differences():
    """Search uses the public simulator: different operating choices can change waiting cost."""
    scenario, policy = build_two_hostel_wait_case()
    immediate = _make_proposal(policy)
    immediate["proposal_id"] = "immediate_release"
    staggered = _make_proposal(policy)
    staggered["proposal_id"] = "staggered_release"
    staggered["release_rule"] = {"type": "fixed_interval", "interval_s": 60}

    res = search(
        [immediate, staggered],
        [resolve_case(scenario, {"case_id": "base"})],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
    )

    waits = [
        plan["objective_values"]["total_student_waiting"]["base"]
        for plan in res["evaluated_plans"]
        if plan["is_feasible"]
    ]
    assert len(res["evaluated_plans"]) == 2
    assert res["claim"] == "best plans found within the stated search"
    assert len(waits) >= 1
    if len(waits) == 2:
        assert waits[0] != waits[1]


def test_search_candidates_conserve_attending_students():
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = _make_test_scenarios(scenario)
    proposal = _make_proposal(policy)
    proposal["tunable"]["grouping.units_per_group"] = {
        "lower": 1,
        "upper": 1,
        "unit": "units",
    }
    res = search(
        proposal,
        scenarios,
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )
    assert res["evaluated_plans"]
    for plan in res["evaluated_plans"]:
        for sim_res in plan["simulation_outputs"].values():
            attending = sum(
                int(unit.get("resolved_attendance") or 0)
                for unit in sim_res["input_snapshot"]["scenario"]["source_units"]
            )
            completed = int(sim_res["measures"]["completed_students"])
            withdrawn = int(sim_res["measures"].get("withdrawn_students") or 0)
            unfinished = int(sim_res["measures"]["unfinished_students"])
            assert completed + withdrawn + unfinished == attending

def test_search_rejects_gps_replays_in_tuples_and_all_id_fields():
    """F06: Search rejects restu_17sep_replay and restu_18sep_rainy_replay in every ID field including (scenario, case_spec) tuples."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _make_proposal(policy)

    # 1. Tuple with GPS ID in scenario
    sc_gps = copy.deepcopy(scenario)
    sc_gps["scenario_id"] = "restu_17sep_replay"
    with pytest.raises(SimulationError) as exc:
        search(proposal, [(sc_gps, {"case_id": "c1"})], base_scenario=scenario)
    assert exc.value.category == "fixed_rule_violation"

    # 2. Tuple with GPS ID in case_spec
    with pytest.raises(SimulationError) as exc:
        search(proposal, [(scenario, {"scenario_id": "restu_18sep_rainy_replay"})], base_scenario=scenario)
    assert exc.value.category == "fixed_rule_violation"

    # 3. Operating rules ID
    sc_op = copy.deepcopy(scenario)
    sc_op["operating_rules"] = {"scenario_id": "restu_17sep_replay"}
    with pytest.raises(SimulationError) as exc:
        search(proposal, [sc_op], base_scenario=scenario)
    assert exc.value.category == "fixed_rule_violation"


def test_fixed_grouping_basis_not_expanded_unless_tunable():
    """F09: fixed grouping basis is not expanded unless tunable."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = _make_proposal(policy)
    proposal["fixed_choices"] = {"grouping.basis": "floor"}
    proposal["tunable"] = {"release_rule.interval_s": {"allowed": [60.0, 120.0]}}

    candidates = generate_candidates(
        proposal,
        search_space={"fixed_choices": {"grouping.basis": "floor"}, "tunable": {"release_rule.interval_s": {"allowed": [60.0, 120.0]}}},
        max_candidates=20,
        scenario=scenario,
    )
    # Grouping basis should remain 'floor' in all candidates, not expand to wing/building/etc.
    for cand in candidates:
        cand_basis = cand.get("grouping", {}).get("basis") or cand.get("parameters", {}).get("grouping.basis")
        assert cand_basis in (None, "floor")

    res = search(
        proposal,
        [resolve_case(scenario, {"case_id": "base"})],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 12, "max_cases_per_candidate": 1},
    )
    bases = set(res["search_coverage"]["grouping_bases_evaluated"])
    assert bases <= {"floor"}


def test_duplicate_physical_candidates_do_not_multiply_budget():
    """F09: Duplicate physical candidates do not multiply budget."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = [resolve_case(scenario, {"case_id": "base"})]
    p1 = _make_proposal(policy)
    p1["proposal_id"] = "p1"
    p2 = copy.deepcopy(p1)
    p2["proposal_id"] = "p2"

    res = search([p1, p2], scenarios, base_scenario=scenario)
    # 2 candidates against 1 scenario: because p2 is physically duplicate of p1,
    # it reuses simulation result and total_simulations is 1, not 2.
    assert res["search_coverage"]["total_simulations"] == 1


def test_rejected_candidates_count_toward_attempt_limit():
    """F09: Rejected candidates count toward attempt limit."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = [resolve_case(scenario, {"case_id": "base"})]
    # Create an invalid proposal that fails check
    bad = _make_proposal(policy)
    bad["proposal_id"] = "bad"
    bad["grouping"]["mode"] = "invalid_mode_xyz"

    good = _make_proposal(policy)
    good["proposal_id"] = "good"

    # max_candidates=1: after attempting bad, it reaches max_candidates and stops
    res = search([bad, good], scenarios, base_scenario=scenario, evaluation_limits={"max_candidates": 1})
    assert len(res["disqualified_plans"]) == 1
    assert len(res["evaluated_plans"]) == 0


def test_unknown_objective_names_error():
    """F09: Unknown objective names error."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenarios = [resolve_case(scenario, {"case_id": "base"})]
    proposal = _make_proposal(policy)

    with pytest.raises(SimulationError) as exc:
        search(proposal, scenarios, base_scenario=scenario, objectives=["totally_unknown_objective_xyz"])
    assert exc.value.category == "invalid_value_or_unit"

    from usm_sim.search import extract_objective_value

    with pytest.raises(SimulationError) as extract_exc:
        extract_objective_value("totally_unknown_objective_xyz", {"total_student_waiting_student_s": 99})
    assert extract_exc.value.category == "invalid_value_or_unit"


def test_simulation_error_on_one_stress_case_does_not_abort_later_candidates(monkeypatch):
    """F10: SimulationError on one stress case records failure and continues."""
    import importlib

    scenario, policy = build_artificial_120_hostel_case("floor")
    base = resolve_case(scenario, {"case_id": "case_base", "case_type": "typical"})
    stress = resolve_case(scenario, {"case_id": "case_stress", "case_type": "stress", "demand_factor": 1.5})
    p1 = _make_proposal(policy)
    p1["proposal_id"] = "first"
    p2 = _make_proposal(policy)
    p2["proposal_id"] = "second"
    p2["release_rule"] = {"type": "fixed_interval", "interval_s": 90.0}

    uncertainty_mod = importlib.import_module("usm_sim.uncertainty")
    real_simulate = uncertainty_mod.simulate

    def boom(sc, pol):
        if (sc.get("case_metadata") or {}).get("case_id") == "case_stress":
            raise SimulationError(
                "impossible_static_requirement",
                "stress case cannot be simulated",
                field="case_stress",
            )
        return real_simulate(sc, pol)

    monkeypatch.setattr(uncertainty_mod, "simulate", boom)

    res = search(
        [p1, p2],
        [base, stress],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 4, "max_cases_per_candidate": 2},
    )
    assert res["candidates_attempted"] == 2
    assert len(res["evaluated_plans"]) == 2
    assert len(res["feasible_plans"]) == 0
    for plan in res["evaluated_plans"]:
        assert "case_stress" in plan["failed_cases"]
        reasons = " ".join(sum(plan.get("failure_reasons", {}).values(), []))
        assert "Simulation status was infeasible" in reasons


def test_weighted_mean_uses_case_weights():
    """F09: Weighted-mean uses case weights."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    case1 = resolve_case(scenario, {"case_id": "case1"})
    case1["case_metadata"]["weight"] = 1.0
    case2 = resolve_case(scenario, {"case_id": "case2", "demand_factor": 1.5})
    case2["case_metadata"]["weight"] = 9.0

    proposal = _make_proposal(policy)
    res = search(
        [proposal],
        [case1, case2],
        base_scenario=scenario,
        objectives=[{"name": "total_student_waiting", "aggregation": "weighted_mean"}],
    )
    plan = res["evaluated_plans"][0]
    obj = plan["objective_values"]["total_student_waiting"]
    v1 = obj["all_cases"]["case1"]
    v2 = obj["all_cases"]["case2"]
    expected_w_mean = round((1.0 * v1 + 9.0 * v2) / 10.0, 4)
    assert obj["weighted_mean"] == expected_w_mean


def test_search_changing_supported_control_changes_evaluation_and_trace():
    scenario, policy = build_rst_shared_fleet_case(n_buses=2, bus_capacity=40)
    case = resolve_case(scenario, {"case_id": "c1"})
    
    prop1 = _make_proposal(policy)
    prop1["vehicle_dispatch_rule"] = {"type": "shared_fleet", "fleet_id": "rst_fleet", "bus_count": 1}
    
    prop2 = _make_proposal(policy)
    prop2["vehicle_dispatch_rule"] = {"type": "shared_fleet", "fleet_id": "rst_fleet", "bus_count": 2}
    
    res = search(
        [prop1, prop2],
        [case],
        base_scenario=scenario,
        evaluation_limits={"max_candidates": 2, "max_cases_per_candidate": 1},
        objectives=[{"name": "total_student_waiting", "aggregation": "mean"}],
    )
    assert len(res["evaluated_plans"]) == 2
    p1_val = res["evaluated_plans"][0]["objective_values"]["total_student_waiting"]["mean"]
    p2_val = res["evaluated_plans"][1]["objective_values"]["total_student_waiting"]["mean"]
    # Changing bus_count changes vehicle dispatch and total student waiting
    assert p1_val != p2_val
    assert p2_val < p1_val


def test_search_default_target_does_not_leak_hidden_attendance():
    from usm_sim.search import _default_target_students
    scenario, policy = build_artificial_120_hostel_case("floor")
    scenario["source_units"][0]["estimated_attendance"] = 15
    scenario["source_units"][0]["resolved_attendance"] = 99
    proposal = _make_proposal(policy)
    # Without existing target or bounds, default uses estimated attendance, not hidden 99
    target = _default_target_students(proposal, {}, scenario)
    assert target != 99
    assert target <= 20

