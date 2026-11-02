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
coordinator that plans, allocates (Haiku/Sonnet/Opus agents to save tokens) and checks the work.

## Decisions taken (do not re-litigate)
1. `/` → `web/live.html` (the brain-first dashboard, NEW). `/room` → `web/room.html` (was `/`). `/brain` → `web/index.html`
   (the deep 3D brain, unchanged). Old links redirect (`OLD_PATHS` in live_server.py).
2. Nav on every page: live · brain · room · diary · sees · city (then about / map where a page had them).
3. Design system: `web/ui.css` (tokens + header chrome + chips + big numbers). Pages load it before their own CSS.
4. Voice: bold declarative headlines, honest mono sub-lines; his chat replies keep the casual voice from `mind.py`
   (commit 7069cd1) and are shown tagged "his reply · AI-written".
5. Readouts are MODEL readouts, formulas in the spec; labelled "not measured from anyone" wherever shown.
6. The q=1 WebSocket feed now carries `groups`, `aud` and `life.{activity,place,phone,screen}` (screen filtered to
   `BRAIN_SCREEN`), see `Feed.brain_view` in live_server.py and the sample tick in the spec.

## State of the work
| piece | owner | state |
|---|---|---|
| Research, plan, spec, `web/ui.css`, routes, redirects, feed fields, smoke paths, README/HANDOFF tables, `tests/test_feed.py`, `clips.py` → `/room` | coordinator + Haiku agent | **done, committed** (baad99b and the commit that carries this file) |
| New nav + header on `web/index.html, room.html, diary.html, world.html, tastes.html, about.html, life.html, fibres.html` | Sonnet agent | **done, committed**: ui.css linked first on all 8 pages, nav + `on` class right everywhere, 0 JS errors at 1280 and 390; open: eyeball the narrow-width nav wrap on /brain, /life.html and /fibres.html |
| `web/live.html` (the dashboard) + `docs/design/decoded/README.md` | Opus agent | **built, committed**: loads with 0 JS errors at 1440/1024/390, chat round-trip works; raw-WebGL top-view brains (cortex strokes + connectome fibres, colour = region vs own 25 s baseline), 4-trace timeline with markers/scrub, viewport (embed → screenshot → away card), feed, footer. Not done: asleep state unverified; phone LIVE brain over-saturated and RESPONSE brain blank before an event at 390px; fps unconfirmed on real GPUs (software GL gave 2–5 fps; draw brains at 30 fps, stop redrawing a frozen RESPONSE); RESPONSE shows "--" until the first event; chat order wrong across midnight; the LIVE panel's big Attention number sits below the fold at 1440×900 (make the panel fit the viewport); no final polish pass against the references |
| Animation + voice polish pass on `web/live.html` | planned (Opus) | **not started** |
| Full review: `tools/review_shots.py` on a demo server (all routes, desktop + phone, JS errors, h-scroll), `python3 -m pytest -q tests/`, `BROWSE=0 python3 tests/smoke_demo.py` | coordinator | **not done** for the page work |

## Facts the page agent learned (keep)
- brain.json's mesh is in the nodes' `p` space, not `q` (`q` belongs to cortex.bin, used by /brain): map vertices to regions with `p`.
- The q=1 tick's `groups` has 13 keys (the spec's 11 plus `insula` and `language`).
- Plan / notes arrive only on change, so the page also reads `/api/mind` on load and every 60 s, and `/api/decisions`, `/api/music` on load.
- Python Playwright is NOT installed in the cloud image; Node Playwright is (`NODE_PATH=/opt/node-tools/node_modules node …`), and `tools/review_shots.py` needs `pip install playwright` (do not run `playwright install`; the browser is at /opt/pw-browsers/chromium).
- The demo server needs ~20 s to start and dies with its shell; start it with `setsid` or `nohup`.

## How to continue (the coordinator's loop)
1. `python3 -m pip install -r requirements-server.txt pytest` (on Python 3.13 the `chess` wheel fails to build: download the
   sdist with `pip download --no-deps --no-binary :all: chess==1.11.2`, untar, copy its `chess/` folder into site-packages).
2. `BROWSE=0 python3 live_server.py --demo --port 8799 --data-dir /tmp/demo &` then `python3 tools/review_shots.py http://localhost:8799 out/review`
   and LOOK at the PNGs (desktop and phone, every route). Fix: overlaps, empty panels, unreadable text, horizontal scroll, JS errors.
3. Compare `/` with the reference screenshots (the owner's images 2–5; the spec describes them) and `docs/design/decoded/README.md`'s
   "not done" list; finish the missing panels, then do the animation + voice pass (hero line rotation with counter,
   number tweens, marker pops, frame crossfade, brain cloud breathing with sync; prefers-reduced-motion off switch).
4. `python3 -m pytest -q tests/` (spiking tests skip without torch; browser tests without Chromium) and the smoke test.
5. Commit in small, descriptive commits (house style: one line saying what changed and why, no model names), push to the
   branch above. Do not open a PR unless the owner asks. `main` auto-deploys to Railway; this branch does not.
6. Delegation that worked: Haiku for mechanical server/doc edits, Sonnet for multi-file markup edits with a Playwright
   self-check, Opus for the page build. Give each agent disjoint files, its own demo port, the spec path, and a
   required self-check; the coordinator reviews diffs and screenshots and owns commits. Agents must never `pkill`
   by pattern (one killed another's demo server); kill by PID only.

## Hard rules (short form; the full list is in docs/HANDOFF.md)
A model, not a mind: never claim feeling, thought, consciousness or life. The character is fiction. Never name or hint
at the scanned person (credit lives on /about.html only). No coin promotion, no trade tape, no secrets in git or logs.
AI-written text is labelled. Keep the password gate. No new third-party scripts/fonts beyond the CDNs already used.

## About "mods"
The owner installed Claude Code mods (github.com/nateherkai/claude-code-mods: Cache Keeper, Collision Guard, Goal
Meter, Recording Mode) on their own machine. They act on the owner's local terminal/desktop sessions only; a cloud
session cannot load them and nothing in this repo depends on them.
