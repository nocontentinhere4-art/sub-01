# Character from Tripo

AI-generated content: the model, its textures, rig and clips were made with Tripo (tripo3d.ai, paid API) and are used
under Tripo's terms of service. The character is an original fictional ~20-year-old man, not a real person, with no
brands or logos. Preview only: nothing here is used by the live site.

## Reference images

The owner's reference views, generated earlier with Higgsfield image models. They were the inputs for the Tripo multiview
image-to-model task.

- `refs/body_front.png`, `refs/body_back.png`: full body, A-pose, 2048 px.
- `refs/body_side_left.png`: profile with his left side to the camera (he looks toward the left edge of the image). This
  is Tripo's `left` slot.
- `refs/body_side_right.png`: profile with his right side to the camera (he looks toward the right edge of the image).
  This is Tripo's `right` slot.
- `refs/face_front.png`, `refs/face_3q_a.png` (looks image-left), `refs/face_3q_b.png` (looks image-right): face
  close-ups, 1024 px, used for the face comparison.

## The model: `char_tripo.glb`

2.51 MB (meshopt and WebP). It holds one skinned mesh, a 41-bone skeleton, and two clips, `idle` (15.4 s) and `walk`
(2.37 s, in place). He faces +X, stands on y = 0 and is 1.75 m tall.

- 147,598 triangles and 79,801 vertices, one material: PBR base colour, normal and metal/roughness.
- The base colour is 4096 px (kept for the face). Normal and metal/roughness are 2048 px. That is about 134 MB of GPU
  memory with mipmaps; dropping the base colour to 2048 px brings it to about 67 MB.
- Built with `node room_build/build_char_tripo.mjs <dir>` from Tripo's two retarget GLBs. The build merges the two
  clips, scales the figure to 1.75 m (Tripo outputs him 0.98 units tall), and compresses it. It also removes the walk's
  forward drift: Tripo's walk carries the Hip 1.33 units forward although the task asked for `animate_in_place`.

### Tripo tasks (2026-10-05): 105 credits

| step | task id | settings | credits |
|---|---|---|---|
| multiview to model | `06424338-3984-4e5a-bb2b-5917b00ec237` | model v3.1-20260211, geometry detailed, face limit 150k, texture v3.5-20260815 detailed (HD), PBR | 60 |
| rig check | `a5b722b2-09c2-439f-a6ad-3fd624af3262` | riggable, biped | 0 |
| rig | `b4e321c0-fb42-480b-a01e-dc68eab91ca8` | rig v1.0-20240301, biped, spec tripo, glb | 25 |
| retarget idle | `4a3f4c27-403c-42a6-9981-691a4c5932d6` | `preset:idle` | 10 |
| retarget walk | `59aac7f6-6506-4a76-bae5-763051545960` | `preset:walk` (in place requested, not honoured) | 10 |

Balance: 1680 before, 1575 after. The script is `room_build/tripo_char.py`; the proxy supplies the key.

## Bones (Tripo spec, 41 joints, no finger bones)

Tripo's humanoid rig, `v1.0-20240301`, offers no finger bones and no finger option. The `mixamo` spec cannot be
retargeted by Tripo, so `tripo` was used. The hands are one rigid piece each, bound to `L_Hand` and `R_Hand`. Hierarchy:

```
Root
  Hip
    Pelvis
      L_Thigh > L_Calf > L_Foot > L_ToeBase
              L_Calf > L_CalfTwist01 > L_CalfTwist02
              L_ThighTwist01 > L_ThighTwist02
      R_Thigh > R_Calf > R_Foot > R_ToeBase
              R_Calf > R_CalfTwist01 > R_CalfTwist02
              R_ThighTwist01 > R_ThighTwist02
    Waist > Spine01 > Spine02
      Spine02 > NeckTwist01 > NeckTwist02 > Head
      Spine02 > L_Clavicle > L_Upperarm > L_Forearm > L_Hand
                             L_Upperarm > L_UpperarmTwist01 > L_UpperarmTwist02
                                          L_Forearm > L_ForearmTwist01 > L_ForearmTwist02
      Spine02 > R_Clavicle > R_Upperarm > R_Forearm > R_Hand
                             R_Upperarm > R_UpperarmTwist01 > R_UpperarmTwist02
                                          R_Forearm > R_ForearmTwist01 > R_ForearmTwist02
```

For Rokoko mocap clips (reading, stretch, sit), map Rokoko's body bones as follows. Leave the twist bones at rest or
drive them as fractions of the forearm/upper-arm/thigh/calf roll. Rokoko's finger channels have nowhere to go.

| Rokoko | Tripo |
|---|---|
| Hips | Hip |
| Spine | Waist |
| Spine1 | Spine01 |
| Spine2 / Spine3 | Spine02 |
| Neck | NeckTwist01 (+ NeckTwist02) |
| Head | Head |
| Left/RightShoulder | L/R_Clavicle |
| Left/RightArm | L/R_Upperarm |
| Left/RightForeArm | L/R_Forearm |
| Left/RightHand | L/R_Hand |
| Left/RightUpLeg | L/R_Thigh |
| Left/RightLeg | L/R_Calf |
| Left/RightFoot | L/R_Foot |
| Left/RightToe | L/R_ToeBase |

## Quality check

Rendered with three.js in headless Chromium (SwiftShader), lit by a room environment and one key light:

- `qa/body_compare.webp`: references (top) against the model (bottom), front, left, back and right.
- `qa/face_compare.webp`: each reference next to the model at the same angle: front, 3/4 a, 3/4 b, and both profiles
  (the profiles are cropped from the side body views, since there is no profile face close-up).
- `qa/mouth.webp`: a mouth close-up.
- `qa/hands.webp`: both hands.
- `qa/anim_frames.webp`: idle at 0, 3, 6, 9 and 12 s, then the walk at six phases from 3/4, from the side, and close
  on the hips and hands.

To redraw: `node room_build/char_tripo_shots.mjs <glb> <dir> room_build/char_tripo_shots.json`, then
`python room_build/char_tripo_sheets.py <dir> <out>` (with `npm i` in `room_build/`).

### Scores (honest, out of 5)

| check | score | notes |
|---|---|---|
| mouth symmetric | 4 | The lips are even and centred, with one corner very slightly lower. Better than the Meshy/Higgsfield baseline's uneven mouth. |
| hair not a noisy block | 3 | The hair is sculpted into clumps that follow the reference's shape, not noise. But it reads as a glossy helmet with no fine strands. Dark hair colour bleeds onto the skin at his left temple and forehead (3/4 a view). |
| hands and fingers | 4 / rig 0 | Five separate, clean fingers with knuckles, and no webbing or fused stumps. No finger bones, though, so the fingers can't curl (see Bones). |
| texture seams | 3 | No UV seams on the body or the back. Problems: the temple bleed above; the white trouser stripe has ragged edges; the hoodie and trousers are too glossy (satin rather than fleece and cotton, from low roughness in the metal/roughness map). |
| skin through clothes in the walk | 5 | None seen. The body is a single surface with no skin under the clothes, so nothing can poke through; the cuffs and wrists bend together. |
| likeness to the face references | 2 | The face reads older and broader-jawed than the references. The eyes are light grey instead of dark brown. Up close the face is visibly faceted: the 147.6k triangles are spread over the whole body. |

Proportions: a little stockier than the references (wider hips and hoodie). Triangles: 147,598. File: 2.51 MB.
