# Typing from the owner's own hands

The owner on the Mixamo typing: "honestly the keyboard is worse than before, the hands are curved". He sent his own hands
typing, filmed from above, and asked for "the animation of how I move, a bit slower".

## Source
Branch `data/owner-typing`, `mocap_src/owner_typing/overhead_landmarks.json`: MediaPipe hand landmarks from his overhead
video, 198 frames at 30 fps, both hands in every frame. The video itself is not in git.

`tools/motion/owner_typing.py` reduces the landmarks to `web/room/mh/owner_typing.json`. The page plays it at 0.75× his
speed. The loop is 8.1 s: his 6.6 s, less a 0.5 s crossfade at the seam.

## What drives what
| | from | how |
|---|---|---|
| Finger joints (MCP, PIP, DIP) | `world` landmarks | each joint's bend per frame; scaled per finger, in proportion, to his reach (below) |
| Finger spread | the image | each finger's turn from the middle finger, seen from above: left 6 / 4 / 12°, right 7 / 6 / 19° (index / ring / little) |
| Thumb | both | its metacarpal's turn from the index line (image); its MCP and IP bends (`world`), about the thumb's own hinge |
| Hand's turn | the image | yaw from the wrist-to-middle-knuckle line: left 19° in, right 10° in |
| Placement | the image | each hand by its index fingertip, scaled by palm width (0.31 mm/px). His tips sit 7.1 cm apart, about F–J, around our F/J middle. The wrist goes where the arm and the hand's turn put it |
| Arms, body | the capture | the Mixamo typing body is unchanged; the arms reach his wrists by IK |
| Contact | the page | each resting finger settles onto its cap by its knuckle bend alone (±12°, never bent back past 5°); a finger in a stroke is only opened out of a key |

## Where the landmarks could not be used as they are
From straight above, finger bends lie mostly in depth, and depth is what MediaPipe's `world` landmarks get wrong in this
take:
- They put his knuckles 3 cm apart (about 8 cm in the image, at the scale), pitch his palm 49° up (the palm's length in
  the image rules that out), and fan his fingers 17–50° (the image shows 4–19°).
- **Bends.** The table's angles (median MCP 43–51°, PIP 31–63°) applied joint by joint folded our fingertips back under
  the knuckles: the index tip ended 8 cm from the wrist. The image shows his fingertips 16–17 cm from the wrist, his
  fingers reaching nearly their full length: "low and flat, lightly curved". So each finger keeps the take's bends in
  proportion and in time, and its curl is scaled until its wrist-to-fingertip reach, seen from above, matches his.
  - Our fingers are shorter against the palm than his, so his reach alone straightened them into planks: the right
    hand's PIP read 0. The curl has a floor at half the take's bends.
  - That floor is also a trade against the skin at the knuckles, which was modelled curled. Triangles over 2.5× bind on
    the right hand, per frame: 16 at a third of the take's bends, 12 at 0.6, 4 at 0.85. The capture's claw gives 3.
- **Roll.** Read off the palm's foreshortening, his right hand would roll 42° thumb side up. On a flat keyboard that hung
  its index 4.5 cm over the keys with the little finger in them, while both fingers type, so the foreshortening is not
  only roll. The hand is rolled by contact instead: only as far as its thumb needs to stay out of the space bar (at
  most 30°; 0–17° over the loop).
- **Pitch** from the image is about 0 (his palm's length in the image equals ours at the palm-width scale). It is used
  as read.

## Measured in the page (`owner_typing_contact.json`; desk_14, 64 samples over two loops)
| | his hands, now | the capture before |
|---|---|---|
| Resting fingertips over the cap | median +1.2 mm, 83% in 0..+2 mm, deepest −0.5, none >2 mm in | median +0.5, 77% in 0..+2 |
| Strokes | 4% of finger samples, median +9.7 mm | 15%, median +5.4 |
| Thumbs | deepest −1.5 mm, none >2 mm in | 0 |
| Hands, right minus left along the keys | wrists min 13.7 cm, index knuckles min 4.8 cm; never crossing | wrists min 14.7, knuckles min 6.0 |
| Reach, wrist to fingertip over palm length | 1.21–1.49 (his 1.46–1.88) | 1.06–1.46: the claw |
| Skin over 2.5× bind (hands, fingers, forearms, sleeves) | median 48 triangles per frame, worst 6.2× | 33.5, worst 12.7× |
| Arm skin in the desk | 0 | 0 |

**Joints against his table** (rig median vs table, MCP / PIP / DIP):

| | rig | his table |
|---|---|---|
| left index | 16 / 32 / 10 | 43 / 63 / 17 |
| left middle | 24 / 31 / 13 | 45 / 61 / 9 |
| left ring | 30 / 31 / 14 | 50 / 59 / 16 |
| left little | 39 / 30 / 28 | 50 / 46 / 43 |
| right index | 16 / 21 / 11 | 48 / 42 / 18 |
| right middle | 23 / 16 / 8 | 51 / 31 / 24 |
| right ring | 24 / 20 / 15 | 46 / 40 / 29 |
| right little | 29 / 18 / 12 | 43 / 36 / 41 |

So we are not within 10° of the table, by design: the table is the `world` depth that folded the fingers into claws.
The reach seen from above is what the image can check: ours is 0.1–0.4 palm lengths short of his (the curl floor).

## Open
- **Strokes are few.** A resting finger is held on its cap, so the take's smaller finger moves are flattened. Finger
  lifts in height cannot be seen from straight above anyway.
- **Knuckle skin.** The stretch is higher than the capture's: the flat fingers open skin that was modelled curled. The
  stretched pieces are 2–4 mm at the knuckles and the thumb web; nothing showed in close-ups. More curl would cut it, at
  the cost of the flat hands.
- **Elbows and body** are still the Mixamo performer's.

## Pictures
`owner_typing_views.jpg`, at t = 1 / 3 / 5 / 7 s:
- **Front, above the keys.** The monitor is hidden in this render only.
- **From his right**, at key height.
- **Straight from above**, framed like his take: keys horizontal, him at the bottom. Everything more than 15 cm over the
  keys is clipped in this render only, because his head and shoulders lean into that camera.
