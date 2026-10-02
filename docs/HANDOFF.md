# SUB-01 — handoff for new sessions (state on 2026-10-01)

Read this first. It replaces the local memory that cloud sessions cannot see.

## What SUB-01 is now
- A whole-brain model built from one real person's public MRI (MyConnectome, OpenNeuro ds000031, PDDL):
  real tractography fibres, real cortex, his real resting-state recordings.
- It "lives" as a **fictional young man in a Tokyo room** (Kichijoji). The character is invented and must never
  resemble, name or speak as the real scanned person. Never claim consciousness or that it is alive.
- Live on Railway (`sub01-production.up.railway.app`, behind `SITE_PASSWORD`), auto-deploys from `main`.
- Memecoin context: no financial advice, no buy pressure, no wallets or on-chain actions without explicit approval.

## Pages (all on `main`)
| path | file | what |
|---|---|---|
| `/` | `web/room.html` | his room in 3D (three.js r169; Higgsfield/Meshy GLBs in `web/room/`, meshopt + WebP, 3 MB), Tokyo day/night through the window, live screens (monitor + phone in his hands, arm IK), camera follows what he looks at, map when he is out, mini brain. `?debug&nolive&hour=21` previews a time of day |
| `/brain` | `web/index.html` | brain v2: full-screen real fibres coloured by sleep stage; chat messages travel along real fibres; `?mini` for the PiP |
| `/diary` | `web/diary.html` | dream diary written each morning (Tokyo) from unattended REM frames |
| `/world.html` | eye frames | what the eye (Replicate FLUX + Llama 3) "sees" |

## Runtime modules
- `brain_sim.py` (10 Hz delayed Stuart-Landau), `real_baseline.py` (replays his fMRI as drive), `sleep.py` (Asia/Tokyo),
  `chat.py` (filter), `eye.py` (Replicate), `diary.py`, `life.py` (needs-based life: research at the computer,
  order_food → simulated courier on a real OSM bike route, get_delivery, bakery/park outings with real routes),
  `research.py` (Wikipedia curiosity chain, sensitive topics skipped; its article seeds what he searches),
  `browse.py` (`BROWSE=1`, on in the Dockerfile: headless Chromium on the open web for the desk + phone screens;
  Bing SafeSearch strict with a Wikipedia → external-sources fallback; read-only, never types/logs in/buys; guard skips
  adult, gore, self-harm, extremism, drugs, gambling and crypto-trading sites/pages; every request to private/internal
  addresses is blocked; Chromium gets no secrets in its env), `live_server.py` (aiohttp; pages served
  with `Cache-Control: no-cache`; `/api/diary`, `/api/reading`, `/api/frames`, `/api/browsing`, `/api/screen/{desk,phone}.jpg`).
- `Dockerfile` must copy every runtime module (currently also `diary.py research.py browse.py`) and installs Chromium
  (`playwright install --with-deps --only-shell chromium`, image ~1.7 GB). BLAS is single-threaded (`OPENBLAS_NUM_THREADS=1`):
  multi-threaded BLAS spins when Chromium shares the CPU.
- Chromium runs as root in the image, so its own sandbox is off (`--no-sandbox`); running the server as a non-root user
  would turn it back on (needs `/data` volume ownership checked on Railway).

## Reading memory (PR `feature/reading-memory`)
- What he reads is a stimulus: up to 8 keywords (title + extract) through chat.py's rules at 0.5x a chat message,
  + language/attention 1.5, times the sleep gain. Stored in `sleep.Memory` with `source="reading"`; REM replay
  weighs a reading 0.6x and caps the reading pool at 0.6x the chat pool (chat from people wins most nights).
- Curiosity: link titles scored by `chat.TOPICS` lexicon x the tick's relative network activity + novelty
  (7 days) + noise, softmax (`SUB01_CURIOSITY_TEMP`, 0.5); the "why" names only above-average networks.
- Shown: room reading card ("will it come back tonight?" Monte Carlo estimate), diary "read that day · replayed
  that night", eye dream prompts (replayed titles as images only). Wording: it does not understand the text.
- Screens: bot checks (CAPTCHA / "unusual traffic") are recognised and left, never solved or clicked.

