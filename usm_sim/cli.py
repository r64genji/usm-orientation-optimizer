from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from usm_sim.behavior_cases import build_behavior_case
from usm_sim.benchmark import build_restu_18sep_rainy_replay, run_benchmark
from usm_sim.campus import build_whole_campus_origins_case, build_whole_campus_full_cohort_case
from usm_sim.constants import ERROR_CATEGORIES
from usm_sim.errors import SimulationError
from usm_sim.loop import replay_loop, run_loop
from usm_sim.proposals import check_proposal
from usm_sim.scenarios import (
    build_artificial_120_hostel_case,
    build_artificial_single_server_case,
    build_restu_17sep_replay,
    build_rst_shared_fleet_case,
)
from usm_sim.search import search
from usm_sim.simulate import simulate
from usm_sim.uncertainty import resolve_case

COMMANDS = [
    "schema",
    "cases",
    "check",
    "simulate",
    "resolve",
    "search",
    "loop",
    "replay",
    "benchmark",
    "routes",
]

CASE_REGISTRY = [
    {
        "id": "artificial",
        "builder": "build_artificial_single_server_case",
        "factory": build_artificial_single_server_case,
    },
    {
        "id": "restu-17sep",
        "builder": "build_restu_17sep_replay",
        "factory": build_restu_17sep_replay,
    },
    {
        "id": "artificial-120-floor",
        "builder": "build_artificial_120_hostel_case",
        "factory": lambda: build_artificial_120_hostel_case("floor"),
    },
    {
        "id": "rst-shared-fleet",
        "builder": "build_rst_shared_fleet_case",
        "factory": build_rst_shared_fleet_case,
    },
    {
        "id": "whole-campus-origins",
        "builder": "build_whole_campus_origins_case",
        "factory": build_whole_campus_origins_case,
    },
    {
        "id": "whole-campus-full-cohort",
        "builder": "build_whole_campus_full_cohort_case",
        "factory": build_whole_campus_full_cohort_case,
    },
    {
        "id": "restu-18sep-rainy",
        "builder": "build_restu_18sep_rainy_replay",
        "factory": build_restu_18sep_rainy_replay,
    },
    {
        "id": "behavior-mixed-readiness",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-mixed-readiness"),
    },
    {
        "id": "behavior-catch-up-walk",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-catch-up-walk"),
    },
    {
        "id": "behavior-queue-jump",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-queue-jump"),
    },
    {
        "id": "behavior-combined",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-combined"),
    },
    {
        "id": "behavior-post-map-choke",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-post-map-choke"),
    },
    {
        "id": "behavior-post-map-elsewhere",
        "builder": "build_behavior_case",
        "factory": lambda: build_behavior_case("behavior-post-map-elsewhere"),
    },
]


