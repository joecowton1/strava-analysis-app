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

/** Check if the user is authenticated. Returns User or null. */
export async function fetchMe(): Promise<User | null> {
  try {
    const r = await fetch(`${API_BASE}/auth/me`, { credentials: "include" });
    if (!r.ok) return null;
    return (await r.json()) as User;
  } catch {
    return null;
  }
}

/** Get the URL to redirect to for Strava OAuth. */
export function getLoginUrl(): string {
  return `${API_BASE}/auth/strava`;
}

/** Log out (clear cookie). */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function fetchReportList(): Promise<ReportListItem[]> {
  const r = await fetch(`${API_BASE}/api/reports`, { credentials: "include" });
  if (!r.ok) throw new Error(`Failed to load reports (${r.status})`);
  const data = (await r.json()) as ReportListResponse;
  return data.items;
}

export async function fetchReport(kind: ReportKind, activityId: number): Promise<ReportDetailResponse> {
  const r = await fetch(`${API_BASE}/api/reports/${kind}/${activityId}`, { credentials: "include" });
  if (!r.ok) throw new Error(`Failed to load report (${r.status})`);
  return (await r.json()) as ReportDetailResponse;
}

export async function triggerBackfill(): Promise<{ queued: number; skipped: number; total_fetched: number }> {
  const r = await fetch(`${API_BASE}/api/backfill`, {
    method: "POST",
    credentials: "include",
  });
  if (!r.ok) throw new Error(`Backfill failed (${r.status})`);
  return await r.json();
}
