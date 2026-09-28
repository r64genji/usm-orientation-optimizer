# Restu walk vs OSRM vs recorded GPS (DUD → DTSP)

**Date:** 2026-09-17 (same telemetry day)
**Question:** Did the 31.7 min OSRM walk skip the sky bridge [jejantas] and use public roads instead of the path in the GPS?

**Verdict:** Yes. Default OSRM **foot** from Restu pavilion to DTSP stays on **Jalan Bukit Gambir / Halaman Bukit Gambir / Jalan Universiti / Persiaran Sains**. It never uses OSM way `1030376052` (Jejantas Padang Kawad). Closest approach to the bridge pin: **131.6 m**.

The GPS file **does** go over that bridge: closest fix is **3.6 m** from the pin at ~07:46, walking speed (~0.76 m/s).

Do **not** use 2,371 m / 31.7 min as “how long a Restu student walks if they take the campus sky-bridge path.”

---

## What was compared

| Layer | What it is |
|---|---|
| GPS | Full Sensor Logger track, DUD / Restu pavilion (start 5.3572768, 100.2898076) to DTSP. Includes queue shuffle + bus + outdoor hold. |
| OSRM foot | FOSSGIS `routed-foot`, pavilion → DTSP OSM door |
| OSRM drive | project-osrm driving, same ends |
| OSRM foot forced via jejantas | same foot engine with a via-point on the bridge |

Overlay GeoJSON: `research/reports/restu_walk_full_gps_vs_osrm.geojson`

---

## Numbers

**OSRM**

| Route | Distance | Time | Distance to jejantas | Uses bridge? |
|---|---|---|---|---|
| Foot default | 2,370.9 m | 31.68 min | 131.6 m | No — public/campus roads |
| Driving | 1,976.8 m | 5.25 min | 41.5 m | No — road under/beside |
| Foot **forced via** bridge | 3,120.4 m | 41.59 min | 0 m | Yes, but **longer** |

Forced-via is longer because the foot graph is poorly connected: OSRM still leaves Restu on the same **Jalan Bukit Gambir** fork, then **detours back** to the bridge. The sky-bridge exists in OSM (`highway=footway`, `bridge=yes`, plus steps ways `1030376053`–`1030376056`) but is not the preferred (or even a short) foot path from the pavilion in OSRM.

Foot step names (default): unnamed paths → **Jalan Bukit Gambir** → **Halaman Bukit Gambir** → **Jalan Universiti** → **Jalan Damai** → **Persiaran Sains** → DTSP. That is the public-road / ring-road walk, not the RST jejantas descent.

**GPS (full file)**

| Metric | Value |
|---|---|
| Raw cumulative (all jitter) | 4,310 m |
| Corridor: first time >80 m from DUD until <40 m from DTSP | 2,707 m (5,822 points) |
| Simplified line (≥8 m vertices) | 2,162 m |
| Closest to jejantas | **3.6 m** at lon 100.2928741, lat 5.3564201, ~07:46, speed 0.76 m/s |
| Leave DUD 80 m | ~07:33 (start of the moving queue) |
| First GPS within 40 m of DTSP | ~08:35 |

So the recorded path **does** use the sky-bridge corridor. The 31.7 min OSRM walk is a **different street**.

GPS vs OSRM (mean nearest-neighbour of GPS corridor points):

- vs foot default: mean 102 m, p90 237 m (they are not the same line)
- vs foot via-bridge: mean 77 m (closer, still messy because OSRM’s via route is a detour)
- vs driving: mean 115 m

About half of the default foot polyline sits within 40 m of the GPS (52%). The via-bridge polyline matches more of the GPS (64%) but is not a usable time estimate.

---

## How to use this in the simulator

1. **Do not** put `walk_restu_dtsp_s = 1901` (31.7 min) in `calibration_frozen.json` as the campus walk.
2. Treat at least **two** Restu walking routes:
   - `restu_foot_public_roads` — OSRM default, 2.37 km / ~32 min at 4.5 km/h. Wrong for marshaled freshies if they are sent over the jejantas.
   - `restu_foot_jejantas` — GPS-aligned campus path. Distance still unknown as a clean free-flow walk (GPS includes queue). Need a traced OSM path or a walking GPS with no bus.
3. Fix OSM connectivity (link Restu pavilion footways to way `1030376052` + steps) so OSRM via-bridge stops being a 41 min loop.
4. Until then, walking time prior for Restu via sky-bridge should stay a **gap**, or a downhill estimate from GPS **moving** segments only — not the 31.7 min road walk.

---

## Files

- `research/reports/restu_walk_osrm_check.json`
- `research/reports/restu_walk_osrm_check.geojson`
- `research/reports/restu_walk_full_gps_vs_osrm.json`
- `research/reports/restu_walk_full_gps_vs_osrm.geojson`
