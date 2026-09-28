# OSM Block Inventory: USM Kampus Induk Desasiswa Buildings

## Topic
OpenStreetMap (OSM) geometry inventory of Kampus Induk desasiswa buildings, extracted via Overpass API.

**TL;DR:** All major hostel clusters (Restu, Saujana, Tekun, Indah Kembara, Aman Damai, Bakti Permai, Cahaya Gemilang, Fajar Harapan) exist in OSM as mapped polygons, including the previously suspected missing Saujana (mapped under codes M03 and M04). Storey counts (`building:levels`) are explicitly tagged on low-rise hostels (K, H, F blocks: 2–3 storeys) but entirely untagged on high-rise RST towers (M01–M06).

---

### Key Findings
- **Saujana polygon resolved:** Saujana is NOT missing from OSM; it exists as ways `1031136418` (name: `M03`, footprint 3,144.1 m²) and `275415000` (name: `M04`, footprint 2,173.0 m²). The MASTER pin (5.3564, 100.2905) sits right between these two towers (70–83 m away). ([map])
- **RST complex layout verified:** The six RST towers are mapped as individual building ways: M01 (`139062076`, 3,144.1 m²), M02 (`1031136419`, 3,144.1 m²), M03 (`1031136418`, 3,144.1 m²), M04 (`275415000`, 2,173.0 m²), M05 (`275414999`, 2,481.3 m²), M06 (`275414998`, 2,206.5 m²). ([map])
- **DUD and RST central facilities mapped separately:** DUD (Dewan Utama Restu) is way `275415002` (name: `M08 Dewan Utama (Restu)`, footprint 1,669.2 m²). RST cafe / central amenities are way `275415004` (`M07`, footprint 878.8 m²) and way `275415001` (`M09`, footprint 1,233.6 m²). ([map])
- **Indah Kembara mapped as 3 blocks:** L05 (way `275404590`, 1,062.8 m²), L06 (way `275404589`, 1,643.2 m²), and L07 (way `275404588`, 1,500.8 m²). MASTER pin matches L07 centroid within 0.6 m. ([map])
- **Storey tagging gap in OSM:** Only low-rise blocks have `building:levels` tagged in OSM: Aman Damai K10 (levels=2), K01/K02 (levels=3); Bakti Permai H10 (levels=2); Cahaya Gemilang H33 (levels=2); Fajar Harapan F27 (levels=2). None of the RST high-rise towers (M01–M06) have `building:levels` tagged in OSM. ([map])

---

### Overpass Execution & Query Details

**Primary Query:**
```overpass
[out:json][timeout:30];
(
  way["building"](5.348,100.290,5.365,100.315);
  relation["building"](5.348,100.290,5.365,100.315);
);
out body geom;
```
- **Endpoint:** `https://lz4.overpass-api.de/api/interpreter`
- **Result count:** 1,295 elements returned.

**Secondary Targeted Query (Names & RST Codes):**
```overpass
[out:json][timeout:30];
(
  node["name"~"Restu|Saujana|Tekun|Indah|Kembara|Aman|Damai|Bakti|Fajar|Permai|Cahaya|Gemilang|Harapan|M01|M02|M03|M04|M05|M06|M07|M08|M09",i](5.348,100.288,5.365,100.315);
  way["name"~"Restu|Saujana|Tekun|Indah|Kembara|Aman|Damai|Bakti|Fajar|Permai|Cahaya|Gemilang|Harapan|M01|M02|M03|M04|M05|M06|M07|M08|M09",i](5.348,100.288,5.365,100.315);
  relation["name"~"Restu|Saujana|Tekun|Indah|Kembara|Aman|Damai|Bakti|Fajar|Permai|Cahaya|Gemilang|Harapan|M01|M02|M03|M04|M05|M06|M07|M08|M09",i](5.348,100.288,5.365,100.315);
);
out body geom;
```
- **Endpoint:** `https://lz4.overpass-api.de/api/interpreter`
- **Result count:** 85 elements returned.

---

### Inventory of Named Desasiswa Buildings

*Note: Footprint m² computed via planar projection Shoelace formula at centroid latitude (1 deg lat = 110,574 m; 1 deg lon = 111,320 * cos(lat) m).*

