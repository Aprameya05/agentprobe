```
     ___                    __  ____           __
    /   | ____ ____  ____  / /_/ __ \________/ /_  ___
   / /| |/ __ `/ _ \/ __ \/ __/ /_/ / ___/ __ __ \/ _ \
  / ___ / /_/ /  __/ / / / /_/ ____/ /  / /_/ /_/ /  __/
 /_/  |_\__, /\___/_/ /_/\__/_/   /_/   \____\____/\___/
        /____/
```

**Agentic Readiness Score for any website.**

AI agents are real traffic now. Booking agents, shopping agents, research agents -- they are
clicking through your site right now, and most of them are silently giving up. SEO agencies
built a whole industry around Google being the visitor. AgentProbe does the same thing for
the new visitor.

Point it at a URL. A real GPT-OSS-120b agent navigates the site and attempts seven tasks:
finding pricing, initiating checkout, extracting contact info, booking a demo, retrieving
your refund policy, routing to support, and reaching API docs. Every click, every decision,
every dead end is recorded. You get a scored report with exactly where the agent failed and
why, compared against the industry baseline, with prioritized recommendations to fix each gap.

[Live Demo](https://agentprobe.pages.dev) &nbsp;|&nbsp;
[API Docs](https://agentprobe-api.onrender.com/docs) &nbsp;|&nbsp;
[Leaderboard](https://agentprobe.pages.dev/leaderboard) &nbsp;|&nbsp;
[Architecture](#architecture) &nbsp;|&nbsp;
[ARS Algorithm](#agentic-readiness-score)

---

## The problem

You redesign your pricing page. It looks great. Your conversion rate goes up 12%.

Three months later your AI traffic is routing elsewhere. A shopping agent tried to find
your pricing, hit a "Contact Sales" wall, and moved on to your competitor in 800 milliseconds.
You have no idea this is happening because your analytics only tracks humans.

Every observability tool built in the last decade assumes the visitor is a person.
Lighthouse measures page speed for humans. Accessibility audits check WCAG for humans.
SEO tools optimize for Google's crawler. Nobody is measuring what happens when an LLM
tries to complete a task on your site.

That is the gap AgentProbe closes.

---

## What AgentProbe does differently

| Capability | Lighthouse | Semrush | AgentProbe |
|---|:---:|:---:|:---:|
| Page speed score | Yes | No | No (not relevant to agents) |
| SEO / crawlability | No | Yes | Partial |
| ARIA / accessibility | Yes | No | Yes |
| Agent can find pricing | No | No | **Yes** |
| Agent can reach checkout | No | No | **Yes** |
| CAPTCHA / login wall detection | No | No | **Yes** |
| Machine-readable price detection | No | No | **Yes** |
| Agent confidence per step | No | No | **Yes** |
| Friction Index (AFI) | No | No | **Yes** |
| JSON-LD / Schema.org analysis | No | Partial | **Yes** |
| Compared to industry baseline | No | Yes | **Yes** |
| Runs as CI check on every deploy | No | No | **Yes** |
| Free, open source | No | No | **Yes** |

The core insight: a browser agent and a human visitor use completely different signals
to navigate a site. The agent reads ARIA labels, structured data, link text, and
form labels. It cannot solve CAPTCHAs, cannot read prices rendered as SVGs, and gets
confused by generic button text like "Click here." A site that scores 95 on Lighthouse
can score 40 on ARS. They measure different things.

---

## Agentic Readiness Score

ARS is a six-dimensional composite score, 0-100, computed from a real agent browsing session.

```
ARS = 0.20 * Discoverability
    + 0.20 * Parseability
    + 0.30 * Task Completion      <-- highest weight: does it actually work?
    + 0.15 * Friction
    + 0.10 * Clarity
    + 0.05 * Resilience
```

| Dimension | Weight | What it measures |
|---|---|---|
| **Discoverability** | 20% | Shortest path from homepage to key pages (pricing, contact, checkout). Scored by hop count: 1 hop = 100, 2 hops = 75, 3 = 55, 4+ = 35. |
| **Parseability** | 20% | Static analysis: JSON-LD structured data, Schema.org markup, ARIA label coverage, form label coverage, plain-text prices, Open Graph tags. |
| **Task Completion** | 30% | Binary per task (completed = 100, failed = 0) with partial credit for meaningful progress. Weighted by task importance (checkout = 2x, pricing = 1.5x). |
| **Friction** | 15% | Starts at 100. Deductions: -25 per CAPTCHA or login wall, -10 per required blocking field (phone, SSN), -8 per backtrack, -4 per low-confidence step. |
| **Clarity** | 10% | Average agent confidence across all steps (0-1 scale, scaled to 100). Penalizes high variance -- an inconsistently confusing site is worse than a consistently average one. |
| **Resilience** | 5% | When the agent hits walls, can it recover? Recovery rate = successful task completions despite friction / total friction events. |

**Grades:** A+ (90+), A (80+), B (70+), C (60+), D (50+), F (<50)

**Industry baselines** (derived from pilot audits across 50 sites):
Discoverability 68, Parseability 52, Task Completion 57, Friction 63, Clarity 61, Resilience 72.

---

## Seven task templates

```
PRICING_DISCOVERY     Find and extract pricing for at least one plan with currency + period.
CHECKOUT_INITIATION   Reach a checkout, payment, or subscription confirmation page.
CONTACT_EXTRACTION    Find at least one direct contact method (email, phone, chat, form).
DEMO_BOOKING          Reach a scheduling page or successfully submit a demo/trial request.
POLICY_RETRIEVAL      Extract key terms from the refund, return, or cancellation policy.
SUPPORT_ROUTING       Reach a support ticket form or help center.
API_DISCOVERY         Reach API reference docs or a developer portal.
```

Each task runs up to 15 steps. The agent uses openai/gpt-oss-120b via Groq (free tier)
and falls back to openai/gpt-oss-20b if the primary model is rate-limited.

---

## Architecture

```
User submits URL
       |
       v
