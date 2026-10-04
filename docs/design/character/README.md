# The character, rebuilt in place (#98, G2)

`web/room/boy.glb` is the owner's original character (Meshy, via Higgsfield), upgraded without changing who he is:
same face, black messy hair, grey hoodie, black track pants with the white stripe, slides over white socks. The 24-bone
rig, its rest pose, the inverse bind matrices and the embedded sit clip are the shipped ones byte for byte, so every
`boy_*.glb` clip and `web/room.html` work unchanged. The build is `room_build/boy_asset/` (README there).

## Sheets
| file | what |
|---|---|
| `sheet_closeups.jpg` | face front, face side, hands, feet, back: old (left) vs new (right), idle clip, same camera |
| `sheet_head_room.jpg` | the frontal head at the room camera's distance (2.2 m, fov 30), 1:1 pixels of a 1280 frame, old vs new |
| `qa_face_{old,new}.jpg` | G8's visual-suite face close-up (`tests/visual`, scene walking 14:00, recipe "face") on the old and the new asset |
| `sheet_clips.jpg` | every clip (sit, idle, walk, door, eat, sleep, text) at the same frames, old vs new, two cameras |
| `room_1280_{day,night}_{old,new}.jpg`, `room_390_…` | `/room?debug&nolive&hour=14|21` at 1280×800 and 390×844, headless Chromium (software WebGL) |

## What the owner sees
- **Face:** smooth (welded mesh, smooth normals, all the skin subdivided once), no facets, no black slivers; the face is
  **repainted as real skin** (three views of his own head rendered, repainted by an image model with the same identity,
  projected back with a depth test; see the build README): pores, real brows and lashes, natural lips, with a light sheen.
- **Eyes:** real eyeballs behind cut-out openings: dark brown iris with fibres and a limbal ring, pupil, glossy cornea;
  eyelid caps for blinking (G3 rotates `LeftEyelid` / `RightEyelid`; eye nodes `LeftEye` / `RightEye` for looking).
- **Hair:** same haircut and silhouette, near-black, shard edges kept crisp, strand normal map and a clumpy roughness;
  the forehead between the bangs is skin (the repaint's hair shadow is kept off it), strands the old paint had
  coloured scalp-pink are hair.
- **Clothes:** authored as fabric materials, the way game clothes are (the old colour map had Meshy's lighting baked
  in; a photoreal repaint of the whole body was tried and rejected, it baked its own folds and light in the same way,
  see the build README): a heathered grey jersey hoodie at the old tone (knit normal map, sheen), black polyester
  track pants with the white stripe (woven normal, roughness ≈ 0.72 after the page's 0.78 factor), white cotton socks
  (ribbed normal), black foam slides; ambient occlusion baked under the hood and in the folds. No skin-coloured
  wedge at the cuffs, no striped flap inside them, no smear on the slides' strap.
- **Hands:** still mitten shapes, subdivided (smooth) with four finger grooves in the normal map; real finger bones are
  left for a later pass (see the build README).
- **Socks with a sole of their own** (#126's bed code): the slides were the sock's sole and instep (one shell), so on
  the duvet the page had to draw the slides' shape in white; now a sock-labelled copy of the slide sits 6 mm inside it,
  and with the slides hidden (`boy_slides`, the last primitive) the foot is a closed white sock.
- **Preview video:** `preview/boy_old_vs_new.mp4`, 40 s, 30 fps, rendered in `/room`: a turn of his head old then new,
  the desk and the walk old vs new side by side (see the build README).

## Budgets
| | old | new | budget |
|---|---|---|---|
| file | 960 KB | 1.65 MB | ≤ 3 MB |
| triangles | 31k | 56k body + 11.9k sock sole + 3.3k invisible bed proxy + 2 × 1.1k eyes (75.3k) | ≤ 80k |
| draw calls | 1 | 6 body (the last one also carries an invisible ~3k-triangle body proxy for the bed code) + 6 eye parts (two shared meshes) | |
| textures (VRAM) | one 2048² | skin 2048² + 2 × 1024², hair 1024² + 2 × 512², cloth 2048² + 2 × 1024², eye 512², lid 128² | |

Not measured here: FPS on a real mid-range phone (headless Chromium renders in software; the extra draw calls and the
alpha-tested skin are cheap, the triangle count is below the budget).
