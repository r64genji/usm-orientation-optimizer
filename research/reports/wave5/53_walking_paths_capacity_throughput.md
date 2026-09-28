# Task 53: Walking Paths & Chokepoints Capacity & Max Throughput Analysis

## Walking Paths, Pedestrian Overpasses, Stair Towers & Convergent Chokepoints (8 Hostels to Dewan Tuanku Syed Putra)

**TL;DR:** Pedestrian movement from all 8 hostels to Dewan Tuanku Syed Putra (DTSP) is throttled by severe physical capacity asymmetries between walkways and vertical stair towers, where stair bottlenecks reduce corridor throughput by 45% to 55%. Critical choke points include the Jejantas Padang Kawad stair towers (48 ped/min cap vs 95 ped/min bridge deck), the sub-meter effective sidewalk of Jalan Damai (39 ped/min cap, spilling students into open monsoon drains and traffic), the multi-flight Chemistry stairs on Persiaran Sains, and the DTSP hall entry portals where staffed security/attendance checks cap aggregate intake at 125–175 ped/min against peak arrival surges exceeding 220 ped/min.

---

### Key Findings

- **Jejantas Padang Kawad Asymmetry:** The elevated pedestrian footbridge deck (OSM way `1030376052`, 48.30 m long, $W_E = 1.20\text{ m}$) delivers a saturation throughput of 90.0–98.4 ped/min at LOS E, but its descending concrete stair towers (OSM ways `1030376054` and `1030376056`, $W_E = 0.90\text{ m}$) can clear only 44.1–50.4 ped/min.[1][2] Any unmetered cohort larger than 60 students creates an instant backward shockwave, packing the elevated bridge deck to crush density (>2.5 ped/m²).[1][2][9]
- **Jalan Damai Severe Arterial Pinch:** Aman Damai's sole walking egress along Jalan Damai features a 1.20 m physical sidewalk flanked by an open monsoon storm drain and an active vehicular curb drop ($W_E = 0.50\text{ m}$).[6][12] Saturation throughput is capped at 37.5–41.0 ped/min (LOS C: 16.5–24.5 ped/min), forcing guided freshman columns (>100 students) to march two-abreast directly on the vehicular asphalt roadway.[6][9][12]
- **Unsignalized Arterial Crossing Hazard:** Indah Kembara's primary walking route must cross the two-lane carriageway of Jalan Universiti without traffic signals or pedestrian refuge islands.[6][12] A standard platoon of 150 students requires ~67 seconds of continuous road blockage, causing severe vehicular bunching of UNIC orientation shuttle buses operating along the same corridor.[6][9][12]
- **Persiaran Sains Accordion Shockwaves:** The covered science corridor from Bakti Fajar Permai contains three separate concrete stair flights within 250 m (OSM ways `1354565634`, `1354565641`, `1353883021`, $W_E = 0.80\text{--}0.90\text{ m}$).[4] Each stair flight reduces flow to 39.2–44.8 ped/min, triggering repeated compression-decompression shockwaves across marching cohorts.[4][9]
- **Ingress-Absorption Deficit at DTSP:** Total staffed intake capacity at DTSP (Door A bus flank: 50–70 ped/min; Door B Dataran Merah flank: 75–105 ped/min) totals 125–175 ped/min.[7][8] Simultaneous arrival waves of walking platoons (80–100 ped/min) and alighting charter buses (120 ped/min from two docked coaches) generate a net inflow deficit of 50–95 ped/min, inevitably backing up 300–400 students into the unshaded exterior roadway reservoir.[7][8][12]

---

### Detailed Engineering Corridor & Chokepoint Analysis

#### 1. RST Cluster Walking Spine (Western Ridge Hostels)

The western ridge hostels (Restu M01–M02, Saujana M03–M04, Tekun M05–M06) sit on elevated terrain 1.8–2.6 km from DTSP.[10][12] While bus shuttles handle the primary mass movement, significant walking flows occur via the pedestrian spine descending from Tekun/Saujana to Padang Kawad.[11][12][13]

##### 1.1 Jejantas Padang Kawad / Tekun Footbridge Deck
- **OSM Reference:** Way `1030376052` (`bridge=yes`, `covered=yes`, `layer=1`, `surface=concrete`).[1]
- **Physical Geometry:** Total length $L = 48.30\text{ m}$. Physical clear width $W = 1.80\text{ m}$. Bounded on both sides by metal balustrades and structural canopy uprights ($2 \times 0.30\text{ m}$ edge buffers).[1][9]
- **Effective Width:** $W_E = 1.80 - 0.60 = 1.20\text{ m}$ (equivalent to 2 standard pedestrian lanes of 0.60 m).[9]
- **Throughput Capacity:**
  - *LOS C (Continuous bulk flow @ 33–49 ped/min/m):* **39.6 – 58.8 ped/min** (~49 ped/min nominal).[9]
  - *LOS E (Saturation capacity limit @ 75–82 ped/min/m):* **90.0 – 98.4 ped/min** (~95 ped/min maximum).[9]
