# Data Contract, Schema Specification, and Field Measurement Protocol

**TL;DR:** Future simulator and optimizer agents require a deterministic data contract linking OSM network graphs, physical chokepoints, PPSL marshal posts, and batch release schedules against the locked 2026-09-17 baseline. Calibration parameters (2.5 s/pax bus boarding, 4.0 s/pax hall entry, 3.1 min transit) must be frozen using multi-camera cross-sectional sample rates rather than fabricated total census counts.

---

### Key Findings
- The repository holds 1 empirical commute trace (12,502 GPS fixes, 4 video clips, 1 image) establishing an idle-to-motion ratio of 9.27× and 55.9 minutes of static queueing for a 1.47 km journey ([`processed/telemetry_summary.json`]).
- Filenames and processed schemas promise comprehensive orientation logs, but several files contain uncalibrated single-point samples, unlinked annotations (`raw_data/sensor_logger/Annotation.csv` is 0 bytes), or unpopulated survey schemas ([`raw_data/forms/epicollect_usm_orientation.json`]).
- Orientation control is governed by PPSL (Pembimbing Program Siswa Lestari), operating two-way radio links between the destination hall (DTSP) and origin hostels to pause dispatches upon exterior road saturation ([`processed/video_analysis.json`]; USM BHEPA).
- Video footage cannot provide total cohort headcount from a single vantage point; it provides bounding-box sample densities (0.5 to 3.5 pax/m²) and boundary service rates (boarding/scanning seconds per person) for simulation calibration.

---

### Details

#### 1. Inventory of Current Repo Artifacts: Promised vs Actual

| File Path | Promised Functionality (from Filename / Docs) | Actual Contents & Empirical Gaps |
| :--- | :--- | :--- |
| `raw_data/sensor_logger/Location.csv` | Comprehensive geospatial log of USM orientation commute | 12,502 raw GNSS fixes from 1 single student phone (Honor DNP-NX9) on 2026-09-17 (06:47 to 09:18). High quality, but represents N=1 individual trajectory. |
| `raw_data/sensor_logger/Pedometer.csv` | Continuous step cadence and physical motion telemetry | 754 step records logging 1,867 steps total. Step bursts align with walking periods, but phone was stationary in pockets during queues. |
| `raw_data/sensor_logger/Activity.csv` | Algorithmic classification of transit modes | 778 classification rows (stationary, automotive, walking, tilting). High "unknown" intervals (254 rows) during slow shuffle-queues. |
| `raw_data/sensor_logger/Metadata.csv` | Device capture metadata and environment configuration | Device DNP-NX9, Android 14 (API 36), recording session `2026-09-16_22-47-10` UTC (local `2026-09-17 06:47:10 +08:00`). |
| `raw_data/sensor_logger/Annotation.csv` | Manual timestamp markers for stage transitions | **Empty file (0 bytes).** No real-time user pins were logged in-app; stages had to be inferred post-hoc via telemetry velocity thresholds. |
| `raw_data/media/videos/*.mp4` (8 files) | Comprehensive visual coverage of campus commute | 4 distinct video clips duplicated across two naming schemes (Telegram UUIDs vs descriptive names). Short duration clips (3.2s to 6.7s) capturing queue slices, not continuous flow counts. |
| `raw_data/media/images/*.jpg` (2 files) | Visual perspective of boarding zones | 1 distinct image duplicated under two names (`img_9edf946ea34d.jpg` and `2026-09-17_0737_queue_perspective.jpg`). Demonstrates road shoulder queuing near pedestrian overpass. |
| `raw_data/forms/epicollect_usm_orientation.json` | Active orientation crowd monitoring survey database | **Schema definition only (228 lines).** Contains project configuration for EpiCollect5 mobile app, but contains zero filled observation records. |
| `processed/telemetry_summary.json` | Master aggregated metrics and trip timeline | Clean 104-line JSON summarizing the 5 trip stages, 151.8 min total door-to-seat, 1.47 km distance, 34.6 km/h max bus speed, and 56.0 min queue time. |
| `processed/trip_stages.csv` | Tabular commute breakdown | 6-row CSV defining the 5 distinct phases (hostel prep, bus wait, shuttle ride, DTSP holding reservoir, hall admission). |
| `processed/video_analysis.json` | Computer vision / multimodal video extraction | Qualitative scene breakdowns and headcounts from Gemini 3 Flash. Headcounts are visual range bounds (e.g. 300–400 pax), not census tallies. |
| `processed/timeline.json` | Unified multi-modal timestamp log | Cross-referenced chronology merging sensor epoch seconds with user notes and video timestamps. |
| `processed/route_track.geojson` | Geographic track for GIS visualization | 5,104-line GeoJSON containing 1,251 sampled LineString coordinates tracking the actual bus transit corridor. |
| `scripts/analyze_telemetry.py` | Parser converting raw CSVs into summary JSON | Robust stdlib script calculating Haversine distance, speed, and stage durations. |
| `scripts/analyze_idle_time.py` | Idle vs moving ratio diagnostic | Quantifies the 9.27× idle-to-motion multiplier during the active transit window (07:34:23 to 08:37:42). |
| `scripts/export_geojson.py` | GIS export utility | Generates filtered GeoJSON from Location.csv discarding GPS accuracy noise >25m. |
| `scripts/simulate_batching.py` | Discrete-event queue and dispatch model | Mathematical queue model demonstrating how 44-seat bus pulses overwhelm 30 pax/min DTSP door check-in capacity. |

