# Plasticity and one memory a day

Part of a digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious,
not the person. This is a toy version of plasticity, not a model of learning in a real brain.

## Equations
Model-space weights W0 are built like `brain_sim.Brain`: `log1p(streamline counts)`, divided by the mean in-strength.
Edges = pairs with W0_ij > 0 (10,204 undirected edges among 214 regions); no edge is ever created.

Wake only (`hebbian(act, dt, stage)`, a no-op unless `stage == "AWAKE"`):

    dW_ij = eta (a_i - <a_i>)(a_j - <a_j>) dt  -  (dt / tau)(W_ij - W0_ij)      (symmetrised, existing edges only)

a = |activity|; <a_i> is a running mean (time constant 1 h). The second term is a slow decay to W0 (its factor
dt/tau is clipped at 1). The decay also fades consolidated memories (time constant tau, during wake only).
Non-finite activity, wrong shape, or dt <= 0 / non-finite are ignored (no update).
After every step: per-edge clip |W - W0| <= c W0 (c = 0.05), then, if ||W - W0||_F / ||W0||_F > 0.02, the deviation is
scaled down to that cap.

Parameters (all unfitted toy values): eta = 1e-9 weight-units per (activity^2 s), tau = 3 days, c = 0.05,
total cap 0.02, consolidation delta = 0.01 (relative), mean time constant 1 h.
Typical edge weight is about 0.010 (max 0.034). For one simulated day (10 s steps) of independent noise-like activity
(0.45 +- 0.1) the Hebbian drift is about 1.1e-6 (relative Frobenius; max per edge 3.4e-5), far below the caps.
With the spatial correlations of the recorded resting-state runs (activity 0.45 + 0.1 z, z = the `out/rest` time
series, cycled frame by frame) one day gives about 2.2e-5 (max per edge 2.2e-4); with 0.45 + 0.3 z about 1.7e-4
(max per edge 1.8e-3). The 1 s and 10 s step sizes give the same drift within 10 %. One `hebbian` call costs
about 1 ms (214 regions), so it should be called every 1 to 10 s of model time, not at every integration step. The caps are what the tests verify, with absurdly large rates.

Rule background: the first term is the covariance Hebbian rule (Hebb 1949, The Organization of Behavior; Sejnowski
1977, J Math Biol 4:303). Hard per-edge and total bounds are used instead of the weight normalisation of Oja (1982,
J Math Biol 15:267), which is not implemented. The decay to W0 is only loosely inspired by homeostatic synaptic
scaling (Turrigiano 2008, Cell 135:422), which is multiplicative and set by activity, unlike this term.

## One memory a day
`record_response(t, text, regions, strength)` keeps each accepted chat message's response until the night (persisted
in `data/pending_responses.json`; nothing about the sender is accepted or stored). `consolidate(day)` (call once in
REM) picks the message with the largest strength, multiplies the existing edges among its regions by (1 + 0.01) (inside
the caps), appends `{n, day, message, regions (names), delta, sha256}` to `data/memories.json`, saves
`data/weights.npz`, and calls `publish_hash(record)`. sha256 = SHA-256 of `W.astype('<f4')` C-order bytes after
consolidation. No messages: no memory. `publish_hash` is a documented no-op (no wallets, transactions or network).
One night moves the weights by about 5e-4 (7 regions) to 1.1e-3 (the 14 left temporal / frontal-operculum
"language" parcels) relative Frobenius, and at most 1 % per edge. At most one memory per `day`: a second call for a
day that already has a record returns None and keeps the pending messages for the next night. Region indices must be
in 0..n-1 (else ValueError); a non-finite strength counts as 0.

## Persistence and safety
`data/weights.npz` holds W, a hash of W0, the running mean, the last memory record and the ids of the messages it
consumed, written atomically (temp file + fsync + `os.replace` + directory fsync). In `consolidate` it is written
first and is the commit point; if the process dies before `memories.json` / `pending_responses.json` are updated, the
next start finishes those writes (the record is appended, the consumed messages are dropped), so the log and the
weights cannot disagree. Pending messages carry only a random id, time, text, regions and strength. If W0
changes (different connectome) the weights restart from the new W0 and the old memory log is renamed aside.
`reset()` returns exactly W0 (the memory log is kept as history). `out/connectome.npz` is only read; a test checks its hash.
`drift()` -> `rel_frobenius`, `edges_changed` (undirected), `max_edge_rel`.

## Limitations (what is not realistic)
- Weights are group-normalised streamline-count proxies, not synaptic strengths; Hebbian change of fibre-bundle
  weights over a day is not a biological claim.
- Rates and caps are chosen to be tiny and safe, not fitted; no spike timing, no neuromodulation, no sleep-dependent
  downscaling beyond the decay.
- "Winning message" = largest model response; the memory is a hash-stamped log entry plus a small weight change, not
  recollection. Edges are symmetric although real pathways are not.
- Persistence is local files only; durability depends on the server's disk.
