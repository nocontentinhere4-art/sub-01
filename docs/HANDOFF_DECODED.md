# SUB-01 — handoff: the "decoded" redesign (state on 2026-11-02, evening)

Read this first in a new session, then `docs/design/decoded/SYSTEM.md` (the "one deck" design system v2: the chrome, tokens
and rules every page follows, and the spec for any new page), then `docs/design/decoded/SPEC.md` (the shared data and
readout spec every agent built from), then `docs/HANDOFF.md` (the project's standing handoff: pages, modules, hard rules).
Branch: `claude/compassionate-fermat-piv6wx` in `nocontentinhere4-art/sub-01` (the live site repo; `sub-01-brain` is an
older snapshot, `sub01-brain` the standalone brain package — leave both alone).

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
   removed (decision 7). Superseded by decision 17 (the numbered deck: 01 live · 02 brain · 03 room · 04 diary · 05 sees · 06 about).
3. Design system: `web/ui.css` (tokens + header chrome + chips + big numbers). Pages load it before their own CSS.
   Now v2, with the one-deck classes (decision 17).
4. Voice: bold declarative headlines, honest mono sub-lines; his chat replies keep the casual voice from `mind.py`
   (commit 7069cd1) and are shown tagged "his reply" (the "AI-written" tag was removed on 2026-11-02, see decision 14).
5. Readouts are MODEL readouts, formulas in the spec; the label "not measured from anyone" was removed on 2 November (owner); readouts are "model readouts", nothing more.
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
11. **Intro deck** (owner: "the first thing when you open the website" is a title slide like the reference, plus a small tutorial). `#intro` is five slides, shown on the first visit per browser session (`sessionStorage` key `sub01.intro`) (its own count was removed on 2 November, owner; the dots mark the place), a two-line lock-up. Slides: "A brain / decoded" (`web/hero_brain.webp`); "Real wiring."; "Simulated activity." (`web/intro_brain_top.webp`, a muted blue top view made from `out/sub01_fibres_top.png`); "Four readouts."; "Send a stimulus." with the primary button. Keyboard, dots and click navigate, Esc skips, and the header link "intro" replays it.
12. **The 3D room in the viewport** (owner: "add there the 3D room"). The "his screen" viewport shows the room whenever his screen is off. `web/room.html` has a chromeless `?embed` mode: scene only, a fading mono caption of what he does (`#ecap`), a slow camera drift (±4° round him over 40 s, a ±3 % dolly over 12 s, a ±0.7° tilt), exposure breathing ±3.5 % over 16 s, 30 fps, DPR 1, cursor hidden after 2 s. Contract: parent → iframe `postMessage {type:"sub01-embed", visible:boolean}`, where `visible:false` stops its render loop; iframe → parent `{type:"sub01-embed-ready"}` when he is first drawn. `live.html` creates the iframe once, shows or hides it by opacity, and posts `visible:false` when he is at a screen, when the tab is hidden, when the viewport is off screen, or while the intro deck is open. The away card stays as the loading placeholder ("camera on him · loading").
13. **Motion** (owner: "make everything beautiful and hypnotic"). A radial bloom under each brain breathes with the model's synchrony (CSS variables `--bl` and `--bs`, set at most 10 times a second). The attention trace has a glow and the playhead has a 0.5 Hz halo. A big number that moves 5 points or more flashes (at most once per 2 s). The grid fades in over 600 ms after the deck closes, the hero image's opacity breathes ±8 % with the same sync, and panel borders lift on hover. All of it is off under `prefers-reduced-motion`. Measured cost: 0 fps under software GL (20.5 → 20.9). The room iframe is a separate, open cost (see the open items).
14. **No AI wording on any page** (owner, 2026-11-02: "remove everything that says AI, AI written"). The tags read "his reply", "his notes" and "why". The diary and world pages say images are "rendered from the brain model's state". The room's page-reader lines say "the page is read for him". `about.html` keeps one factual sentence: a language model writes the notes, plans and replies. **This supersedes the hard rule "AI-written text is labelled" in `docs/HANDOFF.md`** (owner decision, 2026-11-02). The mechanism is still stated on `about.html`.
15. **Writing pass** (owner, 2026-11-02). No fragment-for-punch headlines ("Stimuli in. Readouts out." became "Send it a message.") and no "day and night". Two writing plugins were enabled on the owner's account but could not be loaded in that session, so the pass was done by hand.
16. **"Too many LIVE"** (owner, 2026-11-02 evening). One live chip, in the header only. No other LIVE chip on any page (panels, viewports, HUDs). The viewer count sits with the clock in the pulse strip (decision 17).
17. **"Rebuild EVERYTHING"** (owner, 2026-11-02 evening: "room, brain and everything, same style everywhere, use design references, something never seen"). The result is the "one deck" system, specified in `docs/design/decoded/SYSTEM.md`. Every page is one numbered slide of the same deck: 01 live · 02 brain · 03 room · 04 diary · 05 sees · 06 about. Each page has one header with a two-line lock-up, the one live chip, a Tokyo clock and a counter. The shared code:
    - `web/deck.js`: marks the current nav link, fills the counter, takes ← → and `[` `]` between slides, and runs a 320 ms page crossfade through cross-document view transitions. `body[data-keys]` lets a page use the arrow keys itself.
    - `web/pulse.js`: a 28 px live strip at the bottom of each page that declares `data-pulse`, with the four readouts, the clock and the viewer count, a visually hidden text equivalent, and a spike that travels along the strip on every chat message (`SUB01Pulse.spike()`).
    - `web/ui.css` v2: the lock-up, state, segmented control, primary button, number blocks, rails, hud, sheet, dock and title classes.
18. **Sees one at a time** (owner). The sees page was first rebuilt as a contact sheet grid. The owner rejected it ("I hate it") and chose "one at a time". Now sees shows one eye frame with a filmstrip, and diary shows one night with its date headline, one dream image and a filmstrip. On both pages the arrow keys move within the page and `[` `]` change slide.
19. **Simulated audience** (owner: "simulate thousands of users and change based on what they like"). A simulated audience of six segments reviewed the screenshots: traders on phones 35 %, casual viewers 25 %, non-native readers 15 %, designers 10 %, neuroscientists 10 %, accessibility users 5 %. The consensus changes were applied:
    - room first on phones (front page); tap hints and a close button on the intro for touch;
    - plain words: alertness, mental effort, brain activity, "his normal", "what lit up", "send him a message";
    - captions at 11 px minimum, and greys that pass contrast (`--ui-dim` #9494a1, `--ui-faint` #8a8a98);
    - a 2 px focus ring;
    - no developer lines on the brain page, which opens on the blue glow with plain view labels;
    - diary and sees empty states as one sentence over a faint fibre plate;
    - the room's fiction caption on its own bar;
    - the pulse spike on a sent message.
    The segments are simulated reviewers, so the result is a review aid, not user research.
20. **Pages rebuilt** (owner decisions 16 to 19, applied). Front page: the deck header (the slide counter was removed on 2 November, owner) and the footer inside the first screen. Brain (`/brain`): full-bleed brain under the deck chrome, a title-style state line, a rail of seven numbers, two segmented controls, a "his day" drawer holding the old cards, `?mini` unchanged. Room (`/room`): full-bleed scene, state line, a bottom dock with vote · chat · teach · more, reactions in the dock row, the brain square, today and camera pills, corner marks, `?embed` unchanged. Diary and sees: see decision 18. About (`/about.html`): numbered slides with result tiles. Life, tastes and fibres: chrome only.

## State of the work
| piece | owner | state |
|---|---|---|
| Research, plan, spec, `web/ui.css`, routes, redirects, feed fields, smoke paths, README/HANDOFF tables, `tests/test_feed.py`, `clips.py` → `/room` | coordinator + server agent | **done, committed** (baad99b and the commits after it) |
| New nav + header on `web/index.html, room.html, diary.html, world.html, tastes.html, about.html, life.html, fibres.html` | markup agent | **done, committed**: ui.css linked first on all 8 pages, nav + `on` class right everywhere; on phones the nav has its own scrollable row on `/life.html` and `/fibres.html` (`/brain` needed nothing) |
| `web/live.html` (the dashboard) + `docs/design/decoded/README.md` | page agent | **built, committed** (2313055, then the front-page commits 1f2a327 and 1a6e1c3) |
| Animation + voice polish pass on `web/live.html` | page agent | **done, committed** (1f2a327, 1a6e1c3): fold layout, hero image, brain colour rule, RESPONSE waiting state, fps caps, chat order across midnight, scientific register; verified with screenshots at 1440×900, 1280×800, 1024×768 and 390×844, after a chat event, under reduced motion and in the asleep state (`--time-scale 60 --start 23:50`), 0 JS errors |
| Full review: `tools/review_shots.py` on all routes, desktop + phone | coordinator | **done**: 0 JS errors, no horizontal scroll (the /room phone shot needs a longer screenshot timeout than the script's 30 s; the page itself is fine) |
| `python3 -m pytest -q tests/` (before the one-deck rebuild) | coordinator | **done**: 1863 passed, 43 skipped, 5 failed; all 5 already fail on main (`tests/test_boy_mh.py` node stub; `decider` missing on the test stubs in `test_reading.py` and `test_tastes_faster.py`; `test_spiking_live.py` GPU label; `test_spiking_ops.py` flaky connection) |
| City removal (decision 7) | page agent + server agent | **done, committed** (e2d7d3a, c5a243a) |
| Front page half the words, three-line hero, chat line format (decision 10) | owner (decision) | **done, committed** (6c90d1a, 0237ec7) |
| Intro deck on the first visit per session (decision 11) | owner (decision) | **done, committed** (dc00bd0) |
| 3D room in the viewport: `?embed` and the postMessage contract (decision 12) | owner (decision) | **done, committed** (95b2450, 20f1c92); run in headless Chromium only; cost open |
| Motion polish: blooms, glow, halo, flashes, grid fade-in (decision 13) | owner (decision) | **done, committed** (20f1c92); no measurable cost under software GL |
| No AI wording on any page (decision 14) | owner (decision) | **done, committed** (8b29e26, 112a96c, 20f1c92); the API tags followed (167c6f7) |
| Writing pass by hand (decision 15) | owner (decision) | **done** (the plugins could not load in that session) |
| One live chip, header only (decision 16) | owner (decision) | **done, committed** (0c3ccab and the deck commits after it) |
| One deck: `deck.js`, `pulse.js`, `ui.css` v2 and every page's header (decision 17) | owner (decision) | **done, committed** (66cf739 shared layer, 0c3ccab front page, 5d4fd56 brain, 051a71c room, 1c4a279 diary and sees, a166888 frames); about and the life/tastes/fibres chrome in the same series |
| Sees one at a time, diary one night (decision 18) | owner (decision) | **done, committed** (1c4a279, a166888, 07d8081); the contact sheet grid was rejected and removed |
| Simulated audience round and its consensus changes (decision 19) | owner (decision) | **done, committed** (3b0c017 front page, fb5d06c brain, 07d8081 room, diary and sees, 17b3cab room caption, 66cf739 shared layer) |
| Viewer count | owner | in the pulse strip with the clock; the front page has no strip (`/` omits `data-pulse`, see SYSTEM.md) |
| Tests after the one-deck rebuild | coordinator | **1860 passed, 43 skipped, 5 failed** after the last fix (6 before it). The 5 failing tests are the pre-existing ones: `test_boy_mh`, `test_reading`, `test_spiking_live`, `test_spiking_ops`, `test_tastes_faster`. Tests were updated to follow the pages (1afcafa and the test commits): `test_neurons3d` (plain button words, same order), `test_neurons_morph` (the specimen caption may name the cerebellum; the neuron captions may not), `test_brain_anatomy` (glow is the default), `test_glance_cam`, `test_screens` (about's coin section is one line; the room caption keeps "a simulated life · Not a person, not conscious") |
| Jury review: a blind critic on the crawl screenshots, plus an audit (the `/jury` skill) | coordinator | **run on the local build.** The audit's real fails were fixed (15c2440: meta descriptions on room and about, a main landmark on the room, named image links, the about lead as the h1). The two remaining audit fails are false positives (JavaScript template strings read as links). The score card goes in `docs/design/decoded/JURY.md`, written later by the coordinator |
| Docs for the one deck: this file, `decoded/README.md`, `SYSTEM.md` | docs | **done** (2026-11-02 evening) |
| Docs: this file, `SPEC.md`, `decoded/README.md`, `OPERATIONS.md`, `HANDOFF.md` | docs agent | **done** |

## Round of 2 November 2026 (afternoon): jury fixes, owner removals, v3 controls
Branch `claude/compassionate-fermat-piv6wx`. The jury card is `docs/design/decoded/JURY-1.md`; the second is being written.
- **Shared layer:** a skip link on every page (`deck.js`); hovers move more than colour; chips are 24 px; the phone header
  has the lock-up and the LIVE chip on one row; the nav is one scrolling row of 44 px targets.
- **Live (`/`):** phone CLS 0.385 → 0.005. The intro advances on wheel and swipe (roving dots). A faint brain poster sits
  behind each canvas. Readouts show a dash until the first tick, then the last values seen.
- **Brain (`/brain`):** `web/brain_poster.webp` (99 KB) cross-fades out at the first lit frame. The socket opens before
  the geometry. Under reduced motion the brain is still. The headline is capped clear of the brain.
- **Room (`/room`):** `web/room_poster.webp` (60 KB). He is not drawn until his clips run (no T-pose, also in the window
  reflection). A loader pill; a still with one sentence where WebGL is missing. Headline capped at 18ch; shadow maps off under 768 px.
- **About, diary, sees:** cost rows, then the whole Costs section, removed. The contract address is a full-width block with
  a copy button. Empty states show a live next-dream or next-frame line. Images have dimensions; canonical links; `main` landmarks.
- **Owner removals (same afternoon):** the Costs section of `/about.html` (sections now 01–06); "not measured from anyone"
  from every page, `pulse.js` and the spec; the slide counter from every header and `deck.js`; the intro's own count (the dots mark the place).
- **v3 controls** (`web/ui.css` v3 block, `window.SUB01UI` in `deck.js`), from the owner's five references (Rare UI, Kobra,
  EasyUI, Pin UI, Aceternity UI), in black and white, with no library and no font: a light runs round a hovered pill; a white
  thumb slides in the segmented control; one pill slides under the nav; a faint light follows the pointer in panels; the
  primary button is magnetic and shines; `title=` tooltips and a toast; the send button reads "sent ✓"; a blur-in on a
  changing headline (brain, room); shimmer on loader captions. All of it is off under reduced motion.
- **Bugs fixed just after:** the thumb's MutationObserver re-fired itself. It now ignores the thumb's own style changes and
  changes the control's class only when the value changes.
- **Other:** `robots.txt` lost its relative `Sitemap` line (the directive must be absolute; the public origin is still unknown).
  Jury tooling: `audit.mjs` resolves relative URLs.
- **Tests:** green except the five pre-existing failures from main (`test_boy_mh`, `test_reading`, `test_spiking_live`,
  `test_spiking_ops`, `test_tastes_faster`) and `tests/test_interactive.py::test_server_round_end_applies_when_awake`, which
  depends on the Tokyo clock (the "window" activity scores zero around midnight).
- **Still open from this round:** a decimated room GLB for phones; real-GPU and phone checks; the public origin (canonical
  links, sitemap); two template-literal links in served HTML that the audit reads as 404s; the second jury card.

## Open items (what remains)
From the jury review and the audience round:
- **Real GPU and phone checks.** Brain glow fps and the room-in-viewport cost are not measured on a real GPU. The earlier numbers came from software GL only (rAF 12.8 → 20.6 fps at 1440 px; 91–100 % of lit brain pixels blue-dominant at 1440 and 390 px). The caps are 30 fps on desktop and 15 on phones. Measure on the owner's Mac and on a phone. If the room costs too much, pause it while the brains draw, or lower its resolution in embed mode.
- **Headless room T-pose.** The room's T-pose in headless runs is a renderer artefact (software GL), not a page bug.
- **Phone diary scroll.** On phones a portrait dream image makes the diary scroll.
- **Server-written night text.** The night text the server writes still says "replayed"; the page copy was changed to plain words ("played again").
- **X-post clips.** Every frame still carries the corner label "AI · fictional character" and the hashtags #AI #AIgenerated. Left as is: labelling generated media on a platform is the owner's call.
- **Audit warnings (after the 2 November round).** 11 WARN: em dashes in visible text on three pages, meta descriptions over 160 characters on diary and about, thin text on the diary and sees empty states, a repeated sentence on about, images without dimensions on the live page, the 404 page without an h1. 2 FAIL: the template-literal links in served HTML.

Carried over from the earlier list (not in the jury or audience results, still open):
- **Embed, screenshot viewport and dopamine markers on a live server.** The demo runs with `BROWSE=0` (no `life.screen`) and has no dopamine events, so none of them is checked on a live server yet.
- **Owner decision: `about.html`'s section "The coin".** Left in place with the MINT code; reduced to one contract-address line in 3430e25. Remove or keep.
- **Owner decision: the chat-reply voice.** His replies keep the casual voice from `mind.py`. Should they take the scientific register too?
- **Server label:** `live_server.py` still sends `mind_read.tag` as "notes written by an AI" (and `tests/test_mind_live.py` checks it). The page does not show that string (it shows "his notes"). Change it with the next server edit, and then the SPEC line for `mind_read`.

## Facts learned while building (keep)
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
- WebGL1 refuses to link a program whose shared uniform has different precisions in the two shaders (the brains were blank everywhere until the vertex shader got `precision mediump float;`, d8079e1). A canvas that once gave a WebGL context never gives a 2D one: the fallback swaps in a fresh canvas.
- Arousal = clamp(50 + 30·log2(NE)) (spec amended 2026-11-02): with NE/2·100 the trace sat at 100 for minutes, because the model's noradrenaline runs 1.8–2.6 while he listens to music. Each legend item carries its formula in a `title`.
- The test suite takes about 25 min on a 4-core box; two tests (`test_brain_decides.py::test_vote_is_cheap`, `test_neurons3d.py::test_cpu_frames_are_compact_and_honest`) fail under CPU load and pass alone.
- The room's fiction caption keeps its pinned wording, "a simulated life · Not a person, not conscious" (`test_screens`).
- The brain page's glow is its default view. The specimen caption may name the cerebellum; the neuron captions may not (`test_neurons_morph`).

## How to continue (the coordinator's loop)
1. `python3 -m pip install -r requirements-server.txt pytest` (on Python 3.13 the `chess` wheel fails to build: download the
   sdist with `pip download --no-deps --no-binary :all: chess==1.11.2`, untar, copy its `chess/` folder into site-packages).
2. `BROWSE=0 python3 live_server.py --demo --port 8799 --data-dir /tmp/demo &` then `python3 tools/review_shots.py http://localhost:8799 out/review`
   and LOOK at the PNGs (desktop and phone, every route). Fix: overlaps, empty panels, unreadable text, horizontal scroll, JS errors.
3. The front page is built and polished (see the state table). For any change to it, repeat step 2 and check the shots at
   1440×900, 1280×800, 1024×768 and 390×844, a chat event, reduced motion the asleep state (`--time-scale 60 --start 23:50`), and the intro deck (its key is `sub01.intro` in sessionStorage; clear it to see the deck again).
   Every page is a slide of the one deck: for any new page, or any change to the chrome, follow `docs/design/decoded/SYSTEM.md`
   (the spec for the deck order, the header markup, `deck.js`, `pulse.js`, the ui.css v2 classes and the motion).
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
No text is labelled as AI-written (superseded 2026-11-02, decision 14). No "AI" wording on any page. Keep the password gate. No new third-party scripts/fonts beyond the CDNs already used.

## About "mods"
The owner installed Claude Code mods (github.com/nateherkai/claude-code-mods: Cache Keeper, Collision Guard, Goal
Meter, Recording Mode) on their own machine. They act on the owner's local terminal/desktop sessions only; a cloud
session cannot load them and nothing in this repo depends on them.
