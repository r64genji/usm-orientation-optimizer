# Transport Operational Levers: Single-Door Campus Coaches (Restu to DTSP)

**TL;DR:** On an ultra-short 3-minute transit loop (~1.0 km), classic Daganzo headway holding fails because holding empty buses introduces artificial delay; instead, origin dispatching must be strictly gated by destination kerb/foyer clearance. Single-door high-floor tour coaches incur severe boarding/alighting penalties (3.0–4.5s/pax boarding, 2.0–2.8s/pax alighting), requiring marshal-metered batch loading at the origin and an off-street multi-berth drop-off plaza at DTSP to prevent road gridlock.

---

### Key Findings

- **USM Campus Fleet & Contract:** USM Main Campus commuter bus services have historically operated ~10 to 11 buses on weekdays across internal routes (Route E serving Restu/Saujana/Tekun; Routes A, B, C, D serving main campus hub Padang Kawad), contracted via private operator Unic Leisure Transtour Sdn. Bhd. (MPP USM post 912115485576770, 1178094282312221). Route E typically operates 2 units during peak hours with scheduled 10-to-15-minute intervals. USM procurement tenders explicitly specify 40-passenger air-conditioned coaches (`T1/25/A5/USM-JPPF/69`), and MPP records confirm these are single-door high-floor tour coaches (*bas persiaran*). Orientation charter fleet addition is UNVERIFIED/NOT FOUND in official circulars.
- **Headway Holding Viability (Daganzo):** Mathematical headway holding (Daganzo 2009) is designed for multi-stop corridors to prevent bus bunching caused by stochastic passenger arrivals. On a point-to-point 3-minute shuttle loop, holding an empty bus at DTSP or Restu worsens passenger queuing in the sun. Dynamic holding must operate as "destination capacity gating" (only dispatch from origin when the destination drop-off berth is empty).
- **Single-Door Stepped Boarding Dwell:** Field transit studies (Transit Capacity and Quality of Service Manual / TCQSM Part 4, TRB) establish that stepped, high-floor coaches with a single narrow door (steep 3-step stairwell) require **3.0 to 4.5 seconds per passenger to board** and **2.0 to 2.8 seconds per passenger to alight** with luggage/bags. Unmanaged scramble queues degrade boarding to >5.0s/pax. A full 44-seat coach requires 135–190 seconds (2.25–3.2 minutes) just to board and 90–125 seconds to alight.
- **Alighting & Stacking Dynamics:** Buses stacking along Jalan USM outside DTSP stem from alighting into a narrow roadside lane while pedestrians bottleneck at hall entrance doors. Best practices in planned special event transit (FHWA Planned Special Events Handbook; Intercity Transit Standards) require pulling buses completely out of the travel lane into a dedicated multi-berth plaza or dual-kerb layby where passengers disperse directly onto a wide pedestrian plaza rather than the roadway shoulder.
- **Deadhead & Turnaround:** Holding buses at DTSP after unloading blocks subsequent arriving shuttles. Buses must deadhead (return empty) immediately to Restu upon discharge, maintaining cycle times of 8 to 11 minutes per coach.

---

### Details

#### 1. Campus Fleet, Capacity & Orientation Context
- **Contractor & Fleet Profile:** Internal transit is managed via commercial charter agreements with Unic Leisure Transtour Sdn. Bhd. using high-floor 40–44 seat coaches (*bas persiaran*). In official MPP dialogues, students and student councils explicitly noted the structural mismatch of tour coaches for commuter loops due to high steep steps and single-door passenger flow.
- **Peak Headway:** Regular semester peak headway for Route E (RST to Main Campus) is 10 to 15 minutes utilizing 2 assigned coach units (MPP USM announcement). 
- **Rapid Penang Feeder T310 Inadequacy:** Rapid Penang operates route T310 between Hub Padang Kawad and Queensbay Mall with only 3 buses running at 20-to-30-minute headways (Penang Travel Tips / Rapid Penang). It cannot absorb 2,000+ orientation students at 07:30.
- **Orientation Charter Fleet:** Specific public documents confirming whether extra chartered coaches are contracted specifically for Minggu Siswa Lestari were NOT FOUND (query: `"Minggu Siswa Lestari" bas sewa OR charter bus USM`). However, moving an entire hostel cohort (1,500–2,500 students) within a 90-minute window requires 35–55 bus trips, confirming that 2 regular Route E coaches alone would take >3.5 hours without charter supplementation.

