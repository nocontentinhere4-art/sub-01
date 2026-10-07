# G21: `room.html?char=mixamo` wiring: status

Branch `preview/mixamo-wiring` (off `origin/preview/mixamo-pipeline`). The raw Mixamo FBX stay in scratch (from
`claude/loving-davinci-6hqmjx:mocap_src/mixamo/`); nothing raw is committed.

## State (2026-10-07, live)
- [~] 2. Armpit weights in autorig. This is partly a weights defect and partly the pose itself (numbers below).
- [ ] 1. `?char=mixamo` loads char_mixamo.glb + char_mixamo.js, Mixamo clips baked for our skeleton and chair
- [ ] 3. rig_change.mjs: the 6 PENDING items; contact_pass.mjs over every frame
- [ ] 4. `wiring_sheet.jpg`
- [ ] 5. full pytest + visual hard_failures

## 2. Weights (rig/autorig/fit.py, write.mjs; measured every frame at 30 fps, all vertices, qa.html's test)
What changed in autorig:
- **Bound as modelled, not in the T-pose.** Each bone's inverse bind is now its T-pose placement taken back through the
  rigid T-posing map of the v5 joint it stands for. Rigid parts pose exactly as before. A vertex shared by two bones is
  no longer T-posed by a blend first: blending is not invertible where the maps differ, so the arms coming back down
  never undid the T-posing at the armpit.
- **Span rule.** A limb bone only weights skin within its own span along the limb (±6 cm elbow, ±4 cm wrist, ±7 cm knee,
  ±5 cm ankle). v5's own skin put 0.18 of the forearm on the armpit's sleeve: with the elbow bent 90° that alone moves
  it 5–7 cm.
- **Legs only below the hips** (+10 cm). v5's skin put up to 0.2 of the thigh on the chest at 1.1 m.
- **Sleeve and hoodie as two parts** (old skin's main joint). More than 7 cm from the shoulder joint, the sleeve takes no
  spine weight and the hoodie no arm weight. Under the shoulder, the sleeve takes no clavicle weight; the hoodie keeps it.

| clip (raw Mixamo, on the rig) | before (G20) L / R | after L / R |
|---|---|---|
| Seated_Idle | 2.4 / 2.4 cm (532 / 373 verts) | 2.4 / 0.6 cm (30 / 2 verts) |
| Typing | 2.3 / 2.0 cm (113 / 64) | 2.0 / 1.0 cm (9 / 9) |
| Sit_To_Type | – | 1.9 / 1.4 cm (8 / 7) |
| Type_To_Sit | – | 1.9 / 1.9 cm (7 / 15) |

Why it does not reach 1.2 cm from weights alone (measured): with every sleeve vertex rigid on its arm and every hoodie
vertex rigid on the spine (no blending at all), Seated_Idle is still 2.5 / 2.1 cm. Sitting and Stand_To_Sit are still
2.5 cm over 1300+ vertices. The performer's arms hang against a slimmer body: abduction 9–25° against v5's modelled
27°, and the upper arm 20° forward. Our hoodie and sleeves are baggy. That is the pose against our body, the same
kind of fit as the chair: it goes in the bake, as an arm-clearance step next to G12's seat fit (in progress).

Tried and measured, not kept: re-centring the shoulder joint on the sleeve's cross-section (right side worse); welding
sleeve and hoodie weights across the seam; ramps instead of cuts; a pose-driven pass that hands the sleeve's weights
to the hoodie where they collide (diverged: 154k → 500k hits over 12 rounds).
