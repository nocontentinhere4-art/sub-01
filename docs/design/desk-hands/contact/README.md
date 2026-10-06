# Contact: his hands settle onto the mouse and the keys instead of being kept clear of them

## The defect
Every desk rule in the page only ever pushed his hand out of things:
- On the mouse, the clearance lift (`overMouse`, 8–20 mm) left the hand hovering. The wrist pin also aimed the clip's reference point, not the hand, which put the palm 7 cm behind the mouse's centre.
- On the keys, the tip floor (`lowestTip`: bone heads minus 8 mm over the caps +3 mm) guaranteed a hover, because his fingertip skin is 10–11 mm thick. G12 measured 0.5–1.1 cm over the caps for a whole clip on main.
- On this branch the photo-referenced hand poses also put the typing fingertips 12 cm ahead of the home row, past the keyboard's far edge, with the wrists 11 cm over the keys.

A hovering limb penetrates nothing, so every test passed.

## The resolver (`web/room/boy_mh.js`, the "contact" block)
One resolver, two callers: the mouse (right hand) and the keys (left hand always at the desk, right hand while typing). Each frame, for each hand:
1. **Carried.** The recorded wrist is carried to the room's object by the existing clip-to-room offset. The clip's motion stays the clip's.
2. **Placed by a point of the hand itself:**
   - Mouse: the palm (60% from wrist to middle knuckle) goes 2.2 cm behind and 1.2 cm right of the shell's top. That is mouse2's hand position: index and middle on the buttons, ring and little on the right flank. The mouse still follows the recorded hand.
   - Keys: the index fingertips, measured off his skin, are centred over F and J. This is a slow correction (~1 s), so the typing motion stays the clip's.
3. **Settled vertically:**
   - Mouse: the palm rests on the shell (palm skin 16 mm below the bones' line).
   - Keys: the knuckles sit 3 cm over the caps under them.
   - Both: no knuckle comes closer than its skin (11 mm).
4. **Whole arm.** The arm turns to get the wrist there (upper arm at the shoulder, forearm at the elbow); the wrist keeps the clip's turn. If the arm's skin (sleeve included, on its twist bones) is in the desk, the elbow swings up about the shoulder–wrist line until it is out, at most 15°.
5. **Fingers onto the surface.** Each finger is bent joint by joint: from straightest, in steps, down to the first touch, then refined. The surface is the hard limit.
   - The first phalanx is tested by its bone line with a 10 mm half-thickness. The middle and end phalanges are tested by their own skinned vertices.
   - Each surface is a 2.5 mm height map of its top (the mouse shell, the keycaps); off the surface it is the pad.
   - Mouse: the thumb lies along the shell's left flank; index and ring are set beside the middle finger.
   - Keys: the thumb is laid like the fingers, onto the space bar. The bend is followed over 0.4 s, so a real clip's quick keystrokes survive, but a finger is never bent further than the touch.
   - If a finger is still in a key when fully straightened, the hand rises by that much on the next frame.
6. **No build-up.** The page's finger turns are undone the next frame unless the clip has rewritten that bone, so they never add up.

**The desk.** The room draws the desk as a single 3 mm skin (`room_static_13`, top 0.970–0.973 m, front edge z ≈ −0.845). The resolver treats the 3 cm under that top as solid.
- **Finding:** the page QA's desk test (`page_checks.js`, inside-intervals with 1 cm margins) cannot see anything inside a 3 mm skin. An arm through the desk top can never fail it. That is why the forearm-through-the-edge G12 saw passed every test. Not fixed here (it is the QA's); reported.

## Measured
All measurements are in the page, scene desk_14, every 0.25 s.

**Mouse, 15 s** (`mouse_contact.json`):

| Measure | Value |
|---|---|
| Hand skin into the shell | max 1.3 mm, median 0 |
| Below the pad | ≤ 0.1 mm |
| Wrist above the pad | 5.6 cm (was 8.6) |

**Keys, 15 s, ten fingertips** (`key_contact.json`; skin over the cap under it, per distal phalanx):

| | min | median | max |
|---|---|---|---|
| all fingers | −4.4 mm | −0.1 mm | +8.2 mm |

- 97% of samples are within ±3 mm. A real key travels about 4 mm.
- Before: hovering 0.5–1.1 cm on main (G12). On this branch before the fix, the fingertips were not over the keyboard at all.

**Arm against the desk** (skin of the arm and sleeve):
- After the resolve: 0 mm in both modes.
- Before the swing: up to 13 mm when a mode starts. The swing engaged on 11 frames typing and 5 mousing, at most 12.6°.
- Check of the check: with the desk slab raised 4 cm as a test, the swing engages on most frames and stops at its 15° cap. Up to 12.8 mm then stays in, held as contact rather than hoisting the shoulder.

**Visual suite:** see the commit message.

## Pictures
- `../hands/mouse_grip_contact.jpg`: the mouse against mouse1 and mouse2.
- `keys_and_arms.jpg`:
  - Top row: references kb1 and kb2.
  - Middle row: our top-down over the keyboard, and from his left at key height.
  - Bottom row: typing and mousing from his right, with the arms out of the desk and the elbows natural. An earlier version swung the elbow up to 20° on a too-fat arm model and hunched the shoulder; that is why the swing is now skin-tested and capped.

## Open
- **G12's typing clip.** Needs the clip's keyboard reference point (where the performer's home row was) to replace the clip-to-room offset in step 1. The resolver does the rest.
- **The QA's desk test** cannot see this desk (above).
- **Right little finger.** On our current static-finger typing clip it lifts up to 8 mm at moments.
