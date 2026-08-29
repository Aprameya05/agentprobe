```
     ___                    __  ____           __
    /   | ____ ____  ____  / /_/ __ \________/ /_  ___
   / /| |/ __ `/ _ \/ __ \/ __/ /_/ / ___/ __ __ \/ _ \
  / ___ / /_/ /  __/ / / / /_/ ____/ /  / /_/ /_/ /  __/
 /_/  |_\__, /\___/_/ /_/\__/_/   /_/   \____\____/\___/
        /____/
```

**Agentic Readiness Score for any website.**

AI agents are real traffic now. Booking agents, shopping agents, research agents -- they are clicking through your site right now, and most of them are silently giving up. SEO agencies built a whole industry around Google being the visitor. AgentProbe does the same thing for the new visitor.

Point it at a URL. A real GPT-OSS-120b agent navigates the site and attempts seven tasks: finding pricing, initiating checkout, extracting contact info, booking a demo, retrieving your refund policy, routing to support, and reaching API docs. Every click, every decision, every dead end is recorded. You get a scored report with exactly where the agent failed and why, compared against the industry baseline, with prioritized recommendations to fix each gap.

[Live Demo](https://agentprobe.pages.dev) &nbsp;|&nbsp;
[API Docs](https://agentprobe-api.onrender.com/docs) &nbsp;|&nbsp;
[Leaderboard](https://agentprobe.pages.dev/leaderboard) &nbsp;|&nbsp;
[Architecture](#architecture) &nbsp;|&nbsp;
[ARS Algorithm](#agentic-readiness-score)

---

## The problem

You redesign your pricing page. It looks great. Your conversion rate goes up 12%.

Three months later your AI traffic is routing elsewhere. A shopping agent tried to find your pricing, hit a "Contact Sales" wall, and moved on to your competitor in 800 milliseconds. You have no idea this is happening because your analytics only tracks humans.

Every observability tool built in the last decade assumes the visitor is a person. Lighthouse measures page speed for humans. Accessibility audits check WCAG for humans. SEO tools optimize for Google's crawler. Nobody is measuring what happens when an LLM tries to complete a task on your site.

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

The core insight: a browser agent and a human visitor use completely different signals to navigate a site. The agent reads ARIA labels, structured data, link text, and form labels. It cannot solve CAPTCHAs, cannot read prices rendered as SVGs, and gets confused by generic button text like "Click here." A site that scores 95 on Lighthouse can score 40 on ARS. They measure different things.

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

Each task runs up to 15 steps. The agent uses openai/gpt-oss-120b via Groq (free tier) and falls back to openai/gpt-oss-20b if the primary model is rate-limited. Tasks run sequentially to stay within Groq's free tier token limits (6,000 tokens per minute per model).

You can run all 7 tasks or pick a subset from the dashboard. Only the selected tasks are dispatched to GitHub Actions, so a single-task audit is much faster.

---

## Architecture

### How a full audit flows, step by step

**1. You submit a URL**

The dashboard (Next.js on Cloudflare Pages) sends a POST to the FastAPI backend with the URL, an optional label, and the list of selected tasks. The API creates an audit record in Neon Postgres with a unique ID and returns it immediately. Status is "queued". This takes under a second.

**2. GitHub Actions gets triggered**

In the background, the API calls the GitHub REST API to dispatch the `audit-worker.yml` workflow. It passes the audit ID, target URL, selected tasks as a comma-separated string, and the API's own URL so workers can post results back. If GitHub dispatch fails (network issue, expired token), the API falls back to running the agent in-process on Render itself.

**3. The workflow starts three jobs**

A `setup` job runs first. It takes the comma-separated task list, converts it to a JSON array, and outputs it as the matrix for the task jobs. This is how GitHub Actions knows to spin up 1 VM for a single task or 7 VMs for all tasks.

In parallel, `parseability` and the `task` jobs start.

**4. Parseability job (done in seconds)**

This job does not use a browser or an LLM. It fetches your page HTML, runs it through BeautifulSoup, and checks:
- JSON-LD structured data presence and completeness
- Schema.org markup coverage
- ARIA label coverage on interactive elements
- Form label coverage
- Whether prices appear as plain readable text
- Open Graph tags
- Meta descriptions

It computes a parseability score, posts it back to the API as a `parseability_done` event, and exits. This usually finishes in under 5 seconds.

**5. Task jobs (the actual browser agent)**

Each selected task gets its own GitHub Actions VM with 7GB of RAM and a fresh Chromium install. Each VM runs this loop:

- Navigate to the target URL
- Read the current page state (visible text, links, buttons, inputs, current URL)
- Send the page summary plus task description and action history to the LLM
- LLM returns a JSON action: `navigate`, `click`, `type`, `scroll`, `done`, or `failed`
- Execute the action in the browser via Playwright
- POST a step event to the API with what happened, the reasoning, and the confidence score
- Repeat until the task is done, failed, or 15 steps are reached

Tasks run sequentially (max-parallel: 1 in the GitHub Actions matrix) so they do not all hit Groq's token rate limit simultaneously.

**6. Live feed on the dashboard**

While tasks are running, the dashboard polls `/audit/{id}/events-poll` every 2-3 seconds. Each poll returns all events since the last one. Redis caches each response so that multiple dashboard tabs watching the same audit do not all hit Postgres. When new events arrive, the cache for that audit is invalidated immediately so the next poll gets fresh data.

**7. Aggregate job**

Once all task jobs finish, the `aggregate` job runs. It reads every `task_done` event from the API, reconstructs the full list of task results, runs the ARS scoring algorithm, generates recommendations, optionally enriches those recommendations with code fix suggestions (via Groq), and POSTs the completed report to `/internal/audit/{id}/complete`.

**8. Report appears**

The dashboard polls `/audit/{id}` every 3 seconds. When it sees a `report` field in the response, it stops polling and renders the full report: the radar chart, dimension scores vs industry baseline, per-task breakdown with individual steps, and prioritized recommendations.

### Infrastructure diagram

```
You (browser)
     |
     | HTTPS
     v
