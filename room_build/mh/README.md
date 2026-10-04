# MakeHuman rig + real mocap (crude preview, not installed in web/room)

- `glb/boy_mh.glb`: the MakeHuman base body (CC0, makehumancommunity/makehuman: base.obj + default.mhskel, 163
  bones with fingers, + default_weights.mhw), metres, feet at y = 0, bones world-aligned at rest. Main bones renamed to
  the room page's names (Hips, Spine02, Spine01, Spine, neck, Head, head_end, Left/Right Shoulder, Arm, ForeArm, Hand,
  UpLeg, Leg, Foot, ToeBase); fingers (metacarpalN, fingerN-M .L/.R) and twist bones keep MakeHuman names. Placeholder
  body: G2 builds the real one on the same skeleton.
- `glb/clips/*.glb`: animation-only clips, 20 fps, retargeted with all fingers from Rokoko mocap (Anderson Rohr
  "Everyday Actions" packs 1 and 7, commercial use allowed). Desk modes: `desk_type` (search: typing), `desk_mouse`
  (clicking: right hand on the mouse), `desk_watch` (videos: relaxed in the chair). They keep the recorded finger motion
  as is (the owner rejected a hand-set pose: it looked stiff). The rest are the full source clips.
- `glb/clips/desk_type_ik.glb`: desk_type with a baked arm IK from the owner's typing photo (elbows bent and close,
  hands together on the home row, pointing forward; wrists pinned at world (0.03, 0.878, 0.32) / (-0.13, 0.878, 0.32), drifting with the recorded wrists (70%) for
  a body whose hips sit at the origin), fingers recorded at 80% strength, thumbs swung toward the space bar, fingertips kept above KEYTOP 0.83 (the pin lifts). Awaiting the owner's verdict.
- `glb/clips/desk_mouse_ik.glb`: a palm grip from ergonomic references (wrist extended ~20 deg, index and middle nearly
  straight on the two buttons, ring and little finger on the right flank, thumb on the left flank, hand rolled ~10 deg
  little-finger side down). Mouse: low dome with the hump at the back (radii x 3.1, y 3.6, z front 8 / back 4 cm), hump
  at (-0.36, 0.807, 0.39) for hips at the origin, turned -0.15 rad with the hand. Palm on the hump by contact solve;
  index/middle curl to touch (smoothed); ring/little set (CURL_R_4 [22,38,18], CURL_R_5 [26,42,20]), eased so their undersides stay on the pad (DESK_Y 0.809 + 1.1 cm).
- Room clips (crude, from the owner's "serve il resto"; contacts measured against the room: chair seat 0.505 above
  the floor, mattress top 0.66):
  - `room_walk`: in-place walk loop (1.233 s), travel speed 0.67 m/s; the page moves the root along his path.
  - `room_sit_down` (5.5 s): walks in, turns, sits; ends facing +z, hips at (-0.26, 0.62, -0.25) for a chair whose seat
    centre is at (-0.26, -0.13). `room_stand_up` (3 s): from seated (hips at (0, 0.59, -0.12)) to standing.
    Both keep the hands ON the thighs (HANDSOUT: tapered thigh capsules, r 9.75 cm at the hip to 6 cm at the knee + 1.2 cm skin, checked at the wrist, palm, knuckles, three fingertips and the forearm; the per-frame corrections are spread in time (max over +-5 frames, then a Gaussian) so the hands glide, no jumps).
  - `room_bed_lie` (17 s): sits on the bed edge (legs reach down, LIFT/FEETDOWN), lies back, settles; `room_bed_wake`
    (15.5 s): lying -> sits up on the edge -> stands. Recorded on a ~34 cm bed, lifted by the source hips' height to a
    66 cm mattress.
- Scripts: `build_mh.mjs` (base GLB), `anim_mh.mjs` (retarget; env DY, YAW, ANIMONLY, NAME), `rename_mh.mjs`.
  The source FBX files are not in the repo.

### G2 body (`glb/boy_g2.glb`, built by `build_g2.mjs`)

`node build_g2.mjs <makehuman/data dir> raw.glb && node rename_mh.mjs raw.glb glb/boy_g2.glb`. A fictional young man
(not a real person), built from MakeHuman 1.x CC0 data only: base.obj, then the macro targets (male, age 20, weight 0.4,
muscle 0.5, proportions 0.75, the three ethnic blends at 1/3 each), then the hand targets (finger diameter +0.55, finger
length decrease 1.0, hand scale +0.15; env FD, FL, HS). It is scaled to 1.75 m, in metres, with the feet at y = 0. The rig
is the default default.mhskel (163 bones) with default_weights.mhw, at identity rest, then renamed by `rename_mh.mjs`.

- Eyes: MakeHuman high-poly eye proxy fitted via its .mhclo and scaled to a 24 mm eyeball. Iris, pupil and limbal ring
  are vertex colours; each eye is skinned to eye.L / eye.R.
- Measured on the mesh: 14,444 verts, 28,796 triangles; shoulders 40 cm, hand 19.4 cm, palm (index-to-little knuckle)
  7.5 cm, middle finger 8.4 cm.
- `glb/boy_g2_sheet.jpg` puts the renders next to real reference photos, with faces cropped out:
  - Eadweard Muybridge, *Animal Locomotion* (1887), public domain:
    - side view: https://commons.wikimedia.org/wiki/File:Nude_man_walking_(rbm-QP301M8-1887-553a~3).jpg
    - back view: https://commons.wikimedia.org/wiki/File:Nude_man_walking_(rbm-QP301M8-1887-010c~6).jpg
  - Open palm, CC0 (Unsplash, via Commons): https://commons.wikimedia.org/wiki/File:Man_in_hood_stretching_hand_(Unsplash).jpg
