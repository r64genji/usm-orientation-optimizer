# AI Agent Optimization Specification: USM Student Movement Policies

This document establishes the optimization contract, full authority levers, immutable physical bottlenecks, and Pareto frontier evaluation criteria for an automated AI optimization agent working on the USM Orientation Movement Simulator (`usm_sim`).

---

## 1. Executive Mandate & Objective

The AI optimization agent is granted **full operational authority** to configure, iterate, and discover optimal student movement policies between campus hostels and event halls (Dewan Tuanku Syed Putra, DTSP, and Dewan Budaya G03 overflow).

The optimization objective is multiobjective and strictly governed by the **Pareto frontier**:
1. **Minimize student outdoor waiting time**: Eliminate prolonged exposure to Penang heat/sun on road shoulders, asphalt car parks, and outdoor staging pens.
2. **Minimize transit/trip duration**: Achieve smooth, continuous travel from origin release to indoor seated state without artificial blockages.
3. **Ensure zero event lateness**: 100% of student cohorts must be safely seated before the fixed 09:00 event start. Arriving and being seated before 09:00 is the sole punctuality success criterion.
4. **Minimize PPSL management & coordination friction**: Keep facilitator workload manageable within the 154-worker budget, avoiding high-stress choke points, conflicting duties, and excessive radio chatter.

---

## 2. Hard Physical Bottlenecks (Immutable — What the AI Agent CANNOT Change)

The physical environment, vehicles, and campus geography represent hard, invariant constraints. Any proposal that violates or ignores these constraints is physically invalid and will be rejected.

| Category | Hard Bottleneck / Invariant | Parameter Bound / Physical Law |
|---|---|---|
| **Bus Fleet** | Total campus orientation shuttle fleet | **Exactly 8 buses** (5 high-floor coaches + 3 electric buses). Shuttling in continuous loops (Origin $\rightarrow$ DTSP $\rightarrow$ Origin). |
| **Bus Geometry** | Usable doors for passenger boarding/alighting | **1 door per vehicle** (serial step boarding/alighting). |
| **Dwell Times** | Full-coach loading & unloading dwell | **180 seconds (3.0 min)** boarding dwell, **180 seconds (3.0 min)** alighting dwell per full coach pulse with standees (scaled conservatively). |
| **Berth Geometry** | DTSP road berth unloading capacity | Straight-line corridor holds 8 buses in-line; **maximum 4 buses actively offloading concurrently**. |
| **Mandatory Headcount** | Headcount dwell at ALL gathering areas | **5 minutes (300 seconds)** mandatory PPSL headcount dwell upon arrival at any staging/gathering area. |
| **Car Park Capacity** | DTSP 3-tier car park waiting area | **500 students safe seated capacity**, **600 students absolute maximum** on asphalt. |
| **DTSP Hall Capacity** | Main event hall seating limit | **Strictly 3,000 seats** allocated to orientation attendees (1,338 seats represents Kawsar main floor only; remaining students fill overflow). |
| **Overflow Venue** | Dewan Budaya G03 (Dewan Kuliah G & H) | **~500 seats total** (400–500 seats). Authorized active secondary overflow destination venue only; **NOT a waiting room**. Cohorts divert to fill G03 once DTSP reaches 3,000 seats. |
| **Labor Budget** | Total PPSL facilitator headcount | **154 workers total** across all campus duties. |
| **Door Ingest Physics** | Screening / security dwell at doors | **Zero credential/bag screening dwell** (students walk straight in; flow rate bounded only by door portal width). |
| **Hostel Release & Priority** | Release timing and departure sequencing | **All hostels release at 06:00:00 (t=0)**. Restu students wait at the **Restu cafe** first. **Tekun and Saujana have priority** due to lower headcounts and are queued/dispatched first. **Restu is dispatched last** (primary imposed wait). |
| **Pre-DTSP Holding** | Staging prior to hall entry | **Nearby lecture hall** (NOT Jalan Perpustakaan). Do not simulate this holding hall. |
| **Event Start Clock** | Event start deadline | **09:00 fixed start time**. 100% seated before 09:00 is a hard requirement. |

---

## 3. Full Authority Levers (What the AI Agent CAN Change)

The AI agent has full authority to manipulate and optimize all operational choices:

### 3.1 Simultaneous Bus Boarding & Student Staging at Origins
- **Simultaneous Boarding Berths**: Choose the number of buses boarding concurrently at the origin (e.g., 1, 2, 3, or 4 buses boarding at the same time at DUD/Restu pavilion).
- **PPSL Effort Trade-off**: Each simultaneous active boarding bus consumes dedicated PPSL supervision and queuing staff.
- **Pre-Boarding Student Staging**: Determine how students are queued, pre-arranged, and partitioned in the assembly area to feed the boarding buses efficiently.

### 3.2 Continuous File Flow & Column March Formations
- **One Long Continuous File (No Artificial Fixed Capacity Limit)**: Movement from gathering areas and along walking paths operates as **one long continuous file** (a continuous streaming queue). There is no artificial bucket capacity limit (such as a 20-student cap) blocking movement. Students stream continuously into the hall.
- **Column March Formations**: The AI agent can configure the file structure (single file, double file, or parallel streams) based on available PPSL road marshals and physical path width.
- **Movement Styles & Pacing**: March pacing, assembly buffers, and group cohesion rules.

### 3.3 Batch Sizes & Grouping Hierarchy
- **Group Target Sizes**: Choose batch sizes from small squads ($N=20$) up to full coach loads ($N=65\text{--}80$).
- **Grouping Basis**: Group students by `floor`, `wing`, `building`, `target_size`, or `mixed`.
- **Regrouping Policy**: Define whether cohorts must regroup at intermediate checkpoints or proceed as continuous streams.

