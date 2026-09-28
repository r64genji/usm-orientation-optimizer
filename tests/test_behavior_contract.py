"""Tests for behavior specification contracts, validation, member allocation, and conservation (BV-01)."""

from __future__ import annotations

import copy
import pytest
from usm_sim.grouping import materialize_groups
from usm_sim.scenarios import build_artificial_single_server_case
from usm_sim.simulate import _assert_attendance_conservation, simulate
from usm_sim.validate import validate_inputs

from usm_sim.behavior import (
    ALL_PHENOMENON_FAMILIES,
    allocate_members_for_unit,
    prepare_behavior,
    validate_behavior_spec,
    verify_behavior_conservation,
)
from usm_sim.campus import build_whole_campus_origins_case
from usm_sim.errors import SimulationError


def _valid_all_families_dict() -> dict[str, dict]:
    return {fam: {} for fam in ALL_PHENOMENON_FAMILIES}


def _minimal_valid_scenario(unit_count: int = 10, declared_pop: int = 10) -> dict:
    return {
        "format_version": "1.0",
        "source_units": [
            {
                "id": "su_1",
                "hostel_id": "h_1",
                "declared_population": declared_pop,
                "resolved_attendance": declared_pop,
                "required_reporting_s": 0,
                "actual_reporting_s": 0,
                "readiness_s": 0,
                "late_assembly_s": 0,
                "non_attendance": 0,
                "withdrawn": 0,
            }
        ],
        "behavior": {
            "version": "1.0",
            "case_id": "test_behavior_case",
            "mode": "explicit_events",
            "phenomena": _valid_all_families_dict(),
            "source_unit_splits": {},
            "events": [],
        },
    }


def test_1_no_behavior_campus_zeros_prepare_noop():
    """1. No behavior + campus zeros → prepare no-op, resolved_attendance unchanged."""
    campus, _ = build_whole_campus_origins_case()
    # Campus origins case has no scenario.behavior
    assert campus.get("behavior") is None

    # Before prepare, record original resolved_attendances
    orig_resolved = [int(u["resolved_attendance"]) for u in campus["source_units"]]

    # validate_behavior_spec passes without error
    validate_behavior_spec(campus)

    # prepare_behavior runs as no-op
    prepared = prepare_behavior(campus)
    after_resolved = [int(u["resolved_attendance"]) for u in prepared["source_units"]]

    assert after_resolved == orig_resolved
    assert prepared.get("_behavior_prepared") is True

    # Conservation holds
    cons = verify_behavior_conservation(prepared)
    assert cons["conserved"] is True


def test_2_nonzero_legacy_fields_without_behavior_case_raises_error():
    """2. Nonzero non_attendance / late_assembly_s / withdrawn without behavior case → error."""
    # Nonzero non_attendance
    sc_non_att = {
        "source_units": [
            {
                "id": "su_bad",
                "resolved_attendance": 8,
                "non_attendance": 2,
                "late_assembly_s": 0,
                "withdrawn": 0,
            }
        ]
    }
    with pytest.raises(SimulationError) as exc_info:
        validate_behavior_spec(sc_non_att)
    assert exc_info.value.field == "scenario.source_units[0].non_attendance"
    assert "non_attendance" in exc_info.value.message

    # Nonzero late_assembly_s
    sc_late = {
        "source_units": [
            {
                "id": "su_bad",
                "resolved_attendance": 8,
                "non_attendance": 0,
                "late_assembly_s": 300,
                "withdrawn": 0,
            }
        ]
    }
    with pytest.raises(SimulationError) as exc_late:
        validate_behavior_spec(sc_late)
    assert exc_late.value.field == "scenario.source_units[0].late_assembly_s"
    assert "late_assembly_s" in exc_late.value.message

    # Nonzero withdrawn
    sc_withdrawn = {
        "source_units": [
            {
                "id": "su_bad",
                "resolved_attendance": 8,
                "non_attendance": 0,
                "late_assembly_s": 0,
                "withdrawn": 1,
            }
        ]
    }
    with pytest.raises(SimulationError) as exc_withdrawn:
        validate_behavior_spec(sc_withdrawn)
    assert exc_withdrawn.value.field == "scenario.source_units[0].withdrawn"
    assert "withdrawn" in exc_withdrawn.value.message


