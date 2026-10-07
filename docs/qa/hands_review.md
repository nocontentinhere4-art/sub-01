# Desk hands: review findings F6–F9 (`docs/review/main_since_8d159d2.md`, section 3)

All in `web/room/boy_mh.js`.

## F6: switching between the keys and the mouse snapped
**Cause.** The mode picked the code path at once, while the weights crossfaded. When he took the mouse, the right hand
left the owner's take for the old capture path (`keyOn`) in one frame.

**Fix.**
- The path follows the weights, never `keyOn` while the owner's take is loaded.
- While both weights are up, the right hand is solved twice: for the mouse, and for the keys from the clip's pose. The
  two are crossfaded joint by joint (slerp). `pin()` is not linear in its weight, so weighting it gave a 28 cm jump
  near the end of the fade.
- The left hand blends from typing to rest.
- The fade's time constant is now 0.3 s (was 0.13 s): the right hand travels ~40 cm from the keys to the mouse.

**Per-frame index fingertip movement, max (mm; desk_14, 30 fps, page frames):**

| | type → mouse L | type → mouse R | mouse → type L | mouse → type R | steady typing |
|---|---|---|---|---|---|
| main | 56 | 229–258 | 36 | 31 | 4–8 |
| now | 10 | 72 | 17 | 42 | 6–15 |

The right hand now moves over ~15 frames, with no one-frame spike.

## F7: thumb hinges
They are computed once at load from a sample of the typing clip (`otHinges` at t = 0), not from whatever pose the rig
had then.

## F8: NaN and missing bones
- The stroke count only advances when both values are numbers (`if (dn && kn)`).
- `ownerKeys`, `curl`, `otReach` and `mouseHold` return early if a bone they need is missing (the hand, or the S(side,
  2/3/5, 1) knuckles).

## F9: time per frame
`hands()` now measures itself (`M.handsMs`, `M.handsMsAvg`). Medians in headless software GL (a slow environment):

| | typing | mousing |
|---|---|---|
| before | 26.3 ms | 23.5 ms |
| now | 11–12 ms | 17–18 ms |

- **Warm start.** Each finger's knuckle-bend search starts from last frame's answer, inside a ±3° bracket, and falls
  back to the full search only if that misses.
- **Fewer vertices.** Each fingertip's gap uses its 12 pad-most vertices, not the whole end bone's skin. The thumb keeps
  its whole skin: on the pad alone it went 2.5 mm into the space bar.
- **15 Hz reach.** The curl's reach fit runs at 15 Hz.
- **Tried, then dropped.** The whole settle at 15 Hz, re-applying the last bends in between, brought typing to 7 ms. But
  the take moves between searches: only 48% of fingertips stayed in 0..+2 mm, 23 samples were more than 2 mm in, and the
  thumb went 8.8 mm into the keys.

**Still over 2 ms here.**
- Mousing is mostly the mouse hold (`mouseHold`, ~10 ms; G12's).
- Scratch vectors are reused only in the new code.

## Contact (`tools/motion/key_contact_mesh.py`, keyboard mesh, 64 samples over 16 s)

| | resting fingertips in 0..+2 mm | deepest fingertip | >2 mm in | thumb lowest | deepest hand vertex |
|---|---|---|---|---|---|
| typing, main | 84% | −0.5 mm | 0 | −0.7 mm | 0.7 mm |
| typing, now | 82% | −0.9 mm | 0 | −0.8 mm | 1.4 mm |
| mouse mode, left hand, now | 83% | −0.9 mm | 0 | +0.9 mm | 0.9 mm |

## Tests
- `tests/test_boy_mh.py`, in node: the mode flips twice mid-clip. There must be no `keyOn` on either hand, and the left
  hand's typing/rest share may change by at most 0.3 per frame. On main: `keyOn` 17 times on the right, share step 1.
- `tests/visual/test_hand_switch.py`, in the page: type → mouse → type. Each index fingertip may move at most 30 mm
  (left) and 120 mm (right) per frame. On main the right hand jumped 258 mm in one frame.
