# G14: v5 sat deeper and centred on the owner's chair (clear of the arm pads)

Measured in the page (room-v5 + `tests/visual/contacts --chair-regions`, and a probe of his hips in the chair's frame,
`page_probe.json`): before, his hips sat 7.4-13 cm to his right of the seat's centre (eat 13), so the right thigh's
trousers (outer side at x ~ +0.27 m) went into the right arm pad (pads at x ~ +-0.26 m, y 0.63-0.67, z -0.13 ... +0.11 in
the chair's frame), and 5-7 cm further forward on the seat than the backrest fit in G14's clips assumes.

One pass, then one lateral calibration in the page:
- the clips (web/room/mh_v5, mh_retarget.mjs `shift` / `handShift`): hips and feet 6 cm back on the seat and re-centred
  to his left (type / mouse / watch 1.4-1.7 cm, read 0.6, phone 2.0, eat 7.0: the page's own placement moves him by part
  of it); in read / phone / phone_scroll / eat his hands and the world props (room/mh/props_g2.json) move with him; type /
  mouse keep their hands (the page re-pins them to the keys / mouse anyway);
- the page (`env.seatIn` 0.06 in room.html, boy_mh.js roll()): the chair rolls 6 cm further in at the desk.

Result in the page (max depth, mm, per region of the chair; `contacts_regions.json`, typing re-run with the scenario that
types: `contacts_typing.json`):

| scenario | hips in chair frame x / z (m), before -> after | arm pads | seat cushion | seat front | elbows L / R (deg) |
|---|---|---|---|---|---|
| desk typing / mouse | +0.077 / -0.052 -> 0.000 / -0.006 | 18 (left thigh, first try) -> 0 | 23 | 18 | 53 / 60 (before 57 / 54) |
| room_read | +0.066 / -0.089 -> 0.000 / -0.043 | 12 -> 0 | 18 | 7 | 119 / 87 (unchanged) |
| room_phone, phone_scroll | +0.080 / -0.146 -> 0.000 / -0.100 | 14 -> 0 | 8 | 3 | 73 / 88 (unchanged) |
| eating at the desk | +0.130 / -0.113 -> 0.000 / -0.123 | 29 -> 0 | 3 | 3 | 46 / 89 (unchanged) |

No contact with the arm pads, posts, backrest or base in any seated scenario of G14's clips. Left: cushion compression up
to 23 mm (typing, right thigh) and the seat front 18 mm; the page's mouse re-pin puts the right hand 13 mm into the mouse
in the typing scenario. The elbow angles at the desk are the page's wrist re-pin onto the room's keyboard (unchanged by this
pass; not 100-115 deg: flagged). Stills: `*_side.png`, `all_side.jpg` (G14's render scene with the chair where the page has
it relative to his hips; read, type, mouse, watch / phone, phone_scroll, eat).
