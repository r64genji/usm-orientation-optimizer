# Report 17: Destination Occupancy Signals, Flow Control Failure Modes, and Discrete Event Measurement Specification

**Date:** 2026-09-17  
**Context:** Universiti Sains Malaysia (USM Induk) — Minggu Siswa Lestari (MSL) mass movement from RST (Restu-Saujana-Tekun) hostels to Dewan Tuanku Syed Putra (DTSP)  
**Deliverable Path:** `research/reports/wave2/17_signals_failure_modes.md`

---

## 1. TL;DR & Operational Verdict

**Verdict:** Upstream release must be controlled by a pull-signal ("ready for $N$") rather than downstream panic pushes ("hold after the road is full"). A reactive hold transmitted over radio incurs a 45–90 second human-and-system propagation lag; with an 8-minute coach loop, reactive stops guarantee overfilling the unshaded foyer and kerb. By enforcing a strict token-bucket radio brevity protocol (`"DTSP READY [BATCH_ID]"` / `"RESTU DISPATCHING [BATCH_ID]"`) combined with 60-second mechanical clicker logging at five fixed stations, PPSL can eliminate road-shoulder queuing, prevent hall starvation, and log the exact timestamps needed to calibrate a Discrete Event Simulation (DES).

---

## 2. Occupancy/Queue Signal Specification (Radio & WhatsApp Only)

### 2.1 The Pull Signal Architecture vs Reactive Push
In current operations, Restu dispatches coaches continuously until DTSP marshals see the road exterior packing, prompt a panicked radio message ("Stop sending buses!"), by which time 2 to 3 coaches (88–132 students) are already in transit or boarding.

To maintain zero road-shoulder queuing outside DTSP, the control policy must invert from **Push** (origin sends when bus is full) to **Pull** (destination requests a specific batch when buffer capacity is guaranteed).

```
[Restu Shaded Holding: Cafeteria / Foyer]
       │
       ▼ (Controlled Gate: Clicker 1)
[Boarding Bay: 1 Coach = 44 Pax]
       │
       ▼ (Transit: Coach moving ~3-5 min)
[DTSP Kerb Unloading: Clicker 3]
       │
       ▼ (Walking Channel: Clicker 4)
[DTSP Foyer Buffer: Capacity C_foyer]
       │
       ▼ (Main Hall Doors: Clicker 5)
[Hall Seating: 3,000+ capacity]
```

### 2.2 Standard Radio Brevity Protocol
Based on standard event transit and crowd control protocols (cf. *Tickts Event Radio Guide*, *ALSSA Multi-Service Brevity Codes*, and school bus dispatching standards):

*   **PULL / READY (Destination to Origin):**
    *   *Phrase:* `"RESTU CONTROL, THIS IS DTSP CONTROL. READY FOR [BATCH_ID], 44 SEATS. OVER."`
    *   *Meaning:* Destination has absorbed previous cohort; kerb and foyer are clear to accept exactly one coach.
*   **DISPATCH ACK (Origin to Destination):**
    *   *Phrase:* `"DTSP CONTROL, RESTU COPIED. DISPATCHING [BATCH_ID], 44 PAX, COACH [BUS_NUMBER]. OUT."`
    *   *Meaning:* Coach has loaded from shaded holding and departed origin kerb.
*   **HOLD / FREEZE (Emergency / Capacity Stoppage):**
    *   *Phrase:* `"ALL STATIONS, DTSP CONTROL: HOLD DISPATCH, HOLD DISPATCH. REASON: FOYER SURGE. STAND BY."`
    *   *Meaning:* Absolute halt on any new departures from RST hostels. Buses currently rolling proceed to kerb; upstream holding keeps students seated in shade.
*   **RELEASE / RESUME:**
    *   *Phrase:* `"RESTU CONTROL, DTSP CONTROL: CANCEL HOLD. RESUME METERING. READY FOR [BATCH_ID]. OVER."`
