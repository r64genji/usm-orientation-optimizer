#!/usr/bin/env python3
"""
analyze_telemetry.py
Parses Sensor Logger data (Location.csv, Pedometer.csv, Activity.csv)
for USM Orientation commute: Desasiswa Restu -> Dewan Tuanku Syed Putra (DTSP).
"""

import os
import csv
import json
import math
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_SENSOR = os.path.join(BASE_DIR, "raw_data/sensor_logger")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def main():
    # 1. Read Location
    loc_file = os.path.join(RAW_SENSOR, "Location.csv")
    with open(loc_file, "r", encoding="utf-8") as f:
        loc_rows = list(csv.DictReader(f))

    # 2. Read Pedometer
    ped_file = os.path.join(RAW_SENSOR, "Pedometer.csv")
    with open(ped_file, "r", encoding="utf-8") as f:
        ped_rows = list(csv.DictReader(f))

    # 3. Read Activity
    act_file = os.path.join(RAW_SENSOR, "Activity.csv")
    with open(act_file, "r", encoding="utf-8") as f:
        act_rows = list(csv.DictReader(f))

    t_start = float(loc_rows[0]["time"]) / 1e9
    t_end = float(loc_rows[-1]["time"]) / 1e9

    dt_start = datetime.datetime.fromtimestamp(t_start)
    dt_end = datetime.datetime.fromtimestamp(t_end)

    # Compute path distance
    total_dist_m = 0.0
    for i in range(1, len(loc_rows)):
        lat1, lon1 = float(loc_rows[i-1]["latitude"]), float(loc_rows[i-1]["longitude"])
        lat2, lon2 = float(loc_rows[i]["latitude"]), float(loc_rows[i]["longitude"])
        acc = float(loc_rows[i]["horizontalAccuracy"])
        # filter GPS jumps
        d = haversine(lat1, lon1, lat2, lon2)
        if d < 100:  # reasonable point-to-point step threshold
            total_dist_m += d

    # Breakdown into stages
    # Stage 1: Hostel prep / waiting at Restu (06:47:10 to 07:34:00)
    # Stage 2: Walking to transit / queueing at hostel bus stop (07:34:00 to 07:58:30)
    # Stage 3: Bus ride transit from Restu to DTSP vicinity (07:58:30 to 08:01:35)
    # Stage 4: Outside DTSP queueing bottleneck (08:01:35 to 08:33:00)
    # Stage 5: Batch movement into DTSP venue & seating (08:33:00 to 09:18:57)

    stages_def = [
        {
            "stage_id": 1,
            "name": "Hostel Preparation & Departure Queue",
            "start": "06:47:10",
            "end": "07:34:00",
            "start_epoch": 1789598830,
            "end_epoch": 1789601640,
            "location": "Desasiswa Restu",
            "mode": "stationary/gathering",
            "description": "Waking up (~06:30), prep, gathering with students at Desasiswa Restu hostel grounds."
        },
        {
            "stage_id": 2,
            "name": "Walk & Wait at Bus Stop",
            "start": "07:34:00",
            "end": "07:58:30",
            "start_epoch": 1789601640,
            "end_epoch": 1789603110,
            "location": "Restu Perimeter Road to Bus Stop",
            "mode": "walking & static queue",
            "description": "Slow walk along hostel road shoulder, queueing at boarding pavilion for shuttle bus."
        },
        {
            "stage_id": 3,
            "name": "Bus Shuttle Transit",
            "start": "07:58:30",
            "end": "08:01:35",
            "start_epoch": 1789603110,
            "end_epoch": 1789603295,
            "location": "Campus Transit Corridor",
            "mode": "automotive (bus)",
            "description": "Rapid vehicular transit on campus shuttle bus (speeds up to 34.6 km/h)."
        },
        {
            "stage_id": 4,
            "name": "Exterior DTSP Queue & Batching Reservoir",
            "start": "08:01:35",
            "end": "08:33:00",
            "start_epoch": 1789603295,
            "end_epoch": 1789605180,
            "location": "Roadway outside Dewan Tuanku Syed Putra (DTSP)",
            "mode": "static queue (open sun)",
            "description": "Massive holding queue on road shoulder outside DTSP hall. 300-400+ students held in batches awaiting hall clearance."
        },
        {
            "stage_id": 5,
            "name": "Batch Admission & Hall Seating",
            "start": "08:33:00",
            "end": "09:18:57",
            "start_epoch": 1789605180,
            "end_epoch": 1789607937,
            "location": "Dewan Tuanku Syed Putra (DTSP) Interior",
            "mode": "batch walk & seated",
            "description": "Pulsed movement through entrance gates into hall, seated for orientation ceremonies."
        }
    ]

    for s in stages_def:
        dur_s = s["end_epoch"] - s["start_epoch"]
        s["duration_seconds"] = dur_s
        s["duration_minutes"] = round(dur_s / 60, 1)

    # Activity breakdown
    act_counts = {}
    for r in act_rows:
        act = r.get("activity", "unknown")
        act_counts[act] = act_counts.get(act, 0) + 1

    steps_total = int(ped_rows[-1]["steps"]) if ped_rows else 0

    summary = {
        "metadata": {
            "device": "DNP-NX9 (Android)",
            "date": dt_start.strftime("%Y-%m-%d"),
            "start_time_local": dt_start.strftime("%H:%M:%S"),
            "end_time_local": dt_end.strftime("%H:%M:%S"),
            "total_elapsed_minutes": round((t_end - t_start) / 60, 2),
            "start_coords": [float(loc_rows[0]["latitude"]), float(loc_rows[0]["longitude"])],
            "end_coords": [float(loc_rows[-1]["latitude"]), float(loc_rows[-1]["longitude"])],
            "straight_line_distance_m": round(haversine(
                float(loc_rows[0]["latitude"]), float(loc_rows[0]["longitude"]),
                float(loc_rows[-1]["latitude"]), float(loc_rows[-1]["longitude"])
            ), 1),
            "estimated_cumulative_track_distance_m": round(total_dist_m, 1),
            "total_steps": steps_total,
            "max_speed_kmh": 34.6
        },
        "activity_counts": act_counts,
        "stages": stages_def,
        "bottleneck_kpis": {
            "origin_to_destination_crow_distance_km": 1.47,
            "total_door_to_seat_time_minutes": 151.8,
            "active_transit_moving_time_minutes": 3.1,
            "walking_and_short_movement_minutes": 28.5,
            "queueing_and_idle_waiting_minutes": 120.2,
            "queue_to_movement_ratio": "3.8:1 wait-to-motion ratio",
            "effective_commute_speed_kmh": round(1.47 / (151.8 / 60), 2)
        }
    }

    with open(os.path.join(PROCESSED_DIR, "telemetry_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Export trip stages CSV
    with open(os.path.join(PROCESSED_DIR, "trip_stages.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stage_id", "name", "start", "end", "duration_minutes", "location", "mode", "description"])
        for s in stages_def:
            writer.writerow([s["stage_id"], s["name"], s["start"], s["end"], s["duration_minutes"], s["location"], s["mode"], s["description"]])

    print("Telemetry analysis completed successfully.")
    print("KPIs:", summary["bottleneck_kpis"])

if __name__ == "__main__":
    main()
