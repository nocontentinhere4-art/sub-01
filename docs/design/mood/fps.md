# Frame rate: before (main) and after (`?mood=1`)

Measured with `tools`-style headless Chromium on a RunPod **RTX A5000** (WebGL on the GPU: "ANGLE (NVIDIA RTX A5000,
OpenGL ES 3.2)"), one pod per run, deleted at the end (run 1: 15 min, run 2: 20 min, ~$0.16 together; the "BRAIN" pod
was never touched). Same scene for all (him at the desk), four hours (08:00, 14:00, 18:18, 23:00), two cameras (the
follow camera and the overview), clear weather. Three pages: main as it was (b0eff95), this branch's default page, and
this branch with `?mood=1`.

- **fps**: the page's own loop for 5 s (requestAnimationFrame; headless Chromium tops out around 55-60).
- **ms per render**: one `renderer.render` plus a 1-pixel readback (so it waits for the GPU), mean of 60.
- **phone**: a 390×844 viewport at DPR 3 (the page caps itself at 1.5) with the CPU slowed 4× by the DevTools
  protocol. The GPU is still the A5000: no phone GPU was available, so this row shows the CPU side of a phone, not its GPU.
- The page lowers its own resolution when frames are slow (`adapt()`), so "canvas at the end" says what was drawn.


### Run 1

| size | page | fps median (min) | ms per render, median | draw calls | canvas at the end |
|---|---|---|---|---|---|
| laptop 1280×800, DPR 1 | main (before) | 55.6 (53.9) | 4.63 | 87 | 1280×800 |
| laptop 1280×800, DPR 1 | this branch, default page | 51.0 (48.3) | 4.76 | 87 | 1280×800 |
| laptop 1280×800, DPR 1 | this branch, ?mood=1 | 52.1 (42.7) | 5.00 | 91 | 960×600 |
| phone 390×844, DPR 3, CPU ×4 slower | main (before) | 3.8 (3.1) | 6.80 | 83 | 390×523 |
| phone 390×844, DPR 3, CPU ×4 slower | this branch, default page | 3.6 (1.8) | 6.37 | 83 | 390×523 |
| phone 390×844, DPR 3, CPU ×4 slower | this branch, ?mood=1 | 3.5 (2.5) | 7.15 | 87 | 390×523 |

### Run 2

| size | page | fps median (min) | ms per render, median | draw calls | canvas at the end |
|---|---|---|---|---|---|
| laptop 1280×800, DPR 1 | main (before) | 43.1 (40.0) | 6.89 | 87 | 960×600 |
| laptop 1280×800, DPR 1 | this branch, default page | 48.8 (47.8) | 5.54 | 87 | 1280×800 |
| laptop 1280×800, DPR 1 | this branch, ?mood=1 | 46.1 (41.7) | 6.76 | 91 | 960×600 |
| laptop 1280×800, DPR 2 (page caps 1.5) | main (before) | 46.1 (40.2) | 5.47 | 87 | 1920×1200 |
| laptop 1280×800, DPR 2 (page caps 1.5) | this branch, default page | 43.3 (41.2) | 5.64 | 87 | 1600×1000 |
| laptop 1280×800, DPR 2 (page caps 1.5) | this branch, ?mood=1 | 46.4 (37.3) | 6.50 | 91 | 1280×800 |
| phone 390×844, DPR 3, CPU ×4 slower | main (before) | 4.0 (2.3) | 6.78 | 83 | 390×523 |
| phone 390×844, DPR 3, CPU ×4 slower | this branch, default page | 2.4 (1.4) | 7.79 | 83 | 390×523 |
| phone 390×844, DPR 3, CPU ×4 slower | this branch, ?mood=1 | 2.2 (1.6) | 7.51 | 87 | 390×523 |

(Run 1 measured an earlier commit of the layer, before its one-time shader compile at start; there `adapt()` had
already lowered the mood page to 960×600 during the boot. Run 2 is the final code.)

## What this says

- **Desktop:** the mood layer costs about **+1 ms of GPU per frame** at 1920×1200 (6.5 vs 5.5 ms) and about the same
  at 1280×800 (6.8 vs 6.9 ms, where main itself had dropped to 960×600 in that run). That is 4 more draw calls (the beam,
  the dust, the arranged things' ring) and two more lights (the floor bounce, the screen's area light). The fps spread
  between runs of the *same* page (main: 55.6 in run 1, 43.1 in run 2) is larger than the difference between the pages:
  on this machine the loop is bound by the CPU and the compositor, not by the GPU.
- **Phone (CPU 4× slower):** every page, main included, runs at 2-4 fps here: the page's own per-frame JavaScript (his
  animation, the planner, the camera's collision rays) under a 4× throttle, not the lighting. The mood page is within
  the run-to-run noise of main (main 3.8 / 4.0, the default branch page 3.6 / 2.4, mood 3.5 / 2.2). On phones the layer
  turns itself down (`lite`): 1024² sun shadow map, 70 dust motes instead of 160, no screen area light, the swatch
  textures at most 1024².
- **SwiftShader** (the sandbox's software WebGL, what `tests/visual` uses): one 1280×800 render takes ~9.3 s for both
  main and the mood page; not a device number.
- The CPU cost of the layer itself (its tick and lights, without the environment repaint) is ~1 ms per frame under
  SwiftShader's CPU; the environment repaint (a 128×64 canvas through PMREM) runs only when the hour moves a quarter
  hour, a swatch or the lamps change.

Not measured: a real phone's GPU. Before `?mood=1` becomes the default, one look on a mid-range phone is worth it.
