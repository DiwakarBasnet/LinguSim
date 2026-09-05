"use client";

import { useMemo, useState } from "react";
import type { SessionSummary } from "@/lib/types";

// Categorical palette, slots 1-5 (blue/orange/aqua/yellow/magenta) — this
// order passes the adjacent-pair CVD/contrast validator for line charts.
// Source: dataviz skill's references/palette.md.
const SERIES = [
  { key: "overall_score", label: "Overall", light: "#2a78d6", dark: "#3987e5" },
  { key: "grammar", label: "Grammar", light: "#eb6834", dark: "#d95926" },
  { key: "vocabulary", label: "Vocabulary", light: "#1baf7a", dark: "#199e70" },
  { key: "fluency", label: "Fluency", light: "#eda100", dark: "#c98500" },
  { key: "hesitation", label: "Hesitation", light: "#e87ba4", dark: "#d55181" },
] as const;

const WIDTH = 640;
const HEIGHT = 280;
const PAD = { top: 16, right: 16, bottom: 28, left: 36 };
const PLOT_W = WIDTH - PAD.left - PAD.right;
const PLOT_H = HEIGHT - PAD.top - PAD.bottom;

function xFor(index: number, count: number): number {
  if (count <= 1) return PAD.left + PLOT_W / 2;
  return PAD.left + (index / (count - 1)) * PLOT_W;
}

function yFor(score: number): number {
  return PAD.top + PLOT_H * (1 - score / 100);
}

export default function ProgressChart({ sessions }: { sessions: SessionSummary[] }) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);

  const points = useMemo(
    () =>
      sessions.map((s) => ({
        date: new Date(s.created_at),
        overall_score: s.evaluation.overall_score,
        grammar: s.evaluation.grammar,
        vocabulary: s.evaluation.vocabulary,
        fluency: s.evaluation.fluency,
        hesitation: s.evaluation.hesitation,
      })),
    [sessions]
  );

  if (points.length === 0) {
    return <p className="text-sm text-black/60 dark:text-white/60">No sessions yet.</p>;
  }

  const active = activeIndex !== null ? points[activeIndex] : null;
  const activeSession = activeIndex !== null ? sessions[activeIndex] : null;

  const handleMove = (e: React.PointerEvent<SVGRectElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const relativeX = ((e.clientX - rect.left) / rect.width) * WIDTH;
    const fraction = Math.min(1, Math.max(0, (relativeX - PAD.left) / PLOT_W));
    const index = Math.round(fraction * (points.length - 1));
    setActiveIndex(Math.min(points.length - 1, Math.max(0, index)));
  };

  const seriesVar = (key: (typeof SERIES)[number]["key"]) => `var(--series-${key})`;

  return (
    <div
      className="progress-chart flex flex-col gap-3"
      style={Object.fromEntries(SERIES.map((s) => [`--series-${s.key}`, s.light])) as React.CSSProperties}
    >
      <style>{`
        @media (prefers-color-scheme: dark) {
          .progress-chart { ${SERIES.map((s) => `--series-${s.key}: ${s.dark};`).join(" ")} }
        }
      `}</style>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {SERIES.map((series) => (
          <div key={series.key} className="flex items-center gap-1.5">
            <span
              className="inline-block h-0.5 w-4 rounded-full"
              style={{ backgroundColor: seriesVar(series.key) }}
            />
            <span className="text-black/60 dark:text-white/60">{series.label}</span>
          </div>
        ))}
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className="w-full"
          role="img"
          aria-label="Progress trend across sessions"
          onPointerLeave={() => setActiveIndex(null)}
        >
          {[0, 25, 50, 75, 100].map((tick) => (
            <g key={tick}>
              <line
                x1={PAD.left}
                x2={WIDTH - PAD.right}
                y1={yFor(tick)}
                y2={yFor(tick)}
                stroke="currentColor"
                className="text-black/10 dark:text-white/10"
                strokeWidth={1}
              />
              <text
                x={PAD.left - 8}
                y={yFor(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                className="fill-black/40 text-[10px] dark:fill-white/40"
              >
                {tick}
              </text>
            </g>
          ))}

          {SERIES.map((series) => {
            const d = points
              .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i, points.length)} ${yFor(p[series.key])}`)
              .join(" ");
            return (
              <path
                key={series.key}
                d={d}
                fill="none"
                stroke={seriesVar(series.key)}
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })}

          {activeIndex !== null && (
            <line
              x1={xFor(activeIndex, points.length)}
              x2={xFor(activeIndex, points.length)}
              y1={PAD.top}
              y2={HEIGHT - PAD.bottom}
              stroke="currentColor"
              className="text-black/30 dark:text-white/30"
              strokeWidth={1}
            />
          )}

          {SERIES.map((series) =>
            points.map((p, i) => (
              <circle
                key={`${series.key}-${i}`}
                cx={xFor(i, points.length)}
                cy={yFor(p[series.key])}
                r={activeIndex === i ? 4 : 3}
                fill={seriesVar(series.key)}
              />
            ))
          )}

          <rect
            x={PAD.left}
            y={PAD.top}
            width={PLOT_W}
            height={PLOT_H}
            fill="transparent"
            onPointerMove={handleMove}
            tabIndex={0}
            onFocus={() => setActiveIndex(0)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") setActiveIndex((i) => Math.min(points.length - 1, (i ?? 0) + 1));
              if (e.key === "ArrowLeft") setActiveIndex((i) => Math.max(0, (i ?? 0) - 1));
            }}
          />
        </svg>

        {active && activeSession && (
          <div className="pointer-events-none absolute left-2 top-2 rounded-md border border-black/10 bg-white/95 p-2 text-xs shadow-sm dark:border-white/10 dark:bg-black/90">
            <div className="mb-1 font-medium">{activeSession.scenario_title}</div>
            {SERIES.map((series) => (
              <div key={series.key} className="flex items-center gap-2">
                <span className="inline-block h-0.5 w-3" style={{ backgroundColor: seriesVar(series.key) }} />
                <span className="text-black/60 dark:text-white/60">{series.label}</span>
                <span className="ml-auto font-semibold tabular-nums">{active[series.key]}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <button onClick={() => setShowTable((v) => !v)} className="self-start text-xs underline">
        {showTable ? "Hide" : "Show"} data table
      </button>

      {showTable && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-black/50 dark:text-white/50">
                <th className="py-1 pr-3">Date</th>
                <th className="py-1 pr-3">Scenario</th>
                {SERIES.map((s) => (
                  <th key={s.key} className="py-1 pr-3">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map((s, i) => (
                <tr key={s.id} className="border-t border-black/5 dark:border-white/5">
                  <td className="py-1 pr-3 tabular-nums">{points[i].date.toLocaleDateString()}</td>
                  <td className="py-1 pr-3">{s.scenario_title}</td>
                  {SERIES.map((series) => (
                    <td key={series.key} className="py-1 pr-3 tabular-nums">
                      {points[i][series.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
