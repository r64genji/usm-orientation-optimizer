import { useEffect, useRef } from "react";
import { useMap } from "react-leaflet";
import type { ReplayPayload, StudentTrajectory } from "../types";

type Props = {
  replay: ReplayPayload | null;
  currentTimeMs: number;
  selectedHostel: string | null;
  selectedPlace: string | null;
};
const HOSTEL_COLORS: Record<string, string> = {
  restu: "#8B5CF6",
  saujana: "#0EA5E9",
  tekun: "#F59E0B",
  indah_kembara: "#10B981",
  aman_damai: "#EF4444",
  bakti_fajar_permai: "#06B6D4",
  cahaya_gemilang: "#D97706",
  fajar_harapan: "#EC4899",
};


type PolylinePoint = {
  pos: [number, number];
  fwd: [number, number];
  norm: [number, number];
};

const distsCache = new WeakMap<[number, number][], { dists: number[]; totalDist: number }>();

function getPolylineDists(waypoints: [number, number][]): { dists: number[]; totalDist: number } {
  const cached = distsCache.get(waypoints);
  if (cached) return cached;

  let totalDist = 0;
  const dists: number[] = [0];
  for (let i = 0; i < waypoints.length - 1; i++) {
    const dLat = waypoints[i + 1][0] - waypoints[i][0];
    const dLon = waypoints[i + 1][1] - waypoints[i][1];
    totalDist += Math.hypot(dLat, dLon);
    dists.push(totalDist);
  }
  const entry = { dists, totalDist };
  distsCache.set(waypoints, entry);
  return entry;
}

function getPolylinePoint(
  waypoints: [number, number][],
  targetDist: number,
  dists: number[],
  totalDist: number
): PolylinePoint {
  if (!waypoints || waypoints.length === 0) {
    return { pos: [5.3568, 100.297], fwd: [1, 0], norm: [0, 1] };
  }
  if (waypoints.length === 1 || targetDist <= 0 || totalDist === 0) {
    const next = waypoints[1] || [waypoints[0][0] + 0.0001, waypoints[0][1]];
    const dLat = next[0] - waypoints[0][0];
    const dLon = next[1] - waypoints[0][1];
    const len = Math.hypot(dLat, dLon) || 1;
    return {
      pos: waypoints[0],
      fwd: [dLat / len, dLon / len],
      norm: [-dLon / len, dLat / len],
    };
  }
  if (targetDist >= totalDist) {
    const prev = waypoints[waypoints.length - 2] || waypoints[waypoints.length - 1];
    const last = waypoints[waypoints.length - 1];
    const dLat = last[0] - prev[0];
    const dLon = last[1] - prev[1];
    const len = Math.hypot(dLat, dLon) || 1;
    return {
      pos: last,
      fwd: [dLat / len, dLon / len],
      norm: [-dLon / len, dLat / len],
    };
  }

  for (let i = 0; i < dists.length - 1; i++) {
    if (targetDist <= dists[i + 1]) {
      const segDist = dists[i + 1] - dists[i];
      const segT = segDist === 0 ? 0 : (targetDist - dists[i]) / segDist;
      const lat = waypoints[i][0] + segT * (waypoints[i + 1][0] - waypoints[i][0]);
      const lon = waypoints[i][1] + segT * (waypoints[i + 1][1] - waypoints[i][1]);
      const dLat = waypoints[i + 1][0] - waypoints[i][0];
      const dLon = waypoints[i + 1][1] - waypoints[i][1];
      const len = Math.hypot(dLat, dLon) || 1;
      return {
        pos: [lat, lon],
        fwd: [dLat / len, dLon / len],
        norm: [-dLon / len, dLat / len],
      };
    }
  }

  const last = waypoints[waypoints.length - 1];
  return { pos: last, fwd: [1, 0], norm: [0, 1] };
}

