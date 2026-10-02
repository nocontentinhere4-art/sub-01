# SUB-01 — roadmap (coordinator)

Last pass: **2026-10-02 15:20 UTC** (pass 30). Updated after every coordinator pass. Read with `docs/HANDOFF.md`.

## Waiting for the owner
**Pass 25:** merged #53 (#17, server side + /brain): YouTube muted, locked muted and in Restricted Mode, with a
10–600 s watch; chess with python-chess, a depth-2 opponent, and the brain vote picking among 5 scorer moves ("his brain
model picks among 5 candidate moves from a simple move scorer"). 601 tests with torch and Chromium; tick 8.8 ms. The
room desk view is the last open PR.

**Pass 24:** merged #52 (#46, the mind in the room). He sits at the desk to answer chat on the monitor; replies are
tagged "his reply (AI-written)". The day plan shows "voted by his brain model", or "yesterday's, kept while the AI rests"
when the AI is resting, plus the resting line. 531 tests; tick 8.1 ms. #17 continues: server PR first, then the room
desk view (it will also look at the dark rectangle behind the status sub-line).

**Pass 23:** merged #51 (#15): one view of every paid cost per Tokyo day, caps checked before each paid call (eye
$1.00 — the eye's first cap —, diary $0.10, eyes $1.00, mind $1.00, total $3.10), `/healthz` (public), and `/api/costs`
and `/api/health` (password cookie or admin token). Checked live by the coordinator with the gate on. 569 tests; tick
9.3 ms. Worst case at launch ≈ $3.86/day including RunPod. #17 (YouTube + chess) started.

**Pass 22:** merged #50 (#18). The server and Chromium now run as uid 1000; the entrypoint hands the root-owned
/data over once. Rollback: `RUN_AS_ROOT=1`. The coordinator built and ran the real image in Docker: all processes are
uid 1000, a root 0600 file is readable and writable after the start, and `/api/config` returns 200. Under Docker's
default seccomp Chromium's sandbox falls back to `--no-sandbox`, with a loud log line; check Railway's first deploy
logs for `CHROMIUM SANDBOX FAILED`. `tests/test_dockerfile.py` now fails CI if a server import is missing from the
image. #15 (costs, caps, /healthz) is next, ahead of #17: after today's outage, a health check comes first.

**Pass 21b: incident.** #45 (merged ~07:30) made `live_server.py` import `mind`, but the Dockerfile's COPY list
lacked `mind.py`. Any Railway image built from 07:30 to 08:24 stopped at start (`ModuleNotFoundError`), so the live
site was probably down for about an hour. The #18 worker found it with `docker build`. Hotfix #49 (adds `mind.py`) was
verified with the exact image file set and merged at 08:24. A regression test (local imports ⊆ Dockerfile COPY) is
part of #18.

**Pass 21:** merged #48 (#19): the brain loop is **6× cheaper**. Bench 31.7 → 5.0 ms; whole server 34 → 9.0 ms per
50 ms tick (8.5 ms with --mind), about 18 % of a core. Identity test vs the old step < 1e-9, 541 tests, 0 skipped. It
also explains the post-vote slowdown (malloc churn from old temporaries). #18 Chromium non-root started.

**Pass 20b:** merged #47 (#43): the maps are drawn from a static OSM extract (130 KB), with no tile server and ODbL
attribution. /about now states the search-box typing honestly. #46 (the mind in the room) started.

**Pass 20:** merged #45, the mind layer live: page notes, a day plan voted by the brain, chat replies at the
computer tagged "his reply (AI-written)". 531 tests with torch and Chromium, 0 skipped; tick 34.2–34.9 ms. The
coordinator checked the caps on the real `Share` objects: mind $1.00 and eyes $1.00 each block at their cap, the total
is $2.00, and it survives a restart. **AI spend now runs up to $2.00/Tokyo day** (OpenRouter key already on Railway).
#33 closed. Started #19 (brain loop 3× cheaper, plus the tick rise after worker-thread votes). New #46 (the mind in
the room, after #43).

**Pass 19:** merged #44 (#31 room teach card). Both "does not understand" lines are gone from the room (owner
disliked them), with no claim of understanding added; `/about` keeps "a model, not a mind". #31 closed. #43 map
session started.

