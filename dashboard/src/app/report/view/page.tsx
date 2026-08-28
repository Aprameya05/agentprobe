"use client";

import { useEffect, useState } from "react";
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

// ─── Agent Replay ────────────────────────────────────────────────────────────

const ACTION_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  navigate: { label: "NAV",    color: "#a855f7", bg: "#a855f710" },
  click:    { label: "CLICK",  color: "#60a5fa", bg: "#60a5fa10" },
  type:     { label: "TYPE",   color: "#34d399", bg: "#34d39910" },
  scroll:   { label: "SCROLL", color: "#6b7280", bg: "#6b728010" },
  done:     { label: "DONE",   color: "#10b981", bg: "#10b98120" },
  failed:   { label: "FAIL",   color: "#ef4444", bg: "#ef444420" },
  wait:     { label: "WAIT",   color: "#6b7280", bg: "#6b728010" },
};

function AgentReplay({ tasks }: { tasks: any[] }) {
  const [selectedTask, setSelectedTask] = useState(0);
  const [playIdx, setPlayIdx] = useState(-1);
  const [playing, setPlaying] = useState(false);

  const task = tasks[selectedTask];
  const steps = task?.steps ?? [];

  useEffect(() => {
    setPlayIdx(-1);
    setPlaying(false);
  }, [selectedTask]);

  useEffect(() => {
    if (!playing) return;
    if (playIdx >= steps.length - 1) { setPlaying(false); return; }
    const t = setTimeout(() => setPlayIdx(i => i + 1), 600);
    return () => clearTimeout(t);
  }, [playing, playIdx, steps.length]);

  function startReplay() {
    setPlayIdx(-1);
    setPlaying(false);
    setTimeout(() => { setPlayIdx(0); setPlaying(true); }, 50);
  }

  const visibleSteps = playIdx < 0 ? steps : steps.slice(0, playIdx + 1);

  return (
    <div className="bg-[#111118] border border-[#1e1e2e] rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 bg-[#0d0d14] border-b border-[#1e1e2e]">
        <span className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
        <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/70" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-500/70" />
        <span className="ml-2 text-[11px] text-gray-500 font-mono">agent replay</span>
        <div className="ml-auto flex items-center gap-2">
          {playing && (
            <span className="flex items-center gap-1 text-[10px] text-indigo-400 font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              running step {playIdx + 1}/{steps.length}
            </span>
          )}
          <button
            onClick={startReplay}
            className="px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-mono rounded transition-colors"
          >
            ▶ replay
          </button>
        </div>
      </div>

      {/* Task selector */}
      <div className="flex gap-1 px-4 pt-3 pb-0 overflow-x-auto">
        {tasks.map((t: any, i: number) => (
          <button
            key={i}
            onClick={() => setSelectedTask(i)}
            className={`px-3 py-1.5 rounded-t-lg text-[10px] font-mono whitespace-nowrap transition-all border-b-2 ${
              i === selectedTask
                ? "text-white border-indigo-500 bg-indigo-500/10"
                : "text-gray-600 border-transparent hover:text-gray-400"
            }`}
          >
            {t.task_name?.toLowerCase().replace(/_/g, " ")}
            <span className={`ml-1.5 ${t.status === "completed" ? "text-green-500" : "text-red-500"}`}>
              {t.status === "completed" ? "✓" : "✗"}
            </span>
          </button>
        ))}
      </div>

      {/* Step feed */}
      <div className="px-4 py-3 h-64 overflow-y-auto space-y-1.5 font-mono text-xs">
        {visibleSteps.length === 0 && (
          <p className="text-gray-600 text-center mt-8">Press ▶ replay to watch the agent</p>
        )}
        {visibleSteps.map((step: any, i: number) => {
          const style = ACTION_STYLE[step.action] ?? ACTION_STYLE.navigate;
          const isLatest = i === visibleSteps.length - 1 && playing;
          return (
            <motion.div
              key={step.step_index}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              className={`flex items-start gap-2 p-2 rounded-lg transition-colors ${
                isLatest ? "bg-indigo-500/10 border border-indigo-500/20" : ""
              }`}
            >
              <span className="text-gray-600 w-5 text-right shrink-0">{step.step_index + 1}</span>
              <span
                className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase shrink-0"
                style={{ color: style.color, background: style.bg }}
              >
                {style.label}
              </span>
              <span className="flex-1 text-gray-300 leading-relaxed">{step.reasoning}</span>
              {step.target && (
                <span className="text-gray-600 max-w-[120px] truncate shrink-0" title={step.target}>
                  → {step.target}
                </span>
              )}
              <span className={`text-[10px] shrink-0 ${
                step.confidence >= 0.7 ? "text-green-600" :
                step.confidence >= 0.4 ? "text-amber-600" : "text-red-600"
              }`}>{(step.confidence * 100).toFixed(0)}%</span>
              {step.friction_note && (
                <span className="text-amber-400 text-[10px] shrink-0">⚠</span>
              )}
            </motion.div>
          );
        })}
        {!playing && steps.length > 0 && playIdx === steps.length - 1 && (
          <div className={`text-center text-[10px] font-mono py-2 ${
            task.status === "completed" ? "text-green-400" : "text-red-400"
          }`}>
            {task.status === "completed" ? "✓ Task completed" : `✗ ${task.failure_point || "Task failed"}`}
          </div>
        )}
      </div>

      {/* Stats bar */}
      {steps.length > 0 && (
        <div className="border-t border-[#1e1e2e] px-5 py-2.5 flex gap-6 text-[10px] font-mono text-gray-600 bg-[#0d0d14]">
          <span>{steps.length} steps</span>
          <span>{((task.duration_ms ?? 0) / 1000).toFixed(1)}s</span>
          <span>avg conf {((task.avg_confidence ?? 0) * 100).toFixed(0)}%</span>
          {task.walls_hit > 0 && <span className="text-amber-500">{task.walls_hit} wall(s)</span>}
          {task.backtracks > 0 && <span className="text-orange-500">{task.backtracks} backtrack(s)</span>}
        </div>
      )}
    </div>
  );
}