+-------------------------------+
| Cloudflare Pages              |
| Next.js 14 static export      |
| - Landing page + URL input    |
| - Task selector (pick 1-7)    |
| - Live audit view             |
| - Scored report page          |
| - Public leaderboard          |
+-------------------------------+
     |
     | POST /audit  (fetch API)
     v
+-------------------------------+     +---------------------------+
| Render (FastAPI + uvicorn)    |     | Redis (Render)            |
| - Validates URL               |<--->| - Caches leaderboard      |
| - Creates audit in Postgres   |     | - Caches events-poll      |
| - Dispatches GitHub workflow  |     | - Busts cache on new data |
| - Streams events via polling  |     +---------------------------+
| - Computes recommendations    |
| - Serves final report         |     +---------------------------+
|                               |<--->| Neon Postgres             |
| Falls back to in-process      |     | - audits table            |
| agent if GitHub dispatch fails|     | - audit_events table      |
+-------------------------------+     +---------------------------+
     |
     | workflow_dispatch (GitHub REST API)
     v
+----------------------------------------------+
| GitHub Actions                               |
|                                              |
| [setup job]                                  |
|   Parses tasks CSV into JSON matrix          |
|                                              |
| [parseability job] (parallel with tasks)     |
|   BeautifulSoup static analysis              |
|   POSTs parseability_done event to API       |
|                                              |
| [task jobs] (sequential, max-parallel: 1)    |
|   For each selected task:                    |
|   +----------------------------------------+|
|   | Playwright + Chromium                  ||
|   | Opens site, reads page                 ||
|   |         |                              ||
|   |         v                              ||
|   | Groq (GPT-OSS-120b / GPT-OSS-20b)     ||
|   | Decides next action (JSON)             ||
|   |         |                              ||
|   |         v                              ||
|   | Execute action, POST step event to API ||
|   | Repeat up to 15 steps                  ||
|   +----------------------------------------+|
|                                              |
| [aggregate job] (runs after all tasks)       |
|   Reads task_done events from API            |
|   Computes ARS score                         |
|   Generates recommendations                  |
|   POSTs final report to API                  |
+----------------------------------------------+
```

---

## Tech stack

### FastAPI (Python)

The backend API. We chose FastAPI because the agent work is heavily async: streaming events, waiting for GitHub to respond, handling multiple concurrent audit polls. FastAPI is built on top of Starlette and uses Python's asyncio natively, so none of these operations block each other. It also auto-generates OpenAPI docs at `/docs` which is useful for debugging.

### Neon Postgres

The database. Every audit, every step event, every task result goes here. We use Postgres because the aggregate job needs to join across events for a given audit, and relational queries are the right tool for that. Neon gives us serverless Postgres on a free tier with 0.5GB storage. We connect via asyncpg, an async Postgres driver that fits FastAPI's async model without thread overhead.

### Redis

An in-memory cache sitting in front of Postgres. The live feed dashboard polls every 2-3 seconds. Without Redis, every poll hits Postgres. With Redis, the first request computes and caches the result; all subsequent requests for the same data are served from memory in under a millisecond. We also use it to invalidate the leaderboard cache whenever an audit completes, so the leaderboard stays accurate without being recomputed on every request.

### GitHub Actions

On-demand Linux VMs used as browser compute. Running Playwright with Chromium needs real memory (easily 512MB per browser session). Render's free tier only gives us 512MB total for the API. Rather than paying for a bigger server, we use GitHub Actions which gives free CI minutes to public repos. Each VM gets 7GB RAM and 2 CPU cores. The API triggers runs via `workflow_dispatch` over the GitHub REST API. The workflow posts results back to the API over HTTPS. This is not a typical use of GitHub Actions (most people use it just for CI), but it works extremely well for this use case.

### Playwright + Chromium

The browser automation library. Playwright opens a real Chromium browser, navigates to pages, clicks elements, fills forms, and extracts page content. After every action it returns a structured summary of what is on the screen: visible text, clickable elements, form fields, current URL. This summary is what goes to the LLM for the next decision. We use headless mode (no visible window) since it runs on a Linux VM with no display.

### Groq (LLM API)

Fast inference API for the decision loop. After each browser action, we send the current page state plus the task description to Groq and ask "what should you do next?" The model responds with a JSON object containing an action type, a target (CSS selector or URL), an optional value to type, a one-sentence reasoning, and a confidence score. We use GPT-OSS-120b as the primary model and fall back to GPT-OSS-20b if the primary is rate-limited. If both models fail, we retry with exponential backoff (20s, 40s, 60s) before giving up. The system prompt explicitly tells the model not to use tool calls and to output raw JSON only, because the GPT-OSS models are tool-aware and will try to call browser APIs if not told otherwise.

### Next.js 14 (App Router)

The frontend framework. We use the App Router with static export, meaning at build time Next.js generates plain HTML/CSS/JS files with no server component. This is important because Cloudflare Pages serves static files only. Dynamic data (audit results, live events) is loaded client-side via fetch. The dashboard uses Tailwind for styling, Recharts for the radar chart and dimension bars, and Framer Motion for animations.

### Cloudflare Pages

Static file hosting for the frontend. It serves the Next.js output from Cloudflare's global CDN, so the dashboard loads fast from anywhere. Free tier includes unlimited bandwidth. We have rewrite rules in `_redirects` so that `/audit/view/` and `/report/view/` serve the right pages even though it is a single-page app.

### Docker + Docker Compose

Docker packages the API into a container so it runs identically in local development and on Render. The Dockerfile installs Python dependencies, copies the code, and defines the startup command. Docker Compose adds the dashboard container alongside it so you can run the entire stack locally with one command. This is how you develop and test locally before pushing.

### UptimeRobot

A free monitoring service that pings `https://agentprobe-api.onrender.com/health` every 5 minutes. Render's free tier shuts down the API after 15 minutes of no traffic. Without UptimeRobot, the first person to submit an audit after a quiet period would wait 30+ seconds for Render to cold-start. UptimeRobot keeps it warm.

