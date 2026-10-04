# Short black hair for the MakeHuman default head (preview)

A first, crude pass: short, slightly messy black hair with a fringe, as layered alpha cards grown procedurally on
the MakeHuman default base mesh (hm08, CC0, `makehuman/data/3dobjs/base.obj` in
github.com/makehumancommunity/makehuman; its `LICENSE.ASSETS.md` is CC0 1.0). No other assets are used: the strand
texture is drawn by `hair_tex.js`.

- `hair_sheet.png`: front, 3/4, side and back close-ups; the head 2.2 m away through room.html's 30-degree lens at
  1:1 pixels, and that whole 1280x800 frame at half size. Locked camera, neutral light, plain stand-in skin.
- `hair_mh.glb`: `hair_cards` (about 1350 narrow cards, 6.9k triangles, the 2048 px atlas embedded) and
  `hair_scalp` (a dark shell 0.6 mm off the skin, vertex alpha fading over ~1.4 cm across the hairline). Metres, in
  the base mesh's own frame: face toward +z, origin at the body's middle, crown at y = 0.849 (MakeHuman's feet are at
  y = -0.845). A body built from other MakeHuman targets needs the cards refitted (re-run with that head) or
  parented to the head bone.
- `hair_atlas.png`: the strand atlas (8 columns: dense, medium, wisps; thin, half-transparent hairs placed toward
  each column's middle so a card has no hard side edge), roots at the top. Cards carry a slight per-card brown-black
  tint and baked occlusion in their vertex colours; sides and nape shorten toward the hairline so they taper into
  the skin.

In three.js call `setupHair(THREE, gltf.scene)` from `hair_material.js` after loading: glTF has no
alpha-to-coverage, so the file carries an alpha-MASK fallback. setupHair turns on alpha-to-coverage (needs the
antialiased renderer room.html already has; no sorting, soft see-through tips) and an alpha boost per mip level so
the strands hold up at a distance. The anisotropic highlight along the strands is KHR_materials_anisotropy, which is
in the file.

Rebuild (a few seconds of CPU, software GL):

    python3 extract_head.py makehuman/data/3dobjs/base.obj head.json
    # in a folder with three@0.169.0 and playwright-core installed:
    node room_build/hair_mh/render.mjs head.json node_modules/three out/
