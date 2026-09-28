"""Named behavior variance cases and PPSL post-map policies.

Covers BV-07:
- behavior-mixed-readiness
- behavior-catch-up-walk (empty vs packed occupancy on leftovers)
- behavior-queue-jump (attempt events exist; default refuse unless policy allows)
- combined leftover+jump case used by two post maps
- two PPSL post-map policies on that same resolved leftover+jump population:
  - posts at the choke (min_station_staff at the jump/door place)
  - posts elsewhere (same worker count, different place)
- All unused phenomenon families declared as zero/empty.
- Evidence categorized as 'assumed' with notes.
- Artificial counts only.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from usm_sim.behavior import ALL_PHENOMENON_FAMILIES
from usm_sim.errors import SimulationError
from usm_sim.scenarios import build_artificial_single_server_case


def _declare_phenomena(active: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Declare all phenomenon families, setting unused ones to zero."""
    active_dict = dict(active or {})
    phenomena: dict[str, Any] = {}
    for fam in ALL_PHENOMENON_FAMILIES:
        if fam in active_dict:
            phenomena[fam] = active_dict[fam]
        else:
            phenomena[fam] = {"count": 0}
    return phenomena


def build_behavior_mixed_readiness_case() -> tuple[dict, dict]:
    """Build a scenario with mixed readiness within a single source unit.

    10 declared population: 5 on-time, 3 late attendees, 2 no-shows.
    Attending total = 8.
    Split-and-go policy creates a late remainder part.
    """
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 10
    unit["resolved_attendance"] = 8
    unit["estimated_attendance"] = 10
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(10)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 10},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(10)
            ],
            "student_count": 10,
        }
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "behavior-mixed-readiness",
        "mode": "explicit_events",
        "phenomena": _declare_phenomena({
            "late_reporting": {"count": 3, "evidence": {"category": "assumed", "note": "artificial late cohort"}},
            "mixed_readiness": {"count": 3, "evidence": {"category": "assumed", "note": "mixed readiness in unit"}},
            "no_show": {"count": 2, "evidence": {"category": "assumed", "note": "artificial no-show cohort"}},
        }),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_ontime",
                    "count": 5,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "on-time cohort"},
                },
                {
                    "cohort_id": "c_late",
                    "count": 3,
                    "attendance_state": "attending",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 120.0,
                    "readiness_s": 120.0,
                    "evidence": {"category": "assumed", "note": "late cohort"},
                },
                {
                    "cohort_id": "c_noshow",
                    "count": 2,
                    "attendance_state": "no_show",
                    "reporting_mode": "delay_from_required",
                    "late_assembly_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "no-show cohort"},
                },
            ]
        },
        "events": [],
    }

    policy["policy_id"] = "behavior_mixed_readiness_policy"
    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 60.0
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
        ]
    }
    return scenario, policy


def build_behavior_catch_up_walk_case(overlapping: bool = False) -> tuple[dict, dict]:
    """Build a catch-up walk case comparing empty vs packed path occupancy on leftovers.

    When overlapping is False (vacated):
    - Pulse 1 (2 students) departs at t=0 and vacates walk_1 at t=60.
    - Leftover (2 students) departs at t=100 with occupancy_ahead = 0.
    - Leftover pays 0 shared path extra seconds and factor 1.0 (free walk).

    When overlapping is True:
    - Pulse 1 (10 students) departs at t=0 on a 100s walk with operating limit 5.
    - Leftover (2 students) departs at t=20 while pulse 1 is still on path.
    - Leftover encounters occupancy_ahead >= 5 and pays congested duration factor and shared path extra.
    """
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    n_pulse1 = 10 if overlapping else 2
    n_leftover = 2
    total = n_pulse1 + n_leftover
    unit["declared_population"] = total
    unit["resolved_attendance"] = total
    unit["estimated_attendance"] = total
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(total)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": total},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(total)
            ],
            "student_count": total,
        }
    ]

    base_duration = 100.0 if overlapping else 60.0
    scenario["route_legs"][0]["duration_s"] = base_duration
    scenario["route_legs"][0]["shared_resource_ids"] = ["shared_path_1"]
    scenario["shared_resources"] = [
        {
            "id": "shared_path_1",
            "kind": "path",
            "capacity_students": 100,
            "operating_limit_students": 5,
            "duration_s": 50.0 if overlapping else 400.0,
        }
    ]
    congested_factor = 2.0 if overlapping else 1.5
    scenario["operating_rules"]["walk_occupancy_rule"] = {
        "empty_duration_factor": 1.0,
        "congested_duration_factor": congested_factor,
        "congested_at": "operating_limit",
    }

    leftover_time_s = 20.0 if overlapping else 100.0
    case_name = "behavior-catch-up-walk-overlapping" if overlapping else "behavior-catch-up-walk"
    scenario["behavior"] = {
        "version": "1.0",
        "case_id": case_name,
        "mode": "explicit_events",
        "phenomena": _declare_phenomena({
            "catch_up_walk": {"count": n_leftover, "evidence": {"category": "assumed", "note": "catch up walk"}},
            "late_reporting": {"count": n_leftover, "evidence": {"category": "assumed", "note": "leftover"}},
            "mixed_readiness": {"count": n_leftover, "evidence": {"category": "assumed", "note": "leftover"}},
        }),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_pulse1",
                    "count": n_pulse1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "pulse 1"},
                },
                {
                    "cohort_id": "c_leftover",
                    "count": n_leftover,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": leftover_time_s,
                    "readiness_s": leftover_time_s,
                    "evidence": {"category": "assumed", "note": "leftover"},
                },
            ]
        },
        "events": [],
    }

    policy["policy_id"] = "behavior_catch_up_walk_policy"
    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 10.0 if overlapping else 30.0
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "catch_up_walk", "action": "split-and-go"},
        ]
    }
    return scenario, policy


