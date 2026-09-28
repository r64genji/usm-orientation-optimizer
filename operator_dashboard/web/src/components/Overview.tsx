import type { Overview, RunJob } from "../types";

function fmt(value: number | null | undefined, unit = ""): string {
  if (value == null) return "Unknown";
  return `${value}${unit}`;
}

type Props = {
  job: RunJob | null;
  overview: Overview | null;
  selectedHostel: string | null;
  onSelectHostel: (id: string) => void;
};

export default function OverviewPanel({ job, overview, selectedHostel, onSelectHostel }: Props) {
  if (!job) {
    return (
      <section className="panel">
        <h2>Counts</h2>
        <p>Start a test to see counts.</p>
      </section>
    );
  }
  if (job.status === "queued" || job.status === "running") {
    return (
      <section className="panel">
        <h2>Counts</h2>
        <p>This test is still going. Wall time is separate from simulated time.</p>
      </section>
    );
  }
  if (!overview) {
    return (
      <section className="panel">
        <h2>Counts</h2>
        <p>{job.error?.message || "No counts yet."}</p>
      </section>
    );
  }
  const hall = overview.hall_clock || {};
  return (
    <section className="panel" id="overview">
      <h2>Counts</h2>
      {overview.holdout ? <p className="note warn">GPS holdout. Labelled reference only.</p> : null}
      {overview.conservation_ok === false ? (
        <p className="error">{overview.conservation_error}</p>
      ) : null}
      <dl className="counts">
        <div>
          <dt>Finished</dt>
          <dd>{fmt(overview.completed_students)}</dd>
        </div>
        <div>
          <dt>Unfinished</dt>
          <dd>{fmt(overview.unfinished_students)}</dd>
        </div>
        <div>
          <dt>Left the event</dt>
          <dd>{fmt(overview.withdrawn_students)}</dd>
        </div>
        <div>
          <dt>Accounted</dt>
          <dd>{fmt(overview.accounted_students)}</dd>
        </div>
      </dl>
      {overview.venue_allocation ? (
        <div className="venue-allocation" style={{ marginTop: "1rem", marginBottom: "1rem", padding: "0.75rem", background: "rgba(59, 130, 246, 0.08)", borderRadius: "6px" }}>
          <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem" }}>Venue Allocation</h3>
          <dl className="counts">
            <div>
              <dt>DTSP Seats</dt>
              <dd>{overview.venue_allocation.dtsp_seated.toLocaleString()}</dd>
            </div>
            <div>
              <dt>G03 Overflow (DK G/H)</dt>
              <dd>{overview.venue_allocation.g03_seated.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Total Seated</dt>
              <dd>{overview.venue_allocation.total_seated.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Cohort Coverage</dt>
              <dd>{overview.venue_allocation.cohort_coverage_pct}%</dd>
            </div>
          </dl>
          <p className="note" style={{ margin: "0.25rem 0 0 0" }}>
            DTSP seats: {overview.venue_allocation.dtsp_seated.toLocaleString()} vs G03 seats: {overview.venue_allocation.g03_seated.toLocaleString()}, {overview.venue_allocation.cohort_coverage_pct}% seated coverage.
          </p>
        </div>
      ) : null}
      <p className="note">No-shows stay separate: {fmt(overview.no_show_students)}.</p>
      <p>
        Average wait {fmt(overview.mean_wait_s, " s")} among {fmt(overview.wait_denominator_students)} students.
        95 of 100 waited {fmt(overview.p95_wait_s, " s")} or less.
      </p>
      <p>
        Hostel with the highest average wait: {overview.worst_hostel_id || "Unknown"} ({fmt(overview.worst_hostel_mean_wait_s, " s")}).
      </p>
      <p className="note">
        Hall arrival {String(hall.first_hall_arrival_clock || "not recorded")} to {String(hall.last_hall_arrival_clock || "not recorded")}.
        After 09:00: {hall.after_09_available ? String(hall.count_after_09 ?? "Unknown") : "this case has no 09:00 clock"}.
        Seated time is separate from hall arrival.
      </p>
      <ul className="hostel-list">
        {(overview.per_hostel || []).map((row) => {
          const id = String(row.hostel_id || "");
          return (
            <li key={id}>
              <button
                type="button"
                className={selectedHostel === id ? "selected" : ""}
                onClick={() => onSelectHostel(id)}
              >
                {id}: finished {String(row.completed_students)} · wait {String(row.mean_wait_s ?? "Unknown")} s
              </button>
            </li>
          );
        })}
      </ul>
      <details>
        <summary>Assumptions</summary>
        <ul>
          {(overview.assumptions || []).map((item, index) => (
            <li key={index}>
              <strong>{item.kind}.</strong> {item.text}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
