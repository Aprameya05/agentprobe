"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Event {
  id?: number;
  event_type: string;
  task_name?: string;
  step?: {
    step_index: number;
    url: string;
    action: string;
    target?: string;
    value?: string;
    reasoning: string;
    confidence: number;
    friction_note?: string;
    duration_ms: number;
  };
  task_result?: any;
  message?: string;
  score?: number;
  signals?: any[];
  report?: any;
}

function ConfidencePip({ val }: { val: number }) {
  const color = val >= 0.7 ? "#10b981" : val >= 0.4 ? "#fbbf24" : "#ef4444";
  return (
    <span className="inline-block w-2 h-2 rounded-full mr-1.5" style={{ background: color }} />
  );
}

function ActionBadge({ action }: { action: string }) {
  const styles: Record<string, string> = {
    click:    "bg-blue-500/10 text-blue-400",
    navigate: "bg-purple-500/10 text-purple-400",
    type:     "bg-yellow-500/10 text-yellow-400",
    scroll:   "bg-gray-500/10 text-gray-400",
    done:     "bg-green-500/10 text-green-400",
    failed:   "bg-red-500/10 text-red-400",
  };
  return (
    <span className={`font-mono text-[10px] px-2 py-0.5 rounded uppercase font-bold ${styles[action] || "bg-gray-500/10 text-gray-400"}`}>
      {action}
    </span>
  );
}

