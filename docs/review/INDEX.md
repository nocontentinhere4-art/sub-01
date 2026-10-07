# Character-line reviews (G23, independent reviewer)

One line per branch: verdict, reviewed commit, time (UTC). Details in `<branch>.md`. Tools to re-shoot: `tools/`.

| branch | verdict | commit | reviewed | one line |
|---|---|---|---|---|
| preview/mixamo-pipeline (G20) | **NOT OK** | 2cbbfa1 | 2026-10-07 13:25 | flank "fins": 4,792 torso vertices skinned to the upper arm down to y 1.04 m, move 15.7 cm with arms down; arms-up web |
| preview/char-fix-feet (G19) | **OK** (2 fixes advised) | 8e65af7 | 2026-10-07 13:45 | big step up from main; in bed a dark seam line across each sock (medium), grey nick on left big toe (low); seated hover 5–14 cm is main's, not this branch's |
| preview/char-fix (G10d) | **NOT OK** | 92003d6 | 2026-10-07 15:05 | collar closed, big step up from main; but no socks/slides (G19's feet.mjs not run), ragged throat edge with a black sliver + pinhole of light, the front fill reads as a flat patch |
| preview/mixamo-wiring (G21) | **NOT OK** (WIP, partial) | edf0bce | 2026-10-07 14:45 | weights fixed: typing torso drag 5.7→2.2 cm, fins gone; new: horns at the hem sides with arms up/T (7.3 cm); not wired to the page yet |
| preview/bed-clips (G17) | not yet pushed | — | 13:45 | |
| preview/standing-clips (G22) | not yet pushed | — | 13:45 | |

## Main, seen while reviewing (C to route)
- `window.contacts()` in `room.html` (the bed contact per body part) reads only `skinMesh()`, the **last** skinned mesh,
  which on v5 is `slides`: lying-in-bed contact numbers from it measure the slides, not his back/hips. Found 15:05.
- A light grey jagged patch on the back of the hoodie below the right shoulder blade (char-fix.md, defect 4).
- Seated at the desk both soles 5–14 cm over the floor (char-fix-feet.md, defect 3).
