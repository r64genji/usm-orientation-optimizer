#!/usr/bin/env python3
"""
analyze_idle_time.py
Calculates precise idle, crawling, walking, and transit durations from Location.csv
across both the full recording and the active commute window.
"""

import os
import csv
import io
import datetime
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP_PATH = os.path.join(BASE_DIR, "raw_data/sensor_logger/M08-2026-09-16_22-47-10.zip")

def main():
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        rows = list(csv.DictReader(io.TextIOWrapper(z.open("Location.csv"))))

    # Buckets:
    # 1. Idle / stationary: speed < 0.5 m/s (< 1.8 km/h)
    # 2. Shuffling / crawl: 0.5 <= speed < 1.0 m/s (1.8 - 3.6 km/h)
    # 3. Brisk walking:     1.0 <= speed < 2.5 m/s (3.6 - 9.0 km/h)
    # 4. Vehicle transit:   speed >= 2.5 m/s (> 9.0 km/h)

    commute_buckets = {"idle": 0.0, "crawl": 0.0, "walk": 0.0, "transit": 0.0}
    full_buckets    = {"idle": 0.0, "crawl": 0.0, "walk": 0.0, "transit": 0.0}

    t_dep_restu = datetime.time(7, 34, 23)
    t_arr_dtsp  = datetime.time(8, 37, 42)

    for i in range(1, len(rows)):
        t1 = float(rows[i-1]["time"]) / 1e9
        t2 = float(rows[i]["time"]) / 1e9
        dt = t2 - t1
        if dt > 10.0:  # ignore large disconnected intervals
            continue

        spd = float(rows[i]["speed"])
        category = "idle" if spd < 0.5 else ("crawl" if spd < 1.0 else ("walk" if spd < 2.5 else "transit"))
        full_buckets[category] += dt

        dt1 = datetime.datetime.fromtimestamp(t1)
        if t_dep_restu <= dt1.time() <= t_arr_dtsp:
            commute_buckets[category] += dt

    commute_tot = sum(commute_buckets.values())
    full_tot = sum(full_buckets.values())

    print("=" * 65)
    print(" EMPIRICAL IDLE TIME ANALYSIS (GPS TELEMETRY)")
    print("=" * 65)
    print(f"\n1. Full Recording Window (06:47:10 - 09:18:57 | {full_tot/60:.1f} min):")
    for k, v in full_buckets.items():
        print(f"   - {k.capitalize():<8}: {v/60:6.2f} min ({v/full_tot*100:5.1f}%)")

    print(f"\n2. Active Commute Window (07:34:23 - 08:37:42 | {commute_tot/60:.1f} min):")
    for k, v in commute_buckets.items():
        print(f"   - {k.capitalize():<8}: {v/60:6.2f} min ({v/commute_tot*100:5.1f}%)")

    queue_tot = commute_buckets["idle"] + commute_buckets["crawl"]
    motion_tot = commute_buckets["walk"] + commute_buckets["transit"]
    print("\n3. Commute Efficiency Summary:")
    print(f"   - Total Non-Productive Queue Time: {queue_tot/60:.2f} min ({queue_tot/commute_tot*100:.1f}%)")
    print(f"   - Total Productive Moving Time:    {motion_tot/60:.2f} min ({motion_tot/commute_tot*100:.1f}%)")
    print(f"   - Idle-to-Motion Ratio:            {queue_tot/motion_tot:.2f}x")

if __name__ == "__main__":
    main()