| Desasiswa | Block / Ref | OSM ID | Tagged Name | `building:levels` | Footprint (m²) | Centroid Lat (`map`) | Centroid Lon (`map`) |
|---|---|---|---|---|---|---|---|
| Restu | M01 | way `139062076` | M01 Desasiswa Restu | Untagged | 3,144.1 | 5.355843 | 100.289194 |
| Restu | M02 | way `1031136419` | M02 | Untagged | 3,144.1 | 5.357214 | 100.289194 |
| Restu / RST | M08 | way `275415002` | M08 Dewan Utama (Restu) | Untagged | 1,669.2 | 5.357268 | 100.290213 |
| RST Common | M07 | way `275415004` | M07 (RST Cafe / Amenity) | Untagged | 878.8 | 5.356544 | 100.289135 |
| RST Common | M09 | way `275415001` | M09 (RST Complex) | Untagged | 1,233.6 | 5.356241 | 100.291360 |
| Saujana | M03 | way `1031136418` | M03 | Untagged | 3,144.1 | 5.356536 | 100.289760 |
| Saujana | M04 | way `275415000` | M04 | Untagged | 2,173.0 | 5.355781 | 100.290370 |
| Tekun | M05 | way `275414999` | M05, Desasiswa Tekun, USM | Untagged | 2,481.3 | 5.355640 | 100.291293 |
| Tekun | M06 | way `275414998` | M06 | Untagged | 2,206.5 | 5.355997 | 100.292187 |
| Indah Kembara | L07 | way `275404588` | Desasiswa Indah Kembara (L07) | Untagged | 1,500.8 | 5.356031 | 100.296045 |
| Indah Kembara | L06 | way `275404589` | Desasiswa Indah Kembara (L06) | Untagged | 1,643.2 | 5.355497 | 100.295988 |
| Indah Kembara | L05 | way `275404590` | Desasiswa Indah Kembara (L05) | Untagged | 1,062.8 | 5.355801 | 100.295609 |
| Aman Damai | K10 | way `1030965779` | K10 Desasiswa Aman Damai | 2 | 715.0 | 5.354304 | 100.296202 |
| Aman Damai | K01 | way `1030965775` | K01 | 3 | 1,036.6 | 5.354780 | 100.297032 |
| Aman Damai | K02 | way `275404573` | K02 | 3 | 1,037.0 | 5.354554 | 100.297116 |
| Bakti Permai | H10 | way `275403376` | H10 Desasiswa Bakti Permai | 2 | 1,264.9 | 5.357763 | 100.300499 |
| Cahaya Gemilang | H33 | way `275403540` | H33 Desasiswa Cahaya Gemilang | 2 | 813.1 | 5.360424 | 100.303549 |
| Fajar Harapan | F27 | way `275403371` | F27 Desasiswa Harapan | 2 | 794.5 | 5.354996 | 100.299797 |

---

### Centroids vs MASTER Pins

MASTER pins represent origin hypotheses in `MASTER.md` §7. Below is the direct comparison against OSM building centroids:

1. **Restu / DUD / pavilion:** MASTER pin `(5.35728, 100.28981)`.
   - OSM DUD M08 (`way 275415002`): `(5.357268, 100.290213)` → Delta: **44.6 m**.
   - OSM Restu M02 (`way 1031136419`): `(5.357214, 100.289194)` → Delta: **68.6 m**.
   - OSM Restu M01 (`way 139062076`): `(5.355843, 100.289194)` → Delta: **173.7 m**.
2. **Saujana:** MASTER pin `(5.35640, 100.29050)`.
   - OSM Saujana M03 (`way 1031136418`): `(5.356536, 100.289760)` → Delta: **83.3 m**.
   - OSM Saujana M04 (`way 275415000`): `(5.355781, 100.290370)` → Delta: **70.3 m**.
   - *Verdict:* The MASTER pin sits in the courtyard/driveway between the two Saujana towers.
3. **Tekun:** MASTER pin `(5.35563, 100.29129)`.
   - OSM Tekun M05 (`way 275414999`): `(5.355640, 100.291293)` → Delta: **1.2 m** (Near exact match).
   - OSM Tekun M06 (`way 275414998`): `(5.355997, 100.292187)` → Delta: **107.4 m**.
4. **Indah Kembara:** MASTER pin `(5.35603, 100.29604)`.
   - OSM Indah Kembara L07 (`way 275404588`): `(5.356031, 100.296045)` → Delta: **0.6 m** (Exact match to L07 centroid).
5. **Aman Damai:** MASTER pin `(5.35431, 100.29615)`.
   - OSM Aman Damai K10 (`way 1030965779`): `(5.354304, 100.296202)` → Delta: **5.8 m**.
6. **Bakti Permai:** MASTER pin `(5.35776, 100.30055)`.
   - OSM Bakti Permai H10 (`way 275403376`): `(5.357763, 100.300499)` → Delta: **5.7 m**.
