# The mouse hand from the owner's own take

COORD: the right hand on the mouse from the owner's take. Every finger and thumb joint per frame, the hand's orientation
from his palm, the mouse's travel from his wrist, at 0.75× his speed, looped. Nothing hand-set.

## Source
Branch `data/owner-typing`, `mocap_src/owner_typing/`:
- `mouse_overhead_landmarks.json` is the source: 666 frames at 30 fps, MediaPipe, the hand in every frame.
- `mouse_front_landmarks.json` is a witness, used for the roll only (below).

The videos are not in git.

`room_build/kimodo_g12/owner_mouse.py` reduces the landmarks to `web/room/mh/owner_mouse.json`:
- 636 frames, looped (a 1 s crossfade at the seam);
- the page plays it at 0.75×, so the loop lasts 28.3 s.

**Check of the reduction:** the take's PIP/DIP medians reproduce the README table exactly, for example index 35/16,
middle 31/29, little 28/38.

## What drives what
| | from | how |
|---|---|---|
| Finger bends (index to little) | the overhead take, `world` | each segment's direction in his palm's frame (wrist→middle knuckle, index→little knuckle); the page builds the same frame from the character's bones and aims each bone along it |
| Finger spread | the overhead image | each finger's turn from the middle finger, seen from above |
| Thumb | the owner | straight: its MCP and IP bones on along its root's line; the root (finger1-1) as recorded (below) |
| Hand's long axis | the overhead take | wrist→middle knuckle over the desk, per frame |
| Hand's roll | the front take | base 18.7°, band 14.0–21.4° (below) |
| Mouse travel | the overhead image | his wrist's track in palm widths (5→17, median 84 px), times the character's own 5→17 width; the room mouse follows the palm as before |
| Arm, body | the capture | the arm reaches by IK; the body is `room_seated_idle`, unchanged |
| Contact | the page | listed under "Contact" below |

The camera's frame comes from the landmarks, not assumed: his fingers point to image −x and his thumb to +y, so
forward = −x, his right = −y, up = −z.

**Removed (hand-set):** GRIP, GRIP_ROLL, GRIP_RIGHT, unpress() and besideMiddle(). curl() stays: the owner typing uses it.

**Spread.** The world landmarks fan his fingers in depth, as G14 found on the typing: index, ring and little sit 26°,
23° and 31° from the middle finger there, but 14°, 9° and 8° in the image. Each finger's three segments are turned in the
palm's plane by the difference; the bends are unchanged.

