# His active neurons inside the 3D brain (#62)

> Simulated spiking neurons (1M on GPU / 20k on CPU) inside the real wiring of one person's brain; each dot stands
> for a sampled model neuron; a model, not a mind.

## What the viewer sees
- `/brain`: a fifth layer button, **neurons** (fibres · cortex · regions · science colours · neurons). On phones the
  layer row is now shown too (without "science colours").
- With a live spiking network, ≤ 20 000 points (12 000 on screens under 600 px, 8 000 in the mini) sit inside the brain: each region gets as many points as the 20k CPU
  network has neurons there (`web/neurons3d.json`), placed just under its parcel of the real cortex mesh
  (`cortex.bin`, nearest region centroid) or, for the 14 subcortical nuclei, in a small cloud around the centroid.
  - a recorded spike flashes its point (a short glow, ~0.35 s fade), played back over the time to the next frame as it
    was spread over the frame;
  - the region's spike rate tints its cloud (blue-grey → orange);
  - while a decision race runs, the striatum (caudate, putamen, accumbens: the action pools) is highlighted;
  - the caption says which network is live, how many of the frame's recorded spikes are shown (or, when the 3 KB/s
    budget left a frame without spikes, "N spikes recorded, none sent"), and the sentence above.
- With no live network the button reads **neurons offline** and the caption says "neurons offline — the 1M network runs
  while he is awake when the GPU is on". Nothing flashes: there is no demo or recorded stream on the server.