def build_behavior_queue_jump_case(allow_jump: bool = False) -> tuple[dict, dict]:
    """Build a queue jump case at a discrete service place.

    A second arriving student attempts to jump FIFO ahead of the first student at 'entrance'.
    Default policy refuses the jump; setting allow_jump=True enacts the jump.
    """
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 2
    unit["resolved_attendance"] = 2
    unit["estimated_attendance"] = 2
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(2)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 2},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(2)
            ],
            "student_count": 2,
        }
    ]
    scenario["route_legs"][0]["duration_s"] = 10.0
    scenario["route_stages"][1]["service_duration_s"] = 50.0

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "behavior-queue-jump",
        "mode": "explicit_events",
        "phenomena": _declare_phenomena({
            "queue_jump": {"count": 1, "evidence": {"category": "assumed", "note": "FIFO queue jump attempt"}},
            "late_reporting": {"count": 1, "evidence": {"category": "assumed", "note": "second arrival"}},
            "mixed_readiness": {"count": 1, "evidence": {"category": "assumed", "note": "second arrival"}},
        }),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_first",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "first arrival"},
                },
                {
                    "cohort_id": "c_second",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 5.0,
                    "readiness_s": 5.0,
                    "evidence": {"category": "assumed", "note": "second arrival attempting jump"},
                },
            ]
        },
        "events": [
            {
                "event_id": "evt_jump_entrance",
                "phenomenon": "queue_jump",
                "place_id": "entrance",
                "target": {"cohort_id": "c_second", "place_id": "entrance"},
                "trigger": {"before_stage": "entrance_service"},
                "evidence": {"category": "assumed", "note": "jump queue at entrance service"},
            }
        ],
    }

    policy["policy_id"] = "behavior_queue_jump_policy"
    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 2.0
    action = "allow-queue-jump" if allow_jump else "refuse-queue-jump"
    policy["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {"trigger": "queue_jump", "action": action, "place_id": "entrance"},
        ]
    }
    return scenario, policy


def build_post_map_choke_policy(
    scenario: Mapping[str, Any] | None = None,
    base_policy: Mapping[str, Any] | None = None,
) -> dict:
    """Build a PPSL post-map policy stationing workers at the choke ('entrance').

    Worker is stationed at 'entrance' with min_station_staff=1.
    """
    if base_policy is None:
        _, base_policy = build_artificial_single_server_case()
    pol = copy.deepcopy(dict(base_policy))
    pol["policy_id"] = "behavior_post_map_choke_policy"
    pol["worker_allocation"] = {
        "assignments": [
            {
                "worker_id": "station_worker_01",
                "role": "station",
                "place_id": "entrance",
                "travel_s": 5.0,
            }
        ]
    }
    pol["min_station_staff"] = {"entrance": 1}
    pol["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {
                "trigger": "queue_jump",
                "action": "intercept-at-station",
                "place_id": "entrance",
                "min_station_staff": 1,
                "fallback": "allow-queue-jump",
            },
        ]
    }
    return pol


def build_post_map_elsewhere_policy(
    scenario: Mapping[str, Any] | None = None,
    base_policy: Mapping[str, Any] | None = None,
) -> dict:
    """Build a PPSL post-map policy stationing the SAME worker elsewhere ('origin').

    Worker is stationed at 'origin' with min_station_staff=1 at 'origin'.
    At the choke ('entrance'), 0 workers are present, leading to a station miss.
    """
    if base_policy is None:
        _, base_policy = build_artificial_single_server_case()
    pol = copy.deepcopy(dict(base_policy))
    pol["policy_id"] = "behavior_post_map_elsewhere_policy"
    pol["worker_allocation"] = {
        "assignments": [
            {
                "worker_id": "station_worker_01",
                "role": "station",
                "place_id": "origin",
            }
        ]
    }
    pol["min_station_staff"] = {"origin": 1}
    pol["behavior_response"] = {
        "rules": [
            {"trigger": "late_reporting", "action": "split-and-go"},
            {"trigger": "mixed_readiness", "action": "split-and-go"},
            {
                "trigger": "queue_jump",
                "action": "intercept-at-station",
                "place_id": "entrance",
                "min_station_staff": 1,
                "fallback": "allow-queue-jump",
            },
        ]
    }
    return pol


