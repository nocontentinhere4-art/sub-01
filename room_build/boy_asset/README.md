# `web/room/boy.glb`: the character, rebuilt in place (#98, G2)

The character on `/room` is the original AI-generated mesh (Meshy, via Higgsfield): same face, black messy hair, grey
hoodie, black track pants with the white stripe, slides with white socks. This directory rebuilds it at game quality
**without touching the rig**: the 24 bones, their names, rest pose and inverse bind matrices, and the embedded sit clip
are copied from the shipped file byte for byte, so `boy_*.glb` and `web/room.html` keep working unchanged.

## What changed in the asset
| | before | after |
|---|---|---|
| mesh | 35,483 vertices split along every one of ~4,400 UV islands, baked flat normals (the facets) | welded (15.5k), smooth normals, the head skin, hands, socks and slides subdivided once, the hair shards rounded a little (28k vertices, 55k triangles) |
| UVs | one 2048 atlas of thousands of 5–40 px islands (black between them: the dark slivers by the nose) | three atlases: skin 2048 (the face is one island, ~1000 px wide), hair 1024, cloth 2048 |
| materials | one, metallic 1, emissive baked in | skin (sheen, pores, cut-out eye openings), hair, hoodie (fleece knit, sheen), pants (nylon weave, sheen), socks (ribbed), slides (foam); eyeball + cornea (clearcoat) and eyelid |
| textures | base colour only (with Meshy's glossy highlights painted into the pants) | base colour (the pants de-lit to matte cloth), tangent normal map (pores, finger grooves, strands, knit, weave, ribs), occlusion + roughness per atlas; the face upscaled once with an AI upscaler |
| eyes | painted on the face | eyeball meshes behind the cut-out openings, iris, pupil, limbal ring, glossy cornea; eyelid caps |
| size | 960 KB | 1.7 MB (budget 3 MB); 55k + 2×1.1k triangles (budget 80k) |

## Pipeline (all headless)
    node ../decode.mjs ../../web/room/boy.glb work/boy_raw.glb        # drop meshopt for Blender (run from room_build/)
    node inspect.mjs work/boy_raw.glb work                             # writes work/tex0.webp; convert it to work/tex_old.png
    blender -b -P build_mesh.py                                        # ~3 min on 4 CPU cores: weld, label, subdivide, UVs, bakes
    python make_textures.py                                            # textures, eye openings, eyeball, spec.json (numpy, Pillow, scipy)
    node assemble.mjs --install                                        # rig from the original + new mesh and materials -> web/room/boy.glb

`build_mesh.py` (Blender 4.2): welds the seam-split mesh, pads the old atlas so that no seam samples black, labels every
face skin / hair / hoodie / pants / socks / slides from the old texture colour + bone weights + height (majority vote,
small islands absorbed), rounds the hair shards (two mild smoothing passes), subdivides the head skin, the hands, the
socks and the slides once with the region boundaries creased (no cracks against the neighbours), writes a `hand_uv`
frame per hand (PCA of its vertices: across the palm, along the fingers) for the finger grooves,
unwraps the head skin as one island (ABF) and Smart-projects the rest, packs three atlases, then bakes with Cycles on the
CPU: the old colour through the old UVs, object-space position and normal buffers (to find the eyes), tangent normal maps
and roughness from procedural object-space materials (pores, finger grooves, strands, knit, weave, ribs, foam; seamless
across islands because they are 3D), ambient occlusion, and a region-id map of the cloth atlas. `make_textures.py` cleans
the painted slivers, blends the upscaled face back in (only when `work/face_up4k.json` matches the current crop: the UV
packing can move the island), de-lights the pants (highlights compressed towards the cloth's base tone, the stripe kept),
cuts the eye openings into the
skin's alpha (MASK; never wider than the eyeball behind), draws the eyeball and the lid, packs occlusion + roughness, and
writes `out/spec.json` (eyeball centres in metres, glTF axes). `assemble.mjs` writes the mesh back into the original's
quantised vertex space (`p = IBM_orig⁻¹ · IBM_blender · p_blender`, checked on all 24 joints), remaps joints by name,
adds the eye nodes under the `Head` joint, and compresses (meshopt + WebP).

The room page multiplies every material's `roughness` by 0.78 (`room.html`'s loader): the roughness maps are written as
wanted / 0.78. It also zeroes `emissive` and sets `envMapIntensity` 0.5; nothing here relies on either.

## Eyes and eyelids (for the motion layer, G3)
Under the `Head` joint, four plain nodes (not skin joints: clips without tracks for them leave them alone; the
#80 retargeting is unaffected because the 24-joint skin is unchanged):
- `LeftEye`, `RightEye`: at the eyeball centres. Their axes are the **world axes at rest** (x his left, y up, z the way
  he faces; the inverse of Head's rest rotation is baked into them), so `node.rotation.y` is yaw (positive = he looks to
  his left) and `node.rotation.x` is pitch (positive = down), in radians; keep them within about ±0.35 rad. The child
  `LeftEyeball` carries the two primitives (ball, cornea) and the tilt that aims the iris along the face at rest.
- `LeftEyelid`, `RightEyelid`: same placement; the child `LeftEyelidCap` is a cap of a slightly larger sphere, resting
  rotated up into the head. **Blink = rotate the `LeftEyelid` node about its x axis**: 0 is open, `+0.9 rad` (about
  52°) is fully closed (`spec.lid.openAngle − closedAngle`); a relaxed half-lid is `+0.3`. A blink is ~60 ms down, 120 ms up.
- The openings are cut out of the face texture (alpha MASK); there are no blendshapes. The painted lash lines stay on the
  skin, so the lid cap only has to cover the opening.
- `room.html` finds the body's skinned meshes by `isSkinnedMesh`; the eye meshes are plain meshes. The phone-grip hand
  cloud (`handVertices`) takes the **first** skinned mesh (the skin primitive, as before). The bed code from #107
  (`bedInit`: how thick he is around each bone, for the duvet and the pillow; `slidesInit` / `setSlides`: the slide
  triangles, dark texels on the feet, hidden on him and parked by the bed; the `?debug` helpers) takes the **last**
  skinned mesh as his whole body. So the last primitive is the slides **plus an invisible low-poly proxy of the whole
  welded body** (decimated to ~3k triangles, same skin weights, its triangles written degenerate (a, a, a) so the rasteriser
  never draws them at any mip level; the page only reads its vertices). `slidesInit` then
  finds exactly the real slide triangles (dark), as it did on the old single mesh, and `bedInit` sees every bone's
  vertices.

## The photoreal face (the owner's "fallo bene")
Upscaling the painted face kept its painted look. The face is now **repainted**: `bl_views.py render` renders the head
unlit from three known cameras (front, left and right three-quarter); each view goes to an image model
(Higgsfield, GPT Image 2.5, the frontal result as the identity reference for the other two) with the instruction to keep
the same person, pose, framing and flat lighting and render real skin; `align_paint.py` finds 468 face landmarks on the
render and on the repaint (MediaPipe Face Landmarker, Apache-2.0, build tool only, model file downloaded into `work/`)
and warps the repaint onto the render (piecewise affine); `bl_views.py project` bakes the atlas texels' world position
and normal and renders a depth map per camera; `project_paint.py` projects every texel into each camera, keeps it
only where it is the surface the camera sees (depth within 4 mm), weights by facing², samples the aligned repaint and
blends the views. `make_textures.py` uses that where it is confident (the face island), colour-matches the rest of the
old skin (neck, ears, hands) to it, keeps the old skin where the repaint's fuller hair would land on skin, and cuts the
eye openings as before. The result is the same character with real skin: pores, real brows and lashes, natural lips.
Credits: 3 generations (about 4.5 credits) + the upscale tests; see `web/room/CREDITS.md`.

    blender -b -P bl_views.py -- render        # work/views/{front,left,right}.png + cameras.json
    # repaint each view with the image model -> work/views/<view>_gen.png (front first; pass it as the identity reference)
    python align_paint.py front; python align_paint.py left; python align_paint.py right
    blender -b -P bl_views.py -- project       # wpos/wnrm bakes + depth maps
    python project_paint.py                    # work/skin_projected.png + mask, read by make_textures.py

The forehead under the bangs is skin: the repaint's fuller hair had painted it grey-brown there, and the mesh showed
that between its hair spikes as grey "strands"; above the brow line every texel that is not skin-coloured is filled from
the skin around it (the real strands are the hair primitive, black). Strands the label votes had absorbed into the face
(thin spikes whose old paint was scalp-pink) are found in `build_mesh.py` by a ray test (a ray cast inward leaves a
spike through its back within 1 cm; from the forehead, the nose or an ear it does not) and labelled hair.

## The clothes (the owner's "anche i vestiti")
The same repaint was tried on the whole body: `bl_body_views.py render` (four unlit views, front / back / left / right,
1536 px), four repaints (Higgsfield, GPT Image 2.5, about 6 credits), `align_body.py` (silhouette fit + dense optical
flow, since there are no landmarks on cloth) and `project_paint.py --body` (the cloth atlas and the skin atlas, depth
test 8 mm, facing > 0.25). The tools stay here and work, the result does not ship: a repaint of a lit body bakes its
lighting and its folds into the albedo, and those folds are the picture's, not the mesh's, so under the room's lights
and in motion the clothes looked printed; at 1536 px for 1.8 m the hands are 80 px, and the repaint's hair shadows
landed on the throat. Game clothes are not photographed, they are authored: `make_textures.py` now builds the cloth
albedo as fabric **materials**, a flat dyed base per garment with fibre-scale variation only (heathered jersey for the
hoodie at the old render's tone, lum 0.13; black polyester for the pants with the white stripe taken from the old atlas,
cleaned; white cotton socks; black EVA slides), and leaves the shading to the lights, the baked occlusion and the knit /
weave / rib normal maps. The projected repaint is read only as a tone reference (printed by the script).

The feet are one shell in Meshy's remesh (the slide's strap and the pants' cuff are bulges of the sock), so a label per
triangle draws the sock's edge as a zigzag of triangle edges. `build_mesh.py` re-reads every foot face from the covered
texels inside its own old UV triangle (the padded atlas had painted the strap's sliver islands white), and
`make_textures.py` paints the sock whole inside the sock faces and, inside the slide's and the cuff's faces, only where
the old paint has a solid white patch (the sock's edge crossing a triangle); the atlas texels' height for that comes
from the build (`work/posz_cloth.npy`).

    blender -b -P bl_body_views.py -- render   # work/body/{front,back,left,right}.png + cameras.json
    # repaint each view -> work/body/<view>_gen.png;  python align_body.py <view>  (x4)
    blender -b -P bl_body_views.py -- project; python project_paint.py --body     # work/cloth_projected.png (reference)

## Checks and sheets
    node render/compare.mjs work/boy_old.glb out/boy.glb out/compare    # every clip at the same frames, old vs new, + close-ups
    node render/room_shots.mjs out/room new out/boy.glb                 # /room at 1280 and 390, day and night (software WebGL)
    python -m pytest tests/test_boy_glb.py                               # rig, clip, budgets, primitive order, eye nodes
`render/view.html` + `render/shot.mjs` is a small three.js r169 harness (same loader and meshopt decoder as the page).

## Licences and credits
Everything here is original work for this project (CC0), derived from the project's own AI-generated character. No
outside asset was downloaded. The face crop was upscaled with Higgsfield's image upscaler (three runs, 6 credits: one
test, one failed at full atlas size, one kept); the face repaint took 3 generations (about 4.5 credits) and the body
repaint trial 4 (about 6 credits, reference only); see `web/room/CREDITS.md`.

## Texture anisotropy (for the coordinator / G6)
Texture anisotropy is a three.js texture property, not something a glTF file can carry. The room's own loader sets it
(`room.html`, `o.material.map.anisotropy = aniso` in the room block); the character's loader block
(`load("room/boy.glb")`, the `boy.traverse` that zeroes `emissive`) does not. One line there does it for every map:
`for (const t of [m.map, m.normalMap, m.roughnessMap, m.metalnessMap, m.aoMap]) if (t) t.anisotropy = aniso;`

## Not done
- Finger bones: the hands are closed mitten shapes (now subdivided, with four finger grooves in the normal map); real fingers would need new hand geometry
  skinned to 30 new joints, and the phone grip in `room.html` collapses the `RightHand` bone into the sleeve and attaches
  `hand_phone.glb` instead, so fingers would only show on the left hand and in the idle clips. Left for a later pass
  (the rig allows it: new joints can be appended as children of `LeftHand` / `RightHand` the way the eye nodes were added).
- Hair cards: the hair is the original sculpted spike shell (silhouette untouched, shard edges kept sharp), strand normal
  map and a clumpier roughness; a card-based haircut would change the silhouette the owner chose.
