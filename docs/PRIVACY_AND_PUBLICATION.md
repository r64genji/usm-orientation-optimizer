# Privacy, Data Protection, and Public Release Policy

**Repository:** `usm-orientation-optimizer`  
**Author:** Abraham Tan  
**Contact / Repository:** `https://github.com/r64genji/usm-orientation-optimizer`  
**Governing Standard:** `MASTER.md` (§10 Data Contract & Privacy Rules)

---

## 1. Overview & Principles

The Universiti Sains Malaysia (USM) Orientation Optimizer models crowd movement and transit logistics during Minggu Siswa Lestari (MSL). Research data was collected through GPS telemetry, field observations, and short media clips of student cohorts on campus.

To ensure ethical stewardship of research data and protect the privacy of students, staff, and volunteers, this repository enforces strict data classification and publication rules.

---

## 2. Data Classification

| Classification Level | Contents | Location | Publication Status |
|---|---|---|---|
| **Tier 1: Public Models & Derived Data** | Core simulation engine (`usm_sim`), GIS network layers, processed trajectories, aggregated delay metrics, web dashboard, and proposal editor. | `usm_sim/`, `operator_dashboard/`, `proposal_site/`, `processed/` | **Fully Public (MIT License)** |
| **Tier 2: Cleaned Field Telemetry** | Cleaned GPS coordinates and timestamps from volunteer traces, anonymized pedometer cadences, and structured video analysis summaries. | `processed/`, `research/reports/`, `tests/fixtures/gps/` | **Public Research Data** |
| **Tier 3: Raw Field Evidence & Sensor Telemetry** | Entire raw data tree (`raw_data/`), including raw sensor logs (`Location.csv`, `Pedometer.csv`, `Activity.csv`), hardware device UUIDs (`Metadata.csv`), sensor archives (`.zip`), and unblurred observational video recordings. | `raw_data/` | **Restricted / Excluded from Public Exports** |

---

## 3. Privacy Invariants

1. **No Student PII:** No student names, matriculation numbers, national identity numbers (MyKad/IC), or contact information are collected or stored in this repository.
2. **Face Blurring & Unblurred Media Exclusion:** In accordance with `MASTER.md` ("*Blur faces before public remotes*"), unblurred video recordings containing visible student silhouettes and three-quarter profiles are restricted to internal operational archives. They are excluded from public source archives via `.gitattributes` (`export-ignore`) and sanitized in public exports.
3. **Structured Analytical Provenance:** Video analysis metrics (boarding throughput, packing density, queue formation) are completely preserved in structured machine-readable form in `processed/video_analysis.json` and `research/reports/06_data_schema_measurement.md`.
4. **Device UUID Isolation:** Hardware device UUIDs from Sensor Logger are restricted to internal calibration records and omitted from public distribution artifacts.
5. **Immutability of Local Evidence:** Internal operational raw data (`raw_data/`) is never modified or deleted, maintaining full research reproducibility.

---

## 4. Export & Sanitization Procedure

To generate a sanitized, public-publishable distribution archive or clean-history public branch:

1. **Automated Verification:**
   Run the privacy compliance and packaging script:
   ```bash
   python scripts/prepare_public_export.py --verify-only
   ```

2. **Clean-History Public Branch Creation:**
   To prevent tracked historical blobs (unblurred raw MP4 videos, device UUID metadata, and sensor ZIP archives) from ever reaching public remotes, generate an orphan `public-release` branch from the export tree:
   ```bash
   python scripts/prepare_public_export.py --create-public-branch
   ```
   This creates a pristine, single-commit orphan branch containing only sanitized code, models, and public research assets. The original local Git history and local raw research evidence remain completely preserved in the internal branches (`master`, feature branches).

3. **Git Archive Export:**
   Git attributes also automatically enforce export exclusion for tar/zip archives:
   ```bash
   git archive --format=tar.gz --prefix=usm-orientation-optimizer/ HEAD > usm-orientation-optimizer-public.tar.gz
   ```

4. **Verifying Export Artifacts:**
   The generated archive and `public-release` branch contain zero raw data files, zero MP4 video files, zero hardware ZIP archives, zero device metadata files, and zero internal agent artifacts, while retaining CI workflows (`.github/`), simulation models, scenarios, processed GIS traces, dashboard bundles, and test suites.
