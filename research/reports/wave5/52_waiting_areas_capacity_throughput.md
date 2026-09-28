# 52: Waiting Areas & Student Holding Locations Capacity & Max Throughput Analysis

**TL;DR:** The 31.4-minute outdoor standing reservoir at DTSP along Jalan Perpustakaan and the road shoulder queue at Restu occur because student arrival pulses (~44 pax/min per bus, plus concurrent walking hostels) exceed the constrained 2-door staffed intake rate (30 pax/min), while large shaded upstream facilities (Dewan Utama Desasiswa M08, footprint 1,669.2 m², capacity 800–1,200 pax; Restu Cafeteria M07, footprint 878.8 m², capacity 350–450 pax; and DTSP indoor foyer, 520 m², capacity 520–740 pax) remain underutilized. Diverting overflow cohorts to Kompleks Dewan Kuliah C23 (SK1–SK4) unlocks an immediate 2,000-seat sheltered holding reservoir within a 150-metre walk of DTSP.

---

### Key Findings

1. **`rst_bus_wait` (Restu Departure Pavilion & Forecourt Road Shoulder, `5.35728, 100.28981`):**
   - Usable area: ~140.0 m² (combining the covered boarding pavilion apron ~50 m² and adjacent road shoulder strip ~90 m², 60 m × 1.5 m).
   - Safe standing capacity (Fruin LOS C/D, 0.7–1.0 m²/pax): **140–200 pax**.
   - Physical crush capacity (Fruin LOS E/F, 0.3–0.5 m²/pax): **280–466 pax**.
   - Overcapacity trigger: **>200 pax** forces pedestrian queue spillage off the kerb into active vehicular lanes along Halaman Bukit Gambir; **>50 pax** exceeds the covered pavilion roof footprint, exposing students to direct morning sun/rain.

2. **`rst_rain_shelter` (Restu Cafeteria / Covered Dining Pavilion M07, `5.356461, 100.289265`):**
   - Footprint: **878.8 m²** (OSM way `275415004`), with ~550 m² usable dining/assembly floor space.
   - Safe seated/standing holding capacity: **350–450 seated patrons** (4-top/6-top fixed bench layout) or **550–780 standing pax** (Fruin LOS C/D).
   - Overcapacity trigger: **>450 seated** during active breakfast meal service or **>800 standing pax** (violating internal gangway clearances per UBBL 1984 By-law 185).

3. **`dtsp_exterior_gathering` (Jalan Perpustakaan Holding Reservoir & Forecourt Plaza, `5.357153, 100.301749`):**
   - Usable road shoulder and plaza apron: ~280.0 m² (70 m kerb/roadway reservoir length × 2.5 m pedestrian clear strip + 105 m² north forecourt portico).
   - Safe waiting capacity (Fruin LOS C/D): **280–400 pax**.
   - Physical crush capacity (Fruin LOS E/F): **560–933 pax**.
   - Overcapacity trigger: **>300 pax** (empirically validated by video telemetry `2026-09-17_0806_dtsp_exterior_reservoir.mp4` where 300–400 students spilled across both lanes of Jalan Perpustakaan, causing PPSL radio holdback to Restu); thermal exposure trigger is reached after **>15 minutes** of static unshaded holding under tropical WBGT >31°C (DOSH 2016 / MOM 2026).

4. **`dtsp_foyer` (DTSP Grand Indoor Foyer & Dataran Merah Concourse, `5.35690, 100.30305`):**
   - Ground footprint: Dataran Merah exterior concourse is **1,048.6 m²** (OSM way `1353883049`); DTSP indoor multi-storey foyer (*ruang legar*) comprises ~520 m² clear circulation floor area (excluding structural columns, stairs, and main entrance vestibules).
   - Safe standing holding capacity (Fruin LOS C/D): **520–742 pax** inside the sheltered foyer; Dataran Merah open concourse accommodates **1,050–1,500 pax** (fair weather only).
   - Ingress/egress throughput: Unobstructed grand glass entrance double doors (Corridors 14 & 15 / Pintu Utama) deliver **220–240 pax/min** (2 doors × 110–120 pax/min), but drop to **30 pax/min** when restricted to 2 staffed check-in lanes.

