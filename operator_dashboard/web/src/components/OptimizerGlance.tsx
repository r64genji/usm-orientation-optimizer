import type { OptimizerPayload } from "../types";

type Props = { payload: OptimizerPayload | null };

export default function OptimizerGlance({ payload }: Props) {
  return (
    <section className="panel" id="optimizer">
      <h2>Optimizer glance</h2>
      <p className="note">The optimizer tests plans in the simulator. This is not live bus or radio control.</p>
      {!payload || payload.message === "No saved result" ? (
        <p>No saved result.</p>
      ) : (
        <p>
          {payload.timestamp || "time unknown"} · status {payload.status || "unknown"}
        </p>
      )}
    </section>
  );
}