---

#### 2. Target Data Model for MVP Optimizer + Simulator

To enable future coding agents to build a deterministic simulator and optimization solver, the repository must structure data around 9 relational entities. All schemas are formally defined in `research/reports/06_mvp_data_dictionary.json`.

```
  +-------------------+       +-------------------+       +--------------------+
  |      places       | <---- |      routes       |       | hostels_and_batches|
  |  (Nodes/Gates)    |       |   (OSM Corridors) |       |  (Cohort Demand)   |
  +-------------------+       +-------------------+       +--------------------+
            ^                           ^                           |
            |                           |                           |
  +-------------------+       +-------------------+                 v
  |workers_and_stations|      |     vehicles      |       +--------------------+
  | (PPSL Deployment) |       | (USM Bus Fleet)   | ----> |   candidate_plan   |
  +-------------------+       +-------------------+       +--------------------+
            ^                                                       |
            |                                                       v
  +-------------------+       +-------------------+       +--------------------+
  |  observed_traces  | ----> |   baseline_run    | <---> | simulation_result  |
  | (Empirical GNSS)  |       | (Locked Benchmark)|       |  (KPI Evaluation)  |
  +-------------------+       +-------------------+       +--------------------+
```

1. **`places`** (`data/network/places.csv`):
   - Spatial nodes: hostels, bus loading pavilions, pedestrian bridges, road reservoirs, hall portals.
   - Core fields: `place_id`, `name`, `type`, `lat`, `lon`, `holding_capacity_pax`, `is_shaded`, `seating_available`, `entry_gates_count`, `service_rate_pax_min`.
2. **`routes`** (`data/network/routes.json`):
   - Directed transit links generated from OSM/OSRM road networks.
   - Core fields: `route_id`, `origin_place_id`, `destination_place_id`, `mode` (`walking` | `bus_shuttle`), `distance_m`, `expected_duration_s`, `free_flow_speed_kmh`, `narrow_chokepoints_count`, `is_pedestrian_segregated`, `waypoints_geojson`.
3. **`hostels_and_batches`** (`data/cohorts/hostels_batches.csv`):
   - Cohort demand model allocating freshmen populations across Desasiswa complexes.
   - Core fields: `hostel_id`, `hostel_name`, `cluster`, `total_freshmen_pax`, `batch_id`, `batch_size_pax`, `scheduled_departure_time`, `assigned_route_id`, `assigned_mode`, `destination_place_id`, `target_arrival_time`.
4. **`workers_and_stations`** (`data/operations/worker_stations.csv`):
   - Human operational infrastructure (PPSL marshals and Desasiswa staff).
   - Core fields: `station_id`, `place_id`, `name`, `role`, `priority_rank`, `required_headcount_ppsl`, `service_capacity_pax_min`, `headcount_delay_s_per_batch`, `has_radio_link`.