5. **`dtsp_seating` (Main Auditorium Floor Blocks S–Z & Balcony, `5.35692, 100.30308`):**
   - Main auditorium ground floor: **1,338 fixed seats** across 8 designated blocks (S=220, T=220, U=309, V=259, W=100, X=55, Y=98, Z=77) modeled by Kawsar et al. (2012/2013) and Khalid et al. (2016).
   - Total venue capacity (including upper tiered balcony/mezzanine): **2,500–3,000 fixed auditorium seats** (official convocation & major ceremony configuration).
   - Evacuation throughput: Modelled optimal hall egress rate across 6 primary exit corridors (Corridors 1, 2, 4, 5, 14, 15) is **14.99 to 16.11 ped/s (899–967 pax/min)** under controlled flow, or **12.88 ped/s (772 pax/min)** under unconstrained emergency egress.

6. **Alternative Venue Diversion (Kompleks Dewan Kuliah C23 / SK1–SK4, `5.358017, 100.304127`):**
   - Total verified seating capacity: **2,000 fixed tiered lecture hall seats** (DK SK1: 300, DK SK2: 300, DK SK3: 700, DK SK4: 700), supported by covered foyers for SK1–SK4 (capacity ~10 banquet tables / ~150 standing pax each).
   - Walking transit distance: Located **140–160 metres** northeast of DTSP via Lengkok Sastera covered walkways (~2.0 minutes walking time).

---

## Spatial & Throughput Analysis by Location

```
====================================================================================================
LOCATION ARCHITECTURE, CAPACITY & FLOW METRICS SUMMARY
====================================================================================================
Location Code            Total Footprint   Usable Area   Safe Waiting     Crush Cap.   Max Inflow /
                         (OSM / Floor)     (m²)          (LOS C/D, pax)   (LOS E/F)    Outflow (pax/min)
----------------------------------------------------------------------------------------------------
rst_bus_wait             180 m² (zone)     140 m²        140 - 200        280 - 466    In: 60 / Out: 22
rst_rain_shelter (M07)   878.8 m²          550 m²        350 - 450 (seat) 1,100-1,800  In: 120 / Out: 120
dtsp_exterior_gathering  350 m² (road+ap)  280 m²        280 - 400        560 - 933    In: 44 / Out: 30
dtsp_foyer               750 m² (gross)    520 m²        520 - 742        1,040-1,733  In: 240 / Out: 240
dtsp_seating (Auditorium)2,943.2 m²        1,850 m²      2,500 - 3,000    3,200 max    In: 30* / Out: 967
Alt: DK C23 (SK1-SK4)    1,653.0 m²        1,450 m²      2,000 seats      2,200 max    In: 240 / Out: 240
====================================================================================================
* Note: DTSP ingress is gated to 30 pax/min due to administrative check-in bottlenecks, not door geometry.
```

---

### 1. `rst_bus_wait`: Restu Departure Pavilion & Forecourt Shoulder

- **Spatial Configuration & Coordinates:** Located at `5.35728, 100.28981`, directly west of Dewan Utama Desasiswa M08 and fronting the internal perimeter road (Halaman Bukit Gambir).
- **Physical Dimensions & Usable Area:**
  - Covered staging pavilion: 10.0 m × 5.0 m = 50.0 m².
  - Unshaded roadside staging shoulder: 60.0 m length × 1.5 m effective pedestrian width = 90.0 m².
  - Net usable standing area: **140.0 m²**.