### 3.4 Release Policies & Staggering Schedules
- **Simultaneous 06:00 Release**: All hostels release at 06:00:00 ($t=0$).
- **Restu Cafe Hold & Priority Invariants**: Restu students wait at the Restu cafe first upon release. Desasiswa Tekun and Desasiswa Saujana are prioritized due to lower headcounts, queued first, and dispatched before Restu. Restu is dispatched last.
- **Wave Pacing & Staggering**: Within the priority order, stagger wave dispatches or metered departure intervals between hostels/cohorts to prevent downstream reservoir overflow.
- **Dynamic Holding / Radio Metering**: Hold subsequent cohorts at hostel origins (or Restu cafe) if the DTSP car park approaches its 500-seat safe limit.
### 3.5 Routing & Modal Allocation
- **Modal Split**: Allocate which hostels/contingents use the 8-bus shuttle vs dedicated pedestrian corridors.
- **Corridor Selection**: Choose between campus perimeter paths, covered walkways, and designated road shoulders.
- **Direct Venue Assignment**: Route designated cohorts directly to Dewan Budaya G03 overflow venue once DTSP capacity (3,000 seats) is reached.

### 3.6 PPSL Worker Distribution (154 Worker Budget)
- **Stationing Strategy**: Allocate the 154 PPSL facilitators across origin boarding berths, student staging queues, walking waypoints, road crossings, gathering headcounts, and hall seating.
- **Marshal vs Escort Trade-off**: Choose between fixed-point corridor marshals or mobile squad escorts.

### 3.7 Bus Fleet Dispatch Rules
- **Dispatch Triggers**: Dispatch on fixed headway, fill-to-capacity, or dynamic origin queue triggers.
- **Hostel Priority**: Manage shuttle cycles between RST hostels (Saujana, Tekun, Restu) while respecting Tekun and Saujana priority (dispatched first) and Restu cafe hold with Restu dispatched last.

### 3.8 Destination & Ingest Management
- **Door Allocations**: Assign incoming cohorts to specific exterior doors (Pintu A, B, C, D) to balance foyer corridors.
- **Seating Block Sequence**: Coordinate hall filling order (back-to-front, section-by-section) to prevent aisle spillback.

---

## 4. Continuous Streaming Flow on Gathering Exit Paths

The three gathering areas (DTSP car park, Dataran Merah north plaza, G28 Siswaniaga south plaza) connect to the hall entry portals:
- **Continuous Single-File Pipeline**: Movement is **one long continuous file** without an arbitrary bucket cap (e.g. no artificial 20-student limit). 
- **Continuous Throughput**: At single-file spacing, students stream through at steady throughput ($\sim 25\text{--}35$ students/minute per file stream), feeding directly into hall doors.
- **Unrestricted Batch Flow**: Groups of 40, 80, or the entire cohort stream sequentially through the corridor without being broken up or halted by artificial capacity barriers.

---

## 5. Multiobjective Pareto Frontier Formulation

The agent must optimize proposals across four primary objective dimensions:

$$\min \quad \mathbf{F}(\mathbf{x}) = \begin{bmatrix} J_{\text{wait}}(\mathbf{x}) \\ J_{\text{trip}}(\mathbf{x}) \\ J_{\text{ppsl}}(\mathbf{x}) \end{bmatrix}$$
$$\text{Subject to: } \quad J_{\text{late}}(\mathbf{x}) = 0 \quad (\text{100\% seated before 09:00})$$

1. **$J_{\text{wait}}(\mathbf{x})$: Avoidable Student Wait Time**
   Penalizes outdoor queueing, sun exposure, and excessive stationary delays above mandatory headcount dwells.

2. **$J_{\text{trip}}(\mathbf{x})$: Total Journey Duration**
   Measures movement efficiency from origin release to indoor seated completion.

3. **$J_{\text{ppsl}}(\mathbf{x})$: PPSL Coordination Effort**
   $$\text{Max simultaneous workers deployed} \le 154, \quad \min(\text{handover friction} + \text{radio congestion})$$
   Accounts for workers required across multiple boarding buses, road safety marshals, and headcount stations.

4. **Punctuality Gate (Hard Feasibility Filter)**:
   $$t_{i, \text{seated}} < 09:00:00 \quad \forall i \in \{1, \dots, N\}$$
   Any proposal where students are seated after 09:00:00 is strictly marked infeasible.

---

## 6. Official Baseline Benchmark

All optimization proposals and Pareto frontier evaluations are measured against the official real-life baseline (`whole-campus-full-cohort`):
- **Full Cohort**: 3,543 students across all 8 hostels.
- **Hostel Release & Sequencing**: All hostels release at 06:00:00 ($t=0$). Restu students wait at the Restu cafe first. Tekun and Saujana have priority due to lower headcounts, queue first, and go through before Restu; Restu is dispatched last.
- **Continuous Queue Full-Bus Loading**: Buses load from continuous staging columns up to 100% capacity (80 for coaches, 40 for electric) without artificial squad capping.
- **Open Hall Access**: Immediate hall seating upon arrival with zero door screening checks.
- **Venue Allocation**: DTSP strictly capped at 3,000 seats (1,338 represents Kawsar main floor only); excess 543 students seated in Dewan Budaya G03 authorized active secondary overflow venue (~500 seats).
- **Event Deadline**: 09:00:00 hard ceiling ($J_{\text{late}} = 0$).
- **Baseline Performance Metrics**:
  - Total student wait: **2,567.0 student-hours** (mean: 43.5 min)
  - Outdoor sun exposure: **960.8 student-hours**
  - Restu average wait: **31.9 minutes**
  - Seating completion: **100% seated before 09:00:00**