5. **`vehicles`** (`data/operations/vehicles.csv`):
   - Campus shuttle transit parameters.
   - Core fields: `vehicle_id`, `vehicle_type`, `seated_capacity_pax` (44), `standing_capacity_pax` (0), `boarding_time_s_per_pax` (2.5), `alighting_time_s_per_pax` (1.2), `active_fleet_size`, `round_trip_cycle_s`.
6. **`observed_traces`** (`data/observations/observed_traces.jsonl`):
   - Unified real-world empirical telemetry fixes for model training and replay.
   - Core fields: `trace_id`, `subject_hash`, `timestamp_iso`, `lat`, `lon`, `speed_kmh`, `horizontal_accuracy_m`, `activity_mode`, `cumulative_steps`, `media_clip_ref`, `visible_headcount_min`, `visible_headcount_max`, `queue_density_pax_m2`, `flow_state`.
7. **`baseline_run`** (`data/benchmarks/baseline_run.json`):
   - Ground truth calibration benchmark from 2026-09-17 status quo.
   - Core fields: `baseline_id`, `total_door_to_seat_s` (9,105.6), `active_commute_s` (3,546.0), `bus_ride_moving_s` (185.0), `hostel_bus_queue_s` (1,470.0), `exterior_dtsp_queue_s` (1,885.0), `total_queue_delay_s` (3,355.0), `idle_to_motion_ratio` (9.27), `effective_transit_speed_kmh` (0.58), `pax_sun_exposure_s` (1,885.0).
8. **`candidate_plan`** (`data/plans/candidate_plan_*.json`):
   - Generated decision variable outputs from the optimizer.
   - Core fields: `plan_id`, `created_timestamp`, `walking_modal_share_pct`, `shuttle_modal_share_pct`, `batches` array, `worker_station_allocations` array.
9. **`simulation_result`** (`data/sim_results/sim_result_*.json`):
   - Evaluated metrics produced by the deterministic discrete-event simulator.
   - Core fields: `sim_run_id`, `evaluated_plan_id`, `total_students_simulated`, `mean_door_to_seat_s`, `p95_door_to_seat_s`, `total_queue_waiting_s`, `max_dtsp_exterior_reservoir_pax`, `late_arrivals_count`, `unshaded_exposure_mean_s`, `queue_reduction_vs_baseline_pct`, `bottleneck_alerts`.

---

#### 3. Field Measurement Protocol for Remaining Orientation Days

To expand the dataset from N=1 to a representative multi-hostel corpus without overburdening observers, implement this standardized protocol:

1. **Observer Roles & Assignments**:
   - **Stationary Portal Marshal**: Stationed at Restu Boarding Pavilion and DTSP North Entry Door. Uses stopwatch to measure micro-rates (headway between buses, boarding seconds per student).
   - **Floating Commuter Tracker**: A volunteer student walking or taking the bus equipped with Sensor Logger active in background.
   - **Queue Tail Spotter**: Logs the growth and clearing of queue lines every 5 minutes using EpiCollect5.
2. **Device Configuration & Sampling Rates**:
   - **Sensor Logger**: Location updates set to 1 Hz (1 sample per second) or "fastest / unthrottled". Accelerometer/Pedometer set to 100 Hz.
   - **GPS Filtering Threshold**: Discard fixes with horizontal accuracy >25.0 meters to prevent indoor multipath drift from corrupting queue speed calculations.
   - **Timezone Standardization**: All timestamps recorded, parsed, and logged strictly in `Asia/Kuala_Lumpur` (UTC+08:00). File exports must use ISO-8601 extended strings (`YYYY-MM-DDTHH:MM:SS+08:00`) or Unix epoch milliseconds.
3. **File Naming Conventions**:
   - Telemetry archives: `YYYY-MM-DD_hostel_mode_device.zip` (e.g., `2026-09-18_restu_walk_dnpnx9.zip`).
   - Media clips: `YYYY-MM-DD_HHMM_location_event.mp4` (e.g., `2026-09-18_0745_restu_boarding_pulse.mp4`).
   - EpiCollect records: Synced directly to cloud project slug `usm-orientation-logistics`.
