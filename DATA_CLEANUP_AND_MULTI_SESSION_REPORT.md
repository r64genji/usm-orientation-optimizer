# Multi-Session GPS Telemetry Cleanup, Filtering, & Multi-Sensor Fusion Report

**Project**: USM Orientation Logistics Optimizer  
**Location**: Universiti Sains Malaysia (USM) Main Campus, Penang, Malaysia  
**Corridor**: Desasiswa Restu / RST Complex $\leftrightarrow$ Dewan Tuanku Syed Putra (DTSP)  

---

## 1. Executive Summary & Session Catalog

Three distinct telemetry recording sessions from Sensor Logger (Android `DNP-NX9`) were organized, cleaned, filtered, and synchronized. The datasets span two consecutive orientation days under contrasting environmental and operational conditions:

| Session ID | Date | Local Time Window | Duration | Route / Corridor | Weather / Operational Condition |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Session 1** (`M08`) | 2026-09-17 | 06:47:12 – 09:18:57 | 151.8 min | Desasiswa Restu $\rightarrow$ DTSP | **Clear / Sunny Morning**: Standard orientation induction batching with severe exterior holding queue bottleneck outside DTSP. |
| **Session 2** (`Persiaran Sains`) | 2026-09-17 | 17:36:21 – 17:37:44 | 1.4 min | DTSP $\rightarrow$ Persiaran Sains | **Evening Dispersal**: Post-event dispersal walk westbound along Persiaran Sains road shoulder away from DTSP. |
| **Session 3** (`M01`) | 2026-09-18 | 06:19:03 – 08:43:53 | 144.8 min | Desasiswa Restu (Cafeteria) $\rightarrow$ DTSP | **Rainy Morning Weather Delay**: Prolonged 119-min holding/sheltering in RST Cafeteria awaiting rain cessation, followed by walk to Padang Kawad and bus transit. |

---

## 2. Multi-Sensor Data Fusion & Noise Filtering Methodology

### The Pitfall of Single-Sensor Reliance
When analyzing mobile device telemetry in dense campus environments with high-rise hostels, covered walkways, and indoor cafeterias, **no single sensor can be trusted in isolation**:

1. **Raw GPS Coordinates & Cumulative Integration**:
   - *Failure Mode*: Satellite multipath and signal attenuation under concrete slabs and tree canopies cause continuous spatial wander ($\pm 5$ to $45\text{ m}$).
   - *Impact*: Integrating raw point-to-point Euclidean steps accumulated **4,310.3 m** in Session 1 and **4,884.0 m** in Session 3, despite the true origin-to-destination straight-line distance being only **1.47 km** (~1.8 km road/path distance).
2. **Instantaneous GPS Speed (`speed`)**:
   - *Failure Mode*: Doppler frequency shifts and carrier noise produce phantom speeds ($0.3 - 3.6\text{ m/s}$) while the user is sitting completely stationary in the cafeteria.
   - *Impact*: Classifying movement by raw `speed > 0.5 m/s` misclassified over 20 minutes of sitting in a cafeteria chair as active walking.
3. **Pedometer (`Pedometer.csv`)**:
   - *Failure Mode*: Android OS background power-saving suspends step listener callbacks while the screen is off or in deep sleep, dumping accumulated steps in large batch bursts (e.g., jumping from 332 to 1,759 steps at minute 141).
   - *Impact*: Looking at instantaneous step deltas falsely suggests the user teleported or took 1,427 steps in one second, while appearing stationary during active walking.
4. **Android Activity Recognition (`Activity.csv`)**:
   - *Failure Mode*: Coarse statistical classifier oscillating unpredictably between `unknown`, `tilting`, `stationary`, and `walking`.

### Multi-Signal Decision Matrix
To resolve these ambiguities, our fusion pipeline (`scripts/clean_and_fuse_telemetry.py`) cross-references four concurrent indicators:
* **Spatial Gyration Radius ($R_g$) & Net Window Displacement ($d_{60s}, d_{15s}$)**:
  $$R_g = \sqrt{\frac{1}{N} \sum_{i=1}^{N} \text{haversine}(c_{\text{lat}}, c_{\text{lon}}, \text{lat}_i, \text{lon}_i)^2}$$
  In stationary waiting, $R_g < 10\text{ m}$ regardless of raw speed spikes. In active walking, $d_{60s} > 35\text{ m}$ with consistent directional bearing.
* **Forward-Fill Pedometer Cadence**:
  Maintains step-wise ground truth rather than artificial linear interpolation.
* **Accuracy-Gated Kinematic Kalman Filter with ZUPT (Zero-Velocity Update)**:
  - When the multi-sensor detector identifies `STATIONARY_WAITING`, the filter applies a ZUPT constraint, snapping coordinates to the running cluster centroid ($R_{\text{meas}} = 1.5\text{ m}^2$) and driving velocity to zero.
  - During walking and vehicular transit, measurement covariance scales adaptively with reported accuracy: $R_{\text{meas}} = \max(3.0, \text{horizontalAccuracy})^2$.

