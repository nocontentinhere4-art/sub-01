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

1. **Fit** (`stage1.py`, run with Blender's Python module, `NOCOLLAR=1 STRETCH=2.5 BACKY=0.26`):
   - **Collar removed.** The owner's own hood collar is dropped: his non-skin parts below the jaw line. His neck then
     ends along the smooth line where his collar met it. Only the largest piece is kept, so no loose collar bits remain.
   - **Placed.** The head is turned 90° about Y (it faced +Z; the body faces +X), then scaled by 0.166 and moved so
     that the chin-to-nose and nose-to-crown distances and the nose tip match the body's own head.
   - **Neck lengthened.** Only the neck band below the chin (in front) and below the hairline (at the back) is
     stretched downward with a linear falloff, so the neck runs down inside the body's hood. The face and hair are not
     moved.
2. **Decimate** (`simp.mjs`): meshopt simplification to 60k triangles. It respects UV seams, so the owner's own base
   colour and normal maps fit unchanged. No baking, reshaping or repainting of the head.
3. **Skin** (`weights_full.py`): the joints and weights come from the 4 nearest body vertices (head, neck, upper spine,
   clavicles), with an inverse-distance blend.
4. **Body** (`weights_full.py`):
   - **Removed:** the body's old face and neck skin, all body skin around the neck and the hood's V, and its old hair
     near the new head.
   - **Kept:** the body's hood, whole and unchanged in shape, so its edge is the body's own smooth edge.
   - **Recoloured:** any skin-toned or bright texels on the hoodie triangles around the neck now use the hoodie's
     median colour, so no pink is left on the hoodie. This touches the body texture only.
5. Assembled with `graft.mjs` (one skinned mesh, two primitives), then `MATTE=0.8 node room_build/build_char_tripo.mjs`.

## QA

- `qa/quick_preview.webp`: front, 3/4 and profile at face distance, an idle frame, a walk frame, and the full body.
- `qa/neck_seam.webp`: the neck and hood from the front, 3/4, side and back.
- `qa/anim_face.webp`: two idle and two walk frames at face distance.

His neck runs continuously into the body's hood from every angle and in the clips. There is no collar overlap and no
skin colour on the hoodie. Left: a few small light-grey flecks of the hood's lining at the bottom of the V, and a
couple of tiny dark specks near the jaw at close range.

Likeness: the face is the owner's own Tripo head, unchanged.
