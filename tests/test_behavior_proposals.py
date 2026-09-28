"""Tests for BV-04: proposal checker behavior response handling and future information rejection."""

from __future__ import annotations

import copy
import pytest

from usm_sim import build_artificial_120_hostel_case, build_loop_proposal
from usm_sim.proposals import check_proposal


def _make_base_scenario_and_proposal():
    scenario, policy = build_artificial_120_hostel_case("floor")
    proposal = build_loop_proposal(policy)
    return scenario, proposal


def test_1_valid_intercept_and_refuse_queue_jump_compiles_to_policy():
    """1. Valid intercept-at-station + refuse-queue-jump proposal compiles to policy.behavior_response."""
    scenario, proposal = _make_base_scenario_and_proposal()

    # Get valid place IDs from scenario
    place_ids = [p["id"] for p in scenario["places"]]
    station_place = place_ids[0]
    door_place = place_ids[1]

    proposal["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "intercept-at-station",
                "place_id": station_place,
                "min_station_staff": 2,
                "fallback": "wait",
            },
            {
                "trigger": "queue_jump",
                "action": "refuse-queue-jump",
                "place_id": door_place,
            },
        ]
    }

    result = check_proposal(proposal, scenario)
    assert result["accepted"] is True, f"Proposal should be accepted: {result.get('message')}"

    policy = result["policy"]
    assert "behavior_response" in policy, "Compiled policy must include behavior_response"
    b_resp = policy["behavior_response"]

    # Verify rules copy by trigger and location
    assert "by_trigger" in b_resp
    assert "by_location" in b_resp
    assert "rules" in b_resp

    assert "late_reporting" in b_resp["by_trigger"]
    assert b_resp["by_trigger"]["late_reporting"]["action"] == "intercept-at-station"
    assert b_resp["by_trigger"]["late_reporting"]["place_id"] == station_place

    assert "queue_jump" in b_resp["by_trigger"]
    assert b_resp["by_trigger"]["queue_jump"]["action"] == "refuse-queue-jump"
    assert b_resp["by_trigger"]["queue_jump"]["place_id"] == door_place

    assert station_place in b_resp["by_location"]
    assert b_resp["by_location"][station_place]["action"] == "intercept-at-station"
    assert door_place in b_resp["by_location"]
    assert b_resp["by_location"][door_place]["action"] == "refuse-queue-jump"


def test_2_declared_handling_actions_accepted():
    """All candidate actions (wait, split-and-go, bump-next-vehicle, hold-bus, refuse-unescorted-walk,
    deny, intercept-at-station, refuse-queue-jump, allow-queue-jump) are accepted."""
    scenario, proposal = _make_base_scenario_and_proposal()
    place_ids = [p["id"] for p in scenario["places"]]

    actions = [
        ("wait", {"wait_limit_s": 300}),
        ("split-and-go", {"min_departure_count": 10}),
        ("bump-next-vehicle", {}),
        ("hold-bus", {"hold_limit_s": 120}),
        ("refuse-unescorted-walk", {}),
        ("deny", {}),
        ("intercept-at-station", {"place_id": place_ids[0]}),
        ("refuse-queue-jump", {"place_id": place_ids[1]}),
        ("allow-queue-jump", {"place_id": place_ids[1]}),
    ]
    rules = []
    for idx, (action, extra) in enumerate(actions):
        rule = {"trigger": f"trigger_{idx}", "action": action}
        rule.update(extra)
        rules.append(rule)

    proposal["behavior_response"] = {"rules": rules}
    result = check_proposal(proposal, scenario)
    assert result["accepted"] is True, f"All valid actions should be accepted: {result.get('message')}"

    policy_rules = result["policy"]["behavior_response"]["rules"]
    assert len(policy_rules) == len(actions)


def test_3_proposal_reading_future_arrivals_or_hidden_no_shows_rejected():
    """2. Proposal that reads future arrivals / hidden no-shows is rejected."""
    scenario, proposal = _make_base_scenario_and_proposal()

    # Case A: reading future_arrivals in behavior rule information source
    bad_prop_a = copy.deepcopy(proposal)
    bad_prop_a["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "wait",
                "information": "future_arrivals",
            }
        ]
    }
    res_a = check_proposal(bad_prop_a, scenario)
    assert res_a["accepted"] is False
    assert res_a["category"] == "unsupported_policy"

    # Case B: reading hidden_no_shows in behavior rule condition
    bad_prop_b = copy.deepcopy(proposal)
    bad_prop_b["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "wait",
                "condition": "hidden_no_shows",
            }
        ]
    }
    res_b = check_proposal(bad_prop_b, scenario)
    assert res_b["accepted"] is False
    assert res_b["category"] == "unsupported_policy"

    # Case C: keying off oracle_schedule
    bad_prop_c = copy.deepcopy(proposal)
    bad_prop_c["behavior_response"] = {
        "rules": [
            {
                "trigger": "queue_jump",
                "action": "refuse-queue-jump",
                "based_on": "oracle_schedule",
            }
        ]
    }
    res_c = check_proposal(bad_prop_c, scenario)
    assert res_c["accepted"] is False
    assert res_c["category"] == "unsupported_policy"

    # Case D: future flag in proposal
    bad_prop_d = copy.deepcopy(proposal)
    bad_prop_d["uses_future_arrivals"] = True
    res_d = check_proposal(bad_prop_d, scenario)
    assert res_d["accepted"] is False
    assert res_d["category"] == "unsupported_policy"

    # Case E: hidden no-show truth flag
    bad_prop_e = copy.deepcopy(proposal)
    bad_prop_e["hidden_no_show_truth"] = True
    res_e = check_proposal(bad_prop_e, scenario)
    assert res_e["accepted"] is False
    assert res_e["category"] == "unsupported_policy"


