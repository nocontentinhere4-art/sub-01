# Character-line reviews (independent reviewer: G23 until 16:30 UTC, G26 since)

One line per branch: verdict, reviewed commit, time (UTC). Details in `<branch>.md`. Tools to re-shoot: `tools/`.

| branch | verdict | commit | reviewed | one line |
|---|---|---|---|---|
| preview/char-fix-feet2 (G10d) | **NOT OK** | 6880ee3 | 2026-10-07 17:50 | feet atlas fixed (checked); throat better; still the light zig-zag at the hood base on his back, seen by the desk camera (high), nape lining torn with glints (medium) |
| preview/phone-camera (G25) | **OK** | 86cae2c | 2026-10-07 19:20 | 390: asleep (also first after load), phone in bed, door, walking framed under the header; desk shot slid down; 1280 identical to main; merges clean (86cae2c: docs/tests only since d9bbf3a) |
| preview/mixamo-pipeline (G20) | **NOT OK** | 2cbbfa1 | 2026-10-07 13:22 | flank "fins": 4,792 torso vertices skinned to the upper arm down to y 1.04 m, move 15.7 cm with arms down; arms-up web |
| preview/char-fix-feet (G19) | **OK** (2 fixes advised) | 8e65af7 | 2026-10-07 13:45 | big step up from main; in bed a dark seam line across each sock (medium), grey nick on left big toe (low); seated hover 5–14 cm is main's, not this branch's |
| preview/char-fix (G10d) | **NOT OK** | 92003d6 | 2026-10-07 14:45 | collar closed, big step up from main; but no socks/slides (G19's feet.mjs not run), ragged throat edge with a black sliver + pinhole of light, the front fill reads as a flat patch |
| preview/mixamo-wiring (G21) | **OK** | 94c2554 | 2026-10-07 19:25 | char_mixamo from main's char_v5 (collar, socks); `?char=mixamo` desk soles 0.2/0.7 cm, hand on the mouse, hem horns gone; default page pixel-equal to main 7f2bf6e (under main's harness) |
| preview/bed-clips (G17) | **NOT OK** | 0908653 | 2026-10-07 20:05 | hand-in-head in the turn fixed (checked); duvet tent unchanged (high); headphone cups at the jaw, not on the ears; its contact_pass crashes headless on this commit, so back/turn rows not re-measured (0908653: its docs only, same code) |
| preview/standing-clips (G22) | **OK** | 4202e97 | 2026-10-07 20:15 | re-baked on G21's char_mixamo (main's char_v5); texting in front of his chest with both hands; soles 0.4 cm every frame; default page pixel-equal to main; low: Gaming's left fingers open |

## Integration (C to decide)
Three branches rewrite `web/room/char_v5.glb`: char-fix (collar), char-fix-feet (feet), bed-clips (its own sock feet,
fc96f54). One chain, scripts not binaries: collar → `feet.mjs` → `bed_rebake.sh` and `rig/autorig.sh` on the result.

## Main, seen while reviewing (C to route)
- (fixed on bed-clips ebb2756: `bodyMesh`) `window.contacts()` in `room.html` (the bed contact per body part) reads only `skinMesh()`, the **last** skinned mesh,
  which on v5 is `slides`: lying-in-bed contact numbers from it measure the slides, not his back/hips. Found 14:45.
- A light grey jagged patch on the back of the hoodie below the right shoulder blade (char-fix.md, defect 4).
- Seated at the desk both soles 5–14 cm over the floor (char-fix-feet.md, defect 3).
