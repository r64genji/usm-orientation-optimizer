# USM Orientation Simulator Replay Realism Report

This document reports on the redesign of the USM orientation operator dashboard replay (`operator_dashboard/`) and its web frontend (`operator_dashboard/web/`). It details the visual replay mechanics implemented and flags physical discrepancies and unrealistic assumptions identified between the simulation engine (`usm_sim/`) and actual campus operations.

---

## 1. Redesigned Components and Replay Capabilities

### A. Continuous Bus Fleet Loops & Empty Return Leg
- **Replay Continuity**: Reconstructed the end-to-end lifecycle for all 8 buses in the operational fleet (5 coach buses and 3 electric buses).
- **Empty Return Leg (`leg_transit_return`)**: Added reverse road waypoints along Persiaran Sains and Jalan Universiti connecting the DTSP alighting area (`[5.357215, 100.301437]`) back to the RST boarding berth (`[5.356012, 100.293748]`). Empty buses now follow the real roadway geometry rather than snapping or teleporting across campus.
- **Turnaround and Berthing Dynamics**: The replay explicitly animates:
  1. `idle`: Staged at RST boarding berths waiting for cohorts.
  2. `boarding`: Passenger intake through single usable door.
  3. `transit_loaded`: Forward transit along Persiaran Sains with passengers aboard.
  4. `alighting`: Drop-off at DTSP alighting area.
  5. `transit_empty_return`: Empty return trip back to RST.
  6. `turnaround`: 60-second operational queue reset / door turnaround at RST berths.

### B. Visual Differentiation: Coach vs. Electric Buses
- **Coach Buses (`coach_1` through `coach_5`)**:
  - Capacity: 80 students (40 seated, single front passenger door).
  - Visuals: Extended 32px chassis, deep navy blue (`#1E3A8A`) with USM amber roof accent (`#F59E0B`), front windshield, headlights, rear brake lights, left-side curb door indicator, and clear "COACH (80)" capacity badging.
- **Electric Buses (`electric_1` through `electric_3`)**:
  - Capacity: 40 students (28 seated, single front passenger door).
  - Visuals: Compact 22px chassis, eco-emerald green (`#047857`) with electric cyan roof trim (`#06B6D4`), electric cyan windshield, headlights, rear brake lights, left-side door indicator, and "⚡ EV (40)" badging.
- **Empty Return Status**: Buses on `leg_transit_return` have zero passengers inside and display an "EMPTY" status indicator while travelling westward back to RST.

### C. DTSP Alighting Docking Berths
- **Multi-Bus Docking**: DTSP drop-off occurs on a wide straight-line road / car park. Rather than stacking arriving buses at a single pixel, multiple buses docked simultaneously (up to 8 buses, 4 active berths) are rendered with realistic longitudinal berth offsets along the drop-off curb.
- **Immediate Passenger Flow**: Replay accurately shows students alighting directly and walking toward the 3-tier car park holding area or foyer entrances without artificial door checkpoints.

### D. Restu Cafe / Rain Shelter Holding & Priority Sequencing
- **Ground Truth Positioning**: Updated `restu_origin` and `rst_rain_shelter` coordinates to the verified Restu Cafe (M07) and rain shelter pavilion location (`[5.356461, 100.289265]`), replacing legacy dormitory coordinates (`[5.35728, 100.28981]`).
- **Sequenced Holding**: Tekun and Saujana depart first due to smaller headcounts. Restu students are held at Restu Cafe pavilion until `t = 2748s` (07:33:00) rather than appearing prematurely at the bus stop.

### E. Realistic Crowd Dispersion at Distinct Holding Locations
- **Restu Cafe Grounds (`rst_rain_shelter` / `restu_origin`)**: Sheltered pavilion grounds distribution.
- **Persiaran Sains Bus Queue (`rst_bus_wait`)**: Ordered linear shoulder queue along the Persiaran Sains road verge.
- **RST Boarding Berth (`rst_boarding_approach`)**: Stepped queue approach feeding into the active bus boarding berths.
- **3-Tier Car Park Waiting Area (`dtsp_exterior_gathering`)**: Realistic 3-tier terraced distribution dividing alightees across Lower, Middle, and Upper parking tiers.
- **Dataran Merah Shaded Pavilion (`dtsp_north_plaza`)**: Rectangular column and rank spacing under the covered pavilion for North walking cohorts (Cahaya Gemilang, Bakti Fajar).
- **Grass Field in Front of G28 Siswaniaga (`dtsp_south_plaza`)**: Organic lawn dispersion across the green field for South walking cohorts (Indah Kembara, Aman Damai, Fajar Harapan).
- **DTSP Main Hall Auditorium Seating (`dtsp_seating`)**: Tiered curved auditorium rows seating up to 3,000 students.
- **Bangunan G03 Overflow Seating (`g03_seating`)**: Tiered lecture theatre seating (DK G/H) seating up to 600 students.

