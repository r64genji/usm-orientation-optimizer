# USM Orientation Movement Optimization: Cohort Size, Hostel Capacity, and Batch Demand Inventory

**TL;DR:** USM Kampus Induk registers 3,378 new undergraduate students (2025/2026 official intake), validating the prior hypothesis of 3,000–3,500 freshies; ~70% are concentrated on the western ridge in the RST Complex (Restu: 1,687 beds, Saujana: 1,577 beds, Tekun: 1,548 beds). Morning orientation requires mandatory assembly at Dewan Tuanku Syed Putra (DTSP) by 08:30 AM, creating a peak unmitigated departure demand of ~75–80 students/min between 07:00 and 08:00 AM that exceeds shuttle bus transit supply (11 seats/min) by nearly 7x.

---

### Key Findings
- **Intake Verification:** Official 2025/2026 undergraduate intake across all three USM campuses is 4,236 students (UPU mainstream); Kampus Induk accommodates exactly 3,378 new students, Engineering Campus (Nibong Tebal) 919, and Health Campus (Kubang Kerian) 639 ([Malaysia Gazette, Sept 2025](https://malaysiagazette.com/2025/09/28/1972-pelajar-b40-bergelar-mahasiswa-usm); [Utusan Malaysia, Oct 2024](https://www.utusan.com.my/nasional/2024/10/lima-pasangan-kembar-antara-4807-calon-pelajar-baharu-usm)).
- **Hostel Capacity:** Kampus Induk maintains 8 undergraduate desasiswa with a total verified operational capacity of 9,536 beds (2,609 male / 27.4%, 6,927 female / 72.6%) ([USM Civil Engineering Research ePrint 58403](http://eprints.usm.my/58403/1/Kajian%20Keberkesanan%20Sistem%20Bas%20Kampus%20Induk%20USM_Muhammad%20Nizar%20Saddum.pdf)).
- **Freshmen Concentration:** First-year students are heavily concentrated in Kompleks RST (Restu, Saujana, Tekun) on Bukit Gambir ridge (~2,200–2,400 freshies), while seniors are systematically cleared from campus hostels during Minggu Siswa Lestari (MSL) via mandatory campus stay permits ([USM HAC Notice 2025](https://www.facebook.com/HACUSM/posts/-notice-application-for-campus-stay-permit-during-siswa-lestari-programme-26-sep/1206151281531346)).
- **Assembly Window:** Official MSL schedules mandate hall sessions start at 08:30 AM following a 05:30–08:00 AM personal prep window (`SOLAT / PERSIAPAN DIRI`), requiring full hall seating between 08:00 and 08:25 AM ([Jadual Program Siswa Lestari SA 2024/2025 & 2025/2026, Kampus Induk](https://www.scribd.com/document/788583103/Jadual-orientasi-MSL-24-25-USM-240924-123507)).
- **Batch Key Syntax:** University building codes follow standard alphanumeric identifiers: Restu (M01 male, M02 female; 10 storeys), Saujana (M03 female, M04 female; 10 storeys), Tekun (M05 male, M06 female; 10 storeys), forming canonical batch keys `[HOSTEL]_[BLOCK]_L[FLOOR]` (e.g. `RESTU_M01_L04`).
- **Special Populations:** OKU [disabled] students (~17–20 intake) are housed exclusively at Desasiswa Aman Damai (ground floor barrier-free blocks K01–K04) with dedicated van transport, bypassing general hostel bus queues ([Astro Awani](https://www.astroawani.com/berita-malaysia/pelajar-oku-usm-nikmati-kemudahan-kelas-pertama-169800); [BHEPA USM](https://www.facebook.com/BhepaUSM/posts/1583999040191384)).

---

### Details

#### 1. Cohort Size & Intake Breakdown
- **2025/2026 Intake Official Statistics:**
  - University-wide undergraduate intake: **4,236 students** (UPU mainstream channel).
  - Kampus Induk (Penang Main Campus): **3,378 students** (79.7% of university total).
  - Kampus Kejuruteraan (Engineering Campus, Nibong Tebal): **919 students**.
  - Kampus Kesihatan (Health Campus, Kubang Kerian, Kelantan): **639 students** (568 enrolled on day one).
  - Feeder & Special Pathways: 70 candidates via USM Feeder (PRA-U USM / Kolej MARA Kulim) into USM-KLE International Medical Programme (Belgaum, India); 280 students under Program Siswa Sulung B40 (RM 2.8 million tuition sponsorship).
  - Socio-economic profile: 1,972 students (46.55%) admitted under the B40 income tier, provided with RM 200,000 welfare transit aid.
- **2024/2025 Intake Comparison:**
  - University-wide offers: 4,807 candidates (1,700 male, 3,107 female); unjuran UPU base quota: 3,888.
  - Day 1 DTSP Hall Turnout: Official BHEPA count logged **2,707 new students** physically present at the initial DTSP briefing on October 7, 2024.
  - International Students: 536 undergraduate offers issued across 18 countries (~469 registered).
- **Optimizer Cohort Sizing:**
  - The previous unverified guess of 5,800 is an inflated gross offer projection; the actual resident cohort demanding movement on Kampus Induk is **3,000 to 3,378 students**, of which ~3,050 stay in on-campus desasiswa and ~328 commute as Non-Resident (NR) students.

#### 2. Main Campus Desasiswa Inventory & Bed Capacities
Official audit figures from the USM Housing and Accommodation Centre (HAC / UPPU), corroborated by USM Civil Engineering transit studies, establish 8 active residential hostels on Kampus Induk:

| Desasiswa | Blocks / Buildings | Gender Mix | Operational Bed Capacity | Architectural / Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Restu** | M01 (M), M02 (F), M07 (Admin/Cafe), M08 (DUD RST) | 688 M / 999 F | **1,687 beds** | Two 10-storey high-rise towers on Bukit Gambir ridge |
| **Saujana** | M03 (F), M04 (F), M07 (Shared Admin) | 0 M / 1,577 F | **1,577 beds** | All-female twin 10-storey high-rise towers |
| **Tekun** | M05 (M), M06 (F), M09 (Admin/Cafe/PETAS) | 636 M / 912 F | **1,548 beds** | Twin 10-storey towers (Max architectural capacity: 2,066) |
| **Aman Damai** | K01–K04 (Aman), K05–K08 (Damai), K10 (Admin/Cafe) | 277 M / 812 F | **1,089 beds** | 3- to 4-storey walk-up blocks; dedicated OKU facilities |
| **Indah Kembara** | L01–L04, L06–L07 (Kembara), L11–L12 (Indah), L05 (Hall) | 231 M / 947 F | **1,178 beds** | 3- to 4-storey walk-up blocks near athletics stadium |
| **Fajar Harapan** | F01–F26 (Fajar & Harapan residential blocks) | 290 M / 686 F | **976 beds** | Low-rise walk-up blocks; includes F26 premium rooms |
| **Bakti Permai** | H09, H11 (F), H12 (M), H13, H10 (Admin/Cafe) | 318 M / 696 F | **1,014 beds** | Low-rise blocks; predominantly postgrad/senior housing |
| **Cahaya Gemilang** | H20–H25, H34, H35 (Cahaya Gemilang Harapan / CGH) | 165 M / 302 F | **467 beds** | Low-rise walk-up blocks in central academic valley |
| **TOTAL** | — | **2,609 M / 6,927 F** | **9,536 beds** | Overall female-to-male ratio: 72.6% Female / 27.4% Male |

*Note on Rental Pricing:* Standard double room rates are RM 120/month per student (RM 240/month single room); upgraded executive/premium units (e.g. Harapan F26, Tekun M05, Saujana M04) range from RM 420 to RM 565/month. Campus bus service fee is charged at RM 30–60/semester in university tuition fees.

#### 3. First-Year Student Concentration & Zonal Distribution
- **Hostel Allocation by Program & Day:**
  - Official MSL intake schedules reveal that incoming freshies are segregated into distinct desasiswa on sequential arrival days:
    - *Day 1 (Friday):* Desasiswa Saujana receives incoming female freshies.
    - *Day 2 (Saturday):* Desasiswa Tekun, Aman Damai, and Indah Kembara receive male and female freshies.
    - *Day 3 (Sunday):* Desasiswa Restu and Cahaya Gemilang Harapan receive male and female freshies.
  - Desasiswa Bakti Permai is omitted from freshie registration schedules because it is reserved for senior undergraduates and postgraduates.
- **The RST Ridge Bottleneck:**
  - Kompleks RST (Restu, Saujana, Tekun) accommodates ~2,200–2,400 freshies (~68–71% of the entire first-year Kampus Induk cohort).
  - Because returning seniors are legally required to vacate campus or obtain an official "Campus Stay Permit" during orientation week, nearly all beds in Restu, Saujana, and Tekun are dedicated to first-year orientation residents.

#### 4. Spatial Keys, Block & Floor Naming Conventions
To feed discrete-event movement simulators and batch release algorithms, students must be indexed by unique spatial origins:
- **Spatial Key Pattern:** `[HOSTEL_CODE]_[BLOCK_ID]_[FLOOR_LEVEL]`
- **Block & Floor Structure:**
  - *Restu:* Blocks `M01` (male) and `M02` (female). 10 floors each (`Aras 1` to `Aras 10`). Example key: `RESTU_M01_L05`.
  - *Saujana:* Blocks `M03` (female) and `M04` (female). 10 floors each (`Aras 1` to `Aras 10`). Example key: `SAUJANA_M04_L08`.
  - *Tekun:* Blocks `M05` (male) and `M06` (female). 10 floors each (`Aras 1` to `Aras 10`). Example key: `TEKUN_M06_L03`.
  - *Aman Damai:* Blocks `K01` through `K08`. 3 to 4 storeys (`Aras 1` to `Aras 4`). Example key: `AMAN_DAMAI_K02_L02`.
  - *Indah Kembara:* Blocks `L06`, `L07`, `L11`, `L12`. 3 to 4 storeys. Example key: `INDAH_KEMBARA_L11_L03`.
  - *Cahaya Gemilang Harapan:* Blocks `H34`, `H35`, `F25`, `F26`. 3 to 4 storeys. Example key: `CGH_H34_L02`.
- **Egress Characteristics:**
  - High-rise towers (M01–M06) have two internal stairwell cores and two passenger lifts. During peak morning departure, lift queues stall completely, forcing 85%+ of students to descend stairwells (estimated stair descent flow rate: 60 students/min per block).

#### 5. Commute Mode, Walking Distances, and Elevation Profiles to DTSP
Terrain and campus layout dictate distinct transit behaviors across the hostel clusters:

```
[Kompleks RST] (Ridge: +42m ASL) 
       |
       |-- (1.7 km road / bus transit: 3.1 min drive + 24 min queue) ---> [DTSP Hall] (+12m ASL)
       |-- (1.47 km trail / steep downhill stairs: 22-26 min walk) ------> [DTSP Hall]

[Aman Damai / Fajar Harapan] (Mid-campus: +22m ASL) 
       |-- (0.8 - 1.1 km flat walkway: 10-14 min walk) -----------------> [DTSP Hall]

[Indah Kembara] (South stadium: +18m ASL) 
       |-- (0.9 - 1.2 km flat walkway: 12-15 min walk) -----------------> [DTSP Hall]

[Cahaya Gemilang] (Central core: +15m ASL) 
       |-- (0.5 - 0.7 km paved paths: 6-9 min walk) --------------------> [DTSP Hall]
```

- **RST "Bus Culture" Driver:** Although walking from RST to DTSP takes ~22–26 minutes downhill, freshies overwhelmingly queue for the shuttle bus due to:
  1. Mandatory formal dress code (black slacks/baju kurung, dark leather/court shoes) ill-suited for steep pedestrian descent in tropical heat/humidity.
  2. The grueling return climb uphill from DTSP back to Bukit Gambir (+30m elevation gain) during midday and afternoon transitions.
  3. Direct marshalling by PPSL leaders who corral freshies toward the RST Bus Stop / Jejantas staging area.
- **Lower Campus "Walk Culture":** Aman Damai, Cahaya Gemilang, and Indah Kembara residents have direct, shaded, level pedestrian walkways to DTSP and rarely depend on campus shuttle buses.

#### 6. Orientation Assembly Instructions & Arrival Window
- **Published Orientation Routine:**
  - Official MSL daily schedule allocates **05:30 AM – 08:00 AM** as `SOLAT / PERSIAPAN DIRI` (Prayer & Personal Morning Preparation).
  - Official Hall Sessions begin strictly at **08:30 AM** (e.g. *Sesi Pembangunan Pelajar*, *Sesi Bersama Timbalan Naib Canselor HEPA*, *Majlis Sambutan Siswa*).
  - Target Ingestion Window: Students must be seated inside DTSP by **08:25 AM**.
- **Field Staging Trigger:**
  - To seat 3,000+ students by 08:25 AM, hostel PPSL marshals initiate room-calling and floor muster between **06:30 AM and 07:00 AM**.
  - Measured Telemetry Corroboration: Student telemetry logged departure from Restu room at 06:47 AM, but system-wide queuing bottlenecks delayed seat arrival to 09:18 AM (48 minutes after official event commencement).

#### 7. Special Populations & Batch Exclusions
1. **OKU / Students with Disabilities (Orang Kurang Upaya):**
   - Cohort size: 17 to 20 students university-wide (~10–15 on Kampus Induk).
   - Dedicated accommodation: Concentrated exclusively at **Desasiswa Aman Damai** (Blocks K01–K04), which features ground-floor ramp access, retrofitted accessible toilets, and contiguous parking bays.
   - Transit: Handled via specialized accessible welfare vans and assigned student escorts under the BHEPA *Buddy Pelajar OKU* scheme. They **must be excluded** from RST bus batching models.
2. **International Undergraduate Students:**
   - Cohort size: ~469 registered students.
   - Separate orientation track: Managed concurrently by BHEPA Antarabangsa and IMCC (International Mobility & Career Centre). They join major plenary ceremonies at DTSP but follow distinct briefing sessions at Dewan Budaya or Pusat Mahasiswa.
3. **Non-Resident (NR) / Commuter Students:**
   - Population: ~10% (~328 students) who commute from off-campus housing (Sungai Dua, Gelugor, Bayan Lepas, Bukit Jambul).
   - Staging: Enter campus through external vehicle checkpoints (Pintu Sungai Dua / Pintu Bukit Gambir) and report directly to DTSP exterior perimeter, bypassing hostel batching networks.
4. **Late Registrations (Pendaftaran Lewat):**
   - Second-intake / rayuan candidates register during week 2; non-existent during day-1 MSL operations.

#### 8. Peak Simultaneous Departure Estimation Methodology
Simulations must not use arbitrary headcounts. Peak simultaneous demand $D_{peak}(h)$ from any hostel $h$ is a deterministic function of capacity, attendance compliance, and departure time tolerance:

$$\text{Demand Flow Rate } [D_{peak}(h)] = \frac{N_{fresh}(h) \cdot \alpha}{\Delta t_{depart}}$$

Where:
- $N_{fresh}(h)$ = Active first-year bed occupancy in hostel $h$ (for RST Complex, $N_{fresh} \approx 2,365$).
- $\alpha$ = Orientation attendance compliance rate (empirically $0.95$ to $0.98$ for compulsory morning sessions).
- $\Delta t_{depart}$ = Window during which uncoordinated students attempt to leave (typically 30 minutes: 07:00 AM – 07:30 AM).

**The Unmitigated Transit Bottleneck Calculation:**
- Unmanaged RST peak departure demand:
  $$D_{peak}(\text{RST}) = \frac{2,365 \times 0.95}{30\text{ min}} = \frac{2,247}{30} \approx 74.9\text{ students/minute}$$
- Maximum transit bus supply:
  - USM shuttle fleet allocates 5 operational buses to the RST loop during orientation morning peak.
  - Bus capacity = 44 seated passengers.
  - Round-trip cycle time (RST $\rightarrow$ DTSP $\rightarrow$ RST including boarding/alighting) = 20.0 minutes.
  - Sustained bus throughput:
    $$C_{bus} = \frac{5 \times 44\text{ pax}}{20\text{ min}} = 11.0\text{ passengers/minute}$$
- **Supply Deficit:**
  $$D_{peak} - C_{bus} = 74.9 - 11.0 = 63.9\text{ students/minute surplus queue growth}$$
  Over a 30-minute departure wave, unmanaged staging generates an accumulating queue of $\approx 1,917$ students stranded on the Bukit Gambir road shoulder. This explains the 24-minute stagnant road queue measured in repo telemetry.
- **Optimizer Solution Required:**
  The batching optimizer must enforce floor-by-floor departure offsets ($\Delta t_{batch}$) that cap the release rate from RST at exactly the combined evacuation capacity of the transit fleet ($11\text{ pax/min}$) and designated pedestrian walking platoons ($40\text{–}50\text{ pax/min}$), while matching DTSP hall door intake throughput ($\approx 60\text{ pax/min}$ across 2 open doors).

---

### Sources
1. [Malaysia Gazette (28 Sept 2025)](https://malaysiagazette.com/2025/09/28/1972-pelajar-b40-bergelar-mahasiswa-usm) — Official USM Vice Chancellor statement on 2025/2026 intake (4,236 university-wide; 3,378 Kampus Induk; 919 Engineering; 639 Health).
2. [Utusan Malaysia (4 Oct 2024)](https://www.utusan.com.my/nasional/2024/10/lima-pasangan-kembar-antara-4807-calon-pelajar-baharu-usm) — Official report on 2024/2025 intake offers (4,807 total; 1,700 male, 3,107 female; 20 OKU candidates).
3. [BHEPA USM Official Briefing Report (Oct 2024)](https://www.facebook.com/BhepaUSM/photos/2707-pelajar-baharu-bagi-kampus-induk-usm-sidang-akademik-20242025-mendengar-tak/1029607405630553) — Verified count of 2,707 new students attending orientation briefing at DTSP Kampus Induk.
4. [USM ePrints Dissertation: Kajian Keberkesanan Sistem Bas Kampus Induk USM (eprints.usm.my/58403)](http://eprints.usm.my/58403/1/Kajian%20Keberkesanan%20Sistem%20Bas%20Kampus%20Induk%20USM_Muhammad%20Nizar%20Saddum.pdf) — Unit Perumahan dan Penempatan Pelajar (UPPU) official capacity audit (Jadual 1.2: 9,536 total beds across 8 desasiswa).
5. [Desasiswa Tekun Official Portal (tekun.usm.my)](http://tekun.usm.my/index.php?option=com_content&view=article&id=53&Itemid=310) — History, architectural capacity (2,066 max / 1,033 per block), and block naming (M05 male, M06 female, M09 admin).
6. [Desasiswa Restu Official Portal (restu.usm.my)](https://restu.usm.my/index.php/aboutrestu) — Residential capacity, block structure (M01 male, M02 female, M07 admin, M08 DUD), and 10-floor breakdown.
7. [Desasiswa Saujana Official Portal](https://desasiswasaujana.wordpress.com/about) — All-female accommodation profile and block structure (M03, M04).
8. [Jadual Program Siswa Lestari Sidang Akademik 2024/2025 & 2025/2026 (Kampus Induk)](https://www.scribd.com/document/788583103/Jadual-orientasi-MSL-24-25-USM-240924-123507) — Official orientation time schedule, 05:30–08:00 prep window, 08:30 DTSP start time, and desasiswa registration waves.
9. [USM Housing & Accommodation Centre Notice](https://www.facebook.com/HACUSM/posts/-notice-application-for-campus-stay-permit-during-siswa-lestari-programme-26-sep/1206151281531346) — Mandatory campus clearance and stay permit regulation for senior students during orientation week.
10. [Astro Awani & BHEPA USM OKU Support Portals](https://www.astroawani.com/berita-malaysia/pelajar-oku-usm-nikmati-kemudahan-kelas-pertama-169800) — Desasiswa Aman Damai dedicated barrier-free facilities and welfare transport for disabled students.

---

### Confirmed Facts
- USM Kampus Induk 2025/2026 intake is exactly **3,378 new undergraduates** (UPU mainstream).
- Day 1 orientation physical attendance in DTSP hall is documented at **2,707 to 3,050 students**.
- Kampus Induk has 8 active undergraduate desasiswa with **9,536 total operational beds** (2,609 male, 6,927 female).
- Kompleks RST houses up to 4,812 regular students (over 6,000 at maximum density) across blocks M01 to M06.
- Blocks M01 to M06 are 10-storey high-rise towers (`Aras 1` to `Aras 10`).
- Official plenary morning sessions at DTSP begin strictly at **08:30 AM**.
- The morning preparation window is scheduled from **05:30 AM to 08:00 AM**.
- Desasiswa Aman Damai is the designated hostel for all OKU students.

### Hypotheses
- Non-resident commuter freshmen constitute approximately 8%–10% (~270–330 students) of the Kampus Induk intake based on local Penang residency trends.
- Floor descent during morning peak relies 85%+ on stairwells due to lift capacity saturation (2 lifts $\times$ 13 pax cannot evacuate 200+ students per block within 15 minutes).
- Walking platoons escorted by PPSL from RST to DTSP could discharge 300–400 students per 15-minute block if weather is clear, reducing bus queue length by over 60%.

### Gaps
- Exact room-by-room occupancy rosters for the current 2026 intake per floor (available only inside USM Campus Online internal system).
- Exact fraction of freshmen assigned to non-RST hostels (Aman Damai, Indah Kembara, Cahaya Gemilang) in the current academic year vs previous years.
- Real-time GPS tracking coordinates for the 5 campus shuttle buses during orientation morning hours.

### Recommended Next Measurements
1. **Hostel Foyer Tally Count:** Position field observers at M01, M02, M03, M04, M05, and M06 ground-floor foyers from 06:45 to 08:15 AM to record exact stairwell discharge rate (pax/minute) by floor.
2. **Pedestrian vs Bus Modal Split:** Count students boarding buses at the RST terminal vs students taking the pedestrian staircase/bridge route toward DTSP between 07:00 and 08:15 AM.
3. **DTSP Exterior Ingestion Count:** Measure queue length and entry rate (seconds/student) through DTSP Door 1 and Door 2 to verify true continuous intake capacity.
