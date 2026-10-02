# Room rendering pass (#98 G6): before / after

Screenshots of `/` at 1280 × 800 (desktop) and 390 × 844 (phone), hours 8, 14, 19 and 23 Tokyo, him placed the same way
in both sets (desk in the morning, the window sill at 14, the desk with the lamp at 19, the phone on the bed at 23):

    python tests/room_render_shots.py --tag before   # on main, before this branch
    python tests/room_render_shots.py --tag after --post high

`before_*` is `main` before this branch; `after_*` is this branch with the high tier pinned (`?post=high`): headless
Chromium draws WebGL in software (SwiftShader), which the page would otherwise detect as a weak GPU and run on the low
tier (no post chain). `results_before.json` / `results_after.json` carry the page's own numbers.

## What changed
- `web/room_post.js` (new): the post chain on three.js's EffectComposer: N8AO ambient occlusion (replaces the render
  pass) → UnrealBloom (the lamp's bulb, the lit screens, the sun in the window) → a light depth of field when the camera
  is close → the grade pass (ACES tone mapping with the page's exposure, white balance, split toning, contrast,
  saturation, a vignette and a little grain, sRGB out) → SMAA. Three tiers: **high** (all of it, 2048 px sun shadow),
  **medium** (N8AO at half resolution, bloom, grade, FXAA, 1024 px shadow), **low** (no composer: plain rendering with the
  canvas's MSAA and the page's CSS vignette). The tier comes from the GPU's name, memory and cores (`detectTier`), or
  `?post=high|medium|low` pins it; the governor lowers it after two seconds of slow frames once the page's adaptive
  pixel ratio has already bottomed out, and raises it back after twelve seconds of fast ones (a failed tier is retried
  after 90 s). Every pass is imported on its own; one that fails to import, throws while building or throws while
  rendering is left out, and the room always draws (`tests/test_room_post.py`).
- Light: the desk lamp is a spot light with one 1024 px shadow map (was a point light with six 512 px faces) plus a small
  bulb light for the spill; its bulb material glows only while it is on. The sun's shadow frustum moves in whole texels
  (no swimming edges), with a higher normal bias. Sun shafts: slices of the window's light along the sun's direction,
  depth-tested so furniture cuts them, by day and at dusk. A contact shadow under his feet that fades as they leave
  the floor. Each material class reflects its own share of the environment (`envClassOf`: glass 1.0, metal 0.9, wood
  0.35, walls 0.2, fabric 0.1). On the medium and high tiers the environment map is the room itself: a 128 px cube
  render from the room's centre (him and the effects left out), re-taken when the quantised light state changes, so the
  monitor, the floor and the metal reflect the real window and lamp.
- Screens are drawn 25 % brighter than white in HDR so that the bloom catches them, and the grade's tone mapping brings
  them back.

## Numbers
See the bottom of this file (filled in by the run; the FPS of software WebGL is a CPU rasteriser's, not a phone GPU's:
the JS ms per frame under the x4 CPU throttle is the number that transfers to a phone).
