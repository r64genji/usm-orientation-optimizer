"""Acceptance tests for ticket 08: shared uncertainty cases and honest accuracy reporting."""

from __future__ import annotations

import copy
import pytest

from usm_sim import (
    SimulationError,
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_delayed_report_case,
    build_rst_shared_fleet_case,
    compare_policies,
    resolve_case,
    simulate,
    validate_policy_information,
)
from usm_sim.uncertainty import (
    PROPERTY_CLASSES,
    RANGE_COVERAGE_NOTE,
    UNCERTAINTY_BANDS,
)


def test_same_seed_reproduces_resolved_inputs_and_results():
    """Repeating the same case configuration reproduces the exact same inputs and results."""
    scenario, policy = build_artificial_single_server_case()
    case_spec = {
        "case_id": "repeatable_case",
        "rain": True,
        "rain_factor": 1.25,
        "demand": "base",
        "random_seed": 42,
    }

    res1 = resolve_case(scenario, case_spec, seed=42)
    res2 = resolve_case(scenario, case_spec, seed=42)

    assert res1["random_seed"] == res2["random_seed"] == 42
    assert res1["case_metadata"] == res2["case_metadata"]
    assert res1["route_legs"] == res2["route_legs"]
    assert res1["source_units"] == res2["source_units"]

    sim1 = simulate(res1, policy)
    sim2 = simulate(res2, policy)

    assert sim1["status"] == sim2["status"] == "completed"
    assert sim1["measures"] == sim2["measures"]
    times1 = [row["completion_time_s"] for row in sim1["outcomes"]["student_completions"]]
    times2 = [row["completion_time_s"] for row in sim2["outcomes"]["student_completions"]]
    assert times1 == times2


def test_changing_grouping_does_not_resample_weather():
    """Changing grouping basis must not change sampled weather or physical draws."""
    scenario, policy_floor = build_artificial_120_hostel_case(grouping_basis="floor")
    _, policy_wing = build_artificial_120_hostel_case(grouping_basis="wing")

    seed = 888
    res_floor = resolve_case(scenario, {"case_id": "weather_check", "rain_probability": 0.5}, seed=seed)
    res_wing = resolve_case(scenario, {"case_id": "weather_check", "rain_probability": 0.5}, seed=seed)

    # Weather draw and rain decision are identical
    floor_weather = res_floor["case_metadata"]["resolved_weather"]
    wing_weather = res_wing["case_metadata"]["resolved_weather"]
    assert floor_weather["key"] == wing_weather["key"] == f"{seed}:weather:campus"
    assert floor_weather["draw"] == wing_weather["draw"]
    assert floor_weather["rain"] == wing_weather["rain"]
    assert res_floor["route_legs"] == res_wing["route_legs"]

    # Simulating both policies executes with different grouping but identical weather
    sim_floor = simulate(res_floor, policy_floor)
    sim_wing = simulate(res_wing, policy_wing)
    assert sim_floor["status"] == "completed"
    assert sim_wing["status"] == "completed"


def test_shared_rain_affects_exposed_routes_together():
    """Shared rain delays all outdoor/exposed walking legs together across campus."""
    scenario, policy = build_rst_shared_fleet_case(n_buses=2)
    dry_case = resolve_case(scenario, {"case_id": "dry_case", "rain": False}, seed=123)
    rain_case = resolve_case(scenario, {"case_id": "rain_case", "rain": True, "rain_factor": 1.5}, seed=123)

    dry_legs = {leg["id"]: leg["duration_s"] for leg in dry_case["route_legs"]}
    rain_legs = {leg["id"]: leg["duration_s"] for leg in rain_case["route_legs"]}

    affected = rain_case["case_metadata"]["shared_conditions"]["affected_legs"]
    walk_ids = [leg["id"] for leg in scenario["route_legs"] if leg.get("mode") == "walk"]
    coach_ids = [leg["id"] for leg in scenario["route_legs"] if leg.get("mode") in ("bus", "coach")]
    assert len(affected) > 0
    assert set(walk_ids) <= set(affected)
    for leg_id in walk_ids:
        assert rain_legs[leg_id] == pytest.approx(dry_legs[leg_id] * 1.5)
    for leg_id in coach_ids:
        assert leg_id not in affected
        assert rain_legs[leg_id] == dry_legs[leg_id]

    sim_dry = simulate(dry_case, policy)
    sim_rain = simulate(rain_case, policy)
    assert sim_dry["status"] == "completed"
    assert sim_rain["status"] == "completed"
    assert (
        sim_rain["measures"]["total_required_journey_student_s"]
        > sim_dry["measures"]["total_required_journey_student_s"]
    )


