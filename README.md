# SUB-01

A whole-brain model of one real human brain, built from public MRI data and wired to live Solana trades.

- **Data:** MyConnectome, OpenNeuro [ds000031](https://openneuro.org/datasets/ds000031) (public domain, PDDL). Raw scans are never stored here; the scripts download what they need.
- **Real parts:** nerve-fibre tractography (diffusion MRI), cortical surface (T1), recorded resting-state activity (fMRI).
- **Simulated part:** region-to-region dynamics (delayed Stuart–Landau oscillators on the subject's connectome).
- It is a model of brain activity, not a mind, and makes no claim of consciousness.

## Pipeline

| Step | Script | Output |
|---|---|---|
| Connectome (tractography + Schaefer-200 / Harvard-Oxford atlas) | `build_connectome.py` | `out/connectome.npz`, `out/labels_dwi.nii.gz` |
| Real fibres for the web | `export_fibres.py` | `web/fibres*.bin`, `web/fibres.json` |
| Cortical surface | `build_cortex.py` | `web/cortex*.bin` |
| Resting-state activity (streamed, raw deleted) | `process_rest.py N` | `out/rest/*.npz` |
| Nodes / edges for the page | `export_web.py` | `web/brain.json` |
| Live page + model + Solana log stream + chat + sleep | `live_server.py --mint <MINT>` or `--demo` | http://localhost:8765 |
| Sleep/wake engine, memory replay | `sleep.py` (used by `live_server.py`) | `data/state.json`, `data/nights/YYYY-MM-DD.json` |
| Chat filter + message -> stimulus rules | `chat.py` (used by `live_server.py`) | |

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
./fetch_data.sh   # ~900 MB from OpenNeuro into data/ (git-ignored)
```

## Resting-state activity (real recorded brain activity)

`process_rest.py N [--workers 6]` streams the first N of the 132 resting-state runs listed in `rest_runs.txt`
from OpenNeuro in parallel worker processes (~1.9 GB RAM each), keeps a region x time series per run in
`out/rest/` (~240 KB each) and deletes the raw file. Runs already in `out/rest/` are skipped. It only needs `out/labels_t1.nii.gz` and `out/t1_brain_1mm.nii.gz` (skull-stripped,
committed), so it runs on a fresh clone: `pip install -r requirements.txt && python process_rest.py 132`.
After processing (or with `--validate` alone) it runs a QC: mean homotopic (left/right, name-matched) correlation
vs mean correlation over all pairs, per run, written to `out/rest/qc.json`. Runs with homotopic < 0.3 (likely bad
registration or motion) are moved to `out/rest/rejected/` (not committed) and not re-downloaded on later runs.

## Sleep, chat and memory (Phase A)

No language model, no generated text: everything below is a rule table.

- **Clock:** Europe/Rome. Awake ~08:00-00:00, asleep 00:00-08:00; with high sleep pressure it goes to bed after 20:00.
  `--time-scale 60` runs one sim hour per real minute, `--start 23:55` starts the demo clock there.
- **Stages** (Stuart-Landau parameters glide over ~1-2 min, never jump):
  AWAKE 10 Hz, normal coupling, stimulus gain 1.0 · NREM 1-3 Hz, 2-3x coupling, high synchrony, gain ~0.15
  (deepest in early cycles) · REM 6 Hz, 0.6x coupling, more noise, gain 0.4 (longer in later cycles). ~90 min cycles.
- **Arousal:** messages and large trades (>= $5k) add to it, it decays over minutes; crossing the threshold wakes it
  ("woken at 03:12 by 5 messages"); after 10 quiet minutes it falls asleep again.
- **Sleep debt:** +1 h per hour awake at night, +0.25 h per wake-up, repaid by sleep (faster before midnight).
  A tired brain is less reactive (lower gain) and noisier the next day.
- **Chat:** max 280 characters, 1 message / 10 s per client, duplicates dropped. The filter runs first and blocks links,
  Solana/ETH addresses, $TICKERS, insults, requests for money and personal data (e-mail, phone): blocked messages are
  never shown or stored. Accepted messages hit: language (left temporal + frontal operculum) + somatomotor always,
  reward (positive words), fear + salience (threat words), attention + control (questions), default network
  (mentions of SUB-01 / "you"). Asleep, the drive is scaled by the stage gain and the message is marked "heard while asleep".
- **Memory + replay:** accepted messages are stored with time, stage, stimulus pattern and emotional tag. In REM the
  hippocampus replays them at 35 % amplitude, picked by recency, emotion and "arrived tonight" (with habituation).
  Each night is written to `data/nights/YYYY-MM-DD.json` (stage timeline, wake-ups + cause, sleep debt, replayed
  messages = "dream ingredients"). State is saved every minute to `data/state.json`. IPs are only kept for the
  10 s rate-limit window; nothing about who sent a message is stored.

```bash
python live_server.py --demo --time-scale 60 --start 23:55   # accelerated night (state in data/demo/)
python tests/test_sleep.py                                    # or: python -m pytest tests/
```

## End-to-end screenshots ("the construct")

`tests/e2e/screenshots.mjs` starts `live_server.py --demo` (temp data dir, free port) once per scenario, opens the page in
headless Chromium (software WebGL) and captures: `home`, `walk` (first-person walk along the real fibre road from the home
district to the reward district, captured at `life.progress` 0.3-0.7), `chat` (message rain in the **orbit view** with
`?nofollow=1`, so the rain and the landing districts are in frame: `chat-falling` ~1 s and `chat` ~3 s of fx time after the words
start falling), `dump` (market glitch, `?fxhold=1`), `night`, `rem`, `orbit` (`?view=orbit`) and `mobile` (390x844). With `--gif` the
walk is run a second time as `walk-gif`: up to 60 frames of the 3D canvas (captured in the page, ~3 fps under software rendering, 800x500
viewport) over the whole ~22 s walk, written to `walk.gif` with the real gaps between frames as delays (real-time playback; it fails
below 20 frames or 10 s).

Every scenario fails on console errors, WebGL errors (`GL_INVALID_*`, context lost), a Python traceback in the server log, a missing
or covered honesty line, or while a construct module it needs (`city`, `fx`, `travel`) is still a `STUB` file (`--allow-stubs` skips
that; a stream must remove the `// STUB` header when it replaces its file). Pixel checks measure the **3D canvas alone** (all DOM
overlays are hidden for that capture); `--selftest` proves it by hiding the canvas over a black page and
expecting both the blank-canvas and the almost-black check to fail. Assertions are state-based where the page exposes state:
- life ticks: outbound route home -> bakery, `life.progress` advancing;
- `window.__sub01.fx` (fx stream debug fields `free, queued, pending, glitch, warp, hold, time`; the chat/dump/rem scenarios depend on
  them, so they are part of the contract in practice) and `?fxhold=1`: rain in flight and landed (waited on fx time, not wall time),
  glitch, warp;
- the camera: the harness hooks the `viewMatrix` uniform uploads of the main canvas (or reads `window.__sub01.camera` if a page ever
  exposes it), so `walk` asserts on camera POSITION: net displacement along the road far above the idle drift measured in `home`;
- the chat rain is also checked in the pixels: new amber glyph pixels outside the scene's own flicker zone (two idle frames define it) must
  far exceed the same count on a third idle frame, so a pool-state-only pass cannot hide an invisible effect.

A failing scenario writes its captures as `<name>.FAILED.<ext>` (and `walk.FAILED.gif`), never over the good files.

```
cd tests/e2e && npm install && npx playwright install chromium     # gifenc, pngjs, playwright + its Chromium
node tests/e2e/screenshots.mjs [--only=home,walk] [--gif] [--format=png|jpg] [--out=docs/real-world/screenshots] [--allow-stubs] [--selftest]
```

Env: `E2E_CHROME` (use a specific Chromium instead of Playwright's), `E2E_PYTHON` (default `.venv/bin/python` or `python3`),
`E2E_TOOLS` (extra directory holding `node_modules/playwright`). `night` compares against the `home` canvas brightness measured in
the SAME run (run them together; an older `report.json` is never used).

Output goes to `docs/real-world/screenshots/` (`<scenario>.png|jpg`, `walk.gif` with `--gif`, `report.json` with fps / draw calls /
triangles per scenario). The fps values are **software-rendered** (SwiftShader, no GPU) and only useful to compare scenarios,
not as device performance. Exit code is non-zero if any scenario fails; servers are always killed, a timed-out scenario is
cancelled (server and browser context closed, no files written) before the next one starts; per-scenario timeout 150 s.
The screenshots are generated from the merged construct and committed with the PR, not from this stream alone.
