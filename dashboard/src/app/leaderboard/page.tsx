"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function gradeColor(grade: string) {
  return {
    "A+": "#10b981", A: "#34d399", B: "#60a5fa",
    C: "#fbbf24",    D: "#f97316", F: "#ef4444",
  }[grade] ?? "#9ca3af";
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
        <a href="/" className="ml-auto text-xs text-gray-500 hover:text-white transition-colors font-mono">
          + Run audit
        </a>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Agentic Readiness Leaderboard</h1>
          <p className="text-gray-500 text-sm mt-1">
            Sites ranked by ARS. Gray line = industry average. Publicly audited sites only.
          </p>
        </div>

        {loading && (
          <div className="text-gray-600 font-mono text-sm">Loading...</div>
        )}

        {data && (
          <>
            {/* Industry baselines */}
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-8">
              {Object.entries(data.industry_baselines ?? {})
                .filter(([k]) => k !== "composite")
                .map(([key, val]) => (
                  <div key={key} className="bg-[#111118] border border-[#1e1e2e] rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-600 font-mono mb-1">{key}</p>
                    <p className="text-lg font-bold text-gray-300">{(val as number).toFixed(0)}</p>
                    <p className="text-[10px] text-gray-600">avg</p>
                  </div>
                ))}
            </div>

            {/* Table */}
            <div className="space-y-2">
              {data.leaderboard?.map((item: any, i: number) => (
                <motion.a
                  key={item.audit_id}
                  href={`/report/${item.audit_id}`}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="flex items-center gap-4 bg-[#111118] border border-[#1e1e2e] rounded-xl px-5 py-4 hover:border-indigo-500/50 transition-all group"
                >
                  <span className="text-gray-600 font-mono text-sm w-6 text-right">{i + 1}</span>
                  <div
                    className="text-2xl font-black w-12 text-center"
                    style={{ color: gradeColor(item.grade) }}
                  >
                    {item.grade}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-white text-sm font-semibold truncate group-hover:text-indigo-300 transition-colors">
                      {item.label || item.url}
                    </p>
                    <p className="text-gray-600 text-xs font-mono truncate">{item.url}</p>
                  </div>
                  <div className="hidden sm:flex gap-4 text-xs font-mono text-gray-600">
                    <span title="Discoverability">D:{item.discoverability?.toFixed(0)}</span>
                    <span title="Parseability">P:{item.parseability?.toFixed(0)}</span>
                    <span title="Task completion">T:{item.task_completion?.toFixed(0)}</span>
                    <span title="Friction">F:{item.friction?.toFixed(0)}</span>
                  </div>
                  <div className="text-right">
                    <p className="text-xl font-bold text-white">{item.composite?.toFixed(0)}</p>
                    <p className="text-[10px] text-gray-600 font-mono">ARS</p>
                  </div>
                </motion.a>
              ))}
            </div>

            {(!data.leaderboard || data.leaderboard.length === 0) && (
              <div className="text-center py-16">
                <p className="text-gray-600 font-mono text-sm">No completed audits yet.</p>
                <a href="/" className="text-indigo-400 text-sm hover:underline mt-2 block">
                  Run the first one
                </a>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