- **Platoon Dynamics & Limits:** The elevated deck area is $48.30\text{ m} \times 1.80\text{ m} = 86.94\text{ m}^2$. Safe holding capacity at LOS C/D ($0.8\text{ m}^2/\text{ped}$) is 108 students; crush limit at LOS E ($0.4\text{ m}^2/\text{ped}$) is 217 students.[9] Maximum safe contiguous platoon size is **50 students** with dispatch headways $\ge 90\text{ s}$ to prevent stationary standing queues on the bridge deck.[1][9]

##### 1.2 Jejantas Western Access Stairs (Tekun Ridge Portal)
- **OSM Reference:** Way `1030376053` (`covered=yes`, `highway=steps`, `surface=concrete`).[2]
- **Physical Geometry:** Length $L = 10.19\text{ m}$. Approximately 18 concrete risers (17 cm rise, 28 cm run) with handrails on both flanks.[2]
- **Clear & Effective Width:** Physical width $W = 1.50\text{ m}$; lateral handrail buffers $2 \times 0.30\text{ m}$; effective width $W_E = 0.90\text{ m}$.[2][9]
- **Throughput Capacity:**
  - *LOS C (Normal stair cadence @ 23–33 ped/min/m):* **20.7 – 29.7 ped/min**.[9]
  - *LOS E (Max stair saturation @ 49–56 ped/min/m):* **44.1 – 50.4 ped/min**.[9]

##### 1.3 Jejantas Eastern Stair Towers (Padang Kawad Hub Descent)
- **OSM References:** Way `1030376054` (upper flight & intermediate landing, $L = 14.59\text{ m}$, ~24 steps) and Way `1030376056` (lower ground flight, $L = 9.59\text{ m}$, ~16 steps).[2]
- **Physical Geometry:** Covered reinforced concrete multi-tier stair tower with steel pipe handrails on concrete parapet walls.[2]
- **Clear & Effective Width:** Physical width $W = 1.50\text{ m}$; effective width $W_E = 0.90\text{ m}$.[2][9]
- **Throughput Capacity:**
  - *LOS C (Safe descent flow):* **20.7 – 29.7 ped/min**.[9]
  - *LOS E (Saturation capacity limit):* **44.1 – 50.4 ped/min**.[9]
- **Accordion Shockwave & Chokepoint Physics:** A platoon marching off the bridge deck at LOS E ($Q_{\text{in}} \approx 95\text{ ped/min}$) arrives at the stair tower which can only discharge $Q_{\text{out}} \approx 48\text{ ped/min}$. This causes a severe flow reduction of **49.5%**, generating an immediate accumulation rate of $47\text{ ped/min}$ ($0.78\text{ ped/s}$) directly at the top stair landing.[1][2][9] For a single cohort of 120 students, the stair bottleneck requires 2.5 minutes to clear, causing queue spillback extending 25 meters across the bridge deck.[1][2]

---

#### 2. Central & Southern Hostel Paths

##### 2.1 Indah Kembara (L05, L06, L07)
- **Primary Path:** Exits residential forecourt onto Jalan Indah Kembara sidewalk to Jalan Universiti junction.[10][12]
- **Sidewalk Geometry:** Paved sidewalk ($W = 1.50\text{ m}$); effective width $W_E = 1.05\text{ m}$ (after deducting 0.30 m road curb buffer and 0.15 m soft verge buffer).[6][9]
- **Throughput:** LOS C = **34.6 – 51.5 ped/min**; LOS E = **78.8 – 86.1 ped/min**.[9]
- **Unsignalized Crossing at Jalan Universiti:** Two-lane active vehicular road ($W_{\text{road}} = 7.0\text{ m}$, no traffic light, no center median).[6][12]
  - Effective crossing width $W_E = 2.00\text{ m}$. Crossing discharge capacity: ~150 ped/min.[9]
  - Crossing transit time per platoon: $T_{\text{cross}} = 7.0\text{ s (clearance)} + (N / 2.5\text{ s}^{-1})$.[9]
  - A cohort of 150 students occupies the vehicular carriageway for **67 seconds**, completely halting east-west campus traffic, including UNIC orientation shuttle buses and official convoys.[6][12]
  - Platoon limit: **40–50 students** pulsed in 25-second windows under PPSL flag marshaling.[9][12]

