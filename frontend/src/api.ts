export type ReportKind = "ride" | "progress";

export type ReportListItem = {
  kind: ReportKind;
  activity_id: number;
  created_at: number;
  model?: string | null;
  prompt_version?: string | null;
  name?: string | null;
  start_date?: string | null;
  sport_type?: string | null;
  distance?: number | null;
  total_elevation_gain?: number | null;
  moving_time?: number | null;
  average_speed?: number | null;
  average_watts?: number | null;
  average_heartrate?: number | null;
};

export type ReportListResponse = { items: ReportListItem[] };

export type ReportDetailResponse = {
  kind: ReportKind;
  activity_id: number;
  created_at: number;
  model?: string | null;
  prompt_version?: string | null;
  markdown: string;
};

export type User = {
  athlete_id: number;
  name?: string | null;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "strava_token";

// ── Token helpers ────────────────────────────────────────────────────────────

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Auth API ─────────────────────────────────────────────────────────────────

/** Check if the user is authenticated. Returns User or null. */
export async function fetchMe(): Promise<User | null> {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const r = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    if (!r.ok) {
      clearToken();
      return null;
    }
    return (await r.json()) as User;
  } catch {
    return null;
  }
}

/** Get the URL to redirect to for Strava OAuth. */
export function getLoginUrl(): string {
  return `${API_BASE}/auth/strava`;
}

/** Log out (clear token). */
export async function logout(): Promise<void> {
  clearToken();
}

// ── Data API ─────────────────────────────────────────────────────────────────

export async function fetchReportList(): Promise<ReportListItem[]> {
  const r = await fetch(`${API_BASE}/api/reports`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`Failed to load reports (${r.status})`);
  const data = (await r.json()) as ReportListResponse;
  return data.items;
}

export async function fetchReport(kind: ReportKind, activityId: number): Promise<ReportDetailResponse> {
  const r = await fetch(`${API_BASE}/api/reports/${kind}/${activityId}`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`Failed to load report (${r.status})`);
  return (await r.json()) as ReportDetailResponse;
}

export async function triggerBackfill(): Promise<{ queued: number; skipped: number; total_fetched: number }> {
  const r = await fetch(`${API_BASE}/api/backfill`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!r.ok) throw new Error(`Backfill failed (${r.status})`);
  return await r.json();
}

export async function fetchFredComparison(): Promise<{ markdown: string; model?: string; prompt_version?: string }> {
  const r = await fetch(`${API_BASE}/api/fred-comparison`, { headers: authHeaders() });
  if (!r.ok) throw new Error(`Failed to load Fred comparison (${r.status})`);
  return await r.json();
}
