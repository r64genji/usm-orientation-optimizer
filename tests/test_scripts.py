"""Tests for USM orientation transit analysis and simulation scripts."""

import json
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.analyze_idle_time as analyze_idle_time
import scripts.analyze_telemetry as analyze_telemetry
import scripts.export_geojson as export_geojson
import scripts.simulate_batching as simulate_batching

SCRIPTS_DIR = REPO_ROOT / "scripts"
PROCESSED_DIR = REPO_ROOT / "processed"
OLD_HARDCODED_ROOT = Path("/home" + "/abe/projects/usm-orientation-optimizer")


def test_script_imports():
    """Verify all script modules import and expose main entry points."""
    assert callable(analyze_telemetry.main)
    assert callable(analyze_idle_time.main)
    assert callable(export_geojson.main)
    assert callable(simulate_batching.run_simulation)


def test_scripts_resolve_repo_root_from_file():
    """BASE_DIR must come from __file__, not the old absolute project path."""
    expected = REPO_ROOT.resolve()
    for mod in (analyze_telemetry, analyze_idle_time, export_geojson):
        base = Path(mod.BASE_DIR).resolve()
        assert base == expected
        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "os.path.dirname(os.path.dirname(os.path.abspath(__file__)))" in source
        assert str(OLD_HARDCODED_ROOT) not in source
    if expected != OLD_HARDCODED_ROOT.resolve():
        for mod in (analyze_telemetry, analyze_idle_time, export_geojson):
            assert Path(mod.BASE_DIR).resolve() != OLD_HARDCODED_ROOT.resolve()


def test_analyze_telemetry_script():
    """Verify analyze_telemetry outputs expected telemetry summary metrics."""
    if not (REPO_ROOT / "raw_data/sensor_logger").is_dir():
        pytest.skip("raw_data/sensor_logger is excluded from public release")
    script_path = SCRIPTS_DIR / "analyze_telemetry.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    assert "Telemetry analysis completed successfully" in proc.stdout

    summary_file = PROCESSED_DIR / "telemetry_summary.json"
    assert summary_file.exists()
    with open(summary_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    assert meta["date"] == "2026-09-17"
    assert meta["start_time_local"].startswith("06:47")
    assert meta["end_time_local"].startswith("09:18")
    assert meta["total_elapsed_minutes"] == pytest.approx(151.8, abs=1.0)
    assert meta["straight_line_distance_m"] / 1000 == pytest.approx(1.47, abs=0.05)
    assert meta["max_speed_kmh"] == pytest.approx(34.6, abs=0.5)

    stages = {s["stage_id"]: s for s in data["stages"]}
    assert stages[2]["duration_minutes"] == pytest.approx(24.5, abs=1.0)
    assert stages[3]["duration_minutes"] == pytest.approx(3.1, abs=0.2)
    assert stages[4]["duration_minutes"] == pytest.approx(31.4, abs=1.0)

    kpis = data["bottleneck_kpis"]
    assert kpis["origin_to_destination_crow_distance_km"] == pytest.approx(1.47, abs=0.05)
    assert kpis["active_transit_moving_time_minutes"] == pytest.approx(3.1, abs=0.2)


def test_analyze_idle_time_script():
    """Verify analyze_idle_time prints commute window and queue ratio."""
    if not (REPO_ROOT / "raw_data/sensor_logger").is_dir():
        pytest.skip("raw_data/sensor_logger is excluded from public release")
    script_path = SCRIPTS_DIR / "analyze_idle_time.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0

    stdout = proc.stdout
    assert "Active Commute Window" in stdout
    assert "07:34:23 - 08:37:42" in stdout
    assert "63.3 min" in stdout
    assert "Idle-to-Motion Ratio:" in stdout
    assert "9.27x" in stdout
    assert "Total Non-Productive Queue Time:" in stdout
    ratio = float(stdout.split("Idle-to-Motion Ratio:")[1].split("x")[0].strip())
    assert ratio > 1.0


def test_simulate_batching_script():
    """Verify simulate_batching exits 0 and discusses walking tradeoff."""
    script_path = SCRIPTS_DIR / "simulate_batching.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0

    stdout = proc.stdout
    assert "Direct Walking Distance: 1.47 km" in stdout
    assert "Unconstrained Walk Time: 18.4 minutes" in stdout
    assert "slower than walking" in stdout
    assert "walk 1.47km in 18-20 mins" in stdout


def test_export_geojson_script():
    """Verify export_geojson generates a valid FeatureCollection with LineString."""
    script_path = SCRIPTS_DIR / "export_geojson.py"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0

    geojson_file = PROCESSED_DIR / "route_track.geojson"
    assert geojson_file.exists()
    with open(geojson_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("type") == "FeatureCollection"
    features = data.get("features", [])
    assert len(features) > 0

    linestrings = [f for f in features if f.get("geometry", {}).get("type") == "LineString"]
    assert len(linestrings) >= 1

    coords = linestrings[0]["geometry"]["coordinates"]
    assert len(coords) > 1
    for pt in coords:
        assert len(pt) == 2
        assert isinstance(pt[0], (int, float))
        assert isinstance(pt[1], (int, float))
