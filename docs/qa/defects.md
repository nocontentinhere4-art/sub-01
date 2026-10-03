# Visible defects on `main`, routed (issue #98, G8)

From the core and full runs of `tests/visual/` on `main` 5f12ea9 / 00af116 (2026-10-02), sent to the coordinator the
same evening and routed by them (G2: 1–6; G3: 7–8; #63: 9; G6: 10, 15–18, 21, 22; G4: 11–13; G5: 14; G7: 19–20).
The bar is photorealism (owner's brief): the "what reads as CG" list in `scorecard.md` adds the general tells
(plastic materials, uniform textures, no contact shadows, knife edges, flat light) that no single item below carries.
Measured numbers come from `tests/visual/out/results.json`; the shots named are in the run's output directory.
Status: open unless marked. Items 7 and 8 become hard CI checks (budgets.json `desk_vertices`, `below_floor_vertices`
→ 0) once G3's fix lands.

## G2 · character asset (`web/room/boy.glb`)
1. **Faceted face.** Flat triangles on cheeks, jaw, neck and collarbones at the 0.5 m close-up (`closeup_face_14.png`);
   the head shares one 2048² texture with the whole body. Needs more head triangles and a normal map, or a smoothed head.
2. **Hair** is spiky flat black shards with no specular, jagged silhouette.
3. **Hoodie and trousers** are glossy black with baked highlights (PVC/latex look) and flat-shaded facets on the sleeves
   and back (`door_8_1280_char.png`, `eating_19_1280_char.png`).
4. **Faceted white socks** on his feet (`closeup_feet_14.png`); the slides are fine.
5. **Mitten hands** on the own mesh (`closeup_bed_14.png`); the `hand_phone.glb` grip is good (`closeup_grip_14.png`).
6. **Texture anisotropy 1** on the character's map (room textures use 8): blur at grazing angles.

## G3 · motion (`web/room/boy_motion.js`, the room's hook block)
7. **Forearms through the desk top** in the sitting pose: 50 of ~17,700 sampled vertices inside the desk slab
   (left forearm 36, right forearm 10, right upper arm 4) in `desk_14_1280`.
8. **Toes under the floor** when standing at the door and the sill: left toes/foot 1.2 cm below (3 sampled vertices).
9. **Sleeping on top of the duvet**, fully dressed, slides on, arms stiff, a hand on the belly (`closeup_bed_14.png`).
10. **The follow camera at the desk** looks at the back of his head over the monitor (`desk_14_1280.png`); his face is
    never seen in the most common activity.
21. **The camera jumps to the monitor before he reaches the desk.** The server's `life` snapshot (life.py `snapshot()`)
    has no `path` or `path_to` field, so the page's `!life.path` guards in `screens()` and `props()` are always true:
    while he walks to the desk with activity `research` (`walking: true`), `screenOn` is already `"desk"` and the
    follow camera frames the monitor, with him walking in from the side or out of frame (`walking_*_1280_clean.png`
    shows the monitor, `walking_*_1280_char.png` shows him). Also `PLACE2ANCHOR[life.path_to]` never resolves. Either
    the server sends `path`/`path_to`, or the page keys on `life.walking`. Server side: coordinator's call.

## G4 · soft goods (`room_build/props_soft.py`)
11. **Hanger socks are tubes**: straight 10-sided cylinders with flat-cut open ends and a second cylinder for the foot;
    the towel is a flat box; the pegs are boxes (`closeup_socks_14.png`). This is the owner's "socks like cones".
12. **Pillow** is a hard rounded box with no dent; the **duvet** has one fold and a sharp straight edge along the frame;
    the sheet is plain (`closeup_duvet_14.png`).
13. **Hoodie and tote on the door** are slabs; curtains are uniform ribbed cylinders (acceptable from the overview).

## G5 · hard surfaces (`room_build/props_hard.py`)
14. The desk set is the strongest area (4/5). Nits: the mouse is a smooth blob, the books are coloured blocks, the bin a
    plain cylinder, no skirting board or trim along the walls (`closeup_desk_19.png`, overview shots).

## G6 · rendering (`web/room_post.js`, the renderer/lighting block)
15. **Night is black**: at 23:00 with the lights off the canvas has mean luminance 10/255, 12 % pure-black pixels at
    1280 and 18 % at 390 (`sleeping_23_1280_clean.png`, `sleeping_23_390_clean.png`); floor, bed and he barely read.
16. **The monitor's page is pure white**: the fake Wikipedia page is an unlit 255-white texture (`toneMapped:false`), so
    it reads as a blown rectangle in every desk shot (4 % of the canvas at 1280, 9 % at 390; all of the "blown" pixels
    the harness counts). A monitor in a game is a little dimmer and off-white, with glow and a faint reflection.
    (Correction to the first list sent: the morning itself does not clip; 08:00 without the monitor in frame has
    ≤ 0.2 % blown pixels.)
17. **No contact shadows or AO on the character**: he floats visually on the floor and on the bed.
22. **The desk lamp blows out the hoodie**: with the lamp lit (eating or research after dusk) the hood and the shoulder
    nearest the lamp go to flat white (`eating_19_1280_char.png`); the lamp's intensity plus the hoodie's glossy
    material (defect 3) clip under ACES. Shared with G2.
18. **Only a far overview camera** when he is not at a screen: he is ~70 px tall at 1280; a medium shot never happens
    (the harness's `_char.png` shots show what one would look like).

## G7 · window (`web/room/window_view.*`)
19. **Flat city**: grey cuboids and two grey towers on one plane by day, no haze or parallax (`closeup_grip_14.png`);
    at night lit dots and a tower only. The sky gradient, sun, moon and stars are fine; the sun glare is oversized.
20. **No glass**: the window has no reflection or sheen.

## Not a defect, noted
- Z-fighting: none flagged by the flicker test (desk at 14:00, 5 frames, camera creeping 0.7 mm a frame).
- Props: every separate object rests on its support (gap ≤ 4 mm) or hangs on a wall; the merged room props are checked
  by the build-time sweep in `room_build/build_room.py`.
- Performance: animate() 0.27 ms per frame at 1280 and 1.2 ms under a 4x CPU throttle at 390; 55 draw calls and 171k
  triangles with the lamp lit. FPS cannot be judged here (software WebGL).