*   **READ-BACK MANDATE:**
    *   Every numerical instruction or batch dispatch MUST be acknowledged by verbatim read-back before the bus driver is given the green flag.

### 2.3 Typical Human Radio Lag and Occupancy Counting Error
*   **Radio & Human Relay Latency:**
    *   *Transmission Latency (Mouth-to-Ear / PTT setup):* Analogue PMR/UHF radios have near-instant mouth-to-ear latency (<50 ms), whereas Push-To-Talk over Cellular (PoC) or digital trunking adds 300–800 ms (NIST IR 8206: *Mission Critical Voice Quality of Experience*).
    *   *Human Verification Lag:* The real bottleneck is human situational awareness and airwave contention. In crowd management events, the latency between a threshold breach (foyer filling up) and the verbal transmission being heard and acted upon at the dispatch gate is **45 to 90 seconds** (Tickts, 2024; NDMA Crowd Management Guidelines).
    *   *WhatsApp Delay:* Texting in a WhatsApp group introduces an operational lag of **60 to 180 seconds** due to typing, phone vibration unnoticed in high-noise environments, and intermittent cellular data handover. **WhatsApp must be restricted to asynchronous logging, never primary real-time line control.**
*   **Occupancy Count Error (Clickers vs Crowds):**
    *   According to the 2021 TETRA study on crowd monitoring (*Crowd Counter / Centre of Expertise Public Impact*), manual mechanical tally clickers have a baseline **margin of error of ~5%** under steady single-file or paired flow.
    *   *Fatigue & Surge Penalty:* When pedestrian flow exceeds ~1.2 persons/second per marshal, or when counting unconstrained wide gates without physical funnels, clicker error climbs to **15%–20%** (*TrafSys / Retail Sensing*). Marshals under heat and continuous counting experience cognitive fatigue after 45 minutes, leading to missed group increments.
    *   *Mitigation:* Single-door coach loading restricts ingress to 1 person per 1.5–2.0 seconds (headcount error drops below 2%). Tally counts must be recorded per 44-seat vehicle batch, not continuous indefinite numbers.

---

## 3. Failure Modes: Metering, Batching, and Holding

| Failure Mode | Mechanism & Symptoms | Operational Consequence | Engineering Prevention Rule |
| :--- | :--- | :--- | :--- |
| **1. Starved Hall** *(Under-metering)* | Destination foyer is completely empty; usher teams inside DTSP are idle waiting for arrivals; stage events fall behind schedule. | Hall utilization collapses; schedule slippage propagates across the university day. | Set a **Lower Buffer Threshold**: DTSP must issue the next `"READY"` call the instant the current cohort begins entering the hall doors, not when the foyer is completely empty. Lead time must match bus transit runtime ($t_{transit} \approx 4\text{ min}$). |
| **2. Overfull Foyer / Kerb Spill** *(Over-metering)* | Coaches arrive faster than hall doors can process students. Foyer buffer overflows onto the road kerb, forcing arriving buses to block live campus traffic. | Pedestrians forced into the roadway under Penang tropical sun; high crush and heatstroke risks. | Set an **Upper Buffer Cap**: Hard threshold of $\le 150$ pax in DTSP foyer. If foyer occupancy crosses 100, the clicker supervisor immediately calls `"HOLD DISPATCH"`. |
| **3. Student Leakage / Ignoring Hold** | Students waiting in hostel shade see friends moving or panic about seating position; line discipline collapses and individuals walk toward the bus stop. | Uncontrolled queue forms at the bus boarding point, destroying the countable batch structure. | Maintain physical gatekeeping at upstream holding (e.g., cafeteria/college foyer doors closed/cordoned). Students are only released into the boarding pen in exact batches of 44. |
| **4. Multi-Origin Collision** *(Two origins dumping simultaneously)* | RST dispatch and another hostel cluster (e.g., Aman/Damai or Indah Kembara) dispatch coaches or walking cohorts at the same time without cross-hub coordination. | Double pulse arrives at DTSP kerb simultaneously. Kerb capacity (2 coaches max) is exceeded; tailback blocks main campus artery. | **Single Command Station:** DTSP Control is the sole authority authorized to grant dispatch clearance. Restu and other hostel origins never dispatch on their own timer. |
| **5. Batch Fragmentation** | Slow movers, students stopping at restrooms, or marshals attempting roll-calls break a 44-student batch across multiple bus runs. | Coach departs half-empty (low capacity utilization) or stays stalled at kerb (ballooning dwell time). | Enforce "Roll call at hostel room, clicker at the bus". Never do paper roll call at the boarding gate. First 44 students in line board coach 1; next 44 board coach 2. |

