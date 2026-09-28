# Agent CLI Reference

This document describes how an automated agent uses the `usm_sim` command line interface.

## 1. Role

The agent proposes operating plans as JSON files. The CLI executes the simulation engine and scores the plan. The simulation engine computes all queue times, lateness values, and bottleneck measures. Do not invent or trust model-generated wait times. Trusted numbers come only from `simulate`, `search`, and `loop`.

## 2. Integration Contract

Any agent harness that can write a local file and execute a shell command can use this CLI. The CLI does not depend on any specific harness, SDK, or network service. Every command writes one JSON object to standard output.

Environment setup:
```bash
# Run with active virtualenv Python or standard Python 3.11+
python -m usm_sim schema
```

CLI execution examples:
```bash
# View command and error schemas
python -m usm_sim schema

# List built-in cases
python -m usm_sim cases

# Check a candidate proposal
python -m usm_sim check --case artificial-120-floor --proposal /path/to/proposal.json

# Simulate a policy
$PY -m usm_sim simulate --case artificial --compact

# Bounded search around a proposal
$PY -m usm_sim search --case artificial-120-floor --proposal /path/to/proposal.json --compact

# Run optimization loop across proposals
$PY -m usm_sim loop --case artificial-120-floor --proposals /path/to/proposals.json --round-budget 1 --compact

# Replay a recorded loop result
$PY -m usm_sim replay --case artificial-120-floor --record /path/to/record.json --compact

# Run full benchmark
python -m usm_sim benchmark --compact
```

## 3. Iterative Workflow

1. Write a structured proposal to a JSON file on disk.
2. Run `check` to validate fixed rules, static constraints, and units.
3. If `check` accepts the proposal, run `simulate` or `search` to score the policy.
4. Read resulting measures from standard output (`measures`, `pareto_set`, `failed_cases`).
5. Adjust proposal parameters to improve bottleneck metrics.
6. Repeat the cycle until performance converges.
7. Use `replay` with the recorded loop JSON to reproduce results deterministically.

## 4. Proposal Structure

A valid operating proposal must contain:
- `proposal_id`: Unique string identifier.
- `grouping`: Grouping basis (`floor`, `wing`, `building`, `target_size`, `mixed`) and options.
- `regroup_policy`: Physical regrouping rules and requirement flags.
- `release_rule`: Interval or trigger for releasing student groups.
- `counting`: Checkpoint placement, worker assignments, and count methods.
- `worker_allocation`: Total worker counts and assigned stations.
- `vehicle_dispatch_rule`: Bus fleet sizing and dispatch rules.
- `destination_rule`: Hall arrival and seating rules.
- `fixed_choices`: Non-tunable operational settings.
- `tunable`: Numerical search bounds and discrete choices.
- `assumptions`: Labeled external operational assumptions.

Refer to `tests/test_sim_ticket09.py` and `.scratch/usm-orientation-simulator/issues/09-ai-strategy-compiler.md` for complete schema examples.

## 5. Invariants and Forbidden Actions

The CLI and engine enforce strict physical rules:
- Never change attendance, room occupancy, or physical capacities in a proposal.
- Never modify route physics, walking speeds, or boarding rates.
- Never use GPS holdout cases (`restu-17sep`, `restu_18sep_rainy_replay`) as development cases in `search` or `loop`.
- Never claim production dispatch or live radio control. Loop execution is simulation only.

## 6. Output Modes and Output Redirection

All commands default to `--compact` mode.
- `--compact`: Omits large event traces (`event_trace`) and raw input copies (`input_snapshot`). Search and loop candidates omit simulation output traces.
- `--full`: Retains complete tick-level event traces.

To save output for subsequent analysis:
```bash
$PY -m usm_sim simulate --case artificial --compact > /tmp/sim_result.json
```
Standard output contains only the JSON payload. Error messages use the same JSON envelope on standard output with exit code `2`.