def test_delayed_reports_reactive_policy_uses_only_delivered_info():
    """A reactive policy cannot act on undelivered reports or future state."""
    # With delay_s=30, Group B departs at 10s because the report of full destination is not delivered until 40s
    sc_delayed, pol_delayed = build_delayed_report_case(delay_s=30.0)
    sim_delayed = simulate(sc_delayed, pol_delayed)
    assert sim_delayed["status"] == "incomplete"

    trace_delayed = sim_delayed["event_trace"]
    b_depart = next(
        e for e in trace_delayed if e.get("event_type") == "departure" and e.get("affected_part_id") == "part_b"
    )
    delivered = [
        e for e in trace_delayed if e.get("event_type") == "report_delivered" and e.get("place_id") == "hall"
    ]
    first_full = next(e for e in delivered if int(e.get("occupancy_students") or 0) >= 4)
    # Group B departed before the report of full destination was delivered
    assert b_depart["time_ms"] < first_full["time_ms"]

    # Group C is scheduled later and is held because report arrived before Group C's departure
    c_depart = next(
        (e for e in trace_delayed if e.get("event_type") == "departure" and e.get("affected_part_id") == "part_c"),
        None,
    )
    assert c_depart is None

    # Test forbidden future / hidden state access
    bad_policy = copy.deepcopy(pol_delayed)
    bad_policy["future_weather"] = "rain"
    with pytest.raises(SimulationError) as exc:
        validate_policy_information(bad_policy)
    assert exc.value.category == "unsupported_policy"


def test_low_and_high_demand_cases():
    """Lower and upper demand cases scale student attendance and measures."""
    scenario, policy = build_artificial_single_server_case()

    low_sc = resolve_case(scenario, {"case_id": "case_low", "demand": "low", "band": "lower"})
    base_sc = resolve_case(scenario, {"case_id": "case_base", "demand": "base", "band": "base"})
    high_sc = resolve_case(scenario, {"case_id": "case_high", "demand": "high", "band": "upper"})

    assert low_sc["case_metadata"]["uncertainty_band"] == "lower"
    assert base_sc["case_metadata"]["uncertainty_band"] == "base"
    assert high_sc["case_metadata"]["uncertainty_band"] == "upper"

    sim_low = simulate(low_sc, policy)
    sim_base = simulate(base_sc, policy)
    sim_high = simulate(high_sc, policy)

    n_low = sim_low["measures"]["wait_denominator_students"]
    n_base = sim_base["measures"]["wait_denominator_students"]
    n_high = sim_high["measures"]["wait_denominator_students"]

    assert n_low < n_base < n_high
    assert sim_low["measures"]["total_student_waiting_student_s"] < sim_high["measures"]["total_student_waiting_student_s"]


def test_plan_passes_base_but_fails_required_stress_case():
    """A plan that passes the base case but fails a required stress case is disqualified and named."""
    scenario, policy = build_artificial_single_server_case()
    # Baseline: 60s walk + 10s service -> completions at 70, 80, 90, 100s.
    # Set deadline to 105s so base case has 0 lateness and passes.
    scenario["deadline_s"] = 105

    base_spec = {"case_id": "base_typical", "case_type": "typical", "rain": False}
    # Stress case: rain slows walk by 1.5x -> 90s walk + 10s service -> completions at 100, 110, 120, 130s > 105s.
    stress_spec = {
        "case_id": "rain_stress",
        "case_type": "stress",
        "rain": True,
        "rain_factor": 1.5,
    }

    res_base = resolve_case(scenario, base_spec)
    res_stress = resolve_case(scenario, stress_spec)

    comparison = compare_policies(
        policies={"plan_fixed": policy},
        cases=[res_base, res_stress],
        required_cases=["base_typical", "rain_stress"],
        hard_constraints={"max_lateness_s": 0.0},
    )

    p_summary = comparison["policies"]["plan_fixed"]
    # Passes base case with 0 lateness
    assert p_summary["base_case"]["total_lateness_s"] == 0.0
    assert p_summary["base_case"]["late_students"] == 0

    # Fails rain_stress case
    assert "rain_stress" in p_summary["failed_cases"]
    assert "rain_stress" in p_summary["required_failed_cases"]
    assert p_summary["is_feasible"] is False
    assert "plan_fixed" in comparison["disqualified_policies"]
    assert "rain_stress" in p_summary["failure_reasons"]
    assert any("lateness" in r.lower() for r in p_summary["failure_reasons"]["rain_stress"])

    # Typical and stress results are reported separately
    assert p_summary["typical_results"]["case_count"] == 1
    assert p_summary["stress_results"]["case_count"] == 1
    assert p_summary["stress_results"]["worst_wait_student_s"] > 0
    assert comparison["aggregate_rule"]["typical"] == "base_case"
    assert comparison["aggregate_rule"]["stress"] == "worst_case"
    assert comparison["coverage_note"] == RANGE_COVERAGE_NOTE
    assert comparison["sensitivity"]["preferred_by_typical"] == "plan_fixed"
    assert comparison["sensitivity"]["preferred_by_worst_stress"] is None
    assert comparison["sensitivity"]["preferred_plan_changed"] is True


