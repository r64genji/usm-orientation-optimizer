export type JobStatus =
  | "queued"
  | "running"
  | "finished"
  | "failed"
  | "timed_out"
  | "interrupted";

export type RunJob = {
  id: string;
  status: JobStatus;
  case: string;
  seed: number;
  output_mode: string;
  engine_status: string | null;
  termination_cause: string | null;
  exit_code: number | null;
  wall_s: number | null;
  error: { message?: string } | null;
  holdout?: boolean;
};

export type CaseRow = {
  id: string;
  label?: string;
  is_realistic?: boolean;
  builder: string;
  holdout: boolean;
  holdout_note: string | null;
};

export type VenueAllocation = {
  dtsp_seated: number;
  g03_seated: number;
  total_seated: number;
  cohort_coverage_pct: number;
};

export type Overview = {
  run_id: string;
  case: string;
  seed: number;
  output_mode: string;
  engine_status: string | null;
  termination_cause: string | null;
  completed_students: number | null;
  unfinished_students: number | null;
  withdrawn_students: number | null;
  accounted_students: number | null;
  attending_students: number | null;
  no_show_students: number | null;
  conservation_ok: boolean | null;
  conservation_error: string | null;
  mean_wait_s: number | null;
  p95_wait_s: number | null;
  wait_denominator_students: number | null;
  worst_hostel_id: string | null;
  worst_hostel_mean_wait_s: number | null;
  per_hostel: Array<Record<string, unknown>>;
  hall_clock: Record<string, unknown>;
  assumptions: Array<{ kind: string; text: string }>;
  fleet: Record<string, unknown>;
  holdout: boolean;
  guide: Record<string, string>;
  missing: string | null;
  venue_allocation?: VenueAllocation | null;
};

export type MapPayload = {
  hostels: Array<{
    id: string;
    name: string;
    color?: string;
    latitude_deg: number;
    longitude_deg: number;
    rst: boolean;
    used_in_run: boolean | null;
  }>;
  places: Array<{
    id: string;
    label: string;
    badge?: string;
    color?: string;
    icon?: string;
    role?: string;
    latitude_deg: number;
    longitude_deg: number;
  }>;
  unknown_places: Array<{ id: string; label: string; reason: string }>;
  planned_links: Array<{
    id: string;
    from: { latitude_deg: number; longitude_deg: number } | null;
    to: { latitude_deg: number; longitude_deg: number } | null;
    mode: string;
    style: string;
    label: string;
    color?: string;
    weight?: number;
    coordinates?: [number, number][];
    leg_name?: string;
    hostel_ids?: string[];
    on_map: boolean;
    used: boolean | null;
  }>;
  used_links: Array<Record<string, unknown>>;
  diagram: Array<{ id: string; label: string }>;
  restu_overlay: { label: string; note: string; geojson: unknown } | null;
  detailed_routes_available: boolean;
  missing: string | null;
};

export type LegsPayload = {
  detailed_legs_available: boolean;
  missing: string | null;
  hostels: Array<{
    hostel_id: string;
    status?: string;
    groups: Array<Record<string, unknown>>;
    first: Record<string, number | null>;
    last: Record<string, number | null>;
  }>;
  groups: Array<Record<string, unknown>>;
};

export type BottlenecksPayload = {
  delays: Array<{
    place_id: string | null;
    cause: string | null;
    duration_s: number | null;
    affected_count: number | null;
  }>;
  unfinished: Array<{
    place_id: string | null;
    cause: string | null;
    student_count: number | null;
    status: string | null;
  }>;
  occupancy_peaks: Array<Record<string, unknown>>;
  destination: Record<string, unknown> | null;
};

export type OptimizerPayload = {
  message?: string;
  explain: string;
  status: string | null;
  timestamp?: string;
  measures?: Record<string, unknown> | null;
  records: Array<Record<string, unknown>>;
};

export type ReplaySegment = {
  start_ms: number;
  end_ms: number;
  type: "wait" | "transit";
  place_id?: string | null;
  leg_id?: string | null;
  waypoints: [number, number][];
};

export type StudentTrajectory = {
  id: string;
  hostel_id: string;
  student_count: number;
  color: string;
  segments: ReplaySegment[];
};
export type BusSegment = {
  start_ms: number;
  end_ms: number;
  type: "idle" | "boarding" | "transit_loaded" | "alighting" | "transit_empty_return" | "turnaround";
  place_id?: string | null;
  leg_id?: string | null;
  waypoints: [number, number][];
  passenger_count?: number;
};

export type BusTrajectory = {
  id: string;
  vehicle_type: "coach" | "electric";
  capacity: number;
  seated_capacity: number;
  usable_doors: number;
  segments: BusSegment[];
};


export type SectorMetrics = {
  headcount: number;
  avg_wait_s: number;
  avg_transit_s: number;
  status: "flowing" | "dense" | "bottleneck";
};

export type SectorTimelinePoint = {
  time_ms: number;
  sectors: Record<string, SectorMetrics>;
};

export type ReplaySector = {
  id: string;
  name: string;
  role: string;
  color: string;
  coordinates: [number, number];
  hostel_id?: string | null;
};

export type ReplayPayload = {
  dto_version: string;
  run_id: string | null;
  time_bounds: {
    start_ms: number;
    end_ms: number;
    clock_start: string;
    duration_s: number;
  };
  sectors: ReplaySector[];
  student_trajectories: StudentTrajectory[];
  bus_trajectories?: BusTrajectory[];
  sector_stats_timeline: SectorTimelinePoint[];
  has_trace: boolean;
  missing?: string | null;
};