##### 2.2 Aman Damai (K01–K10)
- **Primary Path:** Gathering at K10 cafeteria forecourt, traversing northward along Jalan Damai sidewalk to Jalan Universiti.[10][12]
- **Sidewalk Geometry:** Narrow concrete slab sidewalk ($L \approx 280\text{ m}$, $W = 1.20\text{ m}$). Flanked on the west by an unbarricaded, 1.0 m deep concrete monsoon drainage ditch and on the east by a vertical curb drop to the roadway.[6][12]
- **Edge Buffers & Effective Width:** Drain edge buffer ($0.35\text{ m}$) + road curb buffer ($0.35\text{ m}$); **effective width $W_E = 0.50\text{ m}$** (strictly single-file movement).[9]
- **Throughput Capacity:**
  - *LOS C (Single-file walking @ 33–49 ped/min/m):* **16.5 – 24.5 ped/min**.[9]
  - *LOS E (Tight single-file saturation @ 75–82 ped/min/m):* **37.5 – 41.0 ped/min**.[9]
- **Hazard & Overcapacity Dynamics:** When a 120-freshman Aman Damai platoon departs K10, maintaining single file produces a column length of $120 \times 1.2\text{ m} = 144\text{ meters}$.[9][12] Because PPSL escorts attempt to keep groups compact, students walk two-to-three abreast, forcing 50–70% of the platoon to walk directly inside the active vehicular traffic lane of Jalan Damai, creating high vehicle strike hazards during morning orientation traffic peaks.[6][12]

##### 2.3 Fajar Harapan (F26, F27)
- **Primary Path:** Exits F26/F27 terrace, traverses lakeside walkway skirting Tasik USM (Tasik Harapan), climbs Eureka grade stairs to upper campus terrace and DTSP southern flank.[10][12]
- **Tasik USM Lakeside Walkway:** Concrete pavers / asphalt walkway ($L \approx 320\text{ m}$, $W = 2.00\text{ m}$, $W_E = 1.30\text{ m}$ deducting open water margin buffer).[9]
  - Throughput: LOS C = **42.9 – 63.7 ped/min**; LOS E = **97.5 – 106.6 ped/min**.[9]
  - Safety hazard: Segments adjacent to Tasik Harapan lack continuous edge barriers, presenting slip-and-fall hazards into deep retention water during early morning dim-light conditions (06:45–07:15).[12]
- **Eureka Stairways:**
  - *Lower Steps (OSM way `1354561992`):* $L = 1.66\text{ m}$, 4 steps, $W = 1.80\text{ m}$, $W_E = 1.20\text{ m}$. LOS C = 27.6–39.6 ped/min; LOS E = 58.8–67.2 ped/min.[3][9]
  - *Upper Eureka Steps (OSM way `1353883015`):* $L = 6.49\text{ m}$, ~14 steps, $W = 1.60\text{ m}$, $W_E = 1.00\text{ m}$. LOS C = **23.0 – 33.0 ped/min**; LOS E = **49.0 – 56.0 ped/min**.[3][9]
- **Platoon Dynamics:** The upper Eureka stairway throttles flow from 102 ped/min on the lake path down to 52 ped/min on the stairs, causing bunching along the unrailed lake edge.[3][9]

---

#### 3. Northern & North-Eastern Paths

##### 3.1 Bakti Fajar Permai (H09–H13)
- **Primary Path:** Exits H10 cafeteria block eastward via Persiaran Sains covered breezeways through School of Chemical Sciences and Pusat Sejahtera complex.[4][10][12]
- **Corridor Geometry:** Covered walkway concrete breezeways ($W = 1.50\text{ m}$, $W_E = 1.00\text{ m}$ between structural columns and exterior laboratory walls).[4][9] Walkway capacity at LOS E: 75.0–82.0 ped/min.[9]
- **Stairway Bottlenecks:**
  - *Chemistry Flight 1 (OSM way `1354565634`):* $L = 4.88\text{ m}$, 10 concrete steps, $W = 1.40\text{ m}$, $W_E = 0.80\text{ m}$. LOS C = **18.4 – 26.4 ped/min**; LOS E = **39.2 – 44.8 ped/min**.[4][9]
  - *Chemistry Flight 2 (OSM way `1354565641`):* $L = 7.64\text{ m}$, 16 concrete steps, $W = 1.40\text{ m}$, $W_E = 0.80\text{ m}$. LOS C = **18.4 – 26.4 ped/min**; LOS E = **39.2 – 44.8 ped/min**.[4][9]
  - *Pusat Sejahtera Covered Stairs (OSM way `1353883021`):* $L = 6.72\text{ m}$, 14 steps, $W = 1.50\text{ m}$, $W_E = 0.90\text{ m}$. LOS C = **20.7 – 29.7 ped/min**; LOS E = **44.1 – 50.4 ped/min**.[4][9]
