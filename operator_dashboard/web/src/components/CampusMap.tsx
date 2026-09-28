import { useEffect, useState } from "react";
import { CircleMarker, GeoJSON, MapContainer, Polyline, Popup, TileLayer, Tooltip } from "react-leaflet";
import type { MapPayload, ReplayPayload } from "../types";
import ReplayCanvas from "./ReplayCanvas";
import ReplayController from "./ReplayController";
import ReplaySectorMetrics from "./ReplaySectorMetrics";

type Props = {
  payload: MapPayload | null;
  replay?: ReplayPayload | null;
  selectedHostel: string | null;
  selectedPlace: string | null;
  onSelectHostel: (id: string) => void;
  onSelectPlace: (id: string) => void;
};
const LEGEND_HOSTELS = [
  { id: "restu", name: "Restu", color: "#8B5CF6", mode: "RST Bus" },
  { id: "saujana", name: "Saujana", color: "#0EA5E9", mode: "RST Bus" },
  { id: "tekun", name: "Tekun", color: "#F59E0B", mode: "RST Bus" },
  { id: "indah_kembara", name: "Indah Kembara", color: "#10B981", mode: "Walk" },
  { id: "aman_damai", name: "Aman Damai", color: "#EF4444", mode: "Walk" },
  { id: "bakti_fajar_permai", name: "Bakti Fajar", color: "#06B6D4", mode: "Walk" },
  { id: "cahaya_gemilang", name: "Cahaya Gemilang", color: "#D97706", mode: "Walk" },
  { id: "fajar_harapan", name: "Fajar Harapan", color: "#EC4899", mode: "Walk" },
];

