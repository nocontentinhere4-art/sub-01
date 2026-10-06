# Mixamo (and, next, CMU) clips on v5

## Sources and licences

Mixamo clips (mixamo.com, Adobe) are used under Mixamo's terms. They are royalty-free, including commercial use, but the raw animation files may not be redistributed on their own.
- The raw FBX files stay in scratch and are never committed by this pipeline.
- Only the clips retargeted onto v5 and baked are committed (`web/room/mh_v5/*.glb`).

CMU motion capture: data obtained from mocap.cs.cmu.edu. It is free for research and for inclusion in commercial products, but may not be resold, even converted. The same rule applies: the raw BVH stays out of git.

## Pipeline: one path for every source

- `room_build/kimodo/mixamo_src.mjs` reads a Mixamo FBX (Binary, Without Skin) and writes a source in the MakeHuman clips' conventions:
  - MakeHuman bone names, with the finger chains mapped onto v5's `finger1..5-1..3`
  - the rest pose made world-aligned
  - metres, facing +Z
- `room_build/kimodo/mh_retarget.mjs` is the shared retarget (G14's, extended). It applies:
  - the bone map, rest alignment and wrist/ankle IK
  - `{"scale":"hip"}`: scale by the hip joints' rest height over the ankles
  - `pitch`: the torso tipped forward off a backrest
- `room_build/kimodo_g12/post.py` fits a seated clip onto OUR chair:
  - the hips' joint at `seatHipY` over the floor
  - `seatForward`, so the knees clear the cushion's front edge
  - the soles `soleUp` over the floor (the slides under his socks)
  - resting hands `handUp` off his thighs
  - the feet planted by leg IK
- `room_build/kimodo/mixamo_clips.json` holds one row per clip (the fit is data). `room_build/kimodo/mixamo_build.sh <Clip> <work dir>` builds it.
- `room_build/kimodo/contact_pass.mjs` runs over the whole clip in the room (room.html?debug), every frame, every 2nd skin vertex. It checks the chair, the seat cushion, the desk and nearby furniture, the floor (each sole's gap to what supports it), the bed, and his hands and fingers against his own thighs. Results are reported per body region.

## Seated_Idle: the first clip end to end

The clip is `web/room/mh_v5/room_seated_idle.glb`: 4.17 s, 126 frames, 79 joints including the fingers. The page does not load it yet; wiring it is the page's (G10d's) part.

Contact pass, 8.3 s (two loops), in the desk slot, against our chair, desk and bed and his legs:

| region | before: main's seated idle (desk_watch) | after: Mixamo Seated_Idle |
|---|---|---|
| chair (inside) | legs 1.8 cm (18 verts) | legs 2.5 cm (241 verts) |
| seat (thighs/buttocks vs cushion top) | lowest gap -0.8…4.2 cm | lowest gap -2…2.7 cm |
| desk | hands 1.5 cm (41 verts); arms 1.5 cm (15 verts) | clear |
| other furniture | arms 1.5 cm (101 verts); hands 1.5 cm (24 verts) | clear |
| floor | clear | clear |
| bed | clear | clear |
| soles over the floor | L 9.1…13.9, R 5.3…10.4 cm | L 0.1…4.8, R -0.2…4.5 cm |
| hands in his thighs | 0 verts, 0 cm | 0 verts, 0 cm |

- The remaining seat and chair numbers are his thighs settling up to 2–2.5 cm into the cushion (light cushion give).
- The backrest, desk, floor and bed are clear.
- His hands are clear of his thighs over the whole clip.
- His hands rest where the performer's did. The performer's armrests are at our armrests' height and spacing (about 0.69 m and ±0.30 m against our 0.67 m and ±0.30 m), so the hands come down onto the armrests and knees rather than into the legs.

Fit for our chair, measured in the room rather than guessed:
- the hips' joint 0.68 m over the floor, where main's seated poses put it (0.677)
- forward 4.5 cm off the backrest, with the knees beyond the cushion's front edge
- the spine tipped forward 10°
- the soles 2.7 cm up for the slides
- resting hands 1.2 cm off the thighs

Sheets:
- `seated_idle_room_before_after.jpg` (the page's camera)
- `seated_idle_side_back_before_after.jpg` (beside and behind the chair)

Before: main's seated idle, feet hovering 5–14 cm. After: on the seat, feet on the floor, hands on the armrests and knees.

## A note for the page's wiring

`boy_mh.js` swaps in the mouse clip's legs when the watch clip's feet start more than 0.12 m up. Seated_Idle's ankles sit 2.7 cm higher for the slides, which trips that test. So the test here plays it with that swap off, and the wiring should do the same for these clips (or give them their own slot).

## The bed set: what the three captures are, and how they sit on our bed

The page does not place a lying clip by its own pose. It turns and moves him by a reference pose (asleep: `room_bedtime`'s end; lying awake: `room_bed_lie`'s end). So `room_build/kimodo_g12/bed_fit.py` does two things for each clip:
- puts the clip's hips and heading on the reference's;
- holds his lowest skin at the reference's level in every frame, so the page's once-a-second lift never steps (he turns over in Sleeping_Idle).

All three clips loop on their own: the first and last frames match within 1.3°.

| clip (out) | what it actually is | bed penetration | hands in his thighs | feet vs the mattress end (x −0.21) | notes |
|---|---|---|---|---|---|
| Sleeping_Idle → `room_sleeping_idle.glb` | 17.6 s; curled on his side; turns over and back (head 85°, arms 100°) | 0 (whole clip) | 0 | inside (−0.27…−0.37) | the turns carry his head 33 cm off the pillow, and the duvet balloons over the moving arms (`sleeping_idle_room.jpg`) |
| Laying_Sleeping → `room_laying_sleeping.glb` | 1.7 s loop; on his back, breathing (spine/neck 3–4°) | 0 | 0 | **12–18 cm past** (−0.09 / −0.03) | head on the pillow, hands on his chest under the duvet |
| Laying_Nodding → `room_laying_nodding.glb` | 1.43 s loop; on his back, hands clasped on his chest, a 5° nod | 0 | 0 | **12–18 cm past** | for lying awake (`laying_sleeping_nodding_room.jpg`) |

He is 1.75 m and the mattress is 1.65 m, so a straight-legged lying capture overhangs its end whatever the retarget does.

Decisions (COORD A):
- **The mattress gets longer** (a real single bed, about 1.90–1.95 m). That is the room's fix and G10d's. Until it lands, the overhang stays as it is, named here and not patched. The captured legs are not bent to hide it.
- **Laying_Sleeping is the sleep loop.** On his back, breathing, head on the pillow, hands on his chest.
- **Sleeping_Idle is a rare night event**, not the base. It is in the same family as Scared, Angry_Gesture and Standing_Clap: it fires occasionally and never twice close together. Its acceptance criteria when it is wired: his head does not leave the pillow by 33 cm; his arm does not come up out of the covers; the duvet follows the turn instead of ballooning. If the duvet cannot follow a 100° arm sweep and an 85° head turn, the event is cut.
- **The hands are answered by the captures alone.** In Laying_Sleeping and Laying_Nodding his hands rest on his chest, not dead at his sides. No hand motion is invented anywhere (the hand clip was rejected).

## The desk transitions

Built with the seated fit (`web/room/mh_v5/room_mx_*.glb`). The hip lift reaches 0.27–0.29 m because the performer's chair is lower (his hips at 0.41 m); the cap is an option, set to 0.45 m.

### Stand_To_Sit and Sit_To_Stand in the page's sit-down and stand-up steps

Measured in the page's own steps: `room_sit_down` / `room_stand_up` served as these clips, `contact_pass.mjs <port> "window>research" 4` (sit down) and `"research>window" 4` (stand up), sampled from the moment the page's pose step begins.

| region | sit down: main | sit down: Stand_To_Sit | stand up: main (`room_stand_up`) | stand up: Sit_To_Stand |
|---|---|---|---|---|
| chair (inside) | legs 2.9 cm (155 verts); hands 1.3 cm | legs 3.3 cm (1182 verts, as he lands); arms 1.1 cm (2 verts) | legs 4.1 cm (769); feet 3.8 cm | legs 3.4 cm (809) |
| seat (thighs/buttocks vs cushion top) | -1.5 cm lowest | -2.9 cm lowest (as he lands) | -4.7 cm | -2.5 cm |
| desk | hands 1.5 cm (2 frames) | hands 1.5 cm (6 frames), arms 1.5 cm (3 frames) | clear | clear |
| soles over the floor | L -0.2…9.3, R -0.2…5.8 cm | L -0.2…9.4, R -0.2…5.9 cm | L **-2.1**…13.2, R -0.2…9.7 cm | L -0.2…10.6, R -0.2…7.4 cm |
| hands vs his thighs | 61 frames, 11 cm | 45 frames, 13.4 cm | 62 frames, 9 cm | 112 frames, 14.7 cm |

- The soles' maxima are the steps (a foot lifted while he turns into the chair), not hovering.
- "Hands vs his thighs" in a transition is his hands on his thighs as he lowers or pushes himself (the performers of both main's clip and Mixamo's do it). The capsule is measured from his baggy trousers (radius up to 16 cm), so a fist resting on the cloth reads as deep. The close-ups show the fist on the trousers, not in the leg. This row is only a hard gate for the seated loops.

Three fixes, all in the build, all data or general rules:
- **The cushion stops him.** Mixamo's performer drops onto a lower seat, so he dipped 2.4 cm under his seated height as he landed (seat -3.8 cm), and in Sit_To_Stand the hips sank while he leaned forward to rise. post.py now holds the hips at no lower than the seat height whenever they are over the seat. That was keyed to the hips' position, not to "seated" by head height, because the performer's head is low while he bends forward to sit or rise. The lift is not spread early, so the descent is not held up before he lands. Seated_Idle rebuilds byte for byte.
- **`seatOrigin`** (row option): the page places these two clips by its chair (`chairPlace`), with the seat centre at the clip's origin as in `room_stand_up`. The clip is moved along the floor so his hips are there at the join (a sit-down's last frame, a stand-up's first). Before this, the sit-down ended 6.8 cm to the side of where the seated loop then put him; now it ends 0.6 cm away.
- **`trim`** (row option): Mixamo's Sit_To_Stand runs on past the act. Over its last 6 frames his hips drop 20 cm as if sitting back down, so the row keeps 0–2.07 s.

What the page does around them (main's clips do the same; reported, not changed):
- Leaving the desk on the live page is not `room_stand_up`. It is the one-take get-up from `room_bedtime` (`flow()`), so Sit_To_Stand only plays if the wiring gives it that step. These numbers are measured with the get-up take switched off in a test copy of `boy_mh.js`. For the record, the live get-up measures chair legs 13.7 cm, torso 9.2 cm into the chair, seat -10 cm and soles to -3 cm.
- At the start of the sit-down, the cross-fade from the walk carries his root 45 cm in 0.2 s (main: 26 cm). The walk ends where it ends for main's clip, and Mixamo's performer starts standing further from the seat (0.43 m in front of it, main's 0.27 m). The walk's end belongs with the clip's standing start, in the wiring.
- At the end of the stand-up without the get-up take, the page's standing pose is about 30 cm from where either clip leaves him, and he slides there in the fade.

Sheets: `sit_down_before_after.jpg` and `stand_up_before_after.jpg` (behind the bed, every 0.2 s).

### Typing: decided, waiting on the page's resolver

Typing has its own contact row (the `keys` row of the contact pass: his fingertip skin over the room keyboard against its key tops, every frame). How it was found:
- **main's typing (live):** fingertips 0.5…1.1 cm *over* the key tops, touching within 5 mm in 0 of 180 frames. He has been typing on air. No test caught it, because the gate only looked for penetration and a hovering hand penetrates nothing.
- **Mixamo Typing as retargeted:** fingertips 10.4–19.5 cm under the key tops. The performer typed at a lower desk.
- **with only the wrists moved onto our keyboard** (9 cm back, 11.5 cm up, eased in by reach): -10.1…-2.8 cm, and the forearms run through the desk's front edge.

The decision (COORD A): one mechanism, in the page, owned by G14. Nothing is baked into the clip. These three clips are now built without a keyboard fit. The resolver maps the performer's keyboard point onto ours and settles the whole arm chain (shoulder, elbow, wrist, fingers) onto the desk. Moving the wrists alone puts the elbow through the desk edge.

The performer's keyboard point, from `room_mx_typing.glb` over its 16.5 s. It is the mean of the last finger joints (index to little), in the clip's frame: +x forward, y up, z to the side, with the hips' joint at (0.071, 0.680, -0.001).
- left hand: (0.534, 0.679, -0.152), steady (sd 0.5 / 1.7 / 0.5 cm); 0.463 m in front of the hips, level with them
- right hand: (0.564, 0.707, 0.095), but it wanders sideways (sd 13.6 cm across the keyboard)
- our key tops are at 0.84 m over the floor in the same frame (1.001 in the room), so the resolver lifts the hands about 16 cm
