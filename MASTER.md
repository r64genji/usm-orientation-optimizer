# MASTER — USM Orientation Movement

Canonical context for any agent in this repo. Facts, constraints, bottlenecks, data, open questions. **Not a plan.** Later files under `research/reports/` are literature. They do not override this file unless Abraham updates this file.

Repo: `r64genji/usm-orientation-optimizer`  
Campus: Universiti Sains Malaysia, **Kampus Induk**, Gelugor, Pulau Pinang  
Event class: Minggu Siswa Lestari (MSL) — **student movement** to a hall event, not the speeches  
Timezone: `Asia/Kuala_Lumpur`  

Provenance tags: **[Abraham]** operator; **[measured]** this repo’s GPS/video; **[source]** named URL/paper; **[unverified]** do not freeze.

---

## 1. What this repo is for

Hermes talks to a **deterministic** optimizer + discrete-event simulator. Same plan → same numbers (integer clock, seeded RNG, no wall-clock).

Pain: students stand a long time with nothing useful to do while being moved **as supervised groups** between hostels and a hall (typically Dewan Tuanku Syed Putra, DTSP).

**Search space is open.** Agents may try any class of idea (release policy, holding, vehicles, doors, staffing, information, batch definition, modal mix) if they:

1. State which items in §2–§4 they keep, relax, or violate.
2. Do not invent numbers on §8.
3. Score against measured traces where those traces apply (the 17 Sep Restu phone is **one morning, one contingent**, not every day).
4. Keep calculations deterministic.

This file does **not** name a winning strategy.

---

## Operational Decisions (2026-09-23) [Abraham]

Canonical operational rules confirmed by operator Abraham Tan on 2026-09-23. These locked decisions govern all simulation scenarios, optimization policies, and documentation:

1. **Hostel Release & Priority Sequencing:**
   - **All hostels release at 06:00:00 (t=0).**
   - **Restu cafe hold:** Restu students wait at the Restu cafe first upon release.
   - **Tekun & Saujana priority:** Desasiswa Tekun and Desasiswa Saujana have priority because of their lower headcounts; they are queued and go through first.
   - **Restu dispatched last:** Restu is dispatched last. This sequencing is the primary imposed operational wait.
2. **DTSP Hall & Secondary Overflow Capacity:**
   - **DTSP full hall capacity is confirmed at ~3,000 seats** (previously cited as 2,500 to 3,500; the canonical full-hall limit is locked at 3,000 seats).
   - **Dewan Budaya G03 is confirmed as the authorized active secondary overflow venue (seats ~500)** (specifically Dewan Kuliah G & H, ~400–500 seats). It is an active destination venue, NOT a waiting room.
   - **1,338 seats represents the Kawsar main floor only**, not the full hall.
   - **Pre-DTSP wait is in a nearby lecture hall** (NOT Jalan Perpustakaan; do not simulate that holding hall).
3. **Transit Fleet & Drop-off:**
   - **Fleet locked to 8 buses: exactly 5 coach + 3 electric** (Singapore-style, 1 usable door each, 65–80 pax capacity with standees filling aisle).
   - **Route loop:** gathering outside DUP $\rightarrow$ outside DTSP drop-off $\rightarrow$ same 8 buses return and re-queue. No additional vehicles may be added.
   - **DTSP drop-off layout:** straight-line road / car park where multiple buses dock simultaneously (entire 8-bus fleet can queue in-line, with 3 to 4 buses actively offloading at once).
   - **Zero door checks at DTSP & Doors Open from Start:** students walk straight in and sit down; zero credential or bag screening dwell at hall doors. Doors are NOT locked until 08:32; that was a fabricated narrative.
4. **Staffing Roles:**
   - **PPSL are event workers / facilitators** (154 total across campus duties) who supervise student cohorts, manage queues, and conduct headcounts at stations; students are the supervised flow, not the staff.
---

## 2. Invariants

Properties of the operated system. Ignoring them answers a different problem.

### 2.1 Problem type