def build_behavior_combined_case(post_map: str = "choke") -> tuple[dict, dict]:
    """Build combined leftover + jump case used to compare two PPSL post-map policies.

    The scenario contains a late leftover cohort that also attempts a queue jump
    at 'entrance'. Exactly 1 station worker is declared in the initial state.
    Worker travel is declared between 'origin' and 'entrance'.

    Depending on post_map ('choke' vs 'elsewhere'):
    - 'choke': Worker is stationed at the choke ('entrance') with min_station_staff=1.
    - 'elsewhere': Worker is stationed elsewhere ('origin') with min_station_staff=1 at origin.
    Both policies act on the SAME resolved leftover+jump population without increasing worker count.
    """
    scenario, policy = build_artificial_single_server_case()
    unit = scenario["source_units"][0]
    unit_id = unit["id"]
    unit["declared_population"] = 2
    unit["resolved_attendance"] = 2
    unit["estimated_attendance"] = 2
    unit["members"] = [
        {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
        for i in range(2)
    ]
    scenario["initial_state"]["students"] = [
        {
            "part_id": "part_origin",
            "group_id": "g_walk",
            "source_unit_id": unit_id,
            "place_id": "origin",
            "hostel_id": "synthetic",
            "hostel_composition": {"synthetic": 2},
            "members": [
                {"student_key": f"s{i}", "queue_tie_key": f"{i:02d}", "source_unit_id": unit_id, "hostel_id": "synthetic"}
                for i in range(2)
            ],
            "student_count": 2,
        }
    ]

    # Exactly 1 station worker declared, initially stationed at origin
    scenario["initial_state"]["workers"] = [
        {"id": "station_worker_01", "role": "station", "place_id": "origin", "available_time_s": 0.0}
    ]
    scenario["operating_rules"]["worker_travel"] = [
        {"from_place_id": "origin", "to_place_id": "entrance", "duration_s": 5.0},
        {"from_place_id": "entrance", "to_place_id": "origin", "duration_s": 5.0},
    ]

    scenario["behavior"] = {
        "version": "1.0",
        "case_id": "behavior-combined",
        "mode": "explicit_events",
        "phenomena": _declare_phenomena({
            "late_reporting": {"count": 1, "evidence": {"category": "assumed", "note": "leftover late reporting"}},
            "mixed_readiness": {"count": 1, "evidence": {"category": "assumed", "note": "mixed readiness"}},
            "queue_jump": {"count": 1, "evidence": {"category": "assumed", "note": "queue jump at choke"}},
        }),
        "source_unit_splits": {
            unit_id: [
                {
                    "cohort_id": "c_ontime",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 0.0,
                    "readiness_s": 0.0,
                    "evidence": {"category": "assumed", "note": "on-time"},
                },
                {
                    "cohort_id": "c_leftover",
                    "count": 1,
                    "attendance_state": "attending",
                    "reporting_mode": "absolute",
                    "actual_reporting_s": 20.0,
                    "readiness_s": 20.0,
                    "evidence": {"category": "assumed", "note": "leftover"},
                },
            ]
        },
        "events": [
            {
                "event_id": "evt_jump_combined",
                "phenomenon": "queue_jump",
                "place_id": "entrance",
                "target": {"cohort_id": "c_leftover", "place_id": "entrance"},
                "trigger": {"before_stage": "entrance_service"},
                "evidence": {"category": "assumed", "note": "leftover queue jump at entrance choke"},
            }
        ],
    }

    policy["grouping"] = dict(policy.get("grouping") or {})
    policy["grouping"]["maximum_assembly_wait_s"] = 5.0

    if post_map == "choke":
        pol = build_post_map_choke_policy(scenario, base_policy=policy)
    else:
        pol = build_post_map_elsewhere_policy(scenario, base_policy=policy)

    return scenario, pol


def build_behavior_case(case_id: str, **kwargs: Any) -> tuple[dict, dict]:
    """Build a named behavior variance case by case_id string."""
    if case_id == "behavior-mixed-readiness":
        return build_behavior_mixed_readiness_case()
    if case_id in ("behavior-catch-up-walk", "behavior-catch-up-walk-vacated"):
        return build_behavior_catch_up_walk_case(overlapping=kwargs.get("overlapping", False))
    if case_id in ("behavior-catch-up-walk-overlapping", "behavior-catch-up-walk-congested"):
        return build_behavior_catch_up_walk_case(overlapping=True)
    if case_id == "behavior-queue-jump":
        return build_behavior_queue_jump_case(**kwargs)
    if case_id in ("behavior-combined", "behavior-leftover-jump"):
        post_map = kwargs.get("post_map", "choke")
        return build_behavior_combined_case(post_map=post_map)
    if case_id == "behavior-post-map-choke":
        return build_behavior_combined_case(post_map="choke")
    if case_id == "behavior-post-map-elsewhere":
        return build_behavior_combined_case(post_map="elsewhere")

    raise SimulationError(
        "unknown_reference",
        f"Unknown behavior case: {case_id!r}",
        field="case_id",
    )
