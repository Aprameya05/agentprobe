# Horizontal scaling guide

AgentProbe is designed to scale horizontally with zero code changes for
most of the stack. The one thing that needs attention is the SSE event bus.

## What scales automatically

- **GitHub Actions workers** -- each audit triggers a new workflow run;
  GitHub's parallel job limit (20 concurrent for public repos) is the ceiling.
  You never run out of compute -- you just queue up behind it.
- **Neon Postgres** -- connection pooling via asyncpg; the API uses 1-5
  connections per instance. Add a PgBouncer proxy (Neon's built-in one, free)
  if you scale past 10 API replicas.
- **Cloudflare Pages** -- the dashboard is a static export. It runs on
  Cloudflare's global CDN. No scaling concerns.
- **Redis caching** -- Upstash Redis is managed and horizontally scaled by
  the provider. Your API instances all read from the same cache.

## The one thing that doesn't scale automatically: SSE

The live event stream uses an **in-memory asyncio.Queue** per audit.
If you run two API replicas (two Render instances), a dashboard connected
to replica A won't receive events that the worker posted to replica B.

### Fix: Redis pub/sub SSE (upgrade path)

Replace the in-memory bus with Redis pub/sub. The change is contained to
`api/main.py`:

```python
# Replace _broadcast():
async def _broadcast(audit_id: str, event: dict) -> None:
    payload = json.dumps(event)
    # Publish to Redis channel (all replicas subscribed to this channel get it)
    await cache._client.publish(f"audit:{audit_id}:events", payload)
    await db.append_event(audit_id, event)

# Replace _sse_generator():
async def _sse_generator(audit_id, request):
    # Replay past events
    past = await db.get_events_since(audit_id, after_id=0)
    for ev in past:
        yield f"data: {json.dumps(ev)}\n\n"

    # Subscribe to Redis channel
    async with cache._client.pubsub() as ps:
        await ps.subscribe(f"audit:{audit_id}:events")
        async for msg in ps.listen():
            if await request.is_disconnected():
                break
            if msg["type"] == "message":
                yield f"data: {msg['data']}\n\n"
```

This is a 20-line change. Until you need more than one Render instance
(free tier is single-instance anyway), the in-memory bus is fine.

## Load test before scaling

Run the k6 load test first to find your actual bottleneck:

```bash
# Install k6 (macOS)
brew install k6

# Smoke test (quick sanity check)
k6 run --env BASE_URL=https://agentprobe-api.onrender.com \
       --env SCENARIO=smoke k6/load_test.js

# Load test (find the breaking point)
k6 run --env BASE_URL=https://agentprobe-api.onrender.com \
       --env SCENARIO=load k6/load_test.js
```

The leaderboard and audit report endpoints are cached, so they should
handle 50+ concurrent users on a single Render 512 MB instance. The
POST /audit endpoint is rate-limited to 10/min/IP to prevent abuse.

## Render free tier limits

| Resource | Free tier | When you'll hit it |
|---|---|---|
| RAM | 512 MB | Never for the API alone (Playwright runs on GH Actions) |
| CPU | Shared | Under sustained load -- upgrade to Starter ($7/month) |
| Sleep | After 15 min idle | UptimeRobot keepalive prevents this |
| Bandwidth | 100 GB/month | ~10 million audit requests |

For the Neon free tier (0.5 GB storage), the housekeeping queries in
`infra/schema.sql` keep the DB small. Set up a weekly scheduled query
in the Neon dashboard to prune old events.
