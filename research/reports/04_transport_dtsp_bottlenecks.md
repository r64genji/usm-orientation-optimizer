# 04 Transport, DTSP architecture, and simulator entities

**Status:** SALVAGED. Researcher session `20260917_144109_6d577e` (Hermes `-p researcher`) ran 19m 23s / 200 tool calls, then died on `finish_reason=length` (reasoning ate the output budget). It never wrote this file. Facts below are recovered from that log. Treat as a research draft, not a second independent audit.

**TL;DR:** Everyday USM campus buses are **high-floor tour coaches** (UNIC Leisure Transtours), not city buses. Route **E / RST** is the Restu–Padang Kawad–ring-road loop that dumps onto **Jalan Perpustakaan** beside DTSP. DTSP main-floor seating modelled in a 2013 paper is **1,338** seats (blocks S–Z); full hall including mezzanine is cited as ~2,500–3,500, not a locked official certificate. Orientation still uses **destination-gated holds** [DTSP radios Restu to stop boarding]. Fleet size on an MSL morning is **not measured**.

---

## Key findings (with confidence)

### Buses
- Operator named in the session: **UNIC Leisure Transtours Sdn. Bhd.** contracting campus commuter service. Confidence: **medium** (MPP/Facebook + ePrint 58403 — re-open those URLs before encoding).
- Vehicle type: **single-deck high-floor tour coaches**, typically **one boarding door**, no transit-style stop buttons. Matches field videos in this repo (coach boarding pulse). Confidence: **high for orientation morning 2026-09-17** (video); **medium** that the same type is the all-year fleet.
- Named campus routes in the log: **A, AC, B, C, D, E (RST)**. Route E is the RST cluster link (canteen / jejantas / Padang Kawad / ring / Jalan Perpustakaan / DTSP). Confidence: **medium**.
- Everyday headway cited 10–20 min. **MSL extra charters** were asserted but not proven with a 2026 work order. Confidence: **low**.
- Everyday active fleet cited **~10 buses + 4 vans**, RM 780/bus/day, from the campus-bus thesis / MPP notices. **Do not use 10 as the MSL morning RST allocation.** That is the do-not-hallucinate item. Confidence: **low for optimizer**.
- Rapid Penang **T310** still feeds Hub Padang Kawad (also in report 01). Separate from internal shuttles.
- Field prior (this repo, N=1 clip): boarding **~2.5 s/pax**, 44 seated if the coach is a 44-seater. Confirm plate + seat count in the field.

### DTSP
- Published pedestrian-flow paper (Kawsar et al., DTSP egress): main floor blocks S=220, T=220, U=309, V=259, W=100, X=55, Y=98, Z=77 → **1,338 seats modelled**. Session summed this in Python. Confidence: **high for that paper’s model**, not for 2026 fire certificate.
- Full hall including mezzanine / galleries: session range **2,500–3,500**. Matches older repo notes. Confidence: **medium**.
- Doors in that literature / session notes:
  - Foyer double doors **Pintu A, B, C** (B often VIP).
  - Four perimeter / corridor exits **A', B', C', D'**.
- MSL practice (field + video, not a plan): **1–2 doors staffed** for seating control. Confidence: **high that restriction happens**, **unmeasured** how many were open on 2026-09-17.
- UBBL 1984 comment in the log (3,000 occupants need large total exit width) is a **legal hypothesis**, not a JBPM inspection.

### Drop-off geometry
- Alighting road: **Jalan Perpustakaan**, OSM-queried in-session, two-lane, treated as **one-way** during big events (also report 01).
- Sidewalk too narrow for a 44-pax pulse → spill onto carriageway, unshaded. Matches telemetry stage 4 (08:01:35 reservoir at 5.3568866, 100.3030831).
- Holding pen is the **road + kerb**, not a designed plaza.

### Control
- **ThrottleLink:** DTSP exterior density over a safety feel → radio “hold bas kat Restu”. Reactive. Buses already rolling still arrive (pipeline fill). Radio lag **unmeasured** (prior: 0.5–3 min if you must assume, label `assumed`).
- Analog: airport gate-hold, Kanban, theme-park virtual queue — **proactive** release, not after the road is already full.

---

## Simulator entity list (attributes + units)

Use these names in `sim/`. Null anything not measured.