| ID | Invariant | Provenance |
|---|---|---|
| I1 | **Movement** between origins (hostels / pick-up points) and a **destination hall**, with a **fixed event start that day**. Not scheduling the speeches. | [Abraham] |
| I2 | Students move as **supervised groups**. **PPSL are event workers / facilitators**, not the population being moved. Student movement must be **supervised**. | [Abraham] |
| I3 | **Headcount must be done at key points** (stations). Headcount is part of the system, not optional polish. | [Abraham] |
| I4 | A GPS trace in this repo is **one device inside a contingent** (N=1 random student in the cohort, NOT the head or tail of the hostel wave). Never assume GPS times mark the first or last student of Restu. | [Abraham]; `raw_data/media` |
| I5 | Default sim unit is the **batch / vehicle load**, not individual pedestrian physics, unless an experiment is explicitly labelled otherwise. | [Abraham] MVP |
| I1b | **Hostel release & priority sequencing**: All hostels release at **06:00:00 (t=0)**. Restu students wait at the **Restu cafe** first. Desasiswa **Tekun and Saujana have priority** due to lower headcounts; they are queued and go through first. **Restu is dispatched last** (primary imposed operational wait). | [Abraham] 2026-09-23 |
| I5b | **Benchmark Conservative Principle:** Have **conservative estimates for everything**. It is **better to be later than real life than earlier**, for our benchmark. Dwells, walking pacing, and clearance times should err toward slower/cautious bounds so optimization solutions remain robust. | [Abraham] 2026-09-22 |

### 2.2 People and control

| ID | Invariant | Provenance |
|---|---|---|
| I6 | PPSL (printed: Pembimbing Program Siswa Lestari / Pembimbing Pelajar Siswa Lestari) = **facilitators/workers** of the movement and events. BHEPA sits above them. | [Abraham] + [source] BHEPA |
| I7 | Kampus Induk PPSL headcount 2026: **154** (BHEPA, 8 Sep 2026). Finite labour: extra stations or walking escorts consume workers. | [source] |
| I8 | Mass hall sessions group first-years primarily by **desasiswa / block / floor**, not by faculty, until faculty-breakout days. | [source] + [Abraham] |
| I8b | **Walking to overpass from Restu cafe (via road shoulder) is strictly single file**: PPSL allows only **one file at once** to keep vehicular traffic clear and maintain control. | [Abraham] 2026-09-22 |
| I9 | DTSP (and similar halls) have a **known architectural door/portal set** (see §4.3: 4 exterior doors Pintu A, B, C, D). **NO checks or screening at entry doors**: students walk straight in and sit down. **Doors are NOT locked until 08:32 (fabricated assumption purged)**; doors are open and accessible from the start, and exterior wait times represent operational staging/headcounts, not physical locks. **Seating is direct block-directed flow without a single global seating-server queue.** Cohorts route to distinct parameterized doors operating concurrently. DTSP full-hall capacity is confirmed at **~3,000 seats** [Abraham 2026-09-23]. Dewan Budaya G03 is confirmed as the authorized active secondary overflow venue (seats ~500). | [Abraham] 2026-09-22, 2026-09-23, 2026-09-24 |
| I10 | Origin boarding and destination occupancy can be **coupled by radio / next-station reporting**: destination saturation can pause origin boarding. Buses already rolling still arrive. Lag unmeasured. | [Abraham] NOTES_AND_LOGS |

### 2.3 Vehicles and geometry (do not confuse with policy)

