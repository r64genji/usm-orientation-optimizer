#!/usr/bin/env python3
"""
clean_and_fuse_telemetry.py
Multi-sensor data cleaning, noise filtering, and fusion pipeline for USM Orientation telemetry.
Cross-references GPS (lat/lon, speed, accuracy, bearing), Pedometer (cadence, step accumulation),
and Android Activity states to reliably differentiate between:
- STATIONARY_WAITING (standing around, waiting in cafeteria, seated in hall)
- WALKING (active pedestrian movement)
- VEHICLE_TRANSIT (bus transit)
- QUEUE_SHUFFLE (slow shuffling in queue)
"""

import os
import csv
import json
import math
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS_DIR = os.path.join(BASE_DIR, "raw_data/sensor_logger/sessions")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def clean_session(session_name, raw_dir, output_dir, session_meta_info):
    os.makedirs(output_dir, exist_ok=True)
    
    loc_file = os.path.join(raw_dir, "Location.csv")
    ped_file = os.path.join(raw_dir, "Pedometer.csv")
    meta_file = os.path.join(raw_dir, "Metadata.csv")
    
    with open(loc_file, "r", encoding="utf-8") as f:
        loc_rows = list(csv.DictReader(f))
    with open(ped_file, "r", encoding="utf-8") as f:
        ped_rows = list(csv.DictReader(f))
    with open(meta_file, "r", encoding="utf-8") as f:
        meta_rows = list(csv.DictReader(f))
        
    epoch_ms = float(meta_rows[0].get("recording epoch time", 0))
    tz_offset_hours = 8  # Asia/Kuala_Lumpur (UTC+8)
    
    # Parse Pedometer timeline for step-wise constant / forward-fill lookup
    ped_data = []
    for r in ped_rows:
        try:
            ped_data.append((float(r["seconds_elapsed"]), int(float(r["steps"]))))
        except Exception:
            continue
    ped_data.sort(key=lambda x: x[0])
    
    def get_steps_at(t):
        if not ped_data:
            return 0
        if t < ped_data[0][0]:
            return ped_data[0][1]
        low, high, ans = 0, len(ped_data) - 1, 0
        while low <= high:
            mid = (low + high) // 2
            if ped_data[mid][0] <= t:
                ans = mid
                low = mid + 1
            else:
                high = mid - 1
        return ped_data[ans][1]
    
    # Parse Location rows
    parsed_loc = []
    for r in loc_rows:
        try:
            t = float(r["seconds_elapsed"])
            lat = float(r["latitude"])
            lon = float(r["longitude"])
            spd = float(r.get("speed", 0.0) or 0.0)
            hacc = float(r.get("horizontalAccuracy", 10.0) or 10.0)
            bearing = float(r.get("bearing", 0.0) or 0.0)
            parsed_loc.append({
                "seconds_elapsed": t,
                "latitude": lat,
                "longitude": lon,
                "speed": spd,
                "horizontalAccuracy": hacc,
                "bearing": bearing,
                "steps": get_steps_at(t)
            })
        except Exception:
            continue
            
    n = len(parsed_loc)
    if n == 0:
        return None
        
    # Multi-window spatial metrics & sensor cross-referencing
    for i in range(n):
        t_now = parsed_loc[i]["seconds_elapsed"]
        
        # 15s window (local translational speed)
        idx_15 = i
        while idx_15 > 0 and (t_now - parsed_loc[idx_15]["seconds_elapsed"]) < 15.0:
            idx_15 -= 1
        d_15 = haversine(parsed_loc[idx_15]["latitude"], parsed_loc[idx_15]["longitude"],
                         parsed_loc[i]["latitude"], parsed_loc[i]["longitude"])
        parsed_loc[i]["disp_15s"] = d_15
        
        # 60s window (displacement & gyration radius)
        idx_60 = i
        while idx_60 > 0 and (t_now - parsed_loc[idx_60]["seconds_elapsed"]) < 60.0:
            idx_60 -= 1
        d_60 = haversine(parsed_loc[idx_60]["latitude"], parsed_loc[idx_60]["longitude"],
                         parsed_loc[i]["latitude"], parsed_loc[i]["longitude"])
        parsed_loc[i]["disp_60s"] = d_60
        
        pts = parsed_loc[idx_60:i+1]
        c_lat = sum(p["latitude"] for p in pts) / len(pts)
        c_lon = sum(p["longitude"] for p in pts) / len(pts)
        gyr = math.sqrt(sum(haversine(c_lat, c_lon, p["latitude"], p["longitude"])**2 for p in pts) / len(pts))
        parsed_loc[i]["gyr_60s"] = gyr
        parsed_loc[i]["step_diff_60s"] = parsed_loc[i]["steps"] - parsed_loc[idx_60]["steps"]

    # State Inference Engine
    for i in range(n):
        p = parsed_loc[i]
        spd = p["speed"]
        hacc = p["horizontalAccuracy"]
        d15 = p["disp_15s"]
        d60 = p["disp_60s"]
        gyr = p["gyr_60s"]
        s_diff = p["step_diff_60s"]
        
        # 1. Vehicle Transit
        if (spd > 3.0 and d15 > 25.0) or (spd > 4.5 and d15 > 15.0):
            st = "VEHICLE_TRANSIT"
            conf = 0.95
        # 2. Active Walking
        elif s_diff >= 30 and spd > 0.4:
            st = "WALKING"
            conf = 0.95
        elif d60 > 35.0 and gyr > 12.0 and spd > 0.5 and hacc < 30.0:
            st = "WALKING"
            conf = 0.90
        elif d15 > 12.0 and spd > 0.6 and hacc < 25.0:
            st = "WALKING"
            conf = 0.85
        # 3. Queue Shuffle
        elif (s_diff >= 8 and s_diff < 30) or (d60 > 15.0 and gyr > 6.0 and spd > 0.25 and hacc < 20.0):
            st = "QUEUE_SHUFFLE"
            conf = 0.80
        # 4. Stationary Waiting
        else:
            st = "STATIONARY_WAITING"
            conf = 0.95 if gyr < 10.0 else 0.80
            
        p["inferred_state"] = st
        p["state_confidence"] = conf

    # Unconditionally Stable Adaptive Kalman Filter with Stationary Cluster Snapping
    m_to_deg_lat = 1.0 / 111000.0
    m_to_deg_lon = 1.0 / (111000.0 * math.cos(math.radians(parsed_loc[0]["latitude"])))

    f_lats = [parsed_loc[0]["latitude"]]
    f_lons = [parsed_loc[0]["longitude"]]
    P_lat = (10.0 * m_to_deg_lat) ** 2
    P_lon = (10.0 * m_to_deg_lon) ** 2
    
    c_lat_pts = [parsed_loc[0]["latitude"]]
    c_lon_pts = [parsed_loc[0]["longitude"]]

    for i in range(1, n):
        dt = max(0.01, parsed_loc[i]["seconds_elapsed"] - parsed_loc[i-1]["seconds_elapsed"])
        st = parsed_loc[i]["inferred_state"]
        hacc = parsed_loc[i]["horizontalAccuracy"]
        
        if st == "STATIONARY_WAITING":
            q_lat = (0.01 * m_to_deg_lat) ** 2
            q_lon = (0.01 * m_to_deg_lon) ** 2
            r_lat = (1.5 * m_to_deg_lat) ** 2
            r_lon = (1.5 * m_to_deg_lon) ** 2
            c_lat_pts.append(parsed_loc[i]["latitude"])
            c_lon_pts.append(parsed_loc[i]["longitude"])
            if len(c_lat_pts) > 60:
                c_lat_pts.pop(0)
                c_lon_pts.pop(0)
            z_lat = sum(c_lat_pts) / len(c_lat_pts)
            z_lon = sum(c_lon_pts) / len(c_lon_pts)
        elif st == "VEHICLE_TRANSIT":
            q_lat = (6.0 * m_to_deg_lat) ** 2
            q_lon = (6.0 * m_to_deg_lon) ** 2
            r_lat = (max(3.0, hacc) * m_to_deg_lat) ** 2
            r_lon = (max(3.0, hacc) * m_to_deg_lon) ** 2
            c_lat_pts = [parsed_loc[i]["latitude"]]
            c_lon_pts = [parsed_loc[i]["longitude"]]
            z_lat = parsed_loc[i]["latitude"]
            z_lon = parsed_loc[i]["longitude"]
        else:
            q_lat = (1.2 * m_to_deg_lat) ** 2
            q_lon = (1.2 * m_to_deg_lon) ** 2
            r_lat = (max(3.0, hacc) * m_to_deg_lat) ** 2
            r_lon = (max(3.0, hacc) * m_to_deg_lon) ** 2
            c_lat_pts = [parsed_loc[i]["latitude"]]
            c_lon_pts = [parsed_loc[i]["longitude"]]
            z_lat = parsed_loc[i]["latitude"]
            z_lon = parsed_loc[i]["longitude"]

        # Lat update
        p_pred_lat = P_lat + q_lat * dt
        k_lat = p_pred_lat / (p_pred_lat + r_lat)
        new_lat = f_lats[-1] + k_lat * (z_lat - f_lats[-1])
        P_lat = (1.0 - k_lat) * p_pred_lat
        f_lats.append(new_lat)

        # Lon update
        p_pred_lon = P_lon + q_lon * dt
        k_lon = p_pred_lon / (p_pred_lon + r_lon)
        new_lon = f_lons[-1] + k_lon * (z_lon - f_lons[-1])
        P_lon = (1.0 - k_lon) * p_pred_lon
        f_lons.append(new_lon)

    # Build Cleaned Telemetry Records
    cum_raw_dist = 0.0
    cum_filt_dist = 0.0
    cleaned_rows = []
    
    start_dt = datetime.datetime.fromtimestamp(epoch_ms / 1000.0, datetime.timezone(datetime.timedelta(hours=tz_offset_hours)))
    
    for i in range(n):
        p = parsed_loc[i]
        f_lat = f_lats[i]
        f_lon = f_lons[i]
        
        f_spd = 0.0
        if i > 0:
            prev_raw = parsed_loc[i-1]
            dt_step = max(0.001, p["seconds_elapsed"] - prev_raw["seconds_elapsed"])
            raw_d = haversine(prev_raw["latitude"], prev_raw["longitude"], p["latitude"], p["longitude"])
            filt_d = haversine(f_lats[i-1], f_lons[i-1], f_lat, f_lon)
            cum_raw_dist += raw_d
            cum_filt_dist += filt_d
            f_spd = filt_d / dt_step
            if p["inferred_state"] == "STATIONARY_WAITING":
                f_spd = 0.0
            
        cur_dt = start_dt + datetime.timedelta(seconds=p["seconds_elapsed"])
        
        cleaned_rows.append({
            "timestamp_iso": cur_dt.isoformat(),
            "time_local": cur_dt.strftime("%H:%M:%S"),
            "seconds_elapsed": round(p["seconds_elapsed"], 3),
            "latitude_raw": round(p["latitude"], 7),
            "longitude_raw": round(p["longitude"], 7),
            "latitude_filtered": round(f_lat, 7),
            "longitude_filtered": round(f_lon, 7),
            "horizontal_accuracy_m": round(p["horizontalAccuracy"], 2),
            "speed_gps_mps": round(p["speed"], 2),
            "speed_filtered_mps": round(f_spd, 2),
            "speed_filtered_kmh": round(f_spd * 3.6, 2),
            "cumulative_raw_distance_m": round(cum_raw_dist, 1),
            "cumulative_filtered_distance_m": round(cum_filt_dist, 1),
            "cumulative_steps": p["steps"],
            "inferred_state": p["inferred_state"],
            "state_confidence": p["state_confidence"]
        })

    # Write cleaned CSV
    out_csv = os.path.join(output_dir, "cleaned_telemetry.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cleaned_rows[0].keys()))
        writer.writeheader()
        writer.writerows(cleaned_rows)

    # State Durations & KPIs
    durations_s = {"STATIONARY_WAITING": 0.0, "QUEUE_SHUFFLE": 0.0, "WALKING": 0.0, "VEHICLE_TRANSIT": 0.0}
    for i in range(1, n):
        dt = cleaned_rows[i]["seconds_elapsed"] - cleaned_rows[i-1]["seconds_elapsed"]
        durations_s[cleaned_rows[i]["inferred_state"]] += dt
        
    durations_m = {k: round(v / 60.0, 2) for k, v in durations_s.items()}
    total_min = round(cleaned_rows[-1]["seconds_elapsed"] / 60.0, 2)
    crow_dist_m = round(haversine(cleaned_rows[0]["latitude_filtered"], cleaned_rows[0]["longitude_filtered"],
                                  cleaned_rows[-1]["latitude_filtered"], cleaned_rows[-1]["longitude_filtered"]), 1)
    
    # Generate stages (grouping contiguous blocks of state >= 15 seconds)
    raw_stages = []
    curr_stage = None
    stage_idx = 1
    
    for row in cleaned_rows:
        st = row["inferred_state"]
        if curr_stage is None or curr_stage["mode"] != st:
            if curr_stage is not None:
                curr_stage["duration_minutes"] = round((curr_stage["end_seconds"] - curr_stage["start_seconds"]) / 60.0, 2)
                raw_stages.append(curr_stage)
                stage_idx += 1
            curr_stage = {
                "stage_id": stage_idx,
                "mode": st,
                "start_time": row["time_local"],
                "end_time": row["time_local"],
                "start_seconds": row["seconds_elapsed"],
                "end_seconds": row["seconds_elapsed"],
                "start_lat": row["latitude_filtered"],
                "start_lon": row["longitude_filtered"],
                "end_lat": row["latitude_filtered"],
                "end_lon": row["longitude_filtered"],
                "start_steps": row["cumulative_steps"],
                "end_steps": row["cumulative_steps"]
            }
        else:
            curr_stage["end_time"] = row["time_local"]
            curr_stage["end_seconds"] = row["seconds_elapsed"]
            curr_stage["end_lat"] = row["latitude_filtered"]
            curr_stage["end_lon"] = row["longitude_filtered"]
            curr_stage["end_steps"] = row["cumulative_steps"]
            
    if curr_stage is not None:
        curr_stage["duration_minutes"] = round((curr_stage["end_seconds"] - curr_stage["start_seconds"]) / 60.0, 2)
        raw_stages.append(curr_stage)

    # Filter out micro-jitter transitions (< 15 seconds) unless vehicle
    consolidated_stages = []
    for s in raw_stages:
        if s["duration_minutes"] * 60.0 >= 15.0 or s["mode"] == "VEHICLE_TRANSIT" or not consolidated_stages:
            s["stage_id"] = len(consolidated_stages) + 1
            consolidated_stages.append(s)
        else:
            # merge into previous
            prev = consolidated_stages[-1]
            prev["end_time"] = s["end_time"]
            prev["end_seconds"] = s["end_seconds"]
            prev["end_lat"] = s["end_lat"]
            prev["end_lon"] = s["end_lon"]
            prev["end_steps"] = s["end_steps"]
            prev["duration_minutes"] = round((prev["end_seconds"] - prev["start_seconds"]) / 60.0, 2)

    # Merge consecutive identical stages
    merged_stages = []
    for s in consolidated_stages:
        if not merged_stages or merged_stages[-1]["mode"] != s["mode"]:
            merged_stages.append(s.copy())
        else:
            prev = merged_stages[-1]
            prev["end_time"] = s["end_time"]
            prev["end_seconds"] = s["end_seconds"]
            prev["end_lat"] = s["end_lat"]
            prev["end_lon"] = s["end_lon"]
            prev["end_steps"] = s["end_steps"]
            prev["duration_minutes"] = round((prev["end_seconds"] - prev["start_seconds"]) / 60.0, 2)
            
    for idx, s in enumerate(merged_stages, 1):
        s["stage_id"] = idx

    # Write Trip Stages CSV
    out_stages_csv = os.path.join(output_dir, "trip_stages.csv")
    with open(out_stages_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["stage_id", "mode", "start_time", "end_time", "duration_minutes", "step_gain", "start_coords", "end_coords"])
        for s in merged_stages:
            writer.writerow([
                s["stage_id"], s["mode"], s["start_time"], s["end_time"], s["duration_minutes"],
                s["end_steps"] - s["start_steps"],
                f"{s['start_lat']},{s['start_lon']}", f"{s['end_lat']},{s['end_lon']}"
            ])

    # GeoJSON Export
    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[r["longitude_filtered"], r["latitude_filtered"]] for r in cleaned_rows]
            },
            "properties": {
                "session": session_name,
                "date": session_meta_info["date"],
                "condition": session_meta_info["condition"],
                "direction": session_meta_info["direction"],
                "raw_distance_m": round(cum_raw_dist, 1),
                "filtered_distance_m": round(cum_filt_dist, 1),
                "jitter_reduction_pct": round((1.0 - cum_filt_dist / max(1.0, cum_raw_dist)) * 100.0, 1)
            }
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [cleaned_rows[0]["longitude_filtered"], cleaned_rows[0]["latitude_filtered"]]
            },
            "properties": {
                "name": "Origin",
                "time": cleaned_rows[0]["time_local"],
                "location": session_meta_info["origin"]
            }
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [cleaned_rows[-1]["longitude_filtered"], cleaned_rows[-1]["latitude_filtered"]]
            },
            "properties": {
                "name": "Destination",
                "time": cleaned_rows[-1]["time_local"],
                "location": session_meta_info["destination"]
            }
        }
    ]
    
    with open(os.path.join(output_dir, "filtered_track.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    # Telemetry Summary JSON
    idle_time_min = round(durations_m["STATIONARY_WAITING"] + durations_m["QUEUE_SHUFFLE"], 2)
    active_motion_min = round(durations_m["WALKING"] + durations_m["VEHICLE_TRANSIT"], 2)
    idle_ratio = round(idle_time_min / max(0.1, active_motion_min), 2)
    reduction_pct = round((1.0 - cum_filt_dist / max(1.0, cum_raw_dist)) * 100.0, 1)
    
    summary = {
        "session_id": session_name,
        "metadata": {
            "date": session_meta_info["date"],
            "start_time_local": cleaned_rows[0]["time_local"],
            "end_time_local": cleaned_rows[-1]["time_local"],
            "origin": session_meta_info["origin"],
            "destination": session_meta_info["destination"],
            "direction": session_meta_info["direction"],
            "condition": session_meta_info["condition"],
            "total_elapsed_minutes": total_min,
            "straight_line_distance_m": crow_dist_m,
            "raw_cumulative_distance_m": round(cum_raw_dist, 1),
            "filtered_cumulative_distance_m": round(cum_filt_dist, 1),
            "jitter_noise_reduction_pct": reduction_pct,
            "total_steps": cleaned_rows[-1]["cumulative_steps"] - cleaned_rows[0]["cumulative_steps"],
            "max_gps_speed_kmh": round(max(r["speed_gps_mps"] for r in cleaned_rows) * 3.6, 1),
            "max_filtered_speed_kmh": round(max(r["speed_filtered_mps"] for r in cleaned_rows) * 3.6, 1)
        },
        "state_durations_minutes": durations_m,
        "kpis": {
            "idle_queue_shelter_minutes": idle_time_min,
            "active_motion_minutes": active_motion_min,
            "idle_to_motion_ratio": f"{idle_ratio}x",
            "percent_time_stationary": round((idle_time_min / total_min) * 100.0, 1),
            "percent_time_moving": round((active_motion_min / total_min) * 100.0, 1)
        },
        "stages_count": len(merged_stages)
    }
    
    with open(os.path.join(output_dir, "telemetry_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        
    print(f"Session {session_name} clean: raw {cum_raw_dist:.1f}m -> filt {cum_filt_dist:.1f}m (-{reduction_pct}%), idle {idle_time_min}m vs active {active_motion_min}m ({idle_ratio}x)")
    return summary

def main():
    if not os.path.isdir(SESSIONS_DIR):
        print(f"Raw sensor sessions directory not found ({SESSIONS_DIR}); raw_data/ is restricted in public release.")
        print(f"Committed processed artifacts in {PROCESSED_DIR}/ remain valid.")
        return

    session_configs = [
        {
            "id": "session_1_2026-09-17_morning_M08_to_DTSP",
            "date": "2026-09-17",
            "origin": "Desasiswa Restu (M08 Pavilion)",
            "destination": "Dewan Tuanku Syed Putra (DTSP)",
            "direction": "TO_DTSP",
            "condition": "Sunny morning induction transit (queue bottleneck)"
        },
        {
            "id": "session_2_2026-09-17_evening_Persiaran_Sains_from_DTSP",
            "date": "2026-09-17",
            "origin": "Dewan Tuanku Syed Putra / Dataran Merah",
            "destination": "Persiaran Sains (Westbound)",
            "direction": "FROM_DTSP",
            "condition": "Evening post-induction dispersal walk"
        },
        {
            "id": "session_3_2026-09-18_morning_M01_Rainy_to_DTSP",
            "date": "2026-09-18",
            "origin": "Desasiswa Restu (M01 Complex) via RST Cafeteria",
            "destination": "Dewan Tuanku Syed Putra (DTSP)",
            "direction": "TO_DTSP",
            "condition": "Rainy morning delay: 118-min weather shelter in cafeteria, then transit"
        }
    ]
    
    all_summaries = []
    combined_geojson_features = []
    
    for cfg in session_configs:
        raw_path = os.path.join(SESSIONS_DIR, cfg["id"])
        out_path = os.path.join(PROCESSED_DIR, cfg["id"])
        summ = clean_session(cfg["id"], raw_path, out_path, cfg)
        if summ:
            all_summaries.append(summ)
            track_file = os.path.join(out_path, "filtered_track.geojson")
            with open(track_file, "r", encoding="utf-8") as gf:
                gdata = json.load(gf)
                combined_geojson_features.extend(gdata["features"])
                
    # Multi-session comparison JSON & CSV
    with open(os.path.join(PROCESSED_DIR, "multi_session_comparison.json"), "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2)
        
    with open(os.path.join(PROCESSED_DIR, "multi_session_comparison.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "session_id", "date", "direction", "condition", "total_min", "straight_m",
            "raw_dist_m", "filt_dist_m", "jitter_reduction_pct", "steps", "max_kmh",
            "stat_min", "shuffle_min", "walk_min", "vehicle_min", "idle_to_motion_ratio"
        ])
        for s in all_summaries:
            m = s["metadata"]
            d = s["state_durations_minutes"]
            k = s["kpis"]
            writer.writerow([
                s["session_id"], m["date"], m["direction"], m["condition"], m["total_elapsed_minutes"],
                m["straight_line_distance_m"], m["raw_cumulative_distance_m"], m["filtered_cumulative_distance_m"],
                m["jitter_noise_reduction_pct"], m["total_steps"], m["max_filtered_speed_kmh"],
                d["STATIONARY_WAITING"], d["QUEUE_SHUFFLE"], d["WALKING"], d["VEHICLE_TRANSIT"],
                k["idle_to_motion_ratio"]
            ])
            
    with open(os.path.join(PROCESSED_DIR, "all_sessions_combined.geojson"), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": combined_geojson_features}, f, indent=2)
        
    print(f"\nAll 3 sessions processed and saved successfully to {PROCESSED_DIR}/")

if __name__ == "__main__":
    main()
