# Everyday clips for the character (v5) with NVIDIA Kimodo

Preview only: nothing here is used by the live site and nothing is merged to main. The character is the fictional
~20-year-old man of `docs/design/char-tripo-v5/char_tripo_v5.glb`, the owner's choice (Tripo biped rig, 41 bones, no
finger bones). Its rig is identical to v4's (`char-tripo-v4`: the same bone names, rest transforms and scale), so the
clips play on both; the renders use v5 (d0fc37d). No brands or logos.

Seven clips, generated with **Kimodo-SOMA-RP-v1.1** (text-to-motion with kinematic constraints, SOMA skeleton),
retargeted onto the rig and rendered in the room (`room_clean.glb` with the live site's chair, `chair_owner.glb` of preview/room-upgrade-live,
added whole as the live `room.html` does; its seat top measures 0.50-0.505 m). While he sits, the chair is placed under
his hips (hip joints 10 cm in front of its pivot: his buttocks on the rear half of the seat, back by the backrest).

| clip | file | length | what happens |
|---|---|---|---|
| a | `clips/a_walkin.glb` | 12.0 s | walks in from the door, pulls the chair back by its backrest, sits on it (swivelled towards him), turns to the desk and rolls in |
| b | `clips/b_type.glb` | 16.0 s, loops | seated typing with both hands, the right hand on the mouse from 9 to 15 s |
| c | `clips/c_read.glb` | 14.0 s, loops | seated reading a book open on the desk (left of the keyboard, the chair swivelled 33° towards it), two page turns |
| d | `clips/d_phone.glb` | 14.0 s, loops | seated, the chair turned 29° to the room, scrolling a phone held in both hands |
| e | `clips/e_getup.glb` | 11.7 s | stretch in the chair, stand up (the chair rolls back), step out to the right and walk the chair in under the desk with the left hand |
| f | `clips/f_bed.glb` | 11.5 s | walks to the bed, sits on its edge, lies down on his back, head on the pillow |
| g | `clips/g_wake.glb` | 9.5 s | wakes up on his back, sits up, swings the legs over the edge, stands up |

Each GLB is the bare rig (no mesh) with one animation: rotations of all 41 bones and the Hip translation, 30 fps,
resampled (tolerance 2e-4), 0.3-0.4 MB. The rig's origin goes at the place in `room_build/kimodo/opts/cfg_*.json`
(`root`: x, y, z, turn about y); the chair moves by its `chair` keys (and `chairFollow`: the push in e).

`renders/<clip>.mp4`: the clip in the room from two cameras side by side (640x360 each, 30 fps, headless Chromium on
an RTX 4090 pod: WebGL on the NVIDIA card through ANGLE/EGL);
`renders/<clip>_sheet.jpg`: six frames from each camera. `qa/`: the contact QA (below).

## Prompts and constraints (`room_build/kimodo/specs/`)

Kimodo's canonical frame: the SOMA Hips root at the origin at frame 0, +Z = the desk direction (world -Z), metres of the
SOMA skeleton. `room_targets.py` turns room points into it (the rig is 0.949 x SOMA by leg length; the floor is y 0.16).
The desk clips pin the hips to a seat height (generated for the 0.52 m chair; the retarget then fits them onto the live 0.505 m seat) and the wrists to the keyboard, the mouse or the book
(end-effector constraints, every 0.5 s); the bed clips place a whole lying or seated pose (moved and turned) on the
mattress; walking uses 2D root waypoints with headings. Long actions are split into short generations (Kimodo allows
10 s per prompt and its chained segments drift) and joined (`join.py`: heading and ground position matched, 8-frame
crossfade): e = e1_up + e2_push, a = a1_walk + a2_sit + a3_roll. The pose sources named in the specs (`pose`) are
earlier takes, also listed (b_type1/2, d_phone1, g_wake1). Every spec ran 2-3 seeds x 4 samples; the take kept is the
one with the smallest constraint error and jerk (`eval_e.py`), then checked in the room.