**Roll (COORD's call).** From straight above, MediaPipe's depth puts the roll at 31°, and depth is its weak axis. The
front take sees the roll in its image plane, so it is the witness:
- base 18.7°: the palm's anatomical roll, median;
- band 14.0–21.4°: the 5→17 line's angle in the image (median 14°) and in the world landmarks (21°).

The front take's own up/down sign is not trusted, because its video may be turned. The side that is up, the thumb's,
is the overhead take's. Contact may lower the roll only inside the band, and only to keep the ring and little fingers
out of the shell.

## Contact (all on the mouse's own mesh)
**Finding:** the mouse's 2.5 mm height map is blind in two places.
- It cannot judge a steep flank.
- It reads the space under the shell's bulge as clear.

On 9961024 the thumb was 19–20 mm inside the shell for the whole loop, and the ring fingertip 14 mm. The height map read
these as clear. The mouse path now tests the shell itself (a double-sided copy on its BVH; inside = odd crossings of a
ray up, counted once at shared edges):
- **Palm, knuckles, thumb root.** The hand is lifted by its skin's deepest point in the shell (`shellLift`).
- **Fingers.** A finger with any skin vertex in the shell is opened, its bends kept by the largest share that clears
  (`omOpen`). This tests every vertex: a finger down a flank touches with its side, which the 48-vertex subset missed.
- **Thumb.** Its pad's clearance to the left flank is measured by rays toward the mouse. The hand moves across until
  the pad is 1 mm in (`mouseSettle`, at most 2 mm a frame).
- **Fingertips.** The hand tilts until the index or middle tip touches. A finger that had to open counts as touching,
  which stops the tilt from chasing it.
- **Roll.** It is lowered toward the band's end (14°) while the ring or little finger had to open.
- **Mouse width.** The mouse is ours, so its size is free to match his hand. It narrows (0.3% a frame) while the ring
  or little finger still had to open at the roll's band end, and widens back to its own once they clear.

## Thumb: why its root is left as recorded
The character's thumb root (finger1-1) sits 1.3 cm *inside* its index knuckle's line and 2.8 cm under the palm. His
CMC sits outside the index line. So his thumb, carried over whole:
- along his directions, lies under the index finger and 15–20 mm into the shell;
- placed at his joints' positions, needs a 56° bend at the MCP (his is 14°).

Turning finger1-1 tears the skin at the thumb's base: its triangles reach 5× their bind length at p99, and 10–14× at the
worst triangle. Left as recorded, they stay at 2.05× (p99). The thumb's MCP and IP bones continue its line, straight
(next section).

## The thumb, straight
The owner's verdict on 72d8f50: "the thumb is the only problem: STRAIGHT, not curved". His take agrees: from above, its
bends are 14° and 9°, and the thumb lies almost straight along the left flank.

On the rig the thumb read curved, measured on the bones and the visible tip (the middle of the end bone's farthest skin):
- **MCP 22°, IP 18°.** His segments' directions were applied from the character's root, which lies inside the index
  line; that put the bend at the MCP.
- **The last bone was aimed at the contact pad's centre.** The pad lies off the line the eye follows, so the visible
  end turned a further ~9°.

Now:
- **Straight.** The MCP and IP bones continue the root's line, and the last bone is aimed at the visible tip.
- **The mouse turns under the thumb.** In the take his thumb lies along the flank, so the flank runs where his thumb
  does. The room mouse's long axis follows the thumb's line seen from above, at 0.3° a frame, within 15° of where it
  was put. Over the loop it sat at 10.5–14.9°.
- **The hand moves across** until the straight thumb's pad touches the flank, as before. The thumb is never bent to
  reach it.

72d8f50 against this, every 0.25 s over the 28.3 s loop (113 samples):

| | 72d8f50 | straight |
|---|---|---|
| Thumb MCP bend, median / max | 21.7 / 27.4° | 0 / 0° |
| Thumb IP bend, median / max | 17.8 / 24.9° | 0 / 0° |
| Thumb pad into the flank, median / p90 / max | 0.9 / 1.7 / 4.9 mm | 1.0 / 1.5 / 2.3 mm |
| Thumb touching the flank | 112 of 113 | 113 of 113 |
| Thumb to the mouse's axis, median / max | 7.7 / 21.9° | 7.8 / 16.4° |
| Fingers into the shell, max (index, middle, ring, little) | 0, 0, 0, 3.1 mm | 0, 0, 0, 1.7 mm |
| Palm into the shell, max | 1.5 mm | 0.8 mm |
| Index tip on its button, ≤2 mm | 3 of 113 | 50 of 113 (median 2.2 mm) |
| Middle tip on its button, ≤2 mm | 100 of 113 | 47 of 113 (median 2.2 mm) |
| Left hand on the keyboard | 113 of 113 | 113 of 113 |
| Skin stretch round the thumb's base, p99 / worst triangle | 2.07 / 4.03× | 2.03 / 4.33× |
| Chair, desk penetration | 0 | 0 |

The worst triangle is over 2.5× before and after, and in the clip's own pose with no IK at all. It comes from the
character's skin weights, not the thumb's pose (below).

## Measured, before the thumb was straightened (`owner_mouse_contact.json`)
Desk_14, mouse mode, every 0.25 s over the whole 28.3 s loop (113 samples). The instruments are independent of the
resolver: the shell's mesh, rays toward the mouse for the thumb, and the skin's own bind-pose edge lengths.

| | 9961024 (before) | this branch |
|---|---|---|
| Thumb skin into the shell | 19.3 mm median, every sample | 0.9 mm median, p90 1.6; >2 mm in 6 of 113 (max 5.2) |
| Thumb touching the flank | in it | 111 of 113 |
| Thumb to the mouse's axis | 3° | median 7.7°, max 21.9° (limit 30°) |
| Fingers into the shell, max | ring 14.6 mm | index/middle/ring 0, little 2.0 (once; >0.5 mm in 1 of 113) |
| Palm into the shell, max | 1.9 mm | 1.4 mm |
| Middle tip on its button | 8.3 mm over | median 1.2 mm; ≤2 mm in 100 of 113 |
| Index tip on its button | 15.5 mm over | median 7.7 mm; ≤2 mm in 6 of 113 (below) |
| Left hand touching | nothing under it (before G14's 4744f2e) | on the keyboard, 113 of 113 (G14's rest), deepest 0.45 mm in |
| Skin stretch round the thumb's base, p99 / worst triangle | 1.90 / 4.18× | 2.05 / 4.04× |
| Roll | – | 16° median; at the 14° band end part of the loop; off the 18.7° base in 90 of 113 samples |
| Mouse width | 100% | 82–100%, median 93% |
| Chair, desk penetration | 0 | 0 |

**Flexion against his table** (medians, ours − his, degrees):

| | MCP | PIP | DIP |
|---|---|---|---|
| thumb | −31 (root as recorded) | +8 | +9 |
| index | +3 | −1 | +4 |
| middle | −3 | −3 | −7 |
| ring | −15 | −1 | −6 |
| little | −19 | 0 | +1 |

- The MCP is measured from the wrist→knuckle line, and the character's metacarpals do not run where his do.
- The ring and little MCPs are the opened ones (`omOpen`). With the spread taken from the image they lie closer to the
  middle finger, over the hump.

**The skin's own limit:** the worst triangle at the thumb's base is over 2.5× its bind length in every sample, before
and after, in the clip's own pose too (no IK at all). It is in the character's skin weights, not the pose. The p99 is
the honest figure for the pose.

## Open
- **Index and middle on their buttons.** With the straight thumb and the mouse turned under it, each tip is within
  2 mm about half the loop (index 50, middle 47 of 113; both median 2.2 mm). The cause is the same thumb-root
  difference: the character's index sits over the shell's left edge. Closing a finger onto its button (up to 30% more
  bend) bent it 11° past his table without reaching, so it was dropped. On a regenerated character with the thumb
  root outside the index line, this should close by itself.
- **Thumb-base stretch** belongs to the character's weights (above). The owner is regenerating the character on Tripo.
  Everything here is driven by his landmarks plus the character's own measured palm, with no constant tuned to v5's
  thumb, so it carries over.

## Pictures
- `mouse_sheet.jpg`: five views. Rows: close up from his left at mouse height (the thumb's whole length), from above,
  his right, his left (the thumb's side), over his right shoulder. Columns: 72d8f50 (the curved thumb), then the
  straight thumb at three moments of the loop (~5, 14 and 23 s into his take). In the side views
  the mug, the bottle, the controller, the monitor and the plant are hidden, in that render only.
- `mouse_top_like_take.jpg`: straight down, framed like his take: the pad level, him at the bottom.
