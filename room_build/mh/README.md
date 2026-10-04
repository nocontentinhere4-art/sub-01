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
- `glb/clips/desk_mouse_ik.glb`: the mouse held as in the owner's photos: palm resting on the mouse's back, fingers
  down its front (GRIP_R [22,32,18] deg over 25% of the recorded fingers), thumb on its inner side, an index click now and
  then. Mouse: a dome 6.4 x 7.6 x 11.6 cm, centre (-0.36, 0.807, 0.40) for hips at the origin (next to the keyboard's
  right end); wrist pin (-0.345, 0.828, 0.305), hand pointing straight (yaw 0.12 in, no recorded hand turn), pitched up 0.3; index and middle on the buttons, ring and little finger down the right side, thumb out on the left side. Left hand resting on the keyboard.
- Scripts: `build_mh.mjs` (base GLB), `anim_mh.mjs` (retarget; env DY, YAW, ANIMONLY, NAME), `rename_mh.mjs`.
  The source FBX files are not in the repo.