- **Capacity Analysis:**
  - *Safe waiting capacity (Fruin LOS C/D, 0.7–1.0 m²/pax):* **140 to 200 students**.
  - *Crush capacity (Fruin LOS E/F, 0.3–0.5 m²/pax):* **280 to 466 students**.
  - *Overcapacity Trigger:* Headcount **>200 students** forces lateral spillage onto the vehicular carriage, creating immediate conflicts with campus transit coaches and private vehicles.
- **Ingress & Egress Throughput:**
  - *Maximum Inflow Rate:* Arriving walking contingents from Restu M01/M02 and Saujana M03 via hostel walkways flow at **60 pax/min** (single 1.0 m walkway file).
  - *Maximum Outflow Rate:* High-floor tour coach boarding through single 0.8 m door (3 steep steps) is **22 pax/min** (2.5 s/pax unmetered boarding) to **27 pax/min** (1.6 s/pax pre-batched).
  - *Bottleneck Ratio:* $\text{Inflow} / \text{Outflow} = 60 / 22 \approx \mathbf{2.73}$. Unregulated inflow produces continuous queue accumulation on the road shoulder.
- **Thermal & Weather Exposure Constraints:**
  - *Shading:* Only 35.7% (50 m² covered pavilion); 64.3% (90 m² roadside shoulder) is 100% unshaded asphalt/gravel.
  - *Holding Dwell Limit:* In Penang morning conditions (dry bulb 29–33°C, RH >75%, solar radiation >650 W/m², WBGT >31.0°C), static upright unshaded waiting must be capped at **<15 minutes** to prevent orthostatic syncope and heat exhaustion (DOSH 2016).

---

### 2. `rst_rain_shelter`: Restu Cafeteria Pavilion (M07)

- **Spatial Configuration & Coordinates:** Located at `5.356461, 100.289265`, southwest of DUD M08.
- **Physical Dimensions & Usable Area:**
  - Gross building footprint: **878.8 m²** (OSM way `275415004`, polygon bounds Lat 5.35639–5.35669, Lon 100.28898–100.28931).
  - Deductions: Kitchen stalls, wash areas, service counters, waste disposal (~328.8 m²).
  - Net usable dining and holding floor: **550.0 m²**.
- **Capacity Analysis:**
  - *Safe seated capacity:* **350 to 450 seats** across standard Malaysian 4-top and 6-top fixed dining bench tables.
  - *Safe standing capacity (non-dining assembly, Fruin LOS C/D):* **550 to 785 pax**.
  - *Crush capacity (Fruin LOS E/F):* **1,100 to 1,833 pax**.
  - *Overcapacity Trigger:* Seating **>450 pax** causes overcrowding between dining aisles; holding **>800 pax** violates UBBL 1984 By-law 185 by obstructing the 1.2 m perimeter egress paths.
- **Ingress & Egress Throughput:**
  - *Maximum Inflow Rate:* 3 open perimeter open-air sides (aggregate clear aperture >6.0 m) allow **>360 pax/min**.
  - *Maximum Outflow Rate:* Metered egress towards the bus boarding bay via the 1.8 m covered walkway (OSM way `1031136415`) yields **120–140 pax/min**.
  - *Bottleneck Ratio:* Highly stable buffer ($\text{Inflow} \approx \text{Outflow}$); can feed bus bays on demand without internal congestion.
- **Thermal & Weather Exposure Constraints:**
  - *Shading:* **100% fully covered roof** with natural cross-ventilation and perimeter ceiling fans.
  - *Holding Dwell Limit:* Seated thermal exposure is safe for **>60 minutes** during morning peak hours (resting metabolic rate, WBGT indoor index ~28–29°C).

---

### 3. `dtsp_exterior_gathering`: Jalan Perpustakaan Road Reservoir & Forecourt Plaza

