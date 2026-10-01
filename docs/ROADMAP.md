# SUB-01 — roadmap (coordinator)

Last pass: **2026-10-01 20:25 UTC** (pass 2). Updated after every coordinator pass. Read with `docs/HANDOFF.md`.

## Waiting for the owner
Nothing is ready to merge yet. #9's conflict with `main` is cleared (coordinator merge commit `fe60d9f`, at the owner's request). #7 and #8 still conflict with `main` (#10), and brain-decides still conflicts too.
When a PR is marked **READY TO MERGE (needs owner)**, it is listed here:

| PR | status | why it needs the owner |
|---|---|---|
| — | — | — |

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
| 7 | Room lag fix, phone grip, sky | in progress: needs main merge | #8 |
| 8 | Reading memory (readings → stimuli, REM replay, curiosity) | in progress: needs main merge | #7 |
| 9 | Sleep circuit (Phillips-Robinson) | in progress: waits for #7 | #11 |
| 10 | Spiking memory on GPU, daily test card | in progress: merges cleanly now; needs torch-free tests, re-merge after #7/#11 | #9 |
| 11 | Brain decides what he clicks | in progress: **no PR opened yet** (review fixes pushed, `a8c928e`) | `feature/brain-decides` |
| 12 | CI (tests + demo smoke on every PR) | todo | issue #12 |
| 13 | Honest `/about.html` (numbers, credits, coin disclaimer) | todo | issue #13 |
| 14 | Launch load: cheaper feeds, viewer caps, load test | todo, after #8 | issue #14 |
| 15 | Cost ledger, daily caps, `/healthz`, monitoring | todo, after #9 + brain-decides + #14 | issue #15 |
| 16 | YouTube (muted) + chess, chosen by the brain vote | todo, after brain-decides | issue #17 |
| 17 | Chromium as non-root (sandbox on) | todo, after brain-decides | issue #18 |
| 18 | Brain loop 3× cheaper | todo, after brain-decides | issue #19 |
| 19 | Launch | todo | owner |

## Merge order
1. **#8** room: frontend + a tested feed filter. The coordinator merges it once it has merged `main`.
2. **#7** reading memory (owner: `sleep.py`).
3. **#11** sleep circuit (owner: `sleep.py`). It merges `main` after #7.
4. **#9** spiking (owner: RunPod spend, Dockerfile). It merges `main` after #7 and #11.
5. **brain-decides** (owner: Dockerfile, API spend, browser process). It opens its PR now and merges `main` after #9.
6. Then **#19** perf, **#18** non-root, **#17** YouTube/chess and **#14 → #15** ops, one at a time on `live_server.py`.

**#12** CI and **#13** about page touch no shared files and can merge at any time.

Rule: at least 60 minutes between merges to `main`. Every branch brings `main` in with a merge commit. Never force-push.

## Pre-review: `feature/brain-decides` (reviewed at `98e6c33`; `a8c928e` since, no PR yet)
Tests 140 passed (1 skipped: no `anthropic` installed). The demo smoke passes, including `/api/decisions` and
`/api/tastes`. Tick cost is the same as `main`. Required before it can be marked ready:
1. Open the PR. Merge `main` now (it conflicts in `live_server.py`), and again after #9 (`Dockerfile`, `live_server.py`).
2. **Add a hard daily USD cap for the eyes** (e.g. `BRAIN_DECIDES_MAX_USD_PER_DAY`, default 1.00) on top of
   30 calls/hour.
   - At the call cap that is 720 calls/day.
   - My estimate is ~4k input + ~0.4k output tokens per call on `claude-opus-5-5` ($4/$20 per MTok), about
     $0.024 per call, so up to ~$17/day.
   - Post measured tokens per call from a sample of real pages.
3. Put prompt caching (`cache_control`) on the fixed system prompt.
4. Pin `anthropic>=1.11,<2`.
5. The vote runs ~260 ms of numpy in an executor thread. Measure brain tick lag p95 while votes run, and post it.
6. The model is the owner's choice (`BRAIN_DECIDES_CLAUDE_MODEL`). Say in the PR which model and what daily cost you
   propose.

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
- **2026-10-01: paid-model choice stays with the owner.** Coordinator rule: every paid call has a hard daily USD
  cap and a log line before it can merge.

## Known risks
- **CPU:** the brain loop alone uses ~63 % of one core (~31 ms per 50 ms tick, `main`, `--demo`, no Chromium).
  Chromium shares the CPU, so ticks can run late. Fix: #19.
- **Bandwidth at launch:** `/ws` is 20 ticks/s × ~3.1 KB, about 62 KB/s per brain-page viewer. 300 viewers would be
  ~19 MB/s of Railway egress. Fix: #14.
- **Unbounded spend:** the eye (Replicate) has no daily cap and no log. With viewers always present it renders up to
  ~960 frames/day. Fix: #15. Brain-decides needs a USD cap (above).
- **Chromium runs as root with `--no-sandbox`** on the open web. Fix: #18.
- **Merge conflicts:** five branches touch `live_server.py`, and four touch `sleep.py`. The strict order above
  limits the re-merges.
- **No CI:** a broken `main` deploys straight to Railway. Fix: #12.
- **Test bug on `main`:** `tests/test_browse.py::test_browser_never_shows_local_pages` fails whenever Chromium is
  available (it stops the driver twice after `3c682df`). Fixed on `feature/brain-decides`.
- **Honesty:** the PCI and Pong results are negative and must stay visible as such. "Digital twin" wording suggests
  a copy of the person; use "a model built from one person's public MRI data".
- **Stale branches** (`feature/rw-*`, `feature/twin-*`, `feature/real-world`, `assets/cc0`, `test/integration`,
  `claude/youthful-bohr-*`, `claude/affectionate-brown-*`): delete them after launch. The coordinator never deletes
  branches.
- **Coordinator pushes to PR branches:** only merge commits that clear conflicts, and only when the owner asks. The
  first was #9's `fe60d9f` (2026-10-01). Authoring sessions must pull before pushing.

## Costs per day (estimates; the ledger in #15 will replace them)
| item | now | at launch |
|---|---|---|
| Railway (1 service, ~0.6–1 vCPU, ~300 MB + Chromium ~0.5–1 GB) | plan price | same, plus egress (see #14) |
| Eye: Replicate FLUX schnell + Llama, only while watched | cents | up to ~960 frames/day with no cap → cap at $1/day (#15) |
| Diary: 18 unattended frames/night | ~$0.05 | same |
| Spiking memory test (RunPod, 1 h/day) | $0 (not on) | $0.27–0.85/day, 8 GPU-h/week cap |
| Brain-decides eyes (Anthropic or Replicate) | $0 (not on) | ≤ cap (proposed $1/day) |

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
      optional `ANTHROPIC_API_KEY`; later `SUB01_ADMIN_TOKEN`.
- [ ] Launch day: remove `SITE_PASSWORD`; watch `/api/health` and spend for the first 24 h.
