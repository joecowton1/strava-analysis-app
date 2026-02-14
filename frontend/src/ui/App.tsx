import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchMe,
  fetchReport,
  fetchReportList,
  getLoginUrl,
  logout,
  storeToken,
  type ReportDetailResponse,
  type ReportListItem,
  type ReportKind,
  type User,
} from "../api";

function fmtTs(ts: number) {
  try {
    return new Date(ts * 1000).toLocaleString();
  } catch {
    return String(ts);
  }
}

function fmtDate(iso?: string | null) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function fmtTime(iso?: string | null) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
}

function kindLabel(kind: ReportKind) {
  return kind === "ride" ? "Ride" : "Progress";
}

function fmtDist(m?: number | null) {
  if (m == null) return null;
  return (m / 1000).toFixed(1) + " km";
}

function fmtElev(m?: number | null) {
  if (m == null) return null;
  return Math.round(m) + " m";
}

function RideCard({
  item,
  onClick,
}: {
  item: ReportListItem;
  onClick: () => void;
}) {
  const date = fmtDate(item.start_date);
  const time = fmtTime(item.start_date);
  const dist = fmtDist(item.distance);
  const elev = fmtElev(item.total_elevation_gain);

  return (
    <button className="card" onClick={onClick}>
      <div className="cardHeader">
        <span className="cardTitle">
          {item.name ?? `Activity #${item.activity_id}`}
        </span>
        <span className="cardSport">{item.sport_type ?? "Ride"}</span>
      </div>
      <div className="cardMeta">
        {date && (
          <span className="cardDate">
            {date}
            {time ? ` at ${time}` : ""}
          </span>
        )}
      </div>
      {(dist || elev) && (
        <div className="cardStats">
          {dist && <span className="cardStat">{dist}</span>}
          {elev && (
            <span className="cardStat">
              <svg className="cardStatIcon" viewBox="0 0 16 16" width="12" height="12" fill="currentColor">
                <path d="M1 14L6 4l3 5 2-2 4 7H1z" />
              </svg>
              {elev}
            </span>
          )}
        </div>
      )}
    </button>
  );
}

