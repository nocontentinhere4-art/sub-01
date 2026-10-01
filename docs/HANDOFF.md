# SUB-01 — handoff for new sessions (state on 2026-10-01)

Read this first. It replaces the local memory that cloud sessions cannot see.

## What SUB-01 is now
- A whole-brain model built from one real person's public MRI (MyConnectome, OpenNeuro ds000031, PDDL):
  real tractography fibres, real cortex, his real resting-state recordings.
- It "lives" as a **fictional young man in a Tokyo room** (Kichijoji). The character is invented and must never
  resemble, name or speak as the real scanned person. Never claim consciousness or that it is alive.
- Live on Railway (`sub01-production.up.railway.app`, behind `SITE_PASSWORD`), auto-deploys from `main`.
- Memecoin context: no financial advice, no buy pressure, no wallets or on-chain actions without explicit approval.

## Pages (all on `main`)
| path | file | what |
|---|---|---|
| `/` | `web/room.html` | his room in 3D (Higgsfield/Meshy GLBs in `web/room/`), map of Kichijoji when he is out, reading card, mini brain |
| `/brain` | `web/index.html` | brain v2: full-screen real fibres coloured by sleep stage; chat messages travel along real fibres; `?mini` for the PiP |
| `/diary` | `web/diary.html` | dream diary written each morning (Tokyo) from unattended REM frames |
| `/world.html` | eye frames | what the eye (Replicate FLUX + Llama 3) "sees" |

## Runtime modules
- `brain_sim.py` (10 Hz delayed Stuart-Landau), `real_baseline.py` (replays his fMRI as drive), `sleep.py` (Asia/Tokyo),
  `chat.py` (filter), `eye.py` (Replicate), `diary.py`, `life.py` (needs-based life: research at the computer,
  order_food → simulated courier on a real OSM bike route, get_delivery, bakery/park outings with real routes),
  `research.py` (Wikipedia-only curiosity chain, sensitive topics skipped), `live_server.py` (aiohttp; pages served
  with `Cache-Control: no-cache`; `/api/diary`, `/api/reading`, `/api/frames`).
- `Dockerfile` must copy every runtime module (currently also `diary.py research.py`).

## Science status (be honest on the site)
- The old public "r = 0.40" came from replaying his recorded fMRI as drive; with no coupling at all it is 0.45.
  Never present it as "his wiring produces his activity" (`analysis/null_test.py`).
- PR #5 (`feature/real-wiring`): connectome v2 (MRtrix3 + SIFT2) and a wiring-only Hopf slow layer reach FC r ≈ 0.21
  on held-out sessions, beat strength-preserving nulls, borderline vs geometry-preserving nulls. **Merge this.**
- PR #4 (`feature/digital-twin`): weaker fit (0.10), overlaps PR #5; do not merge as is (salvage receptor maps
  under CC BY 4.0, the sleep circuit, the body model later).
- `feature/spiking-brain` (no PR yet): 1M LIF neurons stable on an RTX 4000 Ada; memory recall 5/5 works and REM replay
  strengthens cortex; **Pong does not learn** (17.5 % vs 25 % no-plasticity control) — say so if shown.
- PR #3 (brain-city "construct") is superseded by the room.
- `netneurolab/hansen_receptors` is CC BY-NC-SA → not usable.

## When merging PR #5 into main, keep from main
- `web/index.html` brain v2 (add the slow-layer label to its status line; it reads `m.baseline` — when the
  recording replay is off, show the slow layer and its held-out r next to what randomised wiring reaches).
- `/` → `room.html`, `/diary`, `/api/diary`, `/api/reading`, the `run_research` task, `NOCACHE`, the diary hooks in
  `run_eye`, `SOLANA_WS` + RPC backoff.
- Dockerfile copies `diary.py research.py` plus whatever the slow layer needs (`twin/`, `out/connectome_v2.npz`).

## Hard rules
- No secrets in git or logs; keep the password gate; skull-stripped T1 only (no face).
- RunPod: max 1 pod per task, delete on finish/error/60 min, log costs, never touch the pod named "BRAIN".
- No heavy compute on the user's Mac (it overheats): use cloud sessions or RunPod.
- Higgsfield credits are the user's: preflight with `get_cost` and confirm big spends.