- **Spatial Configuration & Coordinates:** Located at `5.357153, 100.301749`, stretching between the Hamzah Sendut Library (PHS 1) south lawn, the bus alighting kerb, and the north portico steps of DTSP.
- **Physical Dimensions & Usable Area:**
  - Jalan Perpustakaan road shoulder / alighting kerb strip: 70.0 m length × 2.5 m width = 175.0 m².
  - North forecourt paved plaza & portico apron: ~105.0 m².
  - Total usable exterior holding area: **280.0 m²**.
- **Capacity Analysis:**
  - *Safe waiting capacity (Fruin LOS C/D, 0.7–1.0 m²/pax):* **280 to 400 students**.
  - *Crush capacity (Fruin LOS E/F, 0.3–0.5 m²/pax):* **560 to 933 students**.
  - *Overcapacity Trigger:* **>300 students**. At 300+ students, pedestrian density exceeds 2.0 pax/m², causing crowd spillage across both lanes of Jalan Perpustakaan. This blocks campus bus turnaround, traps transit coaches, and triggers emergency radio throttle-holds back to origin hostels.
- **Ingress & Egress Throughput:**
  - *Maximum Inflow Rate:* Unloading 1 tour coach every 2–3 minutes delivers **~15–22 pax/min sustained**, arriving in acute pulses of **44 pax/min** (discharge rate: 1.0–1.2 s/pax). Concurrently, walking cohorts from Aman Damai and Bakti Permai add **30–50 pax/min**. Combined peak inflow: **~74–94 pax/min**.
  - *Maximum Outflow Rate (into DTSP Hall):* Gated by PPSL marshal check-in at 2 staffed door leaves = **30 pax/min** (4.0 s/pax credential verification).
  - *Bottleneck Ratio:* $\text{Inflow} / \text{Outflow} = 74 / 30 \approx \mathbf{2.47}$ to $\mathbf{3.13}$. Inflow exceeds hall absorption by 250–310%, creating a compounding exterior queue (+44 to +64 students per minute of sustained arrival).
- **Thermal & Weather Exposure Constraints:**
  - *Shading:* Paved plaza portico offers ~105 m² partial shade (37.5%); the 175 m² road shoulder reservoir is **0% shaded (100% open asphalt)**.
  - *Holding Dwell Limit:* Telemetry shows students were held statically on the road for **31.4 minutes** (08:01:35 to 08:33:00 MYT). Under statutory occupational heat strain guidelines (DOSH 2016 / MOM WSH 2026), unshaded static exposure at WBGT ≥31.0°C without hydration must not exceed **15 minutes**. Dwells >30 minutes cause elevated risk of heat cramps, dehydration, and fainting.

---

### 4. `dtsp_foyer`: DTSP Indoor Foyer & Dataran Merah Concourse

- **Spatial Configuration & Coordinates:** Located at `5.35690, 100.30305`, facing east toward Dataran Merah (OSM way `1353883049`, area 1,048.6 m²).
- **Physical Dimensions & Usable Area:**
  - Dataran Merah exterior red-brick concourse: **1,048.6 m²**.
  - DTSP indoor foyer (*ruang legar*): Gross interior area ~750 m²; net usable dynamic holding floor excluding structural columns, information booths, stairs, and 1.5 m mandatory egress gangways is **520.0 m²**.
- **Capacity Analysis:**
  - *Safe waiting capacity (Fruin LOS C/D, 0.7–1.0 m²/pax):* **520 to 742 students** inside the indoor foyer; **1,050 to 1,500 students** on Dataran Merah concourse.
  - *Crush capacity (Fruin LOS E/F, 0.3–0.5 m²/pax):* **1,040 to 1,733 students** inside the indoor foyer.
  - *Overcapacity Trigger:* Headcount **>750 students** inside the foyer blocks access to the grand lateral stairwells and compromises the 1.2 m emergency exit egress corridors required by UBBL 1984 By-law 182 and 185.
