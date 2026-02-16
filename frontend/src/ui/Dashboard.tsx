import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReportListItem } from "../api";
import { fetchFredComparison } from "../api";

// ── Component ────────────────────────────────────────────────────────────────

export function Dashboard({ items }: { items: ReportListItem[] }) {
  const [comparison, setComparison] = useState<string | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  // Load Fred comparison on mount
  useEffect(() => {
    (async () => {
      setLoadingComparison(true);
      try {
        const data = await fetchFredComparison();
        setComparison(data.markdown);
      } catch (e) {
        console.error("Failed to load Fred comparison:", e);
        setComparison(null);
      } finally {
        setLoadingComparison(false);
      }
    })();
  }, []);

  return (
    <div className="dashboard">
      {loadingComparison && (
        <div className="dashLoading">Loading training analysis...</div>
      )}
      {comparison && (
        <div className="dashComparison">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {comparison}
          </ReactMarkdown>
        </div>
      )}
      {!loadingComparison && !comparison && (
        <div className="dashEmpty">No training analysis available</div>
      )}
    </div>
  );
}