// ─── Task Card ───────────────────────────────────────────────────────────────

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
  // Read audit ID from URL path: /report/<id>
  const [id, setId] = useState<string>("");
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [rerunning, setRerunning] = useState(false);

  useEffect(() => {
    const parts = window.location.pathname.replace(/\/$/, "").split("/");
    setId(parts[parts.length - 1]);
  }, []);

  useEffect(() => {
    if (!id) return;
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
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[#111118] border border-[#1e1e2e] rounded-2xl p-8 flex flex-col sm:flex-row items-center gap-8"
        >
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
                <div className="flex items-start justify-between gap-4 mb-3">
                  <div className="flex-1">
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
                {r.fix_code && (
                  <div className="relative">
                    <pre className="bg-[#0d0d14] border border-[#2a2a3a] rounded-lg p-3 text-xs font-mono text-gray-300 overflow-x-auto leading-relaxed whitespace-pre-wrap">
                      {r.fix_code}
                    </pre>
                    <button
                      onClick={() => navigator.clipboard.writeText(r.fix_code)}
                      className="absolute top-2 right-2 px-2 py-0.5 bg-[#1e1e2e] hover:bg-indigo-600 text-[9px] text-gray-500 hover:text-white font-mono rounded transition-all"
                    >
                      copy
                    </button>
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}

        {/* Agent replay */}
        {report.tasks?.length > 0 && (
          <div>
            <h2 className="text-sm font-mono text-gray-400 mb-3">Agent replay</h2>
            <AgentReplay tasks={report.tasks} />
          </div>
        )}

        <div className="space-y-3">
          <h2 className="text-sm font-mono text-gray-400">Task results</h2>
          {(report.tasks ?? []).map((task: any, i: number) => (
            <TaskCard key={i} task={task} />
          ))}
        </div>

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

        <div className="flex flex-wrap gap-3">
          <a
            href="/leaderboard"
            className="px-4 py-2 bg-[#111118] border border-[#1e1e2e] rounded-lg text-sm text-gray-300 hover:border-indigo-500 hover:text-white transition-all font-mono"
          >
            View leaderboard
          </a>
          <button
            onClick={() => {
              const u = window.location.href;
              navigator.clipboard.writeText(u);
            }}
            className="px-4 py-2 bg-[#111118] border border-[#1e1e2e] rounded-lg text-sm text-gray-300 hover:border-indigo-500 hover:text-white transition-all font-mono"
          >
            Copy link
          </button>
          <button
            onClick={async () => {
              if (!report?.url || rerunning) return;
              setRerunning(true);
              try {
                const r = await fetch(`${API}/audit`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ url: report.url, tasks: report.tasks?.map((t: any) => t.task_name) }),
                });
                if (!r.ok) throw new Error("failed");
                const { audit_id } = await r.json();
                window.location.href = `/audit/view/?id=${audit_id}`;
              } catch {
                setRerunning(false);
              }
            }}
            disabled={rerunning}
            className="px-4 py-2 bg-[#111118] border border-[#1e1e2e] rounded-lg text-sm text-gray-300 hover:border-amber-500 hover:text-amber-300 transition-all font-mono disabled:opacity-40"
          >
            {rerunning ? "Starting..." : "↺ Re-run audit"}
          </button>
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
              const a = document.createElement("a");
              a.href = URL.createObjectURL(blob);
              a.download = `agentprobe-${id}.json`;
              a.click();
              URL.revokeObjectURL(a.href);
            }}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm text-white transition-all font-semibold"
          >
            Export JSON
          </button>
          {(() => {
            try {
              const domain = new URL(report.url).hostname.replace(/^www\./, "");
              return (
                <a
                  href={`/site/${domain}`}
                  className="px-4 py-2 bg-[#111118] border border-[#1e1e2e] rounded-lg text-sm text-gray-300 hover:border-indigo-500 hover:text-white transition-all font-mono"
                >
                  📈 Site history
                </a>
              );
            } catch { return null; }
          })()}
        </div>

        {/* Badge embed */}
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5">
          <h2 className="text-sm font-mono text-gray-400 mb-3">README badge</h2>
          <div className="flex items-center gap-3 mb-3">
            {/* Live badge preview */}
            <img
              src={`${API}/badge/${id}.svg`}
              alt="ARS badge"
              className="h-5"
              onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <span className="text-xs text-gray-600 font-mono">live • updates when you re-run</span>
          </div>
          <div className="bg-[#0d0d14] rounded-lg p-3 font-mono text-xs text-gray-300 overflow-x-auto">
            <p className="text-gray-600 mb-1"># Markdown</p>
            <p className="select-all break-all">
              {`![AgentProbe ARS](${API}/badge/${id}.svg)`}
            </p>
          </div>
          <button
            onClick={() => navigator.clipboard.writeText(`![AgentProbe ARS](${API}/badge/${id}.svg)`)}
            className="mt-2 text-[10px] text-gray-500 hover:text-indigo-400 font-mono transition-colors"
          >
            Copy badge markdown
          </button>
        </div>
      </div>
    </main>
  );
}
