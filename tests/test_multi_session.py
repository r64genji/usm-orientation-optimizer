"""Tests for multi-session telemetry cleaning, filtering, and fusion."""

import os
import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
PROCESSED_DIR = REPO_ROOT / "processed"

def test_clean_and_fuse_telemetry_script():
    """Verify clean_and_fuse_telemetry.py executes cleanly and produces all expected artifacts."""
    if not (REPO_ROOT / "raw_data/sensor_logger/sessions").is_dir():
        pytest.skip("raw_data/sensor_logger/sessions is excluded from public release")
    script_path = SCRIPTS_DIR / "clean_and_fuse_telemetry.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True
    )
    assert proc.returncode == 0
    assert "All 3 sessions processed and saved successfully" in proc.stdout

    # Check multi_session_comparison.json
    comp_file = PROCESSED_DIR / "multi_session_comparison.json"
    assert comp_file.exists()
    with open(comp_file, "r", encoding="utf-8") as f:
        comp_data = json.load(f)
    assert len(comp_data) == 3

    # Check combined geojson
    comb_geo = PROCESSED_DIR / "all_sessions_combined.geojson"
    assert comb_geo.exists()
    with open(comb_geo, "r", encoding="utf-8") as f:
        geo = json.load(f)
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) >= 3

def test_noise_filtering_and_jitter_reduction():
    """Verify that GPS jitter noise reduction is substantial (>40%) across long sessions."""
    comp_file = PROCESSED_DIR / "multi_session_comparison.json"
    with open(comp_file, "r", encoding="utf-8") as f:
        comp_data = {s["session_id"]: s for s in json.load(f)}

    s1 = comp_data["session_1_2026-09-17_morning_M08_to_DTSP"]
    s3 = comp_data["session_3_2026-09-18_morning_M01_Rainy_to_DTSP"]

    # Raw distances should be inflated over 4km due to GPS drift
    assert s1["metadata"]["raw_cumulative_distance_m"] > 4000.0
    assert s3["metadata"]["raw_cumulative_distance_m"] > 4500.0

    # Filtered distance should reduce jitter significantly
    assert s1["metadata"]["jitter_noise_reduction_pct"] > 40.0
    assert s3["metadata"]["jitter_noise_reduction_pct"] > 40.0

    # Straight-line distance should match USM campus geography (~1.47km)
    assert s1["metadata"]["straight_line_distance_m"] == pytest.approx(1470, abs=50)

def test_rainy_day_cafeteria_detection():
    """Verify that Session 3 correctly classifies the prolonged cafeteria weather delay as stationary."""
    s3_dir = PROCESSED_DIR / "session_3_2026-09-18_morning_M01_Rainy_to_DTSP"
    with open(s3_dir / "telemetry_summary.json", "r", encoding="utf-8") as f:
        s3 = json.load(f)

    # Over 100 minutes spent stationary
    assert s3["state_durations_minutes"]["STATIONARY_WAITING"] > 100.0
    # Overall idle ratio exceeds 5x
    assert s3["kpis"]["percent_time_stationary"] > 80.0

def test_bus_transit_detection():
    """Verify bus transit physics are captured in both morning sessions."""
    comp_file = PROCESSED_DIR / "multi_session_comparison.json"
    with open(comp_file, "r", encoding="utf-8") as f:
        comp_data = {s["session_id"]: s for s in json.load(f)}

    s1 = comp_data["session_1_2026-09-17_morning_M08_to_DTSP"]
    s3 = comp_data["session_3_2026-09-18_morning_M01_Rainy_to_DTSP"]

    # Bus duration is ~2.5 - 3.5 minutes
    assert s1["state_durations_minutes"]["VEHICLE_TRANSIT"] == pytest.approx(3.0, abs=1.0)
    assert s3["state_durations_minutes"]["VEHICLE_TRANSIT"] == pytest.approx(3.0, abs=1.0)

    # Max filtered vehicular speed exceeds 30 km/h
    assert s1["metadata"]["max_filtered_speed_kmh"] > 30.0
    assert s3["metadata"]["max_filtered_speed_kmh"] > 30.0
