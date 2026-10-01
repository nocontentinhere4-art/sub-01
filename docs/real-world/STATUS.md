# SUB-01 "the construct": status (integration, `feature/real-world`)

Direction: the photorealistic world is cancelled. The main view (`/`, `web/life.html`) is the construct: SUB-01 lives inside
a world built from its own brain data. It is a model of brain activity, not a mind; the workspace is an architecture inspired by
theories of consciousness (Global Workspace). The photoreal CC0 assets in `web/assets/` are kept and credited
(`web/assets/CREDITS.md`, `docs/real-world/ASSETS.md`) but the main view no longer loads them; the old photoreal page
(`web/world.html`, `web/world/main.js`) is unused.

Merged streams: server, core, city, travel, fx, hud, e2e (+ integration fixes below).

## What works (verified end to end)

| chain | how it was checked |
|---|---|
| "ho fame, vai a comprare il pane" -> chat candidate wins the workspace -> inner line with `cid == chat.cid` and `action: buy_bread ok` -> life walks home -> bakery counter -> later home to the table | `tests/test_integration.py` (server, websocket messages) and a headless page run: `__sub01.lastSpeechChat` true 2.4 s after sending, `tick.life.progress` 0.04 -> 0.99 towards `counter`, `__sub01.camera` moving along the road |
| first-person camera on the real fibre road to the reward district | e2e `walk` (camera position, route, progress) + `walk.gif` |
| chat rain lands on the topical districts, city + mini brain flash | e2e `chat` (fx pool state + new glyph pixels on the canvas) |
| threat message -> fear district turns red | headless run: "I am scared, danger, a monster attack" -> `__sub01.fear` = 1 (Italian threat words now count too) |
| market weather (pump pulses / dump glitches) | e2e `dump`; pump seen live (`__sub01.fx.pump` 0.8) |
| night dim + lit roads, NREM dim, REM warp + replayed words | e2e `night`, `rem` |
| views (first person / overview / mini brain PiP), lab look (`?lab=1`, `l`) | e2e `orbit`, `home`; lab checked in a headless run |
| HUD: workspace panel (candidates, winner, self-model), chat with nickname, rules table, inner speech | every e2e capture; phone layout in `mobile` |
| honesty line visible and not covered | every e2e scenario |

Screenshots: `docs/real-world/screenshots/` (`home`, `walk`, `chat-falling`, `chat` (rain), `dump`, `night`, `rem`, `orbit`,
`mobile` as jpg, `walk.gif`, `report.json`).

## Integration fixes in this round

- The mini brain re-downloaded `brain.json` and the 17 MB `fibres.bin` (the browser cache did not dedupe them): startup was 36 MB.
  `data.js` now exports `loadBrainRaw()` and the mini brain reads the same promise: 19.2 MB.
- `--start HH:MM` was ignored at `--time-scale 1` (`sleep.Clock`); it is now honoured at any scale (production passes no start).
- Lab mode existed in the city shaders but nothing set `env.lab`: `?lab=1` / key `l` restore it.
- `window.__sub01.camera` (the e2e harness prefers it over its WebGL hook), `__sub01.fear`, `__sub01.lab`; the debug fields the
  e2e depends on (`__sub01.fx`, `lastChatRegions`, `lastSpeechChat`) are now listed in `CONTRACT.md`.
- The stimulus word lists (`chat.POSITIVE` / `HOSTILE`, not the filter) were English only, so an Italian threat ("ho paura") never
  reached the fear district: Italian words added, with a test.

## Performance

See `README.md` -> Performance. Short version: workspace cycle ~0.5 ms (budget 5 ms); server tick mean ~48-51 ms / p95 ~58-69 ms
on this shared, loaded 4-CPU machine (budget 50 ms; `Brain.step` is ~43 ms of it); 10-33 draw calls and 15-27k triangles
depending on quality and view; 19.2 MB downloaded at startup. Client fps here is software rendering and not representative.

## Missing / known issues

- **Real-device performance** is unmeasured (phones 30 fps / desktop 60 fps targets). Software rendering runs at 12-15 fps.
- **Server tick** is at or above the 50 ms budget here, all in `Brain.step` (numpy oscillator model; BLAS threads do not change
  it). The loop does not burst to catch up, so the effect is a lower tick rate; needs a measurement on the Railway instance.
- **Startup on phones**: low quality still downloads the full 16.5 MB `fibres.bin` and builds on the main thread; a
  pre-subsampled low-quality file (or a Worker build) would help.
- **Walks are long in city units** (about 640-830 vs a straight line of 136-273): real fibre routes pass through 3-4 hub regions.
- **TikTok** embeds were not seen here (tiktok.com blocked); `web/phone_feed.json` is empty and needs human curation.
- **Language-model inner speech** was not exercised (no token in the sandbox; replicate is blocked). Rule lines are used.
- Cosmetic: a district label can be clipped at the frame edge (3D sprite); in first person the inner line can overlap the
  reward district label; the arrived view at the bakery is a close wall of towers; label fan-out snaps on a view switch.
- `FALLBACK_WORLD` / `ACT_PLACE` in `main.js` only matter if the server sends no route / progress (kept as a fallback).
- A late language-model answer for a released held line still counts against the hourly budget (minor).
- `web/world.html` + `web/world/main.js` (photoreal page) can be deleted once nobody needs the reference.

## Next steps

1. Measure on real devices (a mid-range phone at `?q=low`, a laptop at `?q=medium|high`) and tune presets.
2. Ship a pre-subsampled `fibres_low.bin` (~2.5k fibres) so phones download ~2 MB instead of 16.5 MB.
3. Profile `Brain.step` on the production instance; if needed lower its internal steps per tick or vectorise the delay lookup.
4. Curate `web/phone_feed.json` by hand (official TikTok embed URLs only).
5. Smooth label / camera transitions on a view switch; per-district standoff for the arrived view.