def test_3_ten_declared_two_noshow_three_late():
    """3. 10 declared, 2 no-show, 3 late: attending=8, resolved_attendance=8, declared=10, late cohort count=3, keys stable."""
    initial_members = [
        {"student_key": f"s_{i:02d}", "queue_tie_key": f"{i:02d}", "source_unit_id": "su_1", "hostel_id": "h_1"}
        for i in range(10)
    ]
    scenario = _minimal_valid_scenario(declared_pop=10)
    scenario["initial_state"] = {
        "students": [
            {
                "part_id": "part_1",
                "group_id": "g_1",
                "source_unit_id": "su_1",
                "members": copy.deepcopy(initial_members),
                "student_count": 10,
            }
        ]
    }

    cohorts = [
        {
            "cohort_id": "c_noshow",
            "count": 2,
            "attendance_state": "no_show",
            "evidence": {"category": "assumed", "note": "test no-show cohort"},
        },
        {
            "cohort_id": "c_late",
            "count": 3,
            "attendance_state": "attending",
            "reporting_mode": "delay_from_required",
            "late_assembly_s": 300,
            "evidence": {"category": "assumed", "note": "test late cohort"},
        },
        {
            "cohort_id": "c_ontime",
            "count": 5,
            "attendance_state": "attending",
            "reporting_mode": "delay_from_required",
            "late_assembly_s": 0,
            "evidence": {"category": "assumed", "note": "test on-time cohort"},
        },
    ]
    scenario["behavior"]["source_unit_splits"] = {"su_1": cohorts}

    validate_behavior_spec(scenario)
    prepared = prepare_behavior(scenario)

    unit = prepared["source_units"][0]
    assert unit["declared_population"] == 10
    assert unit["non_attendance"] == 2
    assert unit["attending"] == 8
    assert unit["resolved_attendance"] == 8

    # Late cohort count is 3
    late_cohort = next(c for c in unit["cohorts"] if c["cohort_id"] == "c_late")
    assert late_cohort["count"] == 3

    # Member keys in initial_state.students are stable (first 2 were no-shows, remaining 8 preserved)
    kept_students = prepared["initial_state"]["students"][0]["members"]
    assert len(kept_students) == 8
    expected_kept_keys = [f"s_{i:02d}" for i in range(2, 10)]
    assert [m["student_key"] for m in kept_students] == expected_kept_keys


def test_4_withdrawal_not_subtracted_at_prepare():
    """4. Withdrawal not subtracted at prepare."""
    scenario = _minimal_valid_scenario(declared_pop=10)
    cohorts = [
        {
            "cohort_id": "c_noshow",
            "count": 2,
            "attendance_state": "no_show",
            "evidence": {"category": "assumed", "note": "test no-show cohort"},
        },
        {
            "cohort_id": "c_attending",
            "count": 8,
            "attendance_state": "attending",
            "reporting_mode": "delay_from_required",
            "late_assembly_s": 0,
            "evidence": {"category": "assumed", "note": "test attending cohort"},
        },
    ]
    scenario["behavior"]["source_unit_splits"] = {"su_1": cohorts}
    # Declare a withdrawal event targeting 1 student
    scenario["behavior"]["events"] = [
        {
            "event_id": "ev_withdraw_1",
            "phenomenon": "withdrawal",
            "target": "c_attending",
            "evidence": {"category": "assumed", "note": "test withdrawal event"},
            "trigger": {"time_s": 1200},
        }
    ]
    scenario["source_units"][0]["withdrawn"] = 1

    validate_behavior_spec(scenario)
    prepared = prepare_behavior(scenario)

    unit = prepared["source_units"][0]
    # resolved_attendance must be 10 - 2 = 8, NOT 7! Withdrawal is NOT subtracted at prepare
    assert unit["resolved_attendance"] == 8
    assert unit["attending"] == 8
    assert unit["declared_population"] == 10
    assert unit["non_attendance"] == 2


