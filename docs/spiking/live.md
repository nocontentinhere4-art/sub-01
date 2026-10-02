# The 1M-neuron network live on GPU through his waking hours (issue #58)

Owner decision (2026-10-02): run the large network, 1M LIF neurons on a RunPod GPU, through his waking hours. It
answers his real choices and learns from what follows. Hard daily caps apply. When the pod is down or over a cap,
the small CPU network of #55 decides instead, and if that is down too, the rate model alone.

**Off by default.** Nothing changes until `SUB01_DAY_LIVE=1` is set on Railway.

Code:
- `spiking/pod_manager.py` (day-live mode);
- `spiking/server.py` (the decision protocol in the hub);
- `spiking/session.py` (phases `live_decide` and `live_bench`, and the night replay of real decisions);
- `spiking/choice.py` (`LiveChooser`).

Small changes elsewhere:
- `spiking/runpod_ops.py`: a GPU list with a cloud type;
- `spiking/podpack.py`: two more allowed GPU types and the cloud type;
- `spiking/costs.py`: `usage_on`, hours and USD split at Tokyo midnight.

Tests are in `tests/test_day_live.py`. The benchmark and validation driver is `docs/spiking/live/run_live_pod.py`,
with `live_pod_host.py`.

## How a day runs

| sleep engine says | for | the pod manager does |
|---|---|---|
| AWAKE | 5 min (`WAKE_CONFIRM_S`) | starts **one** pod with phases `live_decide` + the night phases; it loads the latest learned weights from the server |
| AWAKE | the waking day | the pod runs the network at most at real time and answers `decide` messages; the learned weights go to the server every 30 min |
| NREM / REM | 10 min (`SLEEP_CONFIRM_S`) | sends `night` to **the same pod**: the day's top items (as for the nightly session) and, with `SUB01_CHOICE=1`, the day's real decisions with their outcome |
| asleep | ≤ 45 min | the pod runs recall_yesterday → encode → choice_train (replay of the real decisions) → memory_test → sleep → memory_test, uploads the weights and says done; the pod is deleted |
| asleep | the rest of the night | no pod. A waking at night (before 05:00) starts nothing: that day's night is already done |

- If no day pod ran (it failed, or the server restarted in the evening), a night-only pod runs the night phases
  alone, bounded by 45 min.
- The NREM ↔ REM switches do not reset the 10-min confirmation; only an awake ↔ asleep switch does.
- The sleep engine's stage reaches the manager through `SpikingHub.forward_sleep`, which `live_server.py`
  already calls every tick. **No `live_server.py` change is needed.**

## The decision protocol (shared with #55)

```
server → network  {"type":"decide","id":str,"options":[label,...],"kind":"browse|chess|plan","deadline_ms":int}
network → server  {"type":"decision","id":str,"pick":int,"pool_rates":[float,...],"sim_ms":float,"n_neurons":int}
server → network  {"type":"reward","id":str,"value":float}
server → pod      {"type":"night","day":str,"items":[...],"decisions":[{"options","pick","reward","kind"}]}   (GPU only)
```

### API for `brain_vote` (#55)

```python
d = await live.spiking.decide(options, kind, deadline_ms=2000)
```

- `d` is `None` when no pod is live, or when it has not answered by the deadline. The caller then uses the CPU
  network, then the rate model.
- Otherwise `d` is the decision plus:
  - `"net": "gpu"`;
  - `"label": "1M-neuron network on GPU"`, the text the decision card shows;
  - `"rtt_ms"`.
- `live.spiking.reward(d["id"], value)` forwards the dopamine for that decision. It returns `False` if the GPU did
  not make the decision.

Every GPU decision and reward is logged by the hub to `/data/spiking/gpu_decisions-<Tokyo date>.jsonl`:
- the decision: `{"t","id","kind","options","pick","net":"gpu","pool_rates","sim_ms","rtt_ms"}`;
- its reward, on its own line: `{"t","id","reward"}`.

At sleep onset the manager reads these files together with #55's `/data/spiking/decisions-<Tokyo date>.jsonl`:
- the same shape: decision rows with `options` + `pick`, reward rows with `reward` (or `value`);
- merged by `id`;
- decisions from the waking day only, with an outcome, at most 300.

**#55 should log the GPU's own id for decisions the GPU answered**, so no decision is counted twice.

## On the pod: `live_decide` and the learning rule

- **Cues are real option labels.** The label's first 3 content words are each hashed as in `memory.py`, at 5 % of
  the excitatory neurons of every visual and language parcel; a 3-word label gets about the 15 % cue of #39.
  Labels that share a word share part of their cue.
