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

Real references (cropped on the detail, no face shown; Pexels licence, free to use and modify,
https://www.pexels.com/license/): `refs/lips.jpg` from "Close Up Photo of Man's Lip",
https://www.pexels.com/photo/3749984/; the eye and the skin are `../skin_eyes/refs/eye.jpg` (946727) and
`../skin_eyes/refs/skin.jpg` (4046562), listed in `../skin_eyes/README.md`.

The character is fictional, an adult of about 20; no scan or likeness of a real person is used.

This folder is a preview on feature/gl-render: it is removed before #103's squash-merge, with `preview/skin_eyes/`
and `preview/phone_cam/`.