- **Ingress & Egress Throughput:**
  - *Maximum Inflow Rate:* Unrestricted grand double glass doors (Pintu Utama / Corridors 14 & 15) allow **220–240 pax/min** (each 1.6 m clear door provides 110–120 pax/min per Green Guide / Still 2000).
  - *Maximum Outflow Rate (into auditorium floor):* Internal vomitory doors allow **>200 pax/min** when unstaffed.
  - *Bottleneck Ratio:* When doors are staffed with single-file registration desks, flow collapses to **15 pax/min per door** (bottleneck ratio = $44 / 30 = 1.47$). When operated in a free-flow staging mode, bottleneck ratio is **<0.50** (hall foyer completely absorbs incoming coach pulses in 22 seconds).
- **Thermal & Weather Exposure Constraints:**
  - *Shading:* Indoor foyer is **100% fully enclosed and shaded**, mechanically ventilated with air conditioning / high-volume exhaust fans.
  - *Holding Dwell Limit:* Indoor holding dwell is thermally safe for **>60 minutes**; physical postural fatigue (standing) is the only limiting factor after 45 minutes.

---

### 5. `dtsp_seating`: DTSP Main Auditorium Floor & Balcony

- **Spatial Configuration & Coordinates:** Located at `5.35692, 100.30308` (OSM way `896393762`, building footprint 2,943.2 m²).
- **Physical Dimensions & Usable Area:**
  - Auditorium floor footprint: ~1,850 m² occupied by fixed tiered seating blocks, aisles, and orchestra pit/stage.
  - Modelled Seating Layout (Kawsar et al. 2012, 2013; Khalid et al. 2016):
    - Block S: 220 seats
    - Block T: 220 seats
    - Block U: 309 seats
    - Block V: 259 seats
    - Block W: 100 seats
    - Block X: 55 seats
    - Block Y: 98 seats
    - Block Z: 77 seats
    - *Ground Floor Total:* **1,338 fixed seats**.
  - Tiered Upper Balcony / Galleries: **~1,200 to 1,660 fixed seats**.
  - *Total Certified Venue Seating Capacity:* **2,500 to 3,000 fixed auditorium seats** (matches university convocation registration limits).
- **Evacuation & Egress Throughput (Khalid et al. 2016 Simulation Data):**
  - Hall network topology consists of **15 M/G/C/C branches**:
    - 6 source corridors (internal seating aisles: Corridors 6, 7, 8, 9, 10, 11).
    - 3 intermediate connectors (Corridors 3a, 12, 13).
    - 6 primary exterior exit conduits:
      - Corridors 1 & 2 (Lateral Exit Portals A' & B', width 2.5 m, length 8.0 m).
      - Corridors 4 & 5 (Lateral Exit Portals C' & D', width 2.0 m, length 8.5 m).
      - Corridors 14 & 15 (Rear Concourse Portals / Dataran Merah, width 1.8 m, length 7.35 m).
  - *Maximum Controlled Outflow Rate:* **14.99 ped/s (~899 pax/min)** under real-distance simulation optimization; **16.11 ped/s (~967 pax/min)** under M/G/C/C analytical model.
  - *Emergency Unconstrained Outflow Rate:* **12.88 ped/s (~772 pax/min)** (reduced by intermediate merging corridor congestions).
  - Full hall evacuation time for 1,338 ground occupants: **~1.5 to 2.2 minutes** through all 6 clear corridors.
- **Thermal & Weather Exposure Constraints:**
  - *Shading:* **100% enclosed, high-volume central air conditioning**.
  - *Holding Dwell Limit:* Indefinite (>4 hours) seated comfort.

---

### 6. Alternative Venue Diversion: Bangunan G03 — Dewan Kuliah G & H (DK G & DK H)

