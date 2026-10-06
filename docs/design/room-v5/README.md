# Character v5 in the room (preview/room-v5, G10d): integration preview, nothing live

From main (56525bb: the live room, the owner's chair at the live seat height 0.505 m), with preview/room-mh's room side
merged in (0b6efe3): room/boy_mh.js (the clip player and G3's choreography: desk modes, sit / stand, the chair pulled and
pushed, routes, the bed), `mh/props_g2.json`, the page's wiring for it, its tests. Not merged in: G2's MakeHuman body,
G11's hair and the MakeHuman-rig clips (`mh/*.glb`). `?char=old` shows the live character with its own clips.

## The contract
- **The body:** `web/room/char_v5.glb`, the v5 character as Tripo's rig gives it (41 bones, faces +X; G13's finger bones
  welcome, MakeHuman names `finger1-1.L` ... `finger5-3.R`). For now: preview/char-tripo-v2's
  `docs/design/char-tripo-v5/char_tripo_v5.glb`, as it is.
- **The clips:** `web/room/mh_v5/<name>.glb`, room-mh's names 1:1 (`desk_type_ik`, `desk_mouse_ik`, `desk_watch`,
  `room_window`, `room_walk`, `room_sit_down`, `room_stand_up`, `room_bed_lie`, `room_bed_wake`, `room_eat`, `room_read`,
  `room_phone`, `room_phone_scroll`, `room_drink`, `room_door`, `room_bedtime`), each one animation on the bare v5 rig in
  its own frame, as G14's `room_build/kimodo/mh_retarget.mjs` (preview/anim-kimodo ef9c0e4) writes them: the rig facing
  +X, Hip translation horizontally in the MakeHuman clips' metres. Drop new files in with the same names; nothing else
  changes. **The ones here now are placeholders**: room-mh's clips run through that script as it is at ef9c0e4.
- **The player:** `web/room/char_v5.js` turns the body to face +z (G14's "MH heading - 90 deg"), hangs its Hip straight
  under that turn (world transform kept, so the skin does not move) and carries every clip's Hip tracks into that frame;
  the bones G3's code names get the MakeHuman names (Hip -> Hips, L_Thigh -> LeftUpLeg, ..., in the rig and in the
  tracks). So `boy_mh.js` runs as on room-mh. Given by the page (`mhEnv`): `clipDir` room/mh_v5, `fixClip`, `seatUp: 0`
  (the live chair stays at 0.505 m; room-mh raised it 1.6 cm for its 0.52 m clips), `noHair` (v5 has its own).

## Contacts
`SEAT=0.505 python -m tests.visual.chair_sdf <repaired chair PLY> sdf.npz` (see `docs/design/chair-tripo/README.md` for
the PLY), then `python -m tests.visual.contacts --chair-sdf sdf.npz`: with `boy_mh.js` driving, it runs room-mh's scenario
set (desk typing / mouse / watch, read, phone, phone scroll, eating, the bedtime get-up, getting up to the window,
sitting down) on the v5 skin, vertex by vertex, against the chair (all of him) and the keyboard, mouse and controller
(hands).

## The armrests, 3.5 cm further out (preview/room-v5 only)
v5's wide trousers pressed into the owner's chair's armrests in every seated clip. `chair_owner_parts.py --arms-out 0.0282`
(model metres; 3.5 cm in the room) moves each arm's pad and post outward, whole; the bar each post bends into under the
seat stretches to the mechanism, so the mount stays attached; the seat, its rim strip, the backrest and the mesh do not
move. Built with `SEAT=0.505 node room_build/build_chair_owner.mjs parts.ply <ambientCG> web/room/chair_owner.glb`
(without `--arms-out` it gives main's chair byte for byte). `arms_before_after.jpg`: the chair alone, before and after;
`arms_seated_side.jpg`: him seated, close side view, before and after.

The contact grid can now say which part of the chair a hit is in (`SEAT=0.505 python -m tests.visual.chair_sdf parts.ply
sdf.npz` stores each cell's nearest part; `tests.visual.contacts --chair-sdf sdf.npz --chair-regions`). G14's seated clips,
v5, before -> after (max mm into the part):

| clip | arm posts | arm pads | seat top | seat front | frame |
|---|---|---|---|---|---|
| typing / mouse | 23 -> 11 | 20 -> 11 | 18 -> 18 | 8 -> 8 | 13 -> 0 |
| read | 29 -> 19 | 25 -> 15 | 11 -> 11 | 0 | 13 -> 0 |
| phone / phone scroll | 24 -> 12 | 20 -> 7 | 0 | 0 | 12 -> 0 |
| eating | 29 -> 29 | 25 -> 25 | 3 -> 3 | 0 | 13 -> 0 |

The rest is not a matter of width: G14's clips sit him 8-20 cm forward on the seat (seen from above, the seat is behind
his hips in typing, mouse and eating), so his thighs cross the pads' and posts' front ends rather than pressing on their
sides; eating does not change at all.
