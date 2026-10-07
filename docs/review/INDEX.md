# Character-line reviews (independent reviewer: G23 until 16:30 UTC, G26 since)

One line per branch: verdict, reviewed commit, time (UTC). Details in `<branch>.md`. Tools to re-shoot: `tools/`.

| branch | verdict | commit | reviewed | one line |
|---|---|---|---|---|
| preview/char-fix-feet2 (G10d) | **NOT OK** | 9052af0 | 2026-10-07 17:20 | feet atlas fixed (sock seam in bed and toe nick gone, checked); collar brief not done: white zig-zag at the hood base on his back seen from the desk camera (high), nape still torn with glints, throat/front patch identical to main |
| preview/phone-camera (G25) | not reviewable | – | 2026-10-07 17:45 | no such branch on origin yet |
| preview/mixamo-pipeline (G20) | **NOT OK** | 2cbbfa1 | 2026-10-07 13:22 | flank "fins": 4,792 torso vertices skinned to the upper arm down to y 1.04 m, move 15.7 cm with arms down; arms-up web |
| preview/char-fix-feet (G19) | **OK** (2 fixes advised) | 8e65af7 | 2026-10-07 13:45 | big step up from main; in bed a dark seam line across each sock (medium), grey nick on left big toe (low); seated hover 5–14 cm is main's, not this branch's |
| preview/char-fix (G10d) | **NOT OK** | 92003d6 | 2026-10-07 14:45 | collar closed, big step up from main; but no socks/slides (G19's feet.mjs not run), ragged throat edge with a black sliver + pinhole of light, the front fill reads as a flat patch |
| preview/mixamo-wiring (G21) | **NOT OK** | 94061b7 | 2026-10-07 17:35 | `?char=mixamo` loads now (round 3 blocker closed); but char_mixamo.glb is NOT main's char_v5 (no collar/socks: binding decision), at the desk feet hang 4–7.6 cm in old slides, right hand on the mug not the mouse, hem horns 7.2 cm unchanged |
| preview/bed-clips (G17) | **NOT OK** (WIP) | ecabd00 | 2026-10-07 15:55 | lies on the bed now, no float/drop; but the duvet balloons (20 cm over the torso, peaks in the turn), upper back +2.8 cm off the bed, left headphone cup 3.2 cm inside his head; rewrites char_v5.glb (3rd feet version). No new commit since; still differs from main's char_v5.glb (binding decision) |
| preview/standing-clips (G22) | **NOT OK** (blocked) | 9640cbf | 2026-10-07 17:45 | props fixed (controller, tablet), feet 0.4 cm; blocked on G21's char_mixamo rebuild from main's char_v5; Texting_While_Standing holds the phone at his hip (medium) |

## Integration (C to decide)
Three branches rewrite `web/room/char_v5.glb`: char-fix (collar), char-fix-feet (feet), bed-clips (its own sock feet,
fc96f54). One chain, scripts not binaries: collar → `feet.mjs` → `bed_rebake.sh` and `rig/autorig.sh` on the result.

## Main, seen while reviewing (C to route)
- `window.contacts()` in `room.html` (the bed contact per body part) reads only `skinMesh()`, the **last** skinned mesh,
  which on v5 is `slides`: lying-in-bed contact numbers from it measure the slides, not his back/hips. Found 14:45.
- A light grey jagged patch on the back of the hoodie below the right shoulder blade (char-fix.md, defect 4).
- Seated at the desk both soles 5–14 cm over the floor (char-fix-feet.md, defect 3).
