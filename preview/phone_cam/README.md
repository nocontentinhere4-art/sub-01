# The camera when he is on his phone: before / after (#103)

The coordinator's live check (2026-10-05 09:10 Tokyo): on his phone at the desk chair the shot sat almost inside his
back, at 1280x800 and at 390x844 about 80 % hoodie and shoulder, neither the phone nor his face.

The cause: the phone shot (main's, and #103's "over") stood 0.42 m behind his head, 0.45 m to his right and 0.38 m
up, a fixed over-the-shoulder at ~0.72 m. From any pose where his back is to the room that is his hood and shoulder;
while the camera dollies in from the previous shot it passes through his back.

The fix (`web/room.html`, camera block):
- `bodyBlocks()`: his own body as an occluder, capsules on his bones (the torso, the shoulders, the neck and head, the
  arms), tested against the camera's line of sight to his face and to the phone;
- `phoneShot()`: the phone shot searches [angle, distance, height] round him, front three-quarters first (1.2 m off,
  a little above his head), then his side a little behind it (1.3-1.5 m: the desk chair, where the desk and the wall
  are in front of him), the open side of the bed when he lies; the first that clears the walls, the furniture, the
  room's meshes (the desk lamp beside the monitor), his body, his hands and the phone, at least 0.95 m from his head
  and not behind where his head points. If none clears everything: his face clear first, then 0.95 m off with the room
  clear. The settled position is kept while it clears, and through a second's failure (a glance up, a hand passing);
- the face shot tests his body too, and on the phone never sits behind his face: with no clear angle it uses the
  phone shot's search instead (the desk chair).

`before_after_desktop.jpg` and `before_after_phone.jpg`: each pose (the desk chair, the bed's edge, lying in bed,
standing), left main (the live page, its one phone shot), right #103's phone shot after the fix, with the camera's
distance to his head, the share of the frame his body covers, and whether the lines of sight to his face and to the
phone are clear. Rendered by `tests/room_phone_shots.py` (main with `--root` a main checkout); all of #103's phone
shots pass (both lines clear, >= 0.8 m, his body under 45 % of the frame) at both sizes. The face shots: all pass at
1280x800; at 390x844 the tall frame hands most of them to the overview, as before, and standing his hand covers the
phone from the front (his face is clear).

This folder is a preview: it goes before #103's squash-merge, with `preview/skin_eyes/`.
