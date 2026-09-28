# 54: Ground Truth Operational Audit — DTSP Drop-Off Berths, Door Ingress & Coach Loading

**Author:** Staff Software Engineer (Coder)  
**Date:** 2026-09-22  
**Status:** GROUND TRUTH LOCKED (Operational corrections from Abraham Tan)

---

## 1. Ground Truth Operational Principles

1. **NO Credential or Security Checks at DTSP Doors:**
   - There are **no bag checks, lanyard scans, or ticket verification tables** at the entrance doors of Dewan Tuanku Syed Putra (DTSP).
   - Students walk straight into the building unimpeded and proceed directly to their seats.
   - Previous hypotheses modeling a 30 pax/min bottleneck from staffed check-in tables are **superseded and retired**.

2. **Full Coach Crush Loading with Standees:**
   - Orientation coaches operate at **absolute full capacity**.
   - Standing students fill the entire length of the center aisle from the back row all the way down to the front boarding stairwell.
   - Effective vehicle capacity: **65 to 80 passengers per coach** (40–44 seated + 25–36 standees).
   - Boarding dwell time at Restu: **105 seconds (1 minute 45 seconds)** per coach.

3. **Straight-Line Car Park Drop-Off Configuration at DTSP:**
   - Disembarkation does not occur at a restricted single-bus curb.
   - The drop-off area is a wide, straight roadway / parking apron along Jalan Perpustakaan / Dataran Merah approach.
   - Because the road is a continuous straight line, **many buses can dock and discharge simultaneously** (up to 6–10 coaches in line or parallel bays).

---

## 2. Revised Physical Capacity & Flow Throughput Calculations

### A. Bus Capacity & Fleet Pulses
- **Single Coach Passenger Capacity ($C_{\text{coach}}$):**
  $$\text{Seated: } 40\text{--}44 \quad | \quad \text{Standees: } 25\text{--}36 \quad \implies \quad \mathbf{C_{\text{coach}} = 65\text{ to }80\text{ students}}$$
- **Fleet Pulse (8 Buses: 5 Coaches + 3 Electric):**
  - 5 Coaches @ 70–80 pax = 350–400 students.
  - 3 Electric Shuttles @ 50–60 pax = 150–180 students.
  - **Single Fleet Wave Total:** **500 to 580 students delivered per round-trip cycle**.

### B. DTSP Drop-Off / Parking Berths Throughput
- **Docking Envelope:**
  - Standard coach length: 12.0 m + 3.0 m maneuvering clearance = 15.0 m per docking slot.
  - Along the straight roadway and open parking apron (~120–150 m linear length), **8 to 10 buses can physically dock concurrently**.
- **Simultaneous Unloading Capacity:**
  - With 4 to 6 buses unloading at once:
    $$Q_{\text{disembark, peak}} = 4\text{ to }6\text{ buses} \times (65\text{--}80\text{ pax}) = \mathbf{260\text{ to }480\text{ students discharged in } 60\text{ seconds}}$$
  - Individual passenger alighting rate: **0.8 to 1.1 s/pax** (fast gravity-assisted step down, unobstructed wide tarmac).
  - Net vehicle unloading dwell: **50 to 65 seconds**.
  - **Maximum Alighting Throughput:** **>4,500 to 6,000 students/hour** (berth capacity is completely unconstrained by geometry).

### C. DTSP Hall Entry & Seating Throughput (Free-Flow Ingress)
- **Unrestricted Doorway Capacity (Double-Leaf Glass Doors):**
  - Standard free-flow pedestrian doorway flow: **80 to 110 pax/minute per double-leaf door** (Green Guide / HCM).
  - Active Entry Doors:
    - Door A (Western approach): 1 double door = **80–110 pax/min**.
    - Door B / Dataran Merah (Main concourse): 2 double doors = **160–220 pax/min**.
    - Lateral Doors C & D: 2 double doors = **160–220 pax/min**.
  - **Total Free-Flow Doorway Ingress Capacity:** **400 to 550 students/minute (24,000 to 33,000 students/hour)**.
  - *Conclusion:* The physical doors do not throttle flow once opened.

### D. Internal Hall Seating & Aisle Absorption
- **Auditorium Ingress Dynamics:**
  - Main floor seating: **1,338 seats** across 8 blocks (S–Z).
  - Seating is fed by 4 primary longitudinal aisles (Corridors 6, 7, 8, 9; widths 2.0–2.8 m).
  - Rate of students moving down aisles and sliding into rows of fixed theater seats:
    $$Q_{\text{seating}} \approx 30\text{ to }40\text{ pax/min per aisle} \times 4\text{ aisles} = \mathbf{120\text{ to }160\text{ students/minute}}$$
  - **Full Ground Floor Fill Time (1,338 seats):**
    $$T_{\text{fill}} = \frac{1,338\text{ seats}}{120\text{--}160\text{ pax/min}} \approx \mathbf{8.4\text{ to }11.1\text{ minutes}}$$

---

## 3. The True Mechanism of the Exterior Holding Crowd

Since:
1. Buses can dock 6–10 at once and dump 400+ students in 1 minute on the straight road/parking area;
2. There are **zero checks at the doors**;
3. Hall doors can swallow >400 students/minute;

**Why did 300–400 students wait on the road on 17 September for 31.4 minutes?**

1. **Operational Staging and Headcounts (Doors were NOT locked):**
   - DTSP auditorium doors are open and accessible from the start; doors are **NOT locked until 08:32**. The claim that doors were locked until 08:32 is false.
   - Any wait outside DTSP is operational event staging, PPSL headcounts, or holding in the pre-DTSP holding areas, not locked entrance doors.
2. **Arrival-Rate to Seating-Rate Mismatch:**
   - Students enter freely without door screening, and aisle seating proceeds at ~140 pax/min.
   - If multiple full buses (each with 70–80 students) discharge faster than seats can be occupied, backlogs form at the drop-off / exterior staging area.

---

## 4. Key Takeaways for Simulator Calibration

1. **`door_intake_rate`:** Set to free-flow **80–110 pax/min per double door** (not 15–30 pax/min).
2. **`check_in_dwell`:** Set to **0.0 seconds** (no door checks).
3. **`berth_docking_slots` at DTSP:** Set to **6 to 8 vehicles** (straight road/parking apron), with simultaneous discharge enabled.
4. **`coach_capacity`:** Set to **70–80 passengers** (crush loading with full center aisle standees).
5. **`hall_open`:** Doors are open from the start (no artificial calendar lock until 08:32). Exterior delays are operational headcounts and staging.