def test_estimated_scenario_does_not_get_measured_accuracy_pass():
    """An estimated scenario cannot receive a measured-accuracy pass."""
    scenario, policy = build_artificial_single_server_case()
    scenario["scenario_type"] = "estimated"
    scenario["accuracy_references"] = [
        {
            "id": "synthetic_endpoint",
            "role": "predicted",
            "observed_s": 70,
            "limit_s": 600,
            "event_match": {"event_type": "service_complete"},
        }
    ]

    result = simulate(scenario, policy)
    assert result["status"] == "completed"
    checks = result["accuracy_checks"]
    assert len(checks) == 1
    check = checks[0]
    assert check["event_id"] is not None
    assert check.get("abs_error_s") == 0.0
    assert check["counted_as_predicted_success"] is False
    assert check["measured_accuracy_pass"] is False
    assert check.get("eligible_measured_accuracy") is False


def test_unmeasured_route_range_wider_than_600s_reports_not_demonstrated():
    """Unmeasured routes with uncertainty range wider than 600s report not_demonstrated."""
    scenario, policy = build_artificial_single_server_case()
    scenario["accuracy_references"] = [
        {
            "id": "unmeasured_wide",
            "role": "unverified",
            "hostel_id": "hostel_wide",
            "uncertainty_range_s": 650.0,
            "note": "Unmeasured walking route with wide uncertainty",
        },
        {
            "id": "unmeasured_narrow",
            "role": "unverified",
            "hostel_id": "hostel_narrow",
            "uncertainty_range_s": 300.0,
            "note": "Unmeasured walking route with narrow uncertainty",
        },
    ]

    result = simulate(scenario, policy)
    assert result["status"] == "completed"

    wide_check = next(c for c in result["accuracy_checks"] if c["id"] == "unmeasured_wide")
    narrow_check = next(c for c in result["accuracy_checks"] if c["id"] == "unmeasured_narrow")

    assert wide_check["range_s"] == 650.0
    assert wide_check["accuracy_status"] == "not_demonstrated"
    assert wide_check["status"] == "not_demonstrated"
    assert wide_check["demonstrated"] is False
    assert wide_check["passed"] is False

    assert narrow_check["range_s"] == 300.0
    assert narrow_check["accuracy_status"] == "unverified"
    assert narrow_check["passed"] is False


def test_development_vs_final_independent_labels_and_validation_claims():
    """Cases used for selection/development cannot also claim independent validation."""
    scenario, _ = build_artificial_single_server_case()

    # Claiming independent validation on a development case must fail
    with pytest.raises(SimulationError) as exc:
        resolve_case(
            scenario,
            {
                "case_id": "dev_case",
                "dataset_role": "development",
                "claim_independent_validation": True,
            },
        )
    assert exc.value.category == "fixed_rule_violation"

    # Final independent case can claim validation
    resolved = resolve_case(
        scenario,
        {
            "case_id": "indep_case",
            "dataset_role": "final_independent",
            "claim_independent_validation": True,
        },
    )
    assert resolved["case_metadata"]["dataset_role"] == "final_independent"