---

## 4. Minimum Timestamp Set for Discrete Event Simulation (DES)

To build a reliable Discrete Event Simulator (in SimPy or AnyLogic), field data must distinguish between **true queuing**, **forced holding**, **downstream blocking**, **server starvation**, and **synchronization waiting**. 

### 4.1 Required Event Timestamps (Entity: Batch $k$ / Individual $i$)

For every batch $k$ (where $k = 1, 2, \dots$ representing one 44-passenger coach load), marshals log the following Unix/clock timestamps ($hh:mm:ss$):

1.  **$T_{arr}^{origin}$ (Arrival at Holding):** Time the student/batch enters the shaded holding area at RST.
2.  **$T_{call}^{dispatch}$ (Dispatch Clearance):** Time DTSP radio issues `"READY FOR BATCH k"` to Restu.
3.  **$T_{start}^{board}$ (Boarding Start):** Time the first student of batch $k$ steps onto Coach $j$.
4.  **$T_{end}^{board}$ (Boarding Complete):** Time the 44th student takes their seat and doors close.
5.  **$T_{dep}^{origin}$ (Coach Departure):** Time wheels roll at Restu boarding bay.
6.  **$T_{arr}^{dest}$ (Coach Arrival):** Time coach stops at DTSP kerb.
7.  **$T_{start}^{alight}$ (Alight Start):** Time doors open and first student steps onto pavement.
8.  **$T_{end}^{alight}$ (Alight Complete):** Time last student exits coach and coach departs kerb.
9.  **$T_{arr}^{foyer}$ (Foyer Entrance):** Time batch enters the indoor holding/foyer buffer.
10. **$T_{start}^{service}$ (Hall Ingress Start):** Time batch reaches the main DTSP auditorium doors.
11. **$T_{end}^{service}$ (Seated / System Exit):** Time batch clears the door usher and occupies hall seats.

### 4.2 State Distinction Matrix for DES Modeling

$$\begin{array}{l|l|l}
\hline
\textbf{State} & \textbf{Formal Definition} & \textbf{Timestamp Evaluation Formula} \\
\hline
\textbf{Queue Wait} & \text{Waiting behind peers in ordinary FIFO line} & T_{start}^{board} - T_{arr}^{origin} \quad (\text{when } T_{call}^{dispatch} \le T_{arr}^{origin}) \\
\textbf{Held (Metered)} & \text{Held intentionally in shade while server is ready} & T_{call}^{dispatch} - T_{arr}^{origin} \quad (\text{imposed delay upstream}) \\
\textbf{Blocked} & \text{Server ready to discharge but exit is physically blocked} & T_{dep}^{origin} - T_{end}^{board} \quad \text{or} \quad T_{start}^{alight} - T_{arr}^{dest} \\
\textbf{Starved} & \text{Resource ready with zero entities to process} & T_{arr}^{dest}[k] - T_{end}^{alight}[k-1] \quad (\text{kerb/door idle}) \\
\textbf{Sync-Wait} & \text{Waiting for batch/coach assembly before proceeding} & T_{end}^{board}[k] - T_{start}^{board}[k] \quad (\text{passenger 1 waiting for 44}) \\
\hline
\end{array}$$

---

## 5. Why Averages Lie: P50 vs P90 in Crowd and Transit Operations

In pedestrian and mass-transit queue management, **reporting average wait time is dangerous and misleading** (FHWA *Travel Time Reliability Report*; Walker, *Human Transit*):