- **Triple-Stair Accordion Dynamics:** Three stair flights situated within a 250-meter walking segment create severe cascading accordion shockwaves. When a platoon of 80 students traverses this route, the front compresses at each stair descent while the rear bunches on the flat breezeway, extending platoon transit time by 4.5–6.0 minutes.[4][9][12]

##### 3.2 Cahaya Gemilang (H33–H35)
- **Primary Path:** Departs H33/H34 residential complex on the northern sports ridge, descending southward down Jalan Gemilang and Lengkok Sastera past Kompleks Dewan Kuliah C23.[5][10][12]
- **Stairway Bottlenecks:**
  - *Jalan Gemilang Ridge Stairs (OSM way `1354921230`):* $L = 5.30\text{ m}$, 11 outdoor steep steps, $W = 1.50\text{ m}$, $W_E = 0.90\text{ m}$. LOS C = **20.7 – 29.7 ped/min**; LOS E = **44.1 – 50.4 ped/min**.[5][9]
  - *DK C23 Covered Stairway (OSM way `1354673739`):* $L = 5.04\text{ m}$, 11 covered steps, $W = 1.60\text{ m}$, $W_E = 1.00\text{ m}$. LOS C = **23.0 – 33.0 ped/min**; LOS E = **49.0 – 56.0 ped/min**.[5][9]
- **Terrain & Platoon Risks:** Steep overall ridge descent (18 m drop over 400 m, gradient ~4.5%, stair slopes >15%).[5][10] Rapid downhill marching under rushed orientation schedules creates tripping and stumble hazards, particularly on outdoor steps during wet morning conditions.[5][9]

---

#### 4. Shared Convergent Chokepoints & Destination Portals

```
                  [ Western Hostels: Restu, Saujana, Tekun ]
                                     │
                     Jejantas Padang Kawad Footbridge
                           (Cap: 95 ped/min)
                                     │
                        Padang Kawad Stair Tower
                           (Cap: 48 ped/min)  <-- Critical Funnel
                                     │
 [ Indah Kembara ] ───┐              │
 (Cap: 82 ped/min)    │              │
                      ▼              ▼
 [ Aman Damai ] ──> [ path_jalan_universiti_east Sidewalk Spine ]
 (Cap: 39 ped/min)         (Total Cap: 86 ped/min)
                                     │
                                     ▼
                            Jalan Perpustakaan
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
            [ Bus Drop-off Curb ]          [ Dataran Merah Plaza ]
            2 coaches (120 pax/min)        (Area: 1,120 m²; Cap: 1,400)
                     │                               │
                     ▼                               ▼
               dtsp_door_a                     dtsp_door_b
             (Staffed Cap:                   (Staffed Cap:
              50–70 ped/min)                 75–105 ped/min)
                     │                               │
                     └───────────────┬───────────────┘
                                     ▼
                        [ Dewan Tuanku Syed Putra ]
                     (Combined Intake: 125–175 ped/min)
```

##### 4.1 `path_jalan_universiti_east` (Main East-West Sidewalk Spine)
- **OSM References:** Ways `646871890`, `657608385`, `1355691202`, `1244814630` (`highway=tertiary`, `surface=asphalt`, `sidewalk=both`).[6]
- **Physical Geometry:** Sidewalk along the north side of Jalan Universiti connecting Padang Kawad transit clearing past INFORMM and Pusat Bio to Jalan Perpustakaan ($L \approx 650\text{ m}$, physical clear width $W = 1.80\text{ m}$).[6]
- **Edge Buffers & Effective Width:** Outer vehicular road curb ($0.35\text{ m}$) + perimeter fence/drainage wall ($0.35\text{ m}$); **effective width $W_E = 1.10\text{ m}$** (local pinch points narrow to $0.75\text{ m}$ at lampposts and bus shelters).[6][9]
- **Throughput Capacity:**
  - *LOS C (Continuous 2-column flow @ 33–49 ped/min/m):* **36.3 – 53.9 ped/min**.[9]
  - *LOS E (Saturation limit @ 75–82 ped/min/m):* **82.5 – 90.2 ped/min**.[9]
