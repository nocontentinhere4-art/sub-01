# Medium curtain cut as real strands, for G2's body (preview)

About 60,000 individual hairs grown on the scalp of G2's head (`room_build/mh/glb/boy_g2.glb` on `preview/mh-motion`),
the way game grooms do it. The owner changed the style to a medium-length, soft, layered curtain cut on a ~20-year-old:

- the top is 9-12 cm from a part near the centre (a little to his left), lifted at the roots by the part, with volume
  at the crown;
- the two halves of the fringe fall to the brows and outer eye corners and sweep out toward the temples, with a few
  loose strands across the forehead;
- the sides are 6-8 cm over the upper half of the ears and behind them;
- the nape is 8-10 cm to the collar, with soft flicked-out ends;
- loose waves, piece-y clumps of ~30 hairs that twist and split, and near-black colour (#14100e) with faint brown in
  the light.

The short textured cut before it (e4339a6 to 96d389d) was dropped. The cut was approved as of 2e9b77d and has not
changed since. The later passes only bind the hair to the dressed G2 and keep it out of the skin and the hoodie; see
"On the dressed G2" below.

## The sheet (`hair_sheet.png`, preview branch only)

The sheet has three rows.

- **Top row:** front render, then its real photo; 3/4 render, then its real photo.
- **Middle row:** side render, then its real photo; back render, then its real photo.
- **Bottom row:** the room distance (2.2 m through room.html's 30-degree lens, with the LOD), at 1:1 pixels and as
  the whole frame.

Each photo is of the same kind of cut, cropped to the hair, with no face. The renders use a locked camera, neutral
light (a key light and a back light) and G2's head in plain skin with G2's own eyes, and there is no text on the sheet. `VIEWS=front,q34` renders a
crude two-view sheet instead.

| view | trait compared with the photo |
|---|---|
| front | the part near the centre, the two fringe halves sweeping out to the temples, volume at the top |
| 3/4 | the curtain falling past the brow toward the temple, the length over the ear, the layered top |
| side | the side length over the upper ear and behind it, the nape to the collar, the layered top |
| back | the length down the back of the head to the collar, the soft ends, no seam |

### Reference photos

All are under the Unsplash License (free to use, no permission needed); none is committed. The renderer reads them
from `ref/` in its source folder. Each is cropped to the hair above the eyes (`REFS` in `preview.html`).

| sheet file | photo page | photographer | image |
|---|---|---|---|
| `ref/front.jpg` | https://unsplash.com/photos/man-in-black-crew-neck-shirt-near-brown-wall-khV4fTy6-D8 | Oliver Ragfelt | images.unsplash.com/photo-1513956589380-bad6acb9b9d4 |
| `ref/q34.jpg` | https://unsplash.com/photos/a-close-up-of-a-person-wearing-a-blue-shirt-3wReHaYiL9k | Stuart Isaac Harrier | images.unsplash.com/photo-1688679446493-d22bad16b8ae |
| `ref/side.jpg` | https://unsplash.com/photos/a-man-with-long-black-hair-and-a-hoodie-S-xKshOVEw0 | Sehajpal Singh | images.unsplash.com/photo-1677827366776-ded6db523800 |
| `ref/back.jpg` | https://unsplash.com/photos/the-back-of-a-mans-head-in-a-blue-shirt-9mDU8BxZVkA | George Huffman | images.unsplash.com/photo-1731951039647-94f50eea1fd5 |

Download each with `?w=1200&q=85&fm=jpg`. The side photo is cropped behind the face, to the hair only.

## How the hair is made

- **Head** (`extract_head_g2.py`): G2's GLB keeps base.obj's vertex order, so the head is cut out by base.obj's
  indices. It is mapped into the default head's frame (least-squares scale 1.083 and offset; the shape differs by up
  to 2.2 cm from the macro targets), where `hair_gen.js`'s hairline, ear and whorl settings live. Hairs are raycast
  onto the real G2 surface, then mapped back.
- **Growth** (`strands.js`):
  - About 1,200 clump guides, about 6 mm apart, are grown along a combing field. Over the front of the head the hair
    flows away from the part. By the part, the fringe goes nearly straight down the forehead, leaving a narrow V, and
    curves out and back toward the temples from mid-forehead. It runs down over the sides and behind the ears, and
    down the back with no seam (the part stops before the crown).
  - While the head is under the hair, a guide sits on it at a height that grows with the distance travelled, so
    longer hair stacks over shorter (up to 2.8 cm), with lifted roots across the top, more by the part at the front,
    and a raised crown, so the curtain halves stand out from the head before they fall. Once it leaves the skull,
    it hangs under gravity.
  - A soft, loose wave (2-5 mm, 5-8 cm long) rides along each guide.
  - The fringe guides are cut along a curved front edge (brow height at the middle, cheekbone height at the temple,
    with jitter), then resampled.
  - Each guide carries about 50 hairs rooted round it (dense enough that no scalp shows). On the sides and nape the
    hairs stay wider apart toward the tips and end evenly, giving fuller locks instead of spikes. Clumps vary in
    brightness, so the locks read. They twist gently round it along their length and are pulled
    back into it toward the tips, giving fuller, softer clumps; about 5 % split away as pieces.
  - The ends at the sides and nape flick out. Each hair gets a little frizz, and a few loose strands cross the
    forehead.
  - Near the hairline the hairs thin out over about 7 mm.
  - Each hair has 5-11 points (fewer points per hair keeps the cost flat with more hairs).
  - Hairs are shuffled, so the first half is a uniform half-density LOD.
- **Rendering** (`hair_strands.js`):
  - Each hair point becomes two vertices pushed apart across the view: about 0.08 mm wide, full width and opacity
    until the last ~2 mm, then tapering to the tip.
  - A hair is far thinner than a pixel, so the ribbon is drawn at least 0.7 px wide and its alpha carries the true
    coverage.
  - The ribbons are blended without depth writes, after the head and scalp, so thousands of overlapping hairs build
    up into soft fuzz. Alpha-to-coverage was tried first: every hair of the same alpha gets the same sample pattern,
    so they never add up.
- **Shading:**
  - Kajiya-Kay along the strand with two broad, soft lobes (near-white toward the root, warm toward the tip), varied
    per lock: a dry sheen rather than a gloss. The ends are lighter and browner.
  - The base is near-black (#14100e), with a per-hair tint and slightly browner tips.
  - A wrap term over the scalp normal, plus self-shadow (darker deep in the hair and toward the roots).
  - Under the hairs is a painted scalp base: a dark layer with strokes along the growth direction, feathered at the
    hairline.

## On the dressed G2 (the room's clips)

The hair is bound to `room_build/clothes_mh/assets/g2/boy_g2_dressed.glb` (`preview/clothes-mh`; G2's skeleton and bind) the
same way the room page binds props:

- `hair_mh` is parented to the `Head` bone at position 0. The bones are world-aligned at rest, and the hairs are stored
  relative to the Head joint, so they follow the head in every clip.
- **Skin** (`collide.js`, at build time): after growing, every hair point closer to G2's skin than 2 mm goes out along
  the nearest triangle's normal, and 6 mm round the ears. The ears are partly weighted to the neck, so they move a
  little against the Head bone. The push carries on down the hair and fades over the next few points, so the hair
  bends round the ear instead of kinking. 2e9b77d had 77 hairs passing through the ears at rest; the push moves 2,280
  hairs by a few mm and leaves the cut as it was (same sheet).
- **Hoodie** (`collar_map.mjs` + `hair_strands.js`, at run time): when the head tips back, the nape hair would pass
  through the lowered hood and the collar. The hoodie moves against the head, so this is done each frame in the
  strands' vertex shader. `collar_map.mjs` takes two height maps of the hoodie in the `Spine` bone's frame at rest
  (31 × 29 nodes, 1 cm apart) and stores them in the GLB as `hair_mh`'s extras (`userData.collar`):
  - the backmost z of the hood, collar and upper back over (x, y);
  - the topmost y of its upward-facing parts over (x, z), i.e. the rim round the neck and the shoulders.

  Each hair point in front of the back (within 12 cm) goes 4 mm behind it, and one under the top (within 3 cm) goes
  12 mm over it. The 12 mm leaves room for the rim, which rises a little as the neck turns. Cost: up to 8 texel
  fetches per vertex, only on the hair.

**Check** (`bind_check.html`): it plays `room_read` and `room_drink` (`clips_g2` on `preview/mh-motion` at 8ba7fbe) on
the dressed G2, with the clothes' corrective shapes, and samples every 0.25 s (70 and 72 frames). Each frame it counts:

- hair points inside the skin: the closest point on the body's triangles near the head, behind it by more than 1 mm;
- hair segments crossing the hoodie's skinned triangles.

The collar is applied exactly as the shader does. Results with the collar are in `bind_check.json`.

| | inside the skin | through the hoodie | collar pushes |
|---|---|---|---|
| `room_read`, no collar | 1 hair, 3 frames | 0 | - |
| `room_read`, with the collar | 1 hair, 2 frames | 0 | 18 frames, 10.5-16.75 s, up to 102 points by 9 mm or less |
| `room_drink`, no collar | 0 | up to 3,199 hairs (12.5-17.75 s: the head back to drink) | - |
| `room_drink`, with the collar | 0 | 0 | 12.25-17.75 s, up to 15,056 points (the nape lying on the hood) |

The one hair is the tip of a lock tucked behind the right ear. In room_read at 0 s and 5.25 s it sits up to 6 mm inside
the ear, as the ear (partly on the neck) closes the gap behind it. It is hidden under the side hair.

**Frames** (`on_g2.html`): `on_g2_room_read.png` shows `room_read` at 6 s, dressed, with the hair.
- **Top row:** front and 3/4, close, with all hairs.
- **Bottom row:** the same at 2.2 m through room.html's 30-degree lens, with the half LOD (head and torso at 1:1 pixels).

`hair_lod_room.png` shows the head at 2.2 m at 1:1 pixels with all hairs, then 1/2, 1/4 and 1/8.

## Phones and the LOD

This was not measured on a phone; there is no phone or GPU here, and software GL says nothing about a phone. These are
estimates from the vertex and triangle counts.

The strands are vertex- and triangle-bound. At room distance the head is about 150 px tall, so few fragments are
drawn, but every hair vertex is still shaded and every thin triangle is binned. The hairs are shuffled, so any leading
part of them is a uniform thinning. `lod` can be `true` (1/2) or a fraction, and only the hairs drawn are built. Fewer
hairs are drawn a little wider so the coverage holds (width × (1/f)^0.46).

| lod | hairs | vertices | triangles | GPU memory (ribbons) | strand time, mid-range phone (estimate) | at 2.2 m |
|---|---|---|---|---|---|---|
| all | 60,304 | 1.09 M | 971 k | ~73 MB | ~8-15 ms | reference |
| 1/2 (`true`) | 30,152 | 546 k | 486 k | ~37 MB | ~4-8 ms | same as all |
| 1/4 (`0.25`) | 15,076 | 273 k | 243 k | ~18 MB | ~2-4 ms | nearly the same; highlights on top a little streakier |
| 1/8 (`0.125`) | 7,538 | 137 k | 121 k | ~9 MB | ~1-2 ms | visibly thinner on top |

The estimate assumes about 100-150 M shaded vertices per second for this vertex shader on a mid-range phone GPU, plus
the binning of thin triangles. The memory figure is 56 bytes per ribbon vertex plus 24 bytes of indices per segment.

**Suggested budget:**
- desktop at room distance: 1/2;
- phones: 1/4 (about 243 k triangles and 18 MB);
- low-end phones, or if the room drops under 30 fps: 1/8;
- all hairs only for close-ups.

The GLB download is the same for every level, 6.5 MB.

## Numbers

Measured in headless Chromium with software GL (SwiftShader, CPU only), so these are upper bounds; a real GPU is far
faster.

| | |
|---|---|
| hairs | 60,304 (1,203 clumps); 2,280 nudged out of the skin by a few mm |
| strand points | 545,998 (485,694 segments) |
| ribbon vertices / triangles | 1.09M / 971k (the LOD: 486k triangles) |
| grow time | ~1-2.7 s (offline; the GLB carries the result) |
| strand draw, close-up 480×480, full | ~2.6 s |
| strand draw, 1280×800 at 2.2 m, full | ~1.4 s |
| strand draw, 1280×800 at 2.2 m, LOD | ~0.7 s |
| `hair_mh.glb` | 6.5 MB (quantized and meshopt-compressed; the collar map adds 8 kB) |

## Using it in three.js (r169)

```js
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const gltf = await loader.loadAsync("hair_mh.glb");
const hair = gltf.scene.getObjectByName("hair_mh");
hair.position.set(0, 0, 0);
body.getObjectByName("Head").add(hair);             // the dressed G2's Head bone; bones are world-aligned at rest
const strands = useStrands(THREE, hair, {lod: 0.5,  // from hair_strands.js; 0.25 on phones (see above)
  spine: body.getObjectByName("Spine")});           // turns on the collar collider (hair_mh's userData.collar)
// strands.material.uniforms: keyDir/keyCol, rimDir/rimCol, sky/ground, base — set them from the room's lights.
```

`body` is the dressed G2's scene (`boy_g2_dressed.glb`), the one the clips animate. `useStrands` also accepts
`lod: true` (1/2) or `false` (all hairs). The collar map needs WebGL2 (vertex texture fetch), which three r169 requires
anyway.

The GLB holds:

- `hair_strands`: line segments, NORMAL = the scalp normal, COLOR_0 = (t along the hair, per-hair random,
  self-shadow, distance to the tip in cm capped at 1).
- `hair_scalp`: the painted base, with `hair_scalp.png` embedded.

Both are in G2's frame relative to the Head bone's rest position (0, 1.590, 0.052). The node `hair_mh` carries
`extras.collar`: the hoodie's height maps in the Spine bone's frame (`collar_map.mjs`).

## Files and licences

| file | what | licence / source |
|---|---|---|
| `hair_mh.glb`, `hair_scalp.png` | the strands and the painted scalp base | made here, CC0 1.0 |
| `extract_head_g2.py`, `extract_head.py`, `hair_gen.js`, `strands.js`, `collide.js`, `hair_strands.js`, `hair_tex.js`, `hair_material.js`, `preview.html`, `render.mjs`, `compress.mjs`, `collar_map.mjs`, `bind_check.html`, `on_g2.html`, `run_page.mjs` | the sources | made here, CC0 1.0 |
| `on_g2_room_read.png`, `hair_lod_room.png`, `bind_check.json` | the frames on the dressed G2 and the check's numbers (preview branch only) | made here, CC0 1.0 |
| the dressed G2 and its clips (read, not committed here) | `boy_g2_dressed.glb` (`preview/clothes-mh`), `clips_g2/room_read.glb`, `room_drink.glb` (`preview/mh-motion` 8ba7fbe) | CC0 1.0, as stated in their own READMEs |
| G2's body | the head the hair grows on | built from MakeHuman base.obj and targets (CC0 1.0, `LICENSE.ASSETS.md` in github.com/makehumancommunity/makehuman) |

## Known gaps against the photos

- From the side, the front edge of the top layer still reads fairly level at the temple; the curve back toward the
  ear is weaker than in a real curtain cut.
- The back is still darker and smoother than the photo. Lock variation and the back light help, but less than hoped.
- A small tuft remains at the front of the part in the side view.
- The draw is heavy: 971k triangles at full density. The LOD levels bring it down to 121k, but none has been measured
  on a GPU or a phone.
- One lock tucked behind the right ear has its tip up to 6 mm inside the ear in 2 of 70 sampled frames of room_read
  (see above).
- The collar maps come from the rest pose. The hood moves little against the Spine bone (a few mm in these clips), but
  if the hoodie changes, re-run `collar_map.mjs`. Other clips that tip the head far back or sideways (`room_bed_lie`,
  for example) were not checked.
- The collar only knows the hoodie. Another top would need its own maps.

## Rebuild

    git clone --depth 1 https://github.com/makehumancommunity/makehuman                 # base.obj (CC0)
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2.glb > boy_g2.glb
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2_rest.json > boy_g2_rest.json
    python3 extract_head_g2.py makehuman/makehuman/data/3dobjs/base.obj boy_g2.glb boy_g2_rest.json src/head_g2.json
    mkdir -p src/ref    # + the four photos above, named as in the table
    # in a folder with three@0.169.0, playwright-core, @gltf-transform/{core,extensions,functions}@4 and meshoptimizer:
    node room_build/hair_mh/render.mjs src/head_g2.json src node_modules/three out/        # VIEWS=front,q34 for the crude sheet
    node room_build/hair_mh/compress.mjs out/hair_mh_raw.glb out/hair_mh.glb
    git show origin/preview/clothes-mh:room_build/clothes_mh/assets/g2/boy_g2_dressed.glb > assets/boy_g2_dressed.glb
    node room_build/hair_mh/collar_map.mjs assets/boy_g2_dressed.glb out/hair_mh.glb assets/hair_mh.glb   # the collar map in
    for c in room_read room_drink; do git show 8ba7fbe:room_build/mh/glb/clips_g2/$c.glb > assets/$c.glb; done
    node room_build/hair_mh/run_page.mjs "bind_check.html?dt=0.25" assets node_modules/three out/      # ...&collar=0 without it
    node room_build/hair_mh/run_page.mjs "on_g2.html?clip=room_read&t=6" assets node_modules/three out/
