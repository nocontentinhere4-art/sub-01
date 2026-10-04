# Short black hair for the MakeHuman default head (preview)

A short textured-fringe cut as layered hair cards, grown procedurally on the MakeHuman default base mesh (hm08, CC0,
`makehuman/data/3dobjs/base.obj` in github.com/makehumancommunity/makehuman; its `LICENSE.ASSETS.md` is CC0 1.0).
No other assets: every texture is drawn by `hair_tex.js`. Real references studied (not copied, no photos kept): the
textured-fringe guides on latest-hairstyles.com and luxe.digital (the Korean-style short fringe), and the real-time
hair-card write-ups on 80.lv and gamesartist.co.uk.

## The sheet (`hair_sheet.png`), view by view

Top row, left to right; then bottom row. Locked camera, neutral light, plain stand-in skin, no text on the sheet.

- **Front:** the fringe is brought forward in small, separate, point-cut pieces that stop just above the brows,
  with the forehead showing through the gaps (the Korean-style short fringe).
- **3/4:** about 5 cm on top with choppy texture and a slight sweep to his right, over a tight taper at the temple.
  Scalp shadow shows through where the taper meets the skin.
- **Side:** sides tapered short and tight to the head (1-2 cm at the weight line, under 1 cm at the hairline), the
  ear fully clear, with the longer top sitting above the weight line. Nothing hangs over the ear.
- **Back:** hair grows from the crown's whorl. The back tapers down to a short, soft nape edge that fades into the skin
  through the painted scalp layer, with no blunt line.
- **2.2 m, 1:1 pixels:** the head as room.html's 30-degree lens sees it: a dark black-brown cap with a broken fringe
  line and lighter temples.
- **2.2 m, whole frame (half size):** the same shot in context.

## Technique (after the references)

- **Atlas** (2048 px, `hair_atlas.png` + `hair_data.png`): 8 columns, running from dense clumps through looser clumps to
  sparse strands and single hairs. The colour atlas uses natural black-brown (#1b1512 base, never pure black) with
  per-strand variation and alpha thinning to see-through tips. The data atlas holds R = depth/occlusion, G = per-strand
  ID and B = the root-to-tip gradient.
- **Layers:**
  1. A painted scalp base (`hair_scalp.png`): short dark strokes laid along the growth direction, feathered across
     the hairline.
  2. Opaque base cards hugging the scalp on top.
  3. More transparent mid cards, then the fringe pieces and the choppy top pieces.
  4. A few flyaways.
  5. Sparse single-hair cards on the taper.

  Cards are 0.4-1.4 cm wide and follow the growth direction from the crown whorl.
- **Shading** (`hair_material.js`, `setupHair()`): alpha-to-coverage (no sorting) plus two Kajiya-Kay lobes along the
  strand tangent. The primary is narrow, near-white and shifted toward the root. The secondary is broad, dim, tinted
  brown and shifted toward the tip. Both are jittered by the strand ID and dimmed by depth.
- **Numbers:** about 1450 cards, 7.2k triangles, plus 0.6k for the scalp shell.

## Files

- `hair_mh.glb`: `hair_cards` and `hair_scalp`, all textures embedded. Units are metres, in the base mesh's own frame:
  face toward +z, origin at the body's middle, crown at y = 0.849 (MakeHuman's feet are at y = -0.845). Cards carry
  TANGENT (the strand direction) and COLOR_0 (occlusion and tint). glTF can't hold alpha-to-coverage or the hair
  shader, so call `setupHair(THREE, gltf.scene)` after loading. Without it you get a plain alpha-MASK fallback.
- A body built from other MakeHuman targets needs the cards refitted: re-run with that head, or parent the hair to
  the head bone.

## Known leftovers

- A few dark pieces show at the crown whorl from behind.
- The top's silhouette is a little spiky.

## Rebuild

A few seconds of CPU, software GL:

    python3 extract_head.py makehuman/data/3dobjs/base.obj head.json
    # in a folder with three@0.169.0 and playwright-core installed:
    node room_build/hair_mh/render.mjs head.json node_modules/three out/