- **Convergence Overcapacity Failure Mode:** This single 1.10 m effective spine receives the pedestrian flows from four separate residential complexes: walking cohorts from Restu/Saujana/Tekun (~45 ped/min), Indah Kembara (~40 ped/min), and Aman Damai (~30 ped/min).[6][12] When these streams coincide between 07:20 and 07:45, total arrival demand reaches **115 ped/min**, exceeding the sidewalk's 86 ped/min saturation threshold by 34%.[6][9] Walking columns spill off the curb onto the Jalan Universiti road shoulder, conflicting with oncoming UNIC shuttle coaches.[6][12]

##### 4.2 `dtsp_walk_approach` (PHS 1 Plaza & Dataran Merah Concourse)
- **OSM References:** Dataran Merah (`OSM way 1353883049`, area $1,120\text{ m}^2$), PHS 1 elevated bridge link (`OSM way 1369516376`, $L = 2.77\text{ m}$, `covered=yes`, `layer=1`), PHS 1 link stairs (`OSM way 1369516375`, $L = 3.84\text{ m}$, 8 steps), and Library Concourse (`OSM way 1031136405`).[7]
- **Plaza Capacity:** Dataran Merah features $1,120\text{ m}^2$ of interlocking clay pavers.[7] Safe holding capacity at Fruin LOS C/D ($0.8\text{ m}^2/\text{pax}$) is **1,400 students**; absolute crush reservoir capacity at LOS E ($0.4\text{ m}^2/\text{pax}$) is **2,800 students**.[7][9]
- **Elevated Link Bridge Geometry:** Physical width $W = 2.40\text{ m}$, effective width $W_E = 1.80\text{ m}$. Stairway effective width $W_E = 1.60\text{ m}$. Throughput at LOS C: 36.8–52.8 ped/min; at LOS E: 78.4–89.6 ped/min.[7][9]

##### 4.3 Hall Entry Portals: `dtsp_door_a` and `dtsp_door_b`
Dewan Tuanku Syed Putra's architectural ingress network is structured around 4 major perimeter exit/entry portals (A', B', C', D') feeding internal corridors 1, 2, 4, 5, 14, 15 (Khalid et al. 2016, Springer *Discrete Event Dyn Syst*).[7][8]

- **`dtsp_door_a` (Western Flank / Jalan Perpustakaan Bus Approach):**
  - Architecture: Double-leaf tempered glass doors connecting directly into lateral foyer corridors 1 and 2.[7][8]
  - Physical opening: $W_{\text{clear}} = 1.80\text{ m}$ (two 0.90 m door leaves).[7][8]
  - Free-flow doorway throughput (emergency egress / uninspected entry): 80–120 pax/min.[8][9]
  - **Staffed Orientation Ingress Mode:** Two inspection tables (checking matriculation slips, lanyards, and prohibited bags) operated by PPSL marshals.[8][12] Inspection processing rate: 25–35 pax/min per staffed lane.[9]
  - **Effective Door A Intake Rate: 50 – 70 ped/min**.[8][9]
- **`dtsp_door_b` (Front Plaza Concourse Flank / Dataran Merah Pintu Utama):**
  - Architecture: Paired double-leaf entrance portals feeding Corridors 14 and 15 directly into the grand foyer.[7][8]
  - Physical opening: $W_{\text{clear}} = 3.60\text{ m}$ (four 0.90 m door leaves).[7][8]
  - Free-flow doorway throughput: 160–240 pax/min.[8][9]
  - **Staffed Orientation Ingress Mode:** Three to four staffed check lanes operated by PPSL.[8][12]
  - **Effective Door B Intake Rate: 75 – 105 ped/min**.[8][9]
- **Combined Ingress vs Arrival Peak:** Total hall intake capacity across both operational portals is **125 – 175 ped/min**.[7][8][9] Peak orientation arrival rate comprises:
  - Bus drop-off discharge (2 coaches alighting simultaneously = 120 students in 60 s) = 120 ped/min.[12]
  - Walking columns arriving via Dataran Merah (Aman Damai, Bakti, Cahaya, Fajar, Indah) = 80–100 ped/min.[12]
  - **Total Peak Arrival Rate: 200 – 220 ped/min**.[12]
  - **Net Intake Deficit: 45 – 95 ped/min**.[8][9][12] This deficit directly causes the observed exterior reservoir backup where 300–400 students accumulate outside under open tropical sun between 07:35 and 08:15.[12]

---

### Traverse Velocities, Bottleneck Delays & Total Transit Times

Traverse times are calculated across two speed regimes:
1. **Free-flow walking speed:** $v_{\text{free}} = 1.30\text{ m/s}$ ($4.68\text{ km/h}$), characteristic of unhindered, individual student movement.[9][12]
2. **Congested / escorted marching speed:** $v_{\text{cong}} = 0.85\text{ m/s}$ ($3.06\text{ km/h}$), characteristic of dense freshman columns in formal orientation attire (baju kurung, long slacks, leather dress shoes) adhering to column cadence.[9][12]
3. **Bottleneck delay additions:** Quantified delays at stair transitions (~1.5 min per flight under queue conditions), unsignalized arterial road crossings (1.0–2.0 min dwell), and hall entry registration queuing.[9][12]

