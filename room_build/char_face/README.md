# The Tripo character's face, reworked to the reference photos (no credits)

Run from this folder with `room_build/node_modules` linked here and Python packages mediapipe, opencv-python-headless,
playwright, pillow, numpy; the face landmarker model `face_landmarker.task` (MediaPipe) next to `lm.py`.

1. `node dump.mjs <char_rig.glb> mesh` : arrays and textures of Tripo's rigged mesh.
2. `FOC=1.44 python fit.py <glb> cams.json` : cameras for the photos (landmark PnP for the close-ups, silhouettes for the profiles).
3. `JAWCL=0.010 python warp.py <glb> mesh cams.json wA 1.0 --jaw`, `node applypos.mjs`, then a second pass (`JAWCL=0.006`):
   the face reshaped to the photos' triangulated landmarks (Gaussian RBF, hair and neck fixed).
4. `python bake.py <warped glb> <its dump> <its cams> out` : the photos projected onto the base colour; normal map
   flattened on the face skin, skin roughness 0.5, metalness 0.
5. `node ../build_char_tripo.mjs <tripo dir> <out.glb> <dir with pos.f32 nrm.f32 base.png normal.png orm.png>`.
