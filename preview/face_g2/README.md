# The dressed G2 character's face (#98, G6)

The owner's verdict on the dressed character (preview/room-mh): the base MakeHuman face, pale and grey like plastic,
no pores, no colour in the cheeks or the lips, painted brows, no lashes, flat eyes. This folder rebuilds it on that
very model (preview/room-mh's `web/room/boy.glb`, the same file as clothes-mh's `boy_g2_dressed.glb`), without
touching its skeleton, rest pose or vertex order, so its clips and clothes stay valid.

`face_sheet.jpg`: BEFORE (as room-mh draws it today: the glTF's own materials, vertex colours and one roughness) and
AFTER, front, three-quarter and side under the room's daylight colours (the sun 0xfff0dc through the window on his
left, the sky 0xe4ecff, the walls' warm bounce), with the same hair (hair_mh.glb and its strand shader); on the right,
three details of AFTER beside real photos of the same detail.

- `face.js`: `dressFace(THREE, root)`, which runs `../skin_eyes/body.js`'s `dressBody` (the skin: warm light-medium
  albedo with redness on the nose, cheeks and ears and a darker ring round the eyes, the lips' colour, pores and a
  fine furrow net as per-pixel relief, roughness by region with a tighter T-zone, a red-wrapping soft terminator and
  thin-skin translucency, a faint sheen; the eyes: a detailed iris, a sclera that is not white, a wet cornea that
  reflects the room, the lids' shadow on the ball, the tear line, the caruncle, the lashes as curved strands on the
  lid's visible edge) and adds the eyebrows as real strands (thin tapered ribbons rooted on the skin along each
  brow's arc: up at the head, outward along the body, outward and down at the tail; dark brown like his hair).
- `face.html`: the scene and the shots; `render_face.py`: serves this folder's parent, reads the character, its hair
  and the hair shader from `preview/room-mh` with `git show` (nothing of them is copied here), renders the sheet.

Second round (the coordinator's notes on 3fcb539):
- the brows: ~900 strands a side, full and upward at the head, denser in the body, thinning at the tail, a straight
  low man's line, the roots crowding the middle so no outline is drawn, a darker base on the skin under them;
- the lashes: longer (to 8.6 mm), denser, darker and thicker at the root, leaning forward so from the front they read
  as a dark fringe; a few sparse lower ones. They and the lash line are rooted on the lids' edges as the camera sees
  them (`refitLashes`: down each column across the eye, where the first thing a ray from the front hits turns from the
  lid's skin to the ball), not where the coarse lid rims cross the ball (there they floated above the lid line);
- the skin: deeper pores (deepest on the nose), a stronger furrow net, faint light marks and darker flecks, a
  day's stubble on the chin, the upper lip and along the jaw (a blue-grey shadow and dots where the hairs come
  through), a sharper, smaller highlight on the nose and the forehead;
- the lips: fine vertical lines, a lighter vermilion border, a dark mouth line, darker corners, a wet lower lip;
- the eyes: a darker limbal ring, more iris detail, a slightly larger iris, relaxed upper lids (the orbicularis03 lid
  bones turned so the lids come down ~0.6 mm, before the lashes and tear lines are fitted);
- the face's shape (for G2 to bake: `face_shape_delta.json`, {vertex index: [dx, dy, dz]} in the mesh's bind space):
  a firmer, wider jaw and a stronger chin, a little more cheekbone, less fat in the lower cheek, a firmer nose bridge;
  the neck, the ears, the skull and the eyes keep their places (the hair and the clothes stay valid).

The blink and the small movements (`info.blink` from `dressFace`; `update(dt)` each frame, `set(closure)` for a still):
each upper lid's bone (orbicularis03 L/R) turns the lid down over the ball, the full turn found by bisection so the
middle of the upper lid's edge meets the lower lid's (0.42 rad); the upper lash line and lashes are moved under that
bone, so they close with the lid. A blink every 3 to 6 s, now and then a double one: 80 ms down, 40 ms shut, 150 ms up.
The eyes make a small saccade every 1 to 3 s (a degree or two) and come back toward the middle. `blink_strip.jpg`: the
lids 0, 50 and 100 % closed. (The head-only preview's per-pixel lash band is off here: drawn in the skin's bind space,
it rode down the lid as a dark patch in a blink; the lash line is geometry now.)

Real references (cropped on the detail, no face shown; Pexels licence, free to use and modify,
https://www.pexels.com/license/): `refs/lips.jpg` from "Close Up Photo of Man's Lip",
https://www.pexels.com/photo/3749984/; `refs/brow.jpg` from "Close-Up of a Person's Eye",
https://www.pexels.com/photo/4823600/ (the brow and the top of the eye); `refs/stubble.jpg` from "Close-up Photo of the
Beard of a Man", https://www.pexels.com/photo/13072564/ (the jaw, black and white); the eye and the skin are `../skin_eyes/refs/eye.jpg` (946727) and
`../skin_eyes/refs/skin.jpg` (4046562), listed in `../skin_eyes/README.md`.

The character is fictional, an adult of about 20; no scan or likeness of a real person is used.

This folder is a preview on feature/gl-render: it is removed before #103's squash-merge, with `preview/skin_eyes/`
and `preview/phone_cam/`.