- `/brain?mini&neurons=1` (the room's picture-in-picture iframe, 300 × 225): the same layer, 8 000 points, a one-line
  caption at the top. **Room follow-up (after #63):** change the iframe's `src` in `web/room.html` from `/brain?mini` to
  `/brain?mini&neurons=1`; nothing else is needed. A room that draws its own brain can instead call
  `Neurons3D.create({THREE, scene, nodes, cortex, sizes})` (`web/neurons3d.js`, works with r128 and r169).
- `/life` (`web/life.html`) and `/brain`: the Neurons panel (`web/neurons.js`) reads the compact frames; its raster now
  has one row a region (214) and shows the sampled spikes. It also lists the real decisions per Tokyo day from
  `/api/spiking/status` → `learning` (#70): picks that paid off per network, and the night replay's learned vs frozen
  twin agreement, as measured.
- Drawing: one `THREE.Points` draw call, attributes uploaded only when spikes arrive and the layer is on; the page
  draws nothing while the brain is off screen (IntersectionObserver, now for the full page too) or the tab is hidden.

## Stream (`spiking/frames.py`)
Both networks' `{"type": "spiking"}` frames are made compact before any viewer gets them:

| field | what |
|---|---|
| `n3.rq` | base64, 1 byte a region (214 → 288 chars): spike rate, log scale 0.1–100 Hz (byte 0 = below 0.1 Hz) |
| `n3.sq` | base64, 3 bytes a spike: region index, neuron slot 0–255 in the region, time 0–255 of `span`; ≤ 400 a frame |
| `n3.span`, `n3.ns` | simulated ms the frame covers; spikes recorded in it (before the sample) |
| `n3.race` | a decision race is running (CPU: phase `deciding`; GPU: a `decide` pending in the hub, or < 1 s ago) |

- CPU network (`spiking/live.py`, frame builder only): records every neuron's spikes (row = neuron id; the network
  itself is unchanged), measures per-region rates, packs a uniform sample of ≤ 400 spikes.
- GPU network (`spiking/server.py`, `spiking/session.py`): the session's `frame()` adds `"rq":
  frames.quantise_rates(rr)` (the per-region rates it already measured); the hub turns the pod's `raster.spikes` (200
  rows, one neuron a region) into `n3.sq`, which region and slot each row is coming from `frames.gpu_sample(n_neurons)`,
  the same draws as `net.enable_raster`. A pod built before this change sends no `rq`: the page then tints each region
  by its network group's rate and says so.

### Per-viewer budget (`frames.Budget`, one on the server)
A token bucket of 3 000 B/s (burst 1 500 B) over both networks, as the server serialises each frame:
- the panel's numbers (n_neurons, t_sim, spikes_per_s, mean_rate_hz, realtime_x, groups, dopamine) at most once a
  second (and on a phase change); the frames between carry type, net, live, phase, raster t0/t1, n3;
- the spike sample is cut to the bytes left (evenly over the frame);
- the CPU network's frames are dropped while the GPU network streams (the panel already showed the GPU's then);
- the room's lite feed (`/ws?rate=5&lite=1`) no longer gets spiking frames at all (it never drew them; its mini brain
  is the `/brain?mini` iframe with its own socket).

Before: every viewer, room included, got the full raster JSON: 4–12 KB a CPU frame while deciding, up to ~36 KB a GPU
frame (4000 spikes), ~9–40 KB/s.

Measured (`tests/test_neurons3d.py::test_stream_per_viewer_under_3_kb_s`, a real `/ws` socket, bytes as
`tests/load_ws.py` counts them; `-s` prints them):
- CPU network deciding nonstop at 5 frames/s for 30 s (worse than real: it decides ~0.3 s a page): **3 030 B/s**,
  606 B a frame;
- GPU network at the hub's 4 frames/s for 30 s, 4000-spike frames in: **2 987 B/s**, 126 of ~405 recorded spikes shown a frame;
- room (lite feed): 0 B/s of spiking frames.

## Honesty
- Every flash is a recorded spike of a model neuron, sampled; every tint is a measured rate (or, from a pod without `rq`, its network group's
  measured rate, labelled). With no frames the layer is off and says offline.
- The recorded stream in `tests/neurons3d_shots.py` (real frames of the 20k CPU network recorded in the test process)
  is replayed by the test into the page's socket handler for screenshots and FPS only; the server never serves it.
- Wording: "a model, not a mind"; nothing says he understands, feels, is conscious or alive.

## Checks
- `pytest tests/test_neurons3d.py`: quantise/dequantise round trip (within half a step, ~1.4 %), spike packing round
  trip, the GPU sample rebuilt exactly as the network draws it, the 20k layout of `neurons3d.json`, compact CPU frames,
  the budget on `/ws`, the lite feed, the offline state (nothing sent; pod gone → `live: false`), the race flag, the
  page's caption and offline sentence word for word.
- `python tests/neurons3d_shots.py --out docs/screens/neurons3d`: screenshots (1280 and 390 px, offline and live, the
  mini) and the FPS / main-thread numbers under ×4 CPU throttle (`docs/screens/neurons3d/results.json`).

### Measured (2026-10-02, this sandbox: headless Chromium, WebGL in software via SwiftShader, no GPU)
- Main-thread cost of the layer under ×4 CPU throttle (20 000 points): building the clouds 119–232 ms once (when the
  toggle is first switched on), 0.08–0.12 ms per incoming frame, 0.011–0.014 ms per rendered frame.
- FPS under ×4 throttle at 390 px, fibres and cortex hidden: 10.9–15.9 with neurons off, 7.4–10.0 with neurons on.
  These are SwiftShader numbers: the sandbox rasterises on the throttled CPU and does not reach 30 even for an empty
  scene, and the existing fibres alone draw at < 1 frame/s here. **The ≥ 30 FPS phone check still needs a real device
  (or a machine with a GPU)**; the layer's own JS cost (~0.01 ms a frame) is not what would stop it. Mitigations in
  place: 12 000 points under 600 px, one draw call, no uploads while hidden, nothing drawn off screen.
- Server: `python tests/smoke_demo.py --measure 30` tick 5.6 ms CPU per 50 ms tick on this branch and 5.6 ms on main;
  the CPU child between decisions 1.2 % of a core (main 1.6 %).

## Real neuron shapes: close-ups (#78)
> Shapes are real reconstructed neurons from public databases and are illustrative: the simulated network uses point
> neurons (no dendrites are simulated). Pulses are slowed down to be visible.

- **Cells** (`web/neurons_morph.json`, 61 KB, built by `analysis/build_morphologies.py`; credits in
  `docs/spiking/morphology_credits.md` and on `/about`): five real reconstructions from NeuroMorpho.Org, CC BY 4.0,
  each simplified to ≤ 300 segments (axon and dendrites get separate shares of the budget; shortest terminal branches
  pruned first, then Ramer–Douglas–Peucker), soma at the origin, pyramidal apical dendrite turned up, Purkinje fan in
  the x–y plane. Human where the database has a usable cell:
  | drawn as | cell | species, region |
  |---|---|---|
  | pyramidal | NMO_107146 (Tamas; Molnár et al. 2016) | human neocortex L2/3, dendrites + axon complete |
  | basket interneuron | NMO_107145 (Tamas; Molnár et al. 2016) | human neocortex L2/3, dendrites + axon complete |
  | medium spiny | NMO_10032 (Spiga; Spiga et al. 2005) | rat nucleus accumbens shell (no human MSN in the database) |
  | thalamic relay | NMO_115363 (Markram; Iavarone et al. 2019) | rat VPM (no human relay cell) |
  | Purkinje | NMO_307495 (D'Angelo; Masoli et al. 2024) | human cerebellum (no axon reconstructed) |

  None of them is from the scanned person; no data of that person exist at this scale. The Allen Cell Types archive
  (its own terms) is not used. NeuroMorpho.Org was accessed only through its API and direct .swc links with a named user
  agent, as its terms ask; the downloads are cached in `data/morph_cache/` (not in git).
- **Levels of detail** (`web/neurons3d.js`): the whole brain keeps the #77 points. With neurons on, zooming in on the
  brain (camera distance < `LOD_IN`) opens a close-up of the region nearest the camera; zooming out of a close-up
  (beyond `LOD_OUT` × its framing distance) returns to the whole brain. The row "close-up: cortex · striatum ·
  thalamus · cerebellum · whole brain" does the same by hand (cortex/striatum/thalamus: the most active region of
  that kind; hippocampus and amygdala use the cortical shapes; the pallidum has no close-up shape).
- **Close-up**: a block of tissue with 120 (cortex: 96 pyramidal + 24 basket), 220 (striatum), 160 (thalamus) or
  120 (cerebellum) cells, ≤ 60 000 segments (34 920 – 44 660), drawn as instanced `LineSegments`: one draw call per
  cell type (cortex 2, the others 1); each soma is three short crossed strokes in the same geometry. Nothing is drawn
  while the brain is off screen or the tab hidden (as before).
- **Spikes on the shape**: each drawn cell stands for a sampled model neuron of the close-up's region (the frame's
  slot 0–255 picks the cell). When its spike arrives in `n3.sq`, the soma flashes and a pulse runs from the soma
  along the axon at 1 mm/s on screen — about 500× slower than a thin unmyelinated cortical axon (~0.5 m/s) — and the
  dendrites glow with the region's rate (`n3.rq`). Per-instance spike times and the pulse live in the shader: no
  per-frame JS loop over segments. Axons stop where the reconstruction stops (the MSN's and relay cell's are short
  stubs). The stream is unchanged: a close-up shows the few sampled spikes of one region (≲ 1–2 a frame).
- **Cerebellum**: not one of the model's 214 regions. Its close-up shows the Purkinje shapes only, takes no frames,
  and says "the cerebellum is not in the simulated network: shapes only, no activity". Offline (no live network),
  every close-up is static and says "no live network: shapes only, no activity".
- **Checks**: `tests/test_neurons_morph.py` (asset, credits, simplification budget, and via node
  `tests/js/neurons_morph_check.js`: cells / segments / draw calls per close-up, no activity offline or from another
  region, the cerebellum never active, the LOD switch); screenshots and timings: `python tests/neurons_morph_shots.py`
  → `docs/screens/neurons_morph/`.
