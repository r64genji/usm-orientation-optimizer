"""Attach raw GPS observation windows to Restu place records.

Reads the committed Sensor Logger export. Does not rewrite telemetry scripts.
Phone position scatter is never treated as area or storage capacity.
"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import median

from usm_sim.constants import TIMEZONE_NAME
from usm_sim.timeutil import unix_ns_to_local

# Spec section 7 windows. Samples kept when 0 < horizontalAccuracy_m <= 20.
PLACE_WINDOWS = {
    "restu_gathering": ("06:50:00", "07:30:00"),
    "rst_bus_wait": ("07:50:30", "07:53:30"),
    "rst_boarding_approach": ("07:55:30", "07:57:30"),
    "dtsp_alighting_area": ("08:01:50", "08:02:55"),
    "dtsp_exterior_gathering": ("08:04:00", "08:18:00"),
}

RAINY_PLACE_WINDOWS = {
    "rst_rain_shelter": ("06:24:00", "08:18:00"),
    "rst_bus_wait": ("08:33:30", "08:34:40"),
    "dtsp_alighting_area": ("08:38:00", "08:39:00"),
}

MAX_HORIZONTAL_ACCURACY_M = 20.0
GPS_CSV_RELATIVE = Path("raw_data/sensor_logger/Location.csv")
FIXTURE_GPS_RELATIVE = Path(
    "tests/fixtures/gps/session_1_2026-09-17_morning_M08_to_DTSP_Location.csv"
)


def default_gps_path(repo_root: Path) -> Path:
    raw_path = repo_root / GPS_CSV_RELATIVE
    if raw_path.is_file():
        return raw_path
    fixture_path = repo_root / FIXTURE_GPS_RELATIVE
    if fixture_path.is_file():
        return fixture_path
    return raw_path

def collect_window_stats(
    csv_path: Path,
    event_date: str = "2026-09-17",
    timezone_name: str = TIMEZONE_NAME,
    windows: dict[str, tuple[str, str]] | None = None,
) -> dict[str, dict]:
    """Return per-place GPS medians and sample counts for the spec windows."""
    if not csv_path.is_file():
        return {}

    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(timezone_name)
    year, month, day = (int(p) for p in event_date.split("-"))

    def at_clock(hms: str) -> datetime:
        hour, minute, second = (int(p) for p in hms.split(":"))
        return datetime(year, month, day, hour, minute, second, tzinfo=tz)

    active_windows = windows or (
        RAINY_PLACE_WINDOWS if event_date == "2026-09-18" else PLACE_WINDOWS
    )
    bounds = {
        place_id: (at_clock(start_hms), at_clock(end_hms))
        for place_id, (start_hms, end_hms) in active_windows.items()
    }
    buckets: dict[str, list[tuple[float, float, float]]] = {k: [] for k in bounds}

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_acc = row.get("horizontalAccuracy") or ""
            if raw_acc == "":
                continue
            accuracy_m = float(raw_acc)
            if not (0.0 < accuracy_m <= MAX_HORIZONTAL_ACCURACY_M):
                continue
            stamp = unix_ns_to_local(int(row["time"]), timezone_name)
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            for place_id, (start, end) in bounds.items():
                if start <= stamp <= end:
                    buckets[place_id].append((lat, lon, accuracy_m))

    stats: dict[str, dict] = {}
    resolved = csv_path.expanduser().resolve()
    try:
        source_path_str = str(resolved.relative_to(Path.cwd().resolve())).replace("\\", "/")
    except ValueError:
        source_path_str = str(resolved).replace("\\", "/")
    for place_id, samples in buckets.items():
        start_hms, end_hms = active_windows[place_id]
        record = {
            "source_path": source_path_str,
            "observation_date": event_date,
            "window_local_start": start_hms,
            "window_local_end": end_hms,
            "method": (
                "median latitude/longitude of raw samples with "
                "0 < horizontalAccuracy_m <= 20"
            ),
            "sample_count": len(samples),
            "horizontal_accuracy_filter_m": MAX_HORIZONTAL_ACCURACY_M,
            "note": (
                "Phone position scatter is not an area or storage-capacity estimate."
            ),
        }
        if samples:
            record["median_latitude_deg"] = float(median([s[0] for s in samples]))
            record["median_longitude_deg"] = float(median([s[1] for s in samples]))
            record["median_horizontal_accuracy_m"] = float(
                median([s[2] for s in samples])
            )
        stats[place_id] = record
    return stats
