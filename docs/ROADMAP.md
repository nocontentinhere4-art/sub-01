# SUB-01 — roadmap (coordinator)

Last pass: **2026-10-02 05:40 UTC** (pass 18). Updated after every coordinator pass. Read with `docs/HANDOFF.md`.

## Waiting for the owner
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
- **`SUB01_CHOICE=1` on Railway** (optional): adds the choice training to the nightly GPU hour (~90 s, no extra cost).
- **GPU budget beyond 1 h/day:** not decided. Caps stay as they are until the owner names a daily amount.
- **Email account for him** (18d), **reply to Russ**, **Railway paid plan**: owner only.
- **Railway credit: "24 days or $4.17 left"** (owner's screenshot, 2026-10-02). The service stops when it runs out.

Who is on what (cloud sessions, 2026-10-02):
| work | session | state |
|---|---|---|
| #29 free browsing | `session_01MuUA9dxNCVBWAw6ez7R9Ju` | merged as #40 (its 2 novelty hooks ride with #33 phase B) |
| #31 teach him | `session_017R5d56EEZVdrsHDbvQuww9` | merged as #41; room card waits for the room PR |
| #33 mind layer | `session_01KwLm3oYfsh8KhXjWTbrUPt` | phase A merged as #37; phase B started 05:35 (`feature/mind-live`) |
| #35 spiking brain learns to choose | `session_01M78bGx6tpR1jKqBUG5wCPQ` | merged as #39 |
| #36 tastes learn faster | `session_013dKUqHWjLfTXWhGQLBVqcc` | merged as #38 |
| room follow-ups (bed clip, chair, one-line disclaimer) | `session_01Xrq53UQH9EHy4bgPj9B2yL` | asked for a new branch from `main` |
| `fix/eyes-docstring` | `session_01881q1gcHZBtokE8qi8QjxC` | asked to open the PR |

Next on `live_server.py`, one at a time: **#33 phase B** (in progress) → #19 → #18 → #17 → #15. `web/room.html`: room follow-ups → #31 room card → any #33 room change.

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
| 15 | Cost ledger, daily caps, `/healthz`, monitoring | todo, after #9 + brain-decides + #14 | issue #15 |
| 16 | YouTube (muted) + chess, chosen by the brain vote | todo, after brain-decides | issue #17 |
| 17 | Chromium as non-root (sandbox on) | todo, after brain-decides | issue #18 |
| 18 | Brain loop 3× cheaper | todo, after #20 | issue #19 |
| 18c | Free browsing (on-site search, forums, news, video, comments; guard kept for public screens) | done | #40 |
| 18e | Daily memory test on the GPU switched on | key added 2026-10-02; needs `SUB01_POD_SECRET` too | #9 |
| 18f | "Teach him something" (viewer word → studied, dreamt, tested next day) | done on /brain (#41); room card next | issue #31 |
| 18i | Faster learning of tastes (adaptive rate, overnight replay of surprising pages) | done | #38 |
| 18j | Spiking brain learns to choose (dopamine reward vs frozen and random controls) | done; nightly run needs `SUB01_CHOICE=1` on Railway (~90 s inside the 1 h) | #39 |
| 18k | Room movement (walk around furniture, sit, lie down) | done; follow-ups in a new PR | #28 |
| 18g | /tastes page (what he leans towards, over days) | done | #32 |
| 18h | Mind layer: reads and remembers meaning, plans his day (brain votes), answers chat from his computer; $2/day shared AI cap | phase A done (#37); phase B in progress | issue #33 |
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

## Known risks
- **CPU:** the brain loop alone uses ~63 % of one core (~31 ms per 50 ms tick, `main`, `--demo`, no Chromium).
  Chromium shares the CPU, so ticks can run late. Fix: #19.
- **Bandwidth at launch:** after #34, 7.3 KB/s per brain-page viewer and 4.0 KB/s per room viewer. 300 steady viewers ≈
  1.6 MB/s ≈ 140 GB/day of Railway egress: watch the bill after launch. The per-IP cap (4) trusts the first
  `X-Forwarded-For` entry, which a client can forge; the global cap (400) still holds.
- **Unbounded spend:** the eye (Replicate) has no daily cap and no log. With viewers always present it renders up to
  ~960 frames/day. Fix: #15. #20 needs a daily USD cap (Opus 5.5 via OpenRouter is ≈ $0.50/hour at the 30-call cap).
- **State files:** `life.json`, `body.json`, `reading.json` and `browsing.json` are written non-atomically, so a kill mid-write
  crash-loops the server at the next start. Fix: #21.
- **Vote load:** on one core with a vote every 5 s, brain ticks are up to 157 ms late (p95 69 ms). Fine at one vote
  per page; #19 adds headroom.
- **Chromium runs as root with `--no-sandbox`** on the open web. Fix: #18. Since #40 it browses more freely (median
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
| Brain-decides eyes (#20; Haiku 4.5 via OpenRouter, key already on Railway) | $0 (not merged) | ≤ $1.00/day hard cap (≈ $0.004 per page) |

## Launch checklist (owner)
- [ ] All milestones 7–15 merged; CI green; `/healthz` monitored (uptime alert to your phone/email).
- [ ] Costs per day measured for 3 days with the password on, all caps set, Railway usage alert set.
- [ ] Load test (#14) passed at 300 viewers.
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
