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
  welded body** (decimated to ~3k triangles, same skin weights, every texel pointing at a white, alpha 0 band of the
  cloth atlas; the slides material is alpha-masked, so the proxy is never drawn and casts no shadow). `slidesInit` then
  finds exactly the real slide triangles (dark), as it did on the old single mesh, and `bedInit` sees every bone's
  vertices.

## Checks and sheets
    node render/compare.mjs work/boy_old.glb out/boy.glb out/compare    # every clip at the same frames, old vs new, + close-ups
    node render/room_shots.mjs out/room new out/boy.glb                 # /room at 1280 and 390, day and night (software WebGL)
    python -m pytest tests/test_boy_glb.py                               # rig, clip, budgets, primitive order, eye nodes
`render/view.html` + `render/shot.mjs` is a small three.js r169 harness (same loader and meshopt decoder as the page).

## Licences and credits
Everything here is original work for this project (CC0), derived from the project's own AI-generated character. No
outside asset was downloaded. The face crop was upscaled with Higgsfield's image upscaler (three runs, 6 credits: one
test, one failed at full atlas size, one kept); see `web/room/CREDITS.md`.

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
- Hair cards: the hair is the original sculpted spike shell with smooth normals, strand normal map and a glossier,
  clumpier roughness; a card-based haircut would change the silhouette the owner chose.
