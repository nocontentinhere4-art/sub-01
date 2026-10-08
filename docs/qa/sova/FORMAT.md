# Sova clips: the GLB format, for the desk-states layer (G23 → G14)

The clips are the same format as `web/room/mh_mx/*.glb`, so `char_mixamo.js` `fixClip` applies unchanged.

## Files
- **One GLB per clip, one animation in it.** It is animation-only: no mesh, written by `kimodo_g12/writeclip.mjs`.
- Location while the licence is pending: `docs/qa/sova/desk/<slug>.glb` on `preview/sova-phone-src`.
  - Nothing goes into `web/` until COORD says so.
  - When it does, the drop is `web/room/desk_states/<slot>.glb` plus your `index.json`, as you proposed.
- The AnimationClip name = the file's slug. Slugs are the English name normalized: lowercase, `[New!]` / `[MOCAP]` / `[HANDMADE]` dropped, non-alphanumerics → `_`.
  - Examples: `desk_start_01`, `desk_look_behind`, `neutral_1`, `look_left_idle`.
- `docs/qa/sova/desk/index.json` lists each clip: slug, source package/set/English name, duration, loop yes/no, category, a suggested slot, and its room contact numbers.

## Skeleton, units, frame
- **Bones:** char_mixamo's own node names, exactly (`mixamorig:Hips` … `mixamorig:RightHandPinky4`), under the `mixamo` node (scale 0.01), as in the character.
  - Rotations: every one of the 65 joints.
  - Translation: Hips only, kept (not stripped).
- **Units:** as mh_mx, i.e. the Hips translation is in the 0.01 node's frame (centimetres). After `fixClip` it is metres, feet at y = 0, facing +Z.
- 30 fps, linear.

## Seated placement
- Every seated clip is baked for **our** chair by the same fit as the Mixamo desk clips (`kimodo/mx_fit.py`, mx_clips.json `seated` defaults):
  - hip joints at 0.68 m and 4.5 cm forward;
  - feet planted by leg IK, soles 2 mm over the floor;
  - sleeves swung off the hoodie (clearMax 0.8 cm);
  - knees at least 0.55 m.
- Plus `seatOrigin`: the seated hip joints are moved to x = z = 0, as the transitions are. Place them like `room_seated_idle`: `seatAt` [0, −0.075].
- The Sims chair was lower (its hip joints at 0.42–0.50 m after scaling); the fit lifts him 0.22 m onto ours.
- None of the loops needs the chair moved.
- `desk_start_01` is a **sit-down transition**: he walks in, turns 48° and sits. It ends seated at the origin, so it is a candidate for the stand→sit step, not a loop.

## Loops
- The Sova seated clips are pose-pack loops: frame 0 = the last frame within 0.2°, so they are seamless.
- They are nearly still: the median joint moves 0.1°; the head/arms up to 8–9° in the Neutral ones, more in the LOOK clips. They breathe rather than act.
- Lengths: 6.7 s (Neutral, LOOK LEFT/RIGHT idle), 9.2 s (LOOK BEHIND), 10 s (LOOK DOWN→RIGHT, FRONT→LEFT), 6.0 s (DESK START 01, play once).

## Which clips are which bodies
- Neutral [1–6] and Bored [1–6] are **three** distinct bodies, not twelve:
  - Neutral 1 ≈ 2, 3 ≈ 4 and 5 ≈ 6, within 1–3°.
  - Bored N has Neutral N's body; only the face differs, which our rig doesn't carry.
  - So only `neutral_1`, `neutral_3` and `neutral_5` are baked.
- Action & Reactions ([MOCAP] looking around / away / left / right, neck stretching, thinking chin, frustrated, distracted-smile) are all **standing** clips (hips at 1.0 m).
  - At the desk they need their upper body layered on a seated lower body. That's next; they are not in this first batch.