1.  **Asymmetric Tail Latency:** Queue wait times do not follow a Gaussian normal distribution; they exhibit heavy right-skewed distributions. If 80% of students board smoothly with a 5-minute wait, but the last 20% suffer a 45-minute stall due to kerb gridlock, the **average wait is ~13 minutes** (which sounds tolerable to senior university administrators), while the **90th percentile (P90) is 45 minutes**. The student experience, heat exhaustion incidents, and operational collapse are entirely governed by the P90/P95 tail.
2.  **Bus Bunching Dynamics:** As demonstrated in transit headway analysis, when headway variation increases, the expected passenger waiting time is given by:
    $$E[W] = \frac{E[H]}{2} \cdot \left(1 + \frac{\text{Var}(H)}{(E[H])^2}\right)$$
    If buses are scheduled every 6 minutes ($E[H] = 6$), but bunch up into pairs (headways alternate 0 min, 12 min; $\text{Var}(H) = 36$), the average wait jumps from 3.0 minutes to **6.0 minutes** even though the average bus frequency remains identical.
3.  **Buffer Index & Planning Time Index:** Following the FHWA reliability metric, PPSL operations must track the **Buffer Index**:
    $$\text{Buffer Index} = \frac{\text{P95 Wait Time} - \text{Average Wait Time}}{\text{Average Wait Time}} \times 100\%$$
    A high Buffer Index (>50%) indicates severe operational unpredictability. High-reliability metering keeps the Buffer Index under 20%, ensuring that students at the back of the cohort do not suffer disproportionate delays.

---

## 6. One-Page PPSL Clicker Protocol (Operational SOP)

### Equipment Required Per Post
*   1 Mechanical handheld tally counter (four-digit reset clicker, ~RM15 / unit).
*   1 Clipboard with pre-printed 60-Second Interval Log Sheet.
*   1 Synchronized wristwatch / phone clock (all marshals synchronize to official Telco time at 06:30 AM).
*   1 Two-way radio (PMR446 or UHF preset to Channel 1).

### Post Assignments & Physical Stations

```
[Post 1: RST Cafeteria Gate]  -->  [Post 2: RST Bus Bay]  -->  [Post 3: DTSP Kerb Drop]  -->  [Post 4: DTSP Foyer]  -->  [Post 5: DTSP Hall Doors]
```

1.  **Post 1 (RST Shaded Holding Gate — Lead Marshal):** Stands at the exit door of Restu Cafeteria. Regulates release of exactly 44 students into the boarding corridor when Post 2 signals.
2.  **Post 2 (RST Bus Door — Boarding Marshal):** Stands at the single entrance door of the coach. Clicks every student boarding. Hands physical "Batch Card" (plastic laminated card 1–44) to the bus escort marshal.
3.  **Post 3 (DTSP Kerb Arrival — Unloading Marshal):** Stands at the DTSP coach drop-off point. Clicks students stepping off the bus. Confirms coach is empty and signals driver to depart immediately.
4.  **Post 4 (DTSP Foyer Entrance — Buffer Marshal):** Stands at the front outer glass doors of DTSP. Clicks students entering the foyer buffer. Monitors foyer crowd density.
5.  **Post 5 (DTSP Auditorium Main Doors — Ingress Marshal):** Stands at the open double doors of the main hall. Clicks students as they cross the threshold into hall seating.

---

### The 60-Second Logging Sheet (Printed Template)

Every marshal at Posts 1 through 5 writes down their cumulative tally counter reading at the start of every minute mark ($XX:00$). If no movement occurs, repeat the previous number. Never reset the clicker until the entire morning operation concludes.

