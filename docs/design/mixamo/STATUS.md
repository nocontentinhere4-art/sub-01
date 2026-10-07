# G20 — Mixamo Standard Skeleton without mixamo.com: status

Branch `preview/mixamo-pipeline` (off main). Updated as work lands.

## State
- [x] `room_build/rig/autorig/` fitter running on v5 (web/room/char_v5.glb): T-pose from v5's own skin, 65 Mixamo bones fitted, weights computed, GLB written (7.3 MB, meshopt; positions float).
- [ ] `room_build/rig/autorig.sh` wrapper + render sheet + deformation/contact numbers (Seated_Idle, Laying_Sleeping, Typing)
- [ ] G12 loader/check integration, automatic rig-change checklist report
- [ ] Fallback: mixamo_upload.sh / mixamo_import.sh / UPLOAD_STEPS.md
- [ ] Full pytest + visual results

## Numbers so far
- v5: 3 skinned primitives, 260,660 vertices, 402k triangles, old skin 79 joints (Tripo, with fingers).
- Output: 65 bones (`mixamorig:*`, Mixamo hierarchy, T-pose rotations copied from the Standard Skeleton), 1.78 m with slides, hips 0.914 m.
- Hand roll needed to reach Mixamo's palm-down T-pose: L 13.3°, R −13.6° (spread over the forearm twist bones).
