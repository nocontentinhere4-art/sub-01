# Review: preview/mixamo-wiring (G21)

- Reviewed: `edd3a02` (2026-10-07 14:56 UTC), reviewed 2026-10-07 15:35 UTC by G23 (round 3; round 2 was `edf0bce`).
- Default page (no flag) on this branch: v5 loads, boy_mh ready, desk_mouse_ik at the desk, hips at 0.83 m, the same as
  main. **Unchanged.**

## Round 3 (edd3a02): NOT OK, `?char=mixamo` does not load its clips

### 0. BLOCKER: `room/mh_mx/room_mx_typing.glb` is 404; boy_mh.js never starts, he floats in the void
![void](img/mixamo-wiring_3_char_mixamo_void.jpg)
`room.html?debug&char=mixamo`, desk scene: the page camera shows the empty chair; the close-ups show him in black
space. Console: `MakeHuman clips: Error: room/mh_mx/room_mx_typing.glb ... 404`. `mh.ready` is still false after
180 s, the old clip slots play (`type`, `stand`), and his hips are at **y = 73.6 m** (the unscaled skeleton).
`char_mixamo.js` `ROOM.clips` asks for `room_mx_typing`, `room_mx_sit_to_type` and `room_mx_type_to_sit`. None is
in `web/room/mh_mx/` (13 files committed, against 28 in `mh_v5/`: also missing `desk_type_ik`, `desk_watch`,
`room_sit_down`, `room_stand_up`, `room_sleeping_idle`, `room_laying_*`, `room_mx_*`).
Fix: commit every GLB that boy_mh.js asks for under `clipDir`, or fall back to `mh_v5` per missing clip, and make a
failed clip load visible (a hard failure in tests/visual for `?char=mixamo`, not just a console warning). Then I review
the desk/bed/stand clips in the page.

### 1 (still open). Hem horns when the arms go up: the same on edd3a02
![horns](img/mixamo-wiring_1_hem_horns.jpg)
Re-measured on the new GLB: arms up 40°, 359 hoodie vertices move > 3 cm, max **7.2 cm**, down to y **0.93 m**. T: 172
vertices, 4.8 cm. Typing and arms at the sides are still clean (0 vertices > 3 cm, max 2.2 cm). Fix as in round 2.

---

# Round 2 (edf0bce), kept for reference
## Verdict: NOT OK yet (WIP). The weights are a real fix; one new defect at the hem.

How I checked: the same hand-posed test as for G20, but with **absolute arm directions** (G21 now binds as modelled,
arms down, so rest-relative rotations are not comparable): arms as modelled (63° down) as the reference, then arms
at the sides, typing, T, arms up 40°. Metric: vertices whose main bone is `Spine*`/`Hips` (the hoodie's body, every
2nd vertex) that move more than 3 cm when only the arms move. Tool: `tools/mx/w2.mjs`.

| pose | G20 (2cbbfa1): moved > 3 cm / > 6 cm / max | G21 (edf0bce) |
|---|---|---|
| arms at the sides | 154 / 0 / 5.9 cm | **0 / 0 / 2.0 cm** |
| typing | 37 / 0 / 5.7 cm | **0 / 0 / 2.2 cm** |
| T | 2,123 / 643 / 16.2 cm | 195 / 0 / 4.9 cm |
| arms up 40° | 2,504 / 1,696 / 24.1 cm | 386 / 60 / 7.3 cm |

![before/after](img/mixamo-wiring_0_before_after.jpg)
G20 left, G21 right: the flank "fins" in typing are gone.

## Defects, by severity

### 1. Horns at the hem's sides when the arms go up — HIGH for clap / angry gesture / stretch
(image: round 3 above)
Arms up 40° (left) and T (right): a pointed flap sticks out of each side of the hoodie at pocket height. The moved
vertices go down to **y 0.95 m** (the hem), 386 over 3 cm, max 7.3 cm. Likely cause: bound arms-down, the sleeve cuff
and the hand sit right next to the hoodie's hem, so the nearest-bone weights give hem vertices some `ForeArm`/`Hand`
weight; the new span rule limits along the limb, not across the gap to the body.
Fix: in `fit.py`, the "hoodie takes no arm weight beyond 7 cm from the shoulder" rule must also cover `ForeArm`/`Hand`
(and fingers) for every vertex of the hoodie part, whatever its distance to the cuff. Check: arms up 40° and T, hoodie
vertices moved > 3 cm below y 1.15 m → 0.

### 2. Armpit residual 2.0–2.4 cm — MEDIUM, agreed with the maker's reading
I agree with STATUS_WIRING: what remains is pose against a baggy body, not weights. The dark streak across the
shoulder seen in the armpit close-ups is in the texture (it is there in the bind pose too), not a weights fold: I
withdraw that point from my G20 review.

### 3. Feet: char_mixamo has main's old slides
The Mixamo character still carries main's open slides with the white fringe. When G19's feet land (`feet.mjs`), the
autorig input must be the G19 (+G10d) `char_v5.glb`, not main's.

## Still to review when it lands
`?char=mixamo` on the page: desk clips at the page camera and close-ups, soles/seat/keys with `contact_pass.mjs`, the
default page byte-for-byte unchanged without the flag.

![poses](img/mixamo-wiring_2_poses.jpg)