def test_5_overlapping_cohorts_bad_sums_inconsistent_delay_absolute_error():
    """5. Overlapping cohorts / bad sums / inconsistent delay+absolute → error."""
    # 5a: Duplicate cohort_id in same unit
    sc_dup_id = _minimal_valid_scenario(declared_pop=10)
    sc_dup_id["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_dup", "count": 5, "attendance_state": "attending", "evidence": {"category": "assumed", "note": "n"}},
            {"cohort_id": "c_dup", "count": 5, "attendance_state": "attending", "evidence": {"category": "assumed", "note": "n"}},
        ]
    }
    with pytest.raises(SimulationError) as exc_dup:
        validate_behavior_spec(sc_dup_id)
    assert "duplicate cohort_id" in exc_dup.value.message

    # 5b: Bad sum: cohort counts sum to 9 != declared_population 10
    sc_bad_sum = _minimal_valid_scenario(declared_pop=10)
    sc_bad_sum["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_1", "count": 5, "attendance_state": "attending", "evidence": {"category": "assumed", "note": "n"}},
            {"cohort_id": "c_2", "count": 4, "attendance_state": "attending", "evidence": {"category": "assumed", "note": "n"}},
        ]
    }
    with pytest.raises(SimulationError) as exc_sum:
        validate_behavior_spec(sc_bad_sum)
    assert "does not equal declared_population" in exc_sum.value.message

    # 5c: Negative count in cohort
    sc_neg_count = _minimal_valid_scenario(declared_pop=10)
    sc_neg_count["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_1", "count": -1, "attendance_state": "attending", "evidence": {"category": "assumed", "note": "n"}},
        ]
    }
    with pytest.raises(SimulationError) as exc_neg:
        validate_behavior_spec(sc_neg_count)
    assert "invalid count" in exc_neg.value.message

    # 5d: Inconsistent delay and absolute in reporting fields
    sc_inconsistent = _minimal_valid_scenario(declared_pop=10)
    sc_inconsistent["source_units"][0]["required_reporting_s"] = 100
    sc_inconsistent["behavior"]["source_unit_splits"] = {
        "su_1": [
            {
                "cohort_id": "c_1",
                "count": 10,
                "attendance_state": "attending",
                "reporting_mode": "absolute",
                "actual_reporting_s": 300,
                "late_assembly_s": 500,  # required=100, actual=300 -> late delay should be 200, not 500!
                "evidence": {"category": "assumed", "note": "n"},
            }
        ]
    }
    with pytest.raises(SimulationError) as exc_incon:
        validate_behavior_spec(sc_inconsistent)
    assert "inconsistent delay and absolute" in exc_incon.value.message

    # 5e: Overlapping explicit member keys across cohorts
    unit = {"id": "su_1", "declared_population": 4}
    cohorts_overlap = [
        {"cohort_id": "c1", "count": 2, "member_keys": ["m1", "m2"], "evidence": {"category": "assumed", "note": "n"}},
        {"cohort_id": "c2", "count": 2, "member_keys": ["m2", "m3"], "evidence": {"category": "assumed", "note": "n"}},
    ]
    existing = [
        {"student_key": "m1"},
        {"student_key": "m2"},
        {"student_key": "m3"},
        {"student_key": "m4"},
    ]
    with pytest.raises(SimulationError) as exc_overlap_m:
        allocate_members_for_unit(unit, cohorts_overlap, existing_members=existing)
    assert "assigned to multiple cohorts" in exc_overlap_m.value.message


def test_6_missing_phenomenon_family_on_named_case_error():
    """6. Missing phenomenon family on a named case → error."""
    scenario = _minimal_valid_scenario(declared_pop=10)
    # Remove one family: queue_jump
    phenomena = _valid_all_families_dict()
    del phenomena["queue_jump"]
    scenario["behavior"]["phenomena"] = phenomena

    with pytest.raises(SimulationError) as exc_info:
        validate_behavior_spec(scenario)
    assert "missing declaration for phenomenon families" in exc_info.value.message
    assert "queue_jump" in exc_info.value.message
    assert exc_info.value.field == "scenario.behavior.queue_jump"


def test_7_queue_jump_event_without_place_id_error():
    """7. queue_jump event without place_id → error."""
    scenario = _minimal_valid_scenario(declared_pop=10)
    scenario["behavior"]["events"] = [
        {
            "event_id": "qj_event_1",
            "phenomenon": "queue_jump",
            "target": "c_1",
            "evidence": {"category": "assumed", "note": "test"},
            "trigger": {"time_s": 500},
            # Missing place_id!
        }
    ]

    with pytest.raises(SimulationError) as exc_info:
        validate_behavior_spec(scenario)
    assert "missing required place_id" in exc_info.value.message
    assert exc_info.value.field == "scenario.behavior.events[0].place_id"


