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
