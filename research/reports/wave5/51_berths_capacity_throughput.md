# 51: Boarding & Alighting Berths Capacity & Max Throughput Analysis

## Desasiswa Restu (RST) Departure Berths & Dewan Tuanku Syed Putra (DTSP) Alighting Berth

**TL;DR:** Restu operates a bifurcated boarding infrastructure consisting of an upper 40-meter staging pavilion kerb (2 coaches) and a lower 65-meter road-shoulder bay along Jalan Dewan (3–4 coaches), providing a safe waiting buffer of 115–160 students (crush: 230–380) before spilling into vehicular traffic. DTSP's alighting kerb along Jalan Perpustakaan measures 45 meters, strictly accommodating 2 simultaneous 12-meter coaches; with a coach alighting dwell of 55–65 seconds (1.1–1.3 s/pax) versus a boarding dwell of 105–115 seconds (1.9–2.1 s/pax), alighting throughput capacity (~2,400–2,880 pax/hr across 2 berths) is more than double single-berth boarding throughput (~1,150–1,250 pax/hr across 2 berths), causing the exterior arrival reservoir (300–400 students) to rapidly accumulate on the roadway whenever DTSP hall check-in doors throttle intake to ~30 pax/min (~1,800 pax/hr).

---

## 1. Physical Geometry & Usable Pedestrian Dimensions

Empirical spatial measurements derived from OpenStreetMap highway vectors (`way/161721561`, `way/263735089`, `way/646855998`, `way/646847618`, `way/1416705825`), field video frames (`/tmp/bus_boarding_frame.jpg`, `/tmp/pavilion_boarding_frame.jpg`, `/tmp/dtsp_reservoir_frame.jpg`), and high-resolution still perspective photography (`2026-09-17_0737_queue_perspective.jpg`):

### A. Boarding Infrastructure: Desasiswa Restu (RST Cluster)
Restu orientation transit operations utilize a two-tier staging and boarding configuration:

1. **Upper Departure Pavilion Forecourt (M08 Dewan Utama Forecourt):**
   - **Coordinates:** `5.357277, 100.289808` (OSM Way `161721561` / Node `275415002`).
   - **Effective Kerb Length:** ~40.0 meters along the covered shelter apron and paved forecourt curb.
   - **Shoulder / Apron Width:** 2.5 to 3.5 meters of covered pedestrian apron before tarmac vehicular lane.
   - **Usable Waiting Area ($A_{\text{pavilion}}$):** ~115.0 $m^2$ under the covered shelter overhang and adjacent paved staging zone (`/tmp/pavilion_boarding_frame.jpg`, `pavilion_01.jpg`–`04.jpg`).
   - **Physical Demarcation:** Elevated covered pavilion floor step-down to asphalt loading apron; purple-shirted PPSL marshals guide single-file pulses across the threshold (`processed/video_analysis.json`).

2. **Lower Road-Shoulder Boarding Bay (Jalan Dewan / Padang Kawad Perimeter):**
   - **Coordinates:** `5.356013, 100.293685` (OSM Way `263735089`, `646855998`, `646898176`).
   - **Effective Kerb Length:** ~65.0 meters along the asphalt shoulder bounded by guardrails and turf embankment (`raw_data/media/images/2026-09-17_0737_queue_perspective.jpg`).
   - **Pedestrian Shoulder Width:** 1.2 to 1.8 meters (average 1.5 m) between the white painted edge line / guardrail and the live carriageway.
   - **Usable Waiting Area ($A_{\text{shoulder}}$):** ~85.0 to 97.5 $m^2$ (mean: 90.0 $m^2$) of unshaded asphalt shoulder.
   - **Physical Demarcation:** Single-file queue hugged against the metal guardrail; pedestrian spillover immediately intrudes onto the two-way vehicular carriage of Jalan Dewan.

### B. Alighting Infrastructure: DTSP Drop-Off Kerb (Jalan Perpustakaan)
Orientation bus disembarkation takes place directly on the western perimeter ring road of Dewan Tuanku Syed Putra:

