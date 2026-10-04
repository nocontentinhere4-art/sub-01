# Living idles: he does something now and then, and sits up (#63)

What the coordinator saw on the live site: in 5 minutes at the desk he never moved beyond typing, hunched and static. No
drink, no stretch, no look around.

He did have idle variants (#63 part 1), and they did play — 57 in 10 minutes at the desk. But at the default camera
(the whole room at 1280 × 720, where he is about 120 px tall, mostly from behind) a scratch, a knee bounce, a hand on
the mouse or a lean of a few degrees doesn't read, and #114's motion layer keeps a reclined back out of the desk chair,
so the "lean back" was undone. He also sat hunched: the typing clip leans him over the keyboard.

Everything is in `web/room.html`, in the activity / pose block (the idle variants, `alive()`, `holdPhone()`, the drink),
plus one name map passed to #114's motion layer (below). `web/room/boy_motion.js`, the camera and the lighting are
untouched.

## 1. Audit: how static each activity reads (main, default camera, 1280)
Measured by `tools/audit.mjs`: each activity for 180 s (seed 63), his head, hands and chest projected through the
default camera at 10 Hz. *still*: the share of 2 s windows in which none of them moves more than 3 px. *acts*: visible
actions per minute (a hand or the head more than 30 px from where it usually is for at least 1 s; typing, the mouse,
breathing and glances stay under that). *away*: the share of the time he is in one. Asleep is meant to be still and is
left out of the ranking.

| rank | activity | still | acts / min | away | what reads from across the room |
|---|---|---|---|---|---|
| 1 | listening to music, lying | 1.00 | 0 | 0 | nothing: lies flat, a foot taps |
| 2 | phone, lying in bed | 0.76 | 0 | 0 | the thumb only |
| 3 | ordering food (phone, bed edge) | 0.63 | 1.3 | 0.06 | the thumb, a glance up |
| 4 | phone on the bed edge | 0.60 | 0 | 0 | the thumb only |
| 5 | at the window | 0.54 | 2.7 | 0.13 | leans on the sill, chin on hand now and then |
| 6 | playing chess / watching a video | 0.42–0.44 | 2.3 | 0.10–0.13 | typing and the mouse; idles too small to read |
| 7 | reading / chat / the chart | 0.26–0.31 | 1–1.3 | 0.04–0.10 | the same, hunched over the keys |
| 8 | eating | 0.11–0.23 | 5.3–5.7 | 0.31–0.32 | bites: the most alive |

## 2. What changed

**Two kinds of idle** (`ACTS`, `FIDGETS`, `variants()`):
- *actions*, every 25–75 s, never the same as the last one, sized to read at the default camera:

  | where | actions |
  |---|---|
  | desk | sip from the bottle (the hand to it, it to his lips, tipped), lean back with his hands behind his head and look at the screen, turn in the chair to look out of the window, check the phone, roll his neck and shoulders with a hand on his nape, rub his eyes, stretch |
  | window | stretch, rub his eyes, roll his neck |
  | bed edge, with the phone | the phone down in his lap and a look out of the window, rub his eyes, roll his neck |
  | lying, with the phone | the phone down on his chest, face to the ceiling; rub his eyes |
  | lying, with music | hands behind his head; rub his eyes |
  | standing | stretch, the phone, rub his eyes, roll his neck |

- *fidgets* in between, every 4–11 s: a glance, a scratch, resettling in the chair (a lean onto one hip and back), a
  knee bounce, the mouse, chin on hand at the window, a knee up / a foot tapping lying down.

**Tired and bored bias the actions** (`tiredness()`, `BIAS`). Tired — late in his day (from 21:00, fully by midnight,
and before 05:00) and the longer he has sat at the screen (fully after 40 min) — he rubs his eyes, stretches and rolls
his neck more, and leans back more. Bored (the life model's `boredom`) he looks out of the window, checks the phone and
leans back more. The life state has no fatigue of its own; the clock and the time at the desk stand in for it.

**He sits up at the desk.** The typing clip hunches him over the keys; `alive()` now brings his back to a touch forward of
vertical (0.15 rad, the most #114's `sitUp` lets the desk chair's back have), where it used to take off only 30 % of
the hunch.

**#114's motion layer and the new idles.** The layer puts his hands on the keys unless the variant playing is one it
knows by name. The new ones that need his hands are reported to it under one of those names (`IV_AS`: rub and neck as
"scratch", window as "look", hands as "lean"): the one line changed in the hookup block.

**Fixed on the way** (all also on main, all in this page's own idle code):
- the standing stretch (getting up from the desk) brought his hand down into the desk chair's back (72–78 vertices):
  standing, his arms now go straight up;
- the drink never reached his mouth: the target was below `headfront`, which is at his throat, and set before the gaze
  lifts his face; and the bottle tipped away from him. Now it comes to his lips (with his face level) and tips back
  to them;
- putting the bottle down, his fingers went into the desk top (up to 98 vertices): he now holds it on its upper half,
  his hand level round it;
- leaning on the window sill, his fingers went through it into the wall below (up to 643 vertices): his wrists rest
  further back, the hands flat on it;
- eating from a dish, his right forearm touched the desk's edge (3–5 vertices): the hand over the dish is 3 cm higher.

## 3. After: the same audit on this branch (`audit.txt`)

| activity | still (main → now) | acts / min | away |
|---|---|---|---|
| listening to music, lying | 1.00 → 0.76 | 0 → 2 | 0 → 0.17 |
| phone, lying in bed | 0.76 → 0.57 | 0 → 2 | 0 → 0.14 |
| ordering food | 0.63 → 0.57 | 1.3 → 2 | 0.06 → 0.12 |
| phone on the bed edge | 0.60 → 0.43 | 0 → 2.3 | 0 → 0.17 |
| reading / chat / the chart | 0.26–0.31 → 0.31–0.39 | 1–1.3 → 1.3–2.3 | 0.04–0.10 → 0.08–0.12 |
| watching a video / chess | 0.42–0.44 → 0.52–0.53 | 2.3 → 1.7–2.3 | 0.10–0.13 → 0.08–0.12 |
| at the window | 0.54 → 0.66 | 2.7 → 1.7 | 0.13 → 0.08 |
| eating, asleep | unchanged | | |

On the bed (phone, music) he went from never moving visibly to an action every half minute or so. At the desk the
visible actions are more and longer (and they are things you can name from across the room: `after_desk_10min.jpg`),
but between them he is a little stiller than on main: main's idles there were mostly the hand on the mouse and small
spine leans, which keep a few pixels moving without reading as anything. At the window the measure drops although he
does as much (3 minutes: 18 idles here, 19 on main, with a neck roll and an eye rub added): his hands used to rest with
the fingers through the sill into the wall, and now rest on it, nearer to him, so his hand to his chin or his head
travels less far on the screen.

## 4. Evidence
From headless Chromium (SwiftShader WebGL), the page in `?debug&nolive`, its rAF loop frozen and stepped with the page's
own `animate` (the motion layer included). "before" is main at e6dfcaa, "after" is this branch.

- **10 minutes at the desk**, a frame every 20 s, default camera (1280 × 720, cropped to the desk; nothing zoomed), each
  frame labelled with the idle playing: `before_desk_10min.jpg`, `after_desk_10min.jpg` (and `.txt`). A frame every
  20 s catches only some of the actions; `after_desk_timeline.txt` has every idle of a 10-minute run (seed 63): 11
  actions, 32–73 s apart, and 49 fidgets.
- **Each action**, mid-way: `actions_desk.jpg` (a side view of the desk), `actions_window.jpg`, `actions_bed_phone.jpg`,
  `actions_bed_edge.jpg`, `actions_music.jpg` (default camera, cropped).
- **`audit.txt`**: the audit above, main and this branch.
- **`penetration.txt`**: `tools/sweep_idles.mjs`, 3 seeds: 0 bed, 0 chair and 0 wall vertices in every case. The desk
  top: 17 vertices of his left hand whenever #114's hands layer rests it on the mat beside the keys (also on main: its
  palm sits 5 mm into the top; `web/room/boy_motion.js`, G3's), and none from anything here. Every action and fidget of every context made to play
  (checked every 0.1 s), then long runs of every activity (10 min at the desk, 4 min of each other, every 0.25 s): his
  vertices in the bed, the desk chair, the desk top (new in `penetration()`: room_build's slab, 5 mm in) and the walls
  (their inner faces, the window's opening excepted). Not in it: the two #114 hits G3 is fixing, his foot through the
  bed's corner as the walk passes it (445 vertices, identical on main) and — now gone — his hand in the desk chair's back
  in the standing stretch, which was this page's stretch: standing, his arms now go straight up.
- **`perf.txt`**: `tools/perf_idles.mjs`, mid phone profile (390 × 844, DPR 2, CPU × 4): the script cost of a frame of
  him with each action playing: 0.7–1.6 ms (worst run 2.7 ms), as on main (0.75–1.5 ms), against 33 ms a frame at
  30 FPS. The real frame rate can't be measured headless (SwiftShader draws WebGL on the CPU).
- **Tests** (local; GitHub Actions is down at the account level): `pytest tests --ignore=tests/visual`: 1157 passed,
  27 skipped. `pytest tests/visual`: 5 passed. `python -m tests.visual.harness`: 0 hard failures.
- Debug (`?debug`): `IV`, `ACTS` and `FIDGETS` are exported, and `variant(name, seconds)` plays one;
  `penetration()` also returns `desk` and `wall`.
