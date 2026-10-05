# Character v4: the owner's Tripo head on the Tripo body (first pass)

AI-generated content, used under Tripo's terms of service. The character is an original fictional ~20-year-old man, not
a real person, with no brands or logos. Preview only: nothing here is used by the live site.

- **Head:** made by the owner on the Tripo website (a Tripo GLB of 1.98M triangles with 4K PBR textures). The raw file
  is not in the repository because of its size.
- **Body, rig and clips:** v3 (`../char-tripo-v3/`): Tripo multiview body, Tripo biped rig (41 bones, no finger bones),
  Tripo `idle` and `walk`, matte clothes (roughness 0.8).

## `char_tripo_v4.glb`

5.8 MB (meshopt and WebP), 1.75 m, faces +X, `idle` (15.4 s) and `walk` (2.37 s, in place). Two materials: the body
(base colour 4096 px, normal 2048 px) and the owner's head (base colour 4096 px, normal 2048 px). Both are matte
(roughness 0.8, metalness 0).

## How the graft was done (scripts in `room_build/char_v4/`)

1. **Fit** (`stage1.py`, run with Blender's Python module, `NOCOLLAR=1 LINING=1 STRETCH=0 DROPHEAD=0.011`):
   - **Collar removed.** The owner's own hood collar and its grey inner lining are dropped, so his neck ends along the
     smooth line where the collar met it. Only the largest piece is kept, so no loose collar bits remain.
   - **Placed.** The head is turned 90° about Y (it faced +Z; the body faces +X), then scaled by 0.166 and moved so that
     the chin-to-nose and nose-to-crown distances and the nose tip match the body's own head.
   - **Lowered, not stretched.** The whole head is lowered by 2 cm (0.011 Tripo units) onto the body. His neck keeps
     its natural length, as in his Tripo web view.
2. **Decimate** (`simp.mjs`): meshopt simplification to 60k triangles. It respects UV seams, so the owner's own base
   colour and normal maps fit unchanged. No baking, reshaping or repainting of the head.
3. **Inner T-shirt** (`plug.py`): a small dark fabric panel, coloured from a dark texel of his hair, sits just behind his
   neck and the hoodie front. It fills the hood's V below his neck, like a dark T-shirt neckline.
4. **Skin** (`weights_full.py`): the joints and weights come from the 4 nearest body vertices (head, neck, upper spine,
   clavicles), with an inverse-distance blend.
5. **Body** (`weights_full.py`):
   - **Removed:** the body's old face, its old hair near the new head, and stray fragments. Body skin is cut per angle
     around the neck, just below his neck's own bottom edge.
   - **Kept:** the hood, whole.
   - **Recoloured:** skin-toned texels on the hoodie around the neck take the hoodie's median colour, and the lining
     near the neck is clamped to the hoodie tone. This touches the body texture only.
6. Assembled with `graft.mjs` (one skinned mesh, two primitives), then `MATTE=0.8 node room_build/build_char_tripo.mjs`.

## QA

- `qa/quick_preview.webp`: front, 3/4 and profile at face distance, an idle frame, a walk frame, and the full body.
- `qa/neck_seam.webp`: the neck and hood from the front, 3/4, side and back.
- `qa/anim_face.webp`: two idle and two walk frames at face distance.

His neck has its natural length and goes into the body's hood, with a dark T-shirt neckline in the V. There is no
collar overlap, no skin colour on the hoodie, and no stray fragments, from the front, 3/4, side and back, and in the
idle and walk frames. Left, close up only: the inner hood rim near the neck is slightly uneven in tone at one spot.

Likeness: the face is the owner's own Tripo head, unchanged.
