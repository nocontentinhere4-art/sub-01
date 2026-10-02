# SUB-01 — operations: costs, caps, health, monitoring (#15)

## What costs money, and where it is logged
| service | what | logged in | cap (USD per Tokyo day) |
|---|---|---|---|
| `eye` | FLUX schnell frames ($0.003 each) + the eye's Llama 3 8B thought (Replicate) | `/data/costs.jsonl` | `SUB01_CAP_EYE_USD` = 1.00 |
| `diary` | the diary text each morning (Llama 3 8B, 1–2 calls, < $0.001) | `/data/costs.jsonl` | `SUB01_CAP_DIARY_USD` = 0.10 |
| `eyes` | the brain-decides options, one call per page (Haiku 4.5) | `/data/eyes_costs.jsonl` | `SUB01_CAP_EYES_USD` = 1.00 |
| `mind` | page notes, the day plan, chat replies (Haiku 4.5) | `/data/eyes_costs.jsonl` (provider `mind/…`) | `SUB01_CAP_MIND_USD` = 1.00 |
| all of the above | | | `SUB01_CAP_TOTAL_USD` = 3.10 |
| `runpod` | the nightly spiking memory test | `/data/spiking/costs.jsonl` | its own: 1 GPU-h/day, 8 GPU-h per 7 days |

`costs.py` adds the three files up on the Tokyo day (`sleep.ROME`). Each cost is written to one file only, so nothing
is counted twice. The eyes and the mind still share one ledger with its $2.00/day total and 30 calls/hour
(`mind.shared_budget`). `SUB01_CAP_EYES_USD` and `SUB01_CAP_MIND_USD` are new names for that ledger's two shares; the old
`EYES_MAX_USD_PER_DAY` and `MIND_MAX_USD_PER_DAY` still work.

The total's default is the sum of its parts (1.00 + 1.00 + 1.00 + 0.10 = 3.10). With the defaults no part can use up
another part's budget; the total only bites if someone raises a part's cap. RunPod is not in it.

## What each cap does
Every cap is checked **before** each paid call. Over a cap, the feature takes its free path until the Tokyo midnight:
- **eye:** no new frames. The last frame stays up and the pages say "resting its eyes" (`/brain`, `/world.html`, the
  `resting` field of `/api/frames` and of the `eye` websocket message). Unwatched dream frames for the diary stop too.
- **diary:** the morning entry uses its template text ("SUB-01 slept … and replayed …").
- **eyes:** local options from the page's own links (`/api/decisions` shows `why_local`).
- **mind:** keyword-only notes, yesterday's plan, no chat replies ("resting").
- **total:** all four of the above at once.

A cap at `0` turns that paid service off. Caps are read from the environment: change them in Railway's Variables tab
(the service restarts). Without `REPLICATE_API_TOKEN` the eye is not paid at all and has no cap check.

## Reading `/api/costs`
It is private. Behind `SITE_PASSWORD` the login cookie opens it. Without `SITE_PASSWORD` (after launch) it needs the
`SUB01_ADMIN_TOKEN` header; with no token configured it always answers 401. Set a long random `SUB01_ADMIN_TOKEN` on
Railway (never commit it), then:

```sh
curl -s -H "X-Admin-Token: $SUB01_ADMIN_TOKEN" https://sub01-production.up.railway.app/api/costs | jq
```

- `today`: USD per service on the current Tokyo day (`tokyo_day`).
- `today_total_capped`: what `SUB01_CAP_TOTAL_USD` counts (everything except RunPod).
- `caps` and `capped_now`: the caps in force, and which ones are reached now. Each part's flag is its own cap only;
  `total` reached stops every part.
- `days`: the last 7 Tokyo days, newest first, per service plus `total`; `last_7_days_total`.

The eye's and the diary's costs are estimates from Replicate's list prices: $0.003 per FLUX schnell image, and
$0.05/$0.25 per million tokens for Llama 3 8B, with token counts from Replicate's metrics. Replicate's billing page is the
final word. Rows for the eyes and the mind carry OpenRouter's reported cost when there is one.

## Health
- **`GET /healthz`**: public (it bypasses the password gate), with no data in it. It answers `200 ok` if the brain loop
  finished a tick in the last 5 s, else `503 stalled`. It also answers 503 before the first tick, so a deploy that does
  not start is never "healthy".
- **`GET /api/health`** (same access as `/api/costs`) returns:
  - `tick_ms`: p50/p95/max over the last minute of `run_brain` bodies (wall time, 1200-entry ring buffer);
  - `loop_lag_ms`: how late ticks started against their 50 ms slot;
  - `rss_mb`, `websockets`, `chromium` (on, child alive, restarts, consecutive failures);
  - `eye.resting`, `last_diary`, `last_memory_test`, `spend_today`.

### Railway healthcheck
Service → **Settings → Deploy → Healthcheck Path**: `/healthz`. You can do the same in config-as-code (`railway.toml`
→ `[deploy] healthcheckPath = "/healthz"`); this repo does not add that file, so the setting stays in the dashboard.

- Railway calls the path from `healthcheck.railway.app` (nothing in the server filters hosts) on `$PORT`. It waits up to
  `RAILWAY_HEALTHCHECK_TIMEOUT_SEC` (default 300 s; the server ticks within a few seconds of starting).
- A deploy that never answers 200 (an import error as in #49, a crash at start, a stalled loop) is marked **Failed**
  instead of becoming the active deployment.
- **Caveat (Railway docs):** a service with a volume (ours: `/data`) cannot run two deployments at once. Railway stops
  the old one before it starts the new one, so a redeploy has a short gap even with the healthcheck. A failed deploy is
  therefore visible and alerted, but the old deployment is not kept serving. To recover, open the last good deployment
  in Deployments and choose **Redeploy** (or revert the commit on `main`).
- Railway uses the healthcheck only at deploy time, not afterwards. That is what the uptime monitor is for.

### Free uptime monitor
**UptimeRobot** (free: 50 monitors, 5-minute checks, email + app push):
1. Sign up at uptimerobot.com, then **New monitor** → type **HTTP(s)**.
2. URL: `https://sub01-production.up.railway.app/healthz`, interval 5 minutes.
3. Optional: type **Keyword**, keyword `ok`, alert when the keyword is "not exists" (catches a proxy error page that
   returns 200).
4. Alert contacts: your email, and the UptimeRobot mobile app for push notifications.

**Better Stack** (free tier, 3-minute checks) works the same way: Uptime → Create monitor → "URL becomes unavailable"
→ the `/healthz` URL → email / push.

A 503 means the brain loop stalled or the process is restarting. Look at the Railway logs and at `/api/health`
(`last_tick_s_ago`, `tick_ms`).

## Railway usage alerts
Workspace → **Usage** → **Usage limits**:
- set a **custom email alert** at an amount below what you are willing to spend in a month;
- optionally set a **hard limit**. Railway stops the services when it is reached, so set it above the alert.

The Railway credit runs out separately from these caps. The services stop when it does; check the Usage page.
