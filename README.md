# SUB-01

A whole-brain model of one real human brain, built from public MRI data and wired to live Solana trades.

- **Data:** MyConnectome, OpenNeuro [ds000031](https://openneuro.org/datasets/ds000031) (public domain, PDDL). Raw scans are never stored here; the scripts download what they need.
- **Real parts:** nerve-fibre tractography (diffusion MRI), cortical surface (T1), recorded resting-state activity (fMRI).
- **Simulated part:** region-to-region dynamics in two layers on the subject's connectome: a slow (BOLD-band) Hopf layer
  fitted on half of the subject's resting-state runs and tested on the other half, which modulates a fast ~10 Hz
  delayed Stuart-Landau layer used for the live display. How much of the result comes from the wiring itself, compared
  with randomised wiring, is reported in [docs/real_wiring_report.md](docs/real_wiring_report.md).
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

## Real wiring: connectome v2 and the slow layer

| Step | Script | Output |
|---|---|---|
| ACT tissue map from the T1 (tried, not used: it truncated streamlines) | `analysis/make_5tt.py` | (pod input) |
| MRtrix3 tractography on a RunPod pod (gradient check, msmt-CSD, iFOD2, SIFT2) | `analysis/runpod_job.py` + `analysis/pod/tract.sh` | `data/analysis/connectome_v2_raw.tar.gz` |
| Consistency threshold, lengths, centroids | `analysis/build_connectome_v2.py` | `out/connectome_v2.npz` (v1 `out/connectome.npz` kept) |
| Hopf slow layer: fit on half of the runs, test on the other half, 100 + 100 nulls | `analysis/real_wiring.py prep / nulls / run / report / export` | `docs/real_wiring/`, `twin/data/slow_layer.npz` |
| Old quick checks (reconstructed) | `analysis/null_test.py`, `analysis/hopf_test.py` | |

Pods follow fixed rules (`analysis/runpod_job.py`): only CPU or RTX A5000 pods, one at a time, deleted on finish, error or
60 min, 2 h in total, every pod logged in `data/analysis/costs.jsonl`; pods it did not create are never touched.
`live_server.py` runs the fitted slow layer by default (`SUB01_SLOW=wiring` uses the wiring-only version);
`--replay-real-session` replays a recorded session instead (the previous default).

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
