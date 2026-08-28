"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const GRADE_META: Record<string, { color: string; bg: string }> = {
  "A+": { color: "#10b981", bg: "#10b98118" }, "A": { color: "#34d399", bg: "#34d39918" },
  "B":  { color: "#60a5fa", bg: "#60a5fa18" }, "C": { color: "#fbbf24", bg: "#fbbf2418" },
  "D":  { color: "#f97316", bg: "#f9731618" }, "F": { color: "#ef4444", bg: "#ef444418" },
};

const DIMS = [
  { key: "discoverability", color: "#6366f1" },
  { key: "parseability",    color: "#8b5cf6" },
  { key: "task_completion", color: "#10b981" },
  { key: "friction",        color: "#f59e0b" },
];

function gradeColor(g: string) {
  return GRADE_META[g]?.color ?? "#9ca3af";
}

export default function SiteHistoryPage() {
  const [domain, setDomain] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const d = params.get("domain") || "";
    setDomain(d);
    if (!d) { setLoading(false); return; }
    fetch(`${API}/site/${encodeURIComponent(d)}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const completed = (data?.audits ?? []).filter((a: any) => a.status === "completed" && a.ars);

  // Trend chart data — oldest first
  const chartData = [...completed].reverse().map((a: any, i: number) => ({
    i: i + 1,
    date: new Date(a.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    composite: a.ars?.composite ?? 0,
    discoverability: a.ars?.discoverability ?? 0,
    parseability: a.ars?.parseability ?? 0,
    task_completion: a.ars?.task_completion ?? 0,
    friction: a.ars?.friction ?? 0,
  }));

  // Trend: latest vs previous
  const latest = completed[0];
  const prev = completed[1];
  const trend = latest && prev
    ? ((latest.ars?.composite ?? 0) - (prev.ars?.composite ?? 0)).toFixed(1)
    : null;

  return (
    <main className="min-h-screen bg-[#0a0a0f]">
      <nav className="border-b border-[#1e1e2e] px-6 py-4 flex items-center gap-4">
        <a href="/" className="font-mono text-indigo-400 font-bold text-lg">AgentProbe</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400 font-mono text-sm">site</span>
        <span className="text-gray-600">/</span>
        <span className="text-white font-mono text-sm">{domain}</span>
        <a href="/" className="ml-auto px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-xs text-white font-mono rounded-lg transition-colors">
          + New audit
        </a>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-10">
        {loading && (
          <div className="space-y-4">
            <div className="h-32 bg-[#111118] border border-[#1e1e2e] rounded-2xl animate-pulse" />
            <div className="h-64 bg-[#111118] border border-[#1e1e2e] rounded-2xl animate-pulse" />
          </div>
        )}

        {!loading && !data && (
          <div className="text-center py-24">
            <p className="text-4xl mb-4">🔍</p>
            <p className="text-gray-500 font-mono">No audits found for <span className="text-white">{domain}</span></p>
            <a href="/" className="text-indigo-400 hover:underline text-sm mt-2 block">Run the first one →</a>
          </div>
        )}

        {data && (
          <>
            {/* Header stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-4">
                <p className="text-xs text-gray-600 font-mono mb-1">Total audits</p>
                <p className="text-3xl font-black text-white">{data.audits?.length ?? 0}</p>
              </div>
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-4">
                <p className="text-xs text-gray-600 font-mono mb-1">Latest ARS</p>
                <p className="text-3xl font-black" style={{ color: gradeColor(latest?.ars?.grade ?? "F") }}>
                  {latest ? (latest.ars?.composite ?? 0).toFixed(0) : "--"}
                </p>
              </div>
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-4">
                <p className="text-xs text-gray-600 font-mono mb-1">Best grade</p>
                <p className="text-3xl font-black" style={{ color: gradeColor(completed[0]?.ars?.grade ?? "F") }}>
                  {completed.length > 0
                    ? completed.reduce((best: any, a: any) =>
                        (a.ars?.composite ?? 0) > (best.ars?.composite ?? 0) ? a : best
                      ).ars?.grade ?? "F"
                    : "--"}
                </p>
              </div>
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-4">
                <p className="text-xs text-gray-600 font-mono mb-1">vs last audit</p>
                <p className={`text-3xl font-black ${
                  trend === null ? "text-gray-600" :
                  parseFloat(trend) >= 0 ? "text-green-400" : "text-red-400"
                }`}>
                  {trend !== null ? `${parseFloat(trend) >= 0 ? "+" : ""}${trend}` : "--"}
                </p>
              </div>
            </div>

            {/* Trend chart */}
            {chartData.length >= 2 && (
              <div className="bg-[#111118] border border-[#1e1e2e] rounded-2xl p-6 mb-6">
                <h2 className="text-sm font-mono text-gray-400 mb-6">ARS over time</h2>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e1e2e" />
                    <XAxis dataKey="date" tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }} />
                    <YAxis domain={[0, 100]} tick={{ fill: "#6b7280", fontSize: 10, fontFamily: "monospace" }} width={28} />
                    <ReferenceLine y={60} stroke="#374151" strokeDasharray="4 2" label={{ value: "avg", fill: "#4b5563", fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ background: "#111118", border: "1px solid #1e1e2e", borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: "#9ca3af" }}
                    />
                    <Line type="monotone" dataKey="composite" stroke="#6366f1" strokeWidth={2.5} dot={{ fill: "#6366f1", r: 4 }} name="ARS" />
                    {DIMS.map(d => (
                      <Line key={d.key} type="monotone" dataKey={d.key} stroke={d.color} strokeWidth={1} dot={false} strokeDasharray="4 2" opacity={0.5} name={d.key} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-4 mt-3">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-gray-500">
                    <div className="w-4 h-0.5 bg-indigo-500 rounded" />ARS composite
                  </div>
                  {DIMS.map(d => (
                    <div key={d.key} className="flex items-center gap-1.5 text-[10px] font-mono text-gray-600">
                      <div className="w-4 h-px rounded" style={{ background: d.color }} />{d.key.replace("_", " ")}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Audit history list */}
            <div className="space-y-2">
              <h2 className="text-sm font-mono text-gray-400 mb-4">All audits</h2>
              {(data.audits ?? []).map((audit: any, i: number) => {
                const meta = GRADE_META[audit.ars?.grade ?? "F"] ?? { color: "#9ca3af", bg: "#9ca3af18" };
                return (
                  <motion.a
                    key={audit.audit_id}
                    href={`/report/view/?id=${audit.audit_id}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="flex items-center gap-4 bg-[#111118] border border-[#1e1e2e] rounded-xl px-5 py-4 hover:border-indigo-500/50 transition-all group"
                  >
                    {/* Grade */}
                    {audit.ars ? (
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center font-black text-base shrink-0"
                        style={{ color: meta.color, background: meta.bg }}
                      >
                        {audit.ars.grade}
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-[#1e1e2e] flex items-center justify-center">
                        <span className={`text-[10px] font-mono uppercase ${
                          audit.status === "running" ? "text-indigo-400" :
                          audit.status === "failed" ? "text-red-400" : "text-gray-600"
                        }`}>{audit.status}</span>
                      </div>
                    )}

                    <div className="flex-1 min-w-0">
                      <p className="text-white text-sm font-semibold group-hover:text-indigo-300 transition-colors">
                        {new Date(audit.created_at).toLocaleString("en-US", {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
                        })}
                        {i === 0 && <span className="ml-2 text-[10px] text-indigo-400 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded">latest</span>}
                      </p>
                      <p className="text-gray-600 text-xs font-mono">{audit.audit_id}</p>
                    </div>

                    {audit.ars && (
                      <div className="hidden sm:flex gap-4 text-xs font-mono text-gray-600">
                        <span>D:{(audit.ars.discoverability ?? 0).toFixed(0)}</span>
                        <span>P:{(audit.ars.parseability ?? 0).toFixed(0)}</span>
                        <span>T:{(audit.ars.task_completion ?? 0).toFixed(0)}</span>
                        <span>Fr:{(audit.ars.friction ?? 0).toFixed(0)}</span>
                      </div>
                    )}

                    <div className="text-right min-w-[48px]">
                      {audit.ars ? (
                        <>
                          <p className="text-xl font-black" style={{ color: meta.color }}>
                            {(audit.ars.composite ?? 0).toFixed(0)}
                          </p>
                          <p className="text-[9px] text-gray-700 font-mono">/ 100</p>
                        </>
                      ) : (
                        <span className="text-gray-600 text-xs font-mono">--</span>
                      )}
                    </div>

                    <span className="text-gray-700 group-hover:text-gray-400 text-sm">→</span>
                  </motion.a>
                );
              })}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
