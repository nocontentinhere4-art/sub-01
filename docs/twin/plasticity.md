# Plasticity and one memory a day

Part of a digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious,
not the person. This is a toy version of plasticity, not a model of learning in a real brain.

## Equations
Model-space weights W0 are built like `brain_sim.Brain`: `log1p(streamline counts)`, divided by the mean in-strength.
Edges = pairs with W0_ij > 0 (10,204 undirected edges among 214 regions); no edge is ever created.

Wake only (`hebbian(act, dt, stage)`, a no-op unless `stage == "AWAKE"`):

    dW_ij = eta (a_i - <a_i>)(a_j - <a_j>) dt  -  (dt / tau)(W_ij - W0_ij)      (symmetrised, existing edges only)

a = |activity|; <a_i> is a running mean (time constant 1 h). The second term is a slow homeostatic decay to W0.
After every step: per-edge clip |W - W0| <= c W0 (c = 0.05), then, if ||W - W0||_F / ||W0||_F > 0.02, the deviation is
scaled down to that cap.

Parameters (all unfitted toy values): eta = 1e-9 weight-units per (activity^2 s), tau = 3 days, c = 0.05,
total cap 0.02, consolidation delta = 0.01 (relative), mean time constant 1 h.
Typical edge weight is about 0.010 (max 0.034). For one simulated day (10 s steps) of independent noise-like activity
(0.45 +- 0.1) the Hebbian drift is about 1e-6 (relative Frobenius), far below the caps; correlated real-like activity
gives larger values, still limited by the caps. The caps are what the tests verify, with absurdly large rates.

Rule background: Hebb 1949 (The Organization of Behavior); bounded/normalised Hebbian learning, Oja 1982, J Math Biol
15:267; synaptic scaling, Turrigiano 2008, Cell 135:422. The rule above is not any of these exactly.

## One memory a day
`record_response(t, text, regions, strength)` keeps each accepted chat message's response until the night (persisted
in `data/pending_responses.json`; nothing about the sender is accepted or stored). `consolidate(day)` (call once in
REM) picks the message with the largest strength, multiplies the existing edges among its regions by (1 + 0.01) (inside
the caps), appends `{n, day, message, regions (names), delta, sha256}` to `data/memories.json`, saves
`data/weights.npz`, and calls `publish_hash(record)`. sha256 = SHA-256 of `W.astype('<f4')` C-order bytes after
consolidation. No messages: no memory. `publish_hash` is a documented no-op (no wallets, transactions or network).
One night moves the weights by about 5e-4 (relative Frobenius) and at most 1 % per edge.

## Persistence and safety
`data/weights.npz` holds W, a hash of W0 and the running mean, written atomically (temp file + `os.replace`). If W0
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