- **a1_walk**: "A person walks into the room and stops next to an office chair." (4.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [54, 119]
- **a2_sit**: "The person pulls the chair back with the right hand on its backrest." (2.5 s) / "The person turns around and sits down on the chair." (3.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [69]; RightHand (targets) at 2 frames [12, 63]; Hips (placed pose) at 2 frames [150, 164]
- **a3_roll**: "A seated person swivels the office chair to face the desk and rolls closer to it." (3.0 s); seeds [1, 2, 3] x 4 samples; constraints: Hips (placed pose) at 2 frames [0, 8]; Hips (placed pose) at 2 frames [78, 89]
- **b_type1**: "A person sits relaxed on an office chair at a desk, typing on a computer keyboard with both hands, looking at the screen." (8 s) / "A person sits at a desk typing on a keyboard with the left hand and moving a computer mouse with the right hand." (8 s); seeds [1, 2] x 4 samples
- **b_type2**: "A person sits relaxed on an office chair at a desk, typing on a computer keyboard with both hands, looking at the screen." (8 s) / "A person sits at a desk typing on a keyboard with the left hand and moving a computer mouse with the right hand." (8 s); seeds [1, 2] x 4 samples; constraints: LeftHand+RightHand+Hips (targets) at 29 frames [0, 15, 30]...
- **b_type3**: "A person sits relaxed on an office chair at a desk, typing on a computer keyboard with both hands, looking at the screen." (8 s) / "A person sits at a desk typing on a keyboard with the left hand and moving a computer mouse with the right hand." (8 s); seeds [1, 2] x 4 samples; constraints: LeftHand+RightHand+Hips (targets) at 29 frames [0, 15, 30]...
- **c_read2**: "A person sits on a chair at a desk, leaning forward slightly and reading a book that lies open on the desk, forearms resting on the desk." (7 s) / "A person seated at a desk reads a book on the desk and turns a page with the right hand." (7 s); seeds [1, 2] x 4 samples; constraints: LeftHand+RightHand+Hips (targets) at 18 frames [0, 20, 40]...
- **d_phone1**: "A person sits relaxed on a chair holding a smartphone in both hands, looking down at it and scrolling with the thumb." (7 s) / "A person sitting on a chair looks at a phone held in the right hand and scrolls with the thumb." (7 s); seeds [1, 2] x 4 samples
- **d_phone2**: "A person sits relaxed on a chair holding a smartphone in both hands, looking down at it and scrolling with the thumb." (7 s) / "A person sitting relaxed on a chair looks down at a phone held in both hands and scrolls with the thumb." (7 s); seeds [1, 2] x 4 samples; constraints: LeftHand+RightHand+Hips (targets) at 15 frames [0, 30, 60]...
- **e1_up**: "A person sitting on a chair stretches both arms up over the head and leans back, then relaxes." (4.5 s) / "The person stands up from the chair, pushing it back with the legs." (2.5 s) / "The person steps backward to the right and stops." (2.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [216, 268]; Hips (hips height) at 4 frames [0, 40, 80]...
- **e2_push**: "A person walks forward slowly, pushing a chair in front of them with the left hand on its backrest." (3.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [89]; LeftHand (targets) at 2 frames [8, 89]
- **f_bed2**: "A person walks forward to the bed and stops." (3.5 s) / "The person turns around and sits down on the edge of the bed." (3.0 s) / "The person lies down on the back on the bed, swinging the legs up onto it." (5.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [105]; Hips (placed pose) at 2 frames [185, 195]; Hips+LeftFoot+RightFoot (placed pose) at 2 frames [320, 344]
- **g_wake1**: "A person lying on the back wakes up and sits up." (4 s) / "The person swings the legs over the side of the bed, puts the feet on the floor and stands up." (4 s); seeds [1, 2] x 4 samples
- **g_wake2**: "A person lying on the back wakes up and sits up." (3.5 s) / "The person swings the legs over the side of the bed and sits on the edge." (3.0 s) / "The person stands up and takes a step forward." (3.0 s); seeds [1, 2, 3] x 4 samples; constraints: root2d at frames [284]; Hips+LeftFoot+RightFoot+LeftHand+RightHand (placed pose) at 2 frames [0, 15]; Hips (placed pose) at 2 frames [190, 200]

Takes kept: a1_walk s3_0, a2_sit s2_1, a3_roll s3_1; b_type3 s2_0; c_read2 s1_1; d_phone2 s2_1; e1_up s3_0, e2_push s1_2;
f_bed2 s1_2; g_wake2 s2_1. Kimodo's own post-process is on for single-prompt generations and off for chained ones (its
per-segment pass broke later segments' constraints); foot sliding is fixed in the retarget instead.

## Retarget (`room_build/kimodo/retarget.mjs`, options in `opts/o_*.json`)

- The source is turned to face +X; each mapped bone takes its SOMA joint's world rotation with the two rest poses
  aligned per bone (SOMA rests in a T-pose, the rig in an A-pose). Spine chain: Hips→Hip, Spine1→Waist, Spine2→Spine01,
  Chest→Spine02, Neck1/Neck2→NeckTwist01/02, Head; arms and legs one to one; twist bones keep their rest pose.
- The Hip follows the midpoint of SOMA's hip joints (the rig's Hip sits at its thigh joints), scaled 0.949; the body is
  lowered 2.9 cm because the rig's ankle sits lower over its soles.
- **Foot contact**: wherever Kimodo's contact labels say a foot is planted and the ankle is near the floor, the ankle is
  locked to the run's mean position (two-bone leg IK, eased over 4 frames): no sliding. Soles never go under the floor.
- **Seated** (the windows in `seated`): the torso leans forward over the hips (0.33 rad typing, 0.45 reading, 0.25
  phone and the get-up, the head turned back up by 60-75 %) so the shoulders are over the hips and the elbows bend at
  ~100-115° by the body; both feet are planted flat on the floor 0.36 m in front of the hips, 0.13 m to each side
  (`feetPin`, two-bone leg IK, the toes put down too).
- **Seat contact** (`seatfit.py` with the scene's `seatGap`): every 0.1 s the skin behind the hip joints (buttocks)
  over the seat is compared with the seat top under it; the Hip height is corrected per sample (two passes, 0.5 s
  smoothing, linearly interpolated) so the deepest buttock point is 1.5 cm into the cushion. `qa/<clip>_seat.json`
  holds every sample.
- **Hand targets**: two-bone arm IK onto the keyboard (wrists over ASDF and JKL, keytops 1.012 m), the mouse
  (`MOUSE_AT` of room.html), the backrest during the pushes and pulls, the book (resting and turning pages); the
  hand is levelled (pitch -0.08 to -0.1 rad); Kimodo's own small wrist motion (its offset from its 1 s mean, 50-60 %)
  rides on the target so the hands are not frozen.
- **Bed**: while his pelvis, back, head or thighs are over the mattress the root rises until their undersides are on the
  mattress top (0.82 m), smoothed over 0.3 s; hands over the bed rest on top of it; feet up on the bed are not locked to
  the floor; timed root offsets (`rootKeys`) keep the feet and calves in front of the bed's solid side when he sits
  on its edge.
- Loops (b, c, d): the last 0.6 s ease into the first frame, before the hand pins (so the seam keeps the contacts).
- **Smoothing** (against Kimodo's frame-to-frame tremble): a zero-phase Gaussian over time on every bone's rotation
  (quaternions sign-aligned and averaged, sigma 1 frame ≈ 5 Hz on the limbs, 1.7 frames ≈ 3 Hz on the spine, neck and
  head) and on the Hip translation, right after the mapping; a second pass after all the IK (sigma 1-2.2 frames) with the
  hand pins re-solved. The hand targets' detail is low-passed too. Reaches (to the mouse, page turns) follow eased paths
  (smootherstep) with a small arc. `qa/<clip>_jitter.json`: the high-frequency jitter (RMS of the 2nd derivative of the
  wrists', head's and hips' positions after removing their 4-frame-smoothed motion), before and after.

## Quality gate (`qa/`)

Every 0.1 s the skinned mesh (every 2nd vertex, CPU skinning in the page) is tested against: the chair (its own mesh as
placed at that moment, as columns of inside intervals at 1 cm), the desk top, the keyboard box (`room.html`'s split),
the bed (frame and mattress, 2 cm allowed for the duvet) and, in c, the book (in its own frame). `qa/<clip>_qa.json`
holds every sample; `qa/contact_table.md` the table (`room_build/kimodo/contact_table.py`).

Summary (the full per-second table is `qa/contact_table.md`):

- Desk and keyboard: 0 in a, b, d, f, g; (b) fingertip touches ≤0.7 cm; (c) the right forearm rests on the keyboard's end
  and the book's edge ≤2 cm around the page turns (the hands are clear); (e) 4 samples ≤1.5 cm as he rises.
- Seat: buttocks 1.0-2.0 cm into the cushion in every seated sample of b, c, d and e (never above it); (a) 0.4-3 cm, with
  one 0.4 s dip to 6.6 cm while the chair swivels under him.
- Thighs: with his feet flat, the fronts of the thighs press ~6 cm into the seat's front edge in every seated clip: the
  0.505 m seat is higher than his knees (~0.48 m). Heels up or a seat ~3 cm lower would clear it (an owner decision).
  His back rests 2-3 cm into the padded backrest.
- (e): the left calf brushes the chair ≤4 cm while his legs push it back; (a) the hands' grip on the backrest ≤2 cm.
- Bed (f, g): lying on the mattress, sitting on its edge; ≤5 cm at the mattress edge while sitting down or getting up.

## Real references (`refs/`)

`refs/<clip>_refs.jpg`: real photos (Pexels license, `refs/SOURCES.md`: page, photographer, view; brand marks
pixelated) next to our frames: typing (side, 3/4 rear), reading at a desk, phone in a chair, stretching in an office
chair, lying in bed, sitting on the bed's edge. The typing pose follows them: hips back on the seat, an upright trunk
over the hips, elbows bent by the body, wrists level with the keys, feet flat.

## Licences and attribution

- **Kimodo** code (github.com/nv-tlabs/kimodo, commit 58e7818): Apache-2.0. **Kimodo-SOMA-RP-v1.1** weights: NVIDIA Open
  Model License (https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/), attribution
  required: "Motion generated with NVIDIA Kimodo (Kimodo-SOMA-RP-v1.1), NVIDIA Open Model License." The weights stay on
  the (deleted) pod; only the generated motions are here.
- Kimodo's text encoder: LLM2Vec (McGill-NLP, MIT) on Meta Llama 3 8B Instruct (**Llama 3 Community License**,
  https://llama.meta.com/llama3/license): used on the pod only, not distributed. Weights from the public
  `NousResearch/Meta-Llama-3-8B-Instruct` re-upload, whose four shards have the same SHA-256 as
  `meta-llama/Meta-Llama-3-8B-Instruct`'s (checked on the pod: d8cf9c4d…, 8d4782b4…, 3acdd690…, 67e9ad31…); no Hugging
  Face token was used. "Built with Meta Llama 3." Transformers 5.x attaches the MNTP adapter with mismatched keys, so
  `patch_llm2vec.py` loads it explicitly through PEFT (as LLM2Vec's own loader does).
- The SOMA skeleton definition (`soma77.json`, joint names and rest offsets) comes from the Kimodo package (Apache-2.0).
- The retarget, scene, QA and pod scripts are made for this project.

## GPU and cost

One RunPod pod (RTX 4090, Secure Cloud, $0.74/h) for 80 min: install, model download, all generations; deleted at the
end. A second pod (L40S) was created by mistake by the same request loop and deleted after ~10 s. Total about $1.00.
The pod named BRAIN was not touched. The pod ran `room_build/kimodo/pod/exec_server.py` (commands over the RunPod
HTTPS proxy, a random per-run key in the pod's environment, not stored anywhere) and `gen_server.py`.

## Rebuild

1. Pod: `pip install -e` Kimodo (with cmake), download the four models, `patch_llm2vec.py`, then
   `TEXT_ENCODERS_DIR=… TEXT_ENCODER_MODE=local python gen_server.py` and drop `specs/*.json` into `/workspace/queue`.
2. Here: `python npz2json.py take.npz take.json` (or `join.py a.npz b.npz [c.npz] out.json 8`), then
   `node retarget.mjs take.json char_tripo_v5.glb clip.glb opts/o_<clip>.json` (room_build's node packages + three).
3. Renders and QA: `scene/` needs `three` (node_modules/three), `room` (preview/chair-tripo's `web/room`) and
   `char.glb` (the v5 GLB) next to `scene.html`; then `node render.mjs opts/cfg_<clip>.json out --fps 15` (Chromium at
   /opt/pw-browsers; it writes the MP4, the sheet and the QA JSON).
