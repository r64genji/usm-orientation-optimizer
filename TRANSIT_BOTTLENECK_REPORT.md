# USM Orientation Transit Bottleneck: Engineering & Operational Analysis

**Subject**: Commute Diagnostics & Theoretical Optimum — Desasiswa Restu to Dewan Tuanku Syed Putra (DTSP)  
**Campus**: Universiti Sains Malaysia (USM) Kampus Induk, Gelugor, Pulau Pinang  
**Event**: Minggu Siswa Lestari (MSL) Orientation Week  
**Cohort Scale**: ~3,000–3,500 First-Year Undergraduates (Main Campus)  
**Hostel Complex**: RST (Restu, Saujana, Tekun) — Western Hill (~6,000 total residents)  
**Author**: Antigravity (Hermes AI Assistant)  
**Date**: September 17, 2026  

---

## 1. Executive Summary & Route Overview

The transit corridor from **Desasiswa Restu** to **Dewan Tuanku Syed Putra (DTSP)** spans:
* **Straight-line distance**: 1.47 km
* **Road/pedestrian network distance**: 1.70 km
* **Elevation delta**: ~25m descent from the western hilly ridge (Desasiswa Restu, elev. ~35m) to the central academic basin (DTSP/PHS, elev. ~10m).

On September 17, 2026, this 1.70 km trip took **151.8 minutes** door-to-seat, with an active transit duration of **59.1 minutes** (effective velocity: **0.58 km/h**).

### Theoretical Fastest Travel Times (By Mode)

```text
+----------------------+--------------------+--------------------+---------------------------------------+
| Mode                 | Avg Speed          | Travel Time        | Practical Feasibility                 |
+----------------------+--------------------+--------------------+---------------------------------------+
| 1. Bicycle / E-Scoot | 18.0 - 20.0 km/h   |  5.1 -  5.7 min    | Immediate (if personal bike/scooter)  |
| 2. Unconstrained Bus | 28.0 km/h (motion) |  6.1 min           | Requires zero queue at boarding & drop|
| 3. Jog / Run         |  8.5 -  9.5 km/h   | 10.7 - 12.0 min    | High exertion in tropical morning     |
| 4. Brisk Walk        |  4.8 -  5.2 km/h   | 19.6 - 21.2 min    | Optimal individual strategy (reliable)|
| 5. Standard Walk     |  4.0 -  4.2 km/h   | 24.2 - 25.5 min    | Comfortable walk downhill             |
| 6. Observed StatusQuo|  0.58 km/h (eff.)  | 59.1 min (transit) | Stalled in dual batching bottlenecks  |
+----------------------+--------------------+--------------------+---------------------------------------+
```

---

## 2. Cohort Volume & Spatial Context

### A. The Inflow Scale: ~3,000–3,500 Freshies Converging Simultaneously
* **USM Total Intake**: ~5,800 new undergraduate students university-wide.
* **Kampus Induk (Main Campus)**: **3,000 to 3,500 new students** attending Minggu Siswa Lestari (MSL) inductions concurrently.
* **Desasiswa Restu (RST Cluster)**: The RST complex (Restu, Saujana, Tekun) on the western hill houses over **6,000 students** total. Restu alone accommodates ~1,700 students (688 male, 999 female).
* **Simultaneous Inflow**: Between 07:15 and 08:00 AM, approximately **800 to 1,200 students** from the RST cluster attempt to depart for DTSP within the exact same 45-minute departure window.

### B. DTSP Venue Architecture & Gating Mechanics
* **Capacity**: ~3,000–3,500 seated auditorium, flanked by ground floor seating, U-shaped mezzanine galleries, and large entrance foyers.
* **Security Protocol**: **Zero security checks.** There are no bag searches, metal detectors, or pat-downs at DTSP.
* **The Real Hall Bottleneck**:
  1. **Door Gating / Restricted Openings**: Despite DTSP having multiple perimeter double-doors, event organizers typically keep only 1–2 main double-doors open to control inflow.
  2. **Zone-Based Ushering**: Organizers seat students strictly by Desasiswa or School in blocks to fill rows sequentially without aisle congestion. When an interior section fills, the exterior inflow is paused.
  3. **Foyer Funneling**: Wide outdoor road crowd is funneled into narrow foyer doors, causing a standing wave out onto the roadway.

---

## 3. Comprehensive Route Bottleneck Map

Tracing the commute step-by-step from Desasiswa Restu room to DTSP auditorium seat:

```text
[Hostel Room]
     │
     ▼  [Bottleneck 1]: High-rise hostel vertical egress (lift / stairwell batching)
[Restu Ground Concourse]
     │
     ▼  [Bottleneck 2]: Hostel road shoulder queue (100–150 students waiting)
[Restu Bus Stop / Pavilion]
     │
     ▼  [Bottleneck 3]: Single-door coach bus ingress (44 seats @ 2.5s/pax = 110s dwell)
[Campus Transit Corridor]
     │
     ▼  [Bottleneck 4]: Peak morning vehicle merges & campus roundabouts
[DTSP Drop-Off Curb]
     │
     ▼  [Bottleneck 5]: Alighting pulse (44–88 students dumped simultaneously on road)
[Roadway outside DTSP]
     │
     ▼  [Bottleneck 6]: 300–400+ student holding reservoir under open sun
[DTSP Outer Double Doors]
     │
     ▼  [Bottleneck 7]: Restricted door width (1–2 doors active, zero security checks)
[DTSP Interior Foyer & Aisles]
     │
     ▼  [Bottleneck 8]: Micro-ushering into specific seat rows / mezzanine stairs
[Assigned Seat in DTSP]
```

### Bottleneck Diagnostics & Durations

1. **Bottleneck 1: Hostel Vertical Egress (06:47–07:10)**
   * Students in multi-story Restu blocks all head down simultaneously, crowding lifts and stairwells.
2. **Bottleneck 2: Restu Staging Pavilion & Road Shoulder (07:10–07:48)**
   * **Duration**: 24–38 minutes.
   * **Mechanism**: 100–150 students queue along the guardrail and grass embankment (`video_15608a256edc`). Demand (1,000+ students/hr) outstrips bus arrivals (250–350 seats/hr).
3. **Bottleneck 3: Single-Door Coach Loading (07:48–07:58)**
   * USM buses have a single narrow front door with steep steps (`video_904e64840a87`). Loading a full 44-passenger bus takes 1.5–2.0 minutes pure dwell time.
4. **Bottleneck 4: Ring Road Transit (07:58–08:01)**
   * **Duration**: Only 3.1 minutes. Transit itself is fast (speeds reach 34.6 km/h).
5. **Bottleneck 6: DTSP Exterior Roadway Holding Reservoir (08:01–08:33)**
   * **Duration**: 31.5 minutes standing on asphalt under full morning sun.
   * **Mechanism**: 300–400+ students stalled outside (`video_fedd16a3e55d`). Because only 1–2 doors are operated to match inside ushering speed, exterior arrival rate (buses dropping 40–80 pax every 5 min) far exceeds hall intake rate (~30–40 pax/min).
6. **The Next-Station Feedback Loop (Systemic Trap)**:
   * DTSP road marshals see the exterior crowd swelling towards safety limits on the roadway.
   * They radio Restu bus coordinators: *"HOLD BUS DEPARTURES."*
   * Restu stops boarding buses. This instantly freezes Bottleneck 2, locking commuters into a 25-minute wait for a 3-minute ride that leads to another 32-minute wait.

---

## 4. Quantitative Comparison: Walk vs. Bus

```text
+---------------------------+-----------------------+-----------------------+
| Metric                    | Shuttle Bus (Status)  | Direct Walk (Option)  |
+---------------------------+-----------------------+-----------------------+
| Origin Departure          | 07:34                 | 07:45                 |
| Transit / Moving Time     |  3.1 min              | 20.0 min              |
| Queue / Stagnant Wait     | 56.0 min              |  0.0 min (unimpeded)  |
| Exterior Sun Exposure     | 56.0 min (static road)| 20.0 min (walking)    |
| Arrival at DTSP Doors     | 08:33                 | 08:05                 |
| Total Door-to-Door Time   | 59.1 min              | 20.0 min              |
| Net Time Advantage        | Baseline              | +39.1 MINUTES SAVED   |
+---------------------------+-----------------------+-----------------------+
```

### Why Walking Bypasses the Feedback Loop
1. Pedestrians flow continuously at ~1.3 m/s and do not arrive in discrete 44-person shockwaves.
2. Leaving Restu at 07:40–07:45 on foot brings the student to DTSP by ~08:02–08:05, arriving just as the hall begins admission, beating the rear of the exterior reservoir.
3. Downhill gradient from Restu eases walking fatigue.

---

## 5. Summary Recommendations

1. **Immediate Personal Rule**: Walk the 1.7 km route directly. Expected walking time: **19–21 minutes**. Eliminates 56 minutes of stagnant waiting.
2. **Shift Departure Window (If Bus Required)**: Depart Restu before **06:55 AM**. First two bus pulses clear DTSP before the exterior reservoir forms. Any departure after 07:15 AM enters the systemic lockup.
3. **Admin Fix for USM Organizers**:
   * Open all 6 exterior double-doors at DTSP (zero security check means doors only need a direction usher).
   * Streamline zone seating: let students enter all perimeter aisles simultaneously rather than single-file theater batching.
