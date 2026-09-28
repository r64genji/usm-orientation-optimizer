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

const TOKEN_KEY = "usm-dashboard-token";
const RUN_KEY = "usm-dashboard-run-id";

export function getToken(): string {
  return sessionStorage.getItem(TOKEN_KEY) || localStorage.getItem(TOKEN_KEY) || "usm-orient-2026";
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TOKEN_KEY, token);
}

export function getSavedRunId(): string {
  return localStorage.getItem(RUN_KEY) || "";
}

export function setSavedRunId(id: string): void {
  localStorage.setItem(RUN_KEY, id);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) {
    const err = new Error("Sign in needed");
    (err as Error & { status: number }).status = 401;
    throw err;
  }
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || `Request failed (${res.status})`);
  }
  return data as T;
}

export function listCases(): Promise<{ cases: CaseRow[] }> {
  return request("/api/cases");
}

export function startRun(body: Record<string, unknown>): Promise<RunJob> {
  return request("/api/runs", { method: "POST", body: JSON.stringify(body) });
}

export function getRun(id: string): Promise<RunJob> {
  return request(`/api/runs/${id}`);
}

export function getOverview(id: string): Promise<Overview> {
  return request(`/api/runs/${id}/overview`);
}

export function getMap(id: string): Promise<MapPayload> {
  return request(`/api/runs/${id}/map`);
}

export function getLegs(id: string): Promise<LegsPayload> {
  return request(`/api/runs/${id}/legs`);
}

export function getBottlenecks(id: string): Promise<BottlenecksPayload> {
  return request(`/api/runs/${id}/bottlenecks`);
}

export function getOptimizer(): Promise<OptimizerPayload> {
  return request("/api/optimizer");
}

export function rerunFull(id: string): Promise<RunJob> {
  return request(`/api/runs/${id}/rerun-full`, { method: "POST" });
}

export function getMeta(): Promise<Record<string, unknown>> {
  return request("/api/meta");
}

export function fetchReplay(id: string): Promise<ReplayPayload> {
  return request(`/api/runs/${id}/replay`);
}