```
POST LOCATION: _____________________    MARSHAL NAME: ____________________
DATE: 2026-09-XX                         RADIO CALLSIGN: __________________

┌──────────────┬──────────────────┬─────────────────┬──────────────────────────────────────────┐
│ Time (hh:mm) │ Cumulative Tally │ Delta (Pax/Min) │ Operational Notes (Holds, Bus ID, Jam)   │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:00     │      0000        │       -         │ Synchronized. Standing by.               │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:01     │      0024        │      +24        │ Coach #1 boarding started                │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:02     │      0044        │      +20        │ Coach #1 full, doors closed              │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:03     │      0044        │        0        │ Coach #1 departed (Batch 01)             │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:04     │      0044        │        0        │ Holding in shade (awaiting DTSP call)    │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:05     │      0075        │      +31        │ DTSP called "READY 02". Coach #2 loading │
├──────────────┼──────────────────┼─────────────────┼──────────────────────────────────────────┤
│    07:06     │      0088        │      +13        │ Coach #2 full, doors closed (Batch 02)   │
└──────────────┴──────────────────┴─────────────────┴──────────────────────────────────────────┘
```

### Protocol Execution Rules for Marshals
1.  **Do Not Clear the Clicker:** Maintain cumulative tally throughout the morning. If you misclick, note `"-1 error at 07:14"` in the notes column; do not spin the thumb dial backward.
2.  **The 60-Second Glint Rule:** At the 58th second of every minute, look at your watch, freeze your clicker reading, write it on the sheet, and resume clicking.
3.  **Radio Threshold Alert:**
    *   Post 4 (Foyer) calculates: $\text{Foyer Occupancy} = \text{Post 4 Cumulative} - \text{Post 5 Cumulative}$.
    *   If $\text{Foyer Occupancy} \ge 100$, Post 4 radios immediately: `"DTSP CONTROL: FOYER AMBER (100 PAX)."`
    *   If $\text{Foyer Occupancy} \ge 150$, Post 4 radios: `"DTSP CONTROL: HOLD DISPATCH, RED (150 PAX)."`
4.  **End of Shift Data Collection:** At the conclusion of movement, sheets from Posts 1–5 are photographed and uploaded to the coordination group. The delta columns directly supply arrival, service, and queue arrays for Python/SimPy DES validation.

---

## 7. Sources

1.  **Public Impact & TETRA Study (2021):** *Infosheets Crowd Counter — Manual Click Counting vs Digital Systems*. KdG University of Applied Sciences and Arts. URL: `https://www.crowdcounter.be/media/docs/Infosheets%20Crowd%20Counter%20-%20Overview.pdf` (Documented manual clicker error rate of ~5% under normal conditions and maximum operational clicking limit of ~1,700 clicks / 5 min).
2.  **Tickts Professional Events Guide (2024):** *Guide to Two-Way Radio Communications at Large Events & Festivals*. URL: `https://tickts.co.uk/blog/guide-to-radio-communications-events` (Standard radio protocols, channel separation, call-and-readback brevity).
3.  **National Institute of Standards and Technology (NIST) (2018):** *Mission Critical Voice Quality of Experience Mouth-to-Ear Latency Measurement Methods* (NIST IR 8206). URL: `https://nvlpubs.nist.gov/nistpubs/ir/2018/NIST.IR.8206.pdf` (Latency profiling across PTT systems and human communication loops).
4.  **Federal Highway Administration (FHWA):** *Travel Time Reliability: Making It There On Time, All The Time*. US Department of Transportation. URL: `https://ops.fhwa.dot.gov/publications/tt_reliability/ttr_report.htm` (P90/P95 buffer index vs mean average travel time; skewness of transit delays).
5.  **Human Transit (Jarrett Walker):** *The Perils of Succeeding "On Average"*. URL: `https://humantransit.org/2010/08/the-perils-of-succeeding-on-average.html` (Transit dispatch reliability, why passenger wait times deviate heavily from scheduled average headways).
6.  **National Disaster Management Authority (NDMA), India:** *Managing Crowds at Events and Venues of Mass Gathering: A Guide for Organizers and Planners*. URL: `https://ndma.gov.in/sites/default/files/PDF/Reports/managingcrowdsguide.pdf` (Input/output queue holding and flow release controls).