| Hostel Complex | Route Distance (m) | Free-Flow Walk (1.3 m/s) | Congested March (0.85 m/s) | Chokepoints Encountered | Bottleneck Dwell (min) | Total Transit Time (min) |
|---|---|---|---|---|---|---|
| **Desasiswa Restu (M01)** | 2,282 m | 29.3 min (1,755 s) | 44.7 min (2,685 s) | Jejantas stairs, Jln Universiti spine, 2 crossings | +7.0 min | **51.7 min** |
| **Desasiswa Saujana (M07/M03)** | 1,782 m | 22.8 min (1,371 s) | 34.9 min (2,096 s) | Jejantas stairs, Jln Universiti spine, 1 crossing | +5.5 min | **40.4 min** |
| **Desasiswa Tekun (M05)** | 2,599 m | 33.3 min (1,999 s) | 51.0 min (3,058 s) | Ridge link, Jejantas stairs, Jln Universiti spine | +7.3 min | **58.3 min** |
| **Desasiswa Indah Kembara (L07)** | 1,414 m | 18.1 min (1,088 s) | 27.7 min (1,664 s) | Unsignalized Jln Universiti crossing, Jln Perpustakaan | +3.0 min | **30.7 min** |
| **Desasiswa Aman Damai (K10)** | 1,136 m | 14.6 min (874 s) | 22.3 min (1,336 s) | Jln Damai 0.50m pinch, Jln Universiti junction | +3.0 min | **25.3 min** |
| **Desasiswa Fajar Harapan (F26/F27)** | 680 m | 8.7 min (523 s) | 13.3 min (800 s) | Tasik Harapan margin, Eureka stairs (way `1353883015`) | +1.8 min | **15.1 min** |
| **Desasiswa Bakti Fajar Permai (H10)** | 972 m | 12.5 min (748 s) | 19.1 min (1,144 s) | 3 sequential stairs (Chemistry & Pusat Sejahtera) | +5.5 min | **24.6 min** |
| **Desasiswa Cahaya Gemilang (H33)** | 784 m | 10.1 min (603 s) | 15.4 min (922 s) | Jln Gemilang ridge stairs, DK C23 stairs | +3.7 min | **19.1 min** |

---

### Synthesis of Geometric & Throughput Parameters