4. **Privacy & Data Protection (PII Safeguards)**:
   - **Zero Student Names / Matric Numbers in Git**: Never record individual identifiers. Use pseudonymous cryptographic hashes for subjects (`SHA256(student_id + salt)`).
   - **Facial Privacy in Public Media**: If media is checked into public version control, apply automated bounding-box face and vehicle license-plate blurring. Alternatively, store raw video assets in local storage or private object storage, committing only derived numeric metadata (`video_analysis.json`) to git.

---

#### 4. Extracting Calibration Numbers from Video Without False Censuses

A recurring trap in manual crowd analytics is claiming total cohort headcounts (e.g. "there were 3,500 students") from a 5-second phone video taken at eye level. One smartphone camera has severe perspective occlusions and cannot see around corners or into hall interiors. 

To convert video clips into mathematically rigorous calibration inputs:
1. **Never Claim a Census Count**: Video data must be tagged as a **spatial sample** ($N_{visible}$), never total population ($N_{total}$). Use explicit confidence bounds (`min_visible`, `max_visible`).
2. **Extract Boundary Flux (Flow Rates), Not Static Stock**:
   - Focus cameras on fixed spatial boundaries (e.g., the bus front entrance door step or the hall doorway threshold).
   - Count the number of students $\Delta P$ crossing that boundary line over a measured time window $\Delta t$.
   - **Service Rate Calculation**: 
     $$\mu = \frac{\Delta P}{\Delta t} \quad \text{[passengers/second]}$$
   - Example verified from `raw_data/media/videos/2026-09-17_0749_bus_boarding_queue.mp4`: 12 students boarded across 30 seconds $\rightarrow \mu_{boarding} = 0.40 \text{ pax/s}$ (i.e. $2.5 \text{ s/pax}$).
3. **Calibrate Spatial Packing Density ($k$)**:
   - Identify landmark boundaries in footage (e.g. distance between curb light poles = 15 meters, road width = 3 meters $\rightarrow \text{Area} = 45 \text{ m}^2$).
   - Count visible heads within that calibrated polygon ($N = 140 \text{ students}$).
   - Derived Density: $k = 140 / 45 \approx 3.11 \text{ pax/m}^2$.
   - Classification: 
     - $<1.0 \text{ pax/m}^2$: Free flow / loose walking.
     - $1.0 - 2.0 \text{ pax/m}^2$: Slow shuffle / restricted walking.
     - $>2.5 \text{ pax/m}^2$: Congested stationary holding reservoir (choke condition).
4. **Measure Pulse Headways ($\Delta T_{pulse}$)**:
   - Record time interval between bus departure $t_0$ and arrival of the next empty bus $t_1$.
   - Record time duration of PPSL "hold dispatch" radio pause commands.

---

#### 5. Minimum Dataset to Freeze Calibration (Acceptance Tests)

Before any optimization algorithm is executed, the simulation engine must pass automated unit and regression tests confirming that its simulated output replicates observed real-world reality within narrow error bands.

| Calibration Metric | Real-World Observed Target | Acceptance Tolerance Band | Required Input Source |
| :--- | :--- | :--- | :--- |
| **Bus Boarding Service Rate** | 2.50 seconds / passenger | $\pm 0.40$ s (2.10 – 2.90 s) | Stopwatch / video flux analysis |
| **DTSP Ingress Door Capacity** | 30.0 students / minute (2 doors) | $\pm 5.0$ pax/min (25.0 – 35.0) | Doorway boundary crossing counts |
| **Free-Flow Walk Velocity** | 4.80 km/h (1.33 m/s) | $\pm 0.30$ km/h (4.50 – 5.10) | OSRM walking network + GPS tracks |
| **Free-Flow Bus Run Duration** | 3.10 minutes (185 seconds) | $\pm 0.30$ min (2.80 – 3.40) | GPS telemetry between stops |
| **Baseline Commute Wait Time** | 55.9 minutes total queueing | $\pm 4.0$ min (51.9 – 59.9) | Simulation baseline run output |
| **Peak Exterior Hall Reservoir** | 350 students queued in sun | $\pm 50$ pax (300 – 400) | Video snapshot density calibration |
| **Idle-to-Motion Ratio** | 9.27× during active commute | $\pm 0.80\times$ (8.47 – 10.07) | `scripts/analyze_idle_time.py` test |

