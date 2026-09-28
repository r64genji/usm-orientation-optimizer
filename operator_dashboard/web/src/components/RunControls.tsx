import { useState } from "react";
import type { CaseRow, RunJob } from "../types";

type Props = {
  cases: CaseRow[];
  caseId: string;
  seed: string;
  outputMode: "full" | "compact";
  groupTarget: string;
  hallSeats: string;
  applyParameters: boolean;
  busy: boolean;
  job: RunJob | null;
  onCase: (value: string) => void;
  onSeed: (value: string) => void;
  onMode: (value: "full" | "compact") => void;
  onGroupTarget: (value: string) => void;
  onHallSeats: (value: string) => void;
  onApplyParameters: (value: boolean) => void;
  onStart: () => void;
  onRerunFull: () => void;
};

export default function RunControls(props: Props) {
  const [showAllSetups, setShowAllSetups] = useState(false);
  const selected = props.cases.find((row) => row.id === props.caseId);
  const visibleCases = showAllSetups
    ? props.cases
    : props.cases.filter((row) => row.is_realistic || row.id === "whole-campus-full-cohort" || row.id === "whole-campus-origins");

  return (
    <section className="panel controls" id="run-controls">
      <h2>Start a test</h2>
      <label>
        Starting setup
        <select value={props.caseId} onChange={(e) => props.onCase(e.target.value)}>
          {visibleCases.map((row) => (
            <option key={row.id} value={row.id}>
              {row.label || row.id}
              {row.holdout ? " (GPS holdout)" : ""}
            </option>
          ))}
        </select>
      </label>
      <label className="choice small-choice">
        <input
          type="checkbox"
          checked={showAllSetups}
          onChange={(e) => setShowAllSetups(e.target.checked)}
        />
        Show test & holdout setups
      </label>
      {selected?.holdout ? (
        <p className="note warn">{selected.holdout_note}</p>
      ) : null}
      <label>
        Repeat setting (seed)
        <input
          inputMode="numeric"
          value={props.seed}
          onChange={(e) => props.onSeed(e.target.value)}
        />
      </label>
      <fieldset>
        <legend>How much detail</legend>
        <label className="choice">
          <input
            type="radio"
            name="mode"
            checked={props.outputMode === "full"}
            onChange={() => props.onMode("full")}
          />
          Full detail
        </label>
        <label className="choice">
          <input
            type="radio"
            name="mode"
            checked={props.outputMode === "compact"}
            onChange={() => props.onMode("compact")}
          />
          Summary
        </label>
      </fieldset>
      <label className="choice">
        <input
          type="checkbox"
          checked={props.applyParameters}
          onChange={(e) => props.onApplyParameters(e.target.checked)}
        />
        Use my group size and hall seats
      </label>
      {props.applyParameters ? (
        <>
          <label>
            Group target size
            <input
              inputMode="numeric"
              value={props.groupTarget}
              onChange={(e) => props.onGroupTarget(e.target.value)}
            />
          </label>
          <label>
            Hall seats
            <select value={props.hallSeats} onChange={(e) => props.onHallSeats(e.target.value)}>
              <option value="">Keep this case as written</option>
              <option value="1338">Paper main floor 1338</option>
              <option value="2500">Cited full hall 2500 (not confirmed)</option>
              <option value="3500">Cited full hall 3500 (not confirmed)</option>
            </select>
          </label>
        </>
      ) : null}
      <p className="note">8 buses. 5 coach and 3 electric. Each bus has one door. You cannot change the fleet.</p>
      <button className="primary" type="button" disabled={props.busy} onClick={props.onStart}>
        {props.busy ? "Test running…" : "Start test"}
      </button>
      {props.job?.output_mode === "compact" && props.job.status === "finished" ? (
        <button type="button" onClick={props.onRerunFull}>
          Run again with full detail
        </button>
      ) : null}
      {props.job ? (
        <p className="status">
          Run {props.job.id}: {props.job.status}
          {props.job.engine_status ? ` · engine ${props.job.engine_status}` : ""}
          {props.job.wall_s != null ? ` · ${props.job.wall_s.toFixed(1)} s wall time` : ""}
        </p>
      ) : null}
    </section>
  );
}
