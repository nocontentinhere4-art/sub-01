# UniMate test: lying in bed watching the phone (G22, evaluation only)

The question: can [UniMate](https://github.com/Friedrich-M/UniMate) produce the one motion Mixamo doesn't have? The motion is the boy lying on his back or side, a phone held in one or both hands, with small live thumb and head movement, as a 10–20 s loop.

**Verdict: no.**
- From text alone it never puts him in bed with his hands up.
- With its motion-editing mode over our real lying clip it gives a 2 s arm pose with frozen fingers.

Nothing here is wired into the room or `boy_mh.js`.

## Verdict

- **Fingers: dead.**
  - In the edited clips (the only ones that lie down), the 30 finger joints move at most 1–3° in 37 of 60 samples. The others reach 5–23°, almost all of it a slow bend of the index and middle knuckles; the thumbs move less than the index, even with "moves its thumbs" in the prompt.
  - The hands stay in the rig's rest curl. They never close into a grip and never tap.
  - In text-only samples the fingers are frozen too, apart from glitches (single joints jumping 30–100°).
  - In the 10 s chained clips they drift and twist (up to 178°), which is broken, not alive.
  - The reason: UniML3D trains its Mixamo motion on 22 body joints, so our 65-joint rig's fingers are joints the model never saw animate (its `rig_preprocess` README says so: "sampled as an unseen skeleton").
- **Penetration:**
  - In no edited sample does a wrist come within ~9 cm of the spine axis or ~8 cm of the head axis.
  - In the sheets the hands stay outside the hoodie and the face.
  - There is no phone in these clips. With open, ungripping palms a phone prop would float between the hands or need the hand pose invented around it.
- **Next to the real Mixamo mocap: not plausible.**
  - The body is good only because it is our capture held fixed (`room_bed_lie`).
  - Everything we would be buying (arms, wrists, fingers, the head) is generated: hand motion invented by a model with no capture behind it. That is exactly what `docs/design/mixamo/README.md` rules out ("No hand motion is invented anywhere (the hand clip was rejected)").
  - The arms hold one pose with a slow drift. The head turns 10–68° in 2 s (52° in clip A), more than "small natural head movement".
- **Length:**
  - A sample is 60 frames at 30 fps, 2 s.
  - Motion editing (the only mode that lies) cannot be chained: `--motion_expand` and `--motion_edit` exclude each other.
  - Our lying window is 5.5 s. So there is no 10–20 s loop, and nothing that loops on its own.

## What was run

UniMate at commit `5febc2d`, checkpoint `unimate_uniml3d_f60_v3` step 150000 (CC BY-NC 4.0; the site earns nothing, owner OK for a test). Seed 7 throughout. Not committed: checkpoints, datasets, the decoded character, raw samples (all stayed in scratch).

**Character.**
- `web/room/char_mixamo.glb` was decoded (meshopt removed, dequantized), then run through `rig_preprocess`.
- Joint labels: all 65 came from the Mixamo template, and I checked them by hand. The `Thumb4`… end joints are labelled as the finger, as in the training rig.
- Facing pair: `RightUpLeg` / `LeftUpLeg`. The preview's front view has his right on the image's left, as it should. The rig fits the model's 71-joint limit.
- A second copy was pruned to the 22 joints the model trained Mixamo on (finger weights folded into the hands) to rule out the unseen fingers as the cause. It behaved the same.

**1. Text only** (both rigs, cfg 3 and 5, 4 samples each; 96 clips):

| prompt | lies down? |
|---|---|
| An object lies on its back. | yes, in 11 of 16 (flat, curled or prone) |
| An object lies on its back, holding both hands up in front of its face and looking at them. | no: stands or crouches |
| An object lies on its back, holding one hand up in front of its face and looking at it. | no |
| An object lies on its side, looking down at both hands held in front of it. | no |
| An object lies on its back and moves its thumbs while holding both hands above its chest. | no |
| An object lies on its back looking at its raised right hand. | no |

None of the 80 hand prompts lies flat. Their hips stay at 0.27–0.81 of the canonical size (standing is about 0.95). The model keeps the hand action and drops "lying", which makes sense: the training captions have lying clips and texting clips, never both.

**10 s chains**: `--motion_expand` with 6 copies of a prompt (10.3 s; both rigs, 2 samples each). He stands and looks at both hands, which is basically Mixamo's standing texting.

**2. Motion editing over our lying clip.**
- `web/room/mh_mx/room_bed_lie.glb` was trimmed to its lying part (10.5–17 s) and baked onto the character as its own clip (`--save_clips`; 63 joints, since the toe ends are pruned).
- Hips, spines and legs were held (`--keep_joints`); a second set also held the shoulders. Arms, neck, head and fingers were regenerated.
- Windows at frames 0 and 100, cfg 3 (plus cfg 5 on one set), 3 samples each, 60 clips:
  - "An object holds both hands up in front of its face and looks at them."
  - "An object holds one hand up in front of its face and looks at it."
  - "An object lies on its back, looking at both hands held above its chest."
  - "An object holds both hands together above its chest and moves its thumbs."
- All 60 lie (the body is the capture). The best ones raise both forearms over the face with the hands close together, the nearest thing to holding a phone up.

## Files

- `unimate_edit_both_hands_A.glb`: edit, "both hands up in front of its face", window 100–160, cfg 3, sample 0. The best of the 60.
- `unimate_edit_thumbs.glb`: edit, "moves its thumbs", same window. For the fingers: max 10°, at the left index knuckle; the thumbs barely move.
- `unimate_text_only_10s.glb`: text only, 6 chained segments of the "lies on its back, holding both hands up…" prompt (10.3 s), 65-joint rig. It stands.
- `contact_sheet.jpg`: those three clips, 8 frames each. Rows: from the feet, side, hands close-up. Rendered headless (three.js, SwiftShader).
- `text_only_overview.jpg`: all 48 cfg-3 text-only samples, mid-clip, from the feet and the side.

The GLBs are viewer copies: the mesh simplified to 20 %, 512 px WebP textures, meshopt. They are in UniMate's canonical frame: about 2 units tall, on the floor (not our bed), facing +Z, so they are not room-ready.

## Time and money

- Pod 1 (setup and text-only sampling): 19.9 min, $0.245. A 24 GB GPU at $0.74/h; RunPod had no A5000 free, so any 16–24 GB card was allowed.
- Pod 2 (motion editing): 4.3 min, $0.053.
- Total: **24.2 min, about $0.30.** Both pods were deleted by the runner when their job ended. No other pod (BRAIN included) was touched.
- Driving the mesh, rendering and measuring ran on CPU in the cloud session (about 1.5 h of wall time).