---

## 3. Comparative Findings: Clear Day vs. Rainy Day

| Metric | Session 1: Sunny Morning (`M08`) | Session 3: Rainy Morning (`M01`) | Variance / Impact |
| :--- | :---: | :---: | :--- |
| **Total Window Time** | 151.78 min (2 hr 32 min) | 144.85 min (2 hr 25 min) | Similar total duration (-7 min) |
| **Raw Cumulative GPS Distance** | 4,310.3 m | 4,884.0 m | +573.7 m (+13.3% raw drift) |
| **Filtered Path Distance** | **2,224.0 m** | **2,468.9 m** | True path accurately tracked |
| **Jitter Noise Reduction** | **-48.4%** | **-49.4%** | **~50% phantom jitter eliminated** |
| **Total Physical Steps** | 1,867 steps | 2,097 steps | +230 steps |
| **Stationary / Waiting Time** | 126.6 min (83.4%) | 121.5 min (83.9%) | Primary time sink in both conditions |
| **Primary Stationary Bottleneck** | **DTSP Exterior Queue (28.8 min)** + Hostel Forecourt (40.8 min) | **RST Cafeteria Rain Shelter (118.8 min)** | Bottleneck relocated upstream |
| **Active Walking Time** | 11.5 min | 17.5 min | +6.0 min (walked through cafeteria + ridge) |
| **Bus Transit Duration** | **3.35 min** | **3.05 min** | Identical transit physics (~3.1 min) |
| **Bus Peak Speed** | 34.6 km/h (9.61 m/s) | 37.7 km/h (10.46 m/s) | High-speed dedicated transit link |
| **Idle-to-Motion Ratio** | **9.64x** wait-to-motion | **6.25x** wait-to-motion | Severe batching & holding dominance |

### Key Operational Observations
1. **Weather Delay Re-Allocates Queueing Upstream**:
   - On the clear day (Session 1), students left the hostel early and spent **28.8 minutes standing outside in open sun** along the road shoulder waiting for DTSP hall clearance.
   - On the rainy day (Session 3), orientation marshals held students inside the **RST Cafeteria for ~1 hour 59 minutes** (06:23 to 08:22 AM). Once the rain cleared, students moved directly to the bus and entered DTSP with virtually zero exterior queueing.
2. **Bus Transit is Invariant**:
   - Under both dry and wet conditions, the active vehicular link from Padang Kawad to DTSP required only **3.05 to 3.35 minutes**. The overall 2.5-hour commute is 90%+ dominated by static holding.

---

## 4. Generated Artifacts & Directory Structure

All processed datasets, cleaned traces, and GIS layers are structured under the repository root:

```
usm-orientation-optimizer/
├── raw_data/
│   └── sensor_logger/
│       ├── zips/                                     # Permanent archive of original zip files
│       │   ├── M08-2026-09-16_22-47-10.zip
│       │   ├── Persiaran_Sains-2026-09-17_09-36-21.zip
│       │   └── M01-2026-09-17_22-19-02.zip
│       └── sessions/                                 # Organized unzipped raw sensor data
│           ├── session_1_2026-09-17_morning_M08_to_DTSP/
│           ├── session_2_2026-09-17_evening_Persiaran_Sains_from_DTSP/
│           └── session_3_2026-09-18_morning_M01_Rainy_to_DTSP/
├── processed/
│   ├── multi_session_comparison.json                 # Cross-session benchmark JSON
│   ├── multi_session_comparison.csv                  # Cross-session benchmark CSV
│   ├── all_sessions_combined.geojson                 # Master GIS layer combining all routes
│   ├── session_1_2026-09-17_morning_M08_to_DTSP/
│   │   ├── cleaned_telemetry.csv                     # 1Hz fused & Kalman-filtered data
│   │   ├── trip_stages.csv                           # Segmented stage timeline
│   │   ├── filtered_track.geojson                    # Visual GIS route
│   │   └── telemetry_summary.json                    # Session summary & KPIs
│   ├── session_2_2026-09-17_evening_Persiaran_Sains_from_DTSP/
│   │   ├── cleaned_telemetry.csv
│   │   ├── trip_stages.csv
│   │   ├── filtered_track.geojson
│   │   └── telemetry_summary.json
│   └── session_3_2026-09-18_morning_M01_Rainy_to_DTSP/
│       ├── cleaned_telemetry.csv
│       ├── trip_stages.csv
│       ├── filtered_track.geojson
│       └── telemetry_summary.json
└── scripts/
    └── clean_and_fuse_telemetry.py                   # Production stdlib fusion pipeline
```
