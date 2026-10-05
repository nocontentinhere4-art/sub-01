# Character v5: a Tripo bust with a natural neck on the Tripo body (candidate next to v4)

AI-generated content, made with Tripo (tripo3d.ai, paid API) and used under Tripo's terms of service. The character is
an original fictional ~20-year-old man, not a real person, with no brands or logos. Preview only: nothing here is used
by the live site.

v4 (`../char-tripo-v4/`) uses the owner's own Tripo head. That head has no neck under its collar, so its neck stops
just under the chin. v5 is the alternative with a full natural neck: a Tripo bust (head and bare neck), generated
through the API from the same face reference, on the same v3 body, rig and clips. The owner chooses between them.

## `char_tripo_v5.glb`

6.2 MB (meshopt and WebP), 1.75 m, faces +X, `idle` (15.4 s) and `walk` (2.37 s, in place), the 41-bone Tripo
skeleton. Materials: the body (matte, roughness 0.8) and the bust (base colour 4096 px, normal 2048 px, roughness 0.8).

## Tripo tasks (2026-10-05): 95 credits

| step | task id | settings | credits |
|---|---|---|---|
| image to image | `7fd7c84b-8477-4111-99b1-64f31a4d7b7c` | `chat_image_2.5_sunburst`, quality high; input `../char-tripo/refs/face_front.png`; prompt: keep the same face and hair unchanged, show the head and bare neck down to the collarbones, no clothing or collar, black background (`qa/bust_input.webp`) | 25 |
| image to model | `35319971-635a-49d4-ab4e-4e1bea903233` | model v3.1-20260211, geometry detailed, face limit 1M, texture v3.5-20260815 extreme, PBR, alignment original_image | 70 |

Balance: 1275 before, 1180 after. Commands: `python room_build/tripo_char.py edit ...` and
`python room_build/tripo_char.py image ...` (the proxy supplies the key).

## How it was put on the body (scripts in `room_build/char_v5/`)

1. **Fit** (`fitbust.py`): a similarity ICP (scale, rotation, translation) of the bust's face and hair onto the owner's
   head as placed in v4. The median distance is about 1.5 mm and the scale 0.171.
2. **Cut** (`stage1b.py`, run with Blender's Python module): the shoulders are cut away (outside the neck, below the
   jaw line), so nothing pokes through the hood. Small holes are filled.
3. **Decimate** (`simp.mjs`): meshopt simplification to 60k triangles, keeping UV seams.
4. **Crew-neck collar** (`collar.py`): a round, dark T-shirt collar band about 1.5 cm high, following the bottom edge of
   the neck, with the T-shirt continuing a little way down inside the hoodie.
5. **Skin and body** (`weights_full.py`, `graft.mjs`): the weights come from the nearest body vertices (head, neck,
   upper spine, clavicles). The body's old head, neck and hair are removed, and the hood is kept whole. Built with
   `MATTE=0.8 node room_build/build_char_tripo.mjs`.

## QA

- `qa/quick_preview.webp`: front, 3/4 and profile at face distance, an idle frame, a walk frame, and the full body.
- `qa/neck_seam.webp`: the neck and hood from the front, 3/4, side and back.
- `qa/anim_face.webp`: two idle and two walk frames at face distance.
- `qa/face_ref_v4_bust.webp`: the reference, the v4 head (the owner's) and the bust, at the same cameras.

**Better than v4.** A natural neck of normal length runs into a round dark T-shirt collar inside the hoodie, with no
seam from any angle and none in the clips.

**Worse than v4.** The face is Tripo's, not the owner's own export. It is close to the references, with a slimmer jaw,
but:

- the skin is flatter and a little warmer;
- the nostrils read darker and heavier from the front;
- the hair is a little less defined.

**Left:** a few light-grey wisps on the inner hood rim, close up only.
