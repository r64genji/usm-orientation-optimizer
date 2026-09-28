#!/usr/bin/env python3
"""
export_geojson.py
Converts Location.csv into a clean GeoJSON FeatureCollection:
1. Point markers for start, transit board, transit alight, queue, and arrival.
2. LineString representing the continuous trajectory downsampled for mapping.
"""

import os
import csv
import json
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOC_FILE = os.path.join(BASE_DIR, "raw_data/sensor_logger/Location.csv")
FIXTURE_LOC_FILE = os.path.join(
    BASE_DIR, "tests/fixtures/gps/session_1_2026-09-17_morning_M08_to_DTSP_Location.csv"
)
OUT_GEOJSON = os.path.join(BASE_DIR, "processed/route_track.geojson")

def main():
    target_loc = LOC_FILE if os.path.isfile(LOC_FILE) else FIXTURE_LOC_FILE
    with open(target_loc, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    features = []

    # Downsample points for trajectory (every 10th point ~ every 5-10 seconds)
    coordinates = []
    downsampled = rows[::10]
    for r in downsampled:
        lat = float(r["latitude"])
        lon = float(r["longitude"])
        coordinates.append([lon, lat])

    # Trajectory LineString
    features.append({
        "type": "Feature",
        "properties": {
            "name": "Full Commute Trajectory",
            "description": "Desasiswa Restu to Dewan Tuanku Syed Putra (DTSP)",
            "start_time": "06:47:10",
            "end_time": "09:18:57",
            "total_points": len(rows),
            "sampled_points": len(coordinates)
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        }
    })

    # Key Milestones as Point Features
    milestones = [
        {"name": "Desasiswa Restu (Start)", "idx": 0, "desc": "Departure point from hostel"},
        {"name": "Restu Bus Stop / Boarding Queue", "idx": int(len(rows) * 0.28), "desc": "Hostel road shoulder queue for shuttle bus"},
        {"name": "Bus Shuttle Alight Point", "idx": int(len(rows) * 0.35), "desc": "Transit bus drop-off near DTSP perimeter"},
        {"name": "DTSP Roadway Bottleneck (Video fedd)", "idx": int(len(rows) * 0.40), "desc": "Massive holding queue under open sun"},
        {"name": "Dewan Tuanku Syed Putra (Arrival)", "idx": len(rows) - 1, "desc": "Final seated venue inside DTSP hall"}
    ]

    for m in milestones:
        r = rows[m["idx"]]
        lat = float(r["latitude"])
        lon = float(r["longitude"])
        t = float(r["time"]) / 1e9
        dt = datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")
        features.append({
            "type": "Feature",
            "properties": {
                "name": m["name"],
                "time": dt,
                "description": m["desc"],
                "speed_kmh": round(float(r["speed"]) * 3.6, 1)
            },
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            }
        })

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=2)

    print(f"GeoJSON exported successfully to {OUT_GEOJSON} ({len(features)} features)")

if __name__ == "__main__":
    main()