**Pass 18b:** merged #42 room follow-ups (chair node pulled out and ridden in, bed sit/lie with 0 bed penetration,
one-line disclaimer with the owner's text). Found in its screenshots: OSM blocks the map tiles ("Access blocked – tile
usage policy") → new task #43 (static vector map, no tile server). #31 room card started (also rewords "it does not
understand the text").

**Pass 18:** merged #41 teach him (server side + /brain card; 522 tests with torch and Chromium, 0 skipped; tick
32.6 ms). The room teach card follows in a small PR after the room follow-up PR (still in progress). #33 phase B
(mind wired into the live server, shared $2/day ledger) started on `feature/mind-live`.

**Pass 17:** merged #38 (tastes learn faster: Kalman gain per topic + overnight replay; simulated top 5 found ~2.5×
sooner at noise 0.1; 346 tests, tick 32.5 ms) and #39 (spiking network learns to choose: 1M neurons on GPU reached
criterion in 84 trials, re-learned after reversal in 22, exam 1.00 vs 0.275 with learning removed and 0.26 random;
CPU learning test re-run by the coordinator with torch: 20 passed). RunPod checked read-only: only "BRAIN" (EXITED,
untouched). Then #40 free browsing (#29): site search only into verified search boxes, comments, pagination, muted
video, reject-only consent banners; 472 tests incl. Chromium, tick 33.5 ms. #31 started (server side first; the room
card waits for the room follow-up PR).

**Pass 16 (owner: "finish everything on your own, what's missing with the neurons and the rest, verify and proceed"):**
merged #37 (mind layer phase A, new files only), #27 (MyConnectome attribution), #32 (/tastes page), #28 (room movement: walks around furniture, sits, lies
down) and #34 (launch load). Before merging, the coordinator merged all four onto `main` locally: 291 tests passed
(10 skipped), smoke OK at 32.5 ms per 50 ms tick, and the #34 load test with 300 viewers passed (71 % of one core,
tick late p95 3.3 ms, RSS 173 MB).

Owner actions now:
- **RunPod:** the owner added the RunPod key on Railway (2026-10-02). The pod manager also needs **`SUB01_POD_SECRET`**
  (any long random string). Without it the log says `spiking pod manager disabled: SUB01_POD_SECRET is not set`. With
  both set, the first GPU session runs tonight at 21:00 Tokyo (12:00 UTC): ≤ 1 GPU-hour/day, ≈ $0.27–0.85/day.