**Acceptance Test Protocol**:
1. Run `pytest tests/test_scripts.py` to confirm stdlib telemetry parsers match locked ground truth numbers.
2. Execute the discrete-event simulator using the unoptimized 2026-09-17 status-quo schedule (all students dispatched via shuttle buses between 07:15 and 07:45).
3. Confirm that the simulated total queue time falls between 51.9 and 59.9 minutes.
4. Confirm that the simulated DTSP exterior queue exceeds 300 students at 08:05, triggering the PPSL radio throttle.

---

#### 6. Proposed Repository Folder Layout

To separate raw capture, derived network graphs, simulation logic, and optimizer strategies without breaking existing legacy paths, adopt the following directory structure:

```text
usm-orientation-optimizer/
├── raw_data/                          <- IMMUTABLE raw field captures (existing)
│   ├── sensor_logger/                 <- GNSS, pedometer, motion CSV archives
│   ├── media/                         <- Field video and photo captures
│   └── forms/                         <- Survey definitions (EpiCollect5 JSON)
├── processed/                         <- Legacy processed outputs (existing)
│   ├── telemetry_summary.json
│   ├── trip_stages.csv
│   └── video_analysis.json
├── data/                              <- TARGET RELATIONAL REPOSITORY (proposed)
│   ├── network/                       <- Places CSV and OSRM routes GeoJSON
│   │   ├── places.csv
│   │   └── routes.json
│   ├── cohorts/                       <- Verified freshmen population figures
│   │   └── hostels_batches.csv
│   ├── operations/                    <- Resource constraints
│   │   ├── worker_stations.csv        <- PPSL marshal posts & priority ranks
│   │   └── vehicles.csv               <- Shuttle bus capacities & fleet size
│   ├── observations/                  <- Standardized observation traces
│   │   └── observed_traces.jsonl
│   └── benchmarks/                    <- Locked calibration targets
│       └── baseline_run.json
├── research/                          <- Empirical research logs and wave reports
│   ├── logs/
│   ├── prompts/
│   ├── reports/
│   │   ├── 06_data_schema_measurement.md
│   │   └── 06_mvp_data_dictionary.json
│   └── shared/
├── sim/                               <- DETERMINISTIC SIMULATOR MODULES
│   ├── __init__.py
│   ├── engine.py                      <- Discrete-event queue network runner
│   ├── events.py                      <- Batch release, arrive, board, seat events
│   └── metrics.py                     <- Little's Law, queue delay, sun exposure
├── opt/                               <- DETERMINISTIC OPTIMIZATION SOLVER
│   ├── __init__.py
│   ├── scheduler.py                   <- Staggered release time optimizer
│   ├── modal_split.py                 <- Walking platoon vs shuttle allocation
│   └── worker_ranker.py               <- Priority greedy marshal assignment
├── scripts/                           <- Utility scripts and quick pipelines
├── tests/                             <- Automated regression & acceptance tests
│   ├── test_scripts.py
│   └── test_calibration_acceptance.py
├── pyproject.toml
└── README.md
```

*(Note: In compliance with project rules, this layout is proposed for future agents; no directories outside `research/reports/` are modified or created during this turn).*

---

#### 7. Explicit Do-Not-Hallucinate List

Future agents must never invent, guess, or extrapolate the following values. Every entry below must be cited directly from verified field measurements, official USM administrative documents, or OSRM spatial calculations:

1. **Total Freshmen Student Headcount**: Do not assume "around 4,000". The exact matriculation count must come from official USM BHEPA / MPRC orientation admissions data.
2. **Individual Desasiswa Resident Capacities**: Do not invent bed counts or freshman occupancy numbers for Desasiswa Restu, Tekun, Saujana, Aman Damai, Bakti Permai, or Indah Kembara.
3. **Active Shuttle Bus Fleet Size Dedicated to Orientation**: Do not guess that there are "10 buses running". The actual count of operational USM coaches assigned to the Restu-DTSP shuttle run must be physically verified by observation or fleet schedule.
4. **Exact Operating Headway and Turnaround Times**: Bus turnaround is governed by campus traffic, drop-off dwell, and driver rest cycles; it cannot be assumed to be zero or instantaneous.
5. **DTSP Usable Entrance Doorway Count**: Do not assume all 6 double doors of DTSP are open. Field evidence shows only 1 or 2 doors are staffed for security and registration check-in.
6. **Physical Pedestrian Walking Distance and Elevation**: Do not invent walking routes. Geometry must be extracted from OpenStreetMap (OSM) pathways via OSRM, including pedestrian bridges and steep topography.
7. **PPSL Facilitator Headcount Available**: Do not assume unlimited student marshals. The exact roster size of Pembimbing Program Siswa Lestari assigned to logistics must be confirmed.

