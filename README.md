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
| Live page + model + Solana log stream | `live_server.py --mint <MINT>` or `--demo` | http://localhost:8765 |

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
./fetch_data.sh   # ~900 MB from OpenNeuro into data/ (git-ignored)
```

## Resting-state activity (real recorded brain activity)

`process_rest.py N` streams the first N of the 132 resting-state runs listed in `rest_runs.txt`
from OpenNeuro, keeps a region x time series per run in `out/rest/` (~240 KB each) and deletes
the raw file. It only needs `out/labels_t1.nii.gz` and `out/t1_brain_1mm.nii.gz` (skull-stripped,
committed), so it runs on a fresh clone: `pip install -r requirements.txt && python process_rest.py 132`.
Sanity check on run 1: homotopic (left/right) correlation 0.52 vs 0.22 for all pairs.
