# Real references (G10d): preview only, never install or merge

The owner's rule: every item is shown next to a real photo of the same kind of object, at a similar angle and in similar light.
These sheets live only on this preview branch (`preview/g10d-reality`). On each sheet the real photo is on the left and our
render is on the right: `/room` at 14:00, him at the window so the desk is clear, rendered by the visual-QA page in software GL.

| sheet | ours | real photo | source | licence |
|---|---|---|---|---|
| `real_keyboard.jpg` | the original tenkeyless keyboard (room_clean.glb, split into node `keyboard`, 39062ea) | a black keyboard on a wooden desk, from above | https://commons.wikimedia.org/wiki/File:Black_Computer_keyboard.jpg (Samiknoov) | CC0 |
| `real_controller.jpg` | the controller modelled in code (1631de8), from low at the player's side | a plain dark gamepad on a table, from low at the front | https://commons.wikimedia.org/wiki/File:Controller_(Unsplash).jpg (Ugur Akdemir, via Unsplash) | CC0 |
| `real_monitor.jpg` (top) | the monitor modelled in code (1631de8), screen off, from the front | a monitor switched off, from the front (cropped at the left to leave out a far-off person) | https://commons.wikimedia.org/wiki/File:Pantaila.jpg (Anartzzz) | CC0 |
| `real_monitor.jpg` (bottom) | the same, screen off, three-quarter view | a slim monitor on a desk, three-quarter view | https://commons.wikimedia.org/wiki/File:Desk_Setup_(Unsplash).jpg (Luke Chesser, via Unsplash) | CC0 |
| `real_mouse_v2.jpg` | the remodelled mouse (5f52f37): photo, the old mouse, the new one | the same photo | as below | CC0 |
| `real_mouse.jpg` | the code-made mouse on its pad (`mouse.glb`) | a plain black wired mouse, three-quarter view | https://commons.wikimedia.org/wiki/File:ComputerMouseCloseup3.jpg (Raysonho @ Open Grid Scheduler / Grid Engine) | CC0 |

The real keyboard is full size and shows a small maker's emblem in its arrow cluster; I found no CC0 photo of a tenkeyless
board without one. Neither photo shows any person.

How they compare:
- Keyboard: holds up. Key count and layout, keycap shape, legends and colour are believable next to the photo. Ours is
  lit more evenly, and the case edge looks a little flat and plain.
- Mouse: does not hold up. The real one has a sharp split between its two buttons, a seam along the side, a crisp waist
  and a gloss gradient on top. Ours is a soft blob: the button split barely shows, it has no side seam, and its base sinks
  into the pad.

After the remodel (`real_mouse_v2.jpg`): the mouse now has a sharp split between its buttons, the wheel sits in a slot, a
dark parting seam runs all round a third of the way up over an upright skirt, the waist is pinched, the top is a satin
gloss, and a crisp chamfered base sits on the pad. It holds up much better. What still differs: the real one is wired and
has a red wheel, and its front is blunter; ours stays wireless and plain, keeping the same outline so the hand grip fits.

Controller and monitor (1631de8):
- Controller: holds up. It has the parts of a real modern pad in the right places (two grips, sticks with knurled caps on
  boots, D-pad, face buttons, bumpers and triggers) and is matte dark with glossier buttons. What still differs: our grips are
  rounder and softer than the photographed pad's, which has crisper edges and a light bar and touch pad, maker features we leave
  out.
- Monitor: holds up. Its thin bezels, chin, glossy rim, slim side profile and flat foot read like the slim monitor in the
  three-quarter photo. When off, the screen shows a faint anti-glare sheen like the front photo. The front photo is an older
  model with a thicker glossy bezel. Both monitor photos show a small maker's logo; I found no CC0 photo of a current slim
  monitor without one.
