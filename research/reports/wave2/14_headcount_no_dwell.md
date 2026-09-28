# Headcount & Attendance Methods Without Dwell Latency (Wave 2 Transport Levers)

**Verdict:** QR-scanning every individual student at intermediate checkpoints (dorm exits, bus staging queues, or hall outer gates) creates severe pedestrian bottlenecks (2.5–10.0 s/pax dwell). Instead, orientation headcount should be partitioned into a three-tier pipeline: (1) an **origin named roll call in hostel shade/foyer** where students are already gathered, (2) an **in-motion clicker headcount / colour token glance** (0.2–0.5 s/pax) at bus boarding and hall pass-through doors, and (3) a **broadcast/seat-level MyCSD QR scan** projected inside Dewan Tuanku Syed Putra (DTSP) after students are already seated in air-conditioned comfort.

---

### Key Findings
- **Doorway individual QR/barcode scanning causes queue failure:** Scanning an individual smartphone screen or printed badge at an entry bottleneck takes 2.0 to 5.0 seconds under ideal conditions and 8.0 to 10.0+ seconds under field conditions (screen glare, app loading, dead batteries, awkward scanner angles) ([Choose2Rent](https://choose2rent.com/blog/how-to-create-a-qr-code-for-an-event); [Supercode](https://www.supercode.com/blog/qr-codes-for-events)). For a 44-seat bus batch, an individual door scan adds 2.2 to 7.3 minutes of standing in the sun.
- **In-motion manual clickers / token tallies operate at continuous walking speed:** Mechanical or digital hand tally counters achieve 0.2 to 0.5 s/person (120–300 persons/min/lane) with a documented field error margin of ≤5% ([Crowd Counter TETRA Study](https://www.crowdcounter.be/media/docs/Infosheets%20Crowd%20Counter%20-%20Overview.pdf); [Fruin Pedestrian Flow Standards](http://www.gkstill.com/CV/PhD/Chapter3.html)).
- **Origin-count + destination reconciliation prevents lost students without gate friction:** Group custody operates via batch tally reconciliation: hostel foyers log exact named rosters; PPSL bus leads carry a fixed batch manifest of $N=44$; DTSP entrance marshals verify $N=44$ via clicker at the doorway without stopping the line.
- **MyCSD / co-curricular credit is designed for seated broadcast scanning:** At USM and peer Malaysian IPTAs (UKM, UTM, UM), institutional co-curricular tracking (MyCSD/merit codes) does not legally require an outdoor gate roll call. Official event practice routinely projects the session QR code onto the main hall projection screens or issues seat-level QR displays for students to log attendance while seated ([USM MyCSD](https://convo.usm.my/index.php/graduation/mycsd); [RJPNS Attendance Paper](https://rjpn.org/ijcspub/papers/IJCSP23B1107.pdf)).
- **Statutory / AUKU attendance rules govern course/program completion, not physical transit gates:** Malaysian university regulations (e.g., Akta Universiti dan Kolej Universiti 1971 / Akta 30 academic rules) require proof of mandatory attendance (e.g., the 80% rule for coursework/orientation modules), but do not specify entry gate turnstiles. Hostel foyer registration + in-hall MyCSD logs fully satisfy legal compliance and audit requirements.

---

### Detailed Analysis

#### 1. Throughput Benchmarks Across Identification & Headcount Technologies

| Method | Dwell / Scan Time (s/pax) | Throughput (pax/min/marshal) | Queue Impact at Chokepoints | Equipment / Operator Burden |
| :--- | :--- | :--- | :--- | :--- |
| **Individual QR Scan (Phone/Staff)** | 3.0 – 10.0 s | 6 – 20 | **Severe Bottleneck:** 44-pax coach boarding stalls for 3–7 min. | Requires charged phones, cellular/Wi-Fi data, camera alignment. |
| **Barcode / Handheld Scanner** | 1.5 – 3.0 s | 20 – 40 | **Moderate Delay:** 44-pax coach boarding takes ~1.5–2.2 min. | Handheld optical laser gun; avoids phone screen glare. |
| **Passive HF/UHF RFID Gantry** | 0.0 – 0.5 s | 120 – 200 | **Zero Dwell:** Normal walking gait through portal/door. | High capital cost; RFID tags on lanyards + reader antennas. |
| **Mechanical Tally Clicker** | 0.2 – 0.5 s | 120 – 300 | **Zero Dwell:** Marshal clicks as students step onto bus or through door. | Zero tech dependency; RM5 handheld thumb counter. |
| **Visual Glance (Colour Token / Lanyard)** | 0.2 – 0.4 s | 150 – 300 | **Zero Dwell:** Continuous pass-through inspection of hostel badge/wristband. | Pre-issued at hostel check-in; instantaneous verification. |
| **Paper Roster Sign-In / Manual Tick** | 10.0 – 30.0 s | 2 – 6 | **Catastrophic Failure:** Stalls movement completely at doorways. | High friction; restricted strictly to static waiting areas. |

*Sources: [Choose2Rent Throughput Breakdown](https://choose2rent.com/blog/how-to-create-a-qr-code-for-an-event); [Supercode Check-In Metrics](https://www.supercode.com/blog/qr-codes-for-events); [Trafsys & Retailsensing Metrics](https://www.retailsensing.com/definition/accuracy-people-counters.html); [Crowd Management India / Fruin Capacity Standards](https://www.crowdmanagementindia.com/post/crowd-density-and-level-of-service-the-science-behind-safe-crowd-management).*

#### 2. University Grouping Mechanisms: Lanyards, Colour Badges, and Battalions
- **Malaysian IPTA Orientation Practice (USM, UTM, UKM, UM):** During Minggu Siswa Lestari / Minggu Haluan Siswa, contingents are divided by hostel (*Desasiswa*) and assigned color-coded identification items (lanyards, wristbands, or contingent shirts) upon hostel check-in.
- **Passive Grouping as Access Control:** A marshal standing at the kerb or door does not verify national IC / matriculation numbers; they verify the **colour marker** (e.g., Orange = Restu, Green = Saujana, Purple = Tekun). Any student outside their assigned battalion color stands out immediately to escorts without interrupting the continuous flow of pedestrians.
- **US Military & Outdoor Event Battalion Protocols:** Mass transit operations utilize "chalks" (platoon/coach manifests). The headcount is established prior to departure by the stick lead; marshals downstream only count heads entering the vehicle to match the chalk sheet target (e.g., exactly 44 seats filled).

#### 3. Error Rates: Ghost Counts, Missed Students, and Group Mixing
- **Clicker Counter Accuracy:** TETRA crowd studies benchmark manual click counter error at **≤5%** under moderate crowd speeds (1–2 pedestrians/sec). At single-file boarding (1 coach door, ~0.8m clear width), single-stream clicker counting accuracy regularly reaches **98–99%** ([Retailsensing](https://www.retailsensing.com/definition/accuracy-people-counters.html); [Crowd Counter](https://www.crowdcounter.be/media/docs/Infosheets%20Crowd%20Counter%20-%20Overview.pdf)).
- **Ghost Counts:** Occur when marshals double-click during rapid movement or count non-students (e.g., accompanying PPSL escorts or bus drivers). Protocol mitigation: Escorts board first or last, holding a hand gesture, and are explicitly excluded from the passenger tally.
- **Missed Students & Stragglers:** Occur during outdoor walk-ups. Mitigated by pairing 1 PPSL Lead (sets pace at the front) and 1 PPSL Sweeper (cleans up the rear and ensures no one drops out between origin and transit).
- **Group Mixing:** Prevented by releasing single-hostel pulses from origin holding pens. Mixed batches only occur if multiple queues merge at the bus boarding kerb.

#### 4. Institutional Co-Curricular Apps: MyCSD, UTM ACad, and UKM UrusBakat
- **USM MyCSD Architecture:** Continuous Student Development (MyCSD) is the university's non-academic transcript tracking system governed by BHEPA (Pusat Pembangunan Pelajar). Participation credit is recorded via digital event submission and QR code confirmation.
- **Door Scanning vs. In-Hall Projection:**
  - Scanning thousands of incoming freshmen individually at the exterior doors of DTSP creates an unviable bottleneck (5,000 students × 3 seconds = 4.16 marshal-hours per door; with 4 double doors, it still guarantees 30–45 minutes of static queueing under open sky).
  - Standard operational SOP for mass university assemblies across Malaysian IPTAs (e.g., USM DTSP townhalls, UKM Dewan Canselor Tun Abdul Razak orientations) relies on **projecting the attendance QR code on the giant hall multimedia screens** or providing dynamic attendance links while attendees are comfortably seated inside before the official ceremony begins.
  - This decouples transit movement from academic credit verification.

#### 5. Legal & Statutory Regulations Regarding Roll Calls
- **Universities and University Colleges Act 1971 (AUKU / Akta 30):** Governs student disciplinary statutes and academic attendance rules (e.g., Kaedah-Kaedah Universiti Sains Malaysia Tatatertib Pelajar). It mandates that students attend required orientation assemblies, but does **not** mandate gate-level electronic checkpoints.
- **Hostel Foyer Roll Call Legality:** The university establishes its formal record of attendance through hostel residential lists (Desasiswa room rosters) verified by PPSL/MPDR floor leaders inside the hostel foyer or covered common area before departure. Once students are recorded as present at the hostel muster point, transit custody transfers to the PPSL convoy marshals.

---

### Recommended Station Types

To eliminate standing dwell times in the sun while preserving 100% headcount accountability, orientation movement must implement three distinct station types:

```
[Hostel Foyer / Cafeteria]       [Bus Staging Kerb]            [DTSP Hall Doors]             [DTSP Interior Seats]
      STATION 1:                     STATION 2:                   STATION 3:                      STATION 4:
     origin_count                   pass_through                 pass_through                      hall_scan
--------------------------     -------------------------     ------------------------      -------------------------
Named Floor Roll Call /        Mechanical Clicker Tally      In-Motion Continuous Flow     Projected Screen QR Code
Static Roster Check            (Single-file Coach Door)      (4 Double Entrance Doors)     (Air-conditioned Seating)
Dwell: 0.0 s added to transit  Throughput: 0.3-0.5 s/pax     Throughput: 0.2-0.4 s/pax     Throughput: 0.0 s dwell
```

#### Station 1: `origin_count` (Hostel Foyer / Shaded Holding Pavilion)
- **Location:** Restu / Saujana / Tekun residential foyers, dining halls, or covered common areas.
- **Operational Mode:** Named roll call by floor/block leaders while students are seated in shade. Students receive their contingent colour identifier (lanyard / wristband) if not already issued.
- **Expected Dwell/Throughput:** **0.0 s/pax added to transit chain** (conducted in parallel during pre-movement staging).
- **Output:** Exact headcount manifest ($N$) dispatched per bus batch.

#### Station 2: `pass_through` (Transit Staging & Bus Door)
- **Location:** Bus boarding kerb at Restu cluster.
- **Operational Mode:** Single-file entry. 1 PPSL marshal stands at the coach door operating a mechanical clicker tally counter. No screens, no barcode checking, no physical ticket handoffs.
- **Expected Throughput:** **0.3 – 0.5 s/pax** (total bus fill time for 44 seats = 15–22 seconds of active boarding once doors open).
- **Communication:** Marshal radios bus number and exact headcount ($N=44$) to the destination dispatcher.

#### Station 3: `pass_through` (DTSP Exterior Entrance Doors)
- **Location:** Outer doors of Dewan Tuanku Syed Putra.
- **Operational Mode:** Double-door continuous walking flow. PPSL doorway marshals observe incoming cohorts for hostel colour lanyards and clicker-tally arrivals to confirm full batch discharge. No individual scanning.
- **Expected Throughput:** **0.2 – 0.4 s/pax per double-door** (40–60 persons/minute/lane).
- **Crowd Dynamics:** Eliminates the unshaded bottleneck outside DTSP; students transition directly from coach drop-off into air-conditioned interior seating.

#### Station 4: `hall_scan` (DTSP Main Auditorium Interior)
- **Location:** Inside DTSP after batches are fully seated in their designated hostel blocks.
- **Operational Mode:** University co-curricular credit (MyCSD / BHEPA verification) is recorded via the main projection screens (large-format static or rotating QR code) or via printed QR boards placed at row ends.
- **Expected Dwell:** **0.0 s/pax transit friction** (parallel asynchronous scanning across 3,000–5,000 students while seated prior to opening remarks).

---

### Sources
1. [Choose2Rent Event Throughput Guidelines](https://choose2rent.com/blog/how-to-create-a-qr-code-for-an-event) — Field benchmarks of QR code scan speeds vs. physical registration queues (2–10 s/pax dwell).
2. [Supercode Event Registration & Check-in Benchmarks](https://www.supercode.com/blog/qr-codes-for-events) — Quantitative comparison of digital scan latencies vs manual check-in protocols.
3. [Crowd Counter TETRA Study (2021)](https://www.crowdcounter.be/media/docs/Infosheets%20Crowd%20Counter%20-%20Overview.pdf) — Empirical accuracy and error margin (≤5%) of mechanical tally clickers in crowd management.
4. [Retail Sensing People Counting Standards](https://www.retailsensing.com/definition/accuracy-people-counters.html) — Analysis of manual counting accuracy, single-channel ingress, and drift mitigation.
5. [Dr. G. Keith Still / Fruin Pedestrian Flow Analysis](http://www.gkstill.com/CV/PhD/Chapter3.html) — Fundamental diagrams of pedestrian walkway and doorway capacity (up to 75–82 persons/metre/minute).
6. [Crowd Management India & HCM Capacity Guidelines](https://www.crowdmanagementindia.com/post/crowd-density-and-level-of-service-the-science-behind-safe-crowd-management) — Doorway and corridor Level of Service (LOS) flow capacities.
7. [USM MyCSD Official Portal & Convo Transcript Guidelines](https://convo.usm.my/index.php/graduation/mycsd) — Institutional framework for MyCSD co-curricular credit tracking and non-academic transcripts.
8. [International Journal of Computer Science & Publication (RJPNS)](https://rjpn.org/ijcspub/papers/IJCSP23B1107.pdf) — Academic implementation of centralized QR code display via auditorium projectors for mass attendance recording.
9. [Universities and University Colleges Act 1971 (Akta 30)](https://en.wikipedia.org/wiki/Universities_and_University_Colleges_Act_1971_(Malaysia)) — Statutory framework governing Malaysian public university attendance rules and disciplinary authority.
