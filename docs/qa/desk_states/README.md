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
| gesture_a | small gesture | room_mx_sitting_rubbing_arm | once; seat −0.17 |
| gesture_b | small gesture | room_mx_sitting_talking | a 5–8 s window, once; seat −0.11 |
| react_win | reaction | room_mx_standing_clap | once; seat −0.13 |
| react_lose | reaction | room_mx_angry_gesture | once |
| react_up | reaction | room_mx_standing_clap | once; seat −0.13 |

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
Measured locally, alone on 2 cores (`taskset -c 0,1`), with the page's `qa.body(2)` every 0.1 s.
- **Each slot:** swept whole. For a once slot that covers ride, take and ride back.
- **Natural watching:** 120 s with the page's messages handed in as the socket sends them.
- **Chess:** the wait and look sequence, then a won game.

| sweep | desk | chair | bed | below floor |
|---|---|---|---|---|
| every slot, the crossfades, 120 s natural, chess won | 0 | 0 | 0 | 0 |

**Crossfades frame by frame** (idle_c↔attend, idle_a→idle_c): chair + desk 0 on every frame.

**Seat points for the stand-ins.** Swept against the chair, the clearest of −0.03…−0.17 m:

| stand-in | at desk_watch's seat point (−0.075) |
|---|---|
| gesture_a | 545 vertices (left thigh) |
| react_win | 180 |
| gesture_b | 10 |

**Before these fixes**
- The sova slots were placed by the clip's hips height instead of the seat's, which lifted him 6 cm at each switch. They now sit at the seat height, as desk_watch does.

`sheet.jpg`: each slot mid-play from the character camera, plus react_win on a won game.
