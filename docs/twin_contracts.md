# SUB-01 v2 digital twin — interface contracts (shared by all component branches)

Every component is built on its own branch off `feature/digital-twin` and merged back there.
Keep to these interfaces so the pieces fit; if you must change one, say so in your final summary.

Wording rule for every file, comment, doc and page string: this is *a digital twin model of one real
person's brain structure and recorded activity; not a mind, not conscious, not the person*. Never name the
MyConnectome participant or write as if speaking for them. No financial advice in any generated text.

Data (read-only, never modify): `out/connectome.npz` (weights = streamline counts, lengths in mm, 214 regions:
Schaefer-200 7-network + 14 Harvard-Oxford subcortical), `out/atlas_names.json`, `out/rest/*.npz` (`ts` T x 214
z-scored, detrended, band-passed 0.01-0.1 Hz, no nuisance/global-signal regression; `tr` from the BIDS sidecar),
`out/rest/qc.json` (`kept` flag). Runtime state lives in `data/` (git-ignored); small committed results in
`twin/data/` and `web/`.

Runtime budget: the live server (Railway, one shared CPU) must run the model at real time with <= 30 % of one core.

## twin/model.py — `TwinBrain` (owner: model branch)
Drop-in for `brain_sim.Brain` (same public interface; `live_server.py` must keep working unchanged):
- attributes: `names, n, W (model-space weights, n x n), centroids, group_idx (same groups as brain_sim + "language"),
  dt, t, stim, drive`; `a` is settable (sleep engine writes `b.a = p["a"]`) and maps to a documented excitability offset.
- `stimulate(group, amount)`; `step(k=1) -> x` where `x` is a real float array (n,) and `np.abs(x)` is a display
  activity in roughly [0, 2] (baseline ~0.3-0.6, like the old amplitude) and `x` itself is an oscillating signal
  (`wave` on the page uses `x.real`); `run(seconds, every)`; `state() -> {group: mean activity, "sync": 0..1}`;
  `set_rhythm(f_hz, coupling=1.0, noise=None)` (coupling multiplies G, noise sets noise; f_hz may be ignored or mapped —
  document it).
- new: `set_gain(g)` — per-region multiplicative gain vector (n,), 1.0 = fitted resting baseline (used by neurochem);
  `set_weights(W)` — replace model-space weights (used by plasticity; same normalisation space as `self.W`);
  `W0` — the original model-space weights built from `out/connectome.npz`; `bold()` — current simulated BOLD (n,).
- constructor loads fitted parameters from `twin/params.json` when it exists (else documented defaults);
  `TwinBrain(params=dict)` overrides.
- fast offline path for fitting: a batched simulator (several parameter sets at once, no Python per-region loops)
  returning BOLD sampled at a given TR, e.g. `simulate_bold(params_list, seconds, tr, seed, W=None) -> (B, T, n)`.
`brain_sim.make_brain(kind="twin"|"sl", **kw)` factory; env `SUB01_MODEL` picks the default (`twin`).

## twin/neurochem.py (owner: neurochem branch)
- `RECEPTORS`: per-region densities (n=214 in `atlas_names.json` order, z-scored or 0..1, documented) for the maps used.
- `Neuromodulators` with levels `{"DA","5HT","NE","ACh"}`, 1.0 = resting-wake baseline.
  `on_trade(kind, usd, t)` (pumps -> phasic DA as a reward-prediction error vs the running expectation, not price level;
  dumps / volatility -> NE), `update(dt, sleep_levels=None) -> levels` (tonic levels follow `sleep_levels` from the
  sleep engine, phasic parts decay), `region_gain(levels) -> (n,)` gain vector, exactly 1.0 everywhere at baseline levels
  (so the resting fit stays valid), bounded (e.g. 0.5..1.5).

## sleep.py — `SleepEngine` (owner: sleep branch)
Keep the public interface, persistence (`to_dict/from_dict`, `Store`, night files) and live_server usage unchanged.
`params` keeps the keys `f_hz, coupling, noise, a, gain` (old model still works). Add `modulators` -> `{"DA","5HT","NE","ACh"}`
(1.0 = resting wake; REM: ACh high, NE/5-HT low; NREM: all lower) and `pressure()` / `status()` exposing H (homeostatic),
C (circadian) and the flip-flop state. Clock is Asia/Tokyo (`SUB01_TZ`).

## twin/body.py (owner: body branch)
`Body(state=None)`; `update(dt_sim, levels, amygdala=0.0, stage="AWAKE")`; `eat(carbs_g)`; `vitals() -> {"hr_bpm",
"resp_per_min", "glucose_mg_dl"}`; `hunger` in 0..1 from glucose; `intero_drive() -> {group: amount}` for
`brain.stimulate` (insula = `SalVentAttn_FrOperIns` parcels; the atlas has no hypothalamus - document the proxy);
`to_dict()`. `life.py` takes hunger from the body instead of its own rule and calls `body.eat` when it eats.

## twin/plasticity.py (owner: plasticity branch)
`Plasticity(W0, data_dir)`: bounded Hebbian update during wake `hebbian(act, dt)` (tiny, capped per edge and in total),
`record_response(t, text, regions, strength)` for each accepted chat message, `consolidate(day)` in REM ->
strengthens edges among the winning message's regions by a fixed amount, appends `{day, message, regions, delta,
sha256}` to `data/memories.json` (sha256 of the float32 C-order weight bytes after consolidation), `drift()` vs `W0`,
`reset()` back to the original, `W` persisted in `data/weights.npz`. Never touches `out/connectome.npz`.
`publish_hash(record)` is a no-op hook (no wallets, no transactions).

## Fit results (owner: fit branch)
`twin/params.json` (fitted parameters), `web/twin_score.json` (held-out scores + baselines + provenance),
figures in `docs/twin/`, a report section `docs/twin/fit.md`.

Each branch writes its own report section in `docs/twin/<component>.md` (sources, licences, equations, what is not
realistic); they are assembled into `docs/twin_report.md` at the end.