def test_4_unknown_action_rejected_with_field_path():
    """3. Unknown action rejected."""
    scenario, proposal = _make_base_scenario_and_proposal()

    proposal["behavior_response"] = {
        "rules": [
            {
                "trigger": "queue_jump",
                "action": "teleport-away",
            }
        ]
    }
    res = check_proposal(proposal, scenario)
    assert res["accepted"] is False
    assert res["category"] == "unsupported_policy"
    assert "teleport-away" in res["message"]
    assert res["field"] == "proposal.behavior_response.rules[0].action"


def test_5_unknown_place_id_in_behavior_response_rejected():
    """Behavior response referencing unknown place_id is rejected with unknown_reference."""
    scenario, proposal = _make_base_scenario_and_proposal()

    proposal["behavior_response"] = {
        "rules": [
            {
                "trigger": "queue_jump",
                "action": "refuse-queue-jump",
                "place_id": "nonexistent_portal_42",
            }
        ]
    }
    res = check_proposal(proposal, scenario)
    assert res["accepted"] is False
    assert res["category"] == "unknown_reference"
    assert "nonexistent_portal_42" in res["message"]
    assert "place_id" in res["field"]


def test_6_negative_wait_or_hold_limits_rejected():
    """Negative wait/hold limits in behavior response are rejected with invalid_value_or_unit."""
    scenario, proposal = _make_base_scenario_and_proposal()

    proposal_neg_wait = copy.deepcopy(proposal)
    proposal_neg_wait["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "wait",
                "wait_limit_s": -60,
            }
        ]
    }
    res_w = check_proposal(proposal_neg_wait, scenario)
    assert res_w["accepted"] is False
    assert res_w["category"] == "invalid_value_or_unit"

    proposal_neg_hold = copy.deepcopy(proposal)
    proposal_neg_hold["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "hold-bus",
                "hold_limit_s": -15,
            }
        ]
    }
    res_h = check_proposal(proposal_neg_hold, scenario)
    assert res_h["accepted"] is False
    assert res_h["category"] == "invalid_value_or_unit"


def test_7_missing_response_for_active_trigger_when_claiming_to_handle_case():
    """Missing response for an active named-case trigger is an input error."""
    scenario, proposal = _make_base_scenario_and_proposal()

    # Scenario has active queue_jump event
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "behavior-queue-jump",
        "mode": "explicit_events",
        "events": [
            {
                "event_id": "qj_1",
                "phenomenon": "queue_jump",
                "target": "su_1",
                "trigger": {"time_s": 600},
                "place_id": scenario["places"][0]["id"],
            }
        ],
    }

    # Proposal claims to handle behavior case but only provides response for late_reporting
    proposal["behavior_response"] = {
        "rules": [
            {
                "trigger": "late_reporting",
                "action": "wait",
                "wait_limit_s": 300,
            }
        ]
    }
    res = check_proposal(proposal, scenario)
    assert res["accepted"] is False
    assert res["category"] == "missing_input"
    assert "queue_jump" in res["message"]


def test_8_no_behavior_in_case_and_proposal_is_ok():
    """If the proposal has no behavior and case has no behavior, OK."""
    scenario, proposal = _make_base_scenario_and_proposal()
    assert scenario.get("behavior") is None
    assert proposal.get("behavior_response") is None

    res = check_proposal(proposal, scenario)
    assert res["accepted"] is True
    assert "behavior_response" not in res["policy"]


def test_9_fixed_adaptation_does_not_silently_become_bump_next_bus():
    """'fixed' adaptation must not silently become bump-to-next-bus when behavior occurs."""
    scenario, proposal = _make_base_scenario_and_proposal()
    proposal["adaptation_rule"] = {"type": "fixed"}

    # Attach an active behavior case to scenario
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "behavior-late-stragglers",
        "mode": "explicit_events",
        "events": [
            {
                "event_id": "ev_late_1",
                "phenomenon": "late_reporting",
                "target": "su_1",
                "trigger": {"time_s": 900},
            }
        ],
    }

    # Proposal has no behavior_response and relies on fixed adaptation
    proposal["behavior_case_id"] = "behavior-late-stragglers"
    res = check_proposal(proposal, scenario)
    assert res["accepted"] is False
    assert res["category"] == "missing_input"

    # Verify on standard case that fixed adaptation never sets behavior_response
    scenario_standard, proposal_standard = _make_base_scenario_and_proposal()
    proposal_standard["adaptation_rule"] = {"type": "fixed"}
    res_std = check_proposal(proposal_standard, scenario_standard)
    assert res_std["accepted"] is True
    assert res_std["policy"]["grouping"]["adaptation_rule"]["type"] == "fixed"
    assert "behavior_response" not in res_std["policy"]
