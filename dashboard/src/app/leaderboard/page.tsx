"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const GRADE_META: Record<string, { color: string; bg: string; label: string }> = {
  "A+": { color: "#10b981", bg: "#10b98118", label: "Excellent" },
  "A":  { color: "#34d399", bg: "#34d39918", label: "Great" },
  "B":  { color: "#60a5fa", bg: "#60a5fa18", label: "Good" },
  "C":  { color: "#fbbf24", bg: "#fbbf2418", label: "Fair" },
  "D":  { color: "#f97316", bg: "#f9731618", label: "Poor" },
  "F":  { color: "#ef4444", bg: "#ef444418", label: "Failing" },
};

const MEDALS = ["🥇", "🥈", "🥉"];

const DIM_COLORS: Record<string, string> = {
  discoverability: "#6366f1",
  parseability:    "#8b5cf6",
  task_completion: "#10b981",
  friction:        "#f59e0b",
};

const DIMS = [
  { key: "discoverability", short: "Disc", baseline: 68 },
  { key: "parseability",    short: "Parse", baseline: 52 },
  { key: "task_completion", short: "Task",  baseline: 57 },
  { key: "friction",        short: "Fric",  baseline: 63 },
];

function MiniBar({ val, baseline, color, delay }: { val: number; baseline: number; color: string; delay: number }) {
  return (
    <div className="relative h-1.5 bg-[#1e1e2e] rounded-full overflow-visible w-16">
      {/* baseline marker */}
      <div
        className="absolute top-0 bottom-0 w-px bg-gray-600 z-10"
        style={{ left: `${baseline}%` }}
      />
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.min(val, 100)}%` }}
        transition={{ duration: 0.7, delay, ease: "easeOut" }}
        className="h-full rounded-full"
        style={{ background: color }}
      />
    </div>
  );
}

export default function LeaderboardPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/leaderboard?limit=30`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a0f]">
      <nav className="border-b border-[#1e1e2e] px-6 py-4 flex items-center gap-4">
        <a href="/" className="font-mono text-indigo-400 font-bold text-lg">AgentProbe</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400 font-mono text-sm">leaderboard</span>
        <a href="/" className="ml-auto px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-mono rounded-lg transition-colors">
          + Run audit
        </a>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-10">
        <div className="mb-8">
          <h1 className="text-3xl font-black text-white tracking-tight">Agentic Readiness Leaderboard</h1>
          <p className="text-gray-500 text-sm mt-1.5 font-mono">
            Real browser agent results. Gray tick = industry average. Publicly audited only.
          </p>
        </div>

        {/* Industry baseline strip */}
        {data?.industry_baselines && (
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-8">
            {Object.entries(data.industry_baselines)
              .filter(([k]) => k !== "composite")
              .map(([key, val]) => (
                <div key={key} className="bg-[#111118] border border-[#1e1e2e] rounded-lg p-2.5 text-center">
                  <p className="text-[10px] text-gray-600 font-mono mb-0.5 capitalize">{key.replace("_", " ")}</p>
                  <p className="text-base font-bold text-gray-300">{(val as number).toFixed(0)}</p>
                  <p className="text-[9px] text-gray-700 font-mono">avg</p>
                </div>
              ))}
          </div>
        )}

        {loading && (
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-20 bg-[#111118] border border-[#1e1e2e] rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {data && (
          <div className="space-y-2">
            {data.leaderboard?.map((item: any, i: number) => {
              const meta = GRADE_META[item.grade] ?? { color: "#9ca3af", bg: "#9ca3af18", label: "" };
              return (
                <motion.a
                  key={item.audit_id}
                  href={`/report/view/?id=${item.audit_id}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-4 bg-[#111118] border border-[#1e1e2e] rounded-xl px-5 py-4 hover:border-indigo-500/50 hover:bg-[#14141f] transition-all group cursor-pointer"
                >
                  {/* Rank */}
                  <div className="w-7 text-center shrink-0">
                    {i < 3 ? (
                      <span className="text-xl">{MEDALS[i]}</span>
                    ) : (
                      <span className="text-gray-600 font-mono text-sm">{i + 1}</span>
                    )}
                  </div>

                  {/* Grade badge */}
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 font-black text-xl"
                    style={{ color: meta.color, background: meta.bg, border: `1px solid ${meta.color}30` }}
                  >
                    {item.grade}
                  </div>

                  {/* Site info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-semibold truncate group-hover:text-indigo-300 transition-colors">
                      {item.label || new URL(item.url).hostname}
                    </p>
                    <p className="text-gray-600 text-xs font-mono truncate">{item.url}</p>
                  </div>

                  {/* Dimension mini bars */}
                  <div className="hidden lg:flex flex-col gap-1.5 shrink-0">
                    {DIMS.map((d, di) => (
                      <div key={d.key} className="flex items-center gap-1.5 text-[10px] font-mono text-gray-600">
                        <span className="w-8 text-right">{d.short}</span>
                        <MiniBar
                          val={item[d.key] ?? 0}
                          baseline={d.baseline}
                          color={DIM_COLORS[d.key]}
                          delay={i * 0.04 + di * 0.05}
                        />
                        <span className="w-6">{(item[d.key] ?? 0).toFixed(0)}</span>
                      </div>
                    ))}
                  </div>

                  {/* Composite score */}
                  <div className="text-right shrink-0 min-w-[56px]">
                    <p className="text-2xl font-black" style={{ color: meta.color }}>
                      {(item.composite ?? 0).toFixed(0)}
                    </p>
                    <p className="text-[10px] text-gray-600 font-mono">/ 100</p>
                  </div>

                  <span className="text-gray-700 group-hover:text-gray-400 transition-colors text-sm">→</span>
                </motion.a>
              );
            })}

            {(!data.leaderboard || data.leaderboard.length === 0) && (
              <div className="text-center py-24">
                <p className="text-5xl mb-4">🤖</p>
                <p className="text-gray-500 font-mono text-sm">No completed audits yet.</p>
                <a href="/" className="text-indigo-400 text-sm hover:underline mt-3 block">
                  Run the first audit →
                </a>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
