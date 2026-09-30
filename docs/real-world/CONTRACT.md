# SUB-01 "real world" build — shared contract

Integration branch: `feature/real-world` (from `main`). Every workstream works on its own branch
`feature/rw-<stream>` in its own git worktree `/home/user/wt/<stream>` created from `feature/real-world`,
commits there, and never pushes to `main`. The integration owner merges streams into `feature/real-world`.

Python venv with all deps (incl. pytest): `/home/user/sub-01/.venv/bin/python`. Headless Chromium:
`/opt/pw-browsers/chromium-1194/chrome-linux/chrome` (Playwright can use it via `executablePath`).
Network: npm registry and `git clone` from GitHub work; polyhaven.com, quaternius.com, cdn.jsdelivr.net,
unpkg, tiktok.com and api.replicate.com are BLOCKED in this sandbox (they work in production).

## Hard rules (every stream)
- Never claim or imply SUB-01 is conscious, alive, sentient or a person. Approved wording:
  "an architecture inspired by theories of consciousness (Global Workspace)", "a model of brain activity, not a mind".
  The honesty line stays visible on every page:
  "Simulated brain activity built from one real person's public MRI. Messages are stimuli, not conversation.
  It is not a mind and it is not the person."
- Never speak as, name, depict or invent memories of the real person whose scans were used. No real faces;
  the character is a stylised adult without a recognisable face and is not modelled on anyone.
- Generated text never asks for money, never tells anyone to buy/sell, no financial promises, and always
  passes `mind.safe_text()` (which includes `chat.blocked()`); fallback = rule-based line.
- Assets: only CC0 (or equally permissive, attribution recorded) with a line per file in `web/assets/CREDITS.md`
  (file, source URL, author, licence). TikTok only via the official embed of URLs listed in `web/phone_feed.json`;
  never download or re-host videos.
- Keep the password gate, the chat filter and rate limits untouched. Never commit or print secrets (`.env`,
  `REPLICATE_API_TOKEN`, `SITE_PASSWORD`); never log tokens.
- The construct has its own style: no "Matrix" name, logos or green code rain.
- Server stays light (Railway): no local ML, mind cycle < 5 ms, no new heavy deps. Client work runs on the viewer's GPU.
- Replicate calls only while someone is watching (clients > 0), rate-limited.

## Server (Python)
### `mind.py` (new) — Global-Workspace-inspired architecture
```
Candidate: {"id": str, "kind": "need"|"chat"|"memory"|"market"|"perception"|"dream",
            "label": str (short, shown on page), "content": dict, "salience": float >= 0, "source": str}
class Mind:
    def __init__(self, state=None, rng=None, llm=None, clock_fn=None)  # llm(system:str, user:str)->str or None
    def hear(self, msg: dict, t: float)        # accepted chat msg: {"text","nick","networks","regions","emotion","stage"}
    def cycle(self, t, ctx) -> dict             # ctx: {"stage","rel": {group: rel activity},"needs": {...},
                                                #   "life": life snapshot, "market": str, "replays": [str],
                                                #   "memories": [memory items], "viewers": int}
        # returns {"type":"mind","cycle":int,"t":"HH:MM","candidates":[{id,kind,label,salience,source}],
        #          "winner": id|None, "broadcast": {...}|None, "self": {...}}
    def speech_due(self) -> dict|None           # pending inner-speech line: {"text","kind":"rule"|"llm","lang","about","action"}
    def diary(self, date) -> list; def to_dict(self) -> dict
def safe_text(s: str) -> bool
```
- Salience = brain network activity (reward, fear/salience, attention, default, language; `rel` values are
  activity relative to the global mean) x kind weights + need levels + recency/novelty, with inhibition of return
  (a winner is suppressed for a while) and a small noise term. One winner per cycle (~every 2 s real).
- Broadcast of a winner drives: (a) the next action via `life.request(act, t, reason)` (accept/decline with a
  reason tied to needs/state/opening hours), (b) the inner-speech line, (c) memory encoding, (d) the eye (eye gets
  `mind.focus()` text as extra context when available).
- Self-model: doing, feeling (from brain rel -> words), wanting (top need), recent history (last ~10 broadcasts).
  Continuity: diary persisted to `data/diary/YYYY-MM-DD.json` (no personal data, nicknames allowed), loaded on start.
