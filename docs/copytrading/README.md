# SUB-01 learns whom to copy — paper experiment

A trader's new buy is an observation, not an order. SUB-01 chooses among up to five
observed traders and cash, tracks the fixed-horizon outcome, and changes its preferences
from the results. All execution is **paper-only**. There is no Fomo API integration,
account creation, wallet, signing, withdrawal, or transaction submission in this change.

## Brain profiles

The owner's requested sizes are explicit in `spiking/profiles.py`:

| Task | Target | Execution |
|---|---:|---|
| Simple daytime choices | 100,000 | Existing isolated CPU child; reduced idle pulse (10 ms instead of 50 ms) |
| Copy-trading experiment | 500,000 | Torch LIF + native striatal chooser on CUDA |
| Existing nightly / day-live GPU sessions | 1,000,000 | Existing manager and budget caps; not changed |

The trading CLI defaults to 500k. A trading-sized network is rejected on CPU before
allocation. There is no silent 20k/40k fallback masquerading as 500k. `--controller-only`
is explicitly external-only; smaller native networks require `--diagnostic-small-network`.
The profiles are separate networks, not a seamless resizing of one synapse set. The
current GPU day-live mode still uses 1M; this satisfies the trading minimum but does
not automatically switch between sizes based on room activity. The paper CLI is a
separate experiment, not a new activity already executing on his room computer.

Changing the CPU default from 20k to 100k cannot transplant existing learned synapses.
Before writing a new checkpoint, `LiveBrain` preserves an incompatible checkpoint as
`live_weights.npz.incompatible-<content hash>`. The new network starts fresh. To roll
back CPU size use `SUB01_SPIKING_LIVE_NEURONS=20000` and restore the retained checkpoint
with the service stopped. No cloud configuration or paid pod was changed by this PR.

## What learns

Two explicitly separate mechanisms:

1. **External reputation memory.** Observe prospective fixed-horizon paper returns
   for all eligible signals, including signals not copied. Keep the latest 20 returns
   per trader. Score mean net return minus an uncertainty penalty. Explore boundedly
   during cold start and occasionally afterward. Cash is a genuine alternative.
   This reduces selection bias and lets the learner adapt after a regime reversal.
2. **Native spiking learning.** Distinct hashed all-letter cues for each trader drive
   visual/language populations. Striatal pools provide a bounded preference added to
   the external score. The settled return, normalized and compared with the prediction
   captured at entry, produces a simulated reward prediction error. It updates the
   cue-to-striatum weights tagged at the original decision, for the option actually
   followed. It is not an LLM narration or an attribution to the most recent decision.

The native term is deliberately small (`native_weight=.001`). The external controller
accounts for most of the measured adaptation. We have **not established an incremental
performance benefit from native spiking learning**, or that more neurons improve this
trading task. These mechanisms are not evidence of consciousness or market profitability.

Identifiers retain identity after the native word tokenizer removes numbers: e.g.
`wallet123` and `wallet456` become different deterministic alphabetic hashed cues.
Invalid delayed rewards no longer consume valid native eligibility; duplicate settled
rewards do not learn twice. At most four open trades fit within the native pending limit.

## Input and accounting

Strict chronological JSONL, globally unique event IDs; timestamps in Unix seconds or
a clearly synthetic relative clock. Every event labels its source `observed` or
`synthetic`. One run cannot mix the two. Never add future prices to an offer.

```json
{"id":"q1","t":0,"type":"quote","source":"synthetic","prices":{"A":100}}
{"id":"o1","t":1,"type":"offer","source":"synthetic","signals":[{"trader":"alpha","asset":"A","side":"buy"}]}
{"id":"q2","t":61,"type":"quote","source":"synthetic","prices":{"A":110}}
```

A buy observation requires a previously observed quote at most 15 seconds old.
Entry and exit use adverse 30-bp slippage and 20-bp fee per side. Start with 1,000 paper
units, use at most 100 per position, at most four positions, never borrow or go short.
Fixed hold is 60 seconds. Exit only at the first newly supplied quote for that asset
at/after the deadline; late exits record their delay. Missing quotes leave positions
unresolved, valued at **cost**, not marked as wins. `balance_at_cost` is not market equity.
Price quotes are assumed executable; liquidity, order size impact, MEV, transaction
failure, data latency and rug mechanics are not modeled. This is not an exchange backtest.

The importer rejects NaN/Inf, zero/negative prices, duplicate IDs, duplicate traders,
unknown event types, out-of-order timestamps, sells and malformed identifiers.
Malformed imports fail before decisions or snapshot publication. All choices, observed
returns, costs, native preferences and updates can be reconstructed from the source journal.

## Run

On a CUDA worker with this checkout and numpy + torch:

```bash
python -m copytrading --feed observed-feed.jsonl --data-dir /data
```

This selects the 500k trading profile. It does not acquire a GPU or contact any service.
To exercise accounting and external adaptation without a GPU:

```bash
python -m copytrading --controller-only --feed docs/copytrading/synthetic-feed.jsonl --data-dir data/paper-demo
```

A tiny native diagnostic (not a 500k validation):

```bash
python -m copytrading --neurons 5000 --diagnostic-small-network --feed docs/copytrading/synthetic-feed.jsonl --data-dir data/paper-small
```

Supply strictly new events to append:

```bash
python -m copytrading --resume --feed next-events.jsonl --data-dir /data
```

The atomic snapshot contains the complete source journal, configuration, implementation
hash (including wiring and runtime versions), feed hash and report. Restart reconstructs
both native learning and outstanding eligibility by replaying the journal from its
initial state. It does **not** load weights while losing the associated pending trades.
Only resume matching configurations/implementations. Reconstruction must reproduce
previously published decisions and closed outcomes or the snapshot is not replaced.
CPU determinism is tested; CUDA replay is not yet verified on hardware and may fail this
check because GPU reductions can vary. Replay cost grows with history (10k-event cap).
A non-blocking file lock permits only one importer at a time.

`GET /api/copytrading` is behind the existing site's password gate. It returns an off
state until a snapshot is written to that server's data directory. It exposes a **snapshot**,
not a running account, with the latest 100 rows and total counts. There is no HTTP import
or execution endpoint, no automatic trading loop and no visual room modification.

## Validation

- `python -m pytest -q tests/test_copytrading.py tests/test_spiking_live.py`
- Constructed reversal, external controller vs fixed/random/cash, 12 seeds:
  `python analysis/copytrade_benchmark.py --output analysis/copytrade-controller-validation.json`
- Tiny/medium native integration diagnostic, 3 seeds:
  `python analysis/copytrade_benchmark.py --native --output analysis/copytrade-native-validation.json`
- Earlier 20k/40k/80k neuron diagnostic on the existing choice task, 3 wiring seeds x
  100 trials x 3 sizes, each compared with its frozen twin:
  `python analysis/copytrade_benchmark.py --neurons --output analysis/copytrade-neuron-validation.json`

All saved benchmark data are **synthetic**, with a deliberately imposed profitable
trader and a reversal halfway through. Their returns must not be marketed as real
performance. The GPU adapter's actual-followed credit is tested on a 5k CPU diagnostic;
500k CUDA operation and the 100k deployment's sustained server cost remain to validate
on the target infrastructure. Existing paid GPU limits are unchanged.
