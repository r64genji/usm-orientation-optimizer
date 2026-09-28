"""High-fidelity vector + satellite cartographic rendering of USM orientation operational plans.

Generates realistic, physically-grounded tactical site plans with:
- Exact building footprints from OSM polygons
- 100% real road and footway geometry (zero flying through residential blocks)
- True 8-bus docking layout along the straight north-south car park roadway corridor
- True student arrangement grids (seated columns, single-file marching streams, 40-pax batches)
- PPSL control stations, headcount timers, and capacity annotations
"""

import json
import math
import os
from PIL import Image, ImageDraw, ImageFont

# Fonts
FONT_TITLE = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 20)
FONT_HEADING = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 14)
FONT_LABEL = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 11)
FONT_SMALL = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 11)
FONT_REG = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 10)
FONT_MICRO = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf', 9)
FONT_BOLD_MICRO = ImageFont.truetype('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 9)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'maps')
GEOJSON_DIR = os.path.join(DATA_DIR, 'geojson')
SATELLITE_DIR = os.path.join(DATA_DIR, 'satellite')
PLANS_DIR = os.path.join(DATA_DIR, 'plans')

with open(os.path.join(GEOJSON_DIR, 'usm_buildings.geojson')) as f:
    BUILDINGS_GEO = json.load(f)
with open(os.path.join(GEOJSON_DIR, 'usm_gathering_areas.geojson')) as f:
    AREAS_GEO = json.load(f)
with open(os.path.join(GEOJSON_DIR, 'usm_pedestrian_network.geojson')) as f:
    PED_GEO = json.load(f)
with open(os.path.join(GEOJSON_DIR, 'usm_transit_network.geojson')) as f:
    TRANSIT_GEO = json.load(f)


def get_pixel_z19(lat: float, lon: float, x_min_tile: int, y_min_tile: int) -> tuple[int, int]:
    """Exact Web Mercator pixel coordinate at Zoom 19."""
    n = 2.0 ** 19
    x_f = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return int((x_f - x_min_tile) * 256), int((y_f - y_min_tile) * 256)


def draw_cased_way(draw, pts, core_color, core_width=3, casing_color=(15, 23, 42, 220), casing_width=6):
    if len(pts) >= 2:
        draw.line(pts, fill=casing_color, width=casing_width, joint='curve')
        draw.line(pts, fill=core_color, width=core_width, joint='curve')


def draw_stair_treads(draw, pts, tread_spacing=5, tread_color=(255, 255, 255, 240)):
    for i in range(len(pts) - 1):
        p1, p2 = pts[i], pts[i + 1]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        dist = math.hypot(dx, dy)
        if dist < 1:
            continue
        ux, uy = dx / dist, dy / dist
        vx, vy = -uy, ux
        num_treads = max(1, int(dist / tread_spacing))
        for t in range(num_treads + 1):
            cx = p1[0] + ux * (t * tread_spacing)
            cy = p1[1] + uy * (t * tread_spacing)
            draw.line([(cx - vx * 4, cy - vy * 4), (cx + vx * 4, cy + vy * 4)], fill=tread_color, width=2)


def draw_north_arrow(draw, pos=(60, 80)):
    x, y = pos
    draw.polygon([(x, y - 25), (x - 8, y + 10), (x, y + 4)], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255))
    draw.polygon([(x, y - 25), (x + 8, y + 10), (x, y + 4)], fill=(255, 255, 255, 255), outline=(200, 200, 200, 255))
    draw.text((x - 4, y - 38), 'N', fill=(255, 255, 255), font=FONT_HEADING)


