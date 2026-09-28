"""Routing, topological path analysis, physics-based timing, and bottleneck modeling
for USM Kampus Induk orientation movement.

Enables agents and simulators to evaluate measured and unmeasured routes deterministically
without requiring physical on-ground measurement.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

# Base walking speeds (m/s)
V_FREE_WALK = 1.30          # Unimpeded solo pedestrian on flat paved surface
V_SUPERVISED_COLUMN = 0.85  # PPSL-escorted student group in column formation
V_CONGESTED_COLUMN = 0.42   # Dense crowd / restricted road-shoulder / single-file flow
V_MIN = 0.35
V_MAX = 1.65

# Stair speeds (steps per second)
STAIR_ASCENT_STEPS_S = 0.50
STAIR_DESCENT_STEPS_S = 0.65

# Fruin Pedestrian Level of Service (LOS) Flow capacities (pax / min / meter of width)
CAPACITY_FLAT_WALKWAY_PAX_MIN_M = 75.0   # LOS C/D comfortable flow
CAPACITY_STAIRWAY_PAX_MIN_M = 42.0       # Standard stairway discharge
CAPACITY_SINGLE_FILE_PAX_MIN = 45.0      # Strict single file maximum throughput

# Solar heat / exposure penalty multiplier (daytime open sun vs shaded/covered)
HEAT_EXPOSURE_FACTOR = 1.15


@dataclass
class RouteSegment:
    segment_id: str
    name: str
    distance_m: float
    elevation_start_m: float
    elevation_end_m: float
    surface: str  # "paved", "curb_shoulder", "stairway", "footbridge", "covered_walkway"
    width_m: float
    is_covered: bool
    is_stairs: bool = False
    step_count: int = 0
    single_file_enforced: bool = False
    crosses_road: bool = False
    osm_way_id: Optional[int] = None
    notes: str = ""

    @property
    def slope(self) -> float:
        """Slope fraction (rise / run). Positive = uphill, negative = downhill."""
        if self.distance_m <= 0:
            return 0.0
        return (self.elevation_end_m - self.elevation_start_m) / self.distance_m

    def compute_duration(
        self,
        mode: Literal["free", "supervised_column", "congested"] = "supervised_column",
        sun_exposed: bool = True,
    ) -> float:
        """Deterministic duration in seconds using Tobler's Hiking function and stair kinematics."""
        if self.is_stairs:
            steps = self.step_count or max(1, int(abs(self.elevation_end_m - self.elevation_start_m) * 6))
            rate = STAIR_ASCENT_STEPS_S if self.elevation_end_m > self.elevation_start_m else STAIR_DESCENT_STEPS_S
            base_s = steps / rate
            if mode == "congested":
                base_s *= 1.4
            elif mode == "supervised_column":
                base_s *= 1.15
            return round(base_s, 1)

        # Tobler's hiking function: v = 6 * exp(-3.5 * |slope + 0.05|) km/h -> m/s
        s = self.slope
        v_tobler_kmh = 6.0 * math.exp(-3.5 * abs(s + 0.05))
        v_tobler_ms = v_tobler_kmh / 3.6

        # Scale by crowd mode
        if mode == "free":
            v = min(V_MAX, max(V_MIN, v_tobler_ms))
        elif mode == "supervised_column":
            v = min(V_SUPERVISED_COLUMN, max(V_MIN, v_tobler_ms * (V_SUPERVISED_COLUMN / V_FREE_WALK)))
        else:  # congested
            v = min(V_CONGESTED_COLUMN, max(V_MIN, v_tobler_ms * (V_CONGESTED_COLUMN / V_FREE_WALK)))

        if self.single_file_enforced:
            v = min(v, V_CONGESTED_COLUMN)

        duration_s = self.distance_m / max(v, V_MIN)

        # Environmental heat penalty for open unshaded stretches
        if sun_exposed and not self.is_covered:
            duration_s *= HEAT_EXPOSURE_FACTOR

        # Road crossing delay (checking traffic / escort pause)
        if self.crosses_road:
            duration_s += 15.0 if mode == "free" else 30.0

        return round(duration_s, 1)

    def bottleneck_capacity_pax_min(self) -> float:
        """Maximum continuous student throughput (pax / min) through this segment."""
        if self.single_file_enforced:
            if self.is_stairs:
                return min(CAPACITY_SINGLE_FILE_PAX_MIN, round(self.width_m * CAPACITY_STAIRWAY_PAX_MIN_M, 1))
            return CAPACITY_SINGLE_FILE_PAX_MIN
        if self.is_stairs:
            return round(self.width_m * CAPACITY_STAIRWAY_PAX_MIN_M, 1)
        return round(self.width_m * CAPACITY_FLAT_WALKWAY_PAX_MIN_M, 1)