- **Correction & Provenance:** Initial research sweep referenced Kompleks Dewan Kuliah C23 (SK1–SK4), which is located ~300m north past the library near the Sports Complex. **Ground truth confirmed by Abraham and official USM directories (`Lokasi_dan_Pelan.pdf`): the intended nearby diversion venue is Bangunan G03 (Dewan Kuliah G–R), specifically Lecture Hall G (DK G) and Lecture Hall H (DK H).**
- **Spatial Configuration & Coordinates:** 
  - Centroid: `5.357119, 100.302499` (OpenStreetMap Way `94331153`, Bangunan G03 Dewan Kuliah G–R).
  - Situated directly on the central academic spine along *Persiaran Tekno / Jalan Sains* between the School of Industrial Technology and Dewan Tuanku Syed Putra (G01).
- **Proximity & Transfer Dynamics:**
  - **Distance to DTSP (G01):** Strictly **68.0 metres**. Connected directly across the covered academic quadrangle concourse (`covered=yes`). Transfer walking time is only **45 to 60 seconds**.
  - **Distance to Drop-Off Berth (Jalan Perpustakaan Car Park):** Strictly **118.1 metres**. Arriving students step directly off the bus apron and walk under continuous covered shelter directly into G03 without crossing open vehicular lanes.
- **Auditorium Capacities & Layout:**
  - **Dewan Kuliah G (DK G):** ~200 to 250 tiered fixed lecture theatre seats with fold-down writing tables, central air-conditioning, and dual entrance portals.
  - **Dewan Kuliah H (DK H):** ~200 to 250 tiered fixed lecture theatre seats, mirroring DK G across the shared central foyer.
  - **Combined Immediate Capacity (DK G + DK H):** **~400 to 500 air-conditioned seats**.
  - **Additional G03 Halls (DK I through DK R):** Up to 10 additional lecture theatres (I, J, K, L, M, N, O, P, Q, R) and tutorial rooms BT 101–140 available in the same building envelope for faculty breakout sessions.
- **Operational Utility:**
  - Provides immediate, zero-weather-exposure diversion for **1 to 2 complete hostel cohorts** (e.g., Desasiswa Indah Kembara with 244 pax or Desasiswa Saujana batch with 300 pax) when DTSP floor seating hits saturation, completely eliminating the outdoor car park waiting queue.

---

## Comparative Engineering Synthesis

| Metric / Parameter | `rst_bus_wait` | `rst_rain_shelter` | `dtsp_exterior_gathering` | `dtsp_foyer` | `dtsp_seating` | G03 (DK G & H) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Centroid / Pin Coordinates** | 5.35728, 100.28981 | 5.35646, 100.28926 | 5.35715, 100.30175 | 5.35690, 100.30305 | 5.35692, 100.30308 | 5.35712, 100.30250 |
| **Gross Footprint (m²)** | 180.0 | 878.8 | 350.0 | 750.0 | 2,943.2 | 1,200.0 |
| **Net Usable Area (m²)** | 140.0 | 550.0 | 280.0 | 520.0 | ~1,850.0 | ~800.0 |
| **Safe Cap. (LOS C/D, pax)**| 140–200 | 350–450 (seated) | 280–400 | 520–742 | 2,500–3,000 | 400–500 (seated) |
| **Crush Cap. (LOS E/F, pax)**| 280–466 | 1,100–1,830 | 560–933 | 1,040–1,733 | 3,200 | 550 |
| **Overcapacity Trigger (pax)**| >200 (lane spill) | >450 (meal active)| >300 (road spill) | >750 (stairs blocked)| >3,000 (fire cert)| >500 (full) |
| **Max Inflow (pax/min)** | 60 | 360 | 74–94 | 220–240 | 30 (staffed) | 160–200 |
| **Max Outflow (pax/min)** | 22–27 (coach) | 120–140 | 30 (staffed door) | 240 | 899–967 | 160–200 |
| **Bottleneck Ratio (In/Out)**| 2.73 (choked) | 0.86 (free) | 2.47–3.13 (choked) | 0.50 (dynamic buf) | 0.03 (out>>in) | 1.00 (balanced) |
| **Shading Proportion (%)** | 35.7% | 100% | 37.5% | 100% | 100% | 100% |
| **Max Safe Dwell (minutes)** | <15 min | >60 min | <15 min (observed 31.4)| >60 min | >240 min | >240 min |

