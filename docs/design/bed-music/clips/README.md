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
- Both knees are up and both feet stand flat on the quilt, the legs running along the bed. He is 5 cm longer than the mattress, so his toes are held 11 cm inside its end (x ≤ −0.32 in the room; the mattress ends at −0.21).
- The head is propped toward the chest and turned toward the room.

"Hand behind the head" was tried and dropped, because v5's stiff hood bulges behind the neck and swallows the hand.

## The motion

The loop is 90 bpm, 12 beats per 8 s.

- The head bobs on each beat, sways slowly side to side, and rolls a little every two beats.
- The left hand taps on the stomach (0–3.7 s), lifts from the elbow and dances loose at the wrist to the beat (3.7–7.8 s), then settles back.
- The right foot's toes tap on the beat.
- The left knee drifts out and back.

## Contacts

These were measured in the room with `room.html?debug`, `live("listen_music")`, a ray cast down from his lowest skin of each part, and `penetration()`.

| part | gap to the surface under it |
|---|---|
| back | 0.1 cm (mattress) |
| left sole | about 3 cm into the quilt (his lowest point, within the page's give) |
| right sole | 0.8 cm (quilt) |
| calves | 1.1 / 1.8 cm (quilt) |
| right hand | 1.1 cm (pillow) |
| head | 4.8 cm over the pillow: it rests on the stiff hood (the pillow dent is the page's) |

`penetration()` is 0 over the loop. His axis runs along the bed (feet → hips 0.5°), and both foot tips stay at x −0.32 or less through the loop.

His lowest skin is held at one level in every frame of all three clips, using a vertical move of the Hip, measured on every vertex of the body the page shows (`web/room/char_v5.glb` as on this branch, with G10d's new feet).
With G10d's wiring (2da310a) the page's lift is 0.2153 m at every sample through in → loop, the same as bed_lie's on main, so he never bobs and nothing steps.

Why he looked as if he floated from the page's camera (941c316): his legs ran past the mattress end and splayed corner to corner, and nothing marks where his body meets the quilt (it does not dent, and the sun puts his shadow on the floor past the bed's end). The legs are fixed here (`legs_before_after.jpg`); the quilt dent is G10d's.

## For the page (G10d)

- "listen" only: in once, then the loop, then out before the bed_wake step; the out starts when the loop's time is under 3.5 s (wired in 2da310a).
- `phone_lie` / `lie_phone` are left as they are.

## Stills

| file | what it shows |
|---|---|
| `loop_room_camera.jpg` | the page's camera, cropped to the bed, a second apart over one bar |
| `legs_before_after.jpg` | the page's camera: 941c316's legs and the fixed ones |
| `loop_near.jpg` | close, from the foot of the bed |
| `loop_head_end.jpg` | from the desk side by the pillow |
| `mattress_level.jpg` | eye level with the mattress (he lies on it) |
| `in.jpg` / `out.jpg` | the two transitions |

The generator is `room_build/kimodo_g12/music.py`.
