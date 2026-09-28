# USM Orientation Movement Simulator & Transit Optimizer

[![CI](https://github.com/r64genji/usm-orientation-optimizer/actions/workflows/ci.yml/badge.svg)](https://github.com/r64genji/usm-orientation-optimizer/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Zero External Core Deps](https://img.shields.io/badge/core%20deps-standard%20library%20only-brightgreen.svg)](usm_sim/)

A deterministic, discrete-event crowd simulation engine, transit optimizer, and operator mission-control dashboard for university orientation logistics at **Universiti Sains Malaysia (USM), Kampus Induk**.

During **Minggu Siswa Lestari (MSL)** orientation, 3,543 first-year students must be moved from eight residential hostels across campus to the central convocation hall (**Dewan Tuanku Syed Putra, DTSP**) for morning induction ceremonies. Under status-quo operations, students experience up to **151 minutes** of door-to-seat travel with **56 minutes** of static queueing in tropical heat, despite an active bus ride of only **3.1 minutes**.

This repository contains:
1. **Core Simulation Engine (`usm_sim`)**: Pure Python standard library discrete-event simulation engine modeling queue networks, pedestrian columns, 8-bus looping shuttles, finite PPSL marshals, and multi-berth hall ingress.
2. **Web Operator Dashboard (`operator_dashboard`)**: FastAPI service with a React 18/TypeScript GIS canvas delivering 60 FPS continuous particle replay of crowd flows, bus loops, and sector occupancies.
3. **Executive Proposal Site (`proposal_site`)**: Interactive, printable 12-page A4 operational reform proposal for university administration.

---

## Architecture & Subsystems

```
┌────────────────────────────────────────────────────────────────────────┐
│                        usm-orientation-optimizer                       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         ▼                           ▼                           ▼
┌──────────────────┐       ┌──────────────────┐        ┌──────────────────┐
│     usm_sim      │       │operator_dashboard│        │  proposal_site   │
│ Pure Python 3.11+│       │ FastAPI + React  │        │  Printable A4    │
│ Discrete-Event   │──────▶│ 60 FPS Canvas    │        │  12-Page Policy  │
│ Engine & Physics │       │ Particle Replay  │        │  Editor & Viewer │
└──────────────────┘       └──────────────────┘        └──────────────────┘
         │                           │
         ├───────────────────────────┤
         ▼                           ▼
┌──────────────────┐       ┌──────────────────┐
│    processed/    │       │     tests/       │
│ Derived GIS, GPS │       │ Invariant Tests, │
│ Tracks, Analyses │       │ Ingress Physics  │
└──────────────────┘       └──────────────────┘
```

### Module Responsibilities

- **`usm_sim/`**: Discrete-event queue network with integer millisecond scheduling (`heapq`), seeded pseudo-randomness, backpressure limits, and zero external runtime dependencies.
- **`operator_dashboard/`**: Local web service streaming timeline events, bottleneck attributions, capacity meters, and continuous canvas bus replays. Pre-built production frontend assets are included.
- **`proposal_site/`**: Standalone CSS Paged Media A4 interactive document for presentation to university leadership and logistics coordinators.
- **`processed/`**: Cleaned multi-session GPS trajectories, GeoJSON campus routes, and analytical video extraction data.
- **`docs/PRIVACY_AND_PUBLICATION.md`**: Privacy compliance and data stewardship policy (raw field telemetry in `raw_data/` is retained in internal archives and excluded from public distribution exports).

---

## Operational Invariants

All simulation models, policies, and optimizations strictly honor locked physical rules established by campus field measurements:

- **Fleet Composition:** Strictly locked to **8 buses** (5 coach buses + 3 electric shuttles), with exactly **1 usable door** per bus. Effective coach capacity is 65–80 passengers including aisle standees.
- **Route Topology:** The 8 buses continuously loop from the Restu/DUP gathering pavilion to DTSP drop-off, return empty, and re-queue. No extra vehicles may be added.
- **Hostel Release & Dispatch Order:** All hostels release at 06:00:00 ($t=0$). Restu students wait at Restu cafe; Tekun and Saujana depart first due to lower headcounts; Restu is dispatched last.
- **Hall Ingress Capacities:** DTSP full-hall capacity is calibrated at **~3,000 seats** (1,338 seats on the Kawsar main floor only). **Dewan Budaya G03** (DK G & H, ~500 seats) serves as an authorized active secondary overflow destination, not a holding pen.
- **Screening & Checkpoints:** No door security screening at DTSP (doors open from start; direct block seating). Mandatory 5-minute (300 s) headcounts occur at exterior gathering areas before hall admission.
- **Staffing Constraints:** Exactly 154 PPSL student facilitators available campus-wide for queue management, road crossings, and headcount stations.

---

## Quickstart

### 1. Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/r64genji/usm-orientation-optimizer.git
cd usm-orientation-optimizer

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install core simulation engine and CLI
pip install -e .

# Or install with developer and dashboard tools:
pip install -e ".[dev,dashboard]"
```

*Note: The core simulation engine `usm_sim` requires only Python 3.11+ standard library. External dependencies are needed only for the optional web dashboard and test runners.*

### 2. Run Simulations via CLI

```bash
# View CLI envelope schema
python -m usm_sim schema

# List built-in simulation cases
python -m usm_sim cases

# Run an artificial test case
python -m usm_sim simulate --case artificial --compact

# Run full campus cohort simulation (3,543 students)
python -m usm_sim simulate --case whole-campus-full-cohort --compact
```

### 3. Launch Web Operator Dashboard

```bash
# Start the local dashboard service (serves pre-built React app and API)
export DASHBOARD_AUTH_TOKEN="usm-orient-2026"
python -m operator_dashboard --host 127.0.0.1 --port 8866
```

Open `http://127.0.0.1:8866` in your browser. The dashboard provides:
- Interactive campus map with hostel pins and bus routes.
- 60 FPS Canvas replay with play/pause, time scrubbing, and 1×–60× speed multipliers.
- Live capacity meters for Restu Cafe, RST berths, DTSP car park tiers, and main hall seating.

### 4. View Executive A4 Proposal Document

```bash
# Verify and preview the standalone A4 proposal
node proposal_site/tests/verify.mjs
# Open proposal_site/index.html in any modern browser to view and print
```

---

## Testing & Verification

The test suite validates simulation physics, queue invariants, finite worker availability, and API contracts:

```bash
# Run fast invariant and contract tests (< 30 seconds)
pytest -q

# Run specific domain invariant test
pytest -q tests/test_sim_ticket03.py::test_policy_cannot_empty_or_drop_required_checkpoints

# Run slow full-cohort simulation tests
pytest -q --run-slow

# Run full campus benchmark optimization loop (expensive, ~3 minutes)
pytest -q --run-benchmark

---

## Privacy & Research Stewardship

Research telemetry in this repository was gathered during the September 2026 orientation week. In accordance with university research ethics:
- No student names, national ID (MyKad) numbers, or matriculation details are collected or published.
- Raw sensor telemetry (`raw_data/`), unblurred observational video recordings, and hardware identifiers are restricted to internal operational archives and excluded from public distribution exports.
- Cleaned GPS trajectories, campus GeoJSON layers, multi-session analyses, and reproducible test fixtures are published in `processed/` and `tests/fixtures/`.
- For full details, see [docs/PRIVACY_AND_PUBLICATION.md](docs/PRIVACY_AND_PUBLICATION.md).

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
