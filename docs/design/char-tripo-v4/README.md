# Character v4: the owner's Tripo head on the Tripo body (first pass)

AI-generated content, used under Tripo's terms of service. The character is an original fictional ~20-year-old man, not
a real person, with no brands or logos. Preview only: nothing here is used by the live site.

- **Head:** made by the owner on the Tripo website (a Tripo GLB of 1.98M triangles with 4K PBR textures). The raw file
  is not in the repository because of its size.
- **Body, rig and clips:** v3 (`../char-tripo-v3/`): Tripo multiview body, Tripo biped rig (41 bones, no finger bones),
  Tripo `idle` and `walk`, matte clothes (roughness 0.8).

## `char_tripo_v4.glb`

5.9 MB (meshopt and WebP), 1.75 m, faces +X, `idle` (15.4 s) and `walk` (2.37 s, in place). Two materials: the body
(base colour 4096 px, normal 2048 px) and the owner's head (base colour 4096 px, normal 2048 px). Both are matte
(roughness 0.8, metalness 0).

## How the graft was done (scripts in `room_build/char_v4/`)

The owner's head is kept whole, as in his Tripo web view: face, hair, his full neck, and his own hood collar. That is
what makes the neck continuous with no seam.

1. **Fit** (`stage1.py`, run with Blender's Python module, `FULL=1 STRETCH=1.5`): the head is turned 90° about Y (it
   faced +Z; the body faces +X), then scaled by 0.166 and moved so that the chin-to-nose and nose-to-crown distances
   and the nose tip match the body's own head. The band below his chin (lower neck and collar, below 8% of the head
   model's height) is stretched downward with a linear falloff, so the bottom of his collar sinks into the body's hood.
   The face and everything above the chin are not moved.
2. **Decimate** (`simp.mjs`): meshopt simplification from 1.98M to 60k triangles. It respects UV seams, so the owner's
   own base colour and normal maps fit unchanged. No baking, reshaping or repainting.
3. **Skin** (`weights_full.py`): the joints and weights come from the 4 nearest vertices of the body (head, neck,
   upper spine and clavicles), with an inverse-distance blend. The face and hair follow `Head`; his collar follows the
   clavicles and neck, like the body's hood.
4. **Body** (`weights_full.py`): the body's old head, its hair, and its neck skin above 0.80 (Tripo units) are
   removed. The hood is kept. Assembled with `graft.mjs` (one skinned mesh, two primitives), then
   `MATTE=0.8 node room_build/build_char_tripo.mjs`.

## QA

- `qa/quick_preview.webp`: front, 3/4 and profile at face distance, an idle frame, a walk frame, and the full body.
- `qa/neck_seam.webp`: the neck and hood from the front, 3/4, side and back.
- `qa/anim_face.webp`: two idle and two walk frames at face distance.

The neck is continuous into the hood from the front, 3/4 and profile, and in the idle and walk frames. Remaining small
flaws:

- In profile and from behind, where his collar overlaps the body's hood, the hood top has some darker blotches.
- At the bottom of the hood's V-neck there is a small light chip of the body's lining.

Likeness: the face is the owner's own Tripo head, unchanged.
