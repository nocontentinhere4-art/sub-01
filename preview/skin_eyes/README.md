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

Third pass ("as realistic as possible"): the pores are dense, soft pits sized by region (about 1.4 mm apart on the
nose and inner cheeks, 0.9 mm on the forehead and temples), not sparse specks; the T-zone (forehead, nose, chin)
carries a stronger, tighter specular, like sebum under a window; the tear line on the lower lid is wetter (a brighter
clearcoat highlight) and stays on the lid margin.

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

## On G2's body, beside real photos

`body_sheet.jpg`: G2's final body (`room_build/mh/glb/boy_g2.glb` on `preview/mh-motion`, rest pose) with this skin,
these eyes and the hands, each row the render on the left and a real photo on the right at a similar angle and light:
an eye, a cheek patch, the back of the right hand, the fingertips and nails.

- `body.js`: `dressBody(THREE, gltf.scene)`. The skeleton, the rest pose and the vertex order are not touched (G2's
  clips stay valid): the skin gets this material and three vertex attributes (colour, `skinData`, `handData`), all in
  the mesh's bind-pose space so they move with it; G2's eye primitive is hidden and these eyes, lash and tear lines are
  parented to the `Head` bone, at the centres of G2's eyeballs.
- The hands (`handData`, and `sk_hand` in `skin_eyes.js`): each finger vertex knows where it sits along its finger (by
  phalanx, from the finger bones), across it and toward the back of the hand (the hand's plane from its vertices, the
  side from the thumb). Per pixel: the nail plate on the last phalanx (a curved cuticle, a pink bed, a paler lunula at
  its base, a whitish free edge, a glossy thin coat), a darker, drier rim round it, fine creases over the joints on the
  back and deep ones on the pad side, a slightly darker, pinker skin over the knuckles, redder fingertips.
- `body.html` shoots the four panels; `render_body.py` serves the glb straight from G2's branch (`git show`, no copy
  committed here), renders them and puts each beside its crop in `refs/`.

Fourth pass (the coordinator's read of the first body sheet: "still plastic"):
- colour: a warmer base; a blotchy redness a few cm across (stronger where the regions are already red); a wider,
  redder wrap past the terminator; the fingers are marked thin, so light behind them comes through red;
- the back of the hand: bowed crease lines over each finger joint, deeper; the tendons over the metacarpals and a few
  veins as relief; fine dark hairs on the back of the hands and the forearms (short strands drawn per pixel along
  the arm, sparse; a faint tint once they are thinner than a pixel); the knuckles, fingertips and the pad side of the
  fingers redder;
- the eye: upper and lower lash strands (curved ribbons, longest toward the outer corner) rooted on the visible lid
  edge, found where the lids' triangles cross the ball; the cornea reflects the room's environment map, not only the
  lights; a wetter, pinker line on the lower lid; a pinker inner corner and a larger caruncle;
- the nails: the bed is the finger's own skin a little pinker (less contrast), a paler lunula, an off-white, uneven
  free edge, a soft shadow where the cuticle fold meets the plate.

Where it still differs from the photos: the hand is still paler than the photo's (an older man's hand; the agreed
tone is kept, only the zones are redder); the photo's eye is a macro with a big room reflection on the cornea; there
is no hair on the face. The head-only sheet (`sheet.jpg`, a mesh closed over the eyes) has no lash strands: its lids
have no edge to root them on.

Real references (`refs/`, cropped and scaled to 900x675; no face is shown), all under the Pexels licence (free to use,
modify and share, no attribution required; https://www.pexels.com/license/):

| crop | photo | source |
|---|---|---|
| `refs/eye.jpg` | "Brown Human Eye" | https://www.pexels.com/photo/946727/ |
| `refs/skin.jpg` | "A Person's Skin In Close-up View" | https://www.pexels.com/photo/4046562/ |
| `refs/hand.jpg` | "Close-Up Photo of a Person's Hand" | https://www.pexels.com/photo/7298848/ |
| `refs/nails.jpg` | "Human's Fingers in Close Up Photography" | https://www.pexels.com/photo/7479569/ |

Sources and licences: the base mesh is MakeHuman 1.x `makehuman/data/3dobjs/base.obj` from
github.com/makehumancommunity/makehuman. Its `LICENSE.md` section C puts the base mesh, proxies, targets and textures
under CC0 1.0 (full text in `LICENSE.ASSETS.md`). No texture is used: the iris, the colour variation and the pores are
computed here and are CC0 too. three.js (MIT) loads from jsDelivr.
