# Medium curtain cut as real strands, for G2's body (preview)

About 45,000 individual hairs grown on the scalp of G2's head (`room_build/mh/glb/boy_g2.glb` on `preview/mh-motion`),
the way game grooms do it. The owner changed the style to a medium-length, soft, layered curtain cut on a ~20-year-old:

- the top is 9-12 cm from a part near the centre (a little to his left), lifted at the roots by the part, with volume
  at the crown;
- the two halves of the fringe fall to the brows and outer eye corners and sweep out toward the temples, with a few
  loose strands across the forehead;
- the sides are 5-6 cm over the upper half of the ears and behind them;
- the nape is 8-10 cm to the collar, with soft flicked-out ends;
- loose waves, piece-y clumps of ~30 hairs that twist and split, and near-black colour (#14100e) with faint brown in
  the light.

The short textured cut before it (e4339a6 to 96d389d) was dropped.

## The sheet (`hair_sheet.png`, preview branch only)

This round is a crude first look: front and 3/4 only, each next to a real photo of the cut cropped to the hair above
the eyes (no face). Locked camera, neutral light, G2's head in plain skin with G2's own eyes, and no text on the sheet.
`VIEWS=front,q34` gives this crude sheet; without it, `render.mjs` gives the full sheet (front, 3/4, side, back, and
the room distance with the LOD).

| view | trait compared with the photo |
|---|---|
| front | the part near the centre, the two fringe halves sweeping out to the temples, volume at the top |
| 3/4 | the curtain falling past the brow toward the temple, the length over the ear, the layered top |
| back (full sheet) | the length down the back of the head to the collar, the soft ends |

### Reference photos

All are under the Unsplash License (free to use, no permission needed); none is committed. The renderer reads them
from `ref/` in its source folder. Each is cropped to the hair above the eyes (`REFS` in `preview.html`).

| sheet file | photo page | photographer | image |
|---|---|---|---|
| `ref/front.jpg` | https://unsplash.com/photos/man-in-black-crew-neck-shirt-near-brown-wall-khV4fTy6-D8 | Oliver Ragfelt | images.unsplash.com/photo-1513956589380-bad6acb9b9d4 |
| `ref/q34.jpg` | https://unsplash.com/photos/a-close-up-of-a-person-wearing-a-blue-shirt-3wReHaYiL9k | Stuart Isaac Harrier | images.unsplash.com/photo-1688679446493-d22bad16b8ae |
| `ref/back.jpg` | https://unsplash.com/photos/the-back-of-a-mans-head-in-a-blue-shirt-9mDU8BxZVkA | George Huffman | images.unsplash.com/photo-1731951039647-94f50eea1fd5 |

Download each with `?w=1200&q=85&fm=jpg`.

## How the hair is made

- **Head** (`extract_head_g2.py`): G2's GLB keeps base.obj's vertex order, so the head is cut out by base.obj's
  indices. It is mapped into the default head's frame (least-squares scale 1.083 and offset; the shape differs by up
  to 2.2 cm from the macro targets), where `hair_gen.js`'s hairline, ear and whorl settings live. Hairs are raycast
  onto the real G2 surface, then mapped back.
