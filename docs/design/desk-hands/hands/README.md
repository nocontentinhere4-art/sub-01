# Hands at the desk: resting on the keys, holding the mouse

## Owner's note
The right hand must hold the mouse. The left hand was "ultra strange": fingers splayed and stiff, and the mouse untouched on its mat.

## What was wrong (measured in the page, mouse mode, desk_14)
- **Right hand:** wrist 10 cm and lowest fingertip 8.8 cm above the mouse pad on main 95abd03, so it hovered over the mouse.
  After the posture fix: 4.0 / 5.4 cm. Now: 1.3 / 2.6 cm.
- **Finger shapes:** these came straight from the MakeHuman clip's own curls, never posed for keys or a mouse.
- **The page's wrist pin (boy_mh.js `pin` / `ccd`):** it turns the forearm and upper arm to reach the keys or the mouse,
  and the hand, kept local to the forearm, turned with them. Once he sat upright, that turn stood the right hand on edge:
  palm facing back, fingers up.

## Fix
1. **Clips:** desk_type_ik keys/keys, desk_mouse_ik keys/mouse, desk_watch relax/relax. Built with mh_retarget `handPose`
   (preview/motion-c `tools/motion` has the retarget's sibling tools).
   - Each phalanx is aimed along the hand's wrist-knuckle line, spread about the palm normal, and turned toward the palm
     by the summed flex (MCP, PIP, DIP).
   - The thumb tip is set by CCD onto a point in the hand's frame.
   - The hand's own turn follows the photographs: palm down, fingers forward along the desk; keys pitched down 12 deg and
     turned 12 deg inward, mouse pitched down 8 deg.
   - keys: index 25/35/15, middle 28/38/15, ring 30/40/18, little 32/42/18 deg. Fingers together (spread +3/0/-3/-6),
     a gentle dome, the thumb down toward the space bar. References: kb1, kb2.
   - mouse: index and middle 8/12/6 (nearly straight on the two buttons), ring 28/40/20, little 35/45/25 (curled round
     the far side), the thumb flat along the near side, tip at mid-length. References: mouse1, mouse2.
   - relax (desk_watch): loosely curled, 15-21 / 25-31 / 10-12 deg.
   - `clip_space_check.png`: the clip as authored, without the page's pin. The right hand is palm-down over the mouse and
     the left hand's fingers are curled on the keys.
2. **Page (boy_mh.js `pin`):** after each CCD pass the hand keeps its world turn from the clip (blended by the pin
   weight). Only the arm moves to reach, so the photographed hand shape arrives as authored. This is 2 lines in G10d's code.

## Result
`before_after_over_left_shoulder.jpg`:
- Top row, over his left shoulder (the owner's angle): before on the left, after on the right.
- Bottom row: the left hand close, before and after. With the right hand on the mouse, the left now rests relaxed and
  curled beside the keyboard instead of flat and stiff.

`after_mouse_over_and_side.jpg`: the right hand palm-down on the mouse, index and middle fingers over the buttons.

## Not done here
- No finger motion: no typing taps, no clicks. Typing would be motion and needs a real source, as ruled.
- In mouse mode the page does not pin the left hand. It rests where the clip has it: on the desk by the keyboard, not on the keys.

## References
Pexels License, no faces, logos pixelated; details in `SOURCES.md`:
- kb1 18966470 and kb2 28993052: Matheus Bertelli.
- mouse1 5745010: Ryutaro Tsukata.
- mouse2 5185149: cottonbro studio.

## Mouse grip tightened (COORD's nit: the fingers were fanned in the top-down view)
Measured on the references (mouse2 top-down, pixel positions):
- The index finger points about 14 deg toward the thumb from the middle finger. In mouse1 the two lie closer still.
- The middle and ring fingers are together; the little finger is tucked under the ring on the shell's right flank.
- The thumb lies flat on the left flank.

New per-phalanx pose (MCP / PIP / DIP flex, spread about the palm normal):

| finger | flex (deg) | spread (deg) |
|---|---|---|
| index | 8 / 12 / 6 | +2 |
| middle | 8 / 12 / 6 | 0 |
| ring | 42 / 44 / 22 | -4 |
| little | 52 / 50 / 28 | -7 |

- Ring and little are curled down beside the shell's right side instead of fanned across the pad.
- They cannot curl into the shell: the page lifts the hand until every fingertip clears the shell by 8 mm (`overMouse`).

The numbers, measured in the page in mouse mode (desk_14 scene, `mouseprobe`):

| | wrist above the pad | lowest fingertip above the pad | index tip to mouse centre (xz) |
|---|---|---|---|
| main 95abd03 | 10.0 cm | 8.8 cm | 1.2 cm |
| c36173a (committed hands) | 8.1 cm | 2.8 cm | 3.0 cm |
| tightened grip | 8.7 cm | 2.9 cm | 2.9 cm |

**Correction to the earlier figure:** "wrist 1.3 cm above the pad" was measured before the palm-down hand orientation was added. With the palm resting on top of the ~4 cm shell, the wrist joint sits ~8 cm up. The fingertips are on the buttons in both.

`mouse_grip_tightened.jpg` shows the references on top, then c36173a vs the tightened grip, from three views: top-down, his right side, over his left shoulder.

## Mouse grip: contact instead of clearance (COORD: "he reads as resting his hand next to a mouse")
**What was wrong, measured in the page** (mouse mode, desk_14; `tools/motion/grip_probe.py`). The room's mouse shell is 11 cm long and 6.5 cm wide. Its top is 36 mm high at 2 cm behind its centre.
- **Palm not on the shell.** The palm (60% from wrist to middle knuckle) was 7.2 cm behind the mouse's centre. That is behind the shell's rear edge (−5.5 cm), and 7.9 cm above the pad.
- **Fingers floating.** The fingertips hung 2–3 cm over the buttons.
- **Two causes:**
  - The wrist pin aligned the clip's mouse point, not the hand's actual palm, with the room's mouse. Since the photo-referenced hand poses, that put the palm 5 cm short.
  - `overMouse` then lifted the whole hand until every fingertip and knuckle cleared the shell by 8–20 mm. The hand could never come down onto the shell.
- **Correction to the line above** ("the palm resting on top of the ~4 cm shell"): it was not. The palm was behind the shell.

**Fix: the page resolves the hand against the shell by contact** (`boy_mh.js`, mouse mode only; typing still uses `overMouse` while the hand passes the mouse).
- **Shell height map.** The shell's top is sampled once into a 2.5 mm height map in the mouse's own frame.
- **Mouse follows the clip.** The recorded hand still moves the mouse, as before.
- **Hand placed on the shell.** The wrist is then re-pinned so that:
  - The palm is centred 2.2 cm behind the top of the hump and 1.2 cm right of it. That is where the hand sits in mouse2: index and middle on the two buttons, ring and little on the right flank.
  - The palm rests on the shell: palm skin 16 mm below the bones' line.
  - No knuckle goes into it (11 mm).
- **Fingers laid down.** Each finger is laid down joint by joint (base, middle, end) onto whatever is under it, the shell or the pad, until it touches. The shell is the hard limit.
  - Clearance is checked along each phalanx and across its width, so the uphill side counts on the curved shell.
  - The fingertip is measured once off his skin and follows the end joint.
- **Thumb** along the left flank: tip 1.6 cm over the pad, 1 cm ahead of the palm.
- **Index and ring** set beside the middle finger, seen from above: index turned 3° in, ring parallel.
- **No build-up.** Every finger turn the page makes is undone the next frame unless the clip has rewritten that bone. The turns never add up between frames.

**Measured over 15 s of mouse mode, every 0.25 s** (`grip_contact.json`):

| | before (5f3bc7f) | now |
|---|---|---|
| Palm centre vs mouse | 7.2 cm behind centre, 7.9 cm up | on the hump (−4.3 cm), 5.6 cm up |
| Wrist above the pad | 8.6 cm | 5.6 cm |
| Fingertips over the shell | 2–3 cm | 1.0–1.3 cm, which is the 10 mm finger half-thickness: touching |
| Hand skin inside the shell | n/a | max 1.2 mm, median 0 |
| Hand skin below the pad | 0 | 0 |

**Still open:**
- **Palm hollow.** The palm's centre stays about 1.2 cm over the hump. The knuckle row sits on the shell (the 11 mm limit), so the palm arches over the hump instead of pressing into it.
- **Mouse size.** His hand is long for this 11 cm mouse, so the index and middle tips end right at the front edge.

`mouse_grip_contact.jpg` shows:
- **Top row:** the mouse2 reference beside our top-down over the mouse. The mouse is mostly hidden under the hand.
- **Middle row:** mouse1 beside the view from his left (palm on the shell, thumb on the flank).
- **Bottom row:** the view from his right.
