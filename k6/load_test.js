/**
 * AgentProbe -- k6 load test
 *
 * Tests three traffic patterns:
 *   smoke   --  2 VUs, 30 s  -- sanity check before anything else
 *   load    -- 20 VUs, 2 min -- normal expected traffic
 *   spike   -- ramp to 50 VUs in 10 s, hold 30 s, ramp down
 *
 * Run:
 *   # Smoke (quick sanity)
 *   k6 run --env BASE_URL=https://agentprobe-api.onrender.com \
 *          --env SCENARIO=smoke k6/load_test.js
 *
 *   # Full load test
 *   k6 run --env BASE_URL=https://agentprobe-api.onrender.com \
 *          --env SCENARIO=load k6/load_test.js
 *
 *   # Spike test (can the API survive a sudden burst?)
 *   k6 run --env BASE_URL=https://agentprobe-api.onrender.com \
 *          --env SCENARIO=spike k6/load_test.js
 *
 * Install k6:  https://k6.io/docs/getting-started/installation/
 * Free, open source, runs locally.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

// ---------------------------------------------------------------------------
// Custom metrics
// ---------------------------------------------------------------------------
const errorRate = new Rate("error_rate");
const auditSubmitDuration = new Trend("audit_submit_duration", true);
const leaderboardDuration = new Trend("leaderboard_duration", true);

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SCENARIO  = __ENV.SCENARIO  || "smoke";

const scenarios = {
  smoke: {
    executor: "constant-vus",
    vus: 2,
    duration: "30s",
  },
  load: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "30s", target: 10 },  // ramp up
      { duration: "90s", target: 20 },  // hold
      { duration: "30s", target: 0 },   // ramp down
    ],
  },
  spike: {
    executor: "ramping-vus",
    startVUs: 0,
    stages: [
      { duration: "10s", target: 50 },  // sudden spike
      { duration: "30s", target: 50 },  // hold
      { duration: "15s", target: 0 },   // recover
    ],
  },
};

export const options = {
  scenarios: { [SCENARIO]: scenarios[SCENARIO] },

  // Pass/fail thresholds
  thresholds: {
    // 95th-percentile response time under 2 s
    http_req_duration: ["p(95)<2000"],
    // Error rate must stay under 5%
    error_rate: ["rate<0.05"],
    // Audit submit p95 under 3 s (it dispatches a background job)
    audit_submit_duration: ["p(95)<3000"],
    // Leaderboard (cached) p95 under 500 ms
    leaderboard_duration: ["p(95)<500"],
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const HEADERS = { "Content-Type": "application/json" };

const TEST_URLS = [
  "https://stripe.com",
  "https://notion.so",
  "https://linear.app",
  "https://vercel.com",
];

function randomUrl() {
  return TEST_URLS[Math.floor(Math.random() * TEST_URLS.length)];
}

// ---------------------------------------------------------------------------
// Main scenario
// ---------------------------------------------------------------------------
export default function () {
  const rng = Math.random();

  // 50% -- health check (cheapest, validates liveness)
  if (rng < 0.50) {
    const res = http.get(`${BASE_URL}/health`);
    const ok = check(res, {
      "health: status 200": (r) => r.status === 200,
      "health: body has ok": (r) => r.json("status") === "ok",
    });
    errorRate.add(!ok);
    sleep(0.5);
    return;
  }

  // 30% -- leaderboard (should be cache hit after first request)
  if (rng < 0.80) {
    const start = Date.now();
    const res = http.get(`${BASE_URL}/leaderboard`);
    leaderboardDuration.add(Date.now() - start);
    const ok = check(res, {
      "leaderboard: status 200": (r) => r.status === 200,
      "leaderboard: has array": (r) => Array.isArray(r.json("leaderboard")),
    });
    errorRate.add(!ok);
    sleep(1);
    return;
  }

  // 20% -- submit an audit (this hits the rate limiter at high VU counts,
  // which is intentional -- we verify 429s are handled gracefully)
  const start = Date.now();
  const res = http.post(
    `${BASE_URL}/audit`,
    JSON.stringify({ url: randomUrl(), tasks: ["PRICING_DISCOVERY"] }),
    { headers: HEADERS }
  );
  auditSubmitDuration.add(Date.now() - start);

  // 429 is expected under spike load -- not counted as error
  const ok = check(res, {
    "audit: accepted or rate-limited": (r) => [200, 201, 429].includes(r.status),
    "audit: no 500": (r) => r.status < 500,
  });
  errorRate.add(!ok);

  if (res.status === 200 || res.status === 201) {
    const auditId = res.json("audit_id");
    if (auditId) {
      // Follow up with a status poll (simulates the dashboard)
      sleep(0.5);
      const statusRes = http.get(`${BASE_URL}/audit/${auditId}`);
      check(statusRes, {
        "audit status: 200": (r) => r.status === 200,
      });
    }
  }

  sleep(1);
}