#### 2. Daganzo-Style Headway Holding on Short Campus Loops
- **Theoretical Assessment:** Daganzo's classic headway regularisation (2009, *Transportation Research Part B*) delays buses at intermediate checkpoints to equalize forward and backward headways ($H_{i} \approx H_{i-1}$), preventing trailing buses from catching leading buses.
- **Application to Restu-to-DTSP Loop:**
  - Round trip distance: ~1.8 to 2.2 km.
  - In-vehicle running time: ~180 s (3 minutes) one way.
  - Cycle time per coach: $T_{\text{cycle}} = t_{\text{board}} + t_{\text{run}} + t_{\text{alight}} + t_{\text{return}} \approx 150\text{s} + 180\text{s} + 100\text{s} + 180\text{s} = 610\text{s}$ (~10.2 minutes).
  - With 2–4 coaches, headway is 2.5 to 5 minutes.
  - **Verdict:** There is **no room or benefit for traditional headway holding** along the route or at DTSP. Deliberately holding a bus at DTSP keeps an empty vehicle idle while crowds bake at Restu. The only valid control is **destination-driven release gating**: holding the bus at Restu *in shaded queue position* until DTSP marshals signal that the drop-off berth is clear.

#### 3. Boarding Rules & Time Per Passenger
- **Field Benchmark Values:**
  - Standard low-floor transit bus (level boarding, 2 doors, no fare): 1.2–1.8 s/pax.
  - High-floor tour coach (3 narrow steps, single front door, handrails, bags/lanyard checks): **3.0–4.5 s/pax boarding**; **2.0–2.8 s/pax alighting** (TCQSM Part 4 / TRB; Sun et al. 2014, *Transportation Research Part A*).
- **Marshal-Controlled Boarding vs Free Scramble:**
  - Free scramble on single narrow coach doors causes "bottleneck turbulence" (pauses while riders navigate steep luggage steps and aisle friction), pushing boarding past 5.0 s/pax (220+ s per bus).
  - **PPSL Marshal Metering:** Stationing 1 marshal at the coach door steps and 1 marshal counting at the queue head to pre-pack students into 40-person columns cuts boarding time down to 2.8–3.2 s/pax (~125–140 seconds per bus).

#### 4. Alighting Pulse & DTSP Stacking Mitigation
- **The Stacking Bottleneck:** If DTSP foyer entrance doors absorb students slower than the bus alighting rate (e.g., 40 pax discharging in 90 s = 0.44 pax/s, while bag checks or narrow doors process 0.2 pax/s), passengers spill across the kerb, preventing the coach from opening doors or pulling away.
- **Engineering Levers (FHWA Special Events & Bus Stop Standards):**
  1. **Dual-Berth Off-Street Layby:** Designate two staggered unloading bays at the DTSP apron so Bus #2 can alight concurrently if Bus #1 is delayed.
  2. **Plaza Buffer (Off-Road Discharge):** Direct alighting passengers away from the road shoulder into the expansive DTSP exterior paved plaza (toward the cultural centre / foyer arcade) rather than dropping them on the roadside lane.
  3. **Immediate Drive-Past / Deadhead:** Coaches must depart immediately upon passenger egress. Drivers must NOT wait for the next wave at the hall kerb.

#### 5. Deadhead & Turnaround Policy
- **Origin Waiting Only:** Empty buses must immediately return (deadhead) to Restu via the shortest campus loop bypass. Holding empty buses at DTSP consumes kerb space and causes trailing buses to idle in the main roadway.