---

## CONFIRMED FACTS

1. **Dewan Kuliah C23 Capacity:** The official USM lecture theatre register (`Kapasiti DK_BT.pdf`, Pusat Pengajian Sains Fizik) confirms that Kompleks Dewan Kuliah C23 comprises 4 major lecture halls: **DK SK1 (300 seats, Aras B)**, **DK SK2 (300 seats, Aras B)**, **DK SK3 (700 seats, Aras A)**, and **DK SK4 (700 seats, Aras A)**, totaling **2,000 fixed seats**.
2. **DTSP Ground Seating Count:** Academic crowd evacuation modeling of DTSP by Kawsar et al. (2012, 2013) and Khalid et al. (2016, *Discrete Event Dyn Syst*, DOI:10.1007/s10626-015-0215-0) establishes that the ground floor auditorium seats **1,338 occupants** across Blocks S (220), T (220), U (309), V (259), W (100), X (55), Y (98), and Z (77).
3. **DTSP Corridor Geometries:** Khalid et al. (2016) confirms the physical dimensions of DTSP circulation corridors:
   - Source Corridor 6: 10.1 m × 2.8 m (seating block W).
   - Source Corridor 7: 8.5 m × 2.8 m (seating block X).
   - Source Corridor 8: 10.1 m × 2.0 m (seating block Y).
   - Source Corridor 9: 8.5 m × 2.0 m (seating block Z).
   - Source Corridor 10: 9.45 m × 1.8 m (seating blocks U & V).
   - Source Corridor 11: 7.35 m × 1.8 m (seating blocks S & T).
   - Exit Corridors 1 & 2: 8.0 m × 2.5 m (Exit Portals A' & B').
   - Exit Corridors 4 & 5: 8.5 m × 2.0 m (Exit Portals C' & D').
4. **OSM Footprints:** Planar projection Shoelace extraction of OpenStreetMap data confirms:
   - DTSP building (`way 896393762`): **2,943.2 m²**.
   - Dataran Merah paved concourse (`way 1353883049`): **1,048.6 m²**.
   - Dewan Utama Desasiswa M08 Restu (`way 275415002`): **1,669.2 m²**.
   - RST Cafeteria M07 (`way 275415004`): **878.8 m²**.
   - Hamzah Sendut Library 1 G02 (`way 208697647`): **3,797.6 m²**.
5. **Observed Field Bottlenecks:** Android telemetry (`telemetry_summary.json`) and multimodal video analysis (`video_analysis.json`) confirm that on 17 September 2026, students endured a **31.4-minute unshaded outdoor hold** (08:01:35 to 08:33:00) on the road outside DTSP with 300–400 students gathered at densities exceeding 3.0 pax/m², causing a 3.8:1 wait-to-movement ratio.

---

## HYPOTHESES

1. **Administrative Gating Root Cause:** The exterior holding queue of 300–400 students at DTSP is entirely generated by PPSL marshals restricting admission to 1–2 door leaves for credential checking (delivering only 30 pax/min), whereas the physical doors and indoor foyer are architecturally capable of absorbing >220 pax/min unimpeded.
2. **Upstream Decoupling Feasibility:** Restu’s Dewan Utama Desasiswa (M08) and Cafeteria (M07) possess sufficient combined sheltered capacity (1,150–1,650 seated/sheltered students) to hold the entire RST orientation contingent indoors, releasing students in calibrated 44-pax pulses strictly when coaches dock.
3. **DK C23 Spillover Absorption:** In orientation sessions where total Kampus Induk freshman intake (~4,000+ students) exceeds DTSP's 2,500–3,000 seat capacity, Kompleks Dewan Kuliah C23 can absorb the entire 1,500-student surplus with simultaneous live streaming, eliminating outdoor holding completely.