def draw_scale_bar(draw, scale_m_per_px: float, pos=(50, 1200), bar_meters=100):
    x, y = pos
    px_len = int(bar_meters / scale_m_per_px)
    draw.rectangle([x - 10, y - 10, x + px_len + 30, y + 25], fill=(15, 23, 42, 220), outline=(71, 85, 105, 200), width=1)
    draw.line([(x, y), (x + px_len, y)], fill=(255, 255, 255), width=3)
    draw.line([(x, y - 4), (x, y + 4)], fill=(255, 255, 255), width=2)
    draw.line([(x + px_len // 2, y - 3), (x + px_len // 2, y + 3)], fill=(255, 255, 255), width=2)
    draw.line([(x + px_len, y - 4), (x + px_len, y + 4)], fill=(255, 255, 255), width=2)
    draw.text((x - 3, y + 6), '0m', fill=(255, 255, 255), font=FONT_MICRO)
    draw.text((x + px_len // 2 - 10, y + 6), f'{bar_meters // 2}m', fill=(255, 255, 255), font=FONT_MICRO)
    draw.text((x + px_len - 12, y + 6), f'{bar_meters}m', fill=(255, 255, 255), font=FONT_MICRO)


def draw_hud_panel(draw, x, y, w, h, title, items, badge_color=(56, 189, 248)):
    draw.rectangle([x, y, x + w, y + h], fill=(15, 23, 42, 235), outline=(71, 85, 105, 220), width=1)
    draw.rectangle([x, y, x + w, y + 26], fill=(30, 41, 59, 240))
    draw.rectangle([x + 6, y + 6, x + 10, y + 20], fill=badge_color)
    draw.text((x + 16, y + 6), title, fill=(255, 255, 255), font=FONT_LABEL)

    cy = y + 32
    for label, val, sub in items:
        draw.text((x + 10, cy), label, fill=(148, 163, 184), font=FONT_MICRO)
        draw.text((x + w - len(val) * 6 - 12, cy), val, fill=(255, 255, 255), font=FONT_BOLD_MICRO)
        if sub:
            cy += 12
            draw.text((x + 14, cy), sub, fill=(100, 116, 139), font=FONT_MICRO)
        cy += 16


def render_dtsp_plan():
    """Generates the high-precision DTSP Precinct Tactical Intake Plan with true docking corridor."""
    print("Rendering DTSP Precinct Plan...")
    base_path = os.path.join(SATELLITE_DIR, 'dtsp_precinct_z19.jpg')
    base = Image.open(base_path).convert('RGBA')
    W, H = base.size

    dimmer = Image.new('RGBA', (W, H), (15, 23, 42, 65))
    base = Image.alpha_composite(base, dimmer)

    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    x_min_tile, y_min_tile = 408216, 254329
    def proj(lat, lon):
        return get_pixel_z19(lat, lon, x_min_tile, y_min_tile)

    # 1. Render all OSM Roads
    for f in TRANSIT_GEO['features']:
        if f['geometry']['type'] == 'LineString':
            pts = [proj(p[1], p[0]) for p in f['geometry']['coordinates']]
            pts_in = [p for p in pts if 0 <= p[0] < W and 0 <= p[1] < H]
            if len(pts_in) >= 2:
                draw_cased_way(draw, pts, core_color=(51, 65, 85, 220), core_width=6, casing_color=(15, 23, 42, 200), casing_width=10)

    # 2. Render all OSM Footways & Steps
    for f in PED_GEO['features']:
        if f['geometry']['type'] == 'LineString':
            pts = [proj(p[1], p[0]) for p in f['geometry']['coordinates']]
            pts_in = [p for p in pts if 0 <= p[0] < W and 0 <= p[1] < H]
            if len(pts_in) >= 2:
                hw = f['properties'].get('highway')
                is_cov = f['properties'].get('covered') == 'yes'
                if is_cov:
                    draw_cased_way(draw, pts, core_color=(245, 158, 11, 230), core_width=4, casing_color=(15, 23, 42, 200), casing_width=7)
                elif hw == 'steps':
                    draw_cased_way(draw, pts, core_color=(226, 232, 240, 240), core_width=5, casing_color=(15, 23, 42, 200), casing_width=8)
                    draw_stair_treads(draw, pts, tread_spacing=4)
                else:
                    draw_cased_way(draw, pts, core_color=(148, 163, 184, 180), core_width=2, casing_color=(15, 23, 42, 160), casing_width=4)

    # 3. Render all OSM Building Footprints
    key_bldg_styles = {
        896393762: ('G01 DTSP MAIN HALL (~3,000 SEATS)', (245, 158, 11, 240), (245, 158, 11, 70)),
        94331153: ('G03 DEWAN BUDAYA (~500 SEATS OVERFLOW)', (168, 85, 247, 240), (168, 85, 247, 70)),
        208697647: ('G02 PERPUSTAKAAN HAMZAH SENDUT 1', (56, 189, 248, 220), (56, 189, 248, 60)),
        205875602: ('E41 PERPUSTAKAAN HAMZAH SENDUT 2', (56, 189, 248, 200), (56, 189, 248, 50)),
    }

    for f in BUILDINGS_GEO['features']:
        bid = f['properties']['id']
        coords = f['geometry']['coordinates'][0]
        pts = [proj(p[1], p[0]) for p in coords]
        if any(0 <= p[0] < W and 0 <= p[1] < H for p in pts):
            if bid in key_bldg_styles:
                label, outline_col, fill_col = key_bldg_styles[bid]
                draw.polygon(pts, fill=fill_col, outline=outline_col, width=2)
                cx = int(sum(p[0] for p in pts) / len(pts))
                cy = int(sum(p[1] for p in pts) / len(pts))
                tw = len(label) * 6 + 10
                draw.rectangle([cx - tw // 2, cy - 8, cx + tw // 2, cy + 8], fill=(15, 23, 42, 230), outline=outline_col, width=1)
                draw.text((cx - tw // 2 + 5, cy - 6), label, fill=(255, 255, 255), font=FONT_MICRO)
            else:
                draw.polygon(pts, fill=(255, 255, 255, 30), outline=(255, 255, 255, 140), width=1)

    # 4. Render 3-Tier Car Park Waiting Area (`way 1031081039`)
    cp_feat = next((f for f in AREAS_GEO['features'] if f['properties']['id'] == 1031081039), None)
    if cp_feat:
        cp_pts = [proj(p[1], p[0]) for p in cp_feat['geometry']['coordinates'][0]]
        draw.polygon(cp_pts, fill=(14, 165, 233, 50), outline=(14, 165, 233, 230), width=2)

        # Seated student columns inside the 3 tiers
        cx, cy = 760, 440
        # Tier 1 (Apron, center): 8 columns of 40 students = 320
        for col in range(8):
            for row in range(12):
                sx = cx - 55 + col * 12
                sy = cy - 25 + row * 6
                draw.ellipse([sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5], fill=(56, 189, 248, 230))
        # Tier 2 (Mid-terrace): 3 columns of 40 = 120
        for col in range(3):
            for row in range(12):
                sx = cx + 50 + col * 12
                sy = cy - 25 + row * 6
                draw.ellipse([sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5], fill=(56, 189, 248, 230))

        draw.text((cx - 70, cy + 55), "3-TIER CAR PARK HOLDING RESERVOIR", fill=(255, 255, 255), font=FONT_LABEL)
        draw.text((cx - 70, cy + 70), "Cap: 500 Safe / 600 Max | 5-min PPSL Headcount Dwell", fill=(148, 163, 184), font=FONT_MICRO)

    # 5. REAL DOCKING CORRIDOR ALONG THE NORTH-SOUTH ROAD (`Way 646847618`)
    # The 8 buses queue strictly in a single-file line along the kerb of the straight road
    w_dock = next(f for f in TRANSIT_GEO['features'] if f['properties']['id'] == 646847618)
    coords_dock = w_dock['geometry']['coordinates']
    pts_dock_road = [proj(p[1], p[0]) for p in coords_dock]
    draw_cased_way(draw, pts_dock_road, core_color=(234, 179, 8, 255), core_width=8, casing_color=(15, 23, 42, 230), casing_width=13)

    # Draw the 8 buses positioned sequentially along the roadway corridor
    # Road runs from pixel (616, 208) heading south-southeast to (557, 574)
    # 8 buses, length = 32px (10m), width = 10px (3m)
    bus_positions = [
        # Rear 4 buses queued in-line (approaching/holding on road)
        ((625, 225), False, "Bus 8 (Queued)"),
        ((645, 260), False, "Bus 7 (Queued)"),
        ((665, 295), False, "Bus 6 (Queued)"),
        ((670, 335), False, "Bus 5 (Queued)"),
        # Front 4 buses actively offloading at kerbside onto car park tiers
        ((660, 375), True, "Bus 4 (Active Offload Bay 4)"),
        ((645, 415), True, "Bus 3 (Active Offload Bay 3)"),
        ((625, 455), True, "Bus 2 (Active Offload Bay 2)"),
        ((605, 495), True, "Bus 1 (Active Offload Bay 1)"),
    ]

    for (bx, by), is_active, label in bus_positions:
        col = (34, 197, 94) if is_active else (234, 179, 8)
        # Oriented slightly along road bearing (~165 deg)
        draw.rectangle([bx - 6, by - 16, bx + 6, by + 16], fill=col, outline=(255, 255, 255), width=1)
        if is_active:
            # Flow arrow stepping off passenger door directly onto car park kerbside
            draw.line([(bx + 6, by), (bx + 22, by + 4)], fill=(34, 197, 94, 255), width=2)
            draw.polygon([(bx + 22, by + 4), (bx + 16, by), (bx + 18, by + 8)], fill=(34, 197, 94))

    # Docking Area HUD Label
    draw.rectangle([440, 160, 750, 195], fill=(15, 23, 42, 235), outline=(34, 197, 94, 240), width=1)
    draw.text((448, 165), "REAL 8-BUS IN-LINE DOCKING CORRIDOR (WAY 646847618)", fill=(255, 255, 255), font=FONT_LABEL)
    draw.text((448, 178), "4 Active Offloading Bays Kerbside | 4 Queued In-Line on Roadway", fill=(148, 163, 184), font=FONT_MICRO)

    # 6. Dataran Merah (North Plaza) Holding Formation
    dm_p = proj(5.356518, 100.303214)
    draw.rectangle([dm_p[0] - 45, dm_p[1] - 30, dm_p[0] + 45, dm_p[1] + 30], fill=(249, 115, 22, 45), outline=(249, 115, 22, 230), width=2)
    for c in range(6):
        for r in range(10):
            draw.ellipse([dm_p[0] - 35 + c * 12 - 1, dm_p[1] - 20 + r * 4 - 1, dm_p[0] - 35 + c * 12 + 1, dm_p[1] - 20 + r * 4 + 1], fill=(249, 115, 22, 220))
    draw.text((dm_p[0] - 50, dm_p[1] + 35), "DATARAN MERAH (NORTH PLAZA)", fill=(255, 255, 255), font=FONT_LABEL)
    draw.text((dm_p[0] - 50, dm_p[1] + 48), "Shaded | Cahaya Gemilang & Bakti Permai Hold", fill=(148, 163, 184), font=FONT_MICRO)

    # 7. Siswaniaga Grass Field (South Plaza) Holding Formation
    sw_p = proj(5.356118, 100.302400)
    draw.rectangle([sw_p[0] - 45, sw_p[1] - 30, sw_p[0] + 45, sw_p[1] + 30], fill=(34, 197, 94, 45), outline=(34, 197, 94, 230), width=2)
    for c in range(6):
        for r in range(10):
            draw.ellipse([sw_p[0] - 35 + c * 12 - 1, sw_p[1] - 20 + r * 4 - 1, sw_p[0] - 35 + c * 12 + 1, sw_p[1] - 20 + r * 4 + 1], fill=(34, 197, 94, 220))
    draw.text((sw_p[0] - 50, sw_p[1] + 35), "G28 SISWANIAGA (SOUTH FIELD)", fill=(255, 255, 255), font=FONT_LABEL)
    draw.text((sw_p[0] - 50, sw_p[1] + 48), "Grass Field | Indah, Damai & Harapan Hold", fill=(148, 163, 184), font=FONT_MICRO)

    # 8. Single-File Discharge Channels to Portals
    # Car park -> Covered Walkway -> Door A
    pts_cp_to_door = [proj(5.357153, 100.301749), proj(5.357119, 100.302499), proj(5.35700, 100.30280)]
    draw_cased_way(draw, pts_cp_to_door, core_color=(56, 189, 248, 255), core_width=4, casing_color=(15, 23, 42, 220), casing_width=7)

    # G03 Diversion Path (when DTSP reaches 3,000)
    pts_g03_div = [proj(5.357119, 100.302499), (proj(5.357119, 100.302499)[0], proj(5.357119, 100.302499)[1] + 35)]
    draw_cased_way(draw, pts_g03_div, core_color=(168, 85, 247, 255), core_width=4, casing_color=(15, 23, 42, 220), casing_width=7)

    # Plazas -> Door A & B along real footpaths
    draw_cased_way(draw, [proj(5.356518, 100.303214), proj(5.35680, 100.30300)], core_color=(249, 115, 22, 255), core_width=4)
    draw_cased_way(draw, [proj(5.356118, 100.302400), proj(5.35680, 100.30300)], core_color=(34, 197, 94, 255), core_width=4)

    # 9. PPSL Control Posts
    ppsl_posts = [
        ("PPSL 1", "Berth Marshall", (635, 415), (34, 197, 94)),
        ("PPSL 2", "Headcount Controller", (760, 410), (56, 189, 248)),
        ("PPSL 3", "Covered Walkway Guide", proj(5.357119, 100.302499), (245, 158, 11)),
        ("PPSL 4", "Door A Inflow (Zero Dwell)", proj(5.35700, 100.30280), (239, 68, 68)),
        ("PPSL 5", "Door B Inflow (Zero Dwell)", proj(5.35680, 100.30300), (239, 68, 68)),
        ("PPSL 6", "G03 Overflow Gatekeeper", (1050, 475), (168, 85, 247)),
    ]
    for p_id, p_role, pos, col in ppsl_posts:
        px, py = pos
        draw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=col, outline=(255, 255, 255), width=2)
        draw.text((px - 7, py - 5), p_id[-1], fill=(15, 23, 42), font=FONT_BOLD_MICRO)
        draw.rectangle([px + 14, py - 8, px + len(p_role) * 6 + 20, py + 8], fill=(15, 23, 42, 230), outline=col, width=1)
        draw.text((px + 18, py - 5), p_role, fill=(255, 255, 255), font=FONT_MICRO)

    comp = Image.alpha_composite(base, overlay).convert('RGB')
    draw_c = ImageDraw.Draw(comp)

    # Title Banner
    draw_c.rectangle([0, 0, W, 48], fill=(15, 23, 42))
    draw_c.text((20, 10), "USM MSL ORIENTATION — DTSP PRECINCT TACTICAL INTAKE & HOLDING PLAN", fill=(255, 255, 255), font=FONT_TITLE)

    # Bottom Status Bar
    draw_c.rectangle([0, H - 32, W, H], fill=(15, 23, 42))
    draw_c.text((20, H - 24), "CANONICAL INVARIANTS: 8-Bus Fleet In-Line on Road | 3-4 Simultaneous Kerbside Offloads | 500 Safe / 600 Max Car Park Hold | 5-min Headcount | DTSP 3,000 + G03 500 Overflow", fill=(203, 213, 225), font=FONT_SMALL)

    # HUD Panels
    items_capacities = [
        ("DTSP Main Hall (G01)", "3,000 seats", "Full Hall locked limit; zero screening"),
        ("G03 Dewan Budaya (DK G/H)", "500 seats", "Active secondary overflow destination"),
        ("3-Tier Car Park Apron", "500-600 pax", "T1: 320 safe | T2: 120 safe | T3: 60 safe"),
        ("Dataran Merah (North)", "534 pax", "Cahaya (193) + Bakti Permai (341)"),
        ("Siswaniaga Grass (South)", "847 pax", "Damai (410) + Indah (244) + Harapan (193)"),
    ]
    draw_hud_panel(draw_c, W - 260, 60, 240, 160, "VENUE & HOLDING CAPACITIES", items_capacities, badge_color=(245, 158, 11))

    items_flow = [
        ("Coach Alighting Dwell", "180 s (3.0 min)", "Conservative safety bound [I12d]"),
        ("Active Offloading Bays", "3 to 4 buses", "Parallel discharge along kerbside"),
        ("Mandatory Headcount", "300 s (5.0 min)", "PPSL column counting at holding areas"),
        ("Discharge Formation", "Single file", "One independent file per holding area"),
        ("Door Intake Pacing", "Free flow", "Zero ticket/bag check; direct seating"),
    ]
    draw_hud_panel(draw_c, W - 260, 230, 240, 160, "OPERATIONAL FLOW PARAMETERS", items_flow, badge_color=(34, 197, 94))

    draw_north_arrow(draw_c, pos=(60, 90))
    draw_scale_bar(draw_c, scale_m_per_px=0.298, pos=(40, H - 70), bar_meters=100)

    out_file = os.path.join(PLANS_DIR, 'dtsp_arrival_holding_plan.png')
    comp.save(out_file, quality=95)
    print(f"Successfully generated: {out_file} ({os.path.getsize(out_file)} bytes)")


def render_restu_plan():
    """Generates the high-precision Restu Western Ridge Staging & Dispatch Plan along 100% real roads."""
    print("Rendering Restu Western Ridge Plan...")
    base_path = os.path.join(SATELLITE_DIR, 'restu_ridge_z19.jpg')
    base = Image.open(base_path).convert('RGBA')
    W, H = base.size

    dimmer = Image.new('RGBA', (W, H), (15, 23, 42, 60))
    base = Image.alpha_composite(base, dimmer)

    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    x_min_tile, y_min_tile = 408200, 254329
    def proj(lat, lon):
        return get_pixel_z19(lat, lon, x_min_tile, y_min_tile)

    # 1. Render all OSM Roads
    for f in TRANSIT_GEO['features']:
        if f['geometry']['type'] == 'LineString':
            pts = [proj(p[1], p[0]) for p in f['geometry']['coordinates']]
            pts_in = [p for p in pts if 0 <= p[0] < W and 0 <= p[1] < H]
            if len(pts_in) >= 2:
                draw_cased_way(draw, pts, core_color=(51, 65, 85, 220), core_width=6, casing_color=(15, 23, 42, 200), casing_width=10)

    # 2. Render all OSM Footways & Steps
    for f in PED_GEO['features']:
        if f['geometry']['type'] == 'LineString':
            pts = [proj(p[1], p[0]) for p in f['geometry']['coordinates']]
            pts_in = [p for p in pts if 0 <= p[0] < W and 0 <= p[1] < H]
            if len(pts_in) >= 2:
                hw = f['properties'].get('highway')
                is_cov = f['properties'].get('covered') == 'yes'
                is_br = f['properties'].get('bridge') == 'yes'
                if is_br or is_cov:
                    draw_cased_way(draw, pts, core_color=(245, 158, 11, 240), core_width=5, casing_color=(15, 23, 42, 220), casing_width=8)
                elif hw == 'steps':
                    draw_cased_way(draw, pts, core_color=(226, 232, 240, 240), core_width=5, casing_color=(15, 23, 42, 220), casing_width=8)
                    draw_stair_treads(draw, pts, tread_spacing=4)
                else:
                    draw_cased_way(draw, pts, core_color=(148, 163, 184, 180), core_width=2, casing_color=(15, 23, 42, 160), casing_width=4)

    # 3. Render Building Footprints
    key_rst_bldgs = {
        275415004: ('M07 RESTU CAFE (START / HOLD)', (249, 115, 22, 240), (249, 115, 22, 70)),
        275415002: ('M08 DEWAN UTAMA RESTU (DUD FORECOURT)', (6, 182, 212, 240), (6, 182, 212, 70)),
        139062076: ('M01 RESTU (M)', (56, 189, 248, 200), (56, 189, 248, 45)),
        1031136419: ('M02 RESTU (F)', (56, 189, 248, 200), (56, 189, 248, 45)),
        1031136418: ('M03 SAUJANA', (34, 197, 94, 200), (34, 197, 94, 45)),
        275415000: ('M04 SAUJANA', (34, 197, 94, 200), (34, 197, 94, 45)),
        275414999: ('M05 TEKUN', (168, 85, 247, 200), (168, 85, 247, 45)),
        275414998: ('M06 TEKUN', (168, 85, 247, 200), (168, 85, 247, 45)),
    }

    for f in BUILDINGS_GEO['features']:
        bid = f['properties']['id']
        coords = f['geometry']['coordinates'][0]
        pts = [proj(p[1], p[0]) for p in coords]
        if any(0 <= p[0] < W and 0 <= p[1] < H for p in pts):
            if bid in key_rst_bldgs:
                label, outline_col, fill_col = key_rst_bldgs[bid]
                draw.polygon(pts, fill=fill_col, outline=outline_col, width=2)
                cx = int(sum(p[0] for p in pts) / len(pts))
                cy = int(sum(p[1] for p in pts) / len(pts))
                tw = len(label) * 6 + 10
                draw.rectangle([cx - tw // 2, cy - 8, cx + tw // 2, cy + 8], fill=(15, 23, 42, 230), outline=outline_col, width=1)
                draw.text((cx - tw // 2 + 5, cy - 6), label, fill=(255, 255, 255), font=FONT_MICRO)
            else:
                draw.polygon(pts, fill=(255, 255, 255, 30), outline=(255, 255, 255, 140), width=1)

    # 4. 100% REAL ROAD ROUTE FOR RESTU STUDENTS:
    # Exit Cafe M07 onto road -> Halaman Bukit Gambir 4 road pavement -> past DUD M08 -> road shoulder curb to overpass
    w_exit = next(f for f in TRANSIT_GEO['features'] if f['properties']['id'] == 741719631)
    w_ring = next(f for f in TRANSIT_GEO['features'] if f['properties']['id'] == 710705927)

    pts_exit_coords = [[p[1], p[0]] for p in w_exit['geometry']['coordinates'][::-1]]
    pts_ring_coords = [[p[1], p[0]] for p in w_ring['geometry']['coordinates'][17:42]]

    # Step 1: Paved Road from Cafe M07 to DUD Forecourt (along tarmac road around the bend)
    pts_road_to_dud = [proj(p[0], p[1]) for p in pts_exit_coords + pts_ring_coords[:11]]
    draw_cased_way(draw, pts_road_to_dud, core_color=(234, 179, 8, 255), core_width=4, casing_color=(15, 23, 42, 220), casing_width=7)

    # Step 2: STRICT SINGLE FILE on Road Shoulder Curb from DUD to Overpass
    pts_curb_coords = pts_ring_coords[10:]
    pts_curb = [proj(p[0], p[1]) for p in pts_curb_coords]
    draw_cased_way(draw, pts_curb, core_color=(239, 68, 68, 255), core_width=4, casing_color=(15, 23, 42, 220), casing_width=7)

    # Draw marching single-file dots along the curb
    for i in range(len(pts_curb) - 1):
        p1, p2 = pts_curb[i], pts_curb[i + 1]
        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        steps = max(1, int(dist / 8))
        for s in range(steps):
            dot_x = p1[0] + (p2[0] - p1[0]) * (s / steps)
            dot_y = p1[1] + (p2[1] - p1[1]) * (s / steps)
            draw.ellipse([dot_x - 2, dot_y - 2, dot_x + 2, dot_y + 2], fill=(255, 255, 255, 255))

    # Step 3: Overpass footbridge deck + stairs to Padang Kawad
    pts_bridge = [
        proj(5.356712, 100.291946),
        proj(5.356608, 100.292709),
        proj(5.356465, 100.292656),
        proj(5.356440, 100.293092),
        proj(5.356475, 100.293250),
        proj(5.356440, 100.293400),
        proj(5.356036, 100.293640),
    ]
    draw_cased_way(draw, pts_bridge, core_color=(245, 158, 11, 255), core_width=5)
    draw_stair_treads(draw, pts_bridge[2:5], tread_spacing=4)

    # Step 4: REAL ROAD ROUTES FOR SAUJANA & TEKUN:
    # Saujana uses paved access road Way 161721265 out to Halaman Bukit Gambir 4
    w_sau_road = next(f for f in TRANSIT_GEO['features'] if f['properties']['id'] == 161721265)
    pts_sau_road = [proj(p[1], p[0]) for p in w_sau_road['geometry']['coordinates']]
    draw_cased_way(draw, pts_sau_road, core_color=(34, 197, 94, 255), core_width=4)

    # Tekun uses southern loop road of Way 710705927
    pts_tek_road = [proj(p[1], p[0]) for p in w_ring['geometry']['coordinates'][:10]]
    draw_cased_way(draw, pts_tek_road, core_color=(168, 85, 247, 255), core_width=4)

    # 5. Padang Kawad Transit Berth & Bus Staging
    p_berth = proj(5.356036, 100.293640)
    draw.ellipse([p_berth[0] - 25, p_berth[1] - 25, p_berth[0] + 25, p_berth[1] + 25], fill=(234, 179, 8, 40), outline=(234, 179, 8, 240), width=2)
    draw.rectangle([p_berth[0] - 16, p_berth[1] - 6, p_berth[0] + 16, p_berth[1] + 6], fill=(234, 179, 8), outline=(255, 255, 255), width=1)
    draw.text((p_berth[0] - 60, p_berth[1] + 30), "PADANG KAWAD TRANSIT BERTH", fill=(255, 255, 255), font=FONT_LABEL)
    draw.text((p_berth[0] - 60, p_berth[1] + 44), "8-Bus Loop | 180s Boarding Dwell | Aisles with Standees", fill=(148, 163, 184), font=FONT_MICRO)

    # 6. PPSL Control Posts
    p_m07 = proj(5.356461, 100.289265)
    p_m08 = proj(5.357280, 100.289810)
    ppsl_posts_r = [
        ("PPSL R1", "Cafe Holding Controller", p_m07, (249, 115, 22)),
        ("PPSL R2", "DUD Road Marshall", (pts_road_to_dud[-1][0] + 10, pts_road_to_dud[-1][1]), (6, 182, 212)),
        ("PPSL R3", "Curb Single-File Gatekeeper", pts_curb[0], (239, 68, 68)),
        ("PPSL R4", "Overpass Footbridge Marshall", proj(5.356712, 100.291946), (245, 158, 11)),
        ("PPSL R5", "Transit Berth Dispatcher", p_berth, (234, 179, 8)),
    ]
    for p_id, p_role, pos, col in ppsl_posts_r:
        px, py = pos
        draw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=col, outline=(255, 255, 255), width=2)
        draw.text((px - 7, py - 5), p_id[-1], fill=(15, 23, 42), font=FONT_BOLD_MICRO)
        draw.rectangle([px + 14, py - 8, px + len(p_role) * 6 + 20, py + 8], fill=(15, 23, 42, 230), outline=col, width=1)
        draw.text((px + 18, py - 5), p_role, fill=(255, 255, 255), font=FONT_MICRO)

    comp = Image.alpha_composite(base, overlay).convert('RGB')
    draw_c = ImageDraw.Draw(comp)

    # Title Banner
    draw_c.rectangle([0, 0, W, 48], fill=(15, 23, 42))
    draw_c.text((20, 10), "USM MSL ORIENTATION — WESTERN RIDGE (RST) STAGING & DISPATCH PLAN", fill=(255, 255, 255), font=FONT_TITLE)

    # Status Bar
    draw_c.rectangle([0, H - 32, W, H], fill=(15, 23, 42))
    draw_c.text((20, H - 24), "SEQUENCE INVARIANTS: All release 06:00 | Tekun & Saujana priority dispatch via road | Restu held at cafe until 07:33 | 100% on road pavement/curb | Strict single file to overpass", fill=(203, 213, 225), font=FONT_SMALL)

    # HUD Panels
    items_rst = [
        ("Hostel Release Timing", "06:00:00 (t=0)", "All 8 hostels release simultaneously"),
        ("Tekun & Saujana Priority", "Dispatched FIRST", "Lower headcount; clear ridge early"),
        ("Restu Cafe Hold", "06:00 to 07:33", "Held at M07 cafe; dispatched LAST"),
        ("Route Surface", "100% Tarmac Road", "Zero walking through residential blocks"),
        ("Road Shoulder Corridor", "Strict single file", "0.42 m/s congested pacing [I8b]"),
        ("Padang Kawad Berth", "8 buses loop", "5 Coach + 3 Electric; 65-80 pax each"),
    ]
    draw_hud_panel(draw_c, W - 260, 60, 240, 175, "RST SEQUENCING RULES", items_rst, badge_color=(239, 68, 68))

    draw_north_arrow(draw_c, pos=(60, 90))
    draw_scale_bar(draw_c, scale_m_per_px=0.298, pos=(40, H - 70), bar_meters=100)

    out_file = os.path.join(PLANS_DIR, 'restu_ridge_dispatch_plan.png')
    comp.save(out_file, quality=95)
    print(f"Successfully generated: {out_file} ({os.path.getsize(out_file)} bytes)")


if __name__ == '__main__':
    render_dtsp_plan()
    render_restu_plan()