function LoginPage() {
  // Check for auth errors in URL
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth_error");

  return (
    <div className="loginPage">
      <div className="loginCard">
        <div className="loginLogo">Strava Analysis</div>
        <div className="loginSubtitle">
          AI-powered ride analysis and progress tracking
        </div>

        {authError === "not_allowed" && (
          <div className="error loginError">
            Your Strava account is not on the approved list. Contact the admin to
            get access.
          </div>
        )}
        {authError && authError !== "not_allowed" && (
          <div className="error loginError">
            Authentication failed. Please try again.
          </div>
        )}

        <a href={getLoginUrl()} className="stravaBtn">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169" />
          </svg>
          Connect with Strava
        </a>
      </div>
    </div>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [items, setItems] = useState<ReportListItem[]>([]);
  const [selected, setSelected] = useState<ReportListItem | null>(null);
  const [detail, setDetail] = useState<ReportDetailResponse | null>(null);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [latestProgress, setLatestProgress] = useState<ReportDetailResponse | null>(null);
  const [loadingProgress, setLoadingProgress] = useState(false);

  // Check auth on mount — extract token from URL if present (OAuth redirect)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    if (token) {
      storeToken(token);
      // Clean the token out of the URL so it isn't bookmarked / shared
      params.delete("token");
      const clean = params.toString();
      window.history.replaceState({}, "", window.location.pathname + (clean ? `?${clean}` : ""));
    }

    fetchMe().then((u) => {
      setUser(u);
      setAuthChecked(true);
    });
  }, []);

  // Load reports once authenticated
  useEffect(() => {
    if (!user) return;
    (async () => {
      setLoadingList(true);
      setError(null);
      try {
        const list = await fetchReportList();
        setItems(list);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      } finally {
        setLoadingList(false);
      }
    })();
  }, [user]);

  // Auto-load latest progress summary content
  const latestProgressItem = useMemo(() => {
    const all = items
      .filter((it) => it.kind === "progress")
      .sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    return all[0] ?? null;
  }, [items]);

  useEffect(() => {
    if (!latestProgressItem) {
      setLatestProgress(null);
      return;
    }
    (async () => {
      setLoadingProgress(true);
      try {
        const d = await fetchReport(latestProgressItem.kind, latestProgressItem.activity_id);
        setLatestProgress(d);
      } catch {
        // silently ignore — progress just won't show
      } finally {
        setLoadingProgress(false);
      }
    })();
  }, [latestProgressItem?.activity_id]);

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

  const rides = useMemo(
    () =>
      filtered
        .filter((it) => it.kind === "ride")
        .sort((a, b) => {
          const da = a.start_date ? new Date(a.start_date).getTime() : 0;
          const db = b.start_date ? new Date(b.start_date).getTime() : 0;
          return db - da;
        }),
    [filtered]
  );
  const progressCount = useMemo(
    () => items.filter((it) => it.kind === "progress").length,
    [items]
  );

  const closeModal = () => {
    setSelected(null);
    setDetail(null);
  };

  const handleLogout = async () => {
    await logout();
    setUser(null);
    setItems([]);
  };

  // Show nothing until auth check completes
  if (!authChecked) {
    return (
      <div className="shell">
        <div className="loadingBar">
          <div className="loadingBarInner" />
        </div>
      </div>
    );
  }

  // Show login page if not authenticated
  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="shell">
      {/* Top bar */}
      <header className="topbar">
        <div className="topbarLeft">
          <span className="logo">Strava Analysis</span>
          <span className="logoBeta">beta</span>
        </div>
        <div className="topbarCenter">
          <input
            className="searchInput"
            placeholder="Search rides..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="topbarRight">
          <span className="stat">
            <span className="statNum">{rides.length}</span> rides
          </span>
          <span className="statSep" />
          <span className="stat">
            <span className="statNum">{progressCount}</span> summaries
          </span>
          <span className="statSep" />
          <span className="userName">{user.name || `Athlete ${user.athlete_id}`}</span>
          <button className="logoutBtn" onClick={handleLogout}>
            Log out
          </button>
        </div>
      </header>

      {/* Error banner */}
      {error && !selected && (
        <div className="errorBanner">Error: {error}</div>
      )}

      {/* Loading state */}
      {loadingList && (
        <div className="loadingBar">
          <div className="loadingBarInner" />
        </div>
      )}

      {/* Two-column layout */}
      <div className="columns">
        {/* Rides column */}
        <section className="column">
          <div className="columnHeader">
            <h2 className="columnTitle">Rides</h2>
            <span className="columnCount">{rides.length}</span>
          </div>
          <div className="columnList">
            {rides.length === 0 && !loadingList && (
              <div className="emptyState">
                <div className="emptyIcon">&#x1F6B4;</div>
                <div className="emptyText">No rides yet</div>
                <div className="emptyHint">
                  Rides will appear here as the worker processes them
                </div>
              </div>
            )}
            {rides.map((it) => (
              <RideCard
                key={`ride:${it.activity_id}:${it.created_at}`}
                item={it}
                onClick={() => setSelected(it)}
              />
            ))}
          </div>
        </section>

        {/* Latest progress summary */}
        <section className="column">
          <div className="columnHeader">
            <h2 className="columnTitle">Latest Summary</h2>
            {latestProgressItem && (
              <span className="columnMeta">{fmtTs(latestProgressItem.created_at)}</span>
            )}
          </div>
          <div className="columnBody">
            {!latestProgressItem && !loadingList && (
              <div className="emptyState">
                <div className="emptyIcon">&#x1F4CA;</div>
                <div className="emptyText">No summary yet</div>
                <div className="emptyHint">
                  A progress summary is generated alongside ride analyses
                </div>
              </div>
            )}
            {loadingProgress && (
              <div className="muted loadingReport">Loading summary…</div>
            )}
            {latestProgress && (
              <article className="markdown progressInline">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {latestProgress.markdown}
                </ReactMarkdown>
              </article>
            )}
          </div>
        </section>
      </div>

      {/* Detail modal */}
      {selected && (
        <div className="modalOverlay" onClick={closeModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modalHeader">
              <div>
                <div className="modalTitle">
                  <span className={`modalPill ${selected.kind}`}>
                    {kindLabel(selected.kind)}
                  </span>
                  {selected.name ?? `#${selected.activity_id}`}
                </div>
                <div className="modalMeta">
                  <span>{fmtTs(selected.created_at)}</span>
                  {selected.prompt_version && (
                    <>
                      <span className="dot">·</span>
                      <span className="mono">{selected.prompt_version}</span>
                    </>
                  )}
                  {selected.model && (
                    <>
                      <span className="dot">·</span>
                      <span className="mono">{selected.model}</span>
                    </>
                  )}
                </div>
              </div>
              <button className="modalClose" onClick={closeModal}>
                &times;
              </button>
            </div>

            <div className="modalBody">
              {error && <div className="error">Error: {error}</div>}
              {loadingDetail && (
                <div className="muted loadingReport">Loading report…</div>
              )}
              {detail && (
                <article className="markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {detail.markdown}
                  </ReactMarkdown>
                </article>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
