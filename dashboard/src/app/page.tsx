"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TASKS = [
  { id: "PRICING_DISCOVERY",   icon: "💰", label: "Pricing",     desc: "Can an agent find your prices?" },
  { id: "CHECKOUT_INITIATION", icon: "🛒", label: "Checkout",    desc: "Reach buy / subscribe flow" },
  { id: "CONTACT_EXTRACTION",  icon: "📞", label: "Contact",     desc: "Find email, phone, chat" },
  { id: "DEMO_BOOKING",        icon: "📅", label: "Demo",        desc: "Book a call or free trial" },
  { id: "POLICY_RETRIEVAL",    icon: "📄", label: "Policy",      desc: "Find refund / return policy" },
  { id: "SUPPORT_ROUTING",     icon: "🎧", label: "Support",     desc: "Submit a support ticket" },
  { id: "API_DISCOVERY",       icon: "⚡", label: "API docs",    desc: "Reach developer documentation" },
];

const DEMOS = [
  { url: "https://stripe.com",  label: "Stripe",  expected: "A+", color: "#6772e5" },
  { url: "https://notion.so",   label: "Notion",  expected: "B+", color: "#ffffff" },
  { url: "https://linear.app",  label: "Linear",  expected: "B",  color: "#5e6ad2" },
];