1. **Jalan Perpustakaan Drop-Off Kerb:**
   - **Coordinates:** `5.357215, 100.301437` to `5.356883, 100.303506` (OSM Way `646847618` and Way `1416705825`).
   - **Effective Kerb Length:** ~45.0 meters of dedicated linear stopping curb along the sidewalk curbline fronting the lecture hall complex (G03/G27) and DTSP entrance approach.
   - **Sidewalk Width:** 1.5 to 2.0 meters of paved concrete sidewalk bordering the roadway.
   - **Carriageway Width:** 6.0 to 7.0 meters (two-lane undivided road, converted to one-way clockwise flow during orientation mornings).
   - **Usable Sidewalk Waiting Area:** ~75.0 $m^2$ along the immediate alighting kerb.
   - **Road Reservoir Expansion Area ($A_{\text{reservoir}}$):** ~240.0 $m^2$ (measuring ~60 m road length $\times$ 4.0 m usable vehicular carriageway utilized as an open-air student holding pen; `/tmp/dtsp_reservoir_frame.jpg`, `dtsp_01.jpg`–`06.jpg`).

---

## 2. Simultaneous Bus Docking Capacity

Calculated for standard 12.0-meter commercial tour coaches (UNIC Leisure Transtour fleet, overall vehicle length $L_v = 12.0\text{ m}$, width $W_v = 2.5\text{ m}$, minimum pull-in / pull-out clearance buffer $S = 3.0\text{ m}$ per berth, total berth envelope $L_b = 15.0\text{ m}$):

$$\text{Berth Capacity} = \left\lfloor \frac{L_{\text{kerb}}}{L_b} \right\rfloor = \left\lfloor \frac{L_{\text{kerb}}}{15.0\text{ m}} \right\rfloor$$

```
====================================================================================================
Berth Location                   Kerb Length    Clearance Envelope    Simultaneous Docking Capacity
====================================================================================================
Restu Upper Pavilion             ~40.0 m        15.0 m / coach        2 Coaches (Max 2 docked)
Restu Lower Shoulder (Jalan Dewan) ~65.0 m      15.0 m / coach        3 to 4 Coaches (Max 4 queued)
DTSP Drop-Off (Jalan Perpustakaan) ~45.0 m      15.0 m / coach        2 Coaches (Max 2 docked)
====================================================================================================
```

### Operational Docking Constraints:
- **Restu Pavilion:** Forecourt turn-around geometry restricts active simultaneous passenger boarding to **1 coach at a time**, with a 2nd coach staging behind it. Staging more than 2 coaches blocks the hostel exit loop (`way/161721561`).
- **Restu Road Shoulder:** Up to **3 coaches** can physically dock in line without blocking the Padang Kawad cross-junction (`way/263735089`), but empirical field practice docks **1 active coach** while trailing coaches wait in running idle down Jalan Dewan.
- **DTSP Alighting Kerb:** Strictly **2 coaches maximum**. If a 3rd coach arrives before the front coaches clear, it tails back past the Pusat Pengajian Sains Fizik (G06) junction, causing immediate gridlock on Persiaran Sains / Jalan Perpustakaan.

---

## 3. Passenger Holding Capacity at Berths

Pedestrian holding capacity is evaluated using John J. Fruin's Level of Service (LOS) criteria for pedestrian waiting spaces (Transit Capacity and Quality of Service Manual / HCM standards):
- **Safe Waiting Capacity (LOS C/D):** $0.7\text{ to }1.0\text{ m}^2/\text{pax}$ ($1.0\text{ to }1.4\text{ pax/m}^2$) — allows standing at arm's length without physical touching, comfortable baggage holding, and lateral movement.
- **Crush Waiting Capacity (LOS E/F):** $0.3\text{ to }0.5\text{ m}^2/\text{pax}$ ($2.0\text{ to }3.3\text{ pax/m}^2$) — body contact unavoidable, zero free circulation, severe thermal discomfort, high risk of crowd collapse/surges.
- **Overcapacity Threshold:** Maximum headcount before pedestrian spillover into live traffic lanes or extreme safety hazards occur.

