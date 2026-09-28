import { useMemo } from "react";
import type { ReplayPayload, ReplaySector, SectorMetrics } from "../types";

type Props = {
  replay: ReplayPayload | null;
  currentTimeMs: number;
  selectedSector: string | null;
  selectedHostel: string | null;
  onSelectSector: (id: string) => void;
  onSelectHostel: (id: string) => void;
};

export default function ReplaySectorMetrics({
  replay,
  currentTimeMs,
  selectedSector,
  selectedHostel: _selectedHostel,
  onSelectSector,
  onSelectHostel,
}: Props) {
  // Find current sector metrics from timeline
  const currentStats = useMemo<Record<string, SectorMetrics>>(() => {
    if (!replay || !replay.sector_stats_timeline || replay.sector_stats_timeline.length === 0) {
      return {};
    }
    const timeline = replay.sector_stats_timeline;
    // Find nearest or preceding time bucket
    let best = timeline[0];
    for (let i = 0; i < timeline.length; i++) {
      if (timeline[i].time_ms <= currentTimeMs) {
        best = timeline[i];
      } else {
        break;
      }
    }
    return best?.sectors || {};
  }, [replay, currentTimeMs]);

  if (!replay || !replay.has_trace) {
    return null;
  }

  const sectors: ReplaySector[] = useMemo(() => {
    const list = [...(replay.sectors || [])];
    if (!list.some((s) => s.id === "g03_foyer_entrance")) {
      list.push({
        id: "g03_foyer_entrance",
        name: "Bangunan G03 Foyer Entrance",
        role: "foyer",
        color: "#06B6D4",
        coordinates: [5.357119, 100.302499],
        hostel_id: null,
      });
    }
    if (!list.some((s) => s.id === "g03_seating")) {
      list.push({
        id: "g03_seating",
        name: "Bangunan G03 Overflow Seating (DK G/H)",
        role: "seats",
        color: "#3B82F6",
        coordinates: [5.357119, 100.302499],
        hostel_id: null,
      });
    }
    return list;
  }, [replay.sectors]);

  return (
    <div className="replay-sectors-panel">
      <div className="replay-sectors-header">
        <h3>Live Sector Metrics & Crowd Inspector</h3>
        <p className="note" style={{ margin: "0.2rem 0 0.6rem" }}>
          Real-time crowding headcount, average waiting time, and transport duration at each campus sector.
          Click a sector to filter and highlight its students on the map.
        </p>
      </div>

      <div className="replay-sectors-grid">
        {sectors.map((sec) => {
          const stats = currentStats[sec.id] || {
            headcount: 0,
            avg_wait_s: 0,
            avg_transit_s: 0,
            status: "flowing",
          };

          const isSelected = selectedSector === sec.id;
          const statusClass = `status-${stats.status || "flowing"}`;
          const avgWait = Number.isFinite(stats.avg_wait_s) ? stats.avg_wait_s : 0;
          const avgTransit = Number.isFinite(stats.avg_transit_s) ? stats.avg_transit_s : 0;

          const toggleSector = () => {
            if (isSelected) {
              onSelectSector("");
            } else {
              onSelectSector(sec.id);
              if (sec.hostel_id) {
                onSelectHostel(sec.hostel_id);
              }
            }
          };

          return (
            <div
              key={sec.id}
              className={`sector-metric-card ${isSelected ? "selected" : ""} ${statusClass}`}
              onClick={toggleSector}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggleSector();
                }
              }}
              role="button"
              tabIndex={0}
            >
              <div className="sector-card-top">
                <span className="sector-color-indicator" style={{ background: sec.color }} />
                <span className="sector-name" title={sec.name}>
                  {sec.name}
                </span>
                <span className={`sector-status-pill ${statusClass}`}>
                  {stats.status.toUpperCase()}
                </span>
              </div>

              <div className="sector-card-values">
                <div className="sector-val-item">
                  <span className="val-number">{stats.headcount}</span>
                  <span className="val-label">Students</span>
                </div>

                <div className="sector-val-item">
                  <span className="val-number">
                    {avgWait > 60
                      ? `${(avgWait / 60).toFixed(1)}m`
                      : `${Math.round(avgWait)}s`}
                  </span>
                  <span className="val-label">Avg Wait</span>
                </div>

                <div className="sector-val-item">
                  <span className="val-number">
                    {avgTransit > 60
                      ? `${(avgTransit / 60).toFixed(1)}m`
                      : `${Math.round(avgTransit)}s`}
                  </span>
                  <span className="val-label">Avg Transit</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