---

## 2. Unrealistic Simulation Parameters and Physical Discrepancies

### 1. Geodesic Distance vs. Road Curvature for Bus Return
- **Observation**: In `usm_sim/scenarios.py`, vehicle return travel duration (`return_travel_s`) is computed via geodesic straight-line calculation between `rst_boarding_approach` and `dtsp_alighting_area`:
  $$\text{Geodesic Distance} \approx 1,167\text{ m}$$
- **Discrepancy**: The actual roadway distance along Persiaran Sains and Jalan Universiti is approximately $1,350\text{ m}$ (a 15.7% increase).
- **Impact**: Calculating return transit at $20\text{ km/h}$ over $1,167\text{ m}$ yields $210\text{ s}$ ($3.5\text{ min}$). Over the actual $1,350\text{ m}$ route, return transit takes at least $243\text{ s}$ ($4.05\text{ min}$) without accounting for roundabouts, speed humps, and campus traffic. The simulation is optimistic on bus fleet turnaround times by roughly $30\text{--}40\text{ seconds}$ per round trip.

### 2. Single-Door Boarding Bottleneck vs. Multi-Berth PPSL Staffing
- **Observation**: Both coach (80 capacity) and electric (40 capacity) buses are configured with `usable_doors: 1` and `boarding_s_per_passenger_per_door: 2.0`.
- **Discrepancy**: 
  - Boarding a full 80-passenger coach through one narrow door requires:
    $$\text{Dwell Time} = 5\text{ s (setup)} + 80 \times 2.0\text{ s} = 165\text{ s } (2\text{ min } 45\text{ s})$$
  - If only 1 boarding berth is staffed/active, dispatching the 5 coaches and 3 electric buses in the initial wave requires over $18\text{ minutes}$ of vehicle dwell time at the single berth, creating a severe bottleneck at `rst_boarding_approach`.
  - In real operations, activating 2 to 4 simultaneous boarding berths (requiring 2 PPSL staff members per active berth) is mandatory to prevent massive spillback along the Persiaran Sains road shoulder.

### 3. Asymmetry Between Boarding and Alighting Times
- **Observation**: The simulation specifies `boarding_s_per_passenger_per_door: 2.0` vs `alighting_s_per_passenger_per_door: 0.4`.
- **Discrepancy**: Alighting an 80-passenger coach takes only $34\text{ seconds}$ ($2\text{ s setup} + 80 \times 0.4\text{ s}$), which is nearly $5\times$ faster than boarding.
- **Impact**: Buses clear the DTSP drop-off area almost immediately, but spend the vast majority of their cycle time waiting in queue or dwelling at RST boarding. Consequently, congestion occurs almost exclusively at RST origin, while the 4-berth DTSP drop-off area remains largely underutilized.

### 4. Zero-Friction Straight-Line Road Assumptions at DTSP
- **Observation**: The simulation permits multiple buses to dock simultaneously at DTSP with zero queueing delay once dropoff berths are free, and models student exit as instantaneous batch service.
- **Physical Reality**: Arriving buses must decelerate, pull into designated parking bays, allow luggage/baggage retrieval (if any), and safely merge back into Persiaran Sains traffic. While no ticket or security checks occur at DTSP, pedestrian crossing conflicts between alightees and returning buses on Jalan Universiti present a real-world friction point not represented in the engine physics.

### 5. Walking Hostel Release Synchronization
- **Observation**: In `whole_campus_full_cohort_case`, all 5 walking hostels (Indah Kembara, Aman Damai, Bakti Fajar, Cahaya Gemilang, Fajar Harapan) release simultaneously at $t=0$ ($06:00:00$).
- **Discrepancy**: Simultaneous release dumps over 2,500 walking students onto campus pathways within minutes. Cahaya Gemilang and Bakti Fajar arrive at Dataran Merah (`dtsp_north_plaza`) and Door A long before DTSP doors open, forcing substantial standing hold times (up to $45\text{--}60\text{ minutes}$) in outdoor/sheltered pavilions.
- **Recommendation**: Staggering walking hostel departures based on route distance (e.g. Aman Damai and Fajar Harapan earlier, Cahaya Gemilang later) would significantly smooth arrival peaks at DTSP.

---

## 3. Summary of Verification Results

- **Python Dashboard Test Suite**:
  - Command: `pytest tests/dashboard`
  - Result: **69 passed** cleanly.
  - Tests verified: `test_bus_fleet_loop_replay_and_holding_locations`, `test_venue_allocation_and_g03_replay_trajectories`, `test_geometry`, `test_projections`, `test_api`, `test_contracts`, `test_inputs`, `test_mobile_responsiveness`, `test_runner`.
- **Frontend Production Build**:
  - Command: `npm --prefix operator_dashboard/web run build`
  - Result: **Built successfully** with Vite (0 errors, 0 type errors).