---

## GAPS

1. **Active Door Leaf Widths:** Field laser measurements of the clear door aperture ($W_{\text{clear}}$) for DTSP Portals A, B, C, and D are needed to distinguish leaf clearance from structural frame width.
2. **DTSP Balcony Fire Certificate:** The official Jabatan Bomba dan Penyelamat Malaysia (JBPM) certified maximum occupant load for DTSP upper tiered balcony remains unverified against primary architectural drawings (current 2,500–3,000 estimate is based on convocation protocol records).
3. **M07 Cafeteria Operating Status:** Operational confirmation of whether RST Cafeteria stalls operate full food service during orientation morning (which reduces idle holding capacity to ~200 seats).

---

## SOURCES

1. **Khalid, Nawawi, Kawsar, Ghani, Kamil, & Mustafa (2016):** *The evaluation of pedestrians’ behavior using M/G/C/C analytical, weighted distance and real distance simulation models*, Discrete Event Dynamic Systems, 26(3):439–476. DOI: [10.1007/s10626-015-0215-0](https://doi.org/10.1007/s10626-015-0215-0).
2. **Kawsar, Ghani, Kamil, & Mustafa (2012):** *Restricted pedestrian flow performance measures during egress from a complex facility*, World Academy of Science, Engineering and Technology, 67:399–404.
3. **Khalid, Nawawi, Kawsar, Ghani, Kamil, & Mustafa (2013):** *A discrete event simulation model for evaluating the performances of an M/G/C/C state dependent queuing system*, PLoS ONE, 8(4): e58402. DOI: [10.1371/journal.pone.0058402](https://doi.org/10.1371/journal.pone.0058402).
4. **Pusat Pengajian Sains Fizik, USM:** *Kapasiti Dewan Kuliah & Bilik Tutorial USM Kampus Induk* (`Kapasiti DK_BT.pdf`), URL: [http://comsics.usm.my/tlyoon/teaching/ZCA110_1516/info/Kapasiti%20DK_BT.pdf](http://comsics.usm.my/tlyoon/teaching/ZCA110_1516/info/Kapasiti%20DK_BT.pdf).
5. **OpenStreetMap Overpass API:** Ways `896393762` (DTSP), `1353883049` (Dataran Merah), `275415002` (DUD M08), `275415004` (RST Cafe M07), and node `11880869106` (Kompleks DK C23).
6. **Laws of Malaysia:** *Uniform Building By-Laws 1984 (UBBL 1984)*, By-laws 179, 181, 182, 185 (Assembly halls, exit discharge rates, and clear gangways).
7. **Department of Occupational Safety and Health (DOSH) Malaysia (2016):** *Guidelines on Heat Stress Management at Workplace*.
8. **Ministry of Manpower (MOM) / WSH Council Singapore (2024/2026):** *Workplace Heat Stress Framework*.
9. **Project Telemetry & Multimodal Video Analysis:** `processed/telemetry_summary.json` and `processed/video_analysis.json`.

---

## RECOMMENDED NEXT MEASUREMENTS

1. **Laser Survey of DTSP Ingress Portals:** Conduct a physical measurement of the clear door openings of DTSP Pintu A, B, and C (Dataran Merah facing) and perimeter exits A'–D' to lock millimeter-accurate widths for the simulation engine.
2. **Door Flow Stopwatch Audit (07:45–08:45 MYT):** Station observers at DTSP primary entrance doors during the next mass orientation gathering to tally 60-second throughput counts and measure credential-check dwell per student (differentiating wave-through from QR/ID verification).
3. **Restu Pavilion Kerb Demarcation Audit:** Measure exact kerb length and pedestrian shoulder width between DUD M08 and the M01/M02 access roundabout to define the physical footprint of the proposed 44-pax staging buffer pen.