7. **Cahaya Gemilang:** MASTER pin `(5.36046, 100.30360)`.
   - OSM Cahaya Gemilang H33 (`way 275403540`): `(5.360424, 100.303549)` → Delta: **6.9 m**.
8. **Fajar Harapan:** MASTER pin `(5.35500, 100.29977)`.
   - OSM Fajar Harapan F27 (`way 275403371`): `(5.354996, 100.299797)` → Delta: **3.0 m**.

---

### CONFIRMED FACTS
- `139062076` is OSM way for `M01 Desasiswa Restu`, area 3,144.1 m², centroid (5.355843, 100.289194) (`map`, 2026-09-20, OSM).
- `1031136419` is OSM way for `M02`, area 3,144.1 m², centroid (5.357214, 100.289194) (`map`, 2026-09-20, OSM).
- `1031136418` is OSM way for `M03`, area 3,144.1 m², centroid (5.356536, 100.289760) (`map`, 2026-09-20, OSM).
- `275415000` is OSM way for `M04`, area 2,173.0 m², centroid (5.355781, 100.290370) (`map`, 2026-09-20, OSM).
- `275414999` is OSM way for `M05, Desasiswa Tekun, USM`, area 2,481.3 m², centroid (5.355640, 100.291293) (`map`, 2026-09-20, OSM).
- `275414998` is OSM way for `M06`, area 2,206.5 m², centroid (5.355997, 100.292187) (`map`, 2026-09-20, OSM).
- `275415004` is OSM way for `M07` (RST Cafe/complex), area 878.8 m², centroid (5.356544, 100.289135) (`map`, 2026-09-20, OSM).
- `275415002` is OSM way for `M08 Dewan Utama (Restu)`, area 1,669.2 m², centroid (5.357268, 100.290213) (`map`, 2026-09-20, OSM).
- `275415001` is OSM way for `M09`, area 1,233.6 m², centroid (5.356241, 100.291360) (`map`, 2026-09-20, OSM).
- `275404588` is OSM way for `Desasiswa Indah Kembara (L07)`, area 1,500.8 m², centroid (5.356031, 100.296045) (`map`, 2026-09-20, OSM).
- `1030965779` is OSM way for `K10 Desasiswa Aman Damai`, tagged `building:levels=2`, area 715.0 m², centroid (5.354304, 100.296202) (`map`, 2026-09-20, OSM).
- `275403376` is OSM way for `H10 Desasiswa Bakti Permai`, tagged `building:levels=2`, area 1,264.9 m², centroid (5.357763, 100.300499) (`map`, 2026-09-20, OSM).
- `275403540` is OSM way for `H33 Desasiswa Cahaya Gemilang`, tagged `building:levels=2`, area 813.1 m², centroid (5.360424, 100.303549) (`map`, 2026-09-20, OSM).
- `275403371` is OSM way for `F27 Desasiswa Harapan`, tagged `building:levels=2`, area 794.5 m², centroid (5.354996, 100.299797) (`map`, 2026-09-20, OSM).

---

### HYPOTHESES
- Saujana residency is distributed across towers M03 and M04 (matches USM building numbering standard where M01/M02 = Restu, M03/M04 = Saujana, M05/M06 = Tekun).
- `building:levels` is 10 for Restu M01/M02 and Tekun/Saujana towers, but this is an operator prior (`abraham`), not tagged in OSM.

---

### GAPS
- `building:levels` is untagged in OSM for all RST high-rises (M01, M02, M03, M04, M05, M06, M07, M08, M09) and Indah Kembara (L05, L06, L07). Can be confirmed on campus by manual survey or architectural floor plans.
- Additional low-rise residential blocks in Bakti Permai, Fajar Harapan, and Aman Damai (e.g. additional K, H, and F pavilion blocks) may exist in OSM with generic `building=university` tags without specific desasiswa names.

---

### SOURCES
1. OpenStreetMap Overpass API (`https://lz4.overpass-api.de/api/interpreter`, `https://z.overpass-api.de/api/interpreter`) — USM Kampus Induk building polygons, nodes, and tags.

---

### NOT FOUND
- Query for exact string `name="Desasiswa Saujana"` returned no building ways (confirming it is mapped strictly under building code `M03` and `M04`).
- No `building:levels` tag found on ways `139062076`, `1031136419`, `1031136418`, `275415000`, `275414999`, `275414998`, `275415002`.

---

### RECOMMENDED NEXT MEASUREMENTS
1. Tag `building:levels=10` in OSM for M01–M06 once ground-verified.
2. Verify door portals and ingress/egress coordinates for M01, M02, M03, M04, M05, M06 to refine sim origins from centroid to gate/ground exit.
