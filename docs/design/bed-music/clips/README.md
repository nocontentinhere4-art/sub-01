# Lying on the bed, awake, listening to music (G12's clips)

The owner's note: in bed he looked "like a dead man". He should look relaxed and move his head a bit, or do a small hand dance while lying down.
The page held `mh_lie` for "listen", a still of `room_bed_lie`'s last frame, which is the flat sleep pose.
The sleep pose is settled and does not change (asleep at night still uses `room_bedtime`'s end).
These three clips are the awake state. The motion is baked into them; G10d's layer does the headphones only.

| file (`web/room/mh_v5/`) | length | plays | starts on | ends on |
|---|---|---|---|---|
| `room_bed_music_in.glb` | 2.6 s | once | `room_bed_lie`'s last frame (exactly) | the loop's first frame (exactly) |
| `room_bed_music.glb` | 8.0 s | loop | — | its own first frame (seamless) |
| `room_bed_music_out.glb` | 2.2 s | once | the loop's first frame (exactly) | `room_bed_wake`'s first frame, as `bedPlace` places it (exactly) |

The three clips use the same rig and conventions as the other `mh_v5` clips: 80 tracks, Root at rest, Hip translation.
All three keep `room_bed_lie`'s end hips and heading, so `seg.bedLie` places them.

## The pose

- The right arm is flung up beside the head, elbow bent, hand palm up on the pillow by the temple.
- The left forearm lies across the stomach.
- The right knee is drawn up, its foot flat on the mattress.
- The left leg is long and loose: rolled out, knee slightly bent so the heel rests.
- The head is propped toward the chest and turned toward the room.

"Hand behind the head" was tried and dropped, because v5's stiff hood bulges behind the neck and swallows the hand.

## The motion

The loop is 90 bpm, 12 beats per 8 s.

- The head bobs on each beat, sways slowly side to side, and rolls a little every two beats.
- The left hand taps on the stomach (0–3.7 s), lifts from the elbow and dances loose at the wrist to the beat (3.7–7.8 s), then settles back.
- The left foot taps on the beat.
- The raised knee drifts out and back.

## Contacts

These were measured in the room with `room.html?debug`, `live("listen_music")`, a ray cast down from his lowest skin of each part, and `penetration()`.

| part | gap to the surface under it |
|---|---|
| right sole | 0.4 cm (duvet) |
| left heel | 0.6 cm (duvet) |
| left calf | 1.7 cm (duvet) |
| right calf | 2.0 cm (duvet) |
| right hand | 1.3 cm (pillow) |
| back | rests about 2 cm into the mattress (within the page's give) |

`penetration()` is 0 over the loop.

His lowest skin is held at the flat pose's level in every frame of all three clips, using a vertical move of the Hip.
The page lifts him by his lowest skin and re-measures it only once a second while he lies still.
Because the level is held, the lift stays at bed_lie's value through in → loop → out (0.2149–0.2154 m, against 0.2153 m on main).
So nothing steps, and the hood never dips between two measurements.

## For the page (G10d)

- Wire "listen" only: in once, then the loop, then out before the bed_wake step.
- Start the out when the loop's time is under 3.5 s (or wait for the wrap), so the dancing hand never drops in a 0.4 s crossfade.
- `phone_lie` / `lie_phone` are left as they are.

## Stills

| file | what it shows |
|---|---|
| `loop_room_camera.jpg` | the page's camera, cropped to the bed, one bar of the loop |
| `loop_near.jpg` | close, from the foot of the bed |
| `loop_head_end.jpg` | from the desk side by the pillow |
| `mattress_level.jpg` | eye level with the mattress (he lies on it) |
| `in.jpg` / `out.jpg` | the two transitions |

The generator is `room_build/kimodo_g12/music.py`.