- Inner speech: short first-person lines (IT when the triggering message is Italian, else EN). Rule-based by default;
  LLM (existing Replicate Llama path in eye.py) at most once per broadcast worth showing, >= 30 s apart,
  <= 60/hour, only when viewers > 0, run off the event loop; output must pass `safe_text` else rule line.
### `life.py` (extended)
- `Life.request(act, t, reason) -> (ok: bool, why: str)`; opening hours (bakery 07:00-20:00, park daylight),
  baker NPC state in snapshot (`npc.baker`: present, pose), `energy` from sleep pressure, snapshot fields stay
  backwards compatible. Existing utility choice remains the fallback when the workspace has no action winner.
- Demo flag in live_server: `--life-activity <act>` forces the first activity (for screenshots).
### `chat.py` (extended)
- Transparent keyword/semantic table `REGION_RULES` (topic -> networks) added to the existing RULES; the page
  shows the table. Optional nickname: `check_nick(nick) -> (ok, reason)` (<= 20 chars, letters/digits/space/_-,
  passes `blocked`). Returning nicknames remembered in `data/nicks.json` ({nick: {first, last, count}}), no IPs.
### `live_server.py` websocket messages (additive; keep existing fields)
- client -> server chat: `{"type":"chat","text":str,"nick":str?}`
- `hello`: + `"regions": {group: [brain region indices]}`, `"mind": last mind msg`, `"region_rules": [...]`
- `chat`: + `"nick"`, `"returning": bool`, `"regions": [brain region indices]`, `"cid"` (candidate id)
- `tick` (20 Hz): unchanged + `life` snapshot with `npc`, `energy`, `open`
- `mind` (each cycle): as returned by `Mind.cycle`
- `speech`: `{"type":"speech","text","kind","lang","about","cid","action":{"act","ok","reason"}|null,"t"}` -
  `about` is the topic (free text: "bread", "a message", "a dream"); `cid` is the id of the winning chat candidate
  (`"chat:N"`, equal to `chat.cid`) when the line belongs to a chat message that won the workspace, else `null`.
Brain region indices = index into `tick.act` = index into `web/brain.json` nodes (same order).

