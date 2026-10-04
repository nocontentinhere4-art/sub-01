# Skin and eyes: crude first sheet (#98, G6)

`sheet.jpg`: the MakeHuman base head under the room's own light colours (web/room.html). Top row by day: the sun
0xfff0dc through the window and the sky 0xe4ecff as a soft fill. Bottom row in the evening: the desk lamp 0xffb468 and
its bulb 0xffc98a behind the ear, a dim room. Left: a close-up at 0.45 m. Right: the room distance, 2.2 m with the
page's 30° lens. Locked cameras, no text. The head is bald and the body is a charcoal stand-in for the hoodie: G2, G4
and the hair session own those.

Second pass (the owner's notes on the first sheet): the shadow side's wrap is a desaturated warm instead of orange;
the redness is local (nose tip, ear rims, a small cheek patch); the base tone is less peachy; the eyeball is 0.85 of
MakeHuman's eye helper sphere (12.7 mm; the full sphere poked through the lids, which made the eyes look stuck on);
a dark lash line runs along each upper lid margin, so the eyes sit in the head.

- `skin_eyes.js`: the materials (three.js r169) and `buildHead(THREE, data)`.
  - Skin: per-channel wrap lighting past the terminator (red wraps furthest), red translucency where the skin is
    thin (ears, the nose's rim), a procedural pore bump (about 1 mm cells) that fades out once a pixel is wider than a
    pore, colour variation from landmarks found on the mesh (warmer nose, cheeks, ears, the lips, a faint mottle, the
    brow line, a darker socket ring), skin's F0 with a tighter lobe on the T-zone, a faint sheen, no clearcoat.
  - Eyes: one procedural texture for the sclera and iris (fibres, collarette, crypts, a dark limbal ring, faint
    veins), the lids' occlusion on the ball, a wet cornea drawn additively as a bulging cap, the lash line along the
    upper lid margin and the tear line along the lower one (found per 1.5 mm slice as the skin nearest the ball),
    the caruncle in the inner corner.
- `index.html`: the scene and the two views. `render_sheet.py`: renders `sheet.jpg` with headless Chromium.
- `head.json`: the head of MakeHuman's `base.obj` (the `body` group above the neck, in metres, origin at
  `joint-head`, with its UVs), and the eye centres and radius from the `helper-l-eye` / `helper-r-eye` groups.

Sources and licences: the base mesh is MakeHuman 1.x `makehuman/data/3dobjs/base.obj` from
github.com/makehumancommunity/makehuman. Its `LICENSE.md` section C puts the base mesh, proxies, targets and textures
under CC0 1.0 (full text in `LICENSE.ASSETS.md`). No texture is used: the iris, the colour variation and the pores are
computed here and are CC0 too. three.js (MIT) loads from jsDelivr.