def test_related_hostel_totals_constrained_by_campus_attendance():
    """Campus attendance total constrains hostel attendance consistently."""
    scenario, _ = build_artificial_120_hostel_case()
    # Add second hostel
    scenario["hostels"].append(
        {
            "id": "hostel_2",
            "registration": 100,
            "resident_occupancy": 90,
            "expected_event_attendance": 80,
            "resolved_attendance": 80,
            "origin_place_id": "origin",
        }
    )

    resolved = resolve_case(scenario, {"campus_attendance_total": 300}, seed=10)
    sum_hostels = sum(h["resolved_attendance"] for h in resolved["hostels"])
    assert sum_hostels == 300
    spec_hostel = next(h for h in resolved["hostels"] if h["id"] == "spec_hostel")
    spec_units = [u for u in resolved["source_units"] if u.get("hostel_id") == "spec_hostel"]
    assert sum(u["resolved_attendance"] for u in spec_units) == spec_hostel["resolved_attendance"]

    tight = copy.deepcopy(scenario)
    tight["hostels"] = [
        {"id": "a", "resolved_attendance": 1, "expected_event_attendance": 1, "origin_place_id": "origin"},
        {"id": "b", "resolved_attendance": 1, "expected_event_attendance": 1, "origin_place_id": "origin"},
        {"id": "c", "resolved_attendance": 1, "expected_event_attendance": 1, "origin_place_id": "origin"},
    ]
    tight_resolved = resolve_case(tight, {"campus_attendance_total": 2}, seed=10)
    assert sum(h["resolved_attendance"] for h in tight_resolved["hostels"]) == 2


def test_uncertainty_bands_and_range_is_not_probability():
    """Bands are supported and explicit notes affirm range is not a probability distribution."""
    scenario, _ = build_artificial_single_server_case()
    resolved = resolve_case(scenario, {"band": "upper"})
    meta = resolved["case_metadata"]

    assert meta["uncertainty_band"] == "upper"
    assert meta["is_probability_distribution"] is False
    assert meta["range_interpretation"] == "coverage_band"
    assert meta["weights_describe"] == "benchmark_coverage"
    assert meta["coverage_note"] == RANGE_COVERAGE_NOTE
    assert "not a probability distribution" in RANGE_COVERAGE_NOTE
    assert UNCERTAINTY_BANDS == ("lower", "base", "upper")
    with pytest.raises(SimulationError) as exc:
        resolve_case(scenario, {"band": "not_a_band"})
    assert exc.value.category == "invalid_value_or_unit"


def test_property_classes_and_competing_policies_share_demand():
    """Unknown-fixed, between-day, during-day, and search choices stay labelled. Policies share draws."""
    scenario, policy_a = build_artificial_120_hostel_case(grouping_basis="floor")
    _, policy_b = build_artificial_120_hostel_case(grouping_basis="wing")
    classes = {
        "unknown_fixed": resolve_case(scenario, {"case_id": "cap", "property_class": "unknown_fixed", "queue_capacity_factor": 0.5}),
        "between_days": resolve_case(scenario, {"case_id": "demand", "demand": "high"}),
        "during_day": resolve_case(scenario, {"case_id": "rain_day", "rain": True}),
        "search_choice": resolve_case(scenario, {"case_id": "group", "grouping_basis": "wing"}),
    }
    assert set(classes) == set(PROPERTY_CLASSES)
    for name, resolved in classes.items():
        assert resolved["case_metadata"]["property_class"] == name

    shared = resolve_case(
        scenario,
        {"case_id": "shared_compare", "rain": True, "rain_factor": 1.4, "demand": "high"},
        seed=7,
    )
    comparison = compare_policies(policies={"floor": policy_a, "wing": policy_b}, cases=[shared])
    snap_a = comparison["policies"]["floor"]["simulation_outputs"]["shared_compare"]["input_snapshot"]["scenario"]
    snap_b = comparison["policies"]["wing"]["simulation_outputs"]["shared_compare"]["input_snapshot"]["scenario"]
    att_a = [(u["id"], u["resolved_attendance"]) for u in snap_a["source_units"]]
    att_b = [(u["id"], u["resolved_attendance"]) for u in snap_b["source_units"]]
    assert att_a == att_b
    assert [(leg["id"], leg["duration_s"]) for leg in snap_a["route_legs"]] == [
        (leg["id"], leg["duration_s"]) for leg in snap_b["route_legs"]
    ]
    assert snap_a["case_metadata"]["resolved_weather"] == snap_b["case_metadata"]["resolved_weather"]