| ID | Invariant | Provenance |
|---|---|---|
| I11 | MSL uses **campus/orientation buses**, not the published semester Route E timetable. **Buses have NO arrival time — they are already staged and ready when the first batch of students arrives.** Fleet is **strictly locked to 8 buses: exactly 5 coach buses + 3 electric buses**. Route loop: gathering outside Restu (Restu cafe / pavilion) $\rightarrow$ outside DTSP drop-off $\rightarrow$ same 8 buses return and re-queue. No extra vehicles may be added. | [Abraham] 2026-09-19, 2026-09-22, 2026-09-23 |
| I12 | Observed 17 Sep Restu boarding: **high-floor single-front-door coach**; queue single-file at the step. Coaches run at **full capacity with standing students filling the aisle all the way from back to front steps** (effective capacity 65–80 pax). | [Abraham] 2026-09-22; video 07:49 |
| I12b | Smaller electric buses are Singapore-style bodies but **only one door is used** (same serial boarding as the coach, not dual-door city boarding). | [Abraham] 2026-09-19 |
| I12c | Buses **shuttle in a loop**: origin gathering (outside DUP / Restu gathering) → outside DTSP → same vehicles return and **queue again**. First pulse leaves; after a while the same buses reappear in the origin queue. Not a one-shot drop-off. Cycle time including DTSP hold is still unmeasured. | [Abraham] 2026-09-19, seen from gathering |
| I12d | **Dwell times (conservative safety margin)**: **3 minutes (~180 s) for boarding** and **3 minutes (~180 s) for alighting** per full coach with standees. Better for the benchmark to be later than real life than earlier. | [Abraham] 2026-09-22 |
| I12e | **DTSP drop-off berth layout**: straight-line roadway corridor can queue the **entire 8-bus fleet** in-line, with **3 to 4 buses actively offloading at once**. | [Abraham] 2026-09-22 |
| I12f | **DTSP car park waiting area (3 levels / berths) & observed cohort staging**: terraced holding area where students sit directly on the asphalt in rows under trees: <br>• **Conservative capacity**: **500 students safely seated, max 600 students** across the 3 tiers (Level 1 main apron: ~320 safe / 380 max; Level 2 mid-terrace: ~120 safe / 140 max; Level 3 roadside buffer: ~60 safe / 80 max). <br>• **Observed cohort staging [Abraham 2026-09-24]**: students are staged as distinct cohorts across tiers (including one Restu boys cohort observed occupying one of three tiers; headcount unknown; exact tier level unconfirmed since observer noted only that one tier was occupied by Restu boys; other groups staged in remaining areas/tiers). Exact sex counts, 50/50 splits, exact source-unit sex labels, exact tier assignments for every cohort, and exact door mapping A-D are unobserved parameters. Operational routing channels are parameterized without fake individual sex partitions. Each cohort releases through an assigned parameterized DTSP door, and different cohorts use different doors concurrently. | [Abraham] 2026-09-22, 2026-09-24 |
| I12g | **Mandatory headcount at ALL gathering areas (5 minutes / 300 s dwell)**: When students arrive at any gathering area (the drop-off car park, Dataran Merah north plaza, or G28 Siswaniaga grass field), they do NOT walk immediately to the hall doors. They assemble for a mandatory **5-minute (300 s) PPSL headcount** and queue in columns. Movement from each gathering area to the hall or overflow is strictly **one single file per gathering area** peeling off in parallel (not one shared file bottlenecking all areas combined). | [Abraham] 2026-09-22 |
| I12h | **Bangunan G03 / Dewan Budaya G03 (Dewan Kuliah G & H) is an authorized active secondary overflow destination venue, NOT a waiting room**: Only when DTSP fills to capacity (~3,000 seats) are subsequent student cohorts diverted to take their seats in DK G and DK H (each ~200–250 tiered seats, total ~400–500 seats, ~500 seats confirmed), located in building G03 connected by covered walkway (68m from DTSP, 118m from drop-off berth). | [Abraham] 2026-09-22, 2026-09-23 |
| I13 | **Jejantas / hill footpath** near Restu is **narrow** (photo: column on curb, carriageway still used). Geometry is a fact; whether a plan uses that path is open. | [measured] photo 07:37; OSM way `1030376052` |
| I14 | Outdoor standing on asphalt in Penang heat is a **safety/comfort** constraint. Exact legal minutes not frozen. | [measured] DTSP video; DOSH guidance exists [source] |

### 2.4 Time (not a single calendar day)

| ID | Invariant | Provenance |
|---|---|---|
| I15 | **Date is not unique.** Orientation week has **a hall event most mornings** at a **set clock time that day**. Modelling default: **event start 09:00** unless a specific day’s jadual says otherwise. | [Abraham] |
| I16 | The Sensor Logger file is **one morning: 2026-09-17**. Use it as a **trace**, not as “every day looks like this clock.” | [measured] |

---

## 3. Measured trace — 2026-09-17 Restu contingent (rechecked)

GPS is **noisy when stationary** [Abraham]. Horizontal accuracy is often 3–10 m; 30 s windows while `speed < 0.4 m/s` have mean bbox diagonal **~7.6 m** (p90 ~10 m, rare spikes much larger). **Do not treat small GPS wander as walking.** Prefer: speed, 60 s **centroid hop**, activity labels, and **photo/video clock** over raw cumulative distance (`4310 m` raw includes jitter).

Activity.csv (777 rows): stationary 373, unknown 254, tilting 71, walking 48, automotive 28, cycling 3.

### 3.1 Photo/video vs GPS (same local clock)

| Media | Clock | GPS nearest | Reading |
|---|---|---|---|
| Queue photo + `0737_road_shoulder_queue.mp4` | 07:37:46 | 07:37:45, 5.35690, 100.29078, speed 0.35 m/s, acc 5.4 m | On Restu road, ~130 m from DUD start, ~220 m from jejantas pin, **column toward the sky bridge** |
| `0747_pavilion_boarding_pulse.mp4` | 07:47:38 | 07:47:37, 5.35640, 100.29334, speed 0.07 | Near boarding / pavilion, ~47 m from jejantas pin |
| `0749_bus_boarding_queue.mp4` | 07:49:10 | 07:49:09, 5.35620, 100.29348, speed 0.05 | **At the coach**, still |
| `0806_dtsp_exterior_reservoir.mp4` | 08:06:43 | 08:06:42, 5.35716, 100.30175, speed 0.12 | **~150 m from DTSP pin**, still, road reservoir |