def test_8_idempotent_prepare():
    """8. Idempotent prepare: second prepare does not subtract no-shows twice."""
    scenario = _minimal_valid_scenario(declared_pop=10)
    initial_members = [
        {"student_key": f"s_{i:02d}", "queue_tie_key": f"{i:02d}", "source_unit_id": "su_1", "hostel_id": "h_1"}
        for i in range(10)
    ]
    scenario["initial_state"] = {
        "students": [
            {
                "part_id": "part_1",
                "group_id": "g_1",
                "source_unit_id": "su_1",
                "members": copy.deepcopy(initial_members),
                "student_count": 10,
            }
        ]
    }
    cohorts = [
        {
            "cohort_id": "c_noshow",
            "count": 2,
            "attendance_state": "no_show",
            "evidence": {"category": "assumed", "note": "test"},
        },
        {
            "cohort_id": "c_attending",
            "count": 8,
            "attendance_state": "attending",
            "reporting_mode": "delay_from_required",
            "late_assembly_s": 0,
            "evidence": {"category": "assumed", "note": "test"},
        },
    ]
    scenario["behavior"]["source_unit_splits"] = {"su_1": cohorts}

    # First prepare
    first_run = prepare_behavior(scenario)
    unit = first_run["source_units"][0]
    assert unit["attending"] == 8
    assert unit["resolved_attendance"] == 8
    assert unit["declared_population"] == 10
    assert unit["non_attendance"] == 2
    assert len(first_run["initial_state"]["students"][0]["members"]) == 8

    # Second prepare on the same dict
    second_run = prepare_behavior(first_run)
    unit2 = second_run["source_units"][0]
    assert unit2["attending"] == 8
    assert unit2["resolved_attendance"] == 8
    assert unit2["declared_population"] == 10
    assert unit2["non_attendance"] == 2
    assert len(second_run["initial_state"]["students"][0]["members"]) == 8


def test_9_evidence_missing_or_invalid_error():
    """9. Evidence missing or invalid → error."""
    # Cohort with missing evidence
    sc_missing = _minimal_valid_scenario(declared_pop=10)
    sc_missing["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_1", "count": 10, "attendance_state": "attending"}
        ]
    }
    with pytest.raises(SimulationError) as exc_missing:
        validate_behavior_spec(sc_missing)
    assert "evidence" in exc_missing.value.field

    # Cohort with invalid evidence category
    sc_cat = _minimal_valid_scenario(declared_pop=10)
    sc_cat["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_1", "count": 10, "attendance_state": "attending", "evidence": {"category": "unverified", "note": "test"}}
        ]
    }
    with pytest.raises(SimulationError) as exc_cat:
        validate_behavior_spec(sc_cat)
    assert exc_cat.value.category == "unresolved_assumption"
    assert "category" in exc_cat.value.field

    # Cohort with evidence missing note and ref
    sc_no_note = _minimal_valid_scenario(declared_pop=10)
    sc_no_note["behavior"]["source_unit_splits"] = {
        "su_1": [
            {"cohort_id": "c_1", "count": 10, "attendance_state": "attending", "evidence": {"category": "assumed"}}
        ]
    }
    with pytest.raises(SimulationError) as exc_no_note:
        validate_behavior_spec(sc_no_note)
    assert "note or ref" in exc_no_note.value.message


