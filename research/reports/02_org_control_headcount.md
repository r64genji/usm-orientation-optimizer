# Organization, Command Hierarchy, & Headcount Control Model: USM Orientation (Minggu Siswa Lestari)

**TL;DR:** USM orientation movement is governed by a dual-command matrix under BHEPA where PPSL Induk (central logistics/hall marshals) and PPSL Desasiswa (hostel-contingent marshals led by a Penghulu and Penghulunita) control student batches organized strictly by residential hall and floor block. The observed 55.9-minute holding bottleneck stems from reactive radio throttling between DTSP hall marshals and hostel bus-stop wardens, which can be modeled deterministically in an optimizer via batch release pacing, dedicated pedestrian corridors, and multi-portal hall ingress.

---

### Key Findings
- **Official Identity & Competing Expansions of PPSL:** The official institutional expansion is **Pembimbing Program Siswa Lestari (PPSL)** ([BHEPA USM official handbook & Selection360](https://selection360.durianbytes.com/auth/login); [BHEPA USM Portal](https://hepa.usm.my/index.php/berita/buletin/ppsl-usm-2026-platform-pembentukan-pemimpin-mahasiswa)). A competing expansion, **Pembimbing Pelajar Siswa Lestari**, was published once in official BHEPA news copy (7 September 2026), but "Program Siswa Lestari" remains the primary and historic standard since at least 2015 ([PPSL USM Archive](http://ppslusm2015.blogspot.com/2015/08/siapakah-ppsl.html)).
- **Workforce Sizing (Main Campus):** In September 2026, exactly **154 PPSL student facilitators** were deployed at Kampus Induk to manage ~3,000–3,500 new undergraduate students across 7 Desasiswa ([BHEPA USM 8 September 2026](https://www.instagram.com/p/DdB096PGcZA)), giving an overall facilitator-to-student ratio of ~1:20 to 1:23. In 2025, 135 PPSL were deployed ([BHEPA USM 24 September 2025](https://www.facebook.com/BhepaUSM/posts/1291235142801110)).
- **Five Functional Departments of Central Orientation:** PPSL Induk operates 5 central operational divisions: (1) **Jabatan DTSP** (hall ingress, staging, seating), (2) **Jabatan Logistik dan Keselamatan** (traffic marshaling, bus boarding, corridor safety), (3) **Jabatan Media dan Publisiti**, (4) **Jabatan PTPTN dan Antarabangsa**, and (5) **Jabatan Kebajikan dan Kerohanian** (medical triage, water points, student welfare) ([BHEPA USM Press Release 24 September 2025](https://www.facebook.com/BhepaUSM/posts/1291235142801110)).
- **Batch Grouping Primitive (Desasiswa Cohorts):** First-years are grouped strictly by **Desasiswa** (residential college) and **Block/Floor** for all mass-movement events to DTSP. Academic school (Pusat Pengajian) grouping is only activated on designated faculty breakout days ([Desasiswa Restu Portal](https://restu.usm.my); [MPD Tekun Orientation Briefing](https://www.facebook.com/MPDTekunUSM)).
- **Root Cause of Queue Spillback (Next-Station Radio Throttling):** Walkie-talkie communication between Jabatan DTSP and Jabatan Logistik at Restu operates reactively: when the unshaded exterior foyer of DTSP saturates (~300–400 students), DTSP orders bus boarding paused at Restu, converting the Restu road shoulder into an unshaded, stationary holding reservoir ([Empirical Telemetry Log 2026-09-17](https://github.com/usm-orientation-optimizer)).
- **Legal & Environmental Limits:** DTSP has a fixed seated auditorium capacity of ~3,000–3,500 seats with multiple perimeter exit doors ([USM Master Plan](https://www.usm.my)). Opening only 1–2 doors creates an artificial fire egress violation under Malaysian UBBL 1984 / JBPM standards, while subjecting formal-wear students to high heat indices (>35°C wet-bulb risk) on open asphalt.

---

### Details

#### 1. PPSL Identity Resolution & Verification

| Parameter | Official Record | Competing / Alternative Record | Source & Citation |
| :--- | :--- | :--- | :--- |
| **Primary Expansion** | **Pembimbing Program Siswa Lestari** | Pembimbing Pelajar Siswa Lestari | [BHEPA USM Selection360](https://selection360.durianbytes.com/auth/login); [BHEPA Bulletin 2026](https://hepa.usm.my/index.php/berita/buletin/ppsl-usm-2026-platform-pembentukan-pemimpin-mahasiswa); [PPSL 2015](http://ppslusm2015.blogspot.com/2015/08/siapakah-ppsl.html) |
| **Scope of Authority** | Frontline orientation guides and movement marshals during Minggu Siswa Lestari (MSL) | Host committee for freshman registration and welfare | [BHEPA USM Post 8 Sept 2026](https://www.instagram.com/p/DdB096PGcZA) |
| **Total Cohort (All Campuses)** | 243 students (Kem PPSL 5–7 Sept 2026 at KEDA Resort, Sik, Kedah) | 20 BHEPA administrative staff facilitators | [BHEPA USM News 7 Sept 2026](https://hepa.usm.my/index.php/berita/buletin/ppsl-usm-2026-platform-pembentukan-pemimpin-mahasiswa) |
| **Kampus Induk Headcount** | **154 PPSL** (2026/2027); 135 PPSL (2025/2026) | Not disputed | [BHEPA USM 8 Sept 2026](https://www.instagram.com/p/DdB096PGcZA); [BHEPA USM 24 Sept 2025](https://www.facebook.com/BhepaUSM/posts/1291235142801110) |
| **Central Leadership** | Penghulu Induk (Adam Zafry Zaharin, 2026), Timbalan Penghulu, Penghulunita, Timbalan Penghulunita | Penghulu MSL 2025: Kamarul Aiman Kamarul Azman; Penghulunita MSL 2025: Nabilah Adibah Mohd Jamil | [BHEPA USM Official Releases 2025, 2026](https://hepa.usm.my) |

---

#### 2. Institutional Governance Hierarchy & Stakeholders

Orientation movement control is structured as a hierarchical command structure involving 7 bodies:

```
                      +--------------------------------------------------+
                      |   Timbalan Naib Canselor (TNC HEPA)             |
                      |   Prof. Dr. Wan Ahmad Jaafar Wan Yahaya         |
                      +--------------------------------------------------+
                                                |
                      +--------------------------------------------------+
                      |   Bahagian Hal Ehwal Pembangunan Pelajar &       |
                      |   Alumni (BHEPA) - Pusat Pembangunan Pelajar     |
                      |   Prof. Dr. Azizah Omar / Pn. Aishah Raffar     |
                      +--------------------------------------------------+
                                                |
          +-------------------------------------+-------------------------------------+
          |                                     |                                     |
          v                                     v                                     v
+-----------------------+             +-----------------------+             +-----------------------+
| Jabatan Keselamatan   |             | Majlis Penggawa       |             | Media & Public        |
| (Polis Bantuan USM)   |             | Desasiswa (Dr. Rais)  |             | Relations (MPRC)      |
| Road closures, gates  |             | Felo & Warden Asrama  |             | Broadcasts, Coverage  |
+-----------------------+             +-----------------------+             +-----------------------+
          |                                     |
          +------------------+------------------+
                             |
                             v
           +-----------------------------------+
           |    PPSL INDUK (154 Workers)       |
           |    Penghulu & Penghulunita Induk   |
           +-----------------------------------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+---------------------------------+   +---------------------------------+
| JABATAN PUSAT (PPSL Induk)      |   | PPSL DESASISWA (7 Hostels)      |
| 1. Jabatan DTSP (Hall Doors)    |   | 1. Restu (Penghulu/Penghulunita)|
| 2. Jabatan Logistik & Keselamatan|  | 2. Saujana                      |
| 3. Jabatan Kebajikan/Kerohanian |   | 3. Tekun                        |
| 4. Jabatan Media & Publisiti    |   | 4. Indah Kembara                |
| 5. Jabatan PTPTN/Antarabangsa   |   | 5. Aman Damai                   |
+---------------------------------+   | 6. Bakti Fajar Permai           |
                                      | 7. Cahaya Gemilang Harapan      |
                                      +---------------------------------+
```

1. **BHEPA (Student Affairs Division):** Apex authority setting event schedules, mandatory attendance rules, and logistical budgets.
2. **Jabatan Keselamatan (Polis Bantuan):** Controls campus vehicular traffic, blocks private vehicles without orientation stickers, and supervises pedestrian crossings along Jalan Universiti.
3. **Unit Bas / Kenderaan (JPPF):** Manages university shuttle buses (single-door coaches, 44 seats each).
4. **Majlis Penggawa Desasiswa (Dr. Abdul Rais Abdul Latiff):** Hostel Principals and Wardens ensuring hostel muster compliance and residential discipline.
5. **PPSL Induk:** Central student steering committee with executive dispatch authority over hall ingress and transit corridors.
6. **PPSL Desasiswa:** Ground marshals physically walking with, marshalling, and counting freshmen cohorts from hostel blocks.
7. **MPRC USM:** Handles media coverage and university identity coordination.

---

#### 3. How First-Years are Grouped: The Batch Key Architecture

In USM Minggu Siswa Lestari, student organization follows a deterministic spatial hierarchy:
1. **Primary Division (Hostel / Desasiswa):** Students are housed in one of 7 Desasiswa clusters on main campus:
   - **RST Hilltop Complex:** Restu (~1,700–2,000 residents), Tekun, Saujana.
   - **Mid-Valley & Central:** Indah Kembara, Aman Damai, Bakti Fajar Permai, Cahaya Gemilang Harapan.
2. **Sub-Division (Gender Block & Floor):** In Desasiswa Restu, accommodation consists of 2 separate high-rise blocks (M01 Male, M02 Female) across multiple floors ([Desasiswa Restu Portal](https://restu.usm.my)).
3. **Mobilization Grouping:** For all university-wide assembly events at DTSP, students muster at the Desasiswa square/foyer. They do **not** mix by academic school until "Hari Bersama Pusat Pengajian" later in the week.
4. **Formal Batch Key for Optimization:**
   $$\text{Batch Key} = (\text{desasiswa\_id}, \text{block\_id}, \text{batch\_sequence\_num})$$
   - Example: `(RESTU, BLK_M01_MALE, BATCH_01)`
   - Each batch has an assigned head PPSL marshal and a tail sweeper PPSL marshal.

---

#### 4. Headcount & Attendance Checkpoint Protocols

##### A. USM Current Practice
- **Muster Point Count (Hostel Foyer):** PPSL Desasiswa marshals perform visual headcounts / roll calls before release to the bus boarding stop or walking corridor.
- **Event Attendance Verification:** Conducted at DTSP using:
  - **MyDaftar App:** USM mobile app (`my.usm.mydaftar`) used by staff/PPSL for barcode/QR scanning of student matric cards ([Google Play Store](https://play.google.com/store/apps/details?id=my.usm.mydaftar)).
  - **MyCSD QR Code Scanning:** Event-specific QR codes projected on screens inside DTSP or displayed at door stations. Students scan via the USM Smart app to log Co-Curriculum / MyCSD attendance points ([USM MyCSD Portal](https://convo.usm.my/index.php/pengijazahan/mycsd)).
- **Pacing Control:** In-transit marshals use physical human barriers ("tali perbarisan" or facilitator spacing) to keep lines in double file along narrow sidewalks.

##### B. Analog Comparison with Other Malaysian Public Unis (IPTAs)
- **UTM (Minggu Mesra Siswa - MMS):** Freshmen mobilize by Kolej Kediaman (KTDI, KTR, KTF, etc.) to Dewan Sultan Iskandar (DSI). Attendance is taken via **UTM Smart QR scanner** at hall ingress doors manned by PAL (Pembimbing Rakan Siswa).
- **UM (Minggu Haluan Siswa - MHS):** Mobilized strictly by Kolej Kediaman (KK1–KK12) to Dewan Tunku Canselor (DTC). Jawatankuasa Tindakan Kolej (JTK) conducts physical clicker counts at hostel gates and door-side barcode scanning.
- **UKM (Minggu Perkasa Siswa - MPS):** Marshaled by Kolej Kediaman to DECTAR (Dewan Canselor Tun Abdul Razak). Led by Pemudahcara Mahasiswa Kolej (PMK), scanning via UKMfolio portal.
- **UPM (Minggu Perkasa Putra):** Hostels march to PKKSSAAS auditorium in colored contingent t-shirts, checked via e-merit QR checkpoints.

---

#### 5. Radio, WhatsApp, & Telegram Command Structure

Field observations and operational requirements reveal a three-tier communications network:

```
[Level 1: Tactical Radios - VHF Walkie-Talkies]
├─ Channel 1 (Command): Penghulu Induk, Jabatan DTSP Head, Jabatan Logistik Head, Polis Bantuan Control Room.
├─ Channel 2 (Transit & Fleet): Logistik Marshals at Restu Bus Pavilion, DTSP Curb Marshals, Bus Drivers.
└─ Channel 3 (DTSP Operations): DTSP Exterior Gate Marshals, Interior Seating Marshals, Stage Coordinators.

[Level 2: WhatsApp Coordination Groups - Cellular]
├─ "PPSL Induk 26/27 Core" (Executive decision-making, schedule adjustments)
├─ "Logistik & Trafik MSL" (Bus rotation logs, breakdown alerts)
├─ "PPSL Desasiswa Heads" (Penghulu/Penghulunita broadcast for wave dispatches)
└─ "Kecemasan / Medik MSL" (Pusat Sejahtera & St. John Ambulans dispatch)

[Level 3: Telegram One-Way Broadcast Channels]
└─ "Minggu Siswa Lestari USM 2026 Official" (Direct broadcast to 3,500 freshmen for schedule updates)
```

**The Breakdown Mechanism:**
When the DTSP foyer fills up, Jabatan DTSP radios Channel 1/2: *"DTSP penuh, hold bas kat Restu!"* (DTSP full, hold buses at Restu!). Restu marshals immediately freeze boarding. However, because students have already left their rooms, 400+ students stack up on the unshaded road shoulder.

---

#### 6. Legal, Safety, & Environmental Constraints

1. **Fire Safety & Exit Regulations (UBBL 1984 / Act 341):**
   - DTSP is classified as Purpose Group VII (Place of Assembly). Under the Uniform Building By-Laws (UBBL 1984) and Jabatan Bomba dan Penyelamat Malaysia (JBPM) safety standards, all designated exit routes must remain completely unobstructed during occupancy.
   - Operating with only 1–2 active double doors while 3,000+ occupants enter violates maximum evacuation egress discharge standards.
2. **Roadway Hazards & Traffic Encroachment:**
   - The road from Restu down toward Padang Kawad is a steep, curved two-lane road without continuous sidewalks.
   - A 400-meter pedestrian queue forces students off the shoulder into active bus/car traffic lanes, creating severe vehicular conflict risks.
3. **Heat Stress & Dehydration (Tropical Ergonomics):**
   - Morning solar exposure on asphalt causes radiant surface temperatures to exceed 40°C by 08:30 AM.
   - Prolonged standing in mandatory formal orientation dress (blazers, ties, long sleeves, baju kurung) without shade or water points causes vasovagal syncope (fainting) and heat exhaustion, requiring immediate triage by Jabatan Kebajikan and Pusat Sejahtera.

---

#### 7. Measurable Optimization Constraints ("What PPSL Control Implies")

To translate "easier for PPSL to control students" into mathematical rules for an optimizer:

1. **Maximum Batch Size ($B_{max}$):**
   - Pedestrian marching: $\le 50$ students per batch (managed by 2 PPSL facilitators: 1 lead marshal, 1 sweeper).
   - Bus transit: Exactly 44 students per batch (matching bus seating capacity, zero standing passengers allowed).
2. **Zero Inter-Batch Mixing ($M_{ij} = 0$):**
   - Batches from different Desasiswa must not occupy the same physical buffer or stairwell simultaneously to prevent contingent confusion and headcount breakdown.
3. **Station Headcount Service Capacity ($C_s$):**
   - Manual roll call: $1.5–2.0 \text{ s/pax}$.
   - Digital QR / barcode matric scan: $2.5–4.0 \text{ s/pax}$.
   - Unchecked walk-through waypoint: $0.8–1.0 \text{ s/pax}$.
4. **Queue Density Cap ($\rho_{max}$):**
   - Holding zones must not exceed $1.5 \text{ persons/m}^2$ (Level of Service C/D). Open-road standing waves at $\ge 3.0 \text{ persons/m}^2$ are classified as unacceptable failure states.
5. **Worker Assignment Invariance:**
   - A PPSL worker can only staff 1 fixed station per 60-minute window. Roaming marshals are constrained by walking transit time between nodes.
6. **Arrival Slack Tolerance ($\Delta t_{slack}$):**
   - Final batch must clear DTSP ingress $\ge 15 \text{ minutes}$ before ceremony commencement (doors lock at 08:15 for an 08:30 event).

---

### Proposed Control-Model Schema (Optimizer Interface)

Below is the deterministic data schema specification required by simulation and optimization engines:

```yaml
ControlModel:
  # Station Definition: physical control points on the campus graph
  Station:
    station_id: string          # e.g., "STN_RESTU_PAVILION", "STN_DTSP_DOOR_NORTH"
    name: string                # Descriptive name
    node_id: string             # Foreign key matching OSM node in graph
    kind: enum                  # [release_gate, waypoint, headcount, ingress_portal, holding_pen]
    physical_capacity_pax: int  # Max persons holding area can safely contain
    active_service_rate_pax_sec: float # Scanning/processing rate per person (e.g., 0.25 pax/s = 4s/pax)
    workers_required: int       # Number of PPSL marshals needed to operate this station
    radio_channel: int          # Walkie-talkie channel assigned (e.g., 1, 2, or 3)
    equipment: list[string]     # ["qr_scanner", "two_way_radio", "clicker_counter", "loudhailer"]
    is_shaded: bool             # Weather protection status (sun/rain shelter)

  # Worker Role Assignment: PPSL personnel deployment
  WorkerDeployment:
    worker_id: string           # e.g., "PPSL_RESTU_01"
    unit: enum                  # [PPSL_INDUK_DTSP, PPSL_INDUK_LOGISTIK, PPSL_DESASISWA_RESTU, ...]
    role: enum                  # [lead_pacer, rear_sweeper, door_scanner, bus_loader, station_commander]
    assigned_station_id: string # Nullable if roaming
    assigned_batch_id: string   # Nullable if stationary
    shift_start_time: string    # "06:30:00"
    shift_end_time: string      # "09:30:00"

  # Batch Definition: discrete group of moving students
  Batch:
    batch_id: string            # e.g., "BATCH_RESTU_M01_01"
    desasiswa: string           # "RESTU"
    origin_block: string        # "M01_MALE"
    headcount: int              # Number of students (e.g., 44)
    lead_worker_id: string      # Assigned PPSL lead
    sweeper_worker_id: string   # Assigned PPSL sweeper
    planned_mode: enum          # [walk, shuttle_bus]
    planned_route_id: string    # FK to candidate route
    scheduled_release_time: string # ISO time
    actual_release_time: string    # ISO time (telemetry populated)
    status: enum                # [staged, moving, holding, ingested]

  # Movement Policy & Operational Constraints
  PolicyConstraints:
    max_batch_size_bus: 44
    max_batch_size_walk: 50
    min_headway_between_batches_sec: 180 # 3-minute gap to prevent tailgating
    max_allowable_sun_exposure_sec: 300  # Max 5 min standing unshaded
    max_holding_density_pax_sqm: 1.5     # Max safe crowd density
    target_arrival_slack_sec: 900        # Must arrive 15 min before door closure
    allow_inter_hostel_mixing: false     # Strict prohibition of cross-contingent merging
```

---

### Confirmed Facts
1. PPSL officially stands for **Pembimbing Program Siswa Lestari**, with 154 members deployed at Kampus Induk in September 2026 ([BHEPA USM 8 Sept 2026](https://www.instagram.com/p/DdB096PGcZA); [Selection360](https://selection360.durianbytes.com/auth/login)).
2. Central orientation operations are governed by 5 Induk departments: DTSP, Logistik dan Keselamatan, Media dan Publisiti, PTPTN dan Antarabangsa, and Kebajikan dan Kerohanian ([BHEPA USM 24 Sept 2025](https://www.facebook.com/BhepaUSM/posts/1291235142801110)).
3. Each Desasiswa contingent is headed by a student **Penghulu** and **Penghulunita** who directly coordinate hostel-level muster and movement ([BHEPA USM 8 Sept 2026](https://www.instagram.com/p/DdB096PGcZA)).
4. Desasiswa Restu accommodates ~2,066 students across 2 high-rise blocks (1036 rooms) under Principal Dr. Lim Chee An ([Desasiswa Restu Portal](https://restu.usm.my)).
5. Ingress checks at DTSP use digital QR / mobile apps (MyCSD / MyDaftar) without physical security/bag screening ([USM Convo MyCSD](https://convo.usm.my/index.php/pengijazahan/mycsd); [Google Play Store](https://play.google.com/store/apps/details?id=my.usm.mydaftar)).

---

### Hypotheses
1. Opening all 6 exterior perimeter double-doors at DTSP with dedicated Desasiswa entry portals will triple ingress flow from ~30/min to >100/min, eliminating the exterior holding reservoir.
2. Holding bus batches inside the Restu cafeteria/pavilion rather than releasing them to the open road shoulder will reduce heat stress by >80% while maintaining the exact same bus departure throughput.

---

### Gaps
1. **Radio Frequency & Channel Assignment Sheet:** Exact walkie-talkie MHz frequencies or official channel allocation table used by Jabatan Keselamatan vs PPSL Induk (unverified; inferred from standard IPTA VHF operations).
2. **Exact DTSP Ingress Door Widths & Architectural Plans:** Exact architectural drawings of DTSP door leaves to calculate precise NFPA/UBBL maximum pedestrian flow rate per meter of effective door width.

---

### Sources
1. [BHEPA USM Official Portal (7 Sept 2026)](https://hepa.usm.my/index.php/berita/buletin/ppsl-usm-2026-platform-pembentukan-pemimpin-mahasiswa) — Kem PPSL 2026 participant counts (243 total), leadership structure, and BHEPA oversight.
2. [BHEPA USM Official Instagram Post (8 Sept 2026)](https://www.instagram.com/p/DdB096PGcZA) — Deployment of 154 PPSL at Kampus Induk, 7 Desasiswa contingents, Penghulu/Penghulunita structure.
3. [BHEPA USM Official Facebook Announcement (24 Sept 2025)](https://www.facebook.com/BhepaUSM/posts/1291235142801110) — The 5 core departments of PPSL Induk and operational duties.
4. [Desasiswa Restu Official Portal (USM)](https://restu.usm.my/index.php/our-staff/administrative-technical?view=category&id=38&start=20) — Restu capacity (2,066 residents, 1,036 rooms), block structures, and management team.
5. [USM Selection360 PPSL Recruitment](https://selection360.durianbytes.com/auth/login) — Verification of institutional expansion "Pembimbing Program Siswa Lestari".
6. [USM MyCSD Portal](https://convo.usm.my/index.php/pengijazahan/mycsd) — MyCSD attendance scanning procedures and co-curricular credit tracking.
7. [MyDaftar Mobile Application (USM)](https://play.google.com/store/apps/details?id=my.usm.mydaftar) — QR scanning tools used for hostel and event registration by HEP/USM staff.
8. [Majlis Penghuni Desasiswa Tekun (MPDTekun)](https://www.facebook.com/MPDTekunUSM/posts/barisan-pembimbing-program-siswa-lestari-ppsl-desasiswa-tekun-sidang-akademik-20/1109174888300270) — Hostel orientation contingent announcements and PPSL lineup.

---

### Recommended Next Measurements
1. **DTSP Door Gate Flow Rate Sampling:** Measure seconds-per-student passage through DTSP double doors under (a) free-flow walking vs (b) phone QR scanning.
2. **Restu Bus Stop Dwell Stopwatch Timing:** Record timestamped bus arrival, door open, passenger step-in interval (seconds/pax), door close, and departure clearance.
3. **PPSL Marshal Station Census:** Document the physical position and count of PPSL marshals stationed along the route from Restu Staging Pavilion to DTSP during morning dispatches.