- **Growth** (`strands.js`):
  - About 1,650 clump guides, about 5 mm apart, are grown along a combing field: away from the part, forward over the
    forehead at the front and then out toward the temples, down over the sides and behind the ears, down the back.
  - While the head is under the hair, a guide sits on it at a height that grows with the distance travelled, so
    longer hair lies over shorter, with lifted roots by the part and volume at the crown. Once it leaves the skull,
    it hangs under gravity.
  - A slow wave (4-9 mm, 3.5-6 cm long) rides along each guide.
  - Each guide carries about 30 hairs rooted round it. They twist round it along their length, and most are pulled
    back into it toward the tips; about 18 % split away as loose pieces.
  - The ends at the sides and nape flick out. Each hair gets a little frizz, and a few loose strands cross the
    forehead.
  - Near the hairline the hairs thin out over about 7 mm.
  - Each hair has 5-14 points.
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
  - Kajiya-Kay along the strand with two lobes: a dim near-white primary toward the root and a dimmer warm secondary
    toward the tip. It is dry and matte.
  - The base is near-black (#14100e), with a per-hair tint and slightly browner tips.
  - A wrap term over the scalp normal, plus self-shadow (darker deep in the hair and toward the roots).
  - Under the hairs is a painted scalp base: a dark layer with strokes along the growth direction, feathered at the
    hairline.

## Numbers

Measured in headless Chromium with software GL (SwiftShader, CPU only), so these are upper bounds; a real GPU is far
faster.

| | |
|---|---|
| hairs | 43,550 (1,653 clumps) |
| strand points | 480,205 (436,655 segments) |
| ribbon vertices / triangles | 960k / 873k (the LOD: 437k triangles) |
| grow time | ~1-2.5 s (offline; the GLB carries the result) |
| strand draw, close-up 480×480, full | ~2.7 s |
| strand draw, 1280×800 at 2.2 m, full | ~1.6 s |
| strand draw, 1280×800 at 2.2 m, LOD | ~0.7 s |
| `hair_mh.glb` | 4.2 MB (quantized and meshopt-compressed) |

## Using it in three.js (r169)

```js
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const gltf = await loader.loadAsync("hair_mh.glb");
const hair = gltf.scene.getObjectByName("hair_mh");
hair.position.set(0, 0, 0);
headBone.add(hair);                                  // G2's "head" bone; bones are world-aligned at rest
const strands = useStrands(THREE, hair, {lod});     // from hair_strands.js
// strands.material.uniforms: keyDir/keyCol, rimDir/rimCol, sky/ground, base — set them from the room's lights.
```

The GLB holds:

- `hair_strands`: line segments, NORMAL = the scalp normal, COLOR_0 = (t along the hair, per-hair random,
  self-shadow, distance to the tip in cm capped at 1).
- `hair_scalp`: the painted base, with `hair_scalp.png` embedded.

Both are in G2's frame relative to the Head bone's rest position (0, 1.590, 0.052).

## Files and licences

| file | what | licence / source |
|---|---|---|
| `hair_mh.glb`, `hair_scalp.png` | the strands and the painted scalp base | made here, CC0 1.0 |
| `extract_head_g2.py`, `extract_head.py`, `hair_gen.js`, `strands.js`, `hair_strands.js`, `hair_tex.js`, `hair_material.js`, `preview.html`, `render.mjs`, `compress.mjs` | the sources | made here, CC0 1.0 |
| G2's body | the head the hair grows on | built from MakeHuman base.obj and targets (CC0 1.0, `LICENSE.ASSETS.md` in github.com/makehumancommunity/makehuman) |

## Known gaps against the photos (crude round)

- The real cut sweeps out from the part in smooth S-curves; ours hangs straighter and looks shaggier.
- The middle of the forehead is open (the part), but the fringe halves don't yet reach the brows evenly.
- A few long strays arc above the top.
- There is no side reference photo yet.
- The draw is about twice the short cut's (873k triangles at full density; the LOD halves it). On software GL it is
  heavy; it has not been measured on a GPU or a phone.

## Rebuild

    git clone --depth 1 https://github.com/makehumancommunity/makehuman                 # base.obj (CC0)
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2.glb > boy_g2.glb
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2_rest.json > boy_g2_rest.json
    python3 extract_head_g2.py makehuman/makehuman/data/3dobjs/base.obj boy_g2.glb boy_g2_rest.json src/head_g2.json
    mkdir -p src/ref    # + the four photos above, named as in the table
    # in a folder with three@0.169.0, playwright-core, @gltf-transform/{core,extensions,functions}@4 and meshoptimizer:
    node room_build/hair_mh/render.mjs src/head_g2.json src node_modules/three out/        # VIEWS=front,q34 for the crude sheet
    node room_build/hair_mh/compress.mjs out/hair_mh_raw.glb out/hair_mh.glb
