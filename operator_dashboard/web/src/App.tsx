import { useEffect, useMemo, useState } from "react";
import Bottlenecks from "./components/Bottlenecks";
import CampusMap from "./components/CampusMap";
import LegsTimeline from "./components/LegsTimeline";
import OptimizerGlance from "./components/OptimizerGlance";
import OverviewPanel from "./components/Overview";
import RunControls from "./components/RunControls";
import {
  fetchReplay,
  getBottlenecks,
  getLegs,
  getMap,
  getOptimizer,
  getOverview,
  getRun,
  getSavedRunId,
  getToken,
  listCases,
  rerunFull,
  setSavedRunId,
  setToken,
  startRun,
} from "./api";
import type {
  BottlenecksPayload,
  CaseRow,
  LegsPayload,
  MapPayload,
  OptimizerPayload,
  Overview,
  ReplayPayload,
  RunJob,
} from "./types";
function queryRunId(): string {
  const params = new URLSearchParams(window.location.search);
  return params.get("run") || getSavedRunId();
}

function initialToken(): string {
  const params = new URLSearchParams(window.location.search);
  const fromUrl = params.get("token");
  if (fromUrl) {
    setToken(fromUrl.trim());
    return fromUrl.trim();
  }
  const saved = getToken();
  if (saved) return saved;
  return "";
}

