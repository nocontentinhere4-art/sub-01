# Natural, fluid movement in the room (#63, part 1: motion)

The owner's report: "Why is he stuck in this position? I want more fluid, real movements." He stood frozen in the middle
of the room, holding the phone, for the whole 2–4 minutes of ordering food. Part 2 (real dishes, bags, the bin and the
`delivery.dish` field) follows in its own PR.

Everything here is in `web/room.html`. No animation clips or models were added (GLB size change: 0 bytes). The new
props are a few three.js primitives built in code (credited as CC0 in `web/room/CREDITS.md`).

## What changed

### No frozen poses: additive layers on top of the clips (`alive()`, `aliveHead()`)
After the mixer, the walking and sitting steps and the seat IK, every frame:
- **breathing** at his body model's breathing rate (`vitals.resp_per_min`): the chest rises, the shoulders lift; deeper
  asleep;
- **weight shifts** standing: the hips drift a few cm from foot to foot, and two-bone IK keeps both feet planted (no
  sliding);
- **gaze**: head and neck turn towards a point that moves on a spring, within what a neck does. What he looks at depends
  on what he does: reading saccades on the monitor, the street from the window, the phone, glances up from it, the
  door when the courier is due (`courier.status` "on the way" with ≤ 2 min, or "at the door");
- **hands**: thumb flicks and taps on the phone (it dips and tips under the thumb, the wrist rolls a little), the mouse
  at the desk, chopsticks or bread to his mouth, the door handle, the bag;
- **seated**: a slow sway of the back; he sits up from the seated clip's hunch while eating, and a little at the screen.

### Idle variety
Idle variants per situation, picked at random with cooldowns, never the same twice in a row:

| situation | variants |
|---|---|
| standing | look around, scratch head, stretch, check the phone, shift weight |
| at the desk | look around, scratch head, drink from his bottle of tea, lean back, check the phone, knee bounce, hand on the mouse |
| on the bed edge | look around, swing the legs (forward only, never back into the bed frame), scratch head, shift |
| at the window | look around, chin on his hand, shift weight, scratch head, stretch |
| lying (phone, music) | a knee comes up, a foot taps to the music |

Getting up after more than 4 minutes at the desk, he stretches before he walks off.

### Places and poses
| activity | before | now |
|---|---|---|
| `order_food` | frozen standing in the middle of the room | sitting on the bed edge with the phone, or lying if he was in bed |
| `phone` | frozen on the bed edge | on the bed edge, then (at once or after 30–120 s) lies back; the phone moves |
| `window` | standing 2 m from the window | walks through the gap between the chair and the bed and leans on the sill with both hands, looks out (street, sky, towers), glances back in, rests his chin on his hand |
| `get_delivery` | the door clip, alone | walks to the handle side of the door, opens it with the left hand (the leaf swings in; the hallway is dark behind it), takes the courier's bag with the right, pushes the door shut, carries the bag at his side (it swings with his steps) to the desk and puts it down |
| `eat` | the "drink" clip, nothing in his hands | seated upright: a bento held in his left hand and chopsticks, or a bread roll; bites (picking, to the mouth, a bite, down, chewing nods) at a natural pace; the roll gets smaller |
| `listen_music` (#68, new on main) | standing beside the bed | on his back on the bed, headphones on, small nods to the music; at the desk the headphones are on while background music plays |
| away: `buy_konbini` | "out" | "at the konbini" |

Standing now uses a calm pose: the first frame of the door clip. The idle clip turns his whole body through 90°
every 4 s, which was the "same loop for minutes" in the report.

### Transitions
- He **turns on the spot before walking off** (more than 35° off), with small steps: the walk clip at half weight over the
  standing pose, slower. Full strides swept round would kick the bed or the chair.
- **He speeds up and slows down**: 1.4 m/s², top speed 0.9 m/s; he brakes to the end of a path and slows for corners.
  The walk clip plays at the speed his feet move (`timeScale = v / 0.65`), so the feet never slide.
- **Clip fades** are 0.3–0.6 s. Sitting down and getting up use the chair and the bed edge as in #42; that logic is
  unchanged, except for where the chair is parked (below).
- Walking or turning close to the chair or the bed, he keeps his hands in front of his hips (clearance-based).

## Changes to existing behaviour
- **The desk chair.** The model has it turned out by 0.54 rad, which left 34 cm between its backrest and the bed: no
  way through to the window. At load it is squared to the desk and parked 15 cm further in. He still sits where he sat
  before: the ride-in stops at the old distance (`CHAIR.seat`), and only getting up pushes it fully in. It only swivels
  between the seat and pulled out. The route treats it as ±0.40 m (it was ±0.33 m, smaller than the real chair).
- **Bugs fixed along the way:**
  - `q.slerpQuaternions(a, q, w)` always gave `a`: three.js copies `a` into `q` first. So every partly weighted IK
    blend snapped to the clip: the phone arm coming up, the hand on the chair, the feet planted on the bed edge.
    `blendQ()` does it right.
  - A clip that ended a sit-down blend at weight 0 kept `weight = 0`, and `reset()` does not restore it, so a later
    fade-in faded in nothing (he sank into the bed). `play()` sets the weight to 1 first.
  - `touch()` now also keeps bone positions (the hips move for weight shifts).

## Evidence
All frames are from headless Chromium (SwiftShader WebGL) driving the page in `?debug&nolive`. The rAF loop is frozen
and the page's own `sim()` steps him, so every case is exactly reproducible. Scripts are in `tools/` here.

- `strip_<case>.jpg` (after) and `before/strip_<case>.jpg` (main before this PR): one frame every 0.5 s, for order_food,
  phone, phone lying, window (the walk there and the lean), get_delivery (whole, and the door close up), eating a meal
  and bread, and 2 minutes at the window and at the desk (one frame every 4 s).
- `webm/<case>.webm` (after): 10 fps, the same cases.
- `screens/*_1280.png`, `screens/*_390.png`: the whole page at the window, eating, on the phone and listening to music.
- **Penetration** (the #42 check, every skinned vertex inside the bed or the chair): `penetration_sweep.txt`.
  PENETRATION_PLACEHOLDER
- **Performance** (mid phone profile: 390×844, DPR 2, CPU ×4 by CDP): `perf.txt`. PERF_PLACEHOLDER

## Not done here (part 2, and server side)
- Real dishes matching `delivery.dish`; bread, courier and konbini bags; the dish emptying; the container into the bin;
  labels naming the dish. That needs a small `life.py` change (LABEL and the dish field), so it is its own PR.
- No server change is needed for part 1.
