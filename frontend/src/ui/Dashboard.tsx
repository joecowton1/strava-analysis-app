import { useMemo, useState } from "react";
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
const FRED_WHITTON_MONTH = 5; // May
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

function parseMonth(iso: string): { year: number; month: number } | null {
  try {
    const d = new Date(iso);
    return { year: d.getFullYear(), month: d.getMonth() + 1 }; // 1-indexed
  } catch {
    return null;
  }
}

// ── Component ────────────────────────────────────────────────────────────────

export function Dashboard({ items }: { items: ReportListItem[] }) {
  const [metric, setMetric] = useState<MetricKey>("distance");

  const rides = useMemo(
    () => items.filter((it) => it.kind === "ride"),
    [items]
  );

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

  // ── Year-over-year monthly data ──────────────────────────────────────────
  const { chartData, years } = useMemo(() => {
    // Group rides by year+month
    const buckets: Record<string, ReportListItem[]> = {};
    const yearSet = new Set<number>();

    for (const r of rides) {
      if (!r.start_date) continue;
      const parsed = parseMonth(r.start_date);
      if (!parsed) continue;
      yearSet.add(parsed.year);
      const key = `${parsed.year}-${parsed.month}`;
      (buckets[key] ??= []).push(r);
    }

    const sortedYears = [...yearSet].sort();

    // Build chart rows: one per month (1-12)
    const data = MONTH_LABELS.map((label, i) => {
      const month = i + 1;
      const row: Record<string, string | number> = { month: label };

      for (const yr of sortedYears) {
        const group = buckets[`${yr}-${month}`] ?? [];
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
        <div className="dashEmpty">No ride data for Jan-May yet</div>
      ) : (
        <div className="dashChart">
          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={chartData}
              margin={{ top: 24, right: 12, bottom: 0, left: 0 }}
            >
              <XAxis
                dataKey="month"
                tick={{ fontSize: 12, fill: "#6d6d78" }}
                axisLine={{ stroke: "#e8e8ed" }}
                tickLine={false}
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
                x={MONTH_LABELS[FRED_WHITTON_MONTH - 1]}
                stroke="#fc4c02"
                strokeDasharray="4 4"
                strokeWidth={1.5}
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
    </div>
  );
}