export default function App() {
  const [token, setTokenState] = useState(initialToken());
  const [tokenDraft, setTokenDraft] = useState("");
  const [needSignIn, setNeedSignIn] = useState(!initialToken());
  const [cases, setCases] = useState<CaseRow[]>([]);
  const [caseId, setCaseId] = useState("whole-campus-full-cohort");
  const [seed, setSeed] = useState("42");
  const [outputMode, setOutputMode] = useState<"full" | "compact">("full");
  const [groupTarget, setGroupTarget] = useState("25");
  const [hallSeats, setHallSeats] = useState("");
  const [applyParameters, setApplyParameters] = useState(false);
  const [job, setJob] = useState<RunJob | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [mapPayload, setMapPayload] = useState<MapPayload | null>(null);
  const [legs, setLegs] = useState<LegsPayload | null>(null);
  const [bottlenecks, setBottlenecks] = useState<BottlenecksPayload | null>(null);
  const [optimizer, setOptimizer] = useState<OptimizerPayload | null>(null);
  const [selectedHostel, setSelectedHostel] = useState<string | null>(null);
  const [selectedPlace, setSelectedPlace] = useState<string | null>(null);
  const [replay, setReplay] = useState<ReplayPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const busy = job?.status === "queued" || job?.status === "running";

  function rememberRun(id: string) {
    setSavedRunId(id);
    const url = new URL(window.location.href);
    url.searchParams.set("run", id);
    window.history.replaceState({}, "", url.toString());
  }

  async function boot() {
    try {
      const listed = await listCases();
      setCases(listed.cases);
      setNeedSignIn(false);
      setOptimizer(await getOptimizer());
      if (listed.cases.length > 0) {
        const fullCohort = listed.cases.find((c: CaseRow) => c.id === "whole-campus-full-cohort");
        if (fullCohort) {
          setCaseId(fullCohort.id);
        } else if (!listed.cases.some((c: CaseRow) => c.id === caseId)) {
          setCaseId(listed.cases[0].id);
        }
      }
      const existing = queryRunId();
      if (existing) {
        const current = await getRun(existing);
        setJob(current);
        rememberRun(current.id);
      }
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 401) setNeedSignIn(true);
      else setError((err as Error).message);
    }
  }

  useEffect(() => {
    if (token) boot();
  }, [token]);

  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) return;
    const handle = window.setInterval(async () => {
      try {
        const current = await getRun(job.id);
        setJob(current);
      } catch (err) {
        setError((err as Error).message);
      }
    }, 1000);
    return () => window.clearInterval(handle);
  }, [job?.id, job?.status]);

  useEffect(() => {
    if (!job || job.status !== "finished") return;
    Promise.all([
      getOverview(job.id),
      getMap(job.id),
      getLegs(job.id),
      getBottlenecks(job.id),
      fetchReplay(job.id).catch(() => null),
    ])
      .then(([ov, mp, lg, bn, rp]) => {
        setOverview(ov);
        setMapPayload(mp);
        setLegs(lg);
        setBottlenecks(bn);
        setReplay(rp);
      })
      .catch((err) => setError((err as Error).message));
  }, [job?.id, job?.status]);

  async function onStart() {
    setError(null);
    const seedN = Number(seed);
    if (!Number.isInteger(seedN)) {
      setError("Seed must be a whole number.");
      return;
    }
    const body: Record<string, unknown> = {
      case: caseId,
      seed: seedN,
      output_mode: outputMode,
    };
    if (applyParameters) {
      body.apply_parameters = true;
      const groupN = Number(groupTarget);
      if (!Number.isInteger(groupN) || groupN < 1) {
        setError("Group size must be a positive whole number.");
        return;
      }
      body.group_target_students = groupN;
      if (hallSeats) body.hall_seats = Number(hallSeats);
    }
    try {
      const created = await startRun(body);
      setJob(created);
      setOverview(null);
      setMapPayload(null);
      setLegs(null);
      setBottlenecks(null);
      rememberRun(created.id);
      setReplay(null);
    } catch (err) {
      const status = (err as Error & { status?: number }).status;
      if (status === 401) setNeedSignIn(true);
      setError((err as Error).message);
    }
  }

  async function onRerunFull() {
    if (!job) return;
    try {
      const created = await rerunFull(job.id);
      setJob(created);
      rememberRun(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const title = useMemo(() => {
    if (!job) return "No run selected";
    return `Run ${job.id} · ${job.case} · seed ${job.seed}`;
  }, [job]);

  if (needSignIn) {
    return (
      <main className="gate" role="main" aria-label="Operator Authentication">
        <h1>USM Movement Dashboard</h1>
        <p>Enter the operator authorization token to access campus logistics and simulation control.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const trimmed = tokenDraft.trim();
            if (!trimmed) return;
            setToken(trimmed);
            setTokenState(trimmed);
            setNeedSignIn(false);
          }}
        >
          <input
            type="password"
            value={tokenDraft}
            onChange={(e) => setTokenDraft(e.target.value)}
            placeholder="Dashboard token (e.g. usm-orient-2026)"
            aria-label="Dashboard authentication token"
            autoFocus
          />
          <button
            className="primary"
            type="submit"
            aria-label="Open Dashboard"
          >
            Open dashboard
          </button>
        </form>
      </main>
    );
  }

  return (
    <main>
      <header className="top">
        <p className="eyebrow">USM orientation morning</p>
        <h1>Movement test board</h1>
        <p className="run-name">{title}</p>
        <p className="guide">
          Case = starting setup. Run = one test. Seed = repeat setting. Unfinished = students who did not finish before this test stopped.
        </p>
      </header>
      {error ? <p className="error">{error}</p> : null}
      <RunControls
        cases={cases}
        caseId={caseId}
        seed={seed}
        outputMode={outputMode}
        groupTarget={groupTarget}
        hallSeats={hallSeats}
        applyParameters={applyParameters}
        busy={Boolean(busy)}
        job={job}
        onCase={setCaseId}
        onSeed={setSeed}
        onMode={setOutputMode}
        onGroupTarget={setGroupTarget}
        onHallSeats={setHallSeats}
        onApplyParameters={setApplyParameters}
        onStart={onStart}
        onRerunFull={onRerunFull}
      />
      <OverviewPanel
        job={job}
        overview={overview}
        selectedHostel={selectedHostel}
        onSelectHostel={setSelectedHostel}
      />
      <CampusMap
        payload={mapPayload}
        replay={replay}
        selectedHostel={selectedHostel}
        selectedPlace={selectedPlace}
        onSelectHostel={setSelectedHostel}
        onSelectPlace={setSelectedPlace}
      />
      <LegsTimeline
        payload={legs}
        selectedHostel={selectedHostel}
        onSelectHostel={setSelectedHostel}
        onRerunFull={onRerunFull}
      />
      <Bottlenecks
        payload={bottlenecks}
        selectedPlace={selectedPlace}
        onSelectPlace={setSelectedPlace}
      />
      <OptimizerGlance payload={optimizer} />
    </main>
  );
}