Abraham text the same morning: woke ~06:30; felt arrival ~08:30 or 09:30; “waiting outside dud”; next-station radio batching. [NOTES_AND_LOGS.md]

### 3.2 Legs from GPS centroids (60 s), not the old 5-stage script

Old `processed/telemetry_summary.json` stages mixed **walking-in-column** with **boarding wait** into one “24.5 min Restu queue.” Recheck:

| Window (local) | What the phone is doing | Distances / motion |
|---|---|---|
| 06:47–07:33 | At / beside DUD. Speed mostly &lt;0.4 m/s. ~46 m from start pin. **Stationary jitter, not a commute.** | ~45 min prep/gather. Matches “waiting outside DUD.” |
| 07:33–07:49 | Slow column along Restu road, past jejantas, to boarding berth. Centroids hop 20–40 m per minute. Photo 07:37 matches. | ~16 min. Net ~400 m along road. Closest to jejantas ~07:46 (3.6 m). |
| 07:49–07:58 | Still at boarding (centroid barely moves). Video is the coach queue. | ~9 min wait at vehicle. |
| 07:58–08:01:30 | **Automotive.** Three speed≥4 m/s runs: 07:59:53–08:00:15, 08:00:27–08:00:47, 08:00:49–08:01:30. v_max 34.6 km/h. | ~2.5–3.1 min moving. Vehicle-only track ~1.04 km. Lands ~150–180 m from DTSP pin. |
| 08:01–08:32 | Almost no centroid hop. ~150 m from DTSP. Video 08:06 is this. | **~31 min outdoor hold.** |
| 08:32–08:35 | Walk toward hall. 08:35 centroid ~18 m from DTSP pin. | ~3 min ingest crawl. |
| 08:35–09:18 | At hall coordinates; speed noise 0.1–0.4 m/s. | Seated / indoor GPS wander. |

Board dwell [Abraham]: ~3 minutes (180 s) for a big bus, crammed, standees. Alighting dwell [Abraham]: ~3 minutes (180 s) for a full coach. Video 07:49 is the queue at the door, not a timed full load. Use **180 s boarding** and **180 s alighting** per coach pulse as conservative priors with safety margin. Walking from Restu cafe (M07) to overpass is strictly single file (PPSL allows only 1 file at once to keep vehicular lanes clear). At DTSP, buses dock along the straight-line road / car park area where the whole line holds all 8 buses with 3 to 4 buses offloading simultaneously. The 3-tier car park waiting area safely seats 500 students (max 600) on the asphalt as a conservative estimate. Door entry has zero checks. Always use conservative estimates (better later than earlier).

Crow-fly Restu cafe pin (5.356461, 100.289265) → DTSP pin is **1,438.4 m** (historical DUD pin was 1,470.4 m).

---

## 4. Hard physical bottlenecks

Places and objects. They constrain flow. They do not pick a policy.

### 4.1 Restu / RST origin

- Towers Restu M01 (M) / M02 (F), 10 storeys. Lift vs stair discharge **unmeasured**.
- Road **shoulder** as a linear queue: grass/guardrail vs live carriageway.
- **Jejantas Padang Kawad** OSM `1030376052` (`footway` + `bridge=yes`) + steps `1030376053`–`1030376056`. Narrow. Contingent **used it on the way to the bus**, 07:33–07:49.
- DUD M08 OSM `275415002`, footprint ~1,669 m². Exam seating **278** desks. MSL standing/sitting capacity **not measured**.
- Big-coach **single front door**, steps, serial boarding. Smaller **electric** buses also used on MSL [Abraham] — door count and capacity of those: see §5, still thin.

### 4.2 Transit

- Restu ridge tens of metres above DTSP basin (Open-Meteo ~42–54 m vs ~19 m). Outbound downhill.
- OSRM **default foot** pavilion→DTSP = 2,371 m / 31.7 min via **Jalan Bukit Gambir / Jalan Universiti**, **132 m** from jejantas. **Not** this contingent’s path. Public `router.project-osrm.org` “foot” returned **driving** geometry — ignore that engine for walking.
- MSL fleet ≠ semester Route E.