## Brain decides what he clicks (PR `feature/brain-decides`)
- Eyes (`eyes.py`): after a page, an AI lists 3-5 options from the title, visible text and up to 40 numbered links
  (decision 2026-10-01: Claude Haiku 4.5 by default, hard cap $1.00 per Tokyo day). Claude `claude-haiku-4-5` if
  `ANTHROPIC_API_KEY` (`BRAIN_DECIDES_CLAUDE_MODEL`); else OpenRouter if `OPENROUTER_API_KEY` (set on Railway),
  `OPENROUTER_MODEL` default `anthropic/claude-haiku-4.5`, real cost per call logged; else Replicate Llama 3 70B.
  Request fields per model: no effort/thinking/fallbacks for Haiku 4.5; effort low for Opus/Sonnet (+ refusal
  fallbacks on the 5.5 family). cache_control on the fixed system prompt (about 344 tokens: below every model's
  cache minimum, so it caches nothing today). Links by number only, every target through the browse.py guard, search
  queries through the chat filter; max 1 call per page, `BRAIN_DECIDES_MAX_CALLS_PER_HOUR` (30) and
  `BRAIN_DECIDES_MAX_USD_PER_DAY` ($1.00, Tokyo day, from `/data/eyes_costs.jsonl`). No key / over a cap: local
  options; `/api/decisions` shows why. A chosen page that is not shown (guard, bot wall) or redirects says so.
- Vote (`brain_vote.py`): `Brain.clone()` + all options simulated 300 ms side by side (one sparse product per step,
  ~260 ms for 5 options + baseline on one core; identical to `Brain.step`); value = d_reward + 0.6 d_attention
  + 0.3 d_visual (videos) - 0.8 d_fear; + tastes + novelty; softmax, hotter when bored or sleepy. The live brain then
  gets the chosen stimulus. `BRAIN_DECIDES_SEED` makes it reproducible.
- Tastes (`tastes.py`, `/data/tastes.json`, `/api/tastes`): reward-prediction-error table over topics, 7-day decay.
  Interface `topics / predict / learn` for the spiking branch to replace with dopamine-modulated synapses.
- Chromium runs in `browse_service.py` (child process, memory watchdog `BROWSE_MEM_MB` 1200, exits if the parent
  dies), or as its own Railway service via `BROWSE_SERVICE_URL` + `BROWSE_SERVICE_TOKEN`. Down = "browser
  restarting" on the page; the brain loop does not stop (`supervised()` tasks). `/api/decisions` lists choices.

## Science status (be honest on the site)
- The old public "r = 0.40" came from replaying his recorded fMRI as drive; with no coupling at all it is 0.45.
  Never present it as "his wiring produces his activity" (`analysis/null_test.py`).
- PR #5 (`feature/real-wiring`): connectome v2 (MRtrix3 + SIFT2) and a wiring-only Hopf slow layer reach FC r ≈ 0.21
  on held-out sessions, beat strength-preserving nulls, borderline vs geometry-preserving nulls. **Merge this.**
- PR #4 (`feature/digital-twin`): weaker fit (0.10), overlaps PR #5; do not merge as is (salvage receptor maps
  under CC BY 4.0, the sleep circuit, the body model later).
- `feature/spiking-brain`: 1M LIF neurons stable on an RTX 4000 Ada / A5000; memory recall works and REM replay
  strengthens cortex; **Pong does not learn** (17.5 % vs 25 % no-plasticity control): off by default (`SUB01_PONG=1`),
  labelled "not learning yet" when shown.
  Daily session (Railway `spiking/pod_manager.py`, default 21:00-22:00 Tokyo, 1 h/day from pod creation, 8 GPU-h per
  rolling 7 days, needs `SUB01_POD_SECRET` + `RUNPOD_API_KEY`): next-day test of yesterday's items → encode today's top
  5 chat + top 5 readings → test → compressed sleep with replay → test. Weights on `/data/spiking/` (pods have no
  volume). Per-item rows `memory_tests.jsonl` → `GET /api/memory` → room card "Does it remember what it read
  yesterday?". GPU check 2026-10-01 (A5000, 1M): 6/6 items recalled from half cues a simulated day later.
- PR #3 (brain-city "construct") is superseded by the room.
- `netneurolab/hansen_receptors` is CC BY-NC-SA → not usable.

## When merging PR #5 into main, keep from main
- `web/index.html` brain v2 (add the slow-layer label to its status line; it reads `m.baseline` — when the
  recording replay is off, show the slow layer and its held-out r next to what randomised wiring reaches).
- `/` → `room.html`, `/diary`, `/api/diary`, `/api/reading`, the `run_research` task, `NOCACHE`, the diary hooks in
  `run_eye`, `SOLANA_WS` + RPC backoff.
- Dockerfile copies `diary.py research.py` plus whatever the slow layer needs (`twin/`, `out/connectome_v2.npz`).

- Sleep engine = the Phillips-Robinson circuit (PR #11, `docs/twin/sleep.md`). Rollback: revert its merge commit; a
  `state.json` saved by the circuit loads and runs in the old rule engine (checked 2026-10-01), so no state reset.

## Hard rules
- No secrets in git or logs; keep the password gate; skull-stripped T1 only (no face).
- RunPod: max 1 pod per task, delete on finish/error/60 min, log costs, never touch the pod named "BRAIN".
- No heavy compute on the user's Mac (it overheats): use cloud sessions or RunPod.
- Higgsfield credits are the user's: preflight with `get_cost` and confirm big spends.
