// Typed API client for the HEALTH-01 backend (same-origin /api/v1 via nginx or Vite proxy).

export const API = "/api/v1";
const TOKEN_KEY = "hmt.token";
const USER_KEY = "hmt.user";

export type Role = "astronaut" | "flight_surgeon" | "mission_control";
export interface User { username: string; display_name: string; role: Role; astronaut_id: string | null }

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function getStoredUser(): User | null {
  try { const s = localStorage.getItem(USER_KEY); return s ? JSON.parse(s) : null; } catch { return null; }
}
export function storeSession(token: string | null, user: User | null) {
  try {
    if (token && user) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); }
    else { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
  } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(API + path, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });
  if (res.status === 401 && path !== "/auth/login" && path !== "/auth/public" && path !== "/auth/demo-switch") {
    storeSession(null, null);
    window.dispatchEvent(new Event("hmt:logout"));
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  return res.json();
}

// ---- shared types -----------------------------------------------------------
export interface Evidence { metric: string; value: number | null; unit: string; baseline_median?: number; z?: number; note?: string }
export interface Alert {
  id: number; astronaut_id: string | null; severity: "info" | "caution" | "warning"; category: string; title: string;
  message: string; evidence: Evidence[]; recommendation: string; source: string; data_class: string;
  observed_at: string; created_at: string; acknowledged: boolean;
}
export interface MetricSummary {
  metric: string; label: string; unit: string; status: string; concern?: boolean; latest?: number; latest_date?: string;
  avg_7d?: number; baseline_median?: number; baseline_range?: [number, number]; baseline_days?: number;
  trend_per_day_7d?: number; delta_vs_baseline_pct?: number | null;
}
export interface Domain { status: string; metrics: MetricSummary[]; concerns: string[]; [k: string]: any }
export interface Summary {
  astronaut: { id: string; callsign: string; name: string; role: string; data_class?: string };
  as_of: string | null; last_fetched_from_phone?: string | null; days_of_data: number; domains: Record<string, Domain>; unavailable_metrics: string[];
}
export interface CrewMember {
  id: string; callsign: string; name: string; role: string; data_class: string; as_of: string | null;
  last_fetched_from_phone?: string | null;
  key_metrics: Record<string, { latest: number; status: string; unit: string }>; open_alerts: number;
  domain_status: Record<string, string>;
}
export interface Contributor { metric: string; label: string; value: number; baseline_median: number; baseline_range: [number, number]; baseline_days: number; z: number; direction: string }
export interface ForecastSeries {
  metric: string; status: string; points?: { date: string; value: number; lower_80: number; upper_80: number }[];
  recent_mean_7d?: number; projected_change?: number; trend_direction?: string; backtest?: any; required?: number; points_count?: number;
}
export interface Predictions {
  astronaut_id: string; as_of: string | null; disclaimer: string;
  anomaly: { model_version: string; status?: string; latest?: any; history?: { date: string; score: number | null; is_anomaly: boolean; percentile?: number }[]; limitations?: string[] };
  fatigue: { model_version: string; status?: string; fatigue_estimate?: number; interval_80?: [number, number]; category?: string; inputs?: Record<string, number | null>; missing?: string[]; scale?: string; limitations?: string[] };
  forecasts: { model_version: string; series: ForecastSeries[]; limitations: string[] };
}

export const METRIC_LABEL: Record<string, string> = {
  heart_rate: "Heart rate", resting_heart_rate: "Resting HR", hrv_sdnn: "HRV (SDNN)", hrv_rmssd: "HRV (RMSSD)",
  sleep_duration: "Sleep", sleep_efficiency: "Sleep efficiency", sleep_midpoint: "Sleep midpoint", steps: "Steps",
  exercise_minutes: "Exercise", fatigue_score: "Fatigue", stress_score: "Stress", mood_score: "Mood", workload_tlx: "Workload",
  reaction_time: "Reaction time", cabin_co2: "CO₂", cabin_temperature: "Temperature", cabin_humidity: "Humidity",
  cabin_pressure: "Pressure", radiation_dose_rate: "Radiation", blood_pressure_systolic: "Systolic BP",
  blood_pressure_diastolic: "Diastolic BP", oxygen_saturation: "SpO₂", active_energy: "Active energy",
  body_temperature: "Body temperature", blood_glucose: "Blood glucose", body_mass: "Body mass",
};