### k6 (Load testing)

k6 is a load testing tool that simulates many concurrent users hitting the API. The k6 scripts in this repo test things like: what happens when 50 people submit audits at the same time, how does the events-poll endpoint hold up under load, where does latency degrade. This is not running continuously in production -- it is used periodically to identify bottlenecks before they become real problems.

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

---

## Repo structure

```
agentprobe/
|
+-- api/
|   +-- main.py              FastAPI routes: submit audit, poll events, leaderboard, compare, internal worker endpoints
|   +-- models.py            Pydantic v2 models: AuditRequest, TaskResult, ARSBreakdown, Recommendation, etc.
|   +-- database.py          Neon Postgres via asyncpg: create/read audits and events
|   +-- scoring.py           ARS engine: 6 dimension scorers, composite calculator, recommendation generator
|   +-- fixcode.py           Enriches recommendations with concrete code fix suggestions via Groq
|   +-- cache.py             Redis cache layer: get/set/delete/invalidate for events-poll and leaderboard
|   +-- agent/
|   |   +-- browser.py       Playwright BrowserSession, get_page_summary(), execute_action()
|   |   +-- runner.py        Main agent loop: step execution, event streaming, in-process fallback
|   |   +-- claude_loop.py   Groq decision loop: sends page state to LLM, parses JSON response, retries on rate limit
|   |   +-- parseability.py  Static BeautifulSoup analyzer: JSON-LD, ARIA, prices, forms, OG tags
|   +-- tasks/
|   |   +-- registry.py      7 task definitions with descriptions, weights, and success criteria
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- dashboard/               Next.js 14, App Router, static export, Tailwind, Recharts, Framer Motion
|   +-- src/app/
|   |   +-- page.tsx         Landing page: URL input, task selector (pick 1-7), example site chips
|   |   +-- audit/view/      Live audit view: polls events-poll endpoint, renders step feed in real time
|   |   +-- report/view/     Scored report: radar chart, dimension bars vs baseline, task drill-down, recommendations
|   |   +-- leaderboard/     Public ARS leaderboard with industry baseline overlay
|   +-- public/_redirects    Cloudflare rewrite rules for client-side routing
|   +-- next.config.js       Static export config for Cloudflare Pages
|
+-- worker/
|   +-- run_task.py          Single-task runner called by GitHub Actions matrix job
|   +-- run_parseability.py  Parseability-only job: fetches HTML, runs static analysis, posts score
|   +-- aggregate.py         Runs after all task jobs: reads task_done events, computes ARS, posts final report
|
+-- .github/workflows/
|   +-- ci.yml               Import and syntax checks on every push (under 30 seconds)
|   +-- audit-worker.yml     Workflow dispatched by API: setup job, parseability job, sequential task matrix, aggregate job
|
+-- infra/
|   +-- schema.sql           Neon Postgres schema: audits table, audit_events table, indexes
|   +-- render.yaml          Render deploy config: API service and Redis service definitions
|   +-- k6/                  Load test scripts for API endpoints under concurrent traffic
|
+-- docker-compose.yml       Local development: API + dashboard running together
+-- .env.example             All environment variables with descriptions
```