// Animated gradient grid background
function GridBackground() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage: `
            linear-gradient(rgba(99,102,241,0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99,102,241,0.08) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />
      <div
        className="absolute top-[-30%] left-[20%] w-[600px] h-[600px] rounded-full opacity-20"
        style={{ background: "radial-gradient(circle, #6366f140 0%, transparent 70%)" }}
      />
      <div
        className="absolute bottom-[-20%] right-[10%] w-[400px] h-[400px] rounded-full opacity-15"
        style={{ background: "radial-gradient(circle, #8b5cf640 0%, transparent 70%)" }}
      />
    </div>
  );
}

// Spinning ARS ring for visual hero
function ARSRing({ score, grade }: { score: number; grade: string }) {
  const gradeColor = { "A+": "#10b981", A: "#34d399", B: "#60a5fa", C: "#fbbf24", D: "#f97316", F: "#ef4444" }[grade] ?? "#6366f1";
  const r = 54;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score / 100);

  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="#1e1e2e" strokeWidth="10" />
      <circle
        cx="70" cy="70" r={r}
        fill="none"
        stroke={gradeColor}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 1.2s ease, stroke 0.5s ease" }}
      />
      <text x="70" y="64" textAnchor="middle" fill={gradeColor} fontSize="28" fontWeight="900" fontFamily="monospace">{grade}</text>
      <text x="70" y="84" textAnchor="middle" fill="#6b7280" fontSize="13" fontFamily="monospace">{score}</text>
    </svg>
  );
}

// Live terminal-style agent log
const DEMO_LOG = [
  { action: "navigate", text: "Loading https://stripe.com...", color: "#6b7280" },
  { action: "click",    text: "Clicking 'Pricing' in nav", color: "#60a5fa" },
  { action: "done",     text: "Found pricing: Starter $49/mo, Pro $99/mo", color: "#10b981" },
  { action: "navigate", text: "Returning to homepage for next task", color: "#6b7280" },
  { action: "click",    text: "Clicking 'Get started'", color: "#60a5fa" },
  { action: "click",    text: "Selecting Pro plan", color: "#60a5fa" },
  { action: "done",     text: "Reached checkout -- Stripe checkout page", color: "#10b981" },
  { action: "navigate", text: "Returning to homepage", color: "#6b7280" },
  { action: "click",    text: "Clicking 'Contact' in footer", color: "#60a5fa" },
  { action: "done",     text: "Found: support@stripe.com + live chat", color: "#10b981" },
];

function AgentTerminal() {
  const [visible, setVisible] = useState<number[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i < DEMO_LOG.length) {
        const idx = i;          // capture before any async batching changes i
        i++;
        setVisible(prev => [...prev, idx]);
        if (containerRef.current) {
          containerRef.current.scrollTop = containerRef.current.scrollHeight;
        }
      } else if (i === DEMO_LOG.length) {
        i++;                    // sentinel: only schedule one reset
        setTimeout(() => { setVisible([]); i = 0; }, 2000);
      }
    }, 700);
    return () => clearInterval(interval);
  }, []);

  const actionBadge = (action: string) => {
    const styles: Record<string, string> = {
      navigate: "text-purple-400 bg-purple-500/10",
      click:    "text-blue-400 bg-blue-500/10",
      done:     "text-green-400 bg-green-500/10",
      failed:   "text-red-400 bg-red-500/10",
    };
    return <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${styles[action] ?? "text-gray-400 bg-gray-500/10"}`}>{action}</span>;
  };

  return (
    <div className="bg-[#0d0d14] border border-[#1e1e2e] rounded-xl overflow-hidden shadow-2xl">
      {/* Terminal header */}
      <div className="flex items-center gap-1.5 px-4 py-3 bg-[#111118] border-b border-[#1e1e2e]">
        <span className="w-3 h-3 rounded-full bg-red-500/70" />
        <span className="w-3 h-3 rounded-full bg-yellow-500/70" />
        <span className="w-3 h-3 rounded-full bg-green-500/70" />
        <span className="ml-3 text-[11px] text-gray-500 font-mono">agentprobe -- stripe.com -- 7 tasks</span>
        <span className="ml-auto flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
          <span className="text-[10px] text-gray-600 font-mono">agent running</span>
        </span>
      </div>
      {/* Feed */}
      <div ref={containerRef} className="h-48 overflow-hidden p-4 space-y-1.5 font-mono text-xs">
        <AnimatePresence>
          {visible.map(i => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2"
            >
              <span className="text-gray-600 w-4 text-right">{i + 1}</span>
              {actionBadge(DEMO_LOG[i].action)}
              <span style={{ color: DEMO_LOG[i].color }}>{DEMO_LOG[i].text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        <div className="flex items-center gap-1 text-gray-600 mt-1">
          <span className="animate-pulse">▋</span>
        </div>
      </div>
      {/* Score preview */}
      <div className="border-t border-[#1e1e2e] px-4 py-3 flex items-center gap-4 bg-[#0d0d14]">
        <ARSRing score={91} grade="A+" />
        <div className="space-y-1.5 flex-1">
          {[
            { label: "Discoverability", val: 94 },
            { label: "Task Completion", val: 100 },
            { label: "Friction",        val: 85 },
          ].map(d => (
            <div key={d.label} className="flex items-center gap-2 text-xs font-mono">
              <span className="text-gray-600 w-24 shrink-0">{d.label}</span>
              <div className="flex-1 bg-[#1e1e2e] rounded-full h-1.5">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${d.val}%` }}
                  transition={{ duration: 1, delay: 0.5 }}
                  className="h-1.5 rounded-full bg-indigo-500"
                />
              </div>
              <span className="text-indigo-400 w-6 text-right">{d.val}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const GRADE_META: Record<string, { color: string }> = {
  "A+": { color: "#10b981" }, "A":  { color: "#34d399" },
  "B":  { color: "#60a5fa" }, "C":  { color: "#fbbf24" },
  "D":  { color: "#f97316" }, "F":  { color: "#ef4444" },
};

function normalizeUrl(raw: string): string {
  const t = raw.trim();
  if (!t) return t;
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t}`;
}

function isValidUrl(raw: string): boolean {
  try {
    const u = new URL(normalizeUrl(raw));
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

export default function HomePage() {
  const [url, setUrl]         = useState("");
  const [label, setLabel]     = useState("");
  const [tasks, setTasks]     = useState<string[]>(TASKS.map(t => t.id));
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");
  const [showTasks, setShowTasks] = useState(false);
  const [recentAudits, setRecentAudits] = useState<any[]>([]);

  useEffect(() => {
    fetch(`${API}/leaderboard?limit=6`)
      .then(r => r.json())
      .then(d => setRecentAudits(d.leaderboard ?? []))
      .catch(() => {});
  }, []);

  function toggleTask(id: string) {
    setTasks(prev => prev.includes(id) ? prev.filter(t => t !== id) : [...prev, id]);
  }

  async function runAudit(targetUrl?: string) {
    const raw = (targetUrl ?? url).trim();
    if (!raw) return;
    const u = normalizeUrl(raw);
    if (!isValidUrl(u)) { setError("Enter a valid URL (e.g. https://example.com)"); return; }
    if (tasks.length === 0) { setError("Select at least one task."); return; }
    setError("");
    setLoading(true);
    // Update the input to show the normalised URL
    if (!targetUrl) setUrl(u);
    try {
      const r = await fetch(`${API}/audit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u, label: label.trim() || undefined, tasks }),
      });
      if (!r.ok) throw new Error(`API error: ${r.status}`);
      const { audit_id } = await r.json();
      window.location.href = `/audit/view/?id=${audit_id}`;
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] relative overflow-x-hidden">
      <GridBackground />

      {/* Nav */}
      <nav className="relative z-10 border-b border-[#1e1e2e]/60 px-6 py-4 flex items-center justify-between backdrop-blur-sm bg-[#0a0a0f]/80">
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="font-mono text-xl font-black tracking-tight"
        >
          <span className="text-indigo-400">Agent</span>
          <span className="text-white">Probe</span>
        </motion.span>
        <div className="flex items-center gap-6 text-sm text-gray-500">
          <a href="/leaderboard" className="hover:text-white transition-colors font-mono">Leaderboard</a>
          <a
            href="https://github.com/Aprameya05/agentprobe"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-white transition-colors font-mono"
          >
            GitHub
          </a>
          <a
            href={`${API}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded-md border border-[#2a2a3a] hover:border-indigo-500 hover:text-indigo-300 transition-all text-xs font-mono"
          >
            API docs
          </a>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-10 pt-20 pb-16 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid lg:grid-cols-2 gap-16 items-start">
            {/* Left: Copy + Input */}
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <div className="inline-flex items-center gap-2 bg-indigo-500/10 border border-indigo-500/20 rounded-full px-4 py-1.5 mb-6">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                <span className="text-indigo-400 text-xs font-mono uppercase tracking-widest">Agentic Readiness Score</span>
              </div>

              <h1 className="text-5xl sm:text-6xl font-black text-white leading-[1.05] mb-6 tracking-tight">
                Your site is<br />
                <span className="text-transparent bg-clip-text" style={{ backgroundImage: "linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%)" }}>
                  invisible to AI agents.
                </span>
              </h1>

              <p className="text-gray-400 text-lg leading-relaxed mb-10 max-w-lg">
                AI agents are booking, buying, and comparing -- right now. Most sites
                silently fail them. AgentProbe sends a real agent through your site and
                scores exactly where it gives up.
              </p>

              {/* URL input */}
              <div className="space-y-3 max-w-lg">
                <div className="relative">
                  <input
                    type="url"
                    value={url}
                    onChange={e => setUrl(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && runAudit()}
                    placeholder="https://your-site.com"
                    className="w-full bg-[#111118]/80 backdrop-blur border border-[#2a2a3a] focus:border-indigo-500 rounded-xl px-4 py-4 pr-36 text-white placeholder-gray-600 outline-none transition-colors text-sm"
                  />
                  <button
                    onClick={() => runAudit()}
                    disabled={loading || !url.trim() || (url.trim().length > 3 && !isValidUrl(url))}
                    className="absolute right-2 top-2 bottom-2 px-5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-bold text-sm text-white transition-all"
                  >
                    {loading ? (
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Starting
                      </span>
                    ) : "Run audit"}
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={label}
                    onChange={e => setLabel(e.target.value)}
                    placeholder="Label (optional)"
                    className="flex-1 bg-[#111118]/60 border border-[#2a2a3a] focus:border-indigo-500/50 rounded-lg px-4 py-2.5 text-white placeholder-gray-600 outline-none transition-colors text-xs font-mono"
                  />
                  <button
                    onClick={() => setShowTasks(s => !s)}
                    className={`px-3 py-2.5 rounded-lg border text-xs font-mono transition-all whitespace-nowrap ${
                      showTasks ? "border-indigo-500 text-indigo-300 bg-indigo-500/10" : "border-[#2a2a3a] text-gray-500 hover:border-gray-500"
                    }`}
                  >
                    {tasks.length}/{TASKS.length} tasks {showTasks ? "▲" : "▼"}
                  </button>
                </div>

                {error && <p className="text-red-400 text-xs font-mono">{error}</p>}

                <AnimatePresence>
                  {showTasks && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="grid grid-cols-2 gap-1.5 overflow-hidden"
                    >
                      {TASKS.map(t => (
                        <button
                          key={t.id}
                          onClick={() => toggleTask(t.id)}
                          className={`flex items-center gap-2 text-left px-3 py-2 rounded-lg border text-xs transition-all ${
                            tasks.includes(t.id)
                              ? "border-indigo-500/60 bg-indigo-500/10 text-indigo-300"
                              : "border-[#1e1e2e] text-gray-600 hover:border-gray-600"
                          }`}
                        >
                          <span>{t.icon}</span>
                          <div>
                            <p className="font-mono font-semibold">{t.label}</p>
                            <p className="text-[10px] opacity-60">{t.desc}</p>
                          </div>
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Demo shortcuts */}
              <div className="mt-6 flex flex-wrap gap-2">
                <span className="text-xs text-gray-600 font-mono self-center">Try:</span>
                {DEMOS.map(d => (
                  <button
                    key={d.url}
                    onClick={() => { setUrl(d.url); setLabel(d.label); runAudit(d.url); }}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-[#2a2a3a] text-xs text-gray-400 hover:border-indigo-500 hover:text-white transition-all disabled:opacity-40 font-mono"
                  >
                    <span
                      className="text-[10px] font-bold px-1 rounded"
                      style={{ color: d.expected.startsWith("A") ? "#10b981" : "#60a5fa" }}
                    >
                      {d.expected}
                    </span>
                    {d.label}
                  </button>
                ))}
              </div>
            </motion.div>

            {/* Right: Live terminal demo */}
            <motion.div
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.7, delay: 0.2 }}
              className="relative"
            >
              <div
                className="absolute -inset-4 rounded-2xl opacity-30"
                style={{ background: "radial-gradient(ellipse, #6366f130 0%, transparent 70%)" }}
              />
              <AgentTerminal />
            </motion.div>
          </div>
        </div>
      </section>

      {/* Dimension cards */}
      <section className="relative z-10 py-20 px-6 border-t border-[#1e1e2e]/60">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <p className="text-xs font-mono text-indigo-400 uppercase tracking-widest mb-3">Six dimensions</p>
            <h2 className="text-3xl font-bold text-white">What makes a site agent-ready</h2>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { dim: "Discoverability", w: "20%", icon: "🗺", desc: "Hop count from homepage to pricing, checkout, contact. Should be 2 or fewer.", color: "#6366f1" },
              { dim: "Parseability",    w: "20%", icon: "🔍", desc: "JSON-LD, ARIA labels, plain-text prices, form labels, Open Graph tags.", color: "#8b5cf6" },
              { dim: "Task Completion", w: "30%", icon: "✅", desc: "Did the agent actually finish the task end-to-end? Highest weight.", color: "#10b981" },
              { dim: "Friction",        w: "15%", icon: "🚧", desc: "CAPTCHAs, mandatory login walls, phone number fields, dead ends.", color: "#f59e0b" },
              { dim: "Clarity",         w: "10%", icon: "💡", desc: "Average agent confidence per step. Low confidence = ambiguous UI.", color: "#60a5fa" },
              { dim: "Resilience",      w: "5%",  icon: "🛡", desc: "Can the agent recover after hitting a wall or dead end?", color: "#a78bfa" },
            ].map((d, i) => (
              <motion.div
                key={d.dim}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.07 }}
                className="bg-[#111118]/80 backdrop-blur border border-[#1e1e2e] rounded-xl p-5 hover:border-indigo-500/30 transition-all group"
              >
                <div className="flex items-start justify-between mb-3">
                  <span className="text-2xl">{d.icon}</span>
                  <span
                    className="text-xs font-mono font-bold px-2 py-0.5 rounded-full"
                    style={{ color: d.color, background: `${d.color}20` }}
                  >
                    {d.w}
                  </span>
                </div>
                <h3 className="text-white font-bold mb-1.5">{d.dim}</h3>
                <p className="text-gray-500 text-xs leading-relaxed">{d.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="relative z-10 border-y border-[#1e1e2e]/60 py-10 px-6 bg-[#111118]/50">
        <div className="max-w-4xl mx-auto grid grid-cols-2 sm:grid-cols-4 gap-8 text-center">
          {[
            { label: "Free LLM",    value: "Groq",      sub: "llama-3.3-70b" },
            { label: "Max steps",   value: "15",         sub: "per task" },
            { label: "Tasks",       value: "7",          sub: "in parallel" },
            { label: "Stack cost",  value: "$0",         sub: "free tier everything" },
          ].map(s => (
            <div key={s.label}>
              <p className="text-2xl sm:text-3xl font-black text-white mb-0.5">{s.value}</p>
              <p className="text-xs text-gray-600 font-mono">{s.label}</p>
              <p className="text-[10px] text-gray-700 font-mono">{s.sub}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CI integration callout */}
      <section className="relative z-10 py-20 px-6">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="bg-[#111118] border border-[#1e1e2e] rounded-2xl overflow-hidden"
          >
            <div className="px-8 pt-8 pb-4">
              <p className="text-xs font-mono text-indigo-400 uppercase tracking-widest mb-3">CI integration</p>
              <h2 className="text-2xl font-bold text-white mb-2">Catch regressions before they ship</h2>
              <p className="text-gray-500 text-sm">
                Add one step to your CI pipeline. If ARS drops below your threshold, the check fails.
                Your redesign looked great to humans and broke AI agent checkout.
              </p>
            </div>
            <pre className="px-8 py-6 text-xs font-mono text-gray-300 bg-[#0d0d14] overflow-x-auto leading-relaxed">
{`# .github/workflows/agent-ux-check.yml
- uses: Aprameya05/agentprobe-action@v1
  with:
    url: \${{ vars.SITE_URL }}
    tasks: pricing_discovery,checkout_initiation
    min-ars: 70
    groq-api-key: \${{ secrets.GROQ_API_KEY }}`}
            </pre>
          </motion.div>
        </div>
      </section>

      {/* Recently audited */}
      {recentAudits.length > 0 && (
        <section className="relative z-10 py-20 px-6 border-t border-[#1e1e2e]/60">
          <div className="max-w-5xl mx-auto">
            <div className="flex items-end justify-between mb-8">
              <div>
                <p className="text-xs font-mono text-indigo-400 uppercase tracking-widest mb-2">Recently audited</p>
                <h2 className="text-2xl font-bold text-white">See how others score</h2>
              </div>
              <a href="/leaderboard" className="text-xs text-gray-500 hover:text-indigo-400 transition-colors font-mono">
                Full leaderboard →
              </a>
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {recentAudits.slice(0, 6).map((item: any, i: number) => {
                const meta = GRADE_META[item.grade] ?? { color: "#9ca3af" };
                let hostname = item.url;
                try { hostname = new URL(item.url).hostname; } catch {}
                return (
                  <motion.a
                    key={item.audit_id}
                    href={`/report/view/?id=${item.audit_id}`}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.06 }}
                    className="bg-[#111118] border border-[#1e1e2e] rounded-xl p-5 hover:border-indigo-500/40 hover:bg-[#14141f] transition-all group"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div
                        className="text-2xl font-black px-2 py-0.5 rounded-lg"
                        style={{ color: meta.color, background: `${meta.color}18` }}
                      >
                        {item.grade}
                      </div>
                      <span className="text-2xl font-black text-white">{(item.composite ?? 0).toFixed(0)}</span>
                    </div>
                    <p className="text-white text-sm font-semibold truncate group-hover:text-indigo-300 transition-colors">
                      {item.label || hostname}
                    </p>
                    <p className="text-gray-600 text-xs font-mono truncate mt-0.5">{hostname}</p>
                    <div className="flex gap-3 mt-3 text-[10px] font-mono text-gray-600">
                      <span>D:{(item.discoverability ?? 0).toFixed(0)}</span>
                      <span>P:{(item.parseability ?? 0).toFixed(0)}</span>
                      <span>T:{(item.task_completion ?? 0).toFixed(0)}</span>
                    </div>
                  </motion.a>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {/* Footer */}
      <footer className="relative z-10 border-t border-[#1e1e2e]/60 py-8 px-6">
        <div className="max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-gray-600 font-mono">
          <div className="flex items-center gap-4">
            <span className="text-indigo-400 font-bold text-sm">AgentProbe</span>
            <span>Apache 2.0</span>
            <span>Free, open source</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="https://github.com/Aprameya05/agentprobe" target="_blank" className="hover:text-white transition-colors">
              GitHub
            </a>
            <a href={`${API}/docs`} target="_blank" className="hover:text-white transition-colors">
              API
            </a>
            <a href="/leaderboard" className="hover:text-white transition-colors">
              Leaderboard
            </a>
          </div>
        </div>
      </footer>
    </main>
  );
}
