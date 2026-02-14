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

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function fetchReportList(): Promise<ReportListItem[]> {
  const r = await fetch(`${API_BASE}/api/reports`);
  if (!r.ok) throw new Error(`Failed to load reports (${r.status})`);
  const data = (await r.json()) as ReportListResponse;
  return data.items;
}

export async function fetchReport(kind: ReportKind, activityId: number): Promise<ReportDetailResponse> {
  const r = await fetch(`${API_BASE}/api/reports/${kind}/${activityId}`);
  if (!r.ok) throw new Error(`Failed to load report (${r.status})`);
  return (await r.json()) as ReportDetailResponse;
}