### 4.3 DTSP

- OSM way `896393762`, ~5.35695, 100.30311, campus code G01. maps.usm.my
- Drop-off is along a straight road / car park where multiple buses dock simultaneously (entire 8-bus fleet in-line, 3 to 4 buses offloading at once). Pre-DTSP wait is in a nearby lecture hall, NOT Jalan Perpustakaan (do not simulate that holding hall).
- **Building portals [source]** Khalid et al., *Discrete Event Dyn Syst* (doi:10.1007/s10626-015-0215-0): **4 exterior exits A', B', C', D'** plus high-capacity foyer conduits (corridors 14 & 15 / Pintu Utama toward Dataran Merah). Convocation practice names Pintu A–D. **Leaves open that morning = parameter.**
- Kawsar main-floor model **1,338** seats (blocks S–Z) represents the main floor only, not the full hall. Full-hall capacity is confirmed at **~3,000 seats** [Abraham 2026-09-23]. Dewan Budaya G03 is confirmed as the authorized active secondary overflow venue (seats ~500).
- 17 Sep ingest bottleneck: **admission pacing + road storage**, not bag search (none observed).

### 4.4 Control coupling

- Radio can pause origin boarding when destination looks full; in-flight buses still arrive.
- Columns exist; motion is **stop-and-surge** (backpressure) when the front is blocked.

---

## 5. Demand — sidang 2026/2027 (not last year)

University-wide new undergraduates **offered 2026/2027: 5,804** (14 Sep 2026 VC / HEPA / news.usm.my). UPU perdana 4,904. **Kampus Induk-only grand total was not published as one number** in those releases.

**Hostel check-in counts published those days [source] HEPA 12–13 Sep 2026** (new students registered, not beds):

| Hostel | Registered (bulletin) |
|---|---|
| Saujana | 610 (12 Sep) |
| Indah Kembara | 244 (12 Sep) |
| Bakti Fajar Permai | 341 (12 Sep) |
| Aman Damai | 410 (13 Sep) |
| Tekun | 508 (13 Sep) |
| **Subtotal these five** | **2,113** |
| Restu | **not in those two bulletins** |
| Cahaya Gemilang | **not in those two bulletins** |

OKU: 17 candidates, Aman Damai facilities [source] same 14 Sep briefing. IIP Electronic Engineering 200 at Induk (then SAINS@USM later).

Bed table from older UPPU/ePrint (capacities, not 2026 occupancy): Restu 1,687 vs restu.usm.my ~2,066 — conflict. Saujana 1,577, Tekun 1,548, etc.

**Default hall start parameter: 09:00.** Specific days may differ; 17 Sep GPS is still in the hall by ~08:35–09:18.

---

## 6. Vehicles [Abraham + video]

- **Fleet locked [Abraham, 2026-09-23]:** strictly **8 buses: exactly 5 coach buses + 3 electric buses** (each with 1 usable door, 65–80 pax effective capacity with standees filling aisle). Seen from the gathering area outside DUP: a first batch leaves for DTSP; later the **same buses come back and queue again**. Loop is gathering $\rightarrow$ outside DTSP $\rightarrow$ return $\rightarrow$ re-queue. Not a one-way dump.
- **Big coaches:** high-floor, **one front door**, crammed, **standees**. Boarding a **big** bus **~1:45**. Seated often quoted 40–44; **crush &gt; seated**.
- **Smaller electric buses:** Singapore-style body, but **only one door opens** on this operation. Seated/standing capacity still unmeasured. Wave3 claimed they were absent on Restu–DTSP — **do not treat that as fact**.
- Do not use semester Route E “2 units.”
- Simulator Restu replay still uses **one coach** until a scenario is rebuilt on this 8-bus loop.

---

## 7. Hostel → DTSP routes

Coordinates (OSM / places JSON, confidence varies):

| Hostel | Approx origin | Notes |
|---|---|---|
| Restu (Restu cafe M07) | 5.356461, 100.289265 | Measured cafe start (GPS session 3); RST west ridge; bus on the way to berth |
| Tekun | 5.35563, 100.29129 | RST |
| Saujana | 5.3564, 100.2905 | OSM polygon missing; medium |
| Indah Kembara | 5.35603, 100.29604 | Closer in |
| Aman Damai | 5.35431, 100.29615 | OKU |
| Bakti Permai | 5.35776, 100.30055 | Short |
| Cahaya Gemilang | 5.36046, 100.30360 | Short |
| Fajar Harapan | 5.35500, 100.29977 | Short |
| DTSP | 5.35695, 100.30311 | G01 |