export default function AuditLivePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [events, setEvents] = useState<Event[]>([]);
  const [status, setStatus] = useState<"running" | "completed" | "failed">("running");
  const [parseScore, setParseScore] = useState<number | null>(null);
  const [taskStatuses, setTaskStatuses] = useState<Record<string, string>>({});
  const [report, setReport] = useState<any>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const lastIdRef = useRef(0);

  // Poll for events (SSE with fetch-based polling for Cloudflare Pages compat)
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      if (stopped) return;
      try {
        const resp = await fetch(`${API}/audit/${id}`);
        if (!resp.ok) return;
        const data = await resp.json();

        if (data.status === "completed" || data.status === "failed") {
          setStatus(data.status);
          if (data.report) {
            setReport(data.report);
            router.push(`/report/${id}`);
            return;
          }
        }

        // Fetch new events
        const evResp = await fetch(
          `${API}/audit/${id}/events-poll?after=${lastIdRef.current}`
        );
        if (evResp.ok) {
          const newEvents: Event[] = await evResp.json();
          if (newEvents.length > 0) {
            lastIdRef.current = newEvents[newEvents.length - 1].id ?? lastIdRef.current;
            setEvents(prev => [...prev, ...newEvents]);

            for (const ev of newEvents) {
              if (ev.event_type === "parseability_done" && ev.score !== undefined) {
                setParseScore(ev.score);
              }
              if (ev.event_type === "task_start" && ev.task_name) {
                setTaskStatuses(prev => ({ ...prev, [ev.task_name!]: "running" }));
              }
              if (ev.event_type === "task_done" && ev.task_name) {
                setTaskStatuses(prev => ({ ...prev, [ev.task_name!]: ev.task_result?.status || "unknown" }));
              }
              if (ev.event_type === "audit_done" && ev.report) {
                setReport(ev.report);
                setStatus("completed");
                setTimeout(() => router.push(`/report/${id}`), 1200);
              }
            }
          }
        }
      } catch (e) {
        // swallow, retry
      }

      if (!stopped) {
        timer = setTimeout(poll, 1800);
      }
    }

    poll();
    return () => { stopped = true; clearTimeout(timer); };
  }, [id, router]);

  // Auto-scroll feed
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);

  const stepEvents = events.filter(e => e.event_type === "step");

  return (
    <main className="min-h-screen bg-[#0a0a0f]">
      {/* Nav */}
      <nav className="border-b border-[#1e1e2e] px-6 py-4 flex items-center gap-4">
        <a href="/" className="font-mono text-indigo-400 font-bold text-lg">AgentProbe</a>
        <span className="text-gray-600">/</span>
        <span className="text-gray-400 font-mono text-sm truncate">audit:{id?.slice(0, 16)}</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse" />
          <span className="text-xs text-gray-500 font-mono">
            {status === "running" ? "Agent running..." : status === "completed" ? "Done" : "Failed"}
          </span>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Parseability quick score */}
        {parseScore !== null && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-4 flex items-center gap-4"
          >
            <div>
              <p className="text-xs text-gray-500 font-mono mb-0.5">Static parseability</p>
              <p className="text-2xl font-bold text-white">{parseScore}<span className="text-sm text-gray-500 ml-1">/100</span></p>
            </div>
            <div className="flex-1 bg-[#1e1e2e] rounded-full h-2">
              <div
                className="h-2 rounded-full transition-all duration-700"
                style={{
                  width: `${parseScore}%`,
                  background: parseScore >= 70 ? "#10b981" : parseScore >= 50 ? "#fbbf24" : "#ef4444",
                }}
              />
            </div>
            <p className="text-xs text-gray-600 w-32 text-right">Instant static score while agent runs</p>
          </motion.div>
        )}

        {/* Task status pills */}
        {Object.keys(taskStatuses).length > 0 && (
          <div className="flex flex-wrap gap-2">
            {Object.entries(taskStatuses).map(([name, st]) => (
              <span
                key={name}
                className={`font-mono text-xs px-3 py-1 rounded-full border ${
                  st === "running"   ? "border-indigo-500 text-indigo-300 bg-indigo-500/10" :
                  st === "completed" ? "border-green-500 text-green-300 bg-green-500/10" :
                  st === "failed"    ? "border-red-500 text-red-300 bg-red-500/10" :
                                       "border-gray-600 text-gray-400"
                }`}
              >
                {st === "running" && <span className="mr-1 animate-pulse">●</span>}
                {name.toLowerCase().replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {/* Live event feed */}
        <div className="bg-[#111118] border border-[#1e1e2e] rounded-xl overflow-hidden">
          <div className="border-b border-[#1e1e2e] px-5 py-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            <span className="text-xs font-mono text-gray-400">Live agent feed</span>
            <span className="ml-auto text-xs text-gray-600">{stepEvents.length} steps</span>
          </div>
          <div
            ref={feedRef}
            className="h-[420px] overflow-y-auto p-4 space-y-2 font-mono text-xs"
          >
            <AnimatePresence>
              {events.map((ev, i) => {
                if (ev.event_type === "step" && ev.step) {
                  const s = ev.step;
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex items-start gap-2 text-gray-300 hover:bg-white/5 rounded px-2 py-1.5 transition-colors"
                    >
                      <span className="text-gray-600 w-5 text-right shrink-0">{s.step_index + 1}</span>
                      <ActionBadge action={s.action} />
                      <ConfidencePip val={s.confidence} />
                      <span className="flex-1 text-gray-300">{s.reasoning}</span>
                      {s.friction_note && (
                        <span className="text-amber-400 shrink-0 max-w-[200px] truncate" title={s.friction_note}>
                          ⚠ {s.friction_note}
                        </span>
                      )}
                      <span className="text-gray-600 shrink-0">{s.duration_ms.toFixed(0)}ms</span>
                    </motion.div>
                  );
                }

                if (ev.event_type === "task_start") {
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-indigo-400 py-1.5 px-2 border-l-2 border-indigo-500"
                    >
                      Task: {ev.task_name?.toLowerCase().replace(/_/g, " ")}
                    </motion.div>
                  );
                }

                if (ev.event_type === "task_done") {
                  const ok = ev.task_result?.status === "completed";
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className={`py-1.5 px-2 ${ok ? "text-green-400" : "text-red-400"}`}
                    >
                      {ok ? "✓" : "✗"} {ev.task_name?.toLowerCase().replace(/_/g, " ")} {ok ? "completed" : "failed"}
                    </motion.div>
                  );
                }

                if (ev.event_type === "audit_done") {
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-green-400 py-2 px-2 border-l-2 border-green-500 font-bold"
                    >
                      Audit complete. Generating report...
                    </motion.div>
                  );
                }

                return null;
              })}
            </AnimatePresence>

            {status === "running" && (
              <div className="flex items-center gap-2 text-gray-600 py-2 px-2">
                <span className="animate-pulse">▋</span>
                <span>Agent thinking...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
