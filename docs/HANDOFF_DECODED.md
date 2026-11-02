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
2. Nav on every page: live · brain · room · diary · sees (then about / map where a page had them). The city link was
   removed (decision 7).
3. Design system: `web/ui.css` (tokens + header chrome + chips + big numbers). Pages load it before their own CSS.
4. Voice: bold declarative headlines, honest mono sub-lines; his chat replies keep the casual voice from `mind.py`
   (commit 7069cd1) and are shown tagged "his reply" (the "AI-written" tag was removed on 2026-11-02, see decision 14).
5. Readouts are MODEL readouts, formulas in the spec; labelled "not measured from anyone" wherever shown.
6. The q=1 WebSocket feed now carries `groups`, `aud` and `life.{activity,place,phone,screen}` (screen filtered to
   `BRAIN_SCREEN`), see `Feed.brain_view` in live_server.py and the sample tick in the spec.
7. **City removed** (owner, 2026-11-02: abandon the city and everything built around it). Done: the `city` nav link is gone from every
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
   (not changed; see the open items). Decision 10 later cut the hero to three lines.
9. **Rust** (owner's question, 2026-11-02). Answered as an assessment only; nothing was started. The code is about 25k
   lines of Python; the hot loop `brain_sim.step` takes ~4 ms per 50 ms tick, so a full rewrite is not justified. If
   performance ever matters, port `brain_sim.step` as a compiled extension.
10. **Front page: half the words** (owner, 2026-11-02 afternoon: "too much information, keep it simple, clean buttons, everything understandable instantly"). innerText at 1440×900 went from 1728 to 839 characters. One caption per panel, no explanatory paragraphs, a segmented 1m / 5m / 15m control (`#wins`), one primary button (send), a one-line footer, and the viewport strip only when there is a title or music. Chat lines read "nick text · hh:mm" (the networks sit in the line's `title` attribute). The stimulus form's ack reads "sent" or "not sent: reason" (the old "propagating along the model's fibre tracts" line is gone). The hero rotates three lines, not five, every 8 s: "A brain model, live." / "Send it a message." / "A model, not a mind." ("Stimuli in. Readouts out." is replaced).
11. **Intro deck** (owner: "the first thing when you open the website" is a title slide like the reference, plus a small tutorial). `#intro` is five slides, shown on the first visit per browser session (`sessionStorage` key `sub01.intro`), counter 01 / 05, a two-line lock-up. Slides: "A brain / decoded" (`web/hero_brain.webp`); "Real wiring."; "Simulated activity." (`web/intro_brain_top.webp`, a muted blue top view made from `out/sub01_fibres_top.png`); "Four readouts."; "Send a stimulus." with the primary button. Keyboard, dots and click navigate, Esc skips, and the header link "intro" replays it.
12. **The 3D room in the viewport** (owner: "add there the 3D room"). The "his screen" viewport shows the room whenever his screen is off. `web/room.html` has a chromeless `?embed` mode: scene only, a fading mono caption of what he does (`#ecap`), a slow camera drift (±4° round him over 40 s, a ±3 % dolly over 12 s, a ±0.7° tilt), exposure breathing ±3.5 % over 16 s, 30 fps, DPR 1, cursor hidden after 2 s. Contract: parent → iframe `postMessage {type:"sub01-embed", visible:boolean}`, where `visible:false` stops its render loop; iframe → parent `{type:"sub01-embed-ready"}` when he is first drawn. `live.html` creates the iframe once, shows or hides it by opacity, and posts `visible:false` when he is at a screen, when the tab is hidden, when the viewport is off screen, or while the intro deck is open. The away card stays as the loading placeholder ("camera on him · loading").
13. **Motion** (owner: "make everything beautiful and hypnotic"). A radial bloom under each brain breathes with the model's synchrony (CSS variables `--bl` and `--bs`, set at most 10 times a second). The attention trace has a glow and the playhead has a 0.5 Hz halo. A big number that moves 5 points or more flashes (at most once per 2 s). The grid fades in over 600 ms after the deck closes, the hero image's opacity breathes ±8 % with the same sync, and panel borders lift on hover. All of it is off under `prefers-reduced-motion`. Measured cost: 0 fps under software GL (20.5 → 20.9). The room iframe is a separate, open cost (see the open items).
14. **No AI wording on any page** (owner, 2026-11-02: "remove everything that says AI, AI written"). The tags read "his reply", "his notes" and "why". The diary and world pages say images are "rendered from the brain model's state". The room's page-reader lines say "the page is read for him". `about.html` keeps one factual sentence: a language model writes the notes, plans and replies. **This supersedes the hard rule "AI-written text is labelled" in `docs/HANDOFF.md`** (owner decision, 2026-11-02). The mechanism is still stated on `about.html`.
15. **Writing pass** (owner, 2026-11-02). No fragment-for-punch headlines ("Stimuli in. Readouts out." became "Send it a message.") and no "day and night". Two writing plugins were enabled on the owner's account but could not be loaded in that session, so the pass was done by hand.

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
| Front page half the words, three-line hero, chat line format (decision 10) | owner (decision) | **done, committed** (6c90d1a, 0237ec7) |
| Intro deck on the first visit per session (decision 11) | owner (decision) | **done, committed** (dc00bd0) |
| 3D room in the viewport: `?embed` and the postMessage contract (decision 12) | owner (decision) | **done, committed** (95b2450, 20f1c92); run in headless Chromium only; cost open |
| Motion polish: blooms, glow, halo, flashes, grid fade-in (decision 13) | owner (decision) | **done, committed** (20f1c92); no measurable cost under software GL |
| No AI wording on any page (decision 14) | owner (decision) | **done, committed** (8b29e26, 112a96c, 20f1c92); `docs/HANDOFF.md` still states the old rule |
| Writing pass by hand (decision 15) | owner (decision) | **done** (the plugins could not load in that session) |
| Docs: this file, `SPEC.md`, `decoded/README.md`, `OPERATIONS.md`, `HANDOFF.md` | docs agent | **done** |

## Open items (what remains)
- **Real GPU check.** Fps and brain colours were measured only under software GL (rAF 12.8 → 20.6 fps at 1440 px; 91–100 %
  of lit brain pixels blue-dominant at 1440 and 390 px). Check on a device: the caps are 30 fps on desktop, 15 on phones.
- **Room embed, screenshot viewport and dopamine markers, on a live server.** The demo runs with `BROWSE=0` (no
  `life.screen`) and has no dopamine events, so none of them is checked on a live server yet. The room embed (decision 12) has been run in headless Chromium only.
- **Room iframe cost.** Under software GL the room iframe shares the main thread and drops the dashboard's rAF from 20.9 to 1.4 fps while it renders. On a real GPU it is capped at 30 fps and the cost is expected to be small, but that is NOT measured. Measure on the owner's Mac and on a phone. If it costs too much, pause the room while the brains draw, or lower its resolution in embed mode.
- **Headless room T-pose.** The room shows a T-pose in headless runs. That is the software GL animation state, not a page bug.
- **Owner decision: `about.html`'s section "The coin".** Left in place with the MINT code; reduced to one contract-address line in 3430e25. Remove or keep.
- **Owner decision: the chat-reply voice.** His replies keep the casual voice from `mind.py`. Should they take the
  scientific register too?
- **Docs:** `docs/HANDOFF.md` still states the hard rule "AI-written text is labelled", which decision 14 supersedes. Update it in the next docs pass.
- **Server label:** `live_server.py` still sends `mind_read.tag` as "notes written by an AI" (and `tests/test_mind_live.py` checks it). The page does not show that string (it shows "his notes"). Change it with the next server edit, and then the SPEC line for `mind_read`.
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
- The hero rotates three lines every 8 s (`HERO` in `web/live.html`); its counter reads 01 / 03.
- Under reduced motion the hero rotation is off (the counter stays 01 / 03).
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
   1440×900, 1280×800, 1024×768 and 390×844, a chat event, reduced motion the asleep state (`--time-scale 60 --start 23:50`), and the intro deck (its key is `sub01.intro` in sessionStorage; clear it to see the deck again).
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
No text is labelled as AI-written (superseded 2026-11-02, decision 14). Keep the password gate. No new third-party scripts/fonts beyond the CDNs already used.

## About "mods"
The owner installed Claude Code mods (github.com/nateherkai/claude-code-mods: Cache Keeper, Collision Guard, Goal
Meter, Recording Mode) on their own machine. They act on the owner's local terminal/desktop sessions only; a cloud
session cannot load them and nothing in this repo depends on them.
