"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function gradeColor(grade: string) {
  return {
    "A+": "#10b981", A: "#34d399", B: "#60a5fa",
    C: "#fbbf24",  D: "#f97316", F: "#ef4444",
  }[grade] ?? "#9ca3af";
}

function DimBar({ label, score, baseline }: { label: string; score: number; baseline: number }) {
  const delta = score - baseline;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs font-mono">
        <span className="text-gray-400">{label}</span>
        <div className="flex items-center gap-2">
          <span className={delta >= 0 ? "text-green-400" : "text-red-400"}>
            {delta >= 0 ? "+" : ""}{delta.toFixed(0)} vs avg
          </span>
          <span className="text-white font-bold">{score.toFixed(0)}</span>
        </div>
      </div>
      <div className="relative h-2 bg-[#1e1e2e] rounded-full overflow-hidden">
        {/* Baseline marker */}
        <div
          className="absolute top-0 h-full w-0.5 bg-gray-600 z-10"
          style={{ left: `${baseline}%` }}
        />
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${score}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{
            background: score >= 70 ? "#6366f1" : score >= 50 ? "#f59e0b" : "#ef4444",
          }}
        />
      </div>
    </div>
  );
}

function TaskCard({ task }: { task: any }) {
  const [open, setOpen] = useState(false);
  const done = task.status === "completed";
  return (
    <div className="border border-[#1e1e2e] rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-white/5 transition-colors"
      >
        <span className={`text-lg ${done ? "text-green-400" : "text-red-400"}`}>
          {done ? "✓" : "✗"}
        </span>
        <div className="flex-1">
          <p className="font-mono text-sm text-white font-semibold">
            {task.task_name.toLowerCase().replace(/_/g, " ")}
          </p>
          {task.failure_point && (
            <p className="text-xs text-red-400 mt-0.5 truncate">{task.failure_point}</p>
          )}
          {task.agent_summary && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{task.agent_summary}</p>
          )}
        </div>
        <div className="text-right text-xs font-mono">
          <p className="text-gray-400">{task.steps_taken} steps</p>
          <p className="text-gray-600">{(task.duration_ms / 1000).toFixed(1)}s</p>
        </div>
        <span className="text-gray-600 ml-2">{open ? "▲" : "▼"}</span>
      </button>

      {open && task.steps && task.steps.length > 0 && (
        <div className="border-t border-[#1e1e2e] px-5 py-3 space-y-2 bg-[#0d0d14]">
          {task.steps.map((step: any, i: number) => (
            <div key={i} className="flex items-start gap-2 text-xs font-mono">
              <span className="text-gray-600 w-4 text-right">{step.step_index + 1}</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                step.action === "done"   ? "bg-green-500/10 text-green-400" :
                step.action === "failed" ? "bg-red-500/10 text-red-400" :
                step.action === "click"  ? "bg-blue-500/10 text-blue-400" :
                "bg-gray-500/10 text-gray-400"
              }`}>{step.action}</span>
              <span className="flex-1 text-gray-400">{step.reasoning}</span>
              {step.friction_note && (
                <span className="text-amber-400 max-w-[180px] truncate" title={step.friction_note}>
                  ⚠ {step.friction_note}
                </span>
              )}
              <span className="text-gray-600">{step.confidence?.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/audit/${id}`)
      .then(r => r.json())
      .then(data => {
        if (data.report) setReport(data.report);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500 font-mono text-sm">Loading report...</div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-500 font-mono">
          Report not ready yet.{" "}
          <a href={`/audit/${id}`} className="text-indigo-400 hover:underline">
            Watch live progress
          </a>
        </div>
      </div>
    );
  }

  const ars = report.ars ?? {};
  const dims = [
    { key: "discoverability", label: "Discoverability", baseline: 68 },
    { key: "parseability",    label: "Parseability",    baseline: 52 },
    { key: "task_completion", label: "Task Completion", baseline: 57 },
    { key: "friction",        label: "Friction",        baseline: 63 },
    { key: "clarity",         label: "Clarity",         baseline: 61 },
    { key: "resilience",      label: "Resilience",      baseline: 72 },
  ];

  const radarData = dims.map(d => ({
    dimension: d.label,
    score: Math.round(ars[d.key] ?? 0),
    baseline: d.baseline,
  }));

  return (
    <main className="min-h-screen bg-[#0a0a0f]">
      <nav className="border-b border-[#1e1e2e] px-6 py-4 flex items-center gap-4">
        <a href="/" className="font-mono text-indigo-400 font-bold text-lg">AgentProbe</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400 font-mono text-sm">{report.url}</span>
        <a href="/leaderboard" className="ml-auto text-xs text-gray-500 hover:text-white transition-colors">
          Leaderboard
        </a>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        {/* ARS hero */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[#111118] border border-[#1e1e2e] rounded-2xl p-8 flex flex-col sm:flex-row items-center gap-8"
        >
          {/* Big grade */}
          <div className="text-center">
            <div
              className="text-8xl font-black"
              style={{ color: gradeColor(ars.grade ?? "F") }}
            >
              {ars.grade ?? "F"}
            </div>
            <div className="text-4xl font-bold text-white mt-1">{ars.composite ?? 0}</div>
            <div className="text-xs text-gray-500 font-mono mt-1">/ 100 ARS</div>
          </div>

          {/* Radar chart */}
          <div className="flex-1 w-full" style={{ height: 240 }}>
            <ResponsiveContainer>
              <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                <PolarGrid stroke="#1e1e2e" />
                <PolarAngleAxis dataKey="dimension" tick={{ fill: "#6b7280", fontSize: 11, fontFamily: "monospace" }} />
                <Radar name="Your site" dataKey="score" stroke="#6366f1" fill="#6366f1" fillOpacity={0.25} />
                <Radar name="Industry avg" dataKey="baseline" stroke="#374151" fill="#374151" fillOpacity={0.1} strokeDasharray="4 2" />
                <Tooltip contentStyle={{ background: "#111118", border: "1px solid #1e1e2e", borderRadius: 8, fontSize: 12 }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Stats */}
          <div className="text-right space-y-3 min-w-[120px]">
            <div>
              <p className="text-xs text-gray-600 font-mono">Total steps</p>
              <p className="text-xl font-bold text-white">{report.total_steps ?? 0}</p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono">Duration</p>
              <p className="text-xl font-bold text-white">
                {((report.total_duration_ms ?? 0) / 1000).toFixed(0)}s
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono">Tasks run</p>
              <p className="text-xl font-bold text-white">{report.tasks?.length ?? 0}</p>
            </div>
          </div>
        </motion.div>

        {/* Dimension bars */}
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-mono text-gray-400 mb-5">Score breakdown <span className="text-gray-600">-- gray line = industry average</span></h2>
          {dims.map(d => (
            <DimBar
              key={d.key}
              label={d.label}
              score={ars[d.key] ?? 0}
              baseline={d.baseline}
            />
          ))}
        </div>

        {/* Recommendations */}
        {report.recommendations?.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-mono text-gray-400">What to fix</h2>
            {report.recommendations.map((r: any, i: number) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`border rounded-xl p-5 ${
                  r.severity === "critical"
                    ? "border-red-500/40 bg-red-500/5"
                    : r.severity === "warning"
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-[#1e1e2e] bg-[#111118]"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-mono font-bold uppercase ${
                        r.severity === "critical" ? "text-red-400" :
                        r.severity === "warning"  ? "text-amber-400" : "text-gray-400"
                      }`}>{r.severity}</span>
                      <span className="text-xs text-gray-600 font-mono">{r.dimension}</span>
                    </div>
                    <p className="text-white text-sm font-semibold">{r.title}</p>
                    <p className="text-gray-400 text-xs mt-1 leading-relaxed">{r.detail}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-gray-600 font-mono">if fixed</p>
                    <p className="text-green-400 font-bold font-mono">+{r.estimated_impact}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Task results */}
        <div className="space-y-3">
          <h2 className="text-sm font-mono text-gray-400">Task results</h2>
          {(report.tasks ?? []).map((task: any, i: number) => (
            <TaskCard key={i} task={task} />
          ))}
        </div>

        {/* Parseability signals */}
        {report.parseability?.signals && (
          <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-6">
            <h2 className="text-sm font-mono text-gray-400 mb-4">Static parseability signals</h2>
            <div className="space-y-2">
              {report.parseability.signals.map((s: any, i: number) => (
                <div key={i} className="flex items-center gap-3 text-xs font-mono">
                  <span className={s.present ? "text-green-400" : "text-gray-600"}>
                    {s.present ? "✓" : "✗"}
                  </span>
                  <span className="flex-1 text-gray-300">{s.label}</span>
                  {s.detail && <span className="text-gray-500 max-w-[280px] truncate text-right" title={s.detail}>{s.detail}</span>}
                  <span className="text-indigo-400 w-8 text-right font-bold">+{s.points}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Share / compare */}
        <div className="flex flex-wrap gap-3">
          <a
            href={`/leaderboard`}
            className="px-4 py-2 bg-[#111118] border border-[#1e1e2e] rounded-lg text-sm text-gray-300 hover:border-indigo-500 hover:text-white transition-all font-mono"
          >
            View leaderboard
          </a>
          <button
            onClick={() => {
              const u = `${window.location.origin}/report/${id}`;
              navigator.clipboard.writeText(u);
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white transition-all font-semibold"
          >
            Copy report link
          </button>
        </div>
      </div>
    </main>
  );
}