## Client (web) — "the construct" (CHANGE OF DIRECTION: no photorealistic world)
Main view: SUB-01 lives inside a world built from its own brain data. Own style: dark, orange/neon
(#ff6a00 family, warm whites, deep blue-black). NOT a copy of The Matrix: no such name, no logos, no green code rain.
The CC0 photoreal assets in `web/assets/` are no longer used by the main view (kept, credited, not loaded).
- **Districts** = the 214 atlas regions: positions from the real centroids (`web/brain.json` nodes `q`, same order as
  `tick.act`), spread out as a city (radial expansion + flattening onto a ground plane, deterministic); building
  height/glow = live region activity (`tick.act` relative to each region's running baseline).
- **Streets** = the real tractography: `web/fibres.bin` (n x pts x 3 float32, see `fibres.json`) + `fibres_ends.bin`
  (int16 pair of atlas labels per fibre, `-1`/0 = unlabelled; map labels -> node index via `nodes[i].lab`) become light
  roads between districts (bundled/subsampled per quality).
- **Places** (life.py place -> district): home = default-network district (bed/window/table/desk/doors = default-network
  regions around it), bakery/food = reward district (Accumbens/Caudate/Putamen; bakery_door/bakery_in/counter),
  park = calm limbic/memory district (Hippocampus / limbic; park_gate/bench), fear district (Amygdala + salience)
  stays dark unless `groups.fear`/`groups.salience` rise. street_* waypoints lie on the road between districts.
- **Walking**: life.py stays the brain of behaviour. `tick.life` gains `route` (place names of the current walk,
  start..goal) and `progress` (0..1 of walked distance, timed like today: WALK_SPEED on the waypoint graph). The
  first-person camera travels along the real fibre path (shortest path over the region graph built from labelled fibre
  ends, each hop following a representative fibre polyline) from the start district to the goal district at that progress.
- **Chat rain**: each accepted `chat` message falls as orange "rain" made of its own words and lands on the districts
  it stimulates (`regions` from chat.py's rule table), which flash (mini brain flashes too). If the message wins the
  workspace (`speech.cid == chat.cid`; client: `chatByCid.get(m.cid)`), show its inner line.
- **Weather** = market (`tick.market`: pumping -> warm pulses; dumping -> glitches/distortion; choppy/calm).
- **Sleep**: NREM -> city dims and slows; REM -> world warps and replays the day's messages as floating words
  (déjà vu; `tick.events` of type replay). Night (Rome time) -> darker sky, lit roads.
- **Views**: first person (default), orbit/overview, and the mini real-brain PiP (existing minibrain.js) always on.
- Performance: phones 30 fps (quality low: instanced districts, <= ~3k fibres, no heavy post), desktop 60 fps
  (medium/high: more fibres, bloom). One draw call per system where possible (InstancedMesh, merged LineSegments,
  shader-driven activity via textures/attributes, no per-frame allocations).

### Modules (`web/construct/`, ES modules, vendored three via the importmap in `web/life.html`)
| file | owner stream | exports |
|---|---|---|
| `data.js` | core | `loadBrainData(quality)` -> `{nodes, districts:[{i,name,group,pos:Vector3,role}], placeDistrict(place)->i, roads:{positions, pairs}, graph, pathBetween(i,j)->[Vector3...], districtOf(role)}` |
| `main.js` | core / integration | boot, websocket, render loop, views switch, URL params, hooks below |
| `city.js` | city | `createCity(scene, data, quality)` -> `{update(dt, env, act), flash(regions, color), setFear(k), object}` |
| `travel.js` | travel | `createTravel(camera, controls, data)` -> `{update(dt, life, env), setView('first'|'orbit'), view}` |
| `fx.js` | fx | `createFx(renderer, scene, camera, data, quality)` -> `{rain(msg), innerLine(speech), weather(market), update(dt, env), render()}` (owns post-processing: bloom, glitch, warp) |
| `web/world/hud.js`, `minibrain.js`, `phone.js`, `net.js`, `quality.js` | hud / foundation | reused from the foundation (hud adds a view switch; phone = HUD overlay only) |
env = {romeHour, dayK, night, stage, lab, sleep, quality, market, groups}. URL params: `?view=first|orbit`,
`?q=low|medium|high`, `?nofollow=1`; `window.__sub01 = {ready, fps, drawCalls, triangles, quality, connected, view}`.

Core additions (as implemented on `feature/rw-core`; other streams build on these shapes):
- `data.js` also returns `roles {home, reward, park, fear, salience: [i...]}`, `pointAt(path, u, out)`,
  `mapPoint(x, y, z, out)` (brain mm -> city), `radius`, `scale`, `lab2node`, and `groupRegions {group: [i...]}`
  (brain.json groups + `language`, same rule as brain_sim.py; fallback for `hello.regions`). `pathBetween` returns a
  Vector3 array with `.lengths` (cumulative), `.total`, `.hops`.
- `travel.js`: `createTravel(camera, controls, data, {scene})`, also exposes `position`.
- `fx.js`: also `resize(w, h)` (and optional `dispose()`, called when a quality switch recreates fx with the new preset).
- `city.flash(regions)` / `minibrain.flash(regions)` receive region indices: `chat.regions` plus every group in
  `chat.networks` expanded through `hello.regions`. `fx.rain(msg)` gets `msg.regions` = the topical `chat.regions`.
- `web/life.html`: `#view` (view switch container, was `#lab`) and `#fx` (overlay for rain / inner line text).
- env extras: `groupRel`, `groupSelf`, `replays [{text, t, seq}]`, `walking`, `time`, `view`, `follow`.

### Server additions for the construct
- `tick.life.route`, `tick.life.progress`; `tick.market` (pumping/dumping/choppy/calm, existing market_mood).
- Demo-only flags (require `--demo`): `--life-activity <act>`, `--force-market pump|dump`, `--force-stage NREM|REM`.

## Tests
- `tests/test_mind.py`, `tests/test_life.py`, existing `tests/test_sleep.py` (pytest).
- `tests/e2e/`: headless screenshot check against `live_server.py --demo`: home, walking the fibre road to the reward
  district, chat rain landing, dump glitch, night, REM (+ GIF, + 390x844 mobile); fails on console errors, blank
  canvas or missing honesty line.