+---------------------------+
| FastAPI (Render free)     |   POST /audit
| - creates audit record    |   returns audit_id immediately
| - dispatches GA workflow  |
+---------------------------+
       |
       | GitHub workflow_dispatch (REST API)
       v
+----------------------------------+     +----------------------------------+
| GitHub Actions -- parallel matrix |     | Parseability job (runs first)    |
|                                   |     | BeautifulSoup static analysis    |
| task: PRICING_DISCOVERY     ----+ |     | JSON-LD, ARIA, prices, OG tags   |
| task: CHECKOUT_INITIATION   ----+ |     | POSTs score to API in <5 seconds |
| task: CONTACT_EXTRACTION    ----+ |     +----------------------------------+
| task: DEMO_BOOKING          ----+ |
| task: POLICY_RETRIEVAL      ----+ |   Each task job:
| task: SUPPORT_ROUTING       ----+ |     - Playwright chromium (free)
| task: API_DISCOVERY         ----+ |     - Llama 3.3-70b via Groq (free)
|                              |    |     - POSTs step events to API (SSE)
| aggregate job (waits for all)|    |     - POSTs final task result to API
+----------------------------------+
       |
       | POST /audit/{id}/complete
       v
+---------------------------+     +---------------------------+
| Neon Postgres (free)      |     | SSE event stream          |
| - audits table            |<--->| Dashboard polls /events   |
| - audit_events table      |     | Live step feed as it runs |
+---------------------------+     +---------------------------+
       |
       v
+---------------------------+
| Next.js 14 (Cloudflare    |
| Pages, free, global CDN)  |
| - Landing + URL input     |
| - Live audit view (SSE)   |
| - Scored report page      |
| - Public leaderboard      |
+---------------------------+
```

**Stack -- 100% free infrastructure:**

| Component | Service | Free tier |
|---|---|---|
| API | Render | 512 MB, sleeps after 15 min (UptimeRobot keepalive) |
| Browser compute | GitHub Actions | 2000 min/month public repo, parallel matrix |
| LLM | Groq | 14,400 req/day, openai/gpt-oss-120b |
| Database | Neon Postgres | 0.5 GB, 1 project |
| Dashboard | Cloudflare Pages | Unlimited bandwidth, global CDN |
| Keepalive | UptimeRobot | 50 monitors, 5-min interval |

---

## Quickstart

**Prerequisites:** Docker, Python 3.10+, a Groq API key (free at console.groq.com), a Neon
account (free at neon.tech).

```bash
# 1. Clone
git clone https://github.com/Aprameya05/agentprobe
cd agentprobe

# 2. Init the database
# Go to neon.tech, create a project, paste the connection string into .env
# Then run:
psql $DATABASE_URL -f infra/schema.sql

# 3. Configure environment
cp .env.example .env
# Fill in: GROQ_API_KEY, DATABASE_URL

# 4. Start the full stack
docker compose up -d

# 5. Open dashboard
# http://localhost:3000
```

**Or run the API standalone (no Docker):**

```bash
cd api
pip install -r requirements.txt
playwright install chromium
uvicorn api.main:app --reload
```

---

## CLI usage

```bash
pip install agentprobe

# Audit a site
agentprobe audit https://stripe.com

# Run specific tasks only
agentprobe audit https://notion.so --tasks pricing checkout contact

# Compare two sites
agentprobe compare https://stripe.com https://paddle.com

# Output formats
agentprobe audit https://linear.app --format json
agentprobe audit https://linear.app --format table   # default
```

Output:

```
Auditing https://stripe.com...
Running 7 tasks in parallel...

  PRICING_DISCOVERY    ✓ completed    3 steps    4.2s    confidence 0.91
  CHECKOUT_INITIATION  ✓ completed    5 steps    8.1s    confidence 0.84
  CONTACT_EXTRACTION   ✓ completed    2 steps    2.9s    confidence 0.95
  DEMO_BOOKING         ✓ completed    4 steps    6.3s    confidence 0.88
  POLICY_RETRIEVAL     ✓ completed    3 steps    4.8s    confidence 0.90
  SUPPORT_ROUTING      ✓ completed    2 steps    3.1s    confidence 0.93
  API_DISCOVERY        ✓ completed    2 steps    2.7s    confidence 0.97