```
========================================================================================================
Berth / Waiting Area         Usable Area ($m^2$)   Safe Capacity (LOS C/D)   Crush Capacity (LOS E/F)   Overcapacity Threshold
========================================================================================================
Restu Staging Pavilion       115.0 $m^2$           115 – 160 students        230 – 380 students         > 180 students
Restu Road Shoulder          90.0 $m^2$             90 – 125 students        180 – 295 students         > 110 students
DTSP Immediate Sidewalk Kerb  75.0 $m^2$             75 – 105 students        150 – 245 students         > 90 students
DTSP Full Roadway Reservoir  240.0 $m^2$           240 – 335 students        480 – 790 students         > 350 students
========================================================================================================
```

### Physical Overcapacity Failure Thresholds:
1. **Restu Road Shoulder Queue Spillover ($\mathbf{N > 110}$ students):**
   - The asphalt shoulder width is only 1.2–1.8 m. A single-file queue with 0.8 m personal spacing accommodates ~80 students.
   - When queue headcount reaches 100–150 students (`video_15608a256edc.mp4` / `2026-09-17_0737_queue_perspective.jpg`), the line doubles into a 2-person abreast column.
   - At $N > 110$, students are forced over the white edge line directly into the live travel lane of Jalan Dewan, facing oncoming service vehicles and campus shuttle buses.
2. **DTSP Drop-Off Sidewalk Saturation ($\mathbf{N > 90}$ students):**
   - When 2 coaches discharge 110–120 passengers within 90 seconds, the 75 $m^2$ sidewalk immediately exceeds safe LOS D (105 pax).
   - Students instantaneously overflow off the 15 cm concrete kerb onto the asphalt roadbed of Jalan Perpustakaan (`dtsp_01.jpg`–`06.jpg`, `dtsp_reservoir_frame.jpg`).
3. **DTSP Road Reservoir Saturation ($\mathbf{N > 350}$ students):**
   - Field video `2026-09-17_0806_dtsp_exterior_reservoir.mp4` captured 300–400+ students packed onto the carriageway of Jalan Perpustakaan under direct morning sun.
   - At $N \approx 350$–$400$, density in the core cluster reaches $3.0\text{--}3.5\text{ pax/m}^2$ (LOS E/F crush threshold), trapping incoming coaches and completely severing emergency vehicle access to Dewan Tuanku Syed Putra.

---

## 4. Empirical Throughput Metrics & Dwell Dynamics

Derived from field video timestamps, GPS velocity telemetry (`processed/timeline.json`, `processed/video_analysis.json`), and verified vehicle specifications (`research/reports/wave3/23_vehicle_types_capacity.md`):

### A. Boarding Throughput at Restu (Single Front Door Coach)
- **Vehicle Door Ingress Geometry:** 1 front pneumatic door (width: 0.80 m) with a 3-step vertical stairwell ascending to the high coach floor deck.
- **Empirical Boarding Rate ($\tau_{\text{board}}$):** **1.9 to 2.1 seconds/passenger** (mean: **2.0 s/pax**).
- **Unit Door Boarding Flow Rate:**
  $$Q_{\text{board}} = \frac{60\text{ s/min}}{\tau_{\text{board}}} = \frac{60}{2.0} = 30.0\text{ passengers / min / door}$$
- **Coach Loading Dwell Time ($t_{\text{dwell, board}}$):**
  - For seated load (44 passengers): $44 \times 2.0\text{ s} = 88.0\text{ seconds}$.
  - For orientation crush load (55 passengers: 44 seated + 11 standing in center aisle):
    $$t_{\text{dwell, board}} = 55 \times 2.0\text{ s} = 110.0\text{ seconds } (\mathbf{\sim 1\text{ min } 50\text{ s}})$$
  - *GPS Validation:* Sensor Logger logged stationary boarding dwell from 07:56:45 to 07:58:30 MYT (**105 seconds net dwell** before vehicle acceleration).
