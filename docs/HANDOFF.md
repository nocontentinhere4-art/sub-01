# SUB-01 — handoff for new sessions (state on 2026-10-01)

Read this first. It replaces the local memory that cloud sessions cannot see.

## What SUB-01 is now
- A whole-brain model built from one real person's public MRI (MyConnectome, OpenNeuro ds000031, PDDL):
  real tractography fibres, real cortex, his real resting-state recordings.
- It "lives" as a **fictional young man in a Tokyo room** (Kichijoji). The character is invented and must never
  resemble, name or speak as the real scanned person. Never claim consciousness or that it is alive.
- **Data attribution (agreed with the dataset's researcher, 2026-10-02):** credit the data to the **MyConnectome
  project** (Poldrack et al. 2015, Nat Commun 6:8885; OpenNeuro ds000031) on `/about.html` and in the README. Do
  not state or highlight whose brain it is anywhere (site, diary, X posts, coin material); never use the person or
  the project's name to promote the site or the coin.
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
- `brain_sim.py` (10 Hz delayed Stuart-Landau; `step` reads the delayed coupling with one sparse product per step on
  the ring buffer, `ring_coupling()`, #19: ~4 ms CPU per 50 ms tick instead of ~30, same as the old dense step to ~1e-15
  over 10 s (`tests/test_brain_step.py` asserts 1e-9); `analysis/bench_step.py` times both), `real_baseline.py` (replays his fMRI as drive), `sleep.py` (Asia/Tokyo),
  `chat.py` (filter), `eye.py` (Replicate), `diary.py`, `life.py` (needs-based life: research at the computer,
  order_food → simulated courier on a real OSM bike route, get_delivery, bakery/park outings with real routes),
  `research.py` (Wikipedia curiosity chain, sensitive topics skipped; its article seeds what he searches),
  `browse.py` (`BROWSE=1`, on in the Dockerfile: headless Chromium on the open web for the desk + phone screens;
  Bing SafeSearch strict with a Wikipedia → external-sources fallback; the only typing is a filtered query into a
  site's own search box (#29, checked in the browser process), never logs in/signs up/buys; guard skips
  adult, gore, self-harm, extremism, drugs, gambling, crypto-trading/wallet and login/sign-up/checkout sites/pages;
  every request to private/internal addresses is blocked; Chromium gets no secrets in its env), `live_server.py` (aiohttp; pages served
  with `Cache-Control: no-cache`; `/api/diary`, `/api/reading`, `/api/frames`, `/api/browsing`, `/api/screen/{desk,phone}.jpg`).
- State files under `--data-dir` go through `state_io.py` (#21): `save_json` (tmp + fsync + `os.replace`) and
  `load_json` (a missing or torn file gives defaults; a torn one is kept as `<name>.corrupt-<UTC time>` with one log line),
  so a kill mid-write cannot crash-loop the server. JSONL logs append with `append_jsonl` and are read skipping torn lines.
  New JSON state must use these too.
- `Dockerfile` must copy every runtime module (currently also `diary.py research.py browse.py`) and installs Chromium
  (`playwright install --with-deps --only-shell chromium`, image ~1.7 GB). BLAS is single-threaded (`OPENBLAS_NUM_THREADS=1`):
  multi-threaded BLAS spins when Chromium shares the CPU.
- Live feed: plain `/ws` = 20 ticks/s with per-region activity (brain page); the room connects with `/ws?rate=5&lite=1`
  (5/s, no `act`, trades/events of skipped ticks kept). Room: shadow maps updated by hand (~30/s), DPR capped at 1.5
  with adaptive resolution, nothing rendered while the tab is hidden; brain `?mini` draws 1/6 of the fibres at ≤30 fps.
- Room model: `web/room/room_clean.glb` (3.9 MB) is a clean rebuild — modelled in Blender by `room_build/build_room.py`
  (headless Blender 4.2), Poly Haven CC0 props/textures, AO baked into a second UV set; credits in `web/room/CREDITS.md`.
  Monitor/window/lamp positions come from GLB nodes `SURF_monitor|window|lamp`. The old AI-baked room stays behind `?room=old`.
- Phone grip: while he uses the phone his `RightHand` bone is collapsed into the sleeve and `web/room/hand_phone.glb`
  (a hand gripping a phone, Higgsfield GPT Image + Tripo H3.1, 129 KB) is attached at the wrist; the live screen sits on its glass.
- Phone pose: one-handed grip; right arm/neck/head from `web/room/boy_text.glb` (Meshy `Texting_Walk_inplace` #676,
  re-rigged on the same skeleton via Higgsfield, 8 credits) blended into frozen sit/idle poses (`phone_sit`, `phone_stand`).
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

## Teach him something (#31, PR `feature/teach-him`)
- A viewer sends `{"type":"teach","text","nick"}` on `/ws`: a word or a phrase of at most 6 words plus an optional
  nickname (max 16 characters). Both go through `chat.blocked` (no links, addresses, tickers, personal data, money
  requests, slurs). Limits are in `chat.TeachLimits`: one teach per viewer per Tokyo day, keyed by the chat limiter's
  key and kept in memory only, and at most 30 a day in total, counted from memory and from `teach.json`
  (state_io; day + count only, never viewer keys), so a restart cannot reopen the cap; a teach also saves `state.json`. A phrase already taught that day
  is refused.
- The taught item becomes a stimulus (the chat rules) and a `sleep.Memory` item with `source="taught"`. It keeps
  `nick` for display only (never a stimulus) and `replays`, which `sleep_tick` counts. In REM it weighs 1.5× a
  chat message, and the taught pool is capped at 1.0× everything else, so it gets at most half the replays.
- GPU session: `top_items` adds up to 5 of the day's taught items. Those with 2+ content words come first, because
  a single word cannot be cued with half of itself (`spiking/words.py`); then the most replayed. They are tested the
  next day like the others, and `memory_tests.jsonl` keeps `source: "taught"`.
- `GET /api/taught`: today's and yesterday's items with nick and replay count. With the pod manager enabled it adds
  `testable` and `result` (recalled, score, best lure, days_since) and the note "Recall by a simulated spiking
  network from a partial cue; a model, not a mind.". Without it, only replay counts, with no recall claim.
  Teach card on `/brain`.

## Free browsing (#29, PR `feature/free-browsing`)
- New actions: `site_search` (types only into a search input — `browse.search_field_ok` refuses password, email,
  comment, message, login, payment fields, textareas, editable divs, POST forms and forms with a password field; the
  field is re-checked just before typing; Enter only; every typed text is in the service's `/state` → `typed`),
  `next_page`, `open_comments`, `play_video` (muted; YouTube details stay in #17). Eyes list up to 6 options; a
  `leave` option is always offered; the brain vote stays the only decider.
- Chains of up to 30 pages (`browse.MAX_CHAIN`); leaving is boredom-, chain- and taste-driven in `brain_vote.py`
  (`LEAVE_BORED`, `LEAVE_CHAIN`, the leave option's taste is the opposite of the current page's).
- Cookie / consent banners: the reject or "necessary only" button (`browse.choose_dismiss`), never accept; modals
  closed; sign-in walls left (never signed in). ~58 seeds across forums (read-only), news, museums, maps, recipes,
  music, science and video pages; Wikipedia's external sources and pagination / comment links keep a place among the
  40 links. Costs unchanged: 1 eyes call per page, 30/hour, $1.00/Tokyo day.

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