def test_resolve_case_keeps_final_independent_and_gps_ids():
    """F06: resolve_case keeps final_independent / GPS ids from case_metadata, operating_rules, scenario_id, uncertainty_case_id."""
    scenario, _ = build_artificial_120_hostel_case("floor")

    # Case 1: GPS id in scenario_id
    sc1 = copy.deepcopy(scenario)
    sc1["scenario_id"] = "restu_17sep_replay"
    res1 = resolve_case(sc1, {"case_id": "c1"})
    assert res1["case_metadata"]["dataset_role"] == "final_independent"
    assert res1["case_metadata"]["scenario_id"] == "restu_17sep_replay"

    # Case 2: GPS id in case_metadata
    sc2 = copy.deepcopy(scenario)
    sc2["case_metadata"] = {"scenario_id": "restu_18sep_rainy_replay", "dataset_role": "final_independent"}
    res2 = resolve_case(sc2, {"case_id": "c2"})
    assert res2["case_metadata"]["dataset_role"] == "final_independent"
    assert res2["case_metadata"]["scenario_id"] == "restu_18sep_rainy_replay"

    # Case 3: GPS id in operating_rules
    sc3 = copy.deepcopy(scenario)
    sc3["operating_rules"] = {"scenario_id": "restu_17sep_replay"}
    res3 = resolve_case(sc3, {"case_id": "c3"})
    assert res3["case_metadata"]["dataset_role"] == "final_independent"
    assert res3["case_metadata"]["scenario_id"] == "restu_17sep_replay"

    # Case 4: final_independent in uncertainty_case_id / case_metadata
    sc4 = copy.deepcopy(scenario)
    sc4["case_metadata"] = {"dataset_role": "final_independent"}
    res4 = resolve_case(sc4, {"case_id": "c4"})
    assert res4["case_metadata"]["dataset_role"] == "final_independent"


def test_demand_scaling_keeps_unit_hostel_population_totals_consistent():
    """F14: 1+1 at 1.5x must not become 4 vs 3; unit, hostel, and initial_state totals match."""
    scenario, _ = build_artificial_120_hostel_case("floor")
    test_sc = copy.deepcopy(scenario)
    test_sc["hostels"] = [
        {"id": "h1", "resolved_attendance": 2, "expected_event_attendance": 2, "resident_occupancy": 2}
    ]
    test_sc["source_units"] = [
        {"id": "u1", "hostel_id": "h1", "resolved_attendance": 1, "estimated_attendance": 1, "resident_occupancy": 1},
        {"id": "u2", "hostel_id": "h1", "resolved_attendance": 1, "estimated_attendance": 1, "resident_occupancy": 1},
    ]
    test_sc["initial_state"]["students"] = [
        {
            "part_id": "p1",
            "source_unit_id": "u1",
            "hostel_id": "h1",
            "members": [{"student_key": "s1", "queue_tie_key": "00"}],
        },
        {
            "part_id": "p2",
            "source_unit_id": "u2",
            "hostel_id": "h1",
            "members": [{"student_key": "s2", "queue_tie_key": "01"}],
        },
    ]

    # Resolve at demand_factor 1.5
    resolved = resolve_case(test_sc, {"case_id": "scaled", "demand_factor": 1.5})
    h1 = next(h for h in resolved["hostels"] if h["id"] == "h1")
    units = [u for u in resolved["source_units"] if u["hostel_id"] == "h1"]
    unit_sum = sum(u["resolved_attendance"] for u in units)

    assert h1["resolved_attendance"] == 3
    assert unit_sum == 3  # Must be 3, NOT 4 vs 3!

    # Check student members in initial_state
    st_members = sum(len(p["members"]) for p in resolved["initial_state"]["students"])
    assert st_members == 3
    assert h1.get("resident_occupancy") == 2
    assert [u.get("resident_occupancy") for u in units] == [1, 1]
    assert [u.get("estimated_attendance") for u in units] == [1, 1]


def test_estimated_vs_resolved_attendance_stay_distinct():
    """F14: estimated vs resolved attendance stay distinct after demand scaling."""
    scenario, _ = build_artificial_120_hostel_case("floor")
    original_est = {
        u["id"]: u.get("estimated_attendance")
        for u in scenario["source_units"]
        if "estimated_attendance" in u
    }
    resolved = resolve_case(scenario, {"case_id": "distinct_test", "demand_factor": 1.5})
    for u in resolved["source_units"]:
        if u["id"] in original_est:
            assert u.get("estimated_attendance") == original_est[u["id"]]
            assert u.get("estimated_attendance") != u.get("resolved_attendance")