// Deterministic 2D spread for waiting crowds at distinct holding locations
function getWaitOffset(studentIdx: number, placeId: string): [number, number] {
  if (placeId === "restu_origin" || placeId === "rst_rain_shelter") {
    // Restu Cafe grounds / rain shelter (M07) pavilion: sheltered cafe area
    const radius = 0.00022 * Math.sqrt((studentIdx + 1) / 750);
    const angle = studentIdx * 2.3999632;
    return [radius * Math.cos(angle) * 0.85, radius * Math.sin(angle) * 1.25];
  }

  if (placeId.endsWith("_origin")) {
    // Natural courtyard/grounds spread at hostel blocks (fills from center outward)
    const radius = 0.00030 * Math.sqrt((studentIdx + 1) / 1050);
    const angle = studentIdx * 2.3999632; // Golden ratio angle
    return [radius * Math.cos(angle), radius * Math.sin(angle) * 1.15];
  }

  if (placeId === "rst_bus_wait") {
    // Persiaran Sains road shoulder waiting queue: linear queue along road verge
    const file = (studentIdx % 2 === 0 ? -1 : 1) * 0.000012;
    const rank = Math.floor(studentIdx / 2);
    return [-rank * 0.0000065 + file * 0.7, rank * 0.0000065 + file * 0.7];
  }

  if (placeId === "rst_boarding_approach") {
    // Persiaran Sains boarding berth approach: queue into active bus berths
    const file = (studentIdx % 2 === 0 ? -1 : 1) * 0.000008;
    const rank = Math.floor(studentIdx / 2);
    return [-rank * 0.000005 + file, rank * 0.000005 + file];
  }

  if (placeId === "dtsp_exterior_gathering") {
    // 3-tier car park waiting area at DTSP: realistic terraced 3 tiers
    const tier = studentIdx % 3; // 0: Lower, 1: Middle, 2: Upper tier
    const rankInTier = Math.floor(studentIdx / 3);
    const col = (rankInTier % 16) - 8;
    const row = Math.floor(rankInTier / 16);
    // Stepped terrace elevation
    const tierLatOffset = (tier - 1) * 0.000085;
    const tierLonOffset = (tier - 1) * 0.000065;
    const dLat = tierLatOffset + row * 0.000011 + (col * 0.000005);
    const dLon = tierLonOffset + col * 0.000013 - (row * 0.000004);
    return [dLat, dLon];
  }

  if (placeId === "dtsp_north_plaza") {
    // Dataran Merah (Shaded Pavilion) waiting spread: covered pavilion layout
    const col = (studentIdx % 20) - 10;
    const row = Math.floor(studentIdx / 20);
    return [row * 0.000010 + (col * 0.000003), col * 0.000012 - (row * 0.000003)];
  }

  if (placeId === "dtsp_south_plaza") {
    // Grass Field in front of G28 Siswaniaga: open lawn dispersion
    const radius = 0.00022 * Math.sqrt((studentIdx + 1) / 700);
    const angle = studentIdx * 2.3999632;
    return [radius * Math.cos(angle) * 1.1, radius * Math.sin(angle) * 1.3];
  }

  if (placeId === "dtsp_door_a" || placeId === "dtsp_door_b") {
    // Door intake queue (Door A North / Bus, Door B South / Walk)
    const file = (studentIdx % 2 === 0 ? -1 : 1) * 0.000007;
    const rank = Math.floor(studentIdx / 2);
    return [-rank * 0.000005 + file, rank * 0.000005 + file];
  }

  if (placeId === "dtsp_foyer") {
    // DTSP Foyer Lobby
    const radius = 0.00010 * Math.sqrt((studentIdx + 1) / 200);
    const angle = studentIdx * 2.3999632;
    return [radius * Math.cos(angle), radius * Math.sin(angle)];
  }

  if (placeId === "dtsp_seating") {
    // DTSP main hall auditorium seating (3000 seats): structured tiered curved rows
    const seatsPerRow = 50;
    const col = (studentIdx % seatsPerRow) - (seatsPerRow / 2);
    const row = Math.floor(studentIdx / seatsPerRow);
    const curve = Math.cos((col / seatsPerRow) * Math.PI) * 0.000015;
    return [col * 0.0000045, (row / 60) * 0.00028 - curve];
  }

  if (placeId === "g03_seating") {
    // Bangunan G03 lecture hall (DK G/H) overflow seating: 600 seats
    const seatsPerRow = 24;
    const col = (studentIdx % seatsPerRow) - (seatsPerRow / 2);
    const row = Math.floor(studentIdx / seatsPerRow);
    return [col * 0.0000055, (row / 25) * 0.00022];
  }

  // Default plaza or shelter spread
  const radius = 0.00014 * Math.sqrt((studentIdx + 1) / 400);
  const angle = studentIdx * 2.3999632;
  return [radius * Math.cos(angle), radius * Math.sin(angle) * 1.15];
}

