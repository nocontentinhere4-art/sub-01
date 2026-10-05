# Character v4: the owner's Tripo head on the Tripo body (first pass)

AI-generated content, used under Tripo's terms of service. The character is an original fictional ~20-year-old man, not
a real person, with no brands or logos. Preview only: nothing here is used by the live site.

- **Head:** made by the owner on the Tripo website (a Tripo GLB of 1.98M triangles with 4K PBR textures). The raw file
  is not in the repository because of its size.
- **Body, rig and clips:** v3 (`../char-tripo-v3/`): Tripo multiview body, Tripo biped rig (41 bones, no finger bones),
  Tripo `idle` and `walk`, matte clothes (roughness 0.8).

## `char_tripo_v4.glb`

5.8 MB (meshopt and WebP), 1.75 m, faces +X, `idle` (15.4 s) and `walk` (2.37 s, in place). Two materials: the body
(base colour 4096 px, normal 2048 px) and the owner's head (base colour 4096 px, normal 2048 px).

## How the graft was done (scripts in `room_build/char_v4/`)

1. **Cut** (`stage1.py`, run with Blender's Python module): the owner's collar is removed with a smooth slanted plane
   just above its collar line. Skin in front of the ears is always kept, so the jaw is whole. Loose fragments are
   dropped (after welding by position).
2. **Fit:** the head is turned 90° about Y (it faced +Z; the body faces +X) and scaled by 0.166 and moved so that the
   chin-to-nose and nose-to-crown distances and the nose tip match the body's own head.
3. **Decimate** (`simp.mjs`): meshopt simplification from 1.52M to 50k triangles. It respects UV seams, so the
   owner's own base colour and normal maps still fit and are used unchanged. No baking was needed, and the face is not
   reshaped or repainted.
4. **Skin** (`weights.py`): the head's joints and weights come from the 4 nearest vertices of the body's old head and
   neck (inverse-distance blend). The whole head ends up on `Head`.
5. **Body** (`weights.py`): the body's old face, skin and hair above the same cut plane are removed, plus old hair
   within 2 cm of the new head. The hood is kept. The body's remaining neck skin is tinted to the owner's neck tone
   (body texture only, in the neck UV area). Assembled with `graft.mjs` (one skinned mesh, two primitives), then
   `MATTE=0.8 node room_build/build_char_tripo.mjs`.

## Status

`qa/quick_preview.webp`: front, 3/4, profile, an idle frame and a walk frame at face distance, and the full body. The
face is the owner's, unchanged. The head follows the neck in both clips.

Known issue: the neck seam under the chin is still visible from the front and 3/4, as a jagged edge where the owner's
short neck (it ended at his collar) meets the body's neck. The profile is clean. Next: extend the head's neck edge down
into the hood so the seam sits under the hood.
