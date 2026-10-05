# Character from Tripo, v2 (Tripo only)

AI-generated content: the model, its textures, rig and clips were made with Tripo (tripo3d.ai, paid API) and are used
under Tripo's terms of service. The character is an original fictional ~20-year-old man, not a real person, with no
brands or logos. Preview only: nothing here is used by the live site.

This is the second version of `docs/design/char-tripo/` (v1), made to get a face closer to the references. Every
improvement comes from Tripo's own settings: there is no hand painting, warping or photo projection. The references
are v1's, in `../char-tripo/refs/`.

## What changed from v1

Same multiview inputs (front, left, back, right: the four body views; the slot order was checked on the pixels, "left"
is the view whose nose points to image-left). Settings that differ:

| setting | v1 | v2 | why |
|---|---|---|---|
| `face_limit` | 150,000 | 400,000 (383,994 delivered) | v1's face was faceted: its triangles were spread over the whole body |
| `texture_quality` | detailed | extreme (8K base colour from Tripo) | more pixels on the face, which is small in the full-body views |
| `delight` | true (default) | false | keep the references' own skin and eye shading; v1's eyes came out light grey |
| `texture_alignment` | default | original_image (set explicitly) | prioritise the input colours |

Unchanged: geometry model v3.1-20260211, `geometry_quality` detailed, texture model v3.5-20260815, PBR on.

Tripo's retexture endpoint (`/v3/models/texture`) was not used: the remaining differences are in the geometry (cheeks,
lips, eye shape), which a retexture cannot change. Tripo's humanoid rig still has no finger bones and no finger option
(`v2.5-20260210` is for non-humanoid creatures only).

## The model: `char_tripo_v2.glb`

4.81 MB (meshopt and WebP). One skinned mesh, the same 41-bone Tripo skeleton as v1 (see `../char-tripo/README.md` for
the hierarchy and the Rokoko mapping), and two clips, `idle` (15.4 s) and `walk` (2.37 s, in place). He faces +X, stands
on y = 0 and is 1.75 m tall.

- 383,994 triangles, one material: PBR base colour 4096 px (Tripo's 8K, halved), normal and metal/roughness 2048 px.
  About 2.6x v1's triangles; if that is too heavy for phones, Tripo's retopology or a simplify pass can bring it down.
- Built with `node room_build/build_char_tripo.mjs <dir> docs/design/char-tripo-v2/char_tripo_v2.glb` from Tripo's two
  retarget GLBs (the script now scales from the measured mesh height, and takes `BASE_PX` for the base colour size). As
  in v1, the walk's forward drift (1.37 units on the Hip, although `animate_in_place` was asked) is removed.

### Tripo tasks (2026-10-05): 115 credits

| step | task id | settings | credits |
|---|---|---|---|
| multiview to model | `5ba489f4-8170-4156-8014-d2aed56c0d6f` | model v3.1-20260211, geometry detailed, face limit 400k, texture v3.5-20260815 extreme, delight off, alignment original_image, PBR | 70 |
| rig check | `b818ab3d-dcd8-4bfe-bea1-4b4f4e792c22` | riggable, biped | 0 |
| rig | `171aece3-c7cd-427c-ad02-1ca379d80075` | rig v1.0-20240301, biped, spec tripo, glb | 25 |
| retarget idle | `6fab266e-55c6-4cf3-bb24-b05e000d907c` | `preset:idle` | 10 |
| retarget walk | `b2d3ae77-1827-4ee0-ac14-b412029e7c8c` | `preset:walk`, in place requested | 10 |

Balance: 1575 before, 1460 after. Commands (the proxy supplies the key):

```
python room_build/tripo_char.py model char_v2a --out DIR --set '{"face_limit": 400000, "texture_quality": "extreme", "delight": false, "texture_alignment": "original_image"}'
python room_build/tripo_char.py rigcheck char_v2a <model_task>
python room_build/tripo_char.py rig char_rig <model_task> --out DIR
python room_build/tripo_char.py retarget char_idle <rig_task> preset:idle --out DIR
python room_build/tripo_char.py retarget char_walk <rig_task> preset:walk --in-place --out DIR
```

## Quality check

Rendered with v1's cameras, lights and scripts (`room_build/char_tripo_shots.mjs` and `char_tripo_shots.json`), so the
sheets line up with v1's:

- `qa/face_compare.webp`: same layout as v1's: reference left, v2 right; front, 3/4 a, 3/4 b, profile left, profile right.
- `qa/face_compare_v1_v2.webp`: reference, v1, v2 side by side, for picking between the two.
- `qa/body_compare.webp`: references (top) against v2 (bottom), front, left, back and right.
- `qa/hands.webp`, `qa/anim_frames.webp` (idle at 0, 3, 6, 9, 12 s; the walk at six phases from 3/4, the side, and
  close on the hips and hands).

### Likeness to the face references: 2.5 / 5 (v1: 2 / 5)

Better than v1:

- Age: he reads about 20, not v1's late twenties.
- Eyes: dark brown irises, not v1's light grey.
- Skin: smooth, no faceting on the face; the hair-colour bleed at the left temple is mostly gone (a few light strands remain).

Still different from the references:

- Face shape: rounder and fuller in the cheeks; the reference is a narrower oval with a slimmer, defined jaw. In the
  left profile the jaw-to-neck line is soft, almost a double chin.
- Eyes: larger and rounder, with a visible upper crease; the reference eyes are narrower and more almond-shaped.
- Nose: broader with a rounder tip; the reference nose is narrow and straight.
- Lips: fuller, with the lower lip pushed forward and a slight gap; the reference mouth is closed with thin, even lips.
- Hair: the right shape and length, but a glossy sculpted mass with no strands, as in v1; a few flat shiny flakes on the
  crown.
- Skin tone: a little warmer and pinker than the reference's neutral fair skin.

Body: matches the references as well as v1 (A-pose proportions, hoodie with pocket and drawstrings, white-striped
trousers, socks and slides). The hoodie and trousers are still too glossy (satin rather than fleece and cotton). Hands:
five clean fingers each, but the fingertips have grey edges from the black background, and one dark line across a
finger of the right hand. The walk and idle show no skin through the clothes.