**Bus**
- `bus_id` string
- `vehicle_type` enum {tour_coach, city_bus, van, unknown}
- `seated_capacity_pax` int (prior 44, source measured_n1|official)
- `boarding_doors` int (prior 1)
- `board_s_per_pax` float (prior 2.5)
- `alight_s_per_pax` float (prior ~1.2, assumed)
- `assigned_route_id` string
- `cycle_s` float (RST→DTSP→RST, **unknown**)
- `state` enum {idle, boarding, running, alighting, held}

**Stop**
- `stop_id` (e.g. `STOP_RESTU_PAVILION`, `STOP_DTSP_JALAN_PERPUSTAKAAN`)
- `place_id` FK
- `kerb_length_m` float
- `is_shaded` bool
- `holding_capacity_pax` int (Restu shoulder ~400 was a video bound, not a design cap)

**Door**
- `door_id` (A, B, C, A', B', C', D')
- `kind` enum {foyer, perimeter, vip}
- `width_m` float (**unknown**)
- `open` bool (time-varying)
- `service_s_per_pax` float (QR vs wave-through)
- `flow_pax_per_min` derived

**HoldingPen**
- `pen_id`
- `place_id`
- `area_m2` float
- `density_cap_pax_m2` float (policy prior 1.5)
- `is_shaded` bool
- `occupancy_pax` int (sim state)

**ThrottleLink**
- `from_station` DTSP_pen
- `to_station` RESTU_stop
- `trigger_occupancy_pax` int (video bound 300–400)
- `radio_lag_s` float (**unknown**)
- `hold_release_hysteresis_pax` int (assumed: don’t flap)

---

## Parameter priors (for calibration file, not frozen)

| Param | Prior | Source class | How to measure |
|---|---|---|---|
| board_s_per_pax | 2.5 | measured_n1 video | stopwatch at first step |
| alight_s_per_pax | 1.2 | assumed | same at DTSP kerb |
| door_pax_per_min (2 doors) | 30 | assumed | 60 s tallies 07:45–08:45 |
| holding unsafe | 300–400 visible | measured_n1 video bound | density polygon + photos |
| bus cycle Restu–DTSP–Restu | unknown (03 used 20 min as math example) | assumed | plate log |
| radio lag | unknown | — | timestamp hold call vs last board |
| MSL RST fleet | unknown | — | count unique plates 07:00–08:30 |
| seated cap | 44 | measured_n1 / typical coach | photograph interior / operator spec |

---

## CONFIRMED (enough to code stubs)

1. Drop-off is Jalan Perpustakaan next to DTSP; reservoir is the road.
2. Vehicles in the 2026-09-17 videos are coaches with single-file boarding.
3. Destination-gated hold exists (this repo notes + radio story).
4. Kawsar-style DTSP door labels (A/B/C and A'–D') are a usable **id scheme** until a floor plan PDF is obtained.

## HYPOTHESES

1. Everyday fleet ~10 coaches; MSL adds charters.
2. Opening foyer A+C (not VIP B) plus two perimeter doors raises ingest above bus pulse rate and kills the outdoor pen.
3. Tour-coach single door is the boarding bottleneck at Restu; a two-door city bus would cut dwell.

## GAPS (still blocking)

1. MSL morning **plate list** / fleet assigned to RST.
2. True **round-trip cycle** including hold time.
3. DTSP **door widths** and which doors were open 2026-09-17.
4. Official **seating / fire occupancy** certificate (1,338 is a paper’s main floor, not the cert).
5. Radio lag distribution.

## SOURCES (as cited in the researcher log)

1. http://eprints.usm.my/58403/1/Kajian%20Keberkesanan%20Sistem%20Bas%20Kampus%20Induk%20USM_Muhammad%20Nizar%20Saddum.pdf — campus bus study / capacities
2. Kawsar et al. pedestrian flow at DTSP (WASET / SciAlert / PMC copies hunted in-session) — seating blocks S–Z = 1,338
3. MPP USM Facebook notices on bas komuter / Rapid T310
4. OSM Overpass: `Jalan Perpustakaan`, DTSP way 896393762
5. This repo: `processed/telemetry_summary.json`, `processed/video_analysis.json`
6. Session log: `research/logs/04_transport_dtsp_bottlenecks.log`

## Recommended next measurements

Same as context pack §9: plate log, door stopwatch, radio timestamp. Then rewrite this file from primary PDFs, not from this salvage.