export default function ReplayCanvas({
  replay,
  currentTimeMs,
  selectedHostel,
  selectedPlace,
}: Props) {
  const map = useMap();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Clean up canvas on component unmount
  useEffect(() => {
    return () => {
      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext("2d");
        if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const render = () => {
      const size = map.getSize();
      if (!size || size.x === 0 || size.y === 0) return;

      const dpr = window.devicePixelRatio || 1;
      const targetW = Math.round(size.x * dpr);
      const targetH = Math.round(size.y * dpr);

      if (canvas.width !== targetW || canvas.height !== targetH) {
        canvas.width = targetW;
        canvas.height = targetH;
        canvas.style.width = `${size.x}px`;
        canvas.style.height = `${size.y}px`;
      }

      if (!replay || !replay.has_trace) {
        ctx.clearRect(0, 0, targetW, targetH);
        return;
      }

      ctx.save();
      try {
        ctx.scale(dpr, dpr);
        ctx.clearRect(0, 0, size.x, size.y);

        const trajectories: StudentTrajectory[] = replay.student_trajectories || [];

        // Pre-gather bus trips and student dots for batch drawing
        type StudentDot = {
          x: number;
          y: number;
          color: string;
          radius: number;
          alpha: number;
        };

        const dots: StudentDot[] = [];
        type DrawnBus = {
          id: string;
          vehicle_type: "coach" | "electric";
          capacity: number;
          x: number;
          y: number;
          angle: number;
          status: string;
          pax: number;
        };
        const busesToDraw: DrawnBus[] = [];

        // Gather all active buses from replay.bus_trajectories
        if (replay.bus_trajectories && replay.bus_trajectories.length > 0) {
          let dtspDockCount = 0;
          let rstDockCount = 0;

          for (let bIdx = 0; bIdx < replay.bus_trajectories.length; bIdx++) {
            const b = replay.bus_trajectories[bIdx];
            let activeSeg = null;
            for (let sIdx = 0; sIdx < b.segments.length; sIdx++) {
              const seg = b.segments[sIdx];
              if (currentTimeMs >= seg.start_ms && currentTimeMs <= seg.end_ms) {
                activeSeg = seg;
                break;
              }
            }
            if (!activeSeg && b.segments.length > 0) {
              activeSeg = currentTimeMs < b.segments[0].start_ms ? b.segments[0] : b.segments[b.segments.length - 1];
            }
            if (!activeSeg) continue;

            const isTransit = activeSeg.type === "transit_loaded" || activeSeg.type === "transit_empty_return";
            if (isTransit && activeSeg.waypoints.length > 1) {
              const waypoints = activeSeg.waypoints as [number, number][];
              const { dists, totalDist } = getPolylineDists(waypoints);
              const span = Math.max(1, activeSeg.end_ms - activeSeg.start_ms);
              const progress = Math.min(1, Math.max(0, (currentTimeMs - activeSeg.start_ms) / span));
              const busPt = getPolylinePoint(waypoints, progress * totalDist, dists, totalDist);
              const screenCenter = map.latLngToContainerPoint(busPt.pos);
              const aheadPos: [number, number] = [
                busPt.pos[0] + busPt.fwd[0] * 0.0001,
                busPt.pos[1] + busPt.fwd[1] * 0.0001,
              ];
              const screenAhead = map.latLngToContainerPoint(aheadPos);
              const angle = Math.atan2(screenAhead.y - screenCenter.y, screenAhead.x - screenCenter.x);

              if (screenCenter.x >= -60 && screenCenter.x <= size.x + 60 && screenCenter.y >= -60 && screenCenter.y <= size.y + 60) {
                busesToDraw.push({
                  id: b.id,
                  vehicle_type: b.vehicle_type,
                  capacity: b.capacity,
                  x: screenCenter.x,
                  y: screenCenter.y,
                  angle,
                  status: activeSeg.type,
                  pax: activeSeg.passenger_count || 0,
                });
              }
            } else if (activeSeg.place_id === "dtsp_alighting_area" || activeSeg.type === "alighting") {
              // Docked at DTSP drop-off straight road / car park (up to 8 buses, 4 active berths)
              const berthIdx = dtspDockCount++;
              const baseCoords: [number, number] = [5.357215, 100.301437];
              const berthLat = baseCoords[0] + (berthIdx - 1.5) * 0.00012;
              const berthLon = baseCoords[1] + (berthIdx - 1.5) * 0.00008;
              const screenPt = map.latLngToContainerPoint([berthLat, berthLon]);
              if (screenPt.x >= -60 && screenPt.x <= size.x + 60 && screenPt.y >= -60 && screenPt.y <= size.y + 60) {
                busesToDraw.push({
                  id: b.id,
                  vehicle_type: b.vehicle_type,
                  capacity: b.capacity,
                  x: screenPt.x,
                  y: screenPt.y,
                  angle: Math.PI * 0.38,
                  status: activeSeg.type,
                  pax: activeSeg.passenger_count || 0,
                });
              }
            } else {
              // At RST boarding berths / staging (boarding, turnaround, or idle)
              const berthIdx = rstDockCount++;
              const baseCoords: [number, number] = [5.356012, 100.293748];
              const slotCol = berthIdx % 4;
              const slotRow = Math.floor(berthIdx / 4);
              const berthLat = baseCoords[0] + slotRow * 0.00007;
              const berthLon = baseCoords[1] + (slotCol - 1.5) * 0.00013;
              const screenPt = map.latLngToContainerPoint([berthLat, berthLon]);
              if (screenPt.x >= -60 && screenPt.x <= size.x + 60 && screenPt.y >= -60 && screenPt.y <= size.y + 60) {
                busesToDraw.push({
                  id: b.id,
                  vehicle_type: b.vehicle_type,
                  capacity: b.capacity,
                  x: screenPt.x,
                  y: screenPt.y,
                  angle: 0.1,
                  status: activeSeg.type,
                  pax: activeSeg.passenger_count || 0,
                });
              }
            }
          }
        }
        // Precompute hostel-local group indices so students waiting at their hostel origin
        // distribute compactly from the courtyard center (radius 0) outward.
        const hostelGroupIndices: number[] = new Array(trajectories.length);
        const hostelCounters: Record<string, number> = {};
        for (let tIdx = 0; tIdx < trajectories.length; tIdx++) {
          const hid = trajectories[tIdx].hostel_id || "unknown";
          hostelGroupIndices[tIdx] = hostelCounters[hid] || 0;
          hostelCounters[hid] = (hostelCounters[hid] || 0) + 1;
        }

        // Active queue counters for transient waiting places in this frame
        const placeQueueCounters = new Map<string, number>();

        for (let tIdx = 0; tIdx < trajectories.length; tIdx++) {
          const traj = trajectories[tIdx];
          const isHostelMatch = !selectedHostel || traj.hostel_id === selectedHostel;
          const count = traj.student_count || 20;
          const color = (traj.hostel_id && HOSTEL_COLORS[traj.hostel_id]) || traj.color || "#3B82F6";
          // Find active segment
          let activeSeg = null;
          for (let sIdx = 0; sIdx < traj.segments.length; sIdx++) {
            const seg = traj.segments[sIdx];
            if (currentTimeMs >= seg.start_ms && currentTimeMs <= seg.end_ms) {
              activeSeg = seg;
              break;
            }
          }

          if (!activeSeg && traj.segments.length > 0) {
            if (currentTimeMs < traj.segments[0].start_ms) {
              activeSeg = traj.segments[0];
            } else {
              activeSeg = traj.segments[traj.segments.length - 1];
            }
          }

          if (!activeSeg) continue;

          const isPlaceMatch = !selectedPlace || activeSeg.place_id === selectedPlace;
          const isHighlighted = isHostelMatch && isPlaceMatch;

          const alpha = isHighlighted ? (selectedHostel || selectedPlace ? 1.0 : 0.88) : 0.15;
          const dotRadius = isHighlighted ? 2.6 : 1.8;

          if (activeSeg.type === "wait") {
            const center = activeSeg.waypoints[0] || [5.3568, 100.297];
            const placeId = activeSeg.place_id || "unknown";

            let baseIdx = 0;
            if (placeId.endsWith("_origin")) {
              baseIdx = (hostelGroupIndices[tIdx] || 0) * 20;
            } else if (placeId === "dtsp_seating") {
              baseIdx = tIdx * 20;
            } else if (placeId === "g03_seating") {
              baseIdx = placeQueueCounters.get(placeId) || 0;
              placeQueueCounters.set(placeId, baseIdx + count);
            } else {
              baseIdx = placeQueueCounters.get(placeId) || 0;
              placeQueueCounters.set(placeId, baseIdx + count);
            }

            for (let i = 0; i < count; i++) {
              const studentIdx = baseIdx + i;
              const [dLat, dLon] = getWaitOffset(studentIdx, placeId);
              const lat = center[0] + dLat;
              const lon = center[1] + dLon;
              const pt = map.latLngToContainerPoint([lat, lon]);

              if (pt.x >= -10 && pt.x <= size.x + 10 && pt.y >= -10 && pt.y <= size.y + 10) {
                dots.push({ x: pt.x, y: pt.y, color, radius: dotRadius, alpha });
              }
            }
          } else {
            // Transit segment
            const waypoints = activeSeg.waypoints as [number, number][];
            const { dists, totalDist } = getPolylineDists(waypoints);
            const span = Math.max(1, activeSeg.end_ms - activeSeg.start_ms);
            const baseProgress = Math.min(1, Math.max(0, (currentTimeMs - activeSeg.start_ms) / span));
            const isBus = activeSeg.leg_id === "leg_transit";

            if (isBus) {
              // Coach Bus Transit: Students move together inside the bus footprint
              const centerDist = baseProgress * totalDist;
              const busPt = getPolylinePoint(waypoints, centerDist, dists, totalDist);
              const screenCenter = map.latLngToContainerPoint(busPt.pos);
              // Use normalized forward vector to compute screen heading reliably even at polyline end
              const aheadPos: [number, number] = [
                busPt.pos[0] + busPt.fwd[0] * 0.0001,
                busPt.pos[1] + busPt.fwd[1] * 0.0001,
              ];
              const screenAhead = map.latLngToContainerPoint(aheadPos);
              const angle = Math.atan2(screenAhead.y - screenCenter.y, screenAhead.x - screenCenter.x);

              if (
                screenCenter.x >= -30 &&
                screenCenter.x <= size.x + 30 &&
                screenCenter.y >= -30 &&
                screenCenter.y <= size.y + 30
              ) {
                if ((!replay.bus_trajectories || replay.bus_trajectories.length === 0) && !busesToDraw.some((b) => Math.hypot(b.x - screenCenter.x, b.y - screenCenter.y) < 6)) {
                  busesToDraw.push({
                    id: "bus_fallback",
                    vehicle_type: "coach",
                    capacity: 80,
                    x: screenCenter.x,
                    y: screenCenter.y,
                    angle,
                    status: "transit_loaded",
                    pax: count,
                  });
                }

                // Passenger seating layout inside the bus
                const cosA = Math.cos(angle);
                const sinA = Math.sin(angle);

                for (let i = 0; i < count; i++) {
                  const seatRow = Math.floor(i / 4) - 2;
                  const seatCol = (i % 4) - 1.5;
                  const dx = seatRow * 4.2;
                  const dy = seatCol * 2.4;

                  const px = screenCenter.x + (dx * cosA - dy * sinA);
                  const py = screenCenter.y + (dx * sinA + dy * cosA);

                  dots.push({ x: px, y: py, color, radius: dotRadius * 0.9, alpha });
                }
              }
            } else {
              // Walking Contingent: Students move in double-file column along the path
              const centerDist = baseProgress * totalDist;
              const numRanks = Math.ceil(count / 2);

              for (let i = 0; i < count; i++) {
                const rank = Math.floor(i / 2);
                const file = i % 2 === 0 ? -1 : 1;

                // Longitudinal headway between ranks (~1.5m)
                const headwayDist = (rank - numRanks / 2) * 0.000014;
                const studentDist = Math.max(0, Math.min(totalDist, centerDist - headwayDist));

                const pt = getPolylinePoint(waypoints, studentDist, dists, totalDist);

                // Lateral offset (~0.9m file separation + subtle jitter)
                const lateralDist = file * 0.000008 + Math.sin(i * 31.7) * 0.0000015;
                const sLat = pt.pos[0] + pt.norm[0] * lateralDist;
                const sLon = pt.pos[1] + pt.norm[1] * lateralDist;

                const screenPt = map.latLngToContainerPoint([sLat, sLon]);

                if (screenPt.x >= -10 && screenPt.x <= size.x + 10 && screenPt.y >= -10 && screenPt.y <= size.y + 10) {
                  dots.push({ x: screenPt.x, y: screenPt.y, color, radius: dotRadius, alpha });
                }
              }
            }
          }
        }

        // Draw buses first (under passengers)
        for (let bIdx = 0; bIdx < busesToDraw.length; bIdx++) {
          const bus = busesToDraw[bIdx];
          ctx.save();
          ctx.translate(bus.x, bus.y);
          ctx.rotate(bus.angle);

          const isCoach = bus.vehicle_type === "coach";
          const len = isCoach ? 32 : 22;
          const halfLen = len / 2;
          const wid = isCoach ? 14 : 12;
          const halfWid = wid / 2;

          // Bus chassis shadow
          ctx.fillStyle = "rgba(0, 0, 0, 0.25)";
          ctx.beginPath();
          if (typeof ctx.roundRect === "function") {
            ctx.roundRect(-halfLen + 1, -halfWid + 1, len, wid, 3);
          } else {
            ctx.rect(-halfLen + 1, -halfWid + 1, len, wid);
          }
          ctx.fill();

          // Bus chassis body
          // Coach: Deep Navy (#1E3A8A) with Amber roof (#F59E0B)
          // Electric: Emerald Green (#047857) with Cyan roof (#06B6D4)
          ctx.fillStyle = isCoach ? "#1E3A8A" : "#047857";
          ctx.strokeStyle = isCoach ? "#F59E0B" : "#06B6D4";
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          if (typeof ctx.roundRect === "function") {
            ctx.roundRect(-halfLen, -halfWid, len, wid, 3);
          } else {
            ctx.rect(-halfLen, -halfWid, len, wid);
          }
          ctx.fill();
          ctx.stroke();

          // Windshield (front: +x)
          ctx.fillStyle = isCoach ? "#BAE6FD" : "#A5F3FC";
          ctx.fillRect(halfLen - 4, -halfWid + 1.5, 3, wid - 3);

          // Headlights
          ctx.fillStyle = "#FEF08A";
          ctx.fillRect(halfLen - 1.5, -halfWid + 0.5, 1.5, 2);
          ctx.fillRect(halfLen - 1.5, halfWid - 2.5, 1.5, 2);

          // Rear lights
          ctx.fillStyle = "#EF4444";
          ctx.fillRect(-halfLen, -halfWid + 0.5, 1.5, 2);
          ctx.fillRect(-halfLen, halfWid - 2.5, 1.5, 2);

          // Single usable door indicator on curb side (-y)
          ctx.fillStyle = isCoach ? "#F59E0B" : "#06B6D4";
          ctx.fillRect(halfLen - 6, -halfWid - 1.2, 5, 1.8);

          // Vehicle label
          ctx.fillStyle = "#FFFFFF";
          ctx.font = "bold 7px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          const label = isCoach ? "COACH" : "⚡EV";
          ctx.fillText(label, -2, 0);

          // Empty return indicator
          if (bus.status === "transit_empty_return") {
            ctx.fillStyle = "#93C5FD";
            ctx.font = "bold 6px system-ui, sans-serif";
            ctx.fillText("EMPTY", -2, halfWid + 6);
          }
          ctx.restore();
        }
        // Batch draw student dots grouped by alpha/color for maximum performance
        const grouped = new Map<string, Array<{ x: number; y: number; r: number }>>();
        for (let dIdx = 0; dIdx < dots.length; dIdx++) {
          const dot = dots[dIdx];
          const key = `${dot.color}_${dot.alpha}`;
          let list = grouped.get(key);
          if (!list) {
            list = [];
            grouped.set(key, list);
          }
          list.push({ x: dot.x, y: dot.y, r: dot.radius });
        }

        grouped.forEach((pts, key) => {
          const [color, alphaStr] = key.split("_");
          ctx.fillStyle = color;
          ctx.globalAlpha = parseFloat(alphaStr);
          ctx.beginPath();
          for (let pIdx = 0; pIdx < pts.length; pIdx++) {
            const p = pts[pIdx];
            ctx.moveTo(p.x + p.r, p.y);
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
          }
          ctx.fill();
        });
      } finally {
        ctx.restore();
      }
    };

    render();

    const events = ["move", "zoom", "viewreset", "resize"];
    events.forEach((ev) => map.on(ev, render));

    const handleWindowResize = () => {
      map.invalidateSize();
      render();
    };
    window.addEventListener("resize", handleWindowResize);

    return () => {
      events.forEach((ev) => map.off(ev, render));
      window.removeEventListener("resize", handleWindowResize);
    };
  }, [map, replay, currentTimeMs, selectedHostel, selectedPlace]);

  return (
    <canvas
      ref={canvasRef}
      className="replay-canvas"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 450,
      }}
    />
  );
}
