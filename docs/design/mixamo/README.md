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
