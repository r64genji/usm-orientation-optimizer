from __future__ import annotations

import copy
import pytest

from operator_dashboard.contracts import DashboardError, DEFAULT_GROUP_TARGET
from operator_dashboard.inputs import (
    apply_allowed_overrides,
    apply_hall_seats,
    canonical_case_id,
    is_holdout_case,
    list_cases,
    validate_run_request,
)


def test_default_group_target_is_25():
    assert DEFAULT_GROUP_TARGET == 25


def test_unknown_fields_rejected():
    with pytest.raises(DashboardError) as err:
        validate_run_request({"case": "artificial", "seed": 42, "fleet_size": 12})
    assert err.value.field == "fleet_size"


def test_search_loop_rejected():
    with pytest.raises(DashboardError) as err:
        validate_run_request({"case": "artificial", "seed": 42, "command": "search"})
    assert "search or loop" in err.value.message


def test_holdout_search_rejected():
    with pytest.raises(DashboardError) as err:
        validate_run_request({"case": "restu-17sep", "seed": 42, "command": "loop"})
    assert "holdout" in err.value.message.lower()
    with pytest.raises(DashboardError):
        validate_run_request({"case": "restu-18sep-rainy", "seed": 1, "command": "search"})
    with pytest.raises(DashboardError):
        validate_run_request(
            {"case": "restu_18sep_rainy_replay", "seed": 1, "command": "search"}
        )


def test_holdout_can_be_simulated():
    req = validate_run_request({"case": "restu-17sep", "seed": 7, "output_mode": "full"})
    assert req["command"] == "simulate"
    assert req["holdout"] is True
    assert is_holdout_case("restu_18sep_rainy_replay")
    assert canonical_case_id("restu_18sep_rainy_replay") == "restu-18sep-rainy"


def test_summary_alias_is_compact():
    req = validate_run_request({"case": "artificial", "seed": 42, "output_mode": "summary"})
    assert req["output_mode"] == "compact"


def test_default_output_mode_is_full():
    req = validate_run_request({"case": "artificial", "seed": 42})
    assert req["output_mode"] == "full"


def test_group_target_must_be_positive():
    with pytest.raises(DashboardError):
        validate_run_request({"case": "artificial", "seed": 42, "group_target_students": 0})
    with pytest.raises(DashboardError):
        validate_run_request({"case": "artificial", "seed": 42, "group_target_students": -3})


def test_hall_seats_labels_and_storage_unchanged():
    scenario = {
        "destination": {
            "available_seats": 1500,
            "initial_occupants": 20,
            "reserved_seating": 30,
            "seating_place_id": "dtsp_seating",
            "foyer_storage_students": 200,
            "exterior_storage_students": 300,
        },
        "places": [
            {"id": "dtsp_seating", "capacity_students": 1450, "operating_limit_students": 1450},
            {"id": "dtsp_foyer", "capacity_students": 200},
            {"id": "dtsp_exterior_gathering", "capacity_students": 300},
        ],
        "uncertain_assumptions": [],
    }
    policy = {"grouping": {"mode": "from_source_units"}}
    updated_sc, _updated_pol = apply_allowed_overrides(
        scenario,
        policy,
        {"apply_parameters": True, "hall_seats": 1338},
    )
    dest = updated_sc["destination"]
    assert dest["available_seats"] == 1338
    assert dest["available_seats_status"] == "paper_main_floor"
    assert dest["foyer_storage_students"] == 200
    assert dest["exterior_storage_students"] == 300
    seating = next(p for p in updated_sc["places"] if p["id"] == "dtsp_seating")
    assert seating["capacity_students"] == 1338 - 20 - 30
    foyer = next(p for p in updated_sc["places"] if p["id"] == "dtsp_foyer")
    assert foyer["capacity_students"] == 200

    updated_sc, _ = apply_allowed_overrides(
        scenario, policy, {"apply_parameters": True, "hall_seats": 3500}
    )
    assert updated_sc["destination"]["available_seats_status"] == "cited_full_hall"
    assert updated_sc["destination"]["foyer_storage_students"] == 200
    updated_sc, _ = apply_allowed_overrides(
        scenario, policy, {"apply_parameters": True, "hall_seats": 2500}
    )
    assert updated_sc["destination"]["available_seats_status"] == "cited_full_hall"


def test_hall_seats_without_destination_rejected():
    with pytest.raises(DashboardError):
        apply_hall_seats({"places": []}, 1338)


def test_preserve_case_without_apply():
    scenario = {"destination": {"available_seats": 1500, "foyer_storage_students": 200}}
    policy = {"grouping": {"mode": "explicit_parts"}}
    sc, pol = apply_allowed_overrides(scenario, policy, {"apply_parameters": False})
    assert sc["destination"]["available_seats"] == 1500
    assert pol["grouping"]["mode"] == "explicit_parts"


def test_cases_list_marks_holdouts():
    ids = {row["id"]: row for row in list_cases()}
    assert "artificial" in ids
    assert ids["restu-17sep"]["holdout"] is True
    assert ids["restu-18sep-rainy"]["holdout"] is True
    assert ids["artificial"]["holdout"] is False

