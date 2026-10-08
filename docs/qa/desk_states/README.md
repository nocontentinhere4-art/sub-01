# Seated states at the desk (`room.html?char=mixamo&anim=sova`)

A preview layer, off by default. `room/desk_states.js` decides what he does in the chair; `room/boy_mh.js` plays it.
Without `&anim=sova` the page neither loads the module nor queues any message.

## What plays
These states play in `desk_watch` only: a video, a page, or waiting for the opponent at chess. Typing and the mouse stay as on main (the owner's takes).

| slot | kind | stand-in (`room/mh_mx/`) | how it plays |
|---|---|---|---|
| idle_a | waiting | room_seated_idle | loop |
| idle_b | waiting | none | left out: `room_mx_sitting` puts his legs through the seat at every seat point tried (≈5000 vertices) |
| idle_c | waiting | room_mx_sitting_1 | loop |
| attend | on the monitor | room_seated_idle | loop |
| gesture_a | small gesture | room_mx_sitting_rubbing_arm | once; seat −0.22 |
| gesture_b | small gesture | room_mx_sitting_talking | a 5–8 s window, once; seat −0.22 |
| react_win | reaction (a won game only) | room_mx_sitting_talking | a 3–5 s window, once; seat −0.22 |
| react_lose | reaction | room_mx_sitting_rubbing_arm | once; seat −0.22 |
| react_up | reaction (a big burst on a short) | room_mx_sitting_talking | a 3–5 s window, once; seat −0.22 |

**No desk state stands him up.** Two stand-ins were dropped, and react_up stays seated: a short doesn't get him up. Later it becomes Sova's LAUGH SIT / DISTRACTED & THEN SMILE.

| dropped stand-in | was for | why |
|---|---|---|
| room_mx_standing_clap | react_win, react_up | up at the desk, his fingers went into the monitor (up to 834 sampled vertices); his hands were a few cm from the lamp and the monitor |
| room_mx_angry_gesture | react_lose | his forearms went through the monitor (1269 vertices). At seat −0.30 it cleared the monitor, but his right hand went through the bottle on the desk (369) |

**How the loops are picked**
- Each loop is picked at random and never follows the same clip. Two slots on one stand-in count as one clip, so desk_watch is never followed by idle_a or attend.
- Each loop starts at a random phase of its clip and holds for a random time (7–15 s idle, 6–12 s attend). No two loops run in step.
- Between events, the mix is:

  | situation | attend | idle | gesture |
  |---|---|---|---|
  | watching | 0.55 | 0.37 | 0.08 |
  | waiting | 0.25 | 0.65 | 0.10 |

- Gestures come at least 25 s apart and reactions at least 150 s apart.

**Crossfades and the chair**
- Loops crossfade over 0.8 s.
- Gestures and reactions go through the rare events' path (`rareStep`):
  - he rides the chair back by what the take needs (`backFor`), or not at all if it needs nothing;
  - the take plays with a 0.8 s fade in and out;
  - he goes straight into the next loop and rides back in.
- The switches run before the mixer update, like `rareStep`. Run after it, the root blend saw the new clip at full weight for one frame: an 862-vertex chair spike.

**Named clips (G23's).** Put `web/room/desk_states/<slot>.glb` in place and list it in `index.json` (`{"clips": [...], "seat": {...}}`). That slot then plays its own clip instead of the stand-in. The list is empty for now: no clip goes in until its licence is cleared.

## Reactions: only messages the page already receives (`live_server.py`)

| message | when | reaction |
|---|---|---|
| `chess` (#17) | the opponent moved, his turn | attend; with check on him, a gesture |
| `chess` | game over | won → react_win, lost → react_lose, draw → a gesture (the end is broadcast twice; it counts once) |
| `chess` | the opponent's turn | he waits in the chair (desk_watch, idle mix). On his turn he looks for 2.5 s, then takes the mouse. After the end he sits back |
| `decision` (#55) | his brain picked a page or a video | attend |
| `dopamine` (#89) | a new clip or page; size = novelty + interest − expectation | ≥ 0.45 a gesture, ≥ 0.9 react_up. Only shorts reach 0.9: videos are scaled ×0.5, pages ×0.25 |
| `chat` | a viewer's message reaches him | attend |

- **Left out by design:** trades (nothing financial).
- **Also no reaction:** music, ticks and the rest.
- **Expiry:** an event not played within 4 s is dropped. A reaction goes ahead of a look.
- **Scared has no event.** Nothing the page receives warrants it, so it stays unmapped.

## Measured
Measured locally, alone on 2 cores (`taskset -c 0,1`).

**What each sweep covers**
- **Each slot:** swept whole every 0.1 s. For a once slot that covers ride, take and ride back.
- **Natural watching:** 120 s with the page's messages handed in as the socket sends them.
- **Chess:** the wait and look sequence, then a won game.

**Desk, chair, bed, floor** (the page's `qa.body(2)`): 0 in every sweep.

**All of the room** (`sv_room2.py` in the session scratchpad: every room part and every scene object, not only desk/chair/bed/floor):
- **Closed furniture:** inside means an odd number of crossings on 2 of 3 rays, both faces counted. This covers the wardrobe, door, shelves, monitor, lamp, controller, mug and bottle.
- **Walls:** checked against the room's box.
- **Left out:** the keys and the mouse (his hands work on them), flat decals and 4-vertex helper quads.
- **The desk:** counted with freshly built raycast trees. On main the page's trees are stale after the keyboard cut, so they miss 26% of the desk (the freeze-why bug).

| | inside furniture | past a wall | desk during the take (fresh trees) | nearest wall (limbs) | nearest thing other than the desk (limbs) |
|---|---|---|---|---|---|
| every gesture and reaction | 0 | 0 | 0 | ≥ 44 cm | ≥ 3.4 cm (the desk's shelf rail) |

**Inherited from main's own mixamo seated loop** (room_seated_idle, desk_watch's clip on main, and so idle_a and attend too):
- 369–413 sampled vertices are in the desk once the trees are fresh: the forearms on its front edge, which the stale trees hide.
- His right hand and forearm are in the bottle on the desk: 10–22 vertices.

This is not from this layer: the same numbers show with `anim` off.

**The chair ride**
- The rides are longer now: 0.21–0.51 m on top of the slot's seat point.
- The ride-back (`backFor`) misses things in three ways, all fixed for the desk states only (the default page's `rare()` is unchanged):
  - it sampled no fingertips, though raised hands reach 18 cm past the wrist;
  - its rays stopped at 1.14 m, under the monitor;
  - it raycast through main's stale trees.
- The seat points were then swept against the desk counted with fresh trees.

**Crossfades frame by frame** (idle_c↔attend, idle_a→idle_c): chair + desk 0 on every frame. The switches run before the mixer update; run after it, the root saw the new clip at full weight for one frame (an 862-vertex chair spike).

**Before the first fixes:** the slots sat at their clip's hips height instead of the seat's, which lifted him 6 cm at each switch.

## The hood (`char_mixamo.glb`'s autorig; not fixed here: G21 / C)
The dark spikes at the back of the hood are the hood's lining and patches (`hood_lining`, `hood_patches`; 3127 vertices) coming out through the hoodie.

**How it is measured**
- **The lining:** the signed distance of each lining or patch vertex to the hoodie's surface near the neck. A vertex counts as out when it is past the outer face. Each vertex is compared with its own value in desk_watch's seated pose, so only the extra counts: the hood's rim is out by design.
- **The hood and shoulders:** the hoodie's own vertices over the shoulders and behind the neck. This reports how much further from the neck they move than in the seated pose, in the neck's frame. That includes the shoulders' ordinary movement as the arms rise.

| slot (take) | lining out, most | lining vertices out more than 0.5 cm | more than 1.6 cm | hood and shoulders, most | vertices more than 1.6 cm |
|---|---|---|---|---|---|
| idle_a (desk_watch's loop, other frames) | 5.6 cm | 9 | 8 | 0.1 cm | 0 |
| attend | 6.3 cm | 32 | 26 | 3.1 cm | 2001 |
| idle_c | 7.1 cm | 52 | 42 | 3.8 cm | 2742 |
| gesture_b / react_win / react_up (sitting_talking) | 7.1 cm | 56–130 | 45–106 | 3.8–4.3 cm | 4811–5002 |
| gesture_a / react_lose (rubbing_arm) | 7.1 cm | 384 | 257 | 7.1 cm | 5633 |

With the arms up, a few hundred lining vertices go 1.6–7 cm past the hoodie. The arm raise pulls the hood's back and shoulders up to 7 cm off their seated place.

`sheet.jpg`: each slot mid-play from the character camera.
