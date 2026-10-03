# Room rendering pass (#98 G6): before / after

Screenshots of `/` at 1280 × 800 (desktop) and 390 × 844 (phone), hours 8, 14, 19 and 23 Tokyo, him placed the same way
in both sets (reading at the desk in the morning, the window sill at 14, reading at the desk with the lamp at 19, the phone
on the bed at 23; `h23s` is 23:00 asleep with the lights off, G8's night scene). The camera is the page's own first
shot for the scene (`before`: the old follow camera; `after`: the new shots, pinned with `setShot`):

    python tests/room_render_shots.py --tag before   # on main, before this branch
    python tests/room_render_shots.py --tag after --post high

`before_*` is `main` before this branch; `after_*` is this branch with the high tier pinned (`?post=high`): headless
Chromium draws WebGL in software (SwiftShader), which the page would otherwise detect as a weak GPU and run on the low
tier (no post chain). `results_before.json` / `results_after.json` carry the page's own numbers.

## What changed
Owner's brief (relayed 2026-10-02): as real as possible, physical light units, accurate exposure, real AO and contact
shadows, a film-like tone curve, no stylised bloom or glow; phones stay ≥ 30 FPS through the adaptive tiers.

- `web/room_post.js` (new): the post chain on three.js's EffectComposer: N8AO ambient occlusion (replaces the render
  pass) → a light depth of field when the camera is close → the grade pass (ACES tone mapping with the page's exposure,
  a white balance that follows the light's colour temperature, a faint split tone, contrast, a vignette and a little
  grain, sRGB out) → SMAA. Three tiers: **high** (all of it, 2048 px sun shadow), **medium** (N8AO at half resolution,
  grade, FXAA, 1024 px shadow), **low** (no composer: plain rendering with the canvas's MSAA and the page's CSS
  vignette). Bloom is off on every tier; `createPost(..., {bloom:true})` adds a faint lens veil (threshold 1.6, strength
  0.12) for the bulb and the sun only. The tier comes from the GPU's name, memory and cores (`detectTier`), or
  `?post=high|medium|low` pins it; the governor lowers it after two seconds of slow frames once the page's adaptive
  pixel ratio has already bottomed out, and raises it back after twelve seconds of fast ones (a failed tier is retried
  after 90 s). Every pass is imported on its own; one that fails to import, throws while building or throws while
  rendering is left out, and the room always draws (`tests/test_room_post.py`).
