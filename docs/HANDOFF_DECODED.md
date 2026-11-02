# SUB-01 — handoff: the "decoded" redesign (state on 2026-11-02)

Read this first in a new session, then `docs/design/decoded/SPEC.md` (the shared spec every agent built from), then
`docs/HANDOFF.md` (the project's standing handoff: pages, modules, hard rules). Branch: `claude/compassionate-fermat-piv6wx`
in `nocontentinhere4-art/sub-01` (the live site repo; `sub-01-brain` is an older snapshot, `sub01-brain` the standalone
brain package — leave both alone).

## The owner's request (verbatim intent)
"Let's get back to where it all began. Update this old version and make it all brand new, starting with animations,
the new voice, all the features that first we wanted to create. First the UI of the website, second put the brain in
first place on the UI, with the examples I sent (a 'Humans Decoded / cognitive API' dashboard: a video viewport with a
LIVE badge, a multi-trace timeline of Attention · Arousal · Cognitive load · Neural activity with diamond event
markers, two top-down brain heat-map panels with a big score and 'RESPONSE AT 3:55' captions, a feed column, a
'SYNTHETICALLY GENERATED' tag; black ground, bold white Helvetica, small uppercase mono captions, red = live,
teal = projected)." The owner then asked for the work to be run as an autonomous multi-agent effort with a
coordinator that plans, allocates agents by size (the smallest for mechanical work, the largest for the page build) to
save tokens, and checks the work.

## Decisions taken (do not re-litigate)
1. `/` → `web/live.html` (the brain-first dashboard, NEW). `/room` → `web/room.html` (was `/`). `/brain` → `web/index.html`
   (the deep 3D brain, unchanged). Old links redirect (`OLD_PATHS` in live_server.py).
2. Nav on every page: live · brain · room · diary · sees (then about / map where a page had them). The city link is
   gone (decision 7).
3. Design system: `web/ui.css` (tokens + header chrome + chips + big numbers). Pages load it before their own CSS.
4. Voice: bold declarative headlines, honest mono sub-lines; his chat replies keep the casual voice from `mind.py`
   (commit 7069cd1) and are shown tagged "his reply · AI-written".
5. Readouts are MODEL readouts, formulas in the spec; labelled "not measured from anyone" wherever shown.
6. The q=1 WebSocket feed now carries `groups`, `aud` and `life.{activity,place,phone,screen}` (screen filtered to
   `BRAIN_SCREEN`), see `Feed.brain_view` in live_server.py and the sample tick in the spec.
7. **Abandon the city and everything built around it** (owner, 2026-11-02). Done: the `city` nav link is gone from every
   page; the room lost the city card (`#citypip`), its pulse (`/api/city`) and popout, and the coin-address chip (`#ca`);
   the server lost `/api/city`, `CITY_URL`, the `/city` redirect, `DEFAULT_CA`, `coin_address()` and the `ca` field of the
   hello message and of `/api/config`; `web/room/city_preview.jpg` was deleted; `tests/test_coin_address.py` was replaced
   by `tests/test_old_paths.py`. Left in place on purpose: the dormant MINT trade-stimulus code (MINT unset: no feed) and
   the section "The coin" in `about.html` (a decision for the owner, see the open items).
8. **Scientific approach** (owner, 2026-11-02). On the front page the five hero lines now describe the method, the data
   and the readout formulas ("A brain model, decoded live." / "214 regions. Real tractography. One coupled model." /
   "Stimuli in. Readouts out." / "A sleep circuit, modelled." / "A model, not a mind."); feed captions say what the model
   did ("planned by the model", "the model's reason for the page"); the chat ack says a message is "propagating along the
   model's fibre tracts". The fictional-character framing stays (hard rule). His chat replies keep the casual voice
   (not changed; see the open items).
9. **Rust** (owner's question, 2026-11-02). Answered as an assessment only; nothing was started. The code is about 25k
   lines of Python; the hot loop `brain_sim.step` takes ~4 ms per 50 ms tick, so a full rewrite is not justified. If
   performance ever matters, port `brain_sim.step` as a compiled extension.

## State of the work
| piece | owner | state |
|---|---|---|
| Research, plan, spec, `web/ui.css`, routes, redirects, feed fields, smoke paths, README/HANDOFF tables, `tests/test_feed.py`, `clips.py` → `/room` | coordinator + server agent | **done, committed** (baad99b and the commits after it) |
| New nav + header on `web/index.html, room.html, diary.html, world.html, tastes.html, about.html, life.html, fibres.html` | markup agent | **done, committed**: ui.css linked first on all 8 pages, nav + `on` class right everywhere; on phones the nav has its own scrollable row on `/life.html` and `/fibres.html` (`/brain` needed nothing) |
| `web/live.html` (the dashboard) + `docs/design/decoded/README.md` | page agent | **built, committed** (2313055, then the front-page commits 1f2a327 and 1a6e1c3) |
| Animation + voice polish pass on `web/live.html` | page agent | **done, committed** (1f2a327, 1a6e1c3): fold layout, hero image, brain colour rule, RESPONSE waiting state, fps caps, chat order across midnight, scientific register; verified with screenshots at 1440×900, 1280×800, 1024×768 and 390×844, after a chat event, under reduced motion and in the asleep state (`--time-scale 60 --start 23:50`), 0 JS errors |
| Full review: `tools/review_shots.py` on all routes, desktop + phone | coordinator | **done**: 0 JS errors, no horizontal scroll (the /room phone shot needs a longer screenshot timeout than the script's 30 s; the page itself is fine) |
| `python3 -m pytest -q tests/` | coordinator | **done**: 1863 passed, 43 skipped, 5 failed; all 5 already fail on main (`tests/test_boy_mh.py` node stub; `decider` missing on the test stubs in `test_reading.py` and `test_tastes_faster.py`; `test_spiking_live.py` GPU label; `test_spiking_ops.py` flaky connection) |
| City removal (decision 7) | page agent + server agent | **done, committed** (e2d7d3a, c5a243a) |
| Docs: this file, `SPEC.md`, `decoded/README.md`, `OPERATIONS.md`, `HANDOFF.md` | docs agent | **done** |

## Open items (what remains)
- **Real GPU check.** Fps and brain colours were measured only under software GL (rAF 12.8 → 20.6 fps at 1440 px; 91–100 %
  of lit brain pixels blue-dominant at 1440 and 390 px). Check on a device: the caps are 30 fps on desktop, 15 on phones.
- **Embed and screenshot viewport, and dopamine markers, on a live server.** The demo runs with `BROWSE=0` (no
  `life.screen`) and has no dopamine events, so neither is checked in a browser yet.
- **Owner decision: `about.html`'s section "The coin".** Left in place with the MINT code; remove or keep.
- **Owner decision: the chat-reply voice.** His replies keep the casual voice from `mind.py`. Should they take the
  scientific register too?
- **Rust:** answered (decision 9). Nothing to do unless performance becomes a problem.

## Facts the page agent learned (keep)
- brain.json's mesh is in the nodes' `p` space, not `q` (`q` belongs to cortex.bin, used by /brain): map vertices to regions with `p`.
- The q=1 tick's `groups` has 13 keys (the spec's 11 plus `insula` and `language`).
- Plan / notes arrive only on change, so the page also reads `/api/mind` on load and every 60 s, and `/api/decisions`, `/api/music` on load.
- Python Playwright is NOT installed in the cloud image; Node Playwright is (`NODE_PATH=/opt/node-tools/node_modules node …`), and `tools/review_shots.py` needs `pip install playwright` (do not run `playwright install`; the browser is at /opt/pw-browsers/chromium).
- The demo server needs ~20 s to start and dies with its shell; start it with `setsid` or `nohup`.
- Brain colour: blue at the region's own baseline, lighter blue above it, yellow from rel ≈ 1.35, red by 2.0. A 25 s warm-up blends rel towards 1 after the first tick; display smoothing is 1.5 s; additive alphas scale with the drawn size.
- Burst compressor: when the 92nd percentile of rel is above 1.3, the part above baseline is compressed so only about 8 % of regions turn warm. The 2D fallback uses the same thresholds.
- Frame rate: 30 fps on desktop, 15 on phones. A frozen RESPONSE is redrawn only when its snapshot changes or on resize.
- Before the first event, RESPONSE shows the live brain dimmed, the current Attention in dim grey, the head "RESPONSE · waiting" and the caption "ATTENTION · WAITING". Both brains draw once after the mesh loads, on resize and when they come into view, so a full-page capture is never empty.
- Fold: on desktop `#grid` is 100dvh minus the header and the hero (min 560 px); the viewport fills its row (no 16:9 lock). ≤1100 and ≤720 keep the stacked layouts. The hero image is `web/hero_brain.webp` (the server registers image/webp).
- Chat rows from `hello` are ordered by age on the next tick's clock, `(now − minute + 1440) % 1440`, oldest first (stable); a fallback applies after 3 s.
- Under reduced motion the hero rotation is off (the counter stays 01 / 05).
- WebGL1 refuses to link a program whose shared uniform has different precisions in the two shaders (the brains were blank
  everywhere until the vertex shader got `precision mediump float;`, d8079e1). A canvas that once gave a WebGL context never
  gives a 2D one: the fallback swaps in a fresh canvas.
- Arousal = clamp(50 + 30·log2(NE)) (spec amended 2026-11-02): with NE/2·100 the trace sat at 100 for minutes, because the
  model's noradrenaline runs 1.8–2.6 while he listens to music. Each legend item carries its formula in a `title`.
- The test suite takes about 25 min on a 4-core box; two tests (`test_brain_decides.py::test_vote_is_cheap`,
  `test_neurons3d.py::test_cpu_frames_are_compact_and_honest`) fail under CPU load and pass alone.

## How to continue (the coordinator's loop)
1. `python3 -m pip install -r requirements-server.txt pytest` (on Python 3.13 the `chess` wheel fails to build: download the
   sdist with `pip download --no-deps --no-binary :all: chess==1.11.2`, untar, copy its `chess/` folder into site-packages).
2. `BROWSE=0 python3 live_server.py --demo --port 8799 --data-dir /tmp/demo &` then `python3 tools/review_shots.py http://localhost:8799 out/review`
   and LOOK at the PNGs (desktop and phone, every route). Fix: overlaps, empty panels, unreadable text, horizontal scroll, JS errors.
3. The front page is built and polished (see the state table). For any change to it, repeat step 2 and check the shots at
   1440×900, 1280×800, 1024×768 and 390×844, a chat event, reduced motion and the asleep state (`--time-scale 60 --start 23:50`).
   Then work through the open items above.
4. `python3 -m pytest -q tests/` (spiking tests skip without torch; browser tests without Chromium) and the smoke test.
5. Commit in small, descriptive commits (house style: one line saying what changed and why, no model names), push to the
   branch above. Do not open a PR unless the owner asks. `main` auto-deploys to Railway; this branch does not.
6. Delegation that worked: small agents for mechanical server and doc edits, mid-size agents for multi-file markup edits
   with a Playwright self-check, the largest agent for the page build. Give each agent disjoint files, its own demo port,
   the spec path, and a required self-check; the coordinator reviews diffs and screenshots and owns commits. Agents must never `pkill`
   by pattern (one killed another's demo server); kill by PID only.

## Hard rules (short form; the full list is in docs/HANDOFF.md)
A model, not a mind: never claim feeling, thought, consciousness or life. The character is fiction. Never name or hint
at the scanned person (credit lives on /about.html only). No coin promotion, no trade tape, no secrets in git or logs.
AI-written text is labelled. Keep the password gate. No new third-party scripts/fonts beyond the CDNs already used.

## About "mods"
The owner installed Claude Code mods (github.com/nateherkai/claude-code-mods: Cache Keeper, Collision Guard, Goal
Meter, Recording Mode) on their own machine. They act on the owner's local terminal/desktop sessions only; a cloud
session cannot load them and nothing in this repo depends on them.