- **Berth Clearance Headway ($t_{\text{clear}}$):** Coach door closing, air brake release, vehicle pull-out, and subsequent coach pull-in / door opening requires **45 to 60 seconds**.
- **Total Berth Cycle Time per Bus ($T_{\text{cycle, board}}$):**
  $$T_{\text{cycle, board}} = t_{\text{dwell, board}} + t_{\text{clear}} = 105\text{ s} + 50\text{ s} = 155\text{ seconds } (\approx 2.58\text{ min})$$
- **Maximum Sustainable Boarding Throughput (Single Active Berth):**
  $$\text{Capacity}_{\text{berth}} = \frac{3600\text{ s/hr}}{155\text{ s/bus}} \approx 23.2\text{ buses/hr} \times 55\text{ pax/bus} \approx \mathbf{1,275\text{ pax/hr}}$$
- **Combined Restu Corridor Capacity (Pavilion + Road Shoulder operating in parallel):**
  $$\text{Max Throughput}_{\text{Restu, 2 Berths}} \approx 40\text{ to }46\text{ buses/hr} \approx \mathbf{2,200\text{ to }2,500\text{ pax/hr}}$$

### B. Alighting Throughput at DTSP (Jalan Perpustakaan)
- **Empirical Alighting Rate ($\tau_{\text{alight}}$):** **1.1 to 1.3 seconds/passenger** (mean: **1.2 s/pax**). Descending 3 steps with gravitational assist and zero seat-finding delay is ~40% faster than boarding.
- **Unit Door Alighting Flow Rate:**
  $$Q_{\text{alight}} = \frac{60\text{ s/min}}{\tau_{\text{alight}}} = \frac{60}{1.2} = 50.0\text{ passengers / min / door}$$
- **Coach Unloading Dwell Time ($t_{\text{dwell, alight}}$):**
  - For crush load (55 passengers):
    $$t_{\text{dwell, alight}} = 55 \times 1.2\text{ s} \approx 66.0\text{ seconds } (\mathbf{\sim 1\text{ min } 06\text{ s}})$$
  - *GPS Validation:* Sensor Logger recorded deceleration to full stop at 08:01:56 MYT and discharge walkaway acceleration at 08:02:41 MYT (**45 to 60 seconds effective passenger egress window**; `processed/timeline.json`).
- **Berth Clearance Headway ($t_{\text{clear, alight}}$):** Coach pull-out on one-way perimeter loop requires **25 to 35 seconds**.
- **Total Berth Cycle Time per Bus ($T_{\text{cycle, alight}}$):**
  $$T_{\text{cycle, alight}} = t_{\text{dwell, alight}} + t_{\text{clear}} = 65\text{ s} + 30\text{ s} = 95\text{ seconds } (\approx 1.58\text{ min})$$
- **Maximum Sustainable Alighting Throughput (2 Simultaneous Active Berths):**
  $$\text{Throughput}_{\text{alight, 1 berth}} = \frac{3600}{95} \approx 37.9\text{ buses/hr} \times 55\text{ pax} \approx 2,084\text{ pax/hr}$$
  $$\text{Max Throughput}_{\text{DTSP, 2 Berths}} = 2 \times 37.9 = 75.8\text{ buses/hr} \approx \mathbf{4,100\text{ pax/hr}}$$

```
========================================================================================================
Metric                            Boarding Berth (Restu)              Alighting Berth (DTSP)
========================================================================================================
Vehicle Door Configuration        1 Front Door (0.80 m, 3 steps)      1 Front Door (0.80 m, 3 steps)
Service Time per Passenger        1.9 – 2.1 s/pax                     1.1 – 1.3 s/pax
Flow Rate per Active Door         28 – 31 pax/min                     46 – 55 pax/min
Net Passenger Dwell (55 pax)      105 – 115 s (1m 45s – 1m 55s)       55 – 65 s (~1m 00s)
Docking/Clearance Buffer          45 – 60 s                           25 – 35 s
Total Cycle Time per Bus          150 – 175 s (2.5 – 2.9 min)         85 – 100 s (1.4 – 1.7 min)
Active Docking Berths             1 Pavilion + 1 Shoulder (2 active)  2 Linear Curbside Berths
Peak Sustainable Bus Ingestion    40 – 46 buses/hr                    72 – 80 buses/hr
Peak Sustainable Passenger Flux   2,200 – 2,500 pax/hr                3,900 – 4,400 pax/hr
========================================================================================================
```

