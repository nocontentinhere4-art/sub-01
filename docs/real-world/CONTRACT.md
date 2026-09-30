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
- `speech`: `{"type":"speech","text","kind","lang","about","action":{"act","ok","reason"}|null,"t"}`
Brain region indices = index into `tick.act` = index into `web/brain.json` nodes (same order).

## Client (web)
- three.js is vendored (no CDN): `web/vendor/three/` = `three.module.min.js` + needed `examples/jsm` addons +
  draco/basis decoders, loaded through an importmap. `/brain` (web/index.html) may keep its current CDN build.
- `web/life.html` = shell (HUD markup, CSS, importmap) + `web/world/main.js` (entry). One module per stream:
  | file | owner stream | exports |
  |---|---|---|
  | `web/world/main.js` | foundation / integration | boot, WS client, render loop, URL params |
  | `web/world/net.js` | foundation | `connect(handlers)` WS with reconnect (wss on https) |
  | `web/world/quality.js` | foundation | `Quality` presets low/medium/high, auto by device, `?q=` |
  | `web/world/world/*.js` | world | `createWorld(renderer, scene, camera, assets, quality)` -> `{update(dt, env), setLab(on), anchors}` |
  | `web/world/assets.js` | world | manifest loader, lazy-loading, fallbacks when a file is missing |
  | `web/world/character.js` | character | `createCharacter(scene, assets)` -> `{update(dt, life), object}`; `createBaker(...)` |
  | `web/world/phone.js` | phone | `createPhone()` -> `{texture, overlayEl, update(state), setApp(app)}` |
  | `web/world/hud.js` | hud | chat (with nickname), workspace bars, inner speech, clock/stage, honesty line |
  | `web/world/minibrain.js` | hud | mini fibre brain; `flash(regions, color)` + pulse from chat box to brain |
- URL params for tests/screenshots: `?cam=apartment|street|bakery|park|phone|brain`, `?q=low|medium|high`,
  `?lab=1`, `?nofollow=1`. `window.__sub01` exposes `{ready: bool, fps: number, drawCalls, triangles}`.
- Assets: `web/assets/` (+ `manifest.json`, `CREDITS.md`), glTF/GLB with Draco or Meshopt, textures KTX2 or WebP,
  total <= 100 MB (aim <= 40 MB), lazy-loaded per area; every loader has a procedural fallback.
- Rendering: ACES filmic tone mapping, sRGB output, HDRI environment, soft shadows, bloom (+SSAO/GTAO on high),
  day/night from Rome time (`tick.sleep.clock`), lit windows + street lamps at night, lab-mode toggle kept.
  Targets: 60 fps desktop, 30 fps mid phone; quality switch in the HUD.

## Tests
- `tests/test_mind.py`, `tests/test_life.py`, existing `tests/test_sleep.py` (pytest).
- `tests/e2e/`: headless screenshot check (day, night, lab, phone, bakery, chat flash) against
  `live_server.py --demo --start HH:MM`; fails on console errors or blank canvas.