- **Turn the 1M network on (after #67):** `SUB01_POD_SECRET`, `SUB01_DAY_LIVE=1`, `SUB01_CHOICE=1` on Railway.
- **`SUB01_CHOICE=1` on Railway** (optional): adds the choice training to the nightly GPU hour (~90 s, no extra cost).
- **After #51, on Railway:** set the healthcheck path to `/healthz`, set a long random `SUB01_ADMIN_TOKEN`, add a free
  uptime monitor (e.g. UptimeRobot) on `/healthz`, and set a usage alert (see docs/OPERATIONS.md).
- **GPU budget beyond 1 h/day:** not decided. Caps stay as they are until the owner names a daily amount.
- **Email account for him** (18d), **reply to Russ**, **Railway paid plan**: owner only.
- **Railway credit: "24 days or $4.17 left"** (owner's screenshot, 2026-10-02). The service stops when it runs out.

Who is on what (cloud sessions, 2026-10-02):
| work | session | state |
|---|---|---|
| #29 free browsing | `session_01MuUA9dxNCVBWAw6ez7R9Ju` | merged as #40 (its 2 novelty hooks ride with #33 phase B) |
| #31 teach him | `session_017R5d56EEZVdrsHDbvQuww9` | done: #41 (server, /brain) + #44 (room) |
| #43 map without OSM tiles | `session_015XP5haU96uvbRUJf3p7Tam` | merged as #47 |
| #46 the mind in the room | `session_01Ek5DZG7cEvc1v7TV8PrEkz` | merged as #52 |
| #33 mind layer | `session_01KwLm3oYfsh8KhXjWTbrUPt` | done: #37 + #45 |
| #19 brain loop 3× cheaper | `session_017zdDm1BDeRmdNJEEusasoA` | merged as #48 (6×) |
| #18 Chromium non-root | `session_01Fbtw3qXpLr5WZAjU7jQiDT` | merged as #50 (found the #49 outage) |
| #15 costs, caps, /healthz | `session_01M9bv9k1WFLctqBLSHXWPwr` | merged as #51 |
| #17 YouTube + chess | `session_01F3jQL1rvBNU5TaF7Sygkqi` | done: #53 + #54 |
| #35 spiking brain learns to choose | `session_01M78bGx6tpR1jKqBUG5wCPQ` | merged as #39 |
| #36 tastes learn faster | `session_013dKUqHWjLfTXWhGQLBVqcc` | merged as #38 |
| room follow-ups (bed clip, chair, one-line disclaimer) | `session_01Xrq53UQH9EHy4bgPj9B2yL` | merged as #42 |
| `fix/eyes-docstring` | `session_01881q1gcHZBtokE8qi8QjxC` | asked to open the PR |

Next on `live_server.py` / Dockerfile: **#17** (in progress). Then only the launch checklist is left. `web/room.html`: #17 room desk view (next).

## Final goal
A public site where a brain model built from one real person's open MRI data lives as a fictional young man in a
Tokyo room. He:
- sleeps and dreams (diary);
- reads and browses the web, and his brain model decides what to click;
- remembers what he read (spiking memory, tested daily);
- has a body and neuromodulators;
- reacts to chat and to the coin's trades.

The site must be honest: published numbers, and no claims of mind or consciousness. It must be stable on Railway and
cheap to run, with the password gate kept until launch day.

## Milestones
| # | milestone | state | owner |
|---|---|---|---|
| 1 | Brain v2 page, real fibres | done | main |
| 2 | Fitted slow layer (connectome v2, held-out FC r ≈ 0.21, nulls) | done | #5 |
| 3 | Room 3D + open-web screens | done | #6 |
| 4 | Dream diary, Wikipedia reading | done | main |
| 5 | Body + neuromodulators | done | #10 |
| 6 | PCI test (below the cut-off in every state; published as is) | done | main `cd5e25b` |
| 7 | Room lag fix, phone grip, sky, rebuilt bedroom | done | #8 |
| 8 | Reading memory (readings → stimuli, REM replay, curiosity) | done | #7 |
| 9 | Sleep circuit (Phillips-Robinson) | done | #11 |
| 10 | Spiking memory on GPU, daily test card | done (idle until the RunPod keys are set on Railway) | #9 |
| 11 | Brain decides what he clicks (Haiku 4.5 eyes, $1/day cap) | done | #20 |
| 12 | CI (tests + demo smoke on every PR) | done | #22 |
| 13 | Honest `/about.html` (numbers, credits, coin disclaimer) | done (follow-up for credits pending; links from the pages come with the room fix) | #23 |
| 14 | Launch load: cheaper feeds, viewer caps, load test | done (300 viewers: 71 % of a core, 4–7 KB/s each) | #34 |
| 15 | Cost ledger, daily caps, `/healthz`, monitoring | done | #51 |
| 16 | YouTube (muted) + chess, chosen by the brain vote | done | #53, #54 |
| 17 | Chromium as non-root (sandbox on) | done (uid 1000; sandbox on where the host allows it) | #50 |
| 18 | Brain loop 3× cheaper | done (6×: 34 → 9 ms per tick) | #48 |
| 18c | Free browsing (on-site search, forums, news, video, comments; guard kept for public screens) | done | #40 |
| 18e | Daily memory test on the GPU switched on | key added 2026-10-02; needs `SUB01_POD_SECRET` too | #9 |
| 18f | "Teach him something" (viewer word → studied, dreamt, tested next day) | done | #41, #44 |
| 18i | Faster learning of tastes (adaptive rate, overnight replay of surprising pages) | done | #38 |
| 18j | Spiking brain learns to choose (dopamine reward vs frozen and random controls) | done; nightly run needs `SUB01_CHOICE=1` on Railway (~90 s inside the 1 h) | #39 |
| 18k | Room movement (walk around furniture, sit, lie down) | done (+ chair and bed follow-ups) | #28, #42 |
| 18l | Map cards without tile.openstreetmap.org (OSM blocks them) | done | #47 |
| 18g | /tastes page (what he leans towards, over days) | done | #32 |
| 18m | 1M spiking network on GPU through his waking hours (caps 17 h, $14/day, 120 h/week) | done; on with `SUB01_DAY_LIVE=1`; learning at 1M → #70 | #67 |
| 18n | 20k spiking network on the server CPU votes and learns live (GPU fallback) | done | #65 |
| 18o | Browse like a young guy (interests, Shorts/TikTok, finance read-only, logged-in view-only feeds) | done | #64, #66, #69 |
| 18p | Active neurons visible inside the 3D brain | in progress | #62 |
| 18q | Music via Spotify's official embed, picked by the brain vote | PR #71 | #68 |
| 18h | Mind layer: reads and remembers meaning, plans his day (brain votes), answers chat from his computer; $2/day shared AI cap | done (#37, #45, #52) | #46 |
| 18d | His own email (owner-created account: read first, then limited replies) | waiting on the owner (account) | — |
| 18b | Atomic state-file writes (a torn JSON file crash-loops the server) | done | #24 |
| 19 | Launch | todo | owner |

## Merge order
One task at a time on `live_server.py`: **#14** launch load (next) → **#19** perf →
**#18** non-root → **#17** YouTube/chess → **#15** ops (last; it reads every cost log).

**#12** CI and **#13** about page touch no shared files and can merge at any time.

Rule: at least 60 minutes between merges to `main`, unless the owner says otherwise. Every branch brings `main` in with
a merge commit. Never force-push.

## Review bots
`graphify-labs[bot]` reviews every PR: a summary, "Worth a look" findings and inline coupling notes. It marks its own
findings "NOT verified", and its reviews are partial on large diffs.
- The coordinator verifies its findings. Authors fix only the ones the coordinator's review lists as required.
- Ignore its "Health regression" coupling counts on test functions.
- Verified real so far:
  - #8: `?rate=` overflow and unbounded per-client buffering → required change on #8;
  - `main`: non-atomic JSON state writes, from #10 → issue #21.
- Checked and not real: #8 HTML injection (all user text is escaped); #10 `Life.hunger` read-only (nothing writes
  it); #11 removed constants (aliases kept, PCI imports work); #20 NumPy group indexes and the fragment login guard;
  #7 thread races (no crash path in CPython).

## Decisions
- **2026-10-01: merge order** as above. #8 goes first because it is smallest and mostly frontend. #7 goes next
  because #9 and brain-decides both contain its commits. #11 goes before #9 because one one-commit PR should absorb
  #7's `sleep.py` changes, rather than three branches absorbing the circuit. #9 goes before brain-decides because it
  is reviewed, validated on a pod and capped, while brain-decides has no PR yet and changes the browser architecture.
- **2026-10-01: sleep circuit without a flag.** PR #11's full port is accepted over a flag with the old engine kept.
  The port loads old state, has a 48 h hypnogram test, and the modulators reach `neurochem`. Two engines would double
  the code that the diary, dreams and memory depend on. Rollback is a revert. Issue #16 is closed.
- **2026-10-01: memory test timing.** Keep one session a day, 21:00–22:00 Tokyo, on 1 pod for ≤ 1 h. The session
  encodes the day's readings, runs compressed sleep and the after-sleep test, and runs the next-day test at the start
  of the following session. "Tested every morning" in the goal means this daily next-day test. A morning slot is
  only a change to `SUB01_SESSIONS`.
- **2026-10-01: #7, #11 and #9 merged at the owner's request**, before their authors pushed the last fixes. The
  coordinator did the merge-only work: conflicts, the torch skip, the sleep wording, the rollback note, and the
  `expected_replays()` fix. #20 and #8 were held: #20 has no spending cap yet, and #8 has an unreviewed room rebuild
  and the `?rate=` bug.
- **2026-10-02: much more freedom on the internet** (the owner wants "no limits"). The coordinator builds everything
  that makes him freer:
  - free browsing (#29): on-site search, forums, news, video, comments, long chains;
  - his own email, on an account the owner creates by hand: read first, then limited, filtered replies signed as an
    AI character;
  - logins only with owner-created accounts on sites that allow bots.

  Not built, because they are harmful in themselves:
  - automatic account creation or CAPTCHA solving (against every provider's terms; the accounts get banned and the
    owner is liable);
  - any money: purchases, wallets, crypto;
  - adult or gore content on the public screens;
  - the character mentioning or promoting the coin, or pretending to be human.
- **2026-10-02: the mind layer** (owner): a language model becomes his inner voice, governed by the brain model (mood, energy, choices). Wording: "an AI reads and remembers for him; his brain model chooses"; never that he understands, feels or is conscious. The shared AI cap is raised to $2.00 per Tokyo day (eyes + mind).
- **2026-10-02: the site is English-only** (owner). Viewers may write in any language and Italian words still reach the brain as stimuli, but nothing shown or generated is in another language.
- **2026-10-02: CI-only and docs-only merges do not count for the 60-minute spacing:** they don't change what runs on Railway.
- **2026-10-02: the room's default is the new clean room** (`room_clean.glb`, #8), and `?room=old` stays for one week.
  I rendered both in headless Chromium. The new room is cleaner, and its provenance is documented as CC0 or made for
  the project (`web/room/CREDITS.md`); the old room is a single AI-generated mesh. A later PR removes the old GLBs.
- **2026-10-01: review-bot findings are advisory.** The coordinator verifies them before they become required changes.
- **2026-10-01: paid-model choice stays with the owner** unless the owner delegates it. Coordinator rule: every paid
  call has a hard daily USD cap and a log line before it can merge.
- **2026-10-01: brain-decides "eyes" use Claude Haiku 4.5 (OpenRouter `anthropic/claude-haiku-4.5`, or `claude-haiku-4-5`
  direct), capped at $1.00 per Tokyo day.** The owner delegated this decision.
  - The task is listing 3–5 safe options from a page; the brain model decides, so Opus quality is not needed.
  - Haiku is ≈ $0.004 per page, about 5× cheaper than Opus 5.5, and reliable at the JSON format; Llama is not.
  - Over the cap, he browses with the page's own links, and the brain still votes.
  - The default is set in code, so nothing needs setting on Railway.
  - Haiku takes no effort or thinking parameters, so the requests are built per model (#20, change 6).

- **2026-10-02: owner delegated finishing ("finish everything on your own, verify and proceed").** The coordinator
  merges verified PRs, including those that touch `live_server.py`, after running tests, smoke and (for load) the load
  test on `main` plus the PR. Unchanged: spending caps (GPU 1 h/day, AI $1–2/day), the password gate, the safety rules,
  never touching the pod "BRAIN".
- **2026-10-02: "accelerate learning" = three separate tracks.** Understanding = the mind layer (#33, LLM, capped).
  Preferences = tastes learn faster (#36). Neurons = the spiking network learns choices from dopamine (#35), reported
  against frozen and random controls whatever the result. No claim of IQ, understanding or consciousness.

- **2026-10-02: music through Spotify's official embed only** (owner asked for Spotify). The server never streams,
  downloads or relays audio. Visitors press play on their own device: a 30 s preview, or the full track if they are
  logged in to Spotify. His brain model picks tracks among candidates (#68). Optional `SPOTIFY_CLIENT_ID/SECRET` (free
  developer app); otherwise a curated list of playlists.
- **2026-10-02: social accounts, both uses** (owner).
  - (a) Official SUB-01 accounts post daily AI-labelled clips (#59): manual, or the official APIs once approved.
  - (b) He browses logged in to his own TikTok/YouTube, view-only (#60, after #56). No likes, follows, comments or
    DMs, and private pages never reach a public screen.
  - The owner creates the accounts; Claude cannot sign up. Terms-of-service ban risk on (b) is accepted; he falls back
    to logged out.
- **2026-10-02: browse like a real young guy, no restrictions** (owner; this supersedes the earlier same-day note).
  - Variety comes from an interest profile, the daily rhythm, boredom and novelty; there are no external topic quotas.
  - YouTube (incl. Shorts) and TikTok, logged out: muted, bounded, sign-in walls left.
  - All crypto and finance pages are read-only allowed, including exchanges, DEX, launchpads and this project's own
    coin.
  - Kept, non-negotiable:
    - the guard's harmful categories (adult, gore, self-harm, extremism, illegal), because the screens are public;
    - no actions with money: no wallet, no buy/sell/swap/connect/sign clicks, no logins, typing only into search boxes;
    - no financial advice in his words, and "nothing here is financial advice" on finance pages, to protect the owner
      legally.
  - Task #56.
- **2026-10-02: the 1M spiking network runs on GPU through his waking hours** (owner's choice: ≈ $4–14/day,
  ≈ $130–400/month). Off in code until `SUB01_DAY_LIVE=1`. Caps: `SUB01_DAY_MAX_HOURS` 17/day, `SUB01_GPU_USD_PER_DAY`
  $14, 120 GPU-h/week, ≤ 6 restarts/day. One pod at a time; never the pod "BRAIN". The fallback is the 20k CPU network
  (#55), then the rate model. Task #58.
- **2026-10-02: #15 goes before #17.** After the outage, a health check and the Railway healthcheck path matter more
  than YouTube and chess.
- **2026-10-02: review checklist gains "new module → Dockerfile COPY".** After the #45 incident, every PR that adds a
  top-level module imported by the server must add it to the Dockerfile. The coordinator checks this by importing
  `live_server` from the exact COPY file set, until #18's test does it in CI.

## Known risks
- ~~Map tiles~~: fixed by #47 (static vector map).
- **YouTube walk footage on /life** showed "error 153" in headless Chromium (a missing Referer?). Check it on the real
  site before launch.
- ~~Dark rectangle top-left in the room~~: not visible on a real GPU (owner's screenshot, 2026-10-02); headless only.
- ~~CPU~~: fixed by #48. The whole server is ~9 ms per 50 ms tick (~18 % of a core), leaving room for Chromium.
- **Bandwidth at launch:** after #34, 7.3 KB/s per brain-page viewer and 4.0 KB/s per room viewer. 300 steady viewers ≈
  1.6 MB/s ≈ 140 GB/day of Railway egress: watch the bill after launch. The per-IP cap (4) trusts the first
  `X-Forwarded-For` entry, which a client can forge; the global cap (400) still holds.
- ~~Unbounded spend~~ (fixed by #51: every paid call is capped and in one view). Was: the eye (Replicate) had no daily cap and no log. With viewers always present it renders up to
  ~960 frames/day. Fix: #15. #20 needs a daily USD cap (Opus 5.5 via OpenRouter is ≈ $0.50/hour at the 30-call cap).
- **State files:** `life.json`, `body.json`, `reading.json` and `browsing.json` are written non-atomically, so a kill mid-write
  crash-loops the server at the next start. Fix: #21.
- **Vote load:** on one core with a vote every 5 s, brain ticks are up to 157 ms late (p95 69 ms). Fine at one vote
  per page; #19 adds headroom.
- **Chromium sandbox:** since #50 Chromium runs as uid 1000. If Railway's seccomp blocks the sandbox, it falls back to
  `--no-sandbox` (still non-root) with a loud log line. Since #40 it browses more freely (median
  ~450 MB, max 622 MB for the Chromium tree): part of the reason for Railway's paid plan.
- **Merge conflicts:** five branches touch `live_server.py`, and four touch `sleep.py`. The strict order above
  limits the re-merges.
- ~~No CI~~: CI runs on every PR since #22.
- ~~Test bug on `main` (Chromium tests stopped the driver twice)~~: fixed with the #7 merge.
- **Honesty:** the PCI and Pong results are negative and must stay visible as such. "Digital twin" wording suggests
  a copy of the person; use "a model built from one person's public MRI data".
- **Stale branches** (`feature/rw-*`, `feature/twin-*`, `feature/real-world`, `assets/cc0`, `test/integration`,
  `claude/youthful-bohr-*`, `claude/affectionate-brown-*`): delete them after launch. The coordinator never deletes
  branches.
- ~~Character movement in the room~~: fixed by #28 (2026-10-02). Bed clip and chair follow-ups are in a new PR.
- **Coordinator pushes to PR branches:** only merge commits that clear conflicts, and only when the owner asks. The
  first was #9's `fe60d9f` (2026-10-01). Authoring sessions must pull before pushing.

## Costs per day (estimates; the ledger in #15 will replace them)
| item | now | at launch |
|---|---|---|
| Railway (1 service, ~0.6–1 vCPU, ~300 MB + Chromium ~0.5–1 GB) | plan price | same, plus egress (see #14) |
| Eye: Replicate FLUX schnell + Llama, only while watched | cents | up to ~960 frames/day with no cap → cap at $1/day (#15) |
| Diary: 18 unattended frames/night | ~$0.05 | same |
| Spiking memory test (RunPod, 1 h/day) | $0 (not on) | $0.27–0.85/day, 8 GPU-h/week cap |
| Eyes + mind (#20, #45; Haiku 4.5 via OpenRouter, one ledger) | ≤ $2.00/day (eyes $1.00 + mind $1.00) | same hard cap |

**Pass 30:** merged #69 (#56 part 2). He now browses like a young guy: interests rotate with the hour, there are
Shorts/TikTok sessions, he looks up things he has seen, and finance is read-only with a "nothing here is financial
advice" line. In the coordinator's day simulation, Wikipedia's share of pages fell from 28 % to 4 %, and topic entropy
rose from 2.96 to 3.48 bits.

Also merged #65 (#55): a 20k-neuron spiking network runs on the server CPU as a numpy-only child process.
- It votes in browsing choices as one small term (0.3 × lean) and learns from the stay's response.
- The 1M GPU network is asked first, through `day_live_decide`; the rate model is the last fallback.
- Every decision goes to `/data/spiking/decisions-*.jsonl`. The card shows the learned curve against a frozen twin and chance.
- Coordinator run: 901 tests passed. Smoke run with no torch: tick 7.9 ms; the child takes 2.9 CPU-s at start, idles
  at 2 % of a core, and sent 26 frames to /ws.

Started #62 (active neurons in the 3D brain), on /brain and /life only. The room's mini brain follows after #63, and
`session.py`/`choice.py` stay with #70. #71 (music) is waiting for a merge of main (Dockerfile COPY conflict).

**Pass 29:** merged #67 (#58), the 1M network live on GPU through his waking hours. It is off until
`SUB01_DAY_LIVE=1`, with caps of 17 h/day, $14/day, 120 h/week and 6 restarts. Measured A4000 secure at $0.25/h ≈
**$4.1/day**. 842 tests with torch and Chromium; RunPod validation cost $0.127; only "BRAIN" is left (EXITED). No learning is
shown yet at 1M (41/50 races decided at the first check), so follow-up **#70** is started (a read-out that scales).
#68 music (official Spotify embed) is started.

**Pass 28b:** merged #66 (#60): logged-in, view-only TikTok and YouTube from the `SUB01_SESSION_*` secrets.
Chromium's env is scrubbed, cookies are domain-scoped, actions and private pages are blocked, and the avatar is
hidden. 789 tests. After deploy, `/api/browsing` → `accounts.tiktok` should read "logged in". #63 now also covers
real food: props, courier bags, dishes, hand-to-mouth eating.

**Pass 28:** merged #64 (#56 part 1): 10 free search sources routed by topic, ≤ 20 requests/host/hour, follow-up
searches, and queries from notes, reading, taught words, tastes and chat. Searches 31 → 52/hour, with no paid calls on
result pages. Parsers are fixture-tested only; check `/api/browsing` after deploy. Next: #56 part 2 (variety, TikTok
and Shorts, finance) and #60 integration, both in browse.py.

**Pass 27c:** the owner's live screenshot (23:05 Tokyo) shows the site up after the #49 fix, with the mind plan,
the teach card and the static map live. It also shows no dark rectangle on a real GPU, so it was a SwiftShader-only
artifact. He stood frozen while ordering food: `phone_stand` is a `still()` pose in the middle of the room. New #63
(natural movement: no frozen poses, living idles, smooth transitions) is started. The owner set `SUB01_SESSION_TIKTOK`;
#60 is started, with new files first and integration after #56.

**Pass 27b:** merged #61 (#57): he eats before chatting. In the coordinator's re-run, minutes above meal time with
chat waiting went 124–211 → **0** (9 runs); deliveries are eaten within 2 min; a 24 h konbini. New tasks:
- #59 daily clips for the official social accounts (started);
- #60 logged-in, view-only TikTok/YouTube (after #56);
- #62 active neurons inside the 3D brain (after #55 and #58).
The owner has created the TikTok account.

**Pass 27 (owner: "turn his neurons on, more things, more internet searching", "is he fed?", "I want the big one"):**
new tasks:
- #55: a small spiking network on the server CPU votes and learns live; it is the fallback for #58;
- #56: many more free search sources, with queries from memory, wishes and taught words;
- #57: he went hungry while chatting (147 min/day above meal time with chat waiting); fix with needs first and a 24 h konbini;
- #58: the 1M network on GPU through his waking hours.

## Launch readiness (2026-10-02, after pass 26)
**All task issues are closed and no PRs are open.** 27 PRs were merged today, #27–#54: attribution, tastes page,
room movement and follow-ups, launch load, mind layer (A, B, room), tastes faster, spiking choice, free browsing,
teach him (server and room), static map, brain loop 6× cheaper, Dockerfile hotfix, non-root, costs/caps/healthz,
YouTube + chess (server and room). Main has 600+ tests (with torch and Chromium), smoke OK, and a tick of ~9 ms per
50 ms. Every paid call is capped (~$3.10/day AI and images + ≤ 1 GPU-h RunPod).

Everything left is for the owner:
1. Railway: healthcheck path `/healthz`, `SUB01_ADMIN_TOKEN`, an uptime monitor, a usage alert, and a paid plan.
2. Railway: `SUB01_POD_SECRET`, unless already set with the RunPod key; optionally `SUB01_CHOICE=1`.
3. After the next deploys, check the logs and the site:
   - the site is up (the #49 outage is fixed);
   - the `CHROMIUM SANDBOX FAILED` line (fine either way, but note it);
   - YouTube plays muted on /brain (it could not be tested end to end in the sandbox);
   - the /life walk video (headless showed YouTube error 153);
   - the dark rectangle top-left in the room (headless SwiftShader only?).
4. Decide the GPU budget beyond 1 h/day if you want faster neuron learning.
5. Email for him (18d), the reply to Russ, the legal check for the coin, the X account.
6. Launch day: remove `SITE_PASSWORD`; watch `/api/health` and `/api/costs` for 24 h.

## Launch checklist (owner)
- [x] All task milestones merged; CI green (2026-10-02). [ ] `/healthz` monitored (uptime alert to your phone/email).
- [ ] Costs per day measured for 3 days with the password on, all caps set, Railway usage alert set.
- [x] Load test (#14) passed at 300 viewers (#34).
- [ ] `/about.html` live and linked from every page; footer disclaimer on every page.
- [ ] Researcher email: tell the dataset's authors (OpenNeuro ds000031) what the site is, before launch. Do not
      name the scanned person anywhere on the site or on X.
- [ ] Legal check for the coin, in your jurisdiction: the site shows trades only as stimuli; no advice, no buy
      pressure, no wallet or on-chain action by the project.
- [ ] X account ready. Posts follow the same wording rules (no consciousness claims, no price talk).
- [ ] Secrets set on Railway only: `SITE_PASSWORD`, `REPLICATE_API_TOKEN`, `RUNPOD_API_KEY`, `SUB01_POD_SECRET`,
      `OPENROUTER_API_KEY` (set), optional `ANTHROPIC_API_KEY`; later `SUB01_ADMIN_TOKEN`.
- [ ] Railway on a paid plan (trial credit showed 24 days / $4.17 left on 2026-10-02).
- [ ] Launch day: remove `SITE_PASSWORD`; watch `/api/health` and spend for the first 24 h.