@dataclass
class Bottleneck:
    segment_id: str
    name: str
    bottleneck_type: str  # "staircase", "single_file", "road_crossing", "narrow_passage"
    max_flow_pax_min: float
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    mitigation_options: List[str] = field(default_factory=list)


@dataclass
class RouteProfile:
    hostel_id: str
    hostel_name: str
    variant: str  # "standard", "accessible_step_free", "max_covered"
    origin_lat: float
    origin_lon: float
    destination_id: str
    destination_lat: float
    destination_lon: float
    segments: List[RouteSegment]
    is_measured: bool = False
    measured_reference: Optional[str] = None

    @property
    def total_distance_m(self) -> float:
        return sum(s.distance_m for s in self.segments)

    @property
    def total_covered_distance_m(self) -> float:
        return sum(s.distance_m for s in self.segments if s.is_covered)

    @property
    def shaded_percentage(self) -> float:
        tot = self.total_distance_m
        return round((self.total_covered_distance_m / tot * 100.0) if tot > 0 else 0.0, 1)

    @property
    def elevation_gain_m(self) -> float:
        return sum(max(0.0, s.elevation_end_m - s.elevation_start_m) for s in self.segments)

    @property
    def elevation_loss_m(self) -> float:
        return sum(max(0.0, s.elevation_start_m - s.elevation_end_m) for s in self.segments)

    def calculate_timings(self) -> Dict[str, Any]:
        t_free = sum(s.compute_duration("free", sun_exposed=False) for s in self.segments)
        t_column = sum(s.compute_duration("supervised_column", sun_exposed=True) for s in self.segments)
        t_congested = sum(s.compute_duration("congested", sun_exposed=True) for s in self.segments)

        return {
            "free_flow_s": round(t_free),
            "free_flow_min": round(t_free / 60.0, 1),
            "supervised_column_s": round(t_column),
            "supervised_column_min": round(t_column / 60.0, 1),
            "congested_s": round(t_congested),
            "congested_min": round(t_congested / 60.0, 1),
            "recommended_window_s": [round(t_column * 0.95), round(t_column * 1.20)],
            "recommended_window_min": [round(t_column * 0.95 / 60.0, 1), round(t_column * 1.20 / 60.0, 1)],
        }

    def audit_bottlenecks(self) -> List[Bottleneck]:
        bottlenecks: List[Bottleneck] = []
        for s in self.segments:
            cap = s.bottleneck_capacity_pax_min()
            if s.single_file_enforced:
                bottlenecks.append(
                    Bottleneck(
                        segment_id=s.segment_id,
                        name=s.name,
                        bottleneck_type="single_file",
                        max_flow_pax_min=cap,
                        severity="critical" if cap <= 45.0 else "high",
                        description=f"Strict single-file column restriction: max {cap} pax/min.",
                        mitigation_options=[
                            "Pace upstream release in batches of 40-50 students",
                            "Assign dedicated PPSL marshall at entrance to prevent bunching",
                        ],
                    )
                )
            elif s.is_stairs:
                bottlenecks.append(
                    Bottleneck(
                        segment_id=s.segment_id,
                        name=s.name,
                        bottleneck_type="staircase",
                        max_flow_pax_min=cap,
                        severity="high" if cap < 85.0 else "medium",
                        description=f"Stair flight with {s.step_count} steps, width {s.width_m}m: max {cap} pax/min.",
                        mitigation_options=[
                            "Use accessible step-free alternative for large cohorts",
                            "Enforce 2-abreast descent with handrail clearance",
                        ],
                    )
                )
            elif s.crosses_road:
                bottlenecks.append(
                    Bottleneck(
                        segment_id=s.segment_id,
                        name=s.name,
                        bottleneck_type="road_crossing",
                        max_flow_pax_min=100.0,
                        severity="medium",
                        description=f"Unsignalized vehicular carriageway crossing at {s.name}.",
                        mitigation_options=[
                            "Station PPSL road wardens with baton/whistle to halt vehicle traffic",
                            "Pulse crossing in coherent platoons rather than trickle flow",
                        ],
                    )
                )
            elif s.width_m <= 1.2:
                bottlenecks.append(
                    Bottleneck(
                        segment_id=s.segment_id,
                        name=s.name,
                        bottleneck_type="narrow_passage",
                        max_flow_pax_min=cap,
                        severity="medium",
                        description=f"Narrow passage width ({s.width_m}m): max {cap} pax/min.",
                        mitigation_options=["Prohibit overtaking; maintain steady walking interval"],
                    )
                )

        return sorted(bottlenecks, key=lambda b: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[b.severity], b.max_flow_pax_min))


