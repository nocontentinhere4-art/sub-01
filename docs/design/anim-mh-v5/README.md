# MakeHuman room clips on v5 (fingers): seat, backrest and book-grip pass

Clips: `<clip>.glb` (v5 rig, 30 fps; v5 faces +X, root turned as in each `cfg`), `<clip>.mp4` (GPU render, 2 cameras),
`<clip>_sheet.jpg`, `<clip>_qa.json` (skin vs chair/desk/keyboard/bed every 0.1 s), `<clip>_seat_back.json` (per-frame
seat and backrest rows, every 0.1 s). `props_v5.json` = props_g2.json with room_read's book tilted 17 deg more toward the face
(about 37 deg total) and moved 8 cm closer / 2 cm up into v5's reach; the other clips use props_g2.json unchanged.

## Numbers (every 0.1 s over the whole clip)

| clip | buttock gap cm, per-frame min … max (target −0.8 … −0.3) | thigh front into seat edge, max cm (≤ 0.5) | backrest max cm into pad (skin samples > 3 mm) (0.3 … 1.0) | hips forward on seat cm | seat lift cm | result |
|---|---|---|---|---|---|---|
| room_read | -0.37 … -0.24 | 0.67 | 0.91 (96) | 12.6 | 10.5 | FLAG: buttocks, thigh |
| desk_type_ik | -0.70 … -0.36 | 0.17 | 0.67 (21) | 9.0 | 10.4 | PASS |
| desk_mouse_ik | -0.56 … -0.39 | 0.30 | 0.68 (30) | 8.3 | 10.3 | PASS |
| desk_watch | -0.54 … -0.44 | 0.00 | 0.69 (17) | 20.4 | 10.8 | PASS |
| room_phone | -0.65 … -0.34 | 0.29 | 0.70 (46) | 18.7 | 10.7 | PASS |
| room_phone_scroll | -0.65 … -0.34 | 0.29 | 0.70 (46) | 18.7 | 10.7 | PASS |
| room_eat | -1.02 … -0.31 | 1.23 | 0.70 (24) | 15.0 | 10.0 | FLAG: buttocks, thigh |
| room_drink | standing at the desk end (no seat) | – | – | – | 0 | – |

Sign convention: buttock gap < 0 = skin into the cushion; thigh / backrest values = depth into the seat front edge / the
backrest pad (mesh and lumbar pad), measured with rays along the chair's own axes.

## Method (room_build/kimodo/mh_retarget.mjs, fitall.py)

- Seated clips: spine tipped forward 15 deg (spread over Waist/Spine01/Spine02), heels lifted 8.5 cm with the balls of the
  feet kept on the floor, then ONE deterministic fit: hips forward along the seat by (backrest depth - 0.7 cm) (the chair rolls
  back under him; his world position and the desk contacts stay), seat lift corrected by (-0.55 cm - buttock gap); verified
  once. A second identical step only where the backrest was still > 1 cm (watch, phone, phone_scroll, eat), and a small
  backrest/lift step on type, mouse and watch.
- Hands: the hand is now aligned with a full basis (wrist->middle knuckle and index->little knuckle), and fingers ride the
  hand's alignment. Before, only the pointing direction was matched, so the palm twist and the finger curl axis were wrong.
- room_read grip (procedural, from the book's geometry): each palm on its half's back cover near the outer edge, fingers spread
  toward the top under the cover, the thumb over the outer edge on the page margin. For both page turns the right hand leaves
  its cover, thumb and index pinch the turning page's lower outer corner, carry it across with the page, release and come
  back. The real-photo references (Pexels license, faces pixelated) are in `refs_book/`.
- desk_type_ik / desk_mouse_ik: the hands are NOT raised with the seat (they stay on the keyboard and mouse).
- room_drink: a standing clip, placed at the desk's free end (the room has no counter); no seat fit.

Flagged: room_read (buttocks -0.24 cm at max, i.e. 0.06 cm shallower than -0.3; thigh front 0.67 cm) and room_eat (buttocks
-1.02 … -0.31 cm, thigh front 1.23 cm).
