import type { LegsPayload } from "../types";

type Props = {
  payload: LegsPayload | null;
  selectedHostel: string | null;
  onSelectHostel: (id: string) => void;
  onRerunFull: () => void;
};

const HOSTEL_INFO: Record<string, { name: string; mode: string; distance: string }> = {
  restu: { name: "Restu", mode: "🚌 RST Bus", distance: "2.3 km (ridge hill)" },
  saujana: { name: "Saujana", mode: "🚌 RST Bus", distance: "1.8 km (ridge hill)" },
  tekun: { name: "Tekun", mode: "🚌 RST Bus", distance: "2.6 km (ridge hill)" },
  indah_kembara: { name: "Indah Kembara", mode: "🚶 Walk", distance: "1.4 km (flat)" },
  aman_damai: { name: "Aman Damai", mode: "🚶 Walk", distance: "1.1 km (gentle)" },
  bakti_fajar_permai: { name: "Bakti Fajar Permai", mode: "🚶 Walk", distance: "0.97 km (stairs)" },
  cahaya_gemilang: { name: "Cahaya Gemilang", mode: "🚶 Walk", distance: "0.78 km (downhill)" },
  fajar_harapan: { name: "Fajar Harapan", mode: "🚶 Walk", distance: "0.68 km (lake path)" },
};

function clock(value: unknown): string {
  if (value == null) return "Not recorded";
  return String(value);
}

export default function LegsTimeline({ payload, selectedHostel, onSelectHostel, onRerunFull }: Props) {
  if (!payload) {
    return (
      <section className="panel">
        <h2>Legs</h2>
        <p>Legs wait for a finished test.</p>
      </section>
    );
  }
  return (
    <section className="panel" id="legs">
      <h2>Legs & Timelines</h2>
      {!payload.detailed_legs_available ? (
        <div className="note warn">
          <p>{payload.missing || "Detailed legs are unavailable on a summary run."}</p>
          <button type="button" onClick={onRerunFull}>
            Run again with full detail
          </button>
        </div>
      ) : null}
      {payload.hostels.map((hostel) => {
        const info = HOSTEL_INFO[hostel.hostel_id];
        return (
          <article
            key={hostel.hostel_id}
            className={selectedHostel === hostel.hostel_id ? "selected-block" : ""}
          >
            <button type="button" className="linkish" onClick={() => onSelectHostel(hostel.hostel_id)}>
              <strong>{info ? info.name : hostel.hostel_id}</strong> {info ? `· ${info.mode} (${info.distance})` : ""}
              {hostel.status === "not_used" ? " · Not used" : ""}
            </button>
          <dl className="mini">
            <div>
              <dt>Leave origin</dt>
              <dd>{clock(hostel.first.leave_origin_s)}</dd>
            </div>
            <div>
              <dt>Board</dt>
              <dd>{clock(hostel.first.board_s)}</dd>
            </div>
            <div>
              <dt>Ride</dt>
              <dd>{clock(hostel.first.ride_s)}</dd>
            </div>
            <div>
              <dt>Outside hold</dt>
              <dd>{clock(hostel.first.outside_hold_s)}</dd>
            </div>
            <div>
              <dt>Hall arrival</dt>
              <dd>{clock(hostel.first.hall_arrival_s)}</dd>
            </div>
            <div>
              <dt>Seated</dt>
              <dd>{clock(hostel.first.seated_s)}</dd>
            </div>
          </dl>
          {hostel.groups.length ? (
            <details>
              <summary>Group detail</summary>
              <ul>
                {hostel.groups.map((group) => (
                  <li key={String(group.group_id)}>
                    {String(group.group_id)}
                    {group.split ? " (split)" : ""}: finished {String(group.completed_students)}, unfinished {String(group.unfinished_students)}
                  </li>
                ))}
              </ul>
            </details>
          ) : (
            <p className="note">Not reached.</p>
          )}
        </article>
      );
      })}
    </section>
  );
}
