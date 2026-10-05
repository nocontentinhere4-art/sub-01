# Room upgrade (preview/room-upgrade, G10d): preview only, nothing live

Based on preview/room-mh (0b6efe3: G2's body and clips, G3's chair choreography), with feature/tripo-props-2 (1631de8) merged in.

- `prima_dopo.jpg`: Prima (preview/room-mh) | Dopo (this branch), 14:00, him at the window. Shots: the room, the desk, the
  notebook, the chair, the basket, the key bowl, the shoes by the door, the door, its hooks, the floor.
- `real_chair.jpg`: the new chair next to real office chairs, at about the same angles.
- Contact checks: `python -m tests.visual.contacts` (`tests/visual/contacts.js`): every skinned vertex of G2's body, every 2nd
  frame at 30 fps, against the chair (all of him) and against the keyboard, the mouse and the controller (hands and fingers).
  Each object is cut into 5 mm vertical columns of inside-intervals in its own frame, so the test follows the chair as it is
  pulled, swivelled and ridden.

## What is in, what is out
| | from | how |
|---|---|---|
| woven laundry basket (scan), key bowl with the keys, notebook with a pen and a pencil (no logos) | preview/props-hard e3c0376 | `room_build/pick_props.mjs` -> `web/room/props_picked.glb` (only those materials and places; the wallet next to the bowl is left out) |
| controller, monitor (code-made), remodelled mouse, restored tenkeyless keyboard | feature/tripo-props-2 1631de8 | merged |
| the upright sneakers by the door, and nothing else | preview/props-soft 0cbc9ce | `room_build/pick_sneakers.mjs` -> `web/room/sneakers_door.glb` |
| OUT: the hoodie on the door, the jeans on the floor, the T-shirt with the grey floor cushion | today's room | hidden at load (`UPGRADE_DROP` in `web/room.html`), their baked floor shadows lightened out; the floor is left clear there |
| NEW: the desk chair | modelled in code | `room_build/chair_shape.mjs` (signed distance fields) + `build_chair.mjs` -> `web/room/chair_office.glb` |

Today's other objects stay as they are, including the slippers and the white Tripo sneakers in the front corner.

## The chair
A generic ergonomic office chair with no maker's design or logo: a mesh back in a black plastic frame, a padded seat in
charcoal woven fabric, T-armrests, a gas lift with a chrome piston, and a five-star base on twin-wheel casters.

- **Seat:** the cushion's top is 0.52 m over the floor where he sits, 0.50 m wide and 0.48 m deep. It has a waterfall front
  and rolled sides, as real seat cushions do.
- **Shaped to his motion:** before modelling, his skin's positions in every scenario below were recorded in the chair's frame
  (10 million 5 mm voxels). The chair was shaped to stay out of them:
  - the backrest's front follows the line of his back in the seated clips, about 1 cm behind it;
  - the backrest's top is at 1.115 m and leans back, so his head clears it when he stretches at bedtime;
  - the base is turned 11.5° and is 0.28 m to the wheels, which gives his feet the most room as he gets up;
  - the front of the seat and the pan under it are rounded and set back, clear of his calves as he rises.
- **G3's code is unchanged:** the meshes go into the room's own `chair` node, so CHAIR, chairHome, pulling, swivelling, riding
  and the get-up flow are untouched. Its grip points (the backrest's top, the armrests) are unchanged too: moved to the new
  chair, they changed when his hand reached for it while he walks off, and that made the get-up worse. Since the new
  backrest is lower, his hand stays a few centimetres above its top during the short push.
- **raiseChair():** boy_mh.js lifts the old chair by 1.6 cm (`raiseChair()`); the new chair is already built at 0.52 m, so it
  is marked as raised and not lifted.
- **Cost:** 24.8k triangles, 280 KB, 10 meshes (one closed mesh per part, for the contact test).

## Contacts (vertex by vertex, G2's body, every 2nd frame)
| scenario | frames | chair | keyboard / mouse / controller (hands) |
|---|---|---|---|
| desk typing | 150 | 0 | 0 |
| desk mouse | 120 | 0 | 0 |
| room_read | 262 | 0 | keyboard: 1 frame, 2 fingertips (86 vertices), max 4.9 mm |
| room_phone | 326 | 0 | 0 |
| room_phone_scroll | 326 | 0 | 0 |
| eating at the desk | 120 | 0 | keyboard: right hand, 24 frames, max 14 mm |
| bedtime: the stretch, getting up, to bed | 330 | 0 | keyboard: left hand pushing off it, 6 frames, max 14 mm |
| getting up to the window | 180 | left foot over a base leg: 1 frame, 146 vertices, max 12.9 mm | keyboard: left hand pushing off it, 1 frame, max 13.9 mm |
| sitting down at the desk | 240 | 0 | mouse: right hand arriving, 2 frames, max 17.6 mm; keyboard: 1 fingertip, 2 frames, 2.8 mm |

The controller is never touched; no clip plays it. "desk watch" is left out: in this build that act does not seat him, and
read and phone cover the relaxed seated poses. The finger contacts are the clips' and the choreography's own. They are the
same with the old chair (preview/room-mh), and none of them is in typing or mousing.

## Real references (CC0 / public domain, Wikimedia Commons; no faces)
| photo | source | licence |
|---|---|---|
| an office chair, three-quarter view | https://commons.wikimedia.org/wiki/File:Leather_executive_chair.jpg | CC0 |
| a mesh-back office chair, from the front (the emblem on its back blurred out; the people beside it are cropped at the chest) | https://commons.wikimedia.org/wiki/File:One_Cool_Seat.jpg | public domain |

Next to them, ours reads as the same kind of chair: five-star base on casters, gas lift, T-arms, mesh back, padded seat. It
is plainer: no levers on the armrests and no piping on the seat edge. Its backrest is a mid-back, lower than the executive
chair's.