OSRM foot times on the **public-road engine** (wrong corridor for Restu/Tekun): Bakti ~6 min, Cahaya ~7, Fajar ~7, Aman ~13, Indah Kembara ~17, Tekun ~24, Restu ~30. **Do not use Restu OSRM as the jejantas path.**

Street-view + social pack (landed): `research/reports/wave3/22_hostel_routes_social_street.md` + `22_hostel_routes.json`. OSM + some TikTok/IG/Facebook. **Literature, not law:** that write-up claims a hard RST-bus vs inner-walk split and “no electric buses”; Abraham says MSL uses **both** big coaches and smaller electric buses, and modal mix is **not** an invariant. Use it for **named paths, stairs, bus-stop OSM nodes**, not for policy.

Campus bbox OSM relation `11203707`: lat 5.3520–5.3628, lon 100.2886–100.3110.

---

## 8. Do not hallucinate

`null` + a measurement note.

1. **Exact MSL plates** inside the locked 8-bus loop (coach vs electric split is confirmed: **5 coach + 3 electric** [Abraham 2026-09-23]); measured round-trip cycle including DTSP hold (loop itself is observed)
2. **Doors open that morning** and which hostel→which door (building *has* 4 named exterior exits + foyer portals)  
3. DUD / cafe **MSL occupancy** (278 = exam desks)  
4. Restu (and Cahaya) **2026 check-in headcount** (not in the 12–13 Sep HEPA tables above)  
5. Kampus Induk **single official 2026/2027 intake total** (only 5,804 all-campus + partial hostel registrations)  
6. Radio lag  
7. Electric-bus seated/standing capacity  
8. Restu **walk-only** duration to DTSP (this GPS includes bus)  
9. Saujana building polygon  
10. Simultaneous traces from other hostels  
11. Fire occupancy certificate  
12. Using GPS wander while `speed ≈ 0` as path length  

---

## 9. Contradictions (leave both)

| Topic | A | B |
|---|---|---|
| Restu beds | 1,687 ePrint | ~2,066 restu.usm.my |
| PPSL Malay name | Program | Pelajar |
| Coach seats | 40 tender | 44 lore; crush higher [Abraham] |
| Board time | ~105 s big bus [Abraham] | 2.5 s/pax from a 3 s clip; papers 1.5–4.5 s/pax |
| Electric buses on MSL | [Abraham] yes | wave3/23 claimed none on this corridor |
| DTSP elevation | ~19 m Open-Meteo | older notes ~10–12 m |
| Induk 2026 intake | 5,804 is **all campuses** | Induk-only unpublished; ≥2,113 from five hostels’ check-in days |

---

## 10. Data contract

Every stored number: `source` = measured | official | osrm | abraham | assumed.

Tables (see also `research/reports/06_mvp_data_dictionary.json`): places, routes, batches, vehicles (type coach|electric, seated, standing_crush, doors, board_s), stations/workers (PPSL), observed_traces, baseline_run (per trace, not “the” day), candidate_plan, simulation_result.

Privacy: no names/matric in git. Hash subjects. Blur faces before public remotes.

**Parameters** (tunable, not unknown physics): `event_start` default `09:00`; `doors_open` (integer ≥1); `hostel_door_assignment`; `fleet_mix`; `board_s_big_coach` default 105.

**Calibration of the 17 Sep Restu trace** (if replaying that morning): DUD dwell ~06:47–07:33; column 07:33–07:49; berth 07:49–07:58; bus ~07:58–08:01; DTSP road ~08:01–08:32; door crawl ~08:32–08:35. Do not retune physics to make a favourite plan win.

---

## 11. Repo map

```
MASTER.md                 ← start here
README.md
raw_data/                 IMMUTABLE (GPS, media, empty EpiCollect schema)
processed/                derived; stages.json may be stale vs §3
scripts/ tests/
research/reports/         literature
research/reports/gps_leg_recheck.json
research/reports/wave3/   2026 intake, vehicles, hostel routes
```

---

## 12. Agent rules

1. Read this file, then `raw_data/`, then `processed/`. Then `research/reports/` as untrusted.
2. Label every number.
3. Do not delete a class of idea unless Abraham adds it to §2.
4. If §4 makes an idea expensive, **model the cost**; do not silently drop it.
5. PPSL = workers. Students = supervised flow. Headcount at key points.
6. No dummy telemetry. No Route E fleet as MSL.