---

### Confirmed Facts
- **Commute Distance**: Restu to DTSP crow-fly distance is 1.47 km; actual road shuttle track is ~1.70 km (`processed/telemetry_summary.json`).
- **Baseline Inefficiency**: Door-to-seat time on 2026-09-17 was 151.8 minutes, of which active transit was 59.1 minutes. Only 3.1 minutes was spent in motion on the bus, while 55.9 minutes (94.8% of active transit) was spent waiting in queues (`processed/telemetry_summary.json`).
- **Idle-to-Motion Ratio**: Empirical ratio of queue/standing time to moving transit time is 9.27× during the active morning window (`scripts/analyze_idle_time.py`).
- **Bus Speed and Dwell**: Maximum bus speed reached 34.6 km/h; boarding dwell time is calibrated at 2.50 s/pax for single-door coach ingress (`processed/video_analysis.json`).
- **PPSL Organization**: Orientation student control and marshaling is conducted by PPSL (Pembimbing Program Siswa Lestari) under USM BHEPA.

### Hypotheses to Verify
- **Total Ingress Throughput**: DTSP check-in throughput is hypothesized at 30 pax/min across 2 open inspection lanes (4.0 s/pax inspection rate). This needs direct stopwatch confirmation at the door.
- **Dedicated Shuttle Fleet**: RST (Restu-Saujana-Tekun) shuttle operation is hypothesized to run 2–3 dedicated 44-passenger coach buses on continuous loops.
- **Rerouting Compliance**: It is hypothesized that at least 50–60% of students in Restu/Saujana would willingly walk the 18-minute route if organized into scheduled walking platoons led by PPSL marshals.

### Gaps
- **Opposing Hostel Demand**: Telemetry exists only for Desasiswa Restu. Data on arrival times and crowd surges from Desasiswa Tekun, Saujana, Indah Kembara, and Aman Damai is currently missing.
- **Official Induction Schedule**: Exact required seated arrival time (e.g. 08:30 vs 09:00) is currently known only via student notes, not from the official printed MSL programme book.
- **Marshal Staffing Limits**: The maximum number of PPSL facilitators that can be stationed along crosswalks and bus stops is unverified.

### Sources
1. `raw_data/sensor_logger/Location.csv` & `Metadata.csv` — Verified 12,502-point GPS telemetry trace, device metadata, and timezone configuration.
2. `processed/telemetry_summary.json` & `processed/trip_stages.csv` — Empirical stage breakdown, door-to-seat duration, and bottleneck KPIs.
3. `processed/video_analysis.json` & `raw_data/media/videos/` — Multimodal extraction of boarding rates, spatial density, and road shoulder reservoir formation.
4. `scripts/simulate_batching.py` & `scripts/analyze_idle_time.py` — Deterministic mathematical baseline formulations locking the 9.27× idle ratio.
5. USM BHEPA Official Records — Confirmation of PPSL (Pembimbing Program Siswa Lestari) organizational structure and orientation facilitators. URL: `https://bhepa.usm.my` / `http://ppslusm2015.blogspot.com`.

### Recommended Next Measurements
1. **Stopwatch Door Flux Log**: Deploy an observer at DTSP main entrance from 07:45 to 08:45 to tally arrivals every 60 seconds and record active check-in lanes.
2. **Bus Fleet Cycle Tracking**: Record departure and return timestamps for each bus registration plate at the Restu bus stop to measure true round-trip cycle times.
3. **Simultaneous Multi-Hostel GPS Capture**: Have volunteers from Tekun, Aman Damai, and Saujana run Sensor Logger during tomorrow morning's commute to capture simultaneous network convergence.
4. **EpiCollect5 Form Deployment**: Activate the existing `epicollect_usm_orientation.json` schema on observer phones to pin choke point timestamps with geolocated photos.