# ---------------------------------------------------------------------------
# Authoritative Campus Route Registry (Ground-truth topological mapping)
# ---------------------------------------------------------------------------

def _build_default_routes() -> Dict[Tuple[str, str], RouteProfile]:
    """Constructs topological route models for all 8 campus hostels with exact elevations and widths."""
    routes: Dict[Tuple[str, str], RouteProfile] = {}

    # 1. RESTU (Restu Cafe M07) -> DTSP Walk
    routes[("restu", "standard")] = RouteProfile(
        hostel_id="restu",
        hostel_name="Desasiswa Restu",
        variant="standard",
        origin_lat=5.356461,
        origin_lon=100.289265,
        destination_id="dtsp_exterior_gathering",
        destination_lat=5.357153,
        destination_lon=100.301749,
        is_measured=True,
        measured_reference="Sensor Logger 2026-09-17 trace + GPS Session 3 cafe origin",
        segments=[
            RouteSegment("rst_seg_1", "Restu Cafe (M07) to DUD Forecourt", 130.0, 47.0, 47.0, "paved", 4.0, False, notes="Start at Restu Cafe upon release / 06:30, walk north to DUD forecourt assembly"),
            RouteSegment("rst_seg_2", "DUD (M08) to Jejantas Overpass (Road Shoulder)", 210.0, 47.0, 36.0, "curb_shoulder", 1.2, False, single_file_enforced=True, notes="Strict single file enforced on curb from DUD to overpass to keep carriageway clear"),
            RouteSegment("rst_seg_3", "Jejantas Padang Kawad Footbridge Approach", 45.0, 36.0, 38.0, "footbridge", 1.8, True, osm_way_id=1030376052),
            RouteSegment("rst_seg_4", "Jejantas Padang Kawad Descent Stairs", 25.0, 38.0, 14.0, "stairway", 1.2, True, is_stairs=True, step_count=48, single_file_enforced=True, osm_way_id=1030376053),
            RouteSegment("rst_seg_5", "Padang Kawad Roundabout Crossing", 30.0, 14.0, 13.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("rst_seg_6", "Jalan Universiti Arterial Footway (West)", 650.0, 13.0, 16.0, "paved", 2.2, False),
            RouteSegment("rst_seg_7", "Jalan Universiti Arterial Footway (East Shared Spine)", 450.0, 16.0, 18.0, "paved", 2.5, False),
            RouteSegment("rst_seg_8", "Jalan Perpustakaan Entrance Ramp", 140.0, 18.0, 20.0, "paved", 3.0, False),
            RouteSegment("rst_seg_9", "DTSP Arrival Basin & 3-Tier Car Park Apron", 90.0, 20.0, 19.0, "paved", 6.0, False),
        ],
    )

    # 2. TEKUN (M05 / M06) -> DTSP Walk (Unmeasured)
    routes[("tekun", "standard")] = RouteProfile(
        hostel_id="tekun",
        hostel_name="Desasiswa Tekun",
        variant="standard",
        origin_lat=5.355640,
        origin_lon=100.291293,
        destination_id="dtsp_exterior_gathering",
        destination_lat=5.357153,
        destination_lon=100.301749,
        segments=[
            RouteSegment("tek_seg_1", "Tekun M05 Forecourt & Departure Plaza", 70.0, 54.0, 52.0, "paved", 3.5, False),
            RouteSegment("tek_seg_2", "Ridge Stair Flight descending to Hub Padang Kawad", 40.0, 52.0, 22.0, "stairway", 1.1, False, is_stairs=True, step_count=65, single_file_enforced=True),
            RouteSegment("tek_seg_3", "Hub Padang Kawad Perimeter Path", 180.0, 22.0, 12.0, "paved", 2.0, False),
            RouteSegment("tek_seg_4", "Padang Kawad North Gate Crossing", 35.0, 12.0, 12.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("tek_seg_5", "Jalan Universiti Spine (Shared Section)", 1100.0, 12.0, 18.0, "paved", 2.2, False),
            RouteSegment("tek_seg_6", "Jalan Perpustakaan Approach to DTSP Car Park", 230.0, 18.0, 19.0, "paved", 3.5, False),
        ],
    )

    # 3. SAUJANA (M03 / M04) -> DTSP Walk (Unmeasured)
    routes[("saujana", "standard")] = RouteProfile(
        hostel_id="saujana",
        hostel_name="Desasiswa Saujana",
        variant="standard",
        origin_lat=5.356536,
        origin_lon=100.289760,
        destination_id="dtsp_exterior_gathering",
        destination_lat=5.357153,
        destination_lon=100.301749,
        segments=[
            RouteSegment("sau_seg_1", "Saujana M03/M04 Courtyard Assembly", 60.0, 46.0, 45.0, "paved", 3.0, False),
            RouteSegment("sau_seg_2", "Connecting Ridge Road to Jejantas Overpass", 190.0, 45.0, 38.0, "curb_shoulder", 1.5, False, single_file_enforced=True),
            RouteSegment("sau_seg_3", "Jejantas Padang Kawad Overpass & Stairs", 65.0, 38.0, 14.0, "stairway", 1.2, True, is_stairs=True, step_count=48, single_file_enforced=True),
            RouteSegment("sau_seg_4", "Padang Kawad East Connector Path", 210.0, 14.0, 12.0, "paved", 2.0, False),
            RouteSegment("sau_seg_5", "Jalan Universiti Central Arterial Walkway", 980.0, 12.0, 18.0, "paved", 2.5, False),
            RouteSegment("sau_seg_6", "DTSP West Access Ramp", 145.0, 18.0, 19.0, "paved", 3.5, False),
        ],
    )

    # 4. INDAH KEMBARA (L05 - L07) -> DTSP South Plaza / Field (Unmeasured)
    routes[("indah_kembara", "standard")] = RouteProfile(
        hostel_id="indah_kembara",
        hostel_name="Desasiswa Indah Kembara",
        variant="standard",
        origin_lat=5.356031,
        origin_lon=100.296045,
        destination_id="dtsp_south_plaza",
        destination_lat=5.356118,
        destination_lon=100.302400,
        segments=[
            RouteSegment("ik_seg_1", "Indah Kembara L07 Forecourt Assembly", 50.0, 12.0, 12.0, "paved", 3.5, False),
            RouteSegment("ik_seg_2", "Jalan Indah Kembara Sidewalk", 310.0, 12.0, 14.0, "paved", 1.8, False),
            RouteSegment("ik_seg_3", "Junction Jabatan Keselamatan Crossing", 30.0, 14.0, 14.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("ik_seg_4", "Jalan Universiti East Arterial (Flat Valley)", 520.0, 14.0, 17.0, "paved", 2.2, False),
            RouteSegment("ik_seg_5", "Pusat Bahasa Walkway to G28 Siswaniaga Field", 180.0, 17.0, 19.0, "paved", 2.5, True),
        ],
    )

    # 5. AMAN DAMAI (K10) -> DTSP South Plaza / Field (Unmeasured)
    routes[("aman_damai", "standard")] = RouteProfile(
        hostel_id="aman_damai",
        hostel_name="Desasiswa Aman Damai",
        variant="standard",
        origin_lat=5.354304,
        origin_lon=100.296202,
        destination_id="dtsp_south_plaza",
        destination_lat=5.356118,
        destination_lon=100.302400,
        segments=[
            RouteSegment("ad_seg_1", "Damai Cafeteria K10 Gathering Forecourt", 45.0, 14.0, 14.0, "paved", 3.0, False),
            RouteSegment("ad_seg_2", "Internal Residential Walkways between K Blocks", 180.0, 14.0, 15.0, "paved", 1.2, False, notes="Narrow residential sidewalk"),
            RouteSegment("ad_seg_3", "Jalan Damai Egress to Sports Complex", 220.0, 15.0, 15.0, "paved", 2.0, False),
            RouteSegment("ad_seg_4", "Jalan Sungai Dua Gate Road Crossing", 35.0, 15.0, 15.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("ad_seg_5", "Jalan Universiti South Sidewalk to Pusat Bahasa", 480.0, 15.0, 18.0, "paved", 2.0, False),
            RouteSegment("ad_seg_6", "Siswaniaga Grass Field Assembly Buffer", 120.0, 18.0, 19.0, "paved", 3.5, False),
        ],
    )

    # 6. BAKTI FAJAR PERMAI (H10) -> DTSP North Plaza / Dataran Merah (Unmeasured)
    routes[("bakti_fajar_permai", "standard")] = RouteProfile(
        hostel_id="bakti_fajar_permai",
        hostel_name="Desasiswa Bakti Fajar Permai",
        variant="standard",
        origin_lat=5.357763,
        origin_lon=100.300499,
        destination_id="dtsp_north_plaza",
        destination_lat=5.356518,
        destination_lon=100.303214,
        segments=[
            RouteSegment("bfp_seg_1", "H10 Cafeteria Courtyard Assembly", 40.0, 26.0, 25.0, "paved", 3.0, False),
            RouteSegment("bfp_seg_2", "Persiaran Sains Road Crossing", 25.0, 25.0, 25.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("bfp_seg_3", "Pusat Sejahtera Pedestrian Spine", 160.0, 25.0, 23.0, "paved", 2.5, True),
            RouteSegment("bfp_seg_4", "Chemical Sciences Terraced Stairs", 30.0, 23.0, 20.0, "stairway", 1.4, True, is_stairs=True, step_count=22, osm_way_id=1354565634),
            RouteSegment("bfp_seg_5", "Covered Academic Walkway past School of Physics", 220.0, 20.0, 19.0, "covered_walkway", 2.0, True),
            RouteSegment("bfp_seg_6", "Lengkok Perpustakaan to Dataran Merah North Plaza", 140.0, 19.0, 19.0, "paved", 4.0, True),
        ],
    )

    # 7. CAHAYA GEMILANG (H33 - H35) -> DTSP North Plaza / Dataran Merah (Unmeasured)
    routes[("cahaya_gemilang", "standard")] = RouteProfile(
        hostel_id="cahaya_gemilang",
        hostel_name="Desasiswa Cahaya Gemilang",
        variant="standard",
        origin_lat=5.360424,
        origin_lon=100.303549,
        destination_id="dtsp_north_plaza",
        destination_lat=5.356518,
        destination_lon=100.303214,
        segments=[
            RouteSegment("cg_seg_1", "H33-H35 Forecourt Assembly", 50.0, 28.0, 27.0, "paved", 3.5, False),
            RouteSegment("cg_seg_2", "Jalan Gemilang Sidewalk", 210.0, 27.0, 24.0, "paved", 2.0, False),
            RouteSegment("cg_seg_3", "Jalan Mahasiswa Crossing at C23 DK Complex", 35.0, 24.0, 23.0, "paved", 3.0, False, crosses_road=True),
            RouteSegment("cg_seg_4", "Dewan Kuliah Foyer Stairs", 25.0, 23.0, 20.0, "stairway", 1.5, True, is_stairs=True, step_count=18, osm_way_id=1354921230),
            RouteSegment("cg_seg_5", "Lengkok Sastera Covered Walkway", 240.0, 20.0, 19.0, "covered_walkway", 2.2, True),
            RouteSegment("cg_seg_6", "PHS 1 Perimeter Path into Dataran Merah", 90.0, 19.0, 19.0, "paved", 3.5, True),
        ],
    )

    # 8. FAJAR HARAPAN (F25 - F27) -> DTSP South Portico / Field (Unmeasured)
    routes[("fajar_harapan", "standard")] = RouteProfile(
        hostel_id="fajar_harapan",
        hostel_name="Desasiswa Fajar Harapan",
        variant="standard",
        origin_lat=5.354996,
        origin_lon=100.299797,
        destination_id="dtsp_south_plaza",
        destination_lat=5.356118,
        destination_lon=100.302400,
        segments=[
            RouteSegment("fh_seg_1", "F27 Kantin Harapan Gathering Court", 45.0, 25.0, 24.0, "paved", 3.0, False),
            RouteSegment("fh_seg_2", "Fajar Residential Terrace Steps to Eureka Path", 25.0, 24.0, 20.0, "stairway", 1.2, False, is_stairs=True, step_count=24, osm_way_id=1354561992),
            RouteSegment("fh_seg_3", "Kompleks Eureka Access Road", 190.0, 20.0, 18.0, "paved", 2.2, False),
            RouteSegment("fh_seg_4", "Tasik USM Lakeside Path", 210.0, 18.0, 18.0, "paved", 1.8, False, notes="Narrow pathway adjacent to central lake"),
            RouteSegment("fh_seg_5", "Dewan Budaya Approach Path to G28 Field", 110.0, 18.0, 19.0, "paved", 3.0, False),
        ],
    )

    # ACCESSIBLE ALTERNATIVE: Aman Damai Step-Free (Ramps instead of stairs)
    routes[("aman_damai", "accessible_step_free")] = RouteProfile(
        hostel_id="aman_damai",
        hostel_name="Desasiswa Aman Damai (Step-Free)",
        variant="accessible_step_free",
        origin_lat=5.354304,
        origin_lon=100.296202,
        destination_id="dtsp_south_plaza",
        destination_lat=5.356118,
        destination_lon=100.302400,
        segments=[
            RouteSegment("ad_acc_1", "Damai Cafeteria K10 Egress", 45.0, 14.0, 14.0, "paved", 3.0, False),
            RouteSegment("ad_acc_2", "Vehicular Carriageway bypassing block stairs", 280.0, 14.0, 15.0, "paved", 3.5, False),
            RouteSegment("ad_acc_3", "Pusat Sukan Ramp Access to Jalan Universiti", 310.0, 15.0, 16.0, "paved", 2.5, False),
            RouteSegment("ad_acc_4", "Jalan Universiti Paved Sidewalk", 520.0, 16.0, 18.0, "paved", 2.5, False),
            RouteSegment("ad_acc_5", "Siswaniaga Wheelchair-Accessible Ramp", 140.0, 18.0, 19.0, "paved", 3.0, False),
        ],
    )

    return routes


CAMPUS_ROUTES: Dict[Tuple[str, str], RouteProfile] = _build_default_routes()


# ---------------------------------------------------------------------------
# High-Level Scaffolding API for AI & Optimization Agents
# ---------------------------------------------------------------------------

def get_route_profile(hostel_id: str, variant: str = "standard") -> RouteProfile:
    """Retrieve the topological route profile for a given hostel origin."""
    key = (hostel_id.lower().replace("-", "_"), variant)
    if key not in CAMPUS_ROUTES:
        available = [f"{h}:{v}" for h, v in CAMPUS_ROUTES.keys()]
        raise KeyError(f"Route '{key}' not found. Available: {available}")
    return CAMPUS_ROUTES[key]


def calculate_route_timing(hostel_id: str, variant: str = "standard") -> Dict[str, Any]:
    """Calculate physics-based timing estimates for unmeasured and measured routes."""
    route = get_route_profile(hostel_id, variant)
    return {
        "hostel_id": route.hostel_id,
        "variant": route.variant,
        "is_measured": route.is_measured,
        "total_distance_m": route.total_distance_m,
        "elevation_gain_m": route.elevation_gain_m,
        "elevation_loss_m": route.elevation_loss_m,
        "shaded_percentage": route.shaded_percentage,
        "timings": route.calculate_timings(),
    }


def audit_route_bottlenecks(hostel_id: str, variant: str = "standard") -> Dict[str, Any]:
    """Analyze and rank physical bottlenecks along an unmeasured or measured route."""
    route = get_route_profile(hostel_id, variant)
    bottlenecks = route.audit_bottlenecks()
    min_flow = min((b.max_flow_pax_min for b in bottlenecks), default=120.0)

    return {
        "hostel_id": route.hostel_id,
        "variant": route.variant,
        "critical_flow_capacity_pax_min": min_flow,
        "choke_point_count": len(bottlenecks),
        "bottlenecks": [asdict(b) for b in bottlenecks],
    }


def get_route_summary(hostel_id: str, variant: str = "standard") -> Dict[str, Any]:
    """Comprehensive analysis report for an AI planner or simulation agent."""
    route = get_route_profile(hostel_id, variant)
    timings = route.calculate_timings()
    bottlenecks = route.audit_bottlenecks()
    min_flow = min((b.max_flow_pax_min for b in bottlenecks), default=120.0)

    return {
        "hostel_id": route.hostel_id,
        "hostel_name": route.hostel_name,
        "variant": route.variant,
        "is_measured": route.is_measured,
        "measured_reference": route.measured_reference,
        "origin_coords": {"lat": route.origin_lat, "lon": route.origin_lon},
        "destination_id": route.destination_id,
        "destination_coords": {"lat": route.destination_lat, "lon": route.destination_lon},
        "metrics": {
            "total_distance_m": route.total_distance_m,
            "elevation_gain_m": route.elevation_gain_m,
            "elevation_loss_m": route.elevation_loss_m,
            "shaded_distance_m": route.total_covered_distance_m,
            "shaded_percentage": route.shaded_percentage,
            "critical_flow_capacity_pax_min": min_flow,
            "segment_count": len(route.segments),
        },
        "timings": timings,
        "bottlenecks": [asdict(b) for b in bottlenecks],
        "segments": [asdict(s) for s in route.segments],
    }


def generate_campus_routing_matrix() -> List[Dict[str, Any]]:
    """Builds a campus-wide comparative matrix across all hostel origins."""
    rows = []
    for (hid, var), route in sorted(CAMPUS_ROUTES.items()):
        timings = route.calculate_timings()
        bottlenecks = route.audit_bottlenecks()
        min_flow = min((b.max_flow_pax_min for b in bottlenecks), default=120.0)
        critical_b = bottlenecks[0].name if bottlenecks else "None"

        rows.append({
            "hostel_id": hid,
            "variant": var,
            "distance_m": route.total_distance_m,
            "elev_drop_m": route.elevation_loss_m,
            "column_walk_min": timings["supervised_column_min"],
            "window_min": timings["recommended_window_min"],
            "shaded_pct": route.shaded_percentage,
            "critical_capacity_pax_min": min_flow,
            "primary_bottleneck": critical_b,
            "is_measured": route.is_measured,
        })
    return rows


def export_scaffolding_database(dest_path: Optional[str] = None) -> str:
    """Exports full JSON database to disk for offline agent reasoning and dashboards."""
    if dest_path is None:
        repo_root = Path(__file__).resolve().parent.parent
        dest_path = str(repo_root / "data" / "maps" / "unmeasured_routes_analysis.json")
    data = {
        "version": "1.0.0",
        "description": "Deterministic physics-based routing and bottleneck analysis for USM Kampus Induk",
        "matrix": generate_campus_routing_matrix(),
        "routes": {f"{h}:{v}": get_route_summary(h, v) for h, v in CAMPUS_ROUTES.keys()},
    }
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w") as f:
        json.dump(data, f, indent=2)
    return dest_path


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="USM Orientation Routing & Bottleneck Scaffolding")
    parser.add_argument("--hostel", type=str, help="Hostel ID (e.g. aman_damai, bakti_fajar_permai, tekun)")
    parser.add_argument("--variant", type=str, default="standard", help="Route variant (standard, accessible_step_free)")
    parser.add_argument("--matrix", action="store_true", help="Print comparative matrix across all hostels")
    parser.add_argument("--export", action="store_true", help="Export full database to JSON")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")

    args = parser.parse_args()

    if args.export:
        p = export_scaffolding_database()
        print(f"Exported routing scaffolding database to: {p}")
        return

    if args.matrix:
        matrix = generate_campus_routing_matrix()
        if args.json:
            print(json.dumps(matrix, indent=2))
        else:
            print(f"{'Hostel':20} {'Var':12} {'Dist (m)':9} {'Drop (m)':9} {'Walk (min)':11} {'Shade%':8} {'Cap (pax/m)':12} {'Primary Choke Point'}")
            print("-" * 105)
            for r in matrix:
                print(f"{r['hostel_id']:20} {r['variant']:12} {r['distance_m']:<9.0f} {r['elev_drop_m']:<9.1f} {r['column_walk_min']:<11.1f} {r['shaded_pct']:<8.1f} {r['critical_capacity_pax_min']:<12.1f} {r['primary_bottleneck']}")
        return

    if args.hostel:
        try:
            summary = get_route_summary(args.hostel, args.variant)
        except KeyError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"=== ROUTE PROFILE: {summary['hostel_name']} ({summary['variant']}) ===")
            print(f"Distance: {summary['metrics']['total_distance_m']:.0f} m | Elevation: +{summary['metrics']['elevation_gain_m']:.1f}m / -{summary['metrics']['elevation_loss_m']:.1f}m | Shaded: {summary['metrics']['shaded_percentage']}%")
            print(f"Supervised March Time: {summary['timings']['supervised_column_min']} min (Window: {summary['timings']['recommended_window_min'][0]} - {summary['timings']['recommended_window_min'][1]} min)")
            print(f"Critical Capacity: {summary['metrics']['critical_flow_capacity_pax_min']} pax/min | Choke points: {len(summary['bottlenecks'])}")
            print("\nIdentified Bottlenecks:")
            for b in summary["bottlenecks"]:
                print(f"  [{b['severity'].upper()}] {b['name']} ({b['bottleneck_type']}): max {b['max_flow_pax_min']} pax/min — {b['description']}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
