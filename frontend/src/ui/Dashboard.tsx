import { useMemo, useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { ReportListItem } from "../api";
import { fetchFredComparison } from "../api";

// ── Types ────────────────────────────────────────────────────────────────────

type MetricKey =
  | "distance"
  | "elevation"
  | "rides"
  | "time"
  | "avg_power"
  | "avg_hr";

const METRIC_OPTIONS: { key: MetricKey; label: string; unit: string }[] = [
  { key: "distance", label: "Distance", unit: "km" },
  { key: "elevation", label: "Elevation", unit: "m" },
  { key: "rides", label: "Rides", unit: "" },
  { key: "time", label: "Time", unit: "hrs" },
  { key: "avg_power", label: "Avg Power", unit: "W" },
  { key: "avg_hr", label: "Avg HR", unit: "bpm" },
];

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];
const FRED_WHITTON_WEEK = 19; // May 9th is typically week 19
const YEAR_COLORS = [
  "#3b82f6", // blue
  "#10b981", // green
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // purple
  "#ec4899", // pink
  "#06b6d4", // cyan
  "#84cc16", // lime
];

// ── Helpers ──────────────────────────────────────────────────────────────────

function getWeekNumber(date: Date): { year: number; week: number } {
  // Get the week number (1-52/53) for a given date
  const firstDayOfYear = new Date(date.getFullYear(), 0, 1);
  const pastDaysOfYear = (date.getTime() - firstDayOfYear.getTime()) / 86400000;
  const week = Math.ceil((pastDaysOfYear + firstDayOfYear.getDay() + 1) / 7);
  return { year: date.getFullYear(), week };
}

function parseWeek(iso: string): { year: number; week: number } | null {
  try {
    const d = new Date(iso);
    return getWeekNumber(d);
  } catch {
    return null;
  }
}

// ── Component ────────────────────────────────────────────────────────────────

