# Short black hair as real strands, for G2's body (preview)

About 50,000 individual hairs grown on the scalp of G2's head (`room_build/mh/glb/boy_g2.glb` on `preview/mh-motion`),
the way game grooms do short hair. The cut is a short textured fringe:

- about 5 cm on top, standing a little and lying forward;
- the fringe falls forward in clumped pieces to about 1 cm above the brows;
- the sides and nape taper to 0.6-1.9 cm;
- nothing over the ears.

No hair cards: earlier passes used cards (e4339a6 to 9b64f5f) and a re-cut MakeHuman proxy (01fa2b8); the
owner rejected both.

## The comparison sheet (`hair_sheet.png`, preview branch only)

The sheet has three rows.

- **Top row:** front render, then its real photo; 3/4 render, then its real photo.
- **Middle row:** side render, then its real photo; back render, then its real photo.
- **Bottom row:** the head 2.2 m away through room.html's 30-degree lens with the half-density LOD, at 1:1 pixels
  and as the whole frame.

Each photo is cropped to the hair above the brows, with no identifiable face. The renders use a locked camera,
neutral light and G2's head in plain skin, and there is no text on the sheet.

| view | trait compared with the photo |
|---|---|
| front | the hairline and the density of black hair over the forehead (ours: a fringe in pieces; theirs: a crop) |
| 3/4 | the short side taper under the longer top, soft fuzzy edges, a matte black mass |
| side | the side taper tight to the head, the ear clear, the top above the weight line |
| back | the strands running down the back of the head into a short tapered nape |

### Reference photos

All are under the Unsplash License (free to use, no permission needed); none is committed. The renderer reads them
from `ref/` in its source folder.

| sheet file | photo page | photographer | image |
|---|---|---|---|
| `ref/front.jpg` | https://unsplash.com/photos/a-man-in-a-white-shirt-looking-at-the-camera-ntLkvt6OZvQ | Anky Lau | images.unsplash.com/photo-1681097561932-36d0df02b379 |
| `ref/q34.jpg` | https://unsplash.com/photos/a-man-looking-at-something-Z9LaTWt2Xac | nguyen quan | images.unsplash.com/photo-1655495684052-e310039397fc |
| `ref/side.jpg` | https://unsplash.com/photos/man-in-black-coat-standing-near-trees-C_JB2G5mSYQ | Jeff Tumale | images.unsplash.com/photo-1577965283636-1fab49aea713 |
| `ref/back.jpg` | https://unsplash.com/photos/back-view-of-a-young-mans-shoulders-and-head-ENMjfGTcLHM | DIEGO SÁNCHEZ | images.unsplash.com/photo-1762106383160-24b6ef8f762d |

Download each with `?w=1200&q=85&fm=jpg`. The crop boxes are `REFS` in `preview.html`.

## How the hair is made

- **Head** (`extract_head_g2.py`): G2's GLB keeps base.obj's vertex order, so the head is cut out by base.obj's
  indices. It is mapped into the default head's frame (least-squares scale 1.083 and offset; the shape differs by up
  to 2.2 cm from the macro targets), where `hair_gen.js`'s hairline, ear and whorl settings live. Hairs are raycast
  onto the real G2 surface, then mapped back.
- **Growth** (`strands.js`):
  - About 2,150 clump guides, about 4 mm apart, follow the growth direction out from the crown whorl: forward over
    the top into the fringe, down the taper.
  - Each guide is re-projected onto the scalp at a height that rises and then lies over (6-16 mm on top).
  - Each guide carries about 25 hairs rooted in a disc round it. They leave it at the root and are pulled back
    toward it along their length, giving soft clumps that stay mostly separate; the fringe's clumps are firmer.
  - Each hair has its own length (choppy ends), a slight curl and frizz, and 4-7 points.
  - About 2 % of the hairs on top are flyaways.
  - Hairs are shuffled, so the first half is a uniform half-density LOD.
- **Rendering** (`hair_strands.js`):
  - Each hair point becomes two vertices pushed apart across the view: about 0.08 mm wide, tapering to nothing at
    the tip.
  - A hair is far thinner than a pixel, so the ribbon is drawn at least 0.7 px wide and its alpha carries the true
    coverage.
  - The ribbons are blended without depth writes, after the head and scalp, so thousands of overlapping hairs build
    up into soft fuzz. Alpha-to-coverage was tried first: every hair of the same alpha gets the same sample pattern,
    so they never add up.
- **Shading:**
  - Kajiya-Kay along the strand with two lobes: a dim near-white primary toward the root and a dimmer warm secondary
    toward the tip. It is dry and matte.
  - The base is a natural black-brown (#1b1512), with a per-hair tint and slightly browner tips.
  - A wrap term over the scalp normal, plus self-shadow (darker deep in the hair and toward the roots).
  - Under the hairs is a painted scalp base: a dark layer with strokes along the growth direction, feathered at the
    hairline.

## Numbers

Measured in headless Chromium with software GL (SwiftShader, CPU only), so these are upper bounds; a real GPU is far
faster.

| | |
|---|---|
| hairs | 49,521 (2,153 clumps) |
| strand points | 277,388 (227,867 segments) |
| ribbon vertices / triangles | 555k / 456k (the LOD: 228k triangles) |
| grow time | ~0.9 s (offline; the GLB carries the result) |
| ribbons built from the GLB at load | 264 ms |
| strand draw, close-up 480×480, full | ~1.1 s |
| strand draw, 1280×800 at 2.2 m, full | ~0.65 s |
| strand draw, 1280×800 at 2.2 m, LOD | ~0.27-0.35 s |
| `hair_mh.glb` | 3.8 MB (quantized and meshopt-compressed; 13.5 MB raw) |

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
  self-shadow).
- `hair_scalp`: the painted base, with `hair_scalp.png` embedded.

Both are in G2's frame relative to the Head bone's rest position (0, 1.590, 0.052).

## Files and licences

| file | what | licence / source |
|---|---|---|
| `hair_mh.glb`, `hair_scalp.png` | the strands and the painted scalp base | made here, CC0 1.0 |
| `extract_head_g2.py`, `extract_head.py`, `hair_gen.js`, `strands.js`, `hair_strands.js`, `hair_tex.js`, `hair_material.js`, `preview.html`, `render.mjs`, `compress.mjs` | the sources | made here, CC0 1.0 |
| G2's body | the head the hair grows on | built from MakeHuman base.obj and targets (CC0 1.0, `LICENSE.ASSETS.md` in github.com/makehumancommunity/makehuman) |

## Known gaps against the photos

- The fringe's tips thin out into a pale, see-through edge over the skin; the real cut is denser and darker there.
- The back is brushed straight down; the photo shows a visible whorl and more strand separation.
- The strand draw is heavy on software GL. On the room's GPU it should be fine, but it is not measured there yet.
  The LOD halves it.

## Rebuild

    git clone --depth 1 https://github.com/makehumancommunity/makehuman                 # base.obj (CC0)
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2.glb > boy_g2.glb
    git show origin/preview/mh-motion:room_build/mh/glb/boy_g2_rest.json > boy_g2_rest.json
    python3 extract_head_g2.py makehuman/makehuman/data/3dobjs/base.obj boy_g2.glb boy_g2_rest.json src/head_g2.json
    mkdir -p src/ref    # + the four photos above, named as in the table
    # in a folder with three@0.169.0, playwright-core, @gltf-transform/{core,extensions,functions}@4 and meshoptimizer:
    node room_build/hair_mh/render.mjs src/head_g2.json src node_modules/three out/
    node room_build/hair_mh/compress.mjs out/hair_mh_raw.glb out/hair_mh.glb
