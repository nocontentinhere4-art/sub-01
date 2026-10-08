# Room mood (`?mood=1`), a preview awaiting the owner's approval

Branch `preview/mood-lighting`. The default page is unchanged: without `?mood=1` the page does not load
`web/room/mood.js` and every hook added to `web/room.html` is a no-op (`mood` stays `null`). Look at it with
`/room.html?mood=1` (locally: `python -m tests.visual.fake_server --port 8797`, then
`http://127.0.0.1:8797/room.html?debug&mood=1`).

Inspired by the "a room you can set the mood of" kind of page; nothing of anyone else's is used: the light, the
swatches, the props and the card are our own code, colours and primitives, recoloured from the room's own textures.

## What it adds

1. **Light and atmosphere.** The sun comes in through the window from where the window view shows it
   (`window_view.js` now exports the sun's or the moon's direction, `light.dir`), low and warm in the morning and the
   evening, so its patch sweeps over the desk wall, the rug and the bed over the day. Softer sun shadows (PCF with a
   wider kernel), a faint beam of light with dust motes in it, a warm bounce light where the sun lands on the floor
   (tinted by the floor's swatch), and an environment painted from the room's own colours (re-made only when the hour
   moves by a quarter hour or a swatch changes), so reflections and the rough surfaces pick up the warm walls and floor.
   The room's baked ambient occlusion is a little deeper.
2. **Light that follows the hour.** Morning, noon, evening and night cross-fade (`window_view.js` `dayPhase`, used by the
   window's own clock: the same Tokyo `hour` as before, extended, not duplicated). The ceiling light and the desk lamp
   come on from ~17:00 while he is up and in, the ceiling light dims late in the evening, and from ~01:00 the lamps are
   off and the monitor's own light (an area light the size of the screen, desktop only) and the moon carry the room.
   A **"preview the hour"** slider (and Morning / Noon / Evening / Night chips) lets a visitor look at any hour; 6 s
   after the last touch it eases back to the real Tokyo hour on its own (2.5 s). It changes the light only, never his life.
3. **The visitor's materials.** Swatches for the floor (oak, pale ash, honey, walnut, smoked oak), the walls (chalk,
   linen, clay, sage, dusk blue), the duvet (indigo, rust, oat, moss, charcoal) and the rug (5), plus five whole-room
   "looks". The first swatch of each is the room as built. Recoloured in the browser from the room's own textures,
   keeping their grain. (There is no sofa in the room, and the floor cushion was taken out of it before: the bed and
   the rug are the fabrics.)
4. **Arrange** (asked for during the work): move the plant by the window, add a floor lamp (its light follows the
   room's lamps), a plant, a side table, a stack of books or a pouf, drag them on the floor, turn or remove them. No
   spot may be on his routes, next to where he stands, on the furniture or in the door's or the chair's swing
   (`spotOK`, checked against room.html's `BLOCK`, `NODES`, `LINKS` and `ANCHOR`), so his routes stay as they are. The
   bed, the chair and the desk are not movable.
5. **One rounded card** ("Room mood": Time, Mood, Materials, Arrange) in our orange. On desktop it is the first card of
   the right-hand column; on phones the first card under the scene, so it never covers him
   (`tests/visual/test_mood.py` projects his bones against the card at 1280 and 390 in three scenes, two cameras).

Everything a visitor picks is kept in **this browser only** (`localStorage`, every read and write inside try/catch,
values validated on load): nothing is sent anywhere, the server is never touched, and nobody else's room changes.

## Frame rate (before / after)

Before / after at the same hour: `before_after_0800.jpg`, `before_after_1818.jpg`. See `fps.md` (measured on a RunPod RTX A5000 through headless Chromium, and the CPU-throttled phone emulation; the
notes there say what those numbers can and cannot tell).

## Files

- `web/room/mood.js`: the layer (light, hour, swatches, card); `web/room/mood_arrange.js`: Arrange.
- `web/room/window_view.js`: `dayPhase`, `PHASES`, `light.dir` / `light.moon` / `light.up` (additions only).
- `web/room.html`: `MOOD` / `moodModule` / `mood` and five guarded hooks.
- Tests: `tests/test_mood.py` + `tests/js/mood_check.js` (pure functions, storage, swatch lists, Arrange spots against
  his routes, no network calls in the layer, the import only behind `MOOD`), `tests/visual/test_mood.py` (the page).

## To approve

- The look (light by the hour, beam, warmth) and the card's place, from the video and the before/after image.
- Whether `?mood=1` becomes the default (then `MOOD` goes true and the hooks stay as they are), or stays a preview.
