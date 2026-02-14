import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchReport, fetchReportList, type ReportDetailResponse, type ReportListItem, type ReportKind } from "../api";

function fmtTs(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

function kindLabel(kind: ReportKind) {
  return kind === "ride" ? "Ride" : "Progress";
}

export function App() {
  const [items, setItems] = useState<ReportListItem[]>([]);
  const [selected, setSelected] = useState<ReportListItem | null>(null);
  const [detail, setDetail] = useState<ReportDetailResponse | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    (async () => {
      setLoadingList(true);
      setError(null);
      try {
        const list = await fetchReportList();
        setItems(list);
        setSelected((prev) => prev ?? list[0] ?? null);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoadingList(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      if (!selected) {
        setDetail(null);
        return;
      }
      setLoadingDetail(true);
      setError(null);
      try {
        const d = await fetchReport(selected.kind, selected.activity_id);
        setDetail(d);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoadingDetail(false);
      }
    })();
  }, [selected?.kind, selected?.activity_id]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((it) => {
      const hay = [
        it.kind,
        it.activity_id,
        it.name ?? "",
        it.sport_type ?? "",
        it.prompt_version ?? "",
        it.model ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [items, query]);

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebarHeader">
          <div className="title">Ride Reports</div>
          <div className="subtitle">Strava ingest + AI analysis</div>
        </div>

        <div className="search">
          <input
            placeholder="Search (name, id, kind, prompt)..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="list">
          {loadingList ? <div className="muted">Loading…</div> : null}
          {filtered.map((it) => {
            const active = selected?.kind === it.kind && selected?.activity_id === it.activity_id;
            return (
              <button
                key={`${it.kind}:${it.activity_id}:${it.created_at}`}
                className={`row ${active ? "active" : ""}`}
                onClick={() => setSelected(it)}
              >
                <div className="rowTop">
                  <span className="pill">{kindLabel(it.kind)}</span>
                  <span className="rowTitle">{it.name ?? `activity_id=${it.activity_id}`}</span>
                </div>
                <div className="rowMeta">
                  <span>#{it.activity_id}</span>
                  <span>•</span>
                  <span>{fmtTs(it.created_at)}</span>
                </div>
                <div className="rowMeta">
                  <span className="mono">{it.prompt_version ?? ""}</span>
                  <span className="mono">{it.model ?? ""}</span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      <main className="content">
        <div className="contentHeader">
          <div className="contentTitle">
            {selected
              ? `${kindLabel(selected.kind)} • ${selected.name ?? `#${selected.activity_id}`}`
              : "Select a report"}
          </div>
          <div className="contentMeta">
            {selected ? (
              <>
                <span>{fmtTs(selected.created_at)}</span>
                <span className="dot">•</span>
                <span className="mono">{selected.prompt_version ?? ""}</span>
              </>
            ) : null}
          </div>
        </div>

        {error ? <div className="error">Error: {error}</div> : null}
        {loadingDetail ? <div className="muted">Loading report…</div> : null}

        {detail ? (
          <article className="markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail.markdown}</ReactMarkdown>
          </article>
        ) : (
          <div className="muted">No report selected.</div>
        )}
      </main>
    </div>
  );
}