export function Dashboard({ items }: { items: ReportListItem[] }) {
  const [metric, setMetric] = useState<MetricKey>("distance");
  const [comparison, setComparison] = useState<string | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  const rides = useMemo(
    () => items.filter((it) => it.kind === "ride"),
    [items]
  );

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

  // ── Summary stats ────────────────────────────────────────────────────────
  const summary = useMemo(() => {
    let totalDist = 0;
    let totalElev = 0;
    let totalTime = 0;
    let powerSum = 0;
    let powerCount = 0;
    let hrSum = 0;
    let hrCount = 0;

    for (const r of rides) {
      totalDist += r.distance ?? 0;
      totalElev += r.total_elevation_gain ?? 0;
      totalTime += r.moving_time ?? 0;
      if (r.average_watts) {
        powerSum += r.average_watts;
        powerCount++;
      }
      if (r.average_heartrate) {
        hrSum += r.average_heartrate;
        hrCount++;
      }
    }

    return {
      distance: (totalDist / 1000).toFixed(0),
      elevation: Math.round(totalElev).toLocaleString(),
      rides: rides.length,
      time: (totalTime / 3600).toFixed(1),
      avgPower: powerCount ? Math.round(powerSum / powerCount) : null,
      avgHr: hrCount ? Math.round(hrSum / hrCount) : null,
    };
  }, [rides]);

  // ── Year-over-year weekly data ──────────────────────────────────────────
  const { chartData, years } = useMemo(() => {
    // Group rides by year+week
    const buckets: Record<string, ReportListItem[]> = {};
    const yearSet = new Set<number>();
    let maxWeek = 52;

    for (const r of rides) {
      if (!r.start_date) continue;
      const parsed = parseWeek(r.start_date);
      if (!parsed) continue;
      yearSet.add(parsed.year);
      maxWeek = Math.max(maxWeek, parsed.week);
      const key = `${parsed.year}-${parsed.week}`;
      (buckets[key] ??= []).push(r);
    }

    const sortedYears = [...yearSet].sort();

    // Build chart rows: one per week (1-52 or 53)
    const data = Array.from({ length: maxWeek }, (_, i) => {
      const week = i + 1;
      const row: Record<string, string | number> = { week: `W${week}` };

      for (const yr of sortedYears) {
        const group = buckets[`${yr}-${week}`] ?? [];
        let val = 0;

        switch (metric) {
          case "distance":
            val = group.reduce((s, r) => s + (r.distance ?? 0), 0) / 1000;
            break;
          case "elevation":
            val = group.reduce((s, r) => s + (r.total_elevation_gain ?? 0), 0);
            break;
          case "rides":
            val = group.length;
            break;
          case "time":
            val =
              group.reduce((s, r) => s + (r.moving_time ?? 0), 0) / 3600;
            break;
          case "avg_power": {
            const pw = group.filter((r) => r.average_watts);
            val = pw.length
              ? pw.reduce((s, r) => s + (r.average_watts ?? 0), 0) / pw.length
              : 0;
            break;
          }
          case "avg_hr": {
            const hr = group.filter((r) => r.average_heartrate);
            val = hr.length
              ? hr.reduce((s, r) => s + (r.average_heartrate ?? 0), 0) /
                hr.length
              : 0;
            break;
          }
        }

        row[String(yr)] = Math.round(val * 10) / 10;
      }

      return row;
    });

    return { chartData: data, years: sortedYears };
  }, [rides, metric]);

  const activeOption = METRIC_OPTIONS.find((o) => o.key === metric)!;

  return (
    <div className="dashboard">
      {/* ── Summary cards ── */}
      <div className="dashCards">
        <div className="dashCard">
          <div className="dashCardValue">{summary.distance}</div>
          <div className="dashCardLabel">km</div>
        </div>
        <div className="dashCard">
          <div className="dashCardValue">{summary.elevation}</div>
          <div className="dashCardLabel">m elev</div>
        </div>
        <div className="dashCard">
          <div className="dashCardValue">{summary.rides}</div>
          <div className="dashCardLabel">rides</div>
        </div>
        <div className="dashCard">
          <div className="dashCardValue">{summary.time}</div>
          <div className="dashCardLabel">hours</div>
        </div>
        {summary.avgPower && (
          <div className="dashCard">
            <div className="dashCardValue">{summary.avgPower}</div>
            <div className="dashCardLabel">avg W</div>
          </div>
        )}
        {summary.avgHr && (
          <div className="dashCard">
            <div className="dashCardValue">{summary.avgHr}</div>
            <div className="dashCardLabel">avg bpm</div>
          </div>
        )}
      </div>

      {/* ── Metric toggles ── */}
      <div className="dashSection">
        <h3 className="dashSectionTitle">Year-over-Year</h3>
        <div className="dashToggles">
          {METRIC_OPTIONS.map((opt) => (
            <button
              key={opt.key}
              className={`dashToggle ${metric === opt.key ? "active" : ""}`}
              onClick={() => setMetric(opt.key)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Chart ── */}
      {years.length === 0 ? (
        <div className="dashEmpty">No ride data yet</div>
      ) : (
        <div className="dashChart">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={chartData}
              margin={{ top: 24, right: 12, bottom: 0, left: 0 }}
            >
              <XAxis
                dataKey="week"
                tick={{ fontSize: 12, fill: "#6d6d78" }}
                axisLine={{ stroke: "#e8e8ed" }}
                tickLine={false}
                interval={3}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#6d6d78" }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid #e8e8ed",
                  borderRadius: 8,
                  fontSize: 13,
                }}
                formatter={(value: number | undefined) =>
                  [`${value ?? 0} ${activeOption.unit}`, ""]
                }
              />
                <ReferenceLine
                  x={`W${FRED_WHITTON_WEEK}`}
                  stroke="#fc4c02"
                  strokeWidth={2}
                  label={{ value: "Fred Whitton", fill: "#fc4c02", fontSize: 11, position: "top" }}
                />
              <Legend
                wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
              />
              {years.map((yr, i) => (
                <Line
                  key={yr}
                  type="linear"
                  dataKey={String(yr)}
                  name={String(yr)}
                  stroke={YEAR_COLORS[i % YEAR_COLORS.length]}
                  strokeWidth={2.5}
                  dot={{ r: 4, strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Fred Comparison Summary ── */}
      <div className="dashSection">
        <h3 className="dashSectionTitle">Build-up Analysis</h3>
      </div>
      {loadingComparison && (
        <div className="dashLoading">Loading comparison...</div>
      )}
      {comparison && (
        <div className="dashComparison">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {comparison}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
