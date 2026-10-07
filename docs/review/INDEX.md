# Character-line reviews (G23, independent reviewer)

One line per branch: verdict, reviewed commit, time (UTC). Details in `<branch>.md`. Tools to re-shoot: `tools/`.

| branch | verdict | commit | reviewed | one line |
|---|---|---|---|---|
| preview/mixamo-pipeline (G20) | **NOT OK** | 2cbbfa1 | 2026-10-07 13:22 | flank "fins": 4,792 torso vertices skinned to the upper arm down to y 1.04 m, move 15.7 cm with arms down; arms-up web |
| preview/char-fix-feet (G19) | **OK** (2 fixes advised) | 8e65af7 | 2026-10-07 13:45 | big step up from main; in bed a dark seam line across each sock (medium), grey nick on left big toe (low); seated hover 5–14 cm is main's, not this branch's |
| preview/char-fix (G10d) | **NOT OK** | 92003d6 | 2026-10-07 14:45 | collar closed, big step up from main; but no socks/slides (G19's feet.mjs not run), ragged throat edge with a black sliver + pinhole of light, the front fill reads as a flat patch |
| preview/mixamo-wiring (G21) | **NOT OK** (blocker) | edd3a02 | 2026-10-07 15:35 | `?char=mixamo` broken: room/mh_mx/room_mx_typing.glb (and 2 more) 404, boy_mh never starts, he floats at y 73 m; default page unchanged; hem horns 7.2 cm still there |
| preview/bed-clips (G17) | **NOT OK** (WIP) | ecabd00 | 2026-10-07 15:55 | lies on the bed now, no float/drop; but the duvet balloons (20 cm over the torso, peaks in the turn), upper back +2.8 cm off the bed, left headphone cup 3.2 cm inside his head; rewrites char_v5.glb (3rd feet version) |
| preview/standing-clips (G22) | **NOT OK** (WIP) | 7aec913 | 2026-10-07 15:10 | feet planted 0.3–0.4 cm, seats hold; but Gaming/tablet clips have no prop (miming), Texting_While_Standing holds the phone edge-on, hands-in-thighs 7–8.5 cm per contact_pass (needs a surface check) |

## Integration (C to decide)
Three branches rewrite `web/room/char_v5.glb`: char-fix (collar), char-fix-feet (feet), bed-clips (its own sock feet,
fc96f54). One chain, scripts not binaries: collar → `feet.mjs` → `bed_rebake.sh` and `rig/autorig.sh` on the result.

## Main, seen while reviewing (C to route)
- `window.contacts()` in `room.html` (the bed contact per body part) reads only `skinMesh()`, the **last** skinned mesh,
  which on v5 is `slides`: lying-in-bed contact numbers from it measure the slides, not his back/hips. Found 14:45.
- A light grey jagged patch on the back of the hoodie below the right shoulder blade (char-fix.md, defect 4).
- Seated at the desk both soles 5–14 cm over the floor (char-fix-feet.md, defect 3).