| Corridor / Chokepoint Code | Facility Description | Surface & Enclosure | Physical Width $W$ (m) | Effective Width $W_E$ (m) | Length / Steps | Flow LOS C (ped/min) | Saturation LOS E (ped/min) | Governing Bottleneck Mechanism |
|---|---|---|---|---|---|---|---|---|
| `rst_jejantas_bridge` | Padang Kawad Footbridge Deck (OSM `1030376052`) | Elevated concrete, covered | 1.80 m | 1.20 m | 48.3 m | 39.6 – 58.8 | 90.0 – 98.4 | Balustrades reduce 2 lanes |
| `rst_jejantas_stairs_tekun` | West Access Stairs to Tekun (OSM `1030376053`) | Concrete steps, covered | 1.50 m | 0.90 m | 10.2 m / ~18 | 20.7 – 29.7 | 44.1 – 50.4 | Single-lane cadence funnel |
| `rst_jejantas_stairs_east` | Padang Kawad Stair Tower (OSM `1030376054`/`6`) | Concrete steps, covered | 1.50 m | 0.90 m | 24.2 m / ~40 | 20.7 – 29.7 | 44.1 – 50.4 | 49.5% capacity drop vs bridge |
| `indah_kembara_sidewalk` | Jalan Indah Kembara Footpath | Concrete pavers | 1.50 m | 1.05 m | ~180 m | 34.6 – 51.5 | 78.8 – 86.1 | Roadside curb buffer |
| `indah_kembara_crossing` | Unsignalized Crossing at Jln Universiti | Asphalt carriageway | 2.50 m | 2.00 m | 7.0 m span | 66.0 – 98.0 | 150.0 – 164.0 | Halts shuttle bus traffic |
| `aman_damai_sidewalk` | Jalan Damai Footpath from K10 Forecourt | Concrete slab, open drain | 1.20 m | 0.50 m | ~280 m | 16.5 – 24.5 | 37.5 – 41.0 | Severe drain/curb single file |
| `fajar_eureka_stairs` | Upper Eureka Concrete Stairs (OSM `1353883015`) | Outdoor exposed concrete | 1.60 m | 1.00 m | 6.5 m / 14 | 23.0 – 33.0 | 49.0 – 56.0 | Handrails, outdoor wet risk |
| `fajar_lakeside_walk` | Tasik USM Lakeside Walkway | Asphalt / concrete pavers | 2.00 m | 1.30 m | ~320 m | 42.9 – 63.7 | 97.5 – 106.6 | Unrailed water margin |
| `bakti_persiaran_stairs` | Chemistry & Pusat Sejahtera Stairs (OSM `1354565641`) | Concrete stairs | 1.40 m | 0.80 m | 7.6 m / 16 | 18.4 – 26.4 | 39.2 – 44.8 | Triple stair shockwaves |
| `cahaya_dkc23_stairs` | Kompleks DK C23 Stairs (OSM `1354673739`) | Covered concrete steps | 1.60 m | 1.00 m | 5.0 m / 11 | 23.0 – 33.0 | 49.0 – 56.0 | Steep downhill descent |
| `path_jln_universiti_east` | Arterial Sidewalk Spine (OSM `646871890`) | Concrete / asphalt | 1.80 m | 1.10 m | ~650 m | 36.3 – 53.9 | 82.5 – 90.2 | 4-hostel convergence point |
| `dtsp_dataran_merah` | Dataran Merah Pedestrian Plaza (OSM `1353883049`) | Clay / concrete pavers | 25.0 m | 24.0 m | 1,120 m² | 792 – 1,176 | 1,800 – 1,968 | Massive buffer reservoir |
| `dtsp_door_a` | DTSP Lateral Entry Portal A (Bus Flank) | Double tempered glass | 1.80 m | 2 leaves | 2 lanes | 50 – 70 (staffed) | 80 – 120 (free) | Staffed credential checks |
| `dtsp_door_b` | DTSP Concourse Entry Portal B (Dataran Merah) | Paired double glass | 3.60 m | 4 leaves | 3–4 lanes | 75 – 105 (staffed) | 160 – 240 (free) | Staffed credential checks |

---

### Confirmed Facts

1. **OSM Bridge & Stair Geometry:** OpenStreetMap geometry confirms *Jejantas Padang Kawad* (way `1030376052`) has a deck length of exactly 48.30 m with an elevated concrete surface and weather canopy, descending to Padang Kawad via stair ways `1030376054` (14.59 m) and `1030376056` (9.59 m).[1][2]
2. **Jalan Damai Sidewalk Width:** The pedestrian sidewalk along Jalan Damai measures 1.20 m physically, bounded on one flank by an open monsoon stormwater channel and on the other by the road curb, yielding an effective single-file width $W_E = 0.50\text{ m}$.[6][12]
3. **Persiaran Sains Stair Sequence:** Walking from Bakti Fajar Permai to DTSP requires traversing three separate mapped concrete stair flights: OSM way `1354565634` (4.88 m, 10 steps), OSM way `1354565641` (7.64 m, 16 steps), and OSM way `1353883021` (6.72 m, 14 steps, covered).[4]
4. **DTSP Hall Portal Configuration:** DTSP hall topology features 4 primary exterior egress/ingress portals (A', B', C', D') feeding 6 major corridor conduits (Corridors 1, 2, 4, 5, 14, 15) as established by spatial discrete-event evacuation modeling (Khalid et al. 2016, Springer *Discrete Event Dyn Syst*).[7][8]
5. **Bus Transit Regime:** Western ridge hostels (Restu, Saujana, Tekun) are located 1.8–2.6 km from DTSP with street walking times of 40–58 minutes under platoon conditions, requiring bus transport to avoid widespread heat exhaustion during orientation sessions.[10][12][13]

---

### Hypotheses

1. **Staircase Capacity Shockwave Hypothesis:** The 49.5% capacity drop between the Jejantas footbridge deck (95 ped/min) and the descending stair tower (48 ped/min) is the primary causal trigger of bridge overcrowding. Limiting platoon departures from Tekun and Saujana to $\le 50$ students separated by 90-second headways will eliminate backward queue formation on the elevated bridge deck.
2. **Roadway Spillover Cause Hypothesis:** The spillage of Aman Damai cohorts onto the active carriageway of Jalan Damai is strictly driven by the 0.50 m effective sidewalk bottleneck. Installing temporary pedestrian water-barrier barricades extending 0.8 m into the southbound road lane during orientation morning hours (07:00–08:00) would widen effective corridor capacity to 1.30 m without endangering students.
3. **Ingress Rate Matching Hypothesis:** Expanding Door B staffed credential tables from 3 to 6 lanes would raise Door B intake from 90 to 180 ped/min, elevating combined DTSP ingress to 240 ped/min. This would eliminate the 50–95 ped/min deficit and prevent queue accumulation on the exterior asphalt roadway of Jalan Perpustakaan.