---

## Quickstart (local)

**Prerequisites:** Docker, Python 3.10+, a Groq API key (free at console.groq.com), a Neon account (free at neon.tech).

```bash
# 1. Clone
git clone https://github.com/Aprameya05/agentprobe
cd agentprobe

# 2. Init the database
# Go to neon.tech, create a project, paste the connection string into .env
psql $DATABASE_URL -f infra/schema.sql

# 3. Configure environment
cp .env.example .env
# Fill in: GROQ_API_KEY, DATABASE_URL, WORKER_SECRET

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

# Audit a site (all 7 tasks)
agentprobe audit https://stripe.com

# Run specific tasks only
agentprobe audit https://notion.so --tasks pricing checkout contact

# Compare two sites
agentprobe compare https://stripe.com https://paddle.com

# Output formats
agentprobe audit https://linear.app --format json
agentprobe audit https://linear.app --format table   # default
```

---

## GitHub Action (CI integration)

Add to your pipeline to catch agent UX regressions before they ship:

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
          min-ars: 70
          groq-api-key: ${{ secrets.GROQ_API_KEY }}
          api-url: https://agentprobe-api.onrender.com
```

The action posts ARS and a per-task summary to the job summary so it is visible directly in the GitHub PR.

---

## Deployment

**API (Render):**

```bash
# Connect repo to Render, select Docker runtime.
# Set environment variables in the Render dashboard:
#   DATABASE_URL  GROQ_API_KEY  GITHUB_PAT  WORKER_SECRET  REDIS_URL  API_BASE_URL

# Add UptimeRobot monitor pointing to:
# https://agentprobe-api.onrender.com/health
# Interval: every 5 minutes. Keeps Render free tier from sleeping.
```

**Dashboard (Cloudflare Pages):**

```bash
cd dashboard && npm run build
# Connect the /dashboard directory to Cloudflare Pages.
# Set NEXT_PUBLIC_API_URL to your Render URL in Cloudflare Pages environment variables.
```

**GitHub Actions secrets (required for the audit worker):**

```
GROQ_API_KEY      your Groq API key
WORKER_SECRET     same value as WORKER_SECRET on Render (authenticates worker POST requests)
```

---

## Environment variables

```bash
# Required
GROQ_API_KEY=gsk_...            # Free at console.groq.com
DATABASE_URL=postgresql://...   # Free at neon.tech

# Required for GitHub Actions compute
GITHUB_PAT=ghp_...              # Personal access token with repo + workflow scopes
GITHUB_OWNER=Aprameya05
GITHUB_REPO=agentprobe
WORKER_SECRET=...               # Random 32-char string, shared with GitHub Actions secrets

# Required for Redis caching
REDIS_URL=redis://...           # Set automatically if using Render Redis addon

# Set automatically by Render
API_BASE_URL=https://agentprobe-api.onrender.com

# Optional
ALLOWED_ORIGINS=https://agentprobe.pages.dev,http://localhost:3000
DEBUG=false
```

---

## Free infrastructure breakdown

| Component | Service | Free tier limits |
|---|---|---|
| API | Render | 512 MB RAM, sleeps after 15 min (UptimeRobot keepalive) |
| Browser compute | GitHub Actions | 2000 min/month public repo, sequential matrix |
| LLM | Groq | 14,400 req/day, 6000 tokens/min per model |
| Database | Neon Postgres | 0.5 GB storage, 1 project |
| Cache | Redis (Render) | 25 MB, shared instance |
| Dashboard | Cloudflare Pages | Unlimited bandwidth, global CDN |
| Keepalive | UptimeRobot | 50 monitors, 5-min interval |
| Load testing | k6 | Open source, runs locally |

Total monthly cost to run this in production: $0.

---

Apache 2.0 -- built in public -- PRs welcome