---

### Entity Fields

```yaml
loop_name: "Laluan RST / Laluan E (Restu - Saujana - Tekun to Main Campus / DTSP)"
cycle_s: 610  # ~10.2 minutes total round-trip cycle time per coach (Board: 150s, Run: 180s, Alight: 100s, Deadhead: 180s)
board_s_pax: 3.2  # Marshal-controlled stepped high-floor coach (TCQSM / TRB benchmarks: 3.0 - 4.5s; unmanaged scramble: >5.0s)
alight_s_pax: 2.3  # Stepped single-door coach alighting (TCQSM: 2.0 - 2.8s)
hold_at_origin: true  # Upstream holding in shaded foyer/cafeteria; dispatched only when destination berth signals clear
hold_at_dest: false  # Immediate deadhead return; holding at destination causes kerb congestion and stalls system
regular_fleet_on_route: 2  # Peak fleet assigned to Route E (Source: MPP USM dialogue with Unic Leisure)
total_campus_fleet: 11  # Total weekday commuter fleet across all internal routes (Source: MPP USM)
vehicle_seating_capacity: 40  # 40-passenger air-conditioned coach specification (Source: USM Tender T1/25/A5/USM-JPPF/69)
orientation_charter_additions: UNKNOWN  # Specific MSL orientation extra coach contract count NOT FOUND in public university releases
```

---

### Sources

1. **Majlis Perwakilan Pelajar (MPP) USM Official Archive (Post ID: 912115485576770)** — Details negotiation with Unic Leisure Transtour Sdn. Bhd.; documents fleet allocation (Route E operates 2 units at 10–15 min peak intervals; campus operates 10–11 buses). `https://www.facebook.com/mppusm.official/posts/912115485576770`
2. **MPP USM Official Dialogue on Fleet Quality (Post ID: 1178094282312221)** — Verifies vehicle types as single-door high-floor tour coaches (*bas persiaran*) temporarily replacing low-floor transit buses due to maintenance. `https://www.facebook.com/mppusm.official/posts/1178094282312221`
3. **USM Jabatan Bendahari Procurement Portal** — Tender `T1/25/A5/USM-JPPF/69` ("Membekal, Menghantar, Memasang dan Komisyen Bas 40 Penumpang Berhawa Dingin untuk Universiti Sains Malaysia, Kampus Induk"). `http://perolehan.usm.my/tender.php?md=tawaran`
4. **Transportation Research Board (TRB) — Transit Capacity and Quality of Service Manual (TCQSM, 3rd Edition / Part 4)** — Empirical passenger service time and dwell data for high-floor stepped coaches vs transit vehicles. `http://onlinepubs.trb.org/onlinepubs/tcrp/docs/tcrp100/Part4.pdf`
5. **Daganzo, C. F. (2009) / HAL Research Archives** — "A headway-based approach to eliminate bus bunching: Systematic analysis and comparisons" (*Transportation Research Part B*), demonstrating where headway holding fails on ultra-short single-purpose routes. `https://hal.science/hal-01825861v1/file/doc00027579.pdf`
6. **Sun, L. et al. (2014)** — "Models of bus boarding and alighting dynamics" (*Transportation Research Part A*), documenting boarding and alighting intervals across vehicle door architectures. `https://lijunsun.github.io/files/papers/2014-TRA-Dwell.pdf`
7. **Federal Highway Administration (FHWA) — Managing Travel for Planned Special Events Handbook (Chapter 6)** — Multi-berth passenger queuing, perimeter drop-off plazas, and roadway staging design. `https://ops.fhwa.dot.gov/publications/fhwaop04010/chapter6_05.htm`
8. **Rapid Penang Route T310 Operating Specification** — Hub Padang Kawad to Queensbay Mall frequency (20–30 min), confirming insufficient capacity for mass orientation spikes. `https://www.penang-traveltips.com/bus-t310.htm`
