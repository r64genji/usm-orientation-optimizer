import type { BottlenecksPayload } from "../types";

type Props = {
  payload: BottlenecksPayload | null;
  selectedPlace: string | null;
  onSelectPlace: (id: string) => void;
};

export default function Bottlenecks({ payload, selectedPlace, onSelectPlace }: Props) {
  if (!payload) {
    return (
      <section className="panel">
        <h2>Bottlenecks</h2>
        <p>Delays wait for a finished test.</p>
      </section>
    );
  }
  return (
    <section className="panel" id="bottlenecks">
      <h2>Bottlenecks</h2>
      <p className="note">Restu moves last. Use the recorded delay cause. Do not read this as door speed or distance.</p>
      <h3>Delays</h3>
      {payload.delays.length === 0 ? <p>No delay records.</p> : null}
      <ul>
        {payload.delays.map((row, index) => {
          const place = row.place_id || "unknown";
          return (
            <li key={`${place}-${index}`} className={selectedPlace === place ? "selected-block" : ""}>
              <button type="button" className="linkish" onClick={() => onSelectPlace(place)}>
                {place}
              </button>
              : {row.cause || "unknown cause"} · {row.duration_s ?? "Unknown"} s · {row.affected_count ?? "Unknown"} students
            </li>
          );
        })}
      </ul>
      <h3>Students who did not finish</h3>
      {payload.unfinished.length === 0 ? <p>None recorded.</p> : null}
      <ul>
        {payload.unfinished.map((row, index) => {
          const place = row.place_id || "unknown";
          return (
            <li key={`${place}-u-${index}`}>
              <button type="button" className="linkish" onClick={() => onSelectPlace(place)}>
                {place}
              </button>
              : {row.student_count} students · {row.cause || row.status || "cause not recorded"}
            </li>
          );
        })}
      </ul>
      <h3>Place peaks</h3>
      <ul>
        {(payload.occupancy_peaks || []).map((row) => (
          <li key={String(row.place_id)}>
            {String(row.place_id)}: {String(row.peak_students ?? row.end_occupancy_students ?? "Unknown")} ({String(row.label)})
          </li>
        ))}
      </ul>
    </section>
  );
}