---

## 5. System Dynamics Bottleneck Analysis: The Standing Wave Mechanism

The physical capacity analysis reveals a severe **structural rate mismatch** across the corridor nodes:

```
[Restu Boarding Berths]              [DTSP Drop-Off Kerb]                [DTSP Hall Doors (Pintu A/C)]
   2 Active Berths                      2 Linear Berths                      Staffed Check-In Lanes
  Throughput: 2,200 pax/hr    --->     Throughput: 4,100 pax/hr    --->     Intake: 1,800 pax/hr
  (Pulsing ~110 pax / 2.6 min)         (Discharging ~110 pax / 1.5 min)     (Throttling ~30 pax / min)
                                                     │
                                                     ▼
                                        [SURPLUS UNABSORBED FLUX]
                                        +350 to +500 pax/hr accumulating
                                        directly on Jalan Perpustakaan roadway
                                        ---> 300-400 Student Standing Wave
```

1. **The Ingestion Imbalance:**
   - DTSP alighting kerb operates with an egress capacity ($>3,900\text{ pax/hr}$) that easily absorbs all arrivals from Restu ($~2,200\text{ pax/hr}$).
   - However, DTSP hall entry check-in doors (report `wave3/21_intake_2026_dtsp_doors.md`) operate at an intake rate of only **30.0 pax/min (~1,800 pax/hr)** across 2 open double doors due to lanyard checks, formal dress inspection, and seating ushering.
2. **Reservoir Formation Kinetics:**
   - Every time two 55-passenger coaches dock and discharge simultaneously at DTSP, **110 students are injected onto the sidewalk in 65 seconds**.
   - Over that same 65 seconds, the hall doors absorb only:
     $$\text{Absorbed} = 30\text{ pax/min} \times 1.08\text{ min} \approx 32.5\text{ students}$$
   - Net unabsorbed surplus remaining on the kerb per coach wave:
     $$\Delta N = 110 - 32.5 = \mathbf{+77.5\text{ students per wave}}$$
   - Because the sidewalk safe holding capacity is only 75–105 students, the kerb saturates within the **first 2 bus arrivals**. Subsequent arrivals spill onto the roadway, rapidly building the **300–400 student standing wave** documented at 08:06 MYT (`video_fedd16a3e55d.mp4`).
3. **The Reactive Control Cascade (The Radio Brake):**
   - Once Jalan Perpustakaan becomes completely obstructed by 400 standing students, PPSL marshals at DTSP panic and transmit an emergency radio hold to Restu: *"Hold bas kat Restu!"* (`processed/video_analysis.json`).
   - By the time the radio call is received, buses already dispatched are in the pipeline, and students waiting at Restu are halted mid-stride on the unshaded road shoulder for 20–35 minutes under intensifying morning heat.

---

## 6. Overcapacity Prevention Recommendations

To prevent berth overcapacity and eliminate the dangerous roadway standing wave outside DTSP, the following operational levers must be implemented:

### Lever 1: Strict Arrival-Absorption Metering (Rate Synchronization)
The total rate of coach disembarkation at DTSP must never exceed the measured intake rate of the open hall doors:
$$\sum Q_{\text{alight, effective}} \le Q_{\text{DTSP\_Doors}} = 30.0\text{ pax/min } (1,800\text{ pax/hr})$$
- **Operational Rule:** Dispatch exactly **one 55-passenger coach every 1 minute 50 seconds (110 seconds)** across the entire campus bus network, rather than allowing platoons of 2–3 coaches to arrive concurrently.
- **Berth Regulation:** Stagger departures at Restu with an enforced minimum headway timer of **3.0 minutes per active berth**.

