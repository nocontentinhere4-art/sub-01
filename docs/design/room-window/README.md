# The window and the outside (#98 G7, PR `feature/gl-window`)

Before (main) and after, at Tokyo hours 07, 12, 18, 21 and 02, at 1280 and 390 px, clear and in the rain. Each sheet:
**before | after, clear | after, rain**; the page's overview camera above, the view from his place at the window below.
Made by `python tests/room_window_shots.py --before <checkout of main>`; `results.json` has the weather state of each shot
and the cost figures. Headless Chromium draws WebGL in software here (SwiftShader), so the colours are right but the
anti-aliasing and the texture filtering are coarser than on a phone or a laptop.

## What changed
- `web/room/window_view.js`: one plane on the glass marker. Its shader casts the view ray from the real camera through
  each glass pixel onto virtual cards behind the window (near 14 m: the house across the lane, the utility pole and its
  cables, the lamp and the vending machine; mid 30 m: a row of apartment blocks with balconies, AC units, laundry, pipes,
  water tanks and antennas, two gaps with the elevated railway; far 100 m: the sea of roofs and a few towers; the street
  plane; the sky at infinity). True parallax from every camera; nothing exists outside the glass.
- Sky by phase of day (night, blue hour, golden hour, day) from the sun's elevation; the sun and the moon cross the
  window; drifting clouds; stars and the city's glow at night; birds by day.
- Night: the homes' windows switch on and off on their own (each pane has an id; a hash of id and a 2-minute slot decides,
  with a probability that follows the evening), shop fronts and stair lights stay on, a red aviation light blinks.
- A train crosses the viaduct every 150 s, alternating direction, lit at night.
- Weather: clear, overcast, rain. Rain streaks run down the glass and drops refract the view; rain falls outside; the far
  layers haze over; the street turns wet. **There is no weather feed**: nothing in `live_server.py` or `life.py` fetches
  one, so the weather is a **deterministic** daily pattern (`weatherAt`: smooth noise over Tokyo time, about a fifth of
  the hours wet and a third overcast, the same for every viewer), never presented as real. `?debug&weather=rain|overcast|clear`
  previews one; `view.light.sun` (0..1) tells the room's lighting how much sun the weather lets through (not wired yet:
  the lighting block is G6's).
- A diorama cheat, stated plainly: the room's cameras all look down (the orbit controls never go below 12.6° of pitch, and
  the overview looks down ~25°), so a true window would show only the street from the default view. The view rays are
  flattened vertically (gain 0.5) and lifted by a slope that grows with the camera's height over the window (0.12 + 0.06
  per metre, at most 0.4), so the horizon follows the camera up. The horizontal parallax is true (gain 0.7).

## Budget
- Assets: all the cards together are under 200 KB (`room_build/window_cards.py` prints the sizes; budget 1.5 MB), one
  draw call, at most ~10 texture reads per glass pixel, no per-frame JS beyond a few uniforms (`results.json` →
  `window_update_js_ms`).
- The 2 ms per frame on a mid-range phone cannot be measured here (software GL); the shader is bounded by the glass's
  pixels (a fraction of the screen) and its cost per pixel is a handful of texture reads and ~200 ALU ops, below the old
  in-page sky shader's 4-octave noise per pixel. Needs a real device (G8's suite).