def test_bus_loading_factor_and_queue_capacity_factor():
    """F14: bus_loading_factor scales boarding; queue_capacity_factor affects admitting capacity."""
    scenario, _ = build_artificial_120_hostel_case("floor")
    test_sc = copy.deepcopy(scenario)
    test_sc["vehicle_types"] = [
        {
            "id": "bus_type",
            "capacity_students": 40,
            "usable_doors": 1,
            "boarding_setup_s": 10.0,
            "boarding_s_per_passenger_per_door": 2.0,
        }
    ]
    test_sc["places"] = [
        {
            "id": "hall",
            "capacity_students": 50,
            "physical_capacity_students": 50,
            "operating_limit_students": 40,
            "estimated_capacity_students": 60,
        }
    ]

    resolved = resolve_case(
        test_sc,
        {"case_id": "factors_test", "bus_loading_factor": 1.5, "queue_capacity_factor": 0.5},
    )
    vtype = resolved["vehicle_types"][0]
    assert vtype["boarding_setup_s"] == 15.0
    assert vtype["boarding_s_per_passenger_per_door"] == 3.0

    place = resolved["places"][0]
    assert place["capacity_students"] == 25
    assert place["physical_capacity_students"] == 25
    assert place["operating_limit_students"] == 20
    assert place["estimated_capacity_students"] == 30


def test_compare_policies_catches_simulation_error_and_duplicate_case_ids():
    """F10: catch SimulationError per candidate×case; duplicate case IDs do not overwrite."""
    scenario, policy = build_artificial_120_hostel_case("floor")
    case1 = resolve_case(scenario, {"case_id": "shared_id", "demand_factor": 1.0})
    case2 = resolve_case(scenario, {"case_id": "shared_id", "demand_factor": 1.2})

    res = compare_policies(
        policies={"pol1": policy},
        cases=[case1, case2],
        base_scenario=scenario,
    )
    # Duplicate case IDs were disambiguated and not overwritten
    p_outputs = res["policies"]["pol1"]["simulation_outputs"]
    assert len(p_outputs) == 2
    assert len(res["policies"]["pol1"]["typical_results"]["cases"]) == 2


def test_behavior_coverage_band_metadata_and_forbidden_information():
    """BV-02 extension: behavior bands resolved in resolve_case record coverage metadata and forbid hidden info."""
    scenario, policy = build_artificial_single_server_case()
    case_spec = {
        "case_id": "ticket08_behavior_case",
        "demand": "base",
        "band": "base",
        "behavior": {
            "source_unit_splits": {
                "su_origin": [
                    {
                        "cohort_id": "c_noshow",
                        "attendance_state": "no_show",
                        "count_band": {"lower": 0, "base": 1, "upper": 2},
                        "evidence": {"category": "assumed", "note": "ticket08 test no-show"},
                    },
                    {
                        "cohort_id": "c_attending",
                        "attendance_state": "attending",
                        "reporting_mode": "delay_from_required",
                        "late_assembly_s": 0,
                        "allocation_rule": "remainder",
                        "evidence": {"category": "assumed", "note": "ticket08 test remainder"},
                    },
                ]
            }
        },
    }
    resolved = resolve_case(scenario, case_spec, seed=42)
    meta = resolved["case_metadata"]
    assert meta["range_interpretation"] == "coverage_band"
    assert meta["is_probability_distribution"] is False
    assert "raw_bands" in meta["resolved_inputs"]
    assert "selected_values" in meta["resolved_inputs"]
    assert "keys" in meta["resolved_inputs"]
    assert "provenance" in meta["resolved_inputs"]

    unit = resolved["source_units"][0]
    assert unit["non_attendance"] == 1
    assert unit["attending"] == 3
    assert unit["resolved_attendance"] == 3

    # Policy cannot access forbidden hidden no-show or future arrival state
    bad_pol = copy.deepcopy(policy)
    bad_pol["hidden_no_shows"] = True
    with pytest.raises(SimulationError) as exc_ns:
        validate_policy_information(bad_pol)
    assert exc_ns.value.category == "unsupported_policy"

    bad_future = copy.deepcopy(policy)
    bad_future["future_arrivals"] = True
    with pytest.raises(SimulationError) as exc_fa:
        validate_policy_information(bad_future)
    assert exc_fa.value.category == "unsupported_policy"