def test_10_conservation_identities_on_prepared_records():
    """10. Conservation identities on the prepared records (not engine run)."""
    scenario = {
        "format_version": "1.0",
        "source_units": [
            {
                "id": "su_a",
                "hostel_id": "h_a",
                "declared_population": 12,
                "resolved_attendance": 12,
                "required_reporting_s": 0,
            },
            {
                "id": "su_b",
                "hostel_id": "h_b",
                "declared_population": 8,
                "resolved_attendance": 8,
                "required_reporting_s": 0,
            },
        ],
        "behavior": {
            "version": "1.0",
            "case_id": "case_conservation",
            "mode": "explicit_events",
            "phenomena": _valid_all_families_dict(),
            "source_unit_splits": {
                "su_a": [
                    {"cohort_id": "a_noshow", "count": 3, "attendance_state": "no_show", "evidence": {"category": "assumed", "note": "n"}},
                    {"cohort_id": "a_late", "count": 4, "attendance_state": "attending", "reporting_mode": "delay_from_required", "late_assembly_s": 120, "evidence": {"category": "assumed", "note": "n"}},
                    {"cohort_id": "a_ontime", "count": 5, "attendance_state": "attending", "reporting_mode": "delay_from_required", "late_assembly_s": 0, "evidence": {"category": "assumed", "note": "n"}},
                ],
                "su_b": [
                    {"cohort_id": "b_noshow", "count": 1, "attendance_state": "no_show", "evidence": {"category": "assumed", "note": "n"}},
                    {"cohort_id": "b_ontime", "count": 7, "attendance_state": "attending", "reporting_mode": "delay_from_required", "late_assembly_s": 0, "evidence": {"category": "assumed", "note": "n"}},
                ],
            },
            "events": [],
        },
    }

    validate_behavior_spec(scenario)
    prepared = prepare_behavior(scenario)

    # Unit A: declared=12, non_attendance=3, attending=9, resolved_attendance=9
    # Unit B: declared=8, non_attendance=1, attending=7, resolved_attendance=7
    # Totals: declared=20, non_attendance=4, attending=16, resolved_attendance=16
    cons = verify_behavior_conservation(prepared)
    assert cons["conserved"] is True
    assert cons["declared_population"] == 20
    assert cons["non_attendance"] == 4
    assert cons["attending"] == 16
    assert cons["resolved_attendance"] == 16


def test_bv03_campus_no_behavior_simulate_accounted_64():
    """Campus simulate without behavior completes with exactly 64 accounted students."""
    scenario, policy = build_whole_campus_origins_case()
    assert scenario.get("behavior") is None
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["completed_students"] == 64
    assert res["measures"]["accounted_students"] == 64
    assert res["measures"]["attending_students"] == 64


def test_bv03_prepared_mixed_unit_late_members_keep_later_actual_reporting_s():
    """Prepared mixed unit: late members keep later actual_reporting_s into grouping output."""
    scenario, policy = build_whole_campus_origins_case()
    first_unit = scenario["source_units"][0]
    uid = first_unit["id"]
    total_count = int(first_unit["resolved_attendance"])
    late_count = 2
    ontime_count = total_count - late_count

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_mixed_unit",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            uid: [
                {
                    "cohort_id": "c_late",
                    "count": late_count,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 150,
                    "readiness_s": 180,
                    "evidence": {"category": "assumed", "note": "late cohort"},
                },
                {
                    "cohort_id": "c_ontime",
                    "count": ontime_count,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "readiness_s": 0,
                    "evidence": {"category": "assumed", "note": "on-time cohort"},
                },
            ]
        },
        "events": [],
    }
    prepared = prepare_behavior(scenario)
    summary = materialize_groups(prepared["source_units"], policy["grouping"], hostels=scenario.get("hostels"))
    su = next(u for u in summary["source_units"] if u["id"] == uid)
    assert su["cohort_readiness_s"] == {"c_late": 180, "c_ontime": 0}

    all_grouped_members = [m for g in summary["groups"] for m in g["members"]]
    late_members = [m for m in all_grouped_members if m.get("cohort_id") == "c_late"]
    ontime_members = [m for m in all_grouped_members if m.get("cohort_id") == "c_ontime"]
    assert len(late_members) == late_count
    assert len(ontime_members) == ontime_count
    for lm in late_members:
        assert lm["actual_reporting_s"] == 150
        assert lm["readiness_s"] == 180
    for om in ontime_members:
        assert om["actual_reporting_s"] == 0
        assert om["readiness_s"] == 0

    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["accounted_students"] == 64


def test_bv03_no_shows_not_in_initial_moving_parts():
    """No-shows must not appear in initial moving parts."""
    scenario, policy = build_artificial_single_server_case()
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_noshow",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            "su_origin": [
                {
                    "cohort_id": "c_noshow",
                    "count": 1,
                    "attendance_state": "no_show",
                    "evidence": {"category": "assumed", "note": "no-show cohort"},
                },
                {
                    "cohort_id": "c_attend",
                    "count": 3,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "evidence": {"category": "assumed", "note": "attend cohort"},
                },
            ]
        },
        "events": [],
    }
    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    assert res["measures"]["attending_students"] == 3
    assert res["measures"]["accounted_students"] == 3
    assert res["measures"]["completed_students"] == 3


    completed_keys = {
        c["student_key"]
        for c in res["outcomes"]["student_completions"]
    }
    assert completed_keys == {"s2", "s3", "s4"}
    assert "s1" not in completed_keys