export default function CampusMap({
  payload,
  replay,
  selectedHostel,
  selectedPlace,
  onSelectHostel,
  onSelectPlace,
}: Props) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(10);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);

  const durationMs = replay?.time_bounds?.end_ms || 0;
  const clockStart = replay?.time_bounds?.clock_start || "2026-09-17T07:00:00+08:00";

  // Reset time when replay run changes
  useEffect(() => {
    setCurrentTimeMs(0);
    setIsPlaying(false);
  }, [replay?.run_id]);

  // Playback animation ticker
  useEffect(() => {
    if (!isPlaying || durationMs <= 0) return;

    let animId: number;
    let lastWall = performance.now();

    const tick = (now: number) => {
      const deltaSec = Math.max(0, (now - lastWall) / 1000);
      lastWall = now;

      let reachedEnd = false;
      setCurrentTimeMs((prev) => {
        const next = prev + deltaSec * speed * 1000;
        if (next >= durationMs) {
          reachedEnd = true;
          return durationMs;
        }
        return next;
      });

      if (reachedEnd) {
        setIsPlaying(false);
      } else {
        animId = requestAnimationFrame(tick);
      }
    };

    animId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, speed, durationMs]);

  const handleStep = (deltaSec: number) => {
    setCurrentTimeMs((prev) => Math.min(durationMs, Math.max(0, prev + deltaSec * 1000)));
  };
  if (!payload) {
    return (
      <section className="panel">
        <h2>Campus map</h2>
        <p>The map waits for a finished test.</p>
      </section>
    );
  }

  // Campus center: between Restu (west) and DTSP (east)
  const center: [number, number] = [5.3568, 100.2970];

  return (
    <section className="panel" id="map">
      <h2>Campus map</h2>
      <p className="note">
        Real map of Universiti Sains Malaysia (USM Kampus Induk). Shows all 8 student hostels,
        the orientation bus transit corridor, individual walking routes, and the DTSP destination area.
      </p>
      {payload.missing ? <p className="note warn">{payload.missing}</p> : null}
      
      {replay?.has_trace ? (
        <ReplayController
          isPlaying={isPlaying}
          speed={speed}
          currentTimeMs={currentTimeMs}
          durationMs={durationMs}
          clockStart={clockStart}
          onTogglePlay={() => {
            if (!isPlaying && currentTimeMs >= durationMs) {
              setCurrentTimeMs(0);
            }
            setIsPlaying(!isPlaying);
          }}
          onSetSpeed={setSpeed}
          onSeek={setCurrentTimeMs}
          onStep={handleStep}
        />
      ) : replay && !replay.has_trace ? (
        <p className="note warn">
          {replay.missing || "Compact run has no event trace. Run in full mode to view student movement replay."}
        </p>
      ) : null}

      <div className="map-wrap">
        <MapContainer center={center} zoom={16} scrollWheelZoom={true} className="leaflet-host">
          {/* Real OpenStreetMap Tile Layer of USM */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
          />

          {/* Routes and Legs */}
          {payload.planned_links
            .filter((link) => link.on_map)
            .map((link) => {
              const coords: [number, number][] =
                link.coordinates && link.coordinates.length >= 2
                  ? (link.coordinates as [number, number][])
                  : [
                      [link.from!.latitude_deg, link.from!.longitude_deg],
                      [link.to!.latitude_deg, link.to!.longitude_deg],
                    ];
              const selectedHostelObj = selectedHostel ? LEGEND_HOSTELS.find((h) => h.id === selectedHostel) : null;
              const isHostelMatch = Boolean(
                selectedHostel && (link.hostel_ids?.includes(selectedHostel) || link.id?.includes(selectedHostel))
              );
              const isBus = link.mode === "coach" || link.mode === "bus" || link.mode === "electric";
              const weight = selectedHostel ? (isHostelMatch ? 6 : 2) : 4;
              const opacity = selectedHostel ? (isHostelMatch ? 1.0 : 0.15) : 0.9;
              const color = isHostelMatch && selectedHostelObj ? selectedHostelObj.color : link.color || (isBus ? "#1D4ED8" : "#10B981");
              return (
                <Polyline
                  key={String(link.id)}
                  positions={coords}
                  pathOptions={{
                    color,
                    weight,
                    opacity,
                    dashArray: link.used ? undefined : "6 6",
                  }}
                >
                  <Popup>
                    <div>
                      <strong>{link.leg_name || link.label || link.id}</strong>
                      <br />
                      <span>Mode: {isBus ? "Orientation Bus" : "Walk"}</span>
                      <br />
                      <span>Status: {link.used ? "Used in this run" : "Planned route"}</span>
                    </div>
                  </Popup>
                </Polyline>
              );
            })}

          {/* Places and Station Markers */}
          {payload.places.map((place) => {
            const isSelected = selectedPlace === place.id;
            const isHall = place.role === "seats" || place.id === "dtsp_seating" || place.id === "dtsp_hall_reference";
            const isHold = place.role === "road_reservoir" || place.id === "dtsp_exterior_gathering";
            const isBerth = place.role === "boarding_berth" || place.id === "rst_boarding_approach";
            const isShelter = place.role === "shelter" || place.id === "rst_rain_shelter";
            const isKeyNode = isHall || isHold || isBerth || isShelter;
            const radius = isSelected ? 12 : isHall ? 10 : isHold ? 9 : isBerth ? 8 : isShelter ? 8 : 6;
            const color = place.color || (isHold ? "#dc2626" : isHall ? "#ca8a04" : isBerth ? "#1d4ed8" : isShelter ? "#64748b" : "#475569");

            return (
              <CircleMarker
                key={place.id}
                center={[place.latitude_deg, place.longitude_deg]}
                radius={radius}
                pathOptions={{
                  color: isSelected ? "#ffffff" : color,
                  fillColor: color,
                  fillOpacity: 0.9,
                  weight: isSelected ? 3 : 2,
                }}
                eventHandlers={{ click: () => onSelectPlace(place.id) }}
              >
                <Popup>
                  <div>
                    <strong>{place.badge || place.label}</strong>
                    <br />
                    <span>Role: {place.role || "station"}</span>
                  </div>
                </Popup>
                {isKeyNode ? (
                  <Tooltip permanent direction="bottom" offset={[0, 6]} className="map-badge place-badge">
                    {place.badge || place.label}
                  </Tooltip>
                ) : null}
              </CircleMarker>
            );
          })}

          {/* Hostel Origin Markers */}
          {payload.hostels.map((hostel) => {
            const isSelected = selectedHostel === hostel.id;
            const color = hostel.color || (hostel.rst ? "#0EA5E9" : "#10B981");

            return (
              <CircleMarker
                key={hostel.id}
                center={[hostel.latitude_deg, hostel.longitude_deg]}
                radius={isSelected ? 14 : 10}
                pathOptions={{
                  color: isSelected ? "#ffffff" : color,
                  fillColor: color,
                  fillOpacity: 0.95,
                  weight: isSelected ? 4 : 2,
                }}
                eventHandlers={{ click: () => onSelectHostel(hostel.id) }}
              >
                <Popup>
                  <div>
                    <strong>{hostel.name}</strong>
                    <br />
                    <span>Route mode: {hostel.rst ? "RST Bus Shuttle" : "Walking Contingent"}</span>
                    <br />
                    <span>Status: {hostel.used_in_run ? "Active in this test" : "Not moving"}</span>
                  </div>
                </Popup>
                <Tooltip permanent direction="top" offset={[0, -10]} className="map-badge hostel-badge">
                  {hostel.name}
                </Tooltip>
              </CircleMarker>
            );
          })}

          {/* Optional Sensor Logger GPS Ground Truth Overlay */}
          {payload.restu_overlay?.geojson ? (
            <GeoJSON
              data={payload.restu_overlay.geojson as never}
              pathOptions={{ color: "#7928CA", weight: 2, opacity: 0.6, dashArray: "2 4" }}
            />
          ) : null}
          {/* Live Student Replay Dots Layer */}
          <ReplayCanvas
            replay={replay || null}
            currentTimeMs={currentTimeMs}
            selectedHostel={selectedHostel}
            selectedPlace={selectedPlace}
          />
        </MapContainer>
      </div>

      {/* Map Legend */}
      <div className="map-legend">
        <div className="legend-group">
          <strong>Waiting Areas & Ingress Sectors:</strong>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#dc2626" }} />
            ⏳ 3-Tier Car Park Waiting Area (RST Bus Alightees)
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#d97706" }} />
            🎪 Dataran Merah (Shaded Pavilion - Cahaya Gemilang & Bakti Fajar)
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#059669" }} />
            🌱 Grass Field in front of G28 Siswaniaga (Indah Kembara, Aman Damai & Fajar Harapan)
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#8b5cf6" }} />
            🌉 Jejantas Overpass (RST Skybridge)
          </span>
          <span className="legend-item">
            <span className="legend-color" style={{ background: "#1D4ED8", height: "4px" }} />
            🚌 Bus Corridor (Persiaran Sains)
          </span>
          <span className="legend-item">
            <span className="legend-dot" style={{ background: "#ca8a04" }} />
            🏛️ DTSP Hall & Seating
          </span>
        </div>

        <div className="legend-group">
          <strong>Hostel Routes:</strong>
          {LEGEND_HOSTELS.map((h) => (
            <button
              type="button"
              key={h.id}
              className={`legend-item legend-btn ${selectedHostel === h.id ? "active" : ""}`}
              onClick={() => onSelectHostel(h.id)}
            >
              <span className="legend-dot" style={{ background: h.color }} />
              {h.name} ({h.mode})
            </button>
          ))}
        </div>
      </div>

      {/* Live Sector Metrics Panel */}
      <ReplaySectorMetrics
        replay={replay || null}
        currentTimeMs={currentTimeMs}
        selectedSector={selectedPlace}
        selectedHostel={selectedHostel}
        onSelectSector={onSelectPlace}
        onSelectHostel={onSelectHostel}
      />

      {payload.restu_overlay ? (
        <p className="note">
          Purple dashed line: Measured GPS trace ({payload.restu_overlay.label}). {payload.restu_overlay.note}
        </p>
      ) : null}
    </section>
  );
}
