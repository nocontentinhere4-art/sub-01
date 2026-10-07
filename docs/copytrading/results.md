# Synthetic validation — 2026-10-07

This is a deliberately constructed task, not real market data or a Fomo backtest.
Three observed trader signals have noisy fixed-horizon returns; alpha is best for the
first 50 rounds and charlie for the last 50. Fees and adverse slippage apply to every
hypothetical copy. All prospective outcomes are observed, even when not copied.

External controller, 12 random seeds x 100 rounds: it chooses the new best trader in
96.25% of the final 20 rounds on average. It outperforms the fixed/random policies on
this constructed fixture. This is primarily evidence for the **external recent-return
controller**, not native brain intelligence or a return expectation in markets.

The 20k/40k/80k diagnostic is a different, existing rewarded-choice task. Averaged over
three wiring seeds (100 trials each), learned correct choices were 64.33%, 65.00%,
68.67%; frozen twins 37.33%, 31.33%, 33.67%. The outcome varies by seed: on seed 2,
40k was worse than 20k. More neurons do not reliably improve every instance.
This experiment does not validate 100k/500k targets; those are the owner's requested
resource profiles. Native integration results with current hashed trader cues are in
`analysis/copytrade-native-validation.json`; they do not isolate incremental native benefit.

Committed sources, raw summaries and fixture:
- `analysis/copytrade_benchmark.py`
- `analysis/copytrade-controller-validation.json`
- `analysis/copytrade-native-validation.json`
- `analysis/copytrade-neuron-validation.json`
- `docs/copytrading/synthetic-feed.jsonl`

Tests cover invalid data, no lookahead, costs, missing/stale prices, delayed exits,
open-position limits, regime reversal, actual-followed native credit, exact-once reward,
restart with an open trade, distinct wallet cues, CPU/GPU size boundaries, and preserving
old learned checkpoints when changing network size. No paid GPU was started. No live
funds, account, wallet or Fomo connection was used. Full-suite results are recorded in
the pull request rather than inferred from these benchmark outcomes.