class CLIUsageError(Exception):
    def __init__(self, message: str, category: str = "invalid_value_or_unit", field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.field = field


class CLIParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        cat = "missing_input" if "required" in message or "missing" in message else "invalid_value_or_unit"
        raise CLIUsageError(message, category=cat)


def get_case(case_name: str) -> tuple[dict, dict]:
    for entry in CASE_REGISTRY:
        if entry["id"] == case_name:
            return entry["factory"]()
    raise SimulationError("unknown_reference", f"Unknown case: {case_name}", field="case")


def load_json_file(path_or_paths: str | Sequence[str] | None, field: str) -> Any:
    if path_or_paths is None:
        return None
    if isinstance(path_or_paths, str):
        paths = [path_or_paths]
    else:
        paths = list(path_or_paths)
    if not paths:
        return None

    results = []
    for p in paths:
        if p == "-" or p == "/dev/stdin":
            raw = sys.stdin.read()
            if not raw.strip():
                raise SimulationError("missing_input", f"Empty stdin input for {field}", field=field)
            try:
                data = json.loads(raw)
            except Exception as exc:
                raise SimulationError("invalid_value_or_unit", f"Invalid JSON in stdin for {field}: {exc}", field=field) from exc
            results.append(data)
        else:
            if not os.path.exists(p):
                raise SimulationError("missing_input", f"File not found: {p}", field=field)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = f.read()
            except Exception as exc:
                raise SimulationError("missing_input", f"Cannot read file {p}: {exc}", field=field) from exc
            try:
                data = json.loads(raw)
            except Exception as exc:
                raise SimulationError("invalid_value_or_unit", f"Invalid JSON in {p}: {exc}", field=field) from exc
            results.append(data)

    if len(results) == 1:
        return results[0]

    merged: dict[str, Any] = {}
    for item in results:
        if isinstance(item, dict):
            merged.update(item)
        else:
            merged = item
    return merged


def strip_traces(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: strip_traces(v)
            for k, v in obj.items()
            if k not in ("event_trace", "input_snapshot")
        }
    if isinstance(obj, list):
        return [strip_traces(item) for item in obj]
    return obj


def strip_candidate_traces(cand: Any) -> Any:
    if isinstance(cand, dict):
        d = dict(cand)
        d.pop("simulation_outputs", None)
        d.pop("event_trace", None)
        d.pop("input_snapshot", None)
        return d
    return cand
def resolve_scenario(args: argparse.Namespace) -> dict:
    if getattr(args, "scenario", None):
        res = load_json_file(args.scenario, "scenario")
        if isinstance(res, dict):
            return res
        raise SimulationError("invalid_value_or_unit", "Scenario must be a JSON object", field="scenario")
    if getattr(args, "case", None):
        scenario, _ = get_case(args.case)
        return scenario
    if getattr(args, "input", None):
        inp = load_json_file(args.input, "input")
        if isinstance(inp, dict):
            if "scenario" in inp and isinstance(inp["scenario"], dict):
                return inp["scenario"]
            if "route_stages" in inp or "places" in inp or "scenario_id" in inp:
                return inp
    raise SimulationError("missing_input", "Missing critical input: scenario", field="scenario")


def resolve_scenario_and_policy(args: argparse.Namespace) -> tuple[dict, dict]:
    scenario = None
    policy = None

    if getattr(args, "case", None):
        scenario, policy = get_case(args.case)

    if getattr(args, "scenario", None):
        sc = load_json_file(args.scenario, "scenario")
        if not isinstance(sc, dict):
            raise SimulationError("invalid_value_or_unit", "Scenario must be a JSON object", field="scenario")
        scenario = sc

    if getattr(args, "policy", None):
        pol = load_json_file(args.policy, "policy")
        if not isinstance(pol, dict):
            raise SimulationError("invalid_value_or_unit", "Policy must be a JSON object", field="policy")
        policy = pol

    if getattr(args, "input", None):
        inp = load_json_file(args.input, "input")
        if isinstance(inp, dict):
            if scenario is None and "scenario" in inp and isinstance(inp["scenario"], dict):
                scenario = inp["scenario"]
            if policy is None and "policy" in inp and isinstance(inp["policy"], dict):
                policy = inp["policy"]
    if scenario is None:
        raise SimulationError("missing_input", "Missing critical input: scenario", field="scenario")
    if policy is None:
        raise SimulationError("missing_input", "Missing critical input: policy", field="policy")

    return scenario, policy


def resolve_limits(args: argparse.Namespace) -> dict:
    if getattr(args, "limits", None):
        lim = load_json_file(args.limits, "limits")
        if isinstance(lim, dict):
            return lim
        raise SimulationError("invalid_value_or_unit", "Limits must be a JSON object", field="limits")
    return {"max_candidates": 4, "max_cases_per_candidate": 2}


def resolve_proposals(args: argparse.Namespace) -> list[dict]:
    prop_path = getattr(args, "proposals", None) or getattr(args, "proposal", None)
    if not prop_path:
        if getattr(args, "input", None):
            inp = load_json_file(args.input, "input")
            if isinstance(inp, dict) and "proposals" in inp:
                prop_path = inp["proposals"]
            elif isinstance(inp, list):
                return inp
    if not prop_path:
        raise SimulationError("missing_input", "Missing critical input: proposals", field="proposals")

    data = load_json_file(prop_path, "proposals")

    if isinstance(data, dict) and "proposals" in data and isinstance(data["proposals"], list):
        return data["proposals"]
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    raise SimulationError("invalid_value_or_unit", "Proposals must be a list or object with proposals array", field="proposals")


def build_parser() -> CLIParser:
    root_parent = argparse.ArgumentParser(add_help=False)
    root_parent.add_argument("--compact", dest="compact", action="store_true", default=True)
    root_parent.add_argument("--full", dest="compact", action="store_false")
    root_parent.add_argument("--seed", type=int, default=42)

    sub_parent = argparse.ArgumentParser(add_help=False)
    sub_parent.add_argument("--compact", dest="compact", action="store_true", default=argparse.SUPPRESS)
    sub_parent.add_argument("--full", dest="compact", action="store_false", default=argparse.SUPPRESS)
    sub_parent.add_argument("--seed", type=int, default=argparse.SUPPRESS)

    parser = CLIParser(
        prog="usm_sim",
        description="Harness-agnostic JSON CLI for the USM movement simulator.",
        parents=[root_parent],
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("schema", parents=[sub_parent])
    subparsers.add_parser("cases", parents=[sub_parent])

    p_check = subparsers.add_parser("check", parents=[sub_parent])
    p_check.add_argument("--proposal", nargs="+")
    p_check.add_argument("--scenario", nargs="+")
    p_check.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_check.add_argument("--layout", nargs="+")
    p_check.add_argument("--permitted", nargs="+")
    p_check.add_argument("--input", nargs="+")

    p_sim = subparsers.add_parser("simulate", parents=[sub_parent])
    p_sim.add_argument("--scenario", nargs="+")
    p_sim.add_argument("--policy", nargs="+")
    p_sim.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_sim.add_argument("--input", nargs="+")

    p_res = subparsers.add_parser("resolve", parents=[sub_parent])
    p_res.add_argument("--scenario", nargs="+")
    p_res.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_res.add_argument("--spec", nargs="+")
    p_res.add_argument("--input", nargs="+")

    p_search = subparsers.add_parser("search", parents=[sub_parent])
    p_search.add_argument("--proposal", nargs="+")
    p_search.add_argument("--scenario", nargs="+")
    p_search.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_search.add_argument("--limits", nargs="+")
    p_search.add_argument("--input", nargs="+")

    p_loop = subparsers.add_parser("loop", parents=[sub_parent])
    p_loop.add_argument("--scenario", nargs="+")
    p_loop.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_loop.add_argument("--proposals", nargs="+")
    p_loop.add_argument("--proposal", nargs="+")
    p_loop.add_argument("--round-budget", type=int, default=1)
    p_loop.add_argument("--limits", nargs="+")
    p_loop.add_argument("--input", nargs="+")

    p_rep = subparsers.add_parser("replay", parents=[sub_parent])
    p_rep.add_argument("--record", nargs="+")
    p_rep.add_argument("--scenario", nargs="+")
    p_rep.add_argument("--case", choices=[e["id"] for e in CASE_REGISTRY])
    p_rep.add_argument("--input", nargs="+")

    subparsers.add_parser("benchmark", parents=[sub_parent])

    p_routes = subparsers.add_parser("routes", parents=[sub_parent])
    p_routes.add_argument("--hostel", type=str, help="Hostel ID (e.g. restu, aman_damai, tekun)")
    p_routes.add_argument("--variant", type=str, default="standard", help="Route variant (standard, accessible_step_free)")
    p_routes.add_argument("--matrix", action="store_true", help="Print comparative matrix across all hostels")
    p_routes.add_argument("--export", action="store_true", help="Export full database to JSON")

    return parser


def detect_command(args_list: Sequence[str]) -> str:
    for token in args_list:
        if token in COMMANDS:
            return token
        if token.startswith("-"):
            continue
        return token
    return "cli"


def run_command(command: str, args: argparse.Namespace) -> tuple[dict, int]:
    compact = getattr(args, "compact", True)
    seed = getattr(args, "seed", 42)

    if command == "schema":
        result = {
            "commands": COMMANDS,
            "envelope": {
                "ok": "boolean",
                "command": "string",
                "result": "object or null",
                "error": "object or null",
            },
            "error_categories": sorted(ERROR_CATEGORIES),
            "exit_codes": {
                "0": "success (including accepted: false and no_feasible_plan)",
                "1": "simulate status other than completed",
                "2": "usage / JSON parse / missing file / SimulationError",
            },
        }
        return result, 0

    if command == "cases":
        result = {
            "cases": [
                {"id": entry["id"], "builder": entry["builder"]}
                for entry in CASE_REGISTRY
            ]
        }
        return result, 0

    if command == "check":
        if not getattr(args, "proposal", None):
            raise SimulationError("missing_input", "Missing critical input: proposal", field="proposal")
        proposal = load_json_file(args.proposal, "proposal")
        scenario = resolve_scenario(args)
        layout = load_json_file(args.layout, "layout") if getattr(args, "layout", None) else None
        permitted = load_json_file(args.permitted, "permitted") if getattr(args, "permitted", None) else None
        res = check_proposal(proposal, scenario, layout_assumptions=layout, permitted_decisions=permitted)
        if compact:
            res = strip_traces(res)
        return res, 0

    if command == "simulate":
        scenario, policy = resolve_scenario_and_policy(args)
        policy = dict(policy)
        policy["random_seed"] = seed
        res = simulate(scenario, policy)
        if compact:
            res = strip_traces(res)
        exit_code = 0 if res.get("status") == "completed" else 1
        return res, exit_code

    if command == "resolve":
        scenario = resolve_scenario(args)
        spec = load_json_file(args.spec, "spec") if getattr(args, "spec", None) else None
        res = resolve_case(scenario, case_spec=spec, seed=seed)
        if compact:
            res = strip_traces(res)
        return res, 0

    if command == "search":
        if not getattr(args, "proposal", None):
            raise SimulationError("missing_input", "Missing critical input: proposal", field="proposal")
        proposal = load_json_file(args.proposal, "proposal")
        scenario = resolve_scenario(args)
        limits = resolve_limits(args)
        res = search(proposal, scenario, evaluation_limits=limits, seed=seed)
        if compact:
            res = strip_traces(res)
            for key in ("feasible_plans", "feasible_set", "pareto_set", "tradeoffs", "failed_cases", "failure_records", "disqualified_plans", "evaluated_choices"):
                if key in res and isinstance(res[key], list):
                    res[key] = [strip_candidate_traces(c) for c in res[key]]
        return res, 0

    if command == "loop":
        scenario = resolve_scenario(args)
        proposals = resolve_proposals(args)
        round_budget = getattr(args, "round_budget", 1)
        limits = load_json_file(args.limits, "limits") if getattr(args, "limits", None) else None
        res = run_loop(
            campus_facts=scenario,
            proposals=proposals,
            round_budget=round_budget,
            evaluation_limits=limits,
            seed=seed,
        )
        if compact:
            compact_res = {
                "status": res.get("status"),
                "feasible_plan_found": res.get("feasible_plan_found"),
                "best_plan": strip_candidate_traces(strip_traces(res.get("best_plan"))),
                "validation_errors": res.get("validation_errors", []),
                "pareto_set": [strip_candidate_traces(strip_traces(p)) for p in res.get("pareto_set", [])],
                "stopping_reason": res.get("stopping_reason"),
                "claim": res.get("claim"),
                "recorded_proposals": res.get("recorded_proposals", []),
            }
            for opt_key in ("versions", "runtime", "budgets", "failed_cases"):
                if opt_key in res:
                    compact_res[opt_key] = strip_traces(res[opt_key])
            res = compact_res
        return res, 0

    if command == "replay":
        if not getattr(args, "record", None):
            raise SimulationError("missing_input", "Missing critical input: record", field="record")
        record = load_json_file(args.record, "record")
        scenario = resolve_scenario(args)
        res = replay_loop(record, campus_facts=scenario, seed=seed)
        if compact:
            compact_res = {
                "status": res.get("status"),
                "feasible_plan_found": res.get("feasible_plan_found"),
                "best_plan": strip_candidate_traces(strip_traces(res.get("best_plan"))),
                "validation_errors": res.get("validation_errors", []),
                "pareto_set": [strip_candidate_traces(strip_traces(p)) for p in res.get("pareto_set", [])],
                "stopping_reason": res.get("stopping_reason"),
                "claim": res.get("claim"),
            }
            for opt_key in ("versions", "runtime", "budgets", "failed_cases"):
                if opt_key in res:
                    compact_res[opt_key] = strip_traces(res[opt_key])
            res = compact_res
        return res, 0
    if command == "benchmark":
        res = run_benchmark()
        if compact:
            res = strip_traces(res)
        return res, 0
    if command == "routes":
        from usm_sim.routing import (
            export_scaffolding_database,
            generate_campus_routing_matrix,
            get_route_summary,
        )
        if getattr(args, "export", False):
            path = export_scaffolding_database()
            return {"exported": path}, 0
        if getattr(args, "hostel", None):
            variant = getattr(args, "variant", "standard") or "standard"
            return get_route_summary(args.hostel, variant), 0
        return {"matrix": generate_campus_routing_matrix()}, 0

    raise SimulationError("unknown_reference", f"Unknown command: {command}", field="command")


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    command = detect_command(raw_argv)

    if not raw_argv:
        err_payload = {
            "ok": False,
            "command": "cli",
            "error": {
                "error": True,
                "category": "missing_input",
                "message": "No command specified. Choose from: " + ", ".join(COMMANDS),
                "field": "command",
            },
        }
        sys.stdout.write(json.dumps(err_payload, indent=2, sort_keys=True) + "\n")
        return 2

    if raw_argv[0] in ("-h", "--help") and len(raw_argv) == 1:
        parser = build_parser()
        parser.print_help(sys.stdout)
        return 0

    if command not in COMMANDS and not any(t in COMMANDS for t in raw_argv):
        if any(t.startswith("--case") for t in raw_argv):
            raw_argv = ["simulate"] + raw_argv
            command = "simulate"

    parser = build_parser()

    try:
        args = parser.parse_args(raw_argv)
        cmd = args.command or command
        if cmd not in COMMANDS:
            raise CLIUsageError(f"Unknown command: {cmd}", field="command")
        result, exit_code = run_command(cmd, args)
        payload = {
            "ok": True,
            "command": cmd,
            "result": result,
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return exit_code
    except SimulationError as err:
        payload = {
            "ok": False,
            "command": command,
            "error": err.as_dict(),
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 2
    except CLIUsageError as err:
        err_dict: dict[str, Any] = {
            "error": True,
            "category": err.category,
            "message": err.message,
        }
        if err.field is not None:
            err_dict["field"] = err.field
        payload = {
            "ok": False,
            "command": command,
            "error": err_dict,
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 2
    except Exception as exc:
        err_dict = {
            "error": True,
            "category": "missing_input",
            "message": str(exc),
        }
        payload = {
            "ok": False,
            "command": command,
            "error": err_dict,
        }
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 2