def test_bv03_double_prepare_in_simulate_does_not_double_subtract():
    """Double prepare in simulate does not double-subtract no-shows."""
    scenario, policy = build_artificial_single_server_case()
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_double_prep",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            "su_origin": [
                {
                    "cohort_id": "c_noshow",
                    "count": 1,
                    "attendance_state": "no_show",
                    "evidence": {"category": "assumed", "note": "no-show"},
                },
                {
                    "cohort_id": "c_attend",
                    "count": 3,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0,
                    "evidence": {"category": "assumed", "note": "attend"},
                },
            ]
        },
        "events": [],
    }
    prepared = prepare_behavior(scenario)
    assert prepared["source_units"][0]["declared_population"] == 4
    assert prepared["source_units"][0]["non_attendance"] == 1
    assert prepared["source_units"][0]["attending"] == 3
    assert prepared["source_units"][0]["resolved_attendance"] == 3

    res = simulate(prepared, policy)
    assert res["status"] == "completed"
    assert res["measures"]["attending_students"] == 3
    assert res["measures"]["accounted_students"] == 3

    snap_unit = res["input_snapshot"]["scenario"]["source_units"][0]
    assert snap_unit["declared_population"] == 4
    assert snap_unit["non_attendance"] == 1
    assert snap_unit["attending"] == 3
    assert snap_unit["resolved_attendance"] == 3


def test_bv03_attending_0_conservation_does_not_skip_assert():
    """Attending 0 conservation does not skip the assert."""
    scenario = {
        "source_units": [
            {
                "id": "su_zero",
                "resolved_attendance": 0,
            }
        ],
        "initial_state": {"students": []},
    }
    bad_result = {
        "status": "completed",
        "measures": {
            "completed_students": 1,
            "withdrawn_students": 0,
            "unfinished_students": 0,
        },
        "violations": [],
    }
    _assert_attendance_conservation(scenario, bad_result)
    assert bad_result["status"] == "infeasible"
    assert bad_result["termination_cause"] == "attendance_conservation"
    assert any(v["type"] == "attendance_conservation" for v in bad_result["violations"])

    good_result = {
        "status": "completed",
        "measures": {
            "completed_students": 0,
            "withdrawn_students": 0,
            "unfinished_students": 0,
        },
        "violations": [],
    }
    _assert_attendance_conservation(scenario, good_result)
    assert good_result["status"] == "completed"
    assert len(good_result["violations"]) == 0


def test_bv03_validate_inputs_rejects_nonzero_legacy_without_behavior():
    """validate_inputs rejects nonzero legacy behavior fields without named case."""
    scenario, policy = build_artificial_single_server_case()
    scenario["source_units"][0]["non_attendance"] = 2
    with pytest.raises(SimulationError) as exc_info:
        validate_inputs(scenario, policy)
    assert exc_info.value.field == "scenario.source_units[0].non_attendance"


def test_bv03_engine_apply_reporting_choice_does_not_clobber_prepared_arrivals():
    """Engine._apply_reporting_choice must not overwrite prepared arrivals."""
    scenario, policy = build_artificial_single_server_case()
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "case_preserve_arr",
        "mode": "explicit_events",
        "phenomena": _valid_all_families_dict(),
        "source_unit_splits": {
            "su_origin": [
                {
                    "cohort_id": "c_all",
                    "count": 4,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 120,
                    "evidence": {"category": "assumed", "note": "prep"},
                }
            ]
        },
        "events": [],
    }
    policy["reporting_time_s"] = 50
    policy["attendance_response_rule"] = {"type": "report_at_instruction"}

    res = simulate(scenario, policy)
    assert res["status"] == "completed"
    completions = res["outcomes"]["student_completions"]
    first_completion_s = min(c["completion_time_s"] for c in completions)
    assert first_completion_s == 190.0