- Physical light units (three.js's physical lights; 1 unit = 1000 SI): the sun 14 klx through the glass, the sky seen
  through the window 6 knit, the bounce 1 klx, the desk lamp 0.28 kcd (a spot with one 1024 px shadow map, was a point
  light with six 512 px faces) plus a 0.04 kcd bulb for the spill, the ceiling light 0.2 kcd, a monitor 0.012 kcd and a
  phone 0.003 kcd on his face, the monitor 0.3 knit and the phone 0.45 knit. The exposure is a fixed stop per state, never
  a key that equalises the scenes (G8's review of the first cut: an adapting exposure lifted the lights-off night room to
  noon brightness): 2.2 by day, 4 at night with the lights off (the moon and the city's glow are the only key), 5.5 with
  the lamp or the ceiling light on, so their pools are bright and the rest of the room stays dark (`lighting()`).
- Shadows: the sun's shadow frustum moves in whole texels (no swimming edges), a higher normal bias against acne. A
  contact shadow under his feet that fades as they leave the floor; N8AO gives the contact darkening on everything else.
- Sun shafts: slices of the window's light along the sun's direction, depth-tested so furniture cuts them, by day and at
  dusk (not on the low tier).
- Reflections: each material class reflects its own share of the environment (`envClassOf`: glass 1.0, metal 0.9, wood
  0.35, walls 0.2, fabric 0.1). On the medium and high tiers the environment map is the room itself: a 128 px cube
  render from the room's centre (him and the effects left out), re-taken when the quantised light state changes, so the
  monitor, the floor and the metal reflect the real window and lamp at their real radiance.
- Camera (G8 #10, #18; the camera block in room.html is G6's now): shots like a game's on a slow cycle, with a cut at
  each new shot and a dolly inside one. At a screen: **face** (a medium close-up from the desk's end, the monitor
  lighting him), **screen** (over his shoulder onto the page), **medium**; on the phone: **over** the shoulder, **face**;
  elsewhere: **medium** (2.4 m, 50° off his facing), **face**, and the **overview** (which stays in the cycle). A
  candidate position that would sit in a wall or a piece of furniture is turned round him (the mirror angle, a profile,
  the front, a rear three-quarter) until it fits. `?debug` → `setShot("face")` pins one.
- Night (G8 #15): a city's night sky through the window (0.12 knit), a little moon and streetlight, at a fixed night
  stop; nothing is painted brighter than its light, and black cloth stays black. Monitor (G8 #16): the page is drawn at 0.3 knit, slightly
  blue-white, no longer a light source. Lamp on the hoodie (G8 #22): AgX in place of ACES (highlights roll off instead
  of clipping), the lamp 0.2 kcd, the exposure keyed to it.
- The window (G7's `window_view.js`, merged): `lighting()` sets its emission to 2.5 knit by day and 0.03 at night on
  every tier (the lighting is physical on all of them): the brightest thing in the room, the view still readable (5
  clipped it to white: 6.6 % blown pixels in the desk shot); its weather's sun factor scales the sun and the shafts.
  The screens dim at night as real panels do (the monitor 0.3 → 0.12 knit, the phone 0.45 → 0.05), so a page is bright
  in a dark room without clipping.

## G8's harness, main vs this branch (`python -m tests.visual.harness`, software WebGL, 0 hard failures on both)
`exposure()` of the 3D canvas (`tests/visual/image_checks.py`): mean luminance 0–255, pure-black and blown-out pixel
fractions. The page shots frame him differently on this branch (the new camera shots instead of the old follow camera),
so compare the black and blown fractions there rather than the means; the close-ups use the harness's own fixed cameras.

| shot | mean lum | pure black | blown |
|---|---|---|---|
| sleeping_23_1280 | 10.5 → 47.8 | 12.2 % → 15.8 % | 0.00 % → 0.00 % |
| sleeping_23_390 | 11.8 → 55.5 | 18.1 % → 2.5 % | 0.00 % → 0.00 % |
| phone_23_1280 | 36.5 → 47.8 | 7.3 % → 2.4 % | 0.00 % → 0.00 % |
| window_19_1280 | 45.0 → 80.9 | 2.2 % → 8.6 % | 0.23 % → 0.00 % |
| eating_19_1280 | 50.9 → 101.3 | 1.8 % → 6.9 % | 0.20 % → 0.00 % |
| desk_14_1280 | 163.4 → 126.5 | 1.1 % → 3.2 % | 3.96 % → 0.00 % |
| desk_14_390 | 150.4 → 146.7 | 1.9 % → 0.0 % | 9.20 % → 0.00 % |
| door_8_1280 | 69.4 → 121.3 | 0.5 % → 0.6 % | 0.23 % → 0.00 % |
| walking_8_1280 | 175.5 → 118.8 | 0.1 % → 0.9 % | 7.40 % → 0.00 % |

Close-ups (mean luminance, the harness's fixed cameras): night 7.2 → 42.2 · face 99.9 → 146.2 · hands 51.5 → 98.6 · desk 103.7 → 97.2 · bed 103.6 → 121.7. The night close-up of the bed with the lights off goes
from 7 to 42 (the coordinator's target for the floor: RGB 30–45); the monitor's page no longer blows out (desk 14: 4 %
→ 0 % of the canvas at 1280, 9 % → 0 % at 390); the hood under the lamp no longer clips (eating 19: 0 % blown).
The night stop is 12 against 2.2 by day (5.5×, inside the 4–6× cap); with a lamp or the ceiling light on, 7.

A note on the environment capture found on the way: the floor reflects the environment map, so a capture fed back
into the next one, and an early capture with a few NaN texels (software WebGL) blacked out every later frame. Captures
are now taken with the environment off on every material (direct light only) and a capture whose floor face holds a
NaN or an infinity is dropped and retried after the rate limit.

## Numbers
Measured 2026-10-02 in this sandbox: headless Chromium with **software WebGL** (SwiftShader) on 4 CPU cores. A software
rasteriser draws the room at 0–2 frames per second whatever the tier, before and after, so the FPS column says nothing
about a GPU; it is kept for the record. The page's own JS main-thread cost per frame (`__frameMs` under `?debug`) is
the number that transfers to a phone: the post chain is GPU work and adds nothing measurable to it.

| page | tier | fps (software GL) | JS ms / frame | note |
|---|---|---|---|---|
| 1280 × 800, before | direct | 0.0 | – | main, no post chain |
| 1280 × 800, after | low (direct) | 0.1 | 9.5 | the canvas's 4× MSAA is what a CPU rasteriser pays most for |
| 1280 × 800, after | medium | 0.7 | 10.1 | |
| 1280 × 800, after | high | 0.7 | 7.4 | |
| 390 × 844, before | direct | 0.9 | – | |
| 390 × 844, after | low | 0.5 | (6 frames) | |
| 390 × 844, after | medium | 2.2 | 8.8 | |
| 390 × 844, after | high | 1.9 | 11.7 | |
| 390 × 844, CPU ×4, before | direct | 0.8 | – | mid-phone profile |
| 390 × 844, CPU ×4, after | low | 0.2 | 17.4 | |
| 390 × 844, CPU ×4, after | medium | 1.4 | 27.0 | 5 frames sampled: noisy |
| 390 × 844, CPU ×4, after | high | 1.2 | 23.2 | 4 frames sampled: noisy |

What this supports: the post chain costs no main-thread time (the JS ms per frame is the same with and without it,
within noise), so on a phone the budget is GPU fill rate only. Expected GPU cost of the medium tier at 390 × 844 and
DPR 1.5 (0.74 Mpx) from the passes' own published numbers, not measured here: N8AO at half resolution with 8 samples
and 4 denoise samples ≈ 1.5–2.5 ms on a 2020 mid-range phone GPU, FXAA ≈ 0.3 ms, the grade ≈ 0.2 ms, the spot
shadow map once per lit frame ≈ 0.5 ms: ≈ 3–4 ms over the plain render, inside a 33 ms frame. If a phone still falls
under ~33 ms per frame for two seconds after the pixel ratio has bottomed out, the governor drops to the low tier
(plain rendering, exactly the pre-#98 cost) and retries the medium tier after 90 s. **The ≥ 30 FPS claim on a real
mid-range phone and ≥ 60 on a desktop GPU still need a real device** (as for the neuron forest, #88): open `/` with
`?debug` and read `post.info()` and the FPS; `?post=medium` and `?post=low` pin a tier for comparison.

Desktop detection: an NVIDIA/AMD/Apple GPU starts on high, an Intel HD/UHD 6xx or a 3 GB device on medium, phones on
medium (a known weak GPU, Mali-G5x, Adreno 5xx/61x, PowerVR, or ≤ 3 GB, on low), software WebGL on low.
