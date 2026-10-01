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

No language model, no generated text. Sleep is a small published circuit model (details, equations, sources and
limits in `docs/twin/sleep.md`); chat filtering and replay are rule tables.

- **Clock:** local Asia/Tokyo (`SUB01_TZ`). The Phillips & Robinson (2007) flip-flop (monoaminergic group vs VLPO,
  homeostatic somnogen H, circadian drive C) is calibrated to sleep ~23:56-07:54 when nothing disturbs it.
  `--time-scale 60` runs one sim hour per real minute, `--start 23:55` starts the demo clock there.
- **Stages:** NREM/REM come from a REM-on/REM-off flip-flop with a slow REM pressure (~80-100 min cycles, first REM
  after ~75 min, REM ~22 % of sleep, longer REM late in the night, deepest NREM early). Stuart-Landau parameters
  glide over ~1-2 min, never jump: AWAKE 10 Hz, gain 1.0 · NREM 1-3 Hz, 2-3x coupling, gain ~0.1-0.25 · REM 6 Hz,
  0.6x coupling, more noise, gain 0.4. `engine.modulators` gives DA/5-HT/NE/ACh levels read from the circuit.
- **Arousal:** messages and large trades (>= $5k) are an input to the monoaminergic population that decays over
  minutes; waking up is the flip-flop switching ("woken at 03:12 by 5 messages", 2-4 messages in a row mid-night),
  and it falls asleep again once the input fades.
- **Sleep debt** is the homeostatic pressure H above the model's own rested cycle, in hours of lost sleep: lost sleep
  and wake-ups raise it, sleep repays it, high debt means earlier and longer sleep and a less reactive, noisier
  waking brain.
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

## v2: the digital twin (neural mass model, neuromodulators, body, plasticity)

SUB-01 v2 is *a digital twin model of one real person's brain structure and recorded activity; not a mind, not
conscious, not the person.* The live server now runs the fitted neural mass model (`twin/model.py`, Wilson-Cowan E/I
regions on the connectome, parameters fitted on half of the recorded resting-state sessions) instead of the 10 Hz
Stuart-Landau oscillators, and wires in:

- **neuromodulators** (`twin/neurochem.py`): trades give phasic dopamine (reward prediction error) and noradrenaline;
  tonic levels follow the sleep circuit; receptor-weighted per-region gain;
- **a small body** (`twin/body.py`): heart rate, breathing, blood glucose, hunger; the simulated life eats when hungry;
- **toy plasticity** (`twin/plasticity.py`): bounded Hebbian drift while awake and one memory per night, consolidated in
  the first REM episode (a log entry with the sha256 of the weights plus a 1 % weight change);
- a compact **Twin panel** on `/brain` and `/` with the held-out similarity score and its label, neuromodulator bars,
  vitals, sleep pressure, the memories and the drift from the original connectome; every number carries a plain-word
  explanation (text or `title` tooltip) and is labelled as simulated or as a held-out comparison.

The held-out match to the recorded fMRI is **weak and static** (FC r = 0.10 on sessions the fit never saw; it does reproduce
how FC fluctuates over time). The panel says so. Everything, with equations, sources, licences, held-out scores, CPU numbers
and a list of what is still not realistic, is in [`docs/twin_report.md`](docs/twin_report.md) (sections in `docs/twin/`).

```bash
python live_server.py --demo                  # twin model is the default; --model sl (or SUB01_MODEL=sl) = old model
python live_server.py --demo --time-scale 600 --start 23:30   # accelerated night (state in data/demo/)
python -m pytest tests -q                     # includes tests/test_integration.py (headless accelerated night, < 90 s)
OMP_NUM_THREADS=1 python twin/measure_cpu_live.py   # CPU at real time -> twin/data/cpu_live.json (target <= 30 % of a core)
```

Runtime state (`data/`, git-ignored) now also holds `twin_state.json`, `weights.npz`, `memories.json`. The original
`out/connectome.npz` is never written. The Docker image copies `twin/` (with `twin/data` and `twin/params.json`) and
`web/twin_score.json`; no new dependency (numpy, scipy, aiohttp).