Agentic Readiness Score: 91 / 100   A+

  Discoverability   94   +26 vs industry avg
  Parseability      88   +36 vs industry avg
  Task Completion  100   +43 vs industry avg
  Friction          85   +22 vs industry avg
  Clarity           91   +30 vs industry avg
  Resilience       100   +28 vs industry avg

No critical issues. 2 info-level suggestions.
Full report: https://agentprobe.pages.dev/report/aud_abc123
```

---

## GitHub Action

Add to your CI pipeline to catch agent UX regressions before they ship:

```yaml
# .github/workflows/agent-ux-check.yml
name: Agent UX check

on: [push, pull_request]

jobs:
  agentprobe:
    runs-on: ubuntu-latest
    steps:
      - uses: Aprameya05/agentprobe-action@v1
        with:
          url: ${{ vars.SITE_URL }}
          tasks: pricing_discovery,checkout_initiation
          min-ars: 70       # Fail the check if ARS drops below 70
          groq-api-key: ${{ secrets.GROQ_API_KEY }}
          api-url: https://agentprobe-api.onrender.com
```

The action posts ARS and a per-task summary to the job summary so it's visible
directly in the GitHub PR.

---

## Repo structure

```
agentprobe/
|
+-- api/
|   +-- main.py              FastAPI routes (submit, stream events, leaderboard, compare)
|   +-- models.py            Pydantic v2 models (AuditRequest, TaskResult, ARSBreakdown, ...)
|   +-- database.py          Neon Postgres via asyncpg
|   +-- scoring.py           ARS engine -- 6 scorers + recommendation generator
|   +-- agent/
|   |   +-- browser.py       Playwright BrowserSession, get_page_summary(), execute_action()
|   |   +-- runner.py        Main agent loop -- task execution, event streaming
|   |   +-- claude_loop.py   Groq/Llama decision loop with JSON response parsing
|   |   +-- parseability.py  Static BeautifulSoup analyzer (JSON-LD, ARIA, prices, OG)
|   +-- tasks/
|   |   +-- registry.py      7 task templates with descriptions and weights
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- dashboard/               Next.js 14, App Router, Tailwind, Recharts, Framer Motion
|   +-- src/app/
|   |   +-- page.tsx         Landing page + URL input + task selector
|   |   +-- audit/view/      Live audit view -- reads ID from URL, polls event feed
|   |   +-- report/view/     Scored report: radar chart, dim bars, recommendations, task drill-down
|   |   +-- leaderboard/     Public ARS leaderboard with industry baseline overlay
|   +-- public/_redirects    Cloudflare rewrite rules for /audit/* and /report/*
|   +-- next.config.js       Static export for Cloudflare Pages
|
+-- worker/
|   +-- run_task.py          Single-task runner (called by GitHub Actions matrix)
|   +-- run_parseability.py  Parseability-only job
|   +-- aggregate.py         Waits for all tasks, computes ARS, posts final report
|
+-- .github/workflows/
|   +-- ci.yml               Import checks on every push (< 30 seconds)
|   +-- audit-worker.yml     Sequential task matrix triggered by API dispatch
|
+-- infra/
|   +-- schema.sql           Neon Postgres schema (audits + audit_events)
|   +-- render.yaml          Render deploy config
|
+-- docker-compose.yml       Full local stack (API + dashboard)
+-- .env.example
```

---

## Deployment

**API (Render free tier):**

```bash
# Connect your repo to Render, select Docker runtime.
# Set environment variables in the Render dashboard:
#   DATABASE_URL  GROQ_API_KEY  GITHUB_PAT  WORKER_SECRET

# UptimeRobot: add a monitor to https://agentprobe-api.onrender.com/health
# to keep the free tier alive (Render sleeps after 15 min of inactivity).
```

**Dashboard (Cloudflare Pages):**

```bash
cd dashboard && npm run build
# Connect the /dashboard directory to Cloudflare Pages.
# Set NEXT_PUBLIC_API_URL to your Render URL in Cloudflare Pages settings.
```

**GitHub Actions secrets (for the audit worker):**

```
GROQ_API_KEY    your Groq API key
WORKER_SECRET   same as the WORKER_SECRET env var on Render
```

---

## Environment variables

```bash
# Required
GROQ_API_KEY=gsk_...            # Free at console.groq.com
DATABASE_URL=postgresql://...   # Free at neon.tech

# Optional (enables GitHub Actions compute for parallel task execution)
GITHUB_PAT=ghp_...              # repo + workflow scopes
GITHUB_OWNER=Aprameya05
GITHUB_REPO=agentprobe
WORKER_SECRET=...               # random 32-char string, shared with GH Actions secrets

# Set automatically by Render
API_BASE_URL=https://agentprobe-api.onrender.com
```

---

Apache 2.0 -- built in public -- PRs welcome
