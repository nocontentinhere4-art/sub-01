# Character from Tripo, v3 (Tripo only)

AI-generated content: the model, its textures, rig and clips were made with Tripo (tripo3d.ai, paid API) and are used
under Tripo's terms of service. The character is an original fictional ~20-year-old man, not a real person, with no
brands or logos. Preview only: nothing here is used by the live site.

Third pass after v1 (`../char-tripo/`) and v2 (`../char-tripo-v2/`), aimed at v2's gaps: round cheeks, soft jaw, big
round eyes, broad nose tip, the lower lip pushed forward, and glossy clothes. Everything still comes from Tripo: there is
no hand painting, warping or projection.

## What changed from v2

1. **Inputs at 4096 px.** `room_build/char_tripo_refs4k.py` upscales the same four body views 2x (Lanczos, under
   Tripo's 20 MB limit) and applies a mild unsharp mask to the head region only, with a feathered edge. Framing stays the
   same in all four: a tighter front view would break the consistent scale that multiview needs.
2. **Two seeds, best kept.** Same settings as v2 (v3.1 geometry detailed, face limit 400k, texture v3.5 extreme,
   delight off, alignment original_image, PBR), with model and texture seeds 1201 (B) and 7342 (C). C was kept: it has
   the narrowest, most almond-shaped dark-brown eyes, the slimmest cheeks and jaw, and the straightest nose. B had rounder
   eyes with light hazel irises.
3. **Matte clothes.** Built with `MATTE=0.8`: Tripo's metal/roughness map (which made the fleece and cotton read as
   satin) is replaced by one roughness of 0.8 with metalness 0. This is a material setting, and the colours are
   untouched.

Not done:

- **Head pass.** A separate Tripo head grafted at the neck was skipped for time. It is the main remaining lever if the
  face must get closer.
- **Retexture with `face_front` as reference.** Tripo's texture endpoint takes a single `image` for the whole model,
  which would project a face close-up over the full body, and `style_image` only restyles. Neither targets the face.

## The model: `char_tripo_v3.glb`

4.51 MB (meshopt and WebP). One skinned mesh, the same 41-bone Tripo skeleton as v1 and v2 (no finger bones; see
`../char-tripo/README.md`), and two clips: `idle` (15.4 s) and `walk` (2.37 s, in place, with the 1.33-unit Hip drift
removed). He faces +X, stands on y = 0 and is 1.75 m tall. About 384k triangles. Base colour 4096 px, normal 2048 px, no
metal/roughness map.

Build: `MATTE=0.8 node room_build/build_char_tripo.mjs <dir> docs/design/char-tripo-v3/char_tripo_v3.glb`.

### Tripo tasks (2026-10-05): 185 credits

| step | task id | settings | credits |
|---|---|---|---|
| multiview to model, seed B (not kept) | `51282b59-d748-4b37-8f7b-4ec00d533103` | v2 settings, 4K inputs, model/texture seed 1201 | 70 |
| multiview to model, seed C (kept) | `6bf04053-4eb9-4c81-aed9-ebf290057e82` | v2 settings, 4K inputs, model/texture seed 7342 | 70 |
| rig check | `b82fe2be-112e-4f55-aa90-f226d7b2585a` | riggable, biped | 0 |
| rig | `79f590fb-8bf5-42a5-b9f4-9cfbc22bdd7b` | rig v1.0-20240301, biped, spec tripo, glb | 25 |
| retarget idle | `cc1e5ed9-1cef-4ed5-9761-a2e0ce7270d4` | `preset:idle` | 10 |
| retarget walk | `cb939e84-b3dc-441a-a33d-73452b918f28` | `preset:walk`, in place requested | 10 |

Balance: 1460 before, 1275 after.

```
python room_build/char_tripo_refs4k.py DIR/refs4k
python room_build/tripo_char.py model char_v3c --out DIR --refs DIR/refs4k --set '{"face_limit": 400000, "texture_quality": "extreme", "delight": false, "texture_alignment": "original_image", "model_seed": 7342, "texture_seed": 7342}'
```

Then `rigcheck`, `rig` and the two `retarget`s, as in v2.

## Quality check

Same cameras and lights as v1 and v2:

- `qa/face_compare.webp`: reference | v2 | v3, front, 3/4 a, 3/4 b, profile left, profile right.
- `qa/body_compare.webp`: references (top) against v3 (bottom).
- `qa/hands.webp`, `qa/anim_frames.webp`.

### Likeness to the face references: 2.5 / 5 (v2: 2.5, v1: 2)

Closer than v2:

- Eyes: narrower and more almond-shaped, with dark brown irises.
- Cheeks and jaw: slimmer; in profile the jaw line is clean, with no double chin.
- Nose: straighter and narrower.
- Clothes: matte fleece and cotton now, close to the references.

Worse than v2, or still off:

- Age: he reads a little older than v2, about mid-twenties, with darker shading under the eyes and beside the nose. The
  reference looks about 20.
- Ethnic read: the features drift a little away from the reference's East Asian look (deeper-set eyes, a stronger brow).
- Mouth: still fuller and slightly parted, and uneven at the corners; the reference mouth is closed with thin lips.
- Hair: the right shape, but still a sculpted mass with a few flat flakes on the crown.
- Hands: five clean fingers, but grey edges on the fingertips (from the black background).

Overall, the face shape is closer and the age read is weaker, so the score stays the same. Tripo's multiview gives about
this much likeness from full-body views. A Tripo head generated from the close-ups and grafted on (the head pass) is
the next step if the face must match more closely.