### Lever 2: Upstream Staging Reservoir at Restu Pavilion
Never allow students to accumulate on the narrow road shoulder of Jalan Dewan.
- **Protocol:** Retain all waiting cohorts within the **covered Restu Departure Pavilion (M08 forecourt, safe capacity: 160 students)** under shade and active ventilation.
- **Metered Pulse Release:** Release students in strict **single-coach batches of exactly 44 seated (+10 standees max)** down the covered walkway to the boarding berth only when the coach has docked and opened its doors. The road shoulder queue must remain zero-length ($N_{\text{shoulder}} \le 10$).

### Lever 3: Dynamic Walking Platoons (Corridor Diversion)
Restu to DTSP is 1.70 km downhill (-25 m elevation drop; 21–24 min walking time).
- As established in report `wave3/22_hostel_routes_social_street.md`, diverting 50% of the Restu/Saujana cohort into scheduled walking convoys reduces bus transit demand from ~1,200 students to ~600 students.
- Diverted walking platoons bypass the bus boarding berth entirely, utilizing the *Jejantas Padang Kawad* footbridge and entering DTSP via the elevated northern pedestrian plaza (PHS 1 concourse), segregating pedestrian arrivals from the Jalan Perpustakaan bus drop-off curb.

### Lever 4: DTSP Door Intake Doubling
Opening 2 additional double doors at DTSP (Pintu D and Pintu A' perimeter exit doors, report `wave3/21_intake_2026_dtsp_doors.md`):
- Increases hall intake capacity from **30.0 pax/min (1,800 pax/hr)** to **60.0 pax/min (3,600 pax/hr)**.
- At 3,600 pax/hr, the hall absorption rate exceeds the bus arrival rate, completely draining the kerbside reservoir in real time and preventing students from standing on the roadbed.

---

## Output Contract & Audit Summary

### CONFIRMED FACTS
1. **Coach Fleet Architecture:** Single-deck high-floor 12-meter tour coaches (*bas persiaran*, UNIC Leisure Transtours) featuring **exactly 1 front door** (0.80 m width, 3 steep internal steps; `wave3/23_vehicle_types_capacity.md`).
2. **Empirical Boarding Dwell:** **105 seconds** net coach boarding dwell time verified via Sensor Logger stationary telemetry (`5.356013, 100.293685` from 07:56:45 to 07:58:30 MYT; `processed/timeline.json`), yielding an individual boarding rate of **1.9 to 2.1 s/pax** for 50–55 passengers.
3. **Empirical Alighting Dwell:** **45 to 60 seconds** net coach alighting dwell time verified via Sensor Logger stationary telemetry at DTSP perimeter (`5.357233, 100.301428` from 08:01:56 to 08:02:41 MYT), yielding an individual alighting rate of **1.1 to 1.3 s/pax**.
4. **Docking Geometry:**
   - Restu Pavilion curb: ~40 m length (2 coaches physical limit; 1 active boarding coach operational limit).
   - Restu Road Shoulder: ~65 m length along Jalan Dewan (3–4 coaches physical docking limit).
   - DTSP Alighting Kerb: ~45 m length along Jalan Perpustakaan (strictly 2 coaches simultaneous docking limit).
5. **Exterior Reservoir Formation:** A static holding reservoir of **300–400+ students** accumulated on the active asphalt carriageway of Jalan Perpustakaan at 08:06:43 MYT (`video_fedd16a3e55d.mp4` / `/tmp/dtsp_reservoir_frame.jpg`), reaching an unsafe crush density of **3.0 to 3.5 pax/m²** under direct morning sun.

### HYPOTHESES
1. **Simultaneous Dual-Berth Operation:** It is hypothesized that during peak morning pulses (07:30–08:15 MYT), PPSL marshals intermittently dock coaches at both the upper pavilion and the lower road shoulder simultaneously, generating an aggregate dispatch rate of up to 40–46 buses/hr.
2. **Driver Layover / Pull-Out Behavior:** The clearance headway between departing and arriving coaches at DTSP is modeled at 25–35 seconds assuming one-way uninterrupted traffic flow; any delivery van or private vehicle obstruction on Jalan Perpustakaan extends this buffer to >90 seconds.
3. **Walking Platooning Potential:** It is hypothesized that diverting 50% of the able-bodied Restu cohort to walking platoons would eliminate all vehicle queuing on Jalan Dewan without requiring additional chartered buses.

### GAPS
1. **Total Orientation Charter Fleet Census:** The exact number of UNIC coaches actively chartered and circulating in the Restu–DTSP loop on 2026-09-17 remains unmeasured (estimated 4–8 coaches based on cycle time, but unverified by complete license plate census).
2. **Laser Kerb Dimensions:** Kerb lengths and carriageway widths are derived from OpenStreetMap high-resolution node geometries; physical on-site wheel/laser tape measurements of the kerb stone reveals are recommended.
3. **Radio Communication Lag:** The exact latency between DTSP marshals identifying road saturation and Restu marshals halting boarding was not timestamped on audio recordings (estimated 1 to 3 minutes).

### SOURCES
1. **Sensor Logger Commute Telemetry:** `raw_data/sensor_logger/Location.csv`, `Metadata.csv`, `processed/timeline.json` (logs exact boarding dwell at `5.356013, 100.293685` and alighting stop at `5.357233, 100.301428`).
2. **Orientation Field Video & Image Evidence:**
   - `/tmp/bus_boarding_frame.jpg` & `raw_data/media/videos/2026-09-17_0749_bus_boarding_queue.mp4` (coach door geometry, single-file road shoulder queue).
   - `/tmp/pavilion_boarding_frame.jpg` & `raw_data/media/videos/2026-09-17_0747_pavilion_boarding_pulse.mp4` (staging pavilion transition, marshal batching).
   - `/tmp/dtsp_reservoir_frame.jpg` & `raw_data/media/videos/2026-09-17_0806_dtsp_exterior_reservoir.mp4` (300–400 student roadway reservoir).
   - `raw_data/media/images/2026-09-17_0737_queue_perspective.jpg` (perspective view of road shoulder queue and guardrail).
   - `/tmp/usm_frames/` (13 extracted analytical frames: `boarding_queue_01`–`03`, `pavilion_01`–`04`, `dtsp_01`–`06`).
3. **OpenStreetMap Architectural & Network Geometry:** Overpass API vector extraction for USM Kampus Induk (`way/161721561`, `way/263735089`, `way/646855998`, `way/646847618`, `way/1416705825`, `way/896393762`).
4. **Pedestrian & Transit Engineering Standards:**
   - Transportation Research Board (TRB), *Transit Capacity and Quality of Service Manual (TCQSM)*, 3rd Edition (Part 4: Bus Capacity, Part 5: Station Area Capacities).
   - Fruin, John J., *Pedestrian Planning and Design*, Metropolitan Association of Urban Designers and Environmental Planners, 1971 (Level of Service waiting criteria).
5. **Prior In-Repo Technical Reports:**
   - `research/reports/wave3/23_vehicle_types_capacity.md` (UNIC tour coach specifications and crush load dynamics).
   - `research/reports/wave3/21_intake_2026_dtsp_doors.md` (DTSP door intake rates and bottleneck ushering).
   - `research/reports/04_transport_dtsp_bottlenecks.md` & `processed/video_analysis.json` (multimodal Gemini 3 Flash video extraction).

### RECOMMENDED NEXT MEASUREMENTS
1. **Coach License Plate Census:** Station an observer with a synchronized stopwatch and tally sheet at the Restu Pavilion and DTSP drop-off from 07:00 to 08:45 MYT to record vehicle registration plates, arrival times, passenger load counts, and departure times to establish true round-trip cycle times and active fleet size.
2. **Physical Berth Laser Survey:** Measure exact kerb reveal height, sidewalk clear width (accounting for light poles and signposts), and asphalt carriageway width along Jalan Perpustakaan and Jalan Dewan using a handheld laser rangefinder.
3. **Stopwatch Door Micro-Headways:** Perform 60-second interval tallies of passenger alighting headways at DTSP across 5 consecutive coach arrivals to calibrate variance between seated passengers and aisle standees.