- **Pools.** For 2–6 options of any text, the striatal neurons are split among the offered labels by hashed
  affinity (as in #39).
- **The race and the eligibility tag** are those of #39.
- **Reward** applies `dw += η_label · δ · tag`, with `δ = value − V[label]`.
- **Stability fix** (`docs/spiking/choice.md`: the learned preference drifted):
  - a slower value estimate, α = 0.05 instead of 0.1;
  - a learning rate that decays with the number of rewards the label has had, `η_label = max(0.15, 0.6 / √(1 + n/20))`.
- `value` can already be a reward-prediction error (the tastes signal) or an outcome (chess). `V` absorbs a
  constant offset either way.
- `V` and `n` per label are saved in the weights' meta, so they survive a new pod.
- **Speed.** The network runs in 20 ms chunks, paced to at most real time. The server's messages are read between
  chunks, so a decision starts at most ~20 ms after it arrives.
- **Uploads.** The weights go up every 30 min in a background thread, and again at the end. A lost pod loses at
  most 30 min of learning.
- **Reconnects.** After a websocket reconnect the pod says `hello` and `live_ready` again, so the hub uses it again.
- **Night.** `choice_train` replays the day's real decisions: the option he really took is tagged as chosen and its
  real outcome is the dopamine. Before and after, frozen, it reports how often the network's own pick agrees with
  the outcomes (`fit_before`, `fit_after`).

## Hard caps (all enforced by the server, each with a log line)

| Variable | Default | What happens at the cap |
|---|---|---|
| `SUB01_DAY_LIVE` | `0` | `1` turns the mode on |
| `SUB01_DAY_MAX_HOURS` | 17 | GPU hours on the Tokyo day (a pod's time is split at midnight). The pod is asked to stop 90 s before the cap (it uploads the weights) and is deleted at the cap at the latest. No pod until the next Tokyo day |
| `SUB01_GPU_USD_PER_DAY` | 14.00 | RunPod's reported $/h for the pod (`costPerHr` at creation) × uptime. Same stop/delete; #55's network decides until tomorrow |
| `SUB01_GPU_HOURS_CAP` | 120 in this mode (8 otherwise) | rolling 7 days; same stop/delete |
| `SUB01_DAY_MAX_RESTARTS` | 6 | a lost pod (no hello in 15 min, stream lost for 3 min, create or upload failure, done with an error) is a failure. The next pod waits 1, 5, 10, 20, 40, 60 min; after 6 restarts no pod until the next Tokyo day |
| `SUB01_GPU_TYPES` | see below | `"type:CLOUD,type:CLOUD"`, tried in order |

Other rules:
- Every pod's cost goes to `/data/spiking/costs.jsonl` as before, so `/api/costs` shows it under `runpod`. Note that
  `/api/costs` books a pod on its start day, while the cap splits it at midnight.
- **Exactly one SUB-01 pod.** Every 10 min, and at startup, any pod named `sub01-spiking-*` that is not the current
  one is deleted as an orphan.
- **"BRAIN" is never touched.** `RunPodOps` re-fetches every pod before a delete and refuses one without our prefix;
  the tests check it.
- `/api/spiking/status` shows `day_live`:
  - the stage and the pod's mode;
  - why the mode is blocked, if it is;
  - restarts today, today's hours and USD, and the caps;
  - `decisions`: whether the pod answers, plus the asked, answered, timed-out and rewarded counts.

## Cheapest GPU that keeps up (measured 2026-10-02)

Viable means a decision within 2 s and the network at ≥ 0.5× real time.

- **Bench pods** ran the `bench` phase, then `live_bench`, with no server:
  - 5 s free-running with the live settings;
  - then 40 decisions among 2–6 random labels, each with a reward and 500 ms between them.
- **The validation pod** ran the full protocol through the real hub (see below).
- All on 1M neurons, 101M synapses, 5.7 GB of GPU memory.

| GPU | cloud | $/h (RunPod) | steps/s free (×real time) | steps/s with decisions | decision wall p50 / p95 / max | plasticity off / STDP on (bench) | verdict |
|---|---|---|---|---|---|---|---|
| RTX A4000 16 GB | community | 0.17 | 1,242 (1.24×) | 1,061 (1.06×) | 78 / 103 / 126 ms | 1,278 / 240 | viable, cheapest |
| RTX A4000 16 GB | **secure** | **0.25** | live: 1.00× (paced to real time) | — | 71 / 306 / 424 ms on the pod; 116 ms p50 at the hub | — | **viable: the default** (validation pod) |
| A40 48 GB | secure | 0.49 | 1,521 (1.52×) | 1,322 (1.32×) | 59 / 82 / 211 ms | 1,493 / 314 | viable, 2× the price |
| L4 24 GB | secure | 0.49 | ~44 (0.04×), build 136 s instead of 3.5 s | — | — | — | **not viable** (stopped after 10 min) |
| RTX A4500 | secure / community | 0.25 / 0.19 | — | — | — | — | no capacity at the time: not measured |
| RTX 4090 | community | 0.34 | — | — | — | — | no capacity at the time: not measured |

For reference, earlier runs (`docs/spiking/gpu*/results.json`) measured plasticity off at:
- RTX A5000: 1,448 steps/s;
- RTX 4000 Ada: 1,353 steps/s;
- A40: 1,266 steps/s.

**Default list (`DAY_GPUS`), cheapest first:**
1. RTX A4000, secure;
2. RTX A4500, secure;
3. RTX A5000, secure;
4. RTX 4000 Ada, secure;
5. A40, secure, the fallback that is usually in stock.

Why secure only: the pod carries `SUB01_POD_SECRET`, and community hosts are third-party machines. The owner can opt
in with `SUB01_GPU_TYPES="NVIDIA RTX A4000:COMMUNITY,..."` (−32 %).

Capacity changes by the minute: two of five attempted types had no instances, and the same A4000 secure that was
full at 14:00 UTC was free at 14:19. The list is tried in order on every start.

**Expected cost:** ~16 h awake + ~0.5 h night ≈ 16.5 GPU-h/day.

| GPU | per day | per 30 days |
|---|---|---|
| A4000 secure, $0.25/h | **≈ $4.1** | ≈ $124 |
| A40, if only that is available | ≈ $8.1 | ≈ $243 |

The $14/day cap is never reached at these prices. 120 GPU-h/week allows 17 h/day.

## Validation run (one pod, from this session)

Raw results: `docs/spiking/live/validate-a4000-secure.json`.

**Setup.** `run_live_pod.py validate` started one RTX A4000 (secure, $0.25/h). On the pod, `live_pod_host.py` ran
the same `SpikingHub` code as Railway on port 8001, and the session's websocket pointed at it. This session sent
the rounds through the RunPod proxy:
- 50 `decide` messages, each among 2–6 labels from a pool of 20 page titles and chess moves, deadline 2 s;
- after each, a `reward`. The synthetic outcome was +1 for options containing tea / moon / park / bread and −0.5
  otherwise, with noise.

Then it waited for a periodic weight upload (every 3 min in this run instead of 30), sent `night` with 3 items and
the 50 decisions, waited for the night phases, and deleted the pod.

| | result |
|---|---|
| boot → pack uploaded | 25 s |
| pack → `live_ready` (build 1M + calibration) | 18 s |
| decisions answered | **50 / 50**, all within 2 s; 0 timeouts, 0 late |
| decision time on the pod | p50 71 ms, p95 306 ms, max 424 ms |
| hub decide → decision (the protocol round trip on the pod) | p50 116 ms, max 479 ms |
| this session → RunPod proxy → hub → back (not the production path) | p50 545 ms |
| rewards accepted | 50 / 50 |
| real time during the live phase | 1.00× (paced) |
| periodic weight upload | 123.6 MB, landed 109 s after the rounds |
| night phases | 175 s (encode, replay of the 50 decisions, memory tests, sleep 2 min sim); 3/3 items recalled after encoding and after sleep |
| final weight upload | HTTP 200, 123.6 MB |
| pod deleted | yes, confirmed gone from the pod list; "BRAIN" still there and untouched |
| cost | **0.115 GPU-h, $0.029** |

**What it does not show.**
- **No learning effect.** In the first 25 rounds where a paying option was on offer the network picked one 18 of
  22 times; in the last 25, 18 of 25. Fifty rounds over 15 labels is far too few to see learning, and many offers
  contained several paying options. The night replay's frozen fit stayed at 0.88 before and after.
- **The race at 1M.** As in #39, 41 of the 50 decisions were taken at the first allowed check (50 ms), because
  large pools have very little rate noise (sd 0.4 Hz). The race is then mostly "which pool is highest at 50 ms". A
  higher `thr_z` (config `live_thr_z`) is the next thing to try; not tuned here.
- **The production network path.** The Railway → pod websocket path was not exercised; the pod's link pointed at a
  hub on the pod itself. The protocol code is the same and is round-trip tested in CI.

## RunPod use in this task

| pod | GPU, cloud | purpose | minutes | GPU-h | cost |
|---|---|---|---|---|---|
| 9fd5htrbozacib | RTX A4000, community | bench | 1.7 | 0.029 | $0.005 |
| 6jjwp4abcb9ges | L4, secure | bench (stopped by hand: too slow) | 10.0 | 0.167 | $0.082 |
| 3gasanrm71i8ms | A40, secure | bench | 1.5 | 0.025 | $0.012 |
| jwmjydyd51km0r | RTX A4000, secure | validation | 6.9 | 0.115 | $0.029 |
| **total** | | | | **0.334** | **$0.127** |

- One pod at a time; each was deleted and confirmed gone.
- Five create attempts were refused by RunPod for lack of capacity (no pod created): A4000 secure (twice),
  A4500 secure (twice), RTX 4090 community.
- The pod named "BRAIN" was never touched.
- Cost log: `docs/spiking/live/costs.jsonl`.

## Owner actions after merge

Set these on Railway:
1. `RUNPOD_API_KEY` (done, per the owner).
2. `SUB01_POD_SECRET`: a long random string.
3. `SUB01_DAY_LIVE=1`.
4. `SUB01_CHOICE=1`, so the night replays the day's real decisions.

Optional:
- `SUB01_GPU_USD_PER_DAY`;
- `SUB01_GPU_TYPES`, for example to allow the community cloud.

Check after deploy:
- the logs say `day-live mode on`, then `day pod … started` within ~5 min of his waking;
- `/api/spiking/status` → `decisions.live_ready` is true;
- `/api/costs` → `runpod` grows by ≈ $0.25 per hour.