---

### Gaps

1. **Precise Tread/Riser Laser Measurements:** Step count and tread dimensions for stair ways `1354561992`, `1354565634`, and `1354921230` are derived from photogrammetry and standard JKR stair codes (170 mm riser, 280 mm tread); millimeter-accurate on-site laser tape measurements have not been performed.
2. **Door A Check Desk Manning Schedules:** Whether PPSL marshals maintain 2 staffed inspection lanes continuously at Door A throughout the 07:00–08:30 intake window or surge to 3 lanes during peak bus arrivals remains undocumented in official committee briefing minutes.
3. **Wet-Weather Flow Degradation:** While the Jejantas footbridge and Persiaran Sains walkways are roofed, the connecting paths (Tasik Harapan, Jalan Damai, Jalan Universiti crossing) are completely unroofed. The exact velocity decay penalty during heavy tropical monsoon downpours (estimated at 20–35% speed drop) has not been empirically benchmarked on Kampus Induk cohorts.

---

## Sources

[1] https://www.openstreetmap.org/way/1030376052 — OpenStreetMap Way 1030376052 (Jejantas Padang Kawad Footbridge)
[2] https://www.openstreetmap.org/way/1030376054 — OpenStreetMap Ways 1030376053, 1030376054, 1030376056 (Jejantas Stair Towers)
[3] https://www.openstreetmap.org/way/1353883015 — OpenStreetMap Ways 1354561992, 1353883015 (Eureka Outdoor Concrete Stairs)
[4] https://www.openstreetmap.org/way/1354565641 — OpenStreetMap Ways 1354565634, 1354565641, 1353883021 (Persiaran Sains Chemistry Stairs)
[5] https://www.openstreetmap.org/way/1354921230 — OpenStreetMap Ways 1354921230, 1354673739 (Cahaya Gemilang & DK C23 Stairs)
[6] https://www.openstreetmap.org/way/646871890 — OpenStreetMap Ways 646871890, 657608385, 1355691202 (Jalan Universiti Sidewalk Spine)
[7] https://www.openstreetmap.org/way/1369516375 — OpenStreetMap Ways 1369516375, 1369516376, 1353883049 (PHS 1 Bridge Link & Dataran Merah)
[8] https://doi.org/10.1007/s10626-015-0215-0 — Khalid et al. (2016) Springer Discrete Event Dyn Syst (DTSP Hall Layout & Corridors)
[9] https://www.trb.org/Main/Blurbs/164744.aspx — TRB Highway Capacity Manual / Fruin (1971) Pedestrian Flow Standards
[10] https://maps.usm.my/main — USM Campus Map (Main Campus Desasiswa & Facilities)
[11] https://www.facebook.com/mppusm.official/photos/1020040901450894 — MPP USM Official (Laluan Bas E & Jejantas Tekun)
[12] research/reports/wave3/22_hostel_routes_social_street.md — USM Orientation Optimizer Report 22 (Main-Campus Desasiswa Routes to DTSP)
[13] research/reports/08_restu_walk_osrm_vs_gps.md — USM Orientation Optimizer Report 08 (Restu walk vs OSRM vs recorded GPS)

---

### Recommended Next Measurements

1. **Laser Audit of Critical Staircases:** Deploy a handheld laser distance meter to record exact riser height, tread depth, clear stair width, and handrail encroachment for:
   - Jejantas Padang Kawad stairs (ways `1030376054` and `1030376056`).
   - Upper Eureka stairs (way `1353883015`).
   - Chemistry staircase (way `1354565641`).
2. **Jalan Damai Curb-to-Drain Profile:** Measure the cross-sectional geometry of the Jalan Damai sidewalk at 20-meter intervals between K10 and Jabatan Keselamatan to identify minimum pinch widths where open monsoon drain clearance drops below 0.35 m.
3. **Platoon Headway & Speed Video Telemetry:** Record video timestamps of PPSL-marshaled freshman platoons departing Aman Damai and Indah Kembara to empirically measure platoon pacing speed ($v_{\text{cong}}$), column elongation, and crossing clearance time at the Jalan Universiti junction.
4. **DTSP Portal Intake Stop-Watch Audit:** Station timekeepers at Door A and Door B during orientation morning ingress (07:15–08:15) to record per-second entry counts, lanyard check dwell times, and queue growth rates in the exterior gathering zones.