def test_whole_campus_full_cohort_in_cases_and_validation():
    from operator_dashboard.inputs import known_case_ids, resolve_case_inputs
    known = known_case_ids()
    assert "whole-campus-full-cohort" in known

    cases = {c["id"]: c for c in list_cases()}
    assert "whole-campus-full-cohort" in cases
    assert cases["whole-campus-full-cohort"]["is_realistic"] is True
    assert "3,543" in cases["whole-campus-full-cohort"]["label"]

    req = validate_run_request({"case": "whole-campus-full-cohort", "seed": 42})
    assert req["case"] == "whole-campus-full-cohort"
    assert req["seed"] == 42

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")
    # DTSP gross seats is 3050 (effective seats is 3000), NOT monkey-patched 3543!
    assert sc["destination"]["available_seats"] == 3050
    assert "overflow_destination" in sc["destination"]
    assert sc["destination"]["overflow_destination"]["id"] == "g03"
    places = {p["id"] for p in sc["places"]}
    assert "g03_foyer_entrance" in places
    assert "g03_seating" in places
    assert sum(h["expected_event_attendance"] for h in sc["hostels"]) == 3543

def test_dashboard_operational_case_enforces_locked_fleet():
    from operator_dashboard.inputs import apply_allowed_overrides, build_input_payload, resolve_case_inputs

    # Default operational request succeeds
    payload = build_input_payload({"case": "whole-campus-full-cohort", "seed": 42})
    assert len(payload["scenario"]["initial_state"]["vehicles"]) == 8

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")

    # 7 buses rejected
    sc_7 = copy.deepcopy(sc)
    sc_7["initial_state"]["vehicles"].pop()
    with pytest.raises(DashboardError) as err_7:
        apply_allowed_overrides(sc_7, pol, {"case": "whole-campus-full-cohort", "apply_parameters": True})
    assert err_7.value.field == "fleet"
    assert "locked at 8 buses" in err_7.value.message

    # 9 buses rejected
    sc_9 = copy.deepcopy(sc)
    sc_9["initial_state"]["vehicles"].append(copy.deepcopy(sc_9["initial_state"]["vehicles"][0]))
    with pytest.raises(DashboardError) as err_9:
        apply_allowed_overrides(sc_9, pol, {"case": "whole-campus-full-cohort", "apply_parameters": True})
    assert err_9.value.field == "fleet"


def test_dashboard_no_override_cannot_bypass_validation():
    from operator_dashboard.inputs import apply_allowed_overrides, resolve_case_inputs

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")
    sc["initial_state"]["vehicles"].pop()
    # No overrides (apply_parameters=False) cannot bypass fleet validation
    with pytest.raises(DashboardError) as err:
        apply_allowed_overrides(sc, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err.value.field == "fleet"
    assert "locked at 8 buses" in err.value.message


def test_dashboard_operational_case_enforces_locked_fleet_mix():
    from operator_dashboard.inputs import apply_allowed_overrides, resolve_case_inputs

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")
    for v in sc["initial_state"]["vehicles"]:
        if v["id"] == "electric_1":
            v["type"] = "coach"
            break
    with pytest.raises(DashboardError) as err_mix:
        apply_allowed_overrides(sc, pol, {"case": "whole-campus-full-cohort", "apply_parameters": True})
    assert err_mix.value.field == "fleet"
    assert "5 coaches and 3 electric buses" in err_mix.value.message


def test_dashboard_operational_case_enforces_single_door_per_bus():
    from operator_dashboard.inputs import apply_allowed_overrides, resolve_case_inputs

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")
    # 2 doors on vehicle instance
    sc_v = copy.deepcopy(sc)
    sc_v["initial_state"]["vehicles"][0]["usable_doors"] = 2
    with pytest.raises(DashboardError) as err_v:
        apply_allowed_overrides(sc_v, pol, {"case": "whole-campus-full-cohort", "apply_parameters": True})
    assert err_v.value.field == "doors"

    # 2 doors on vehicle type
    sc_vt = copy.deepcopy(sc)
    for vt in sc_vt["vehicle_types"]:
        if vt["id"] == "coach":
            vt["usable_doors"] = 2
    with pytest.raises(DashboardError) as err_vt:
        apply_allowed_overrides(sc_vt, pol, {"case": "whole-campus-full-cohort", "apply_parameters": True})
    assert err_vt.value.field == "doors"


def test_dashboard_operational_case_rejects_dtsp_door_checks_and_screening():
    from operator_dashboard.inputs import apply_allowed_overrides, resolve_case_inputs

    sc, pol = resolve_case_inputs("whole-campus-full-cohort")

    # bag_check on destination
    sc_bag = copy.deepcopy(sc)
    sc_bag["destination"]["bag_check"] = True
    with pytest.raises(DashboardError) as err_bag:
        apply_allowed_overrides(sc_bag, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err_bag.value.field == "destination"

    # security_service on destination
    sc_sec = copy.deepcopy(sc)
    sc_sec["destination"]["security_service"] = True
    with pytest.raises(DashboardError) as err_sec:
        apply_allowed_overrides(sc_sec, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err_sec.value.field == "destination"

    # screening dwell on destination
    sc_dwell = copy.deepcopy(sc)
    sc_dwell["destination"]["screening_dwell_s"] = 12.0
    with pytest.raises(DashboardError) as err_dwell:
        apply_allowed_overrides(sc_dwell, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err_dwell.value.field == "destination"

    # door bag check
    sc_dbag = copy.deepcopy(sc)
    sc_dbag["destination"]["doors"][0]["bag_check"] = True
    with pytest.raises(DashboardError) as err_dbag:
        apply_allowed_overrides(sc_dbag, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err_dbag.value.field == "destination"

    # door screening dwell
    sc_ddwell = copy.deepcopy(sc)
    sc_ddwell["destination"]["doors"][0]["screening_dwell_s"] = 6.0
    with pytest.raises(DashboardError) as err_ddwell:
        apply_allowed_overrides(sc_ddwell, pol, {"case": "whole-campus-full-cohort", "apply_parameters": False})
    assert err_ddwell.value.field == "destination"
