# Real-world assets: manifest, audit and gaps

Source of truth for loaders: [`web/assets/manifest.json`](../../web/assets/manifest.json) (generated from an inspection of every file;
checked by `tests/test_assets_manifest.py`). Assets come from branch `assets/cc0` (CC0 Poly Haven, converted by the user); nothing
was added, downloaded, converted or modified by this stream. Total: **58 files, 42,987,487 bytes (41.0 MB)**: 5 HDRIs (1k), 9 PBR
texture sets (27 JPG, 1024 px), 26 Draco GLB models (WebP textures, 1024 px max).

## How the manifest is meant to be used

- Units are metres, +Y up, glTF convention. URLs are root-absolute (`/assets/...`; the server mounts `web/` at `/`).
- Model transform: `scale` (uniform), then `rotationY` (about +Y), then place the model so that `origin.y = surfaceY + yOffset`.
  `size` is the final size after scale and rotation. `rawSize`, `rawMin` keep the file values. `anchor` says what the model rests on
  (`floor`, `desk`, `bed`, `counter`, `wall`, `ceiling`), `front` where its front faces in the file, `origin` where the pivot sits.
- Every model loads with `GLTFLoader` + `DRACOLoader` (WebP textures need a recent three; tested with r186. The r128 copy in the
  `_tools` sandbox is too old to use here and was not tested). Materials are standard PBR (map, normalMap, roughnessMap/metalnessMap packed).
- Textures: `map` is sRGB, `normalMap` is OpenGL (+Y up, no flip), `roughnessMap` is linear grey. `repeatPerMetre` is the number of **texture
  repeats per metre** (set `texture.repeat` = surface size in metres x repeatPerMetre), i.e. 1 / tile size: 0.33 means one tile covers
  about 3 m. It is an estimate taken from the image content; tune it by eye. Do not invert it.
- Optional hints on models: `seatY` (height of the sitting surface above the model's floor contact, measured by vertical ray casts on the
  baked geometry), `backTopY`, `surfaceY` (top of a table/desk, or the bed spring plane), `variants` (per-node `yOffset`, real `size` and
  `centreX` for files that hold several props), `minQuality` (`medium`/`high`: skip or replace on lower presets), `nodes` (file contains several variants,
  clone one by node name), `notes`.
- `areas.<name>` lists the HDRIs, texture sets and models to fetch when entering an area, with the byte size, for lazy loading.

## Verification done

- All 26 GLBs decode with `GLTFLoader` + `DRACOLoader` in headless Chromium (three r186): **no errors, no warnings**, 50-850 ms each
  (software GL), geometry bounding boxes identical to a separate gltf-transform analysis. Each was also rendered (front, side, 3/4) to
  check orientation and scale by eye.
- All GLBs use one scene, no animations, no skins, Y-up, origin at the base (exceptions in the notes column), 1 to 3 materials each.
- File integrity: HDRs are valid Radiance RGBE, textures are 1024x1024 JPEG (roughness is 1-channel).

## Models

Sorted by area. `scale`, `rotation`, `yOffset` are the values stored in the manifest; size in metres after scale/rotation.

| key (file) | area | role | scale | rotY | yOffset | size x y z (m) | tris | file | front |
|---|---|---|---|---|---|---|---|---|---|
| `old_bed_frame` | apartment | bed | 1.0 | 0 | 0.0 | 0.905 x 1.201 x 2.002 | 46,481 | 474 KB | head end at -z (taller rail 1.20 m), foot end +z (0.84 m) |
| `potted_plant_01` | apartment | bush | 1.0 | 0 | 0.0 | 0.587 x 1.336 x 0.634 | 153,761 | 1132 KB | - |
| `drawer_cabinet` | apartment | cabinet | 0.8 | 0 | 0.0 | 0.913 x 1.505 x 0.39 | 13,630 | 187 KB | +z |
| `modern_ceiling_lamp_01` | apartment | ceiling_lamp | 0.7 | 0 | -0.821 | 0.302 x 0.666 x 0.302 | 5,456 | 139 KB | - |
| `WoodenChair_01` | apartment | chair | 0.68 | 0 | 0.001 | 0.468 x 1.546 x 0.448 | 16,878 | 316 KB | +z |
| `wall_clock` | apartment | clock | 1.0 | 0 | 0.0 | 0.32 x 0.32 x 0.047 | 3,551 | 150 KB | dial faces +z |
| `metal_office_desk` | apartment | desk | 0.9 | 0 | 0.0 | 1.8 x 0.709 x 0.852 | 4,856 | 158 KB | sitter at +z (drawer pedestals face +z) |
| `desk_lamp_arm_01` | apartment | lamp | 0.75 | 0 | 0.066 | 0.152 x 0.67 x 0.461 | 19,630 | 425 KB | - |
| `classic_laptop` | apartment | laptop | 0.55 | 0 | 0.001 | 0.359 x 0.299 x 0.267 | 13,128 | 288 KB | keyboard towards +z, screen hinge at -z |
| `throw_pillows_01` | apartment | pillows | 0.9 | 0 | 0.002 | 0.932 x 0.405 x 0.679 | 6,356 | 870 KB | - |
| `Shelf_01` | apartment | shelf | 0.9 | 0 | 0.0 | 0.903 x 1.872 x 0.231 | 182 | 322 KB | +z |
| `Sofa_01` | apartment | sofa | 1.15 | 0 | 0.001 | 1.807 x 0.917 x 0.757 | 4,009 | 187 KB | +z |
| `electric_stove` | apartment | stove | 1.0 | 0 | 0.0 | 0.503 x 0.859 x 0.648 | 12,532 | 233 KB | +z |
| `WoodenTable_01` | apartment | table | 1.0 | 0 | 0.0 | 1.8 x 0.549 x 0.657 | 950 | 226 KB | long axis x |
| `wicker_basket_01` | bakery | basket | 1.0 | 0 | 0.001 | 0.383 x 0.117 x 0.295 | 21,674 | 387 KB | - |
| `croissant` | bakery | bread | 1.0 | 0 | 0.001 | 0.2 x 0.062 x 0.076 | 1,988 | 335 KB | - |
| `CoffeeCart_01` | bakery | cart | 1.0 | 0 | -0.004 | 2.168 x 1.718 x 1.073 | 27,080 | 515 KB | +z (sliding door) |
| `wooden_display_shelves_01` | bakery | display | 1.0 | -90 deg | 0.0 | 1.078 x 1.556 x 0.371 | 2,854 | 156 KB | open face is +x in the file; rotationY=-pi/2 makes it face +z |
| `fire_hydrant` | street | hydrant | 1.0 | 0 | 0.0 | 0.875 x 0.799 x 0.318 | 78,000 | 741 KB | - |
| `planter_box_01` | street | planter | 1.0 | 0 | 0.0 | 0.913 x 0.425 x 0.414 | 6,898 | 324 KB | long axis x |
| `street_lamp_01` | street | street_lamp | 1.0 | 0 | 0.0 | 0.704 x 3.871 x 0.387 | 20,038 | 221 KB | - |
| `metal_trash_can` | street | trash | 0.8 | 0 | 0.0 | 1.422 x 0.725 x 0.445 (two bins, 0.62 wide each) | 13,664 | 807 KB | - |
| `painted_wooden_bench` | park | bench | 0.7 | 0 | 0.0 | 0.815 x 0.622 x 0.348 | 624 | 255 KB | +z (seat faces +z, back at -z) |
| `grass_medium_01` | park | bush | 1.0 | 0 | 0.0 | 5.605 x 0.342 x 0.327 | 19,242 | 559 KB | strip along x |
| `rock_moss_set_01` | park | rock | 0.5 | 0 | 0.0 | 4.003 x 0.884 x 3.474 | 61,417 | 480 KB | - |
| `island_tree_01` | park | tree | 1.0 | 0 | 0.02 | 4.755 x 5.027 x 4.817 | 1,298,266 | 8571 KB | - |

Notes that matter when placing (full list in each model's `notes`):

- **Bed** is a bare metal spring frame (spring plane y=0.49 m); the mattress, duvet and pillows on it are procedural / `throw_pillows_01`.
  Head end (taller rail) is at **-z**.
- **WoodenTable_01** is a low table (0.55 m), not a dining table. **WoodenChair_01** is a gothic high-back chair (a 2.3 m throne
  at scale 1). At the manifest scale 0.68 its seat is **0.449 m** high (`seatY`, measured by ray casts: flat seat) and the back top 1.55 m; the
  desk top is 0.709 m (`surfaceY`), so a sitter's thighs clear the desk by ~0.26 m. (An earlier version of this file said 0.43 m at scale 0.9;
  that was wrong, the real seat at 0.9 was 0.594 m.) A procedural desk chair is the preferred option for `sit_desk`.
- **Shelf_01** has its origin at the **back face** (z from 0 to +0.26): put it flush on the wall. **wall_clock** has its origin at the dial centre.
  **modern_ceiling_lamp_01** hangs from its origin: `origin.y = ceilingY + yOffset` with yOffset = -0.821.
- **fire_hydrant** and **metal_trash_can** contain TWO variants each (nodes named in `nodes`); take one, drop the other. Per-variant `yOffset`
  (both 0: each variant, lid included, stands exactly on y=0), real size and `centreX` are in `variants`. The 0.16 m "below the floor" that
  three's `Box3.setFromObject` reports for the bins is a loose bounding box of a rotated node, not geometry; `size`/`rawSize` of the bin entry
  is that loose box, use `variants[...].size`.
  **rock_moss_set_01** is a scatter of 6 rocks over ~4x3.5 m (after scale), **grass_medium_01** is a 5.6 m strip of tufts: instance and scatter them.
- **painted_wooden_bench** is a small hall bench (0.82 m wide at scale 0.7, seat 0.456 m = `seatY`), not a park bench. Sofa seat cushions are 0.437 m (`seatY`).
- **classic_laptop** is a 1990s grey laptop; its screen is a flat dark texture, so use an emissive overlay for a lit screen.
- Light sources (street lamp, ceiling lamp, desk lamp) have no emissive light: add lights / emissive materials in the world code.

### Heavy models (performance flags)

| model | tris | file | advice |
|---|---|---|---|
| `island_tree_01` | 1,298,266 | 8.6 MB | about 10x the triangle count of everything else together. One or two instances at most, high quality only, lazy-load; procedural tree on low/medium. Not needed for the first paint. |
| `potted_plant_01` | 153,761 | 1.1 MB | one instance, medium and up |
| `fire_hydrant` | 78,000 (two variants, ~39k each) | 0.74 MB | one variant only; cheap to replace by a procedural hydrant on low |
| `rock_moss_set_01` | 61,417 | 0.48 MB | fine as a single scatter |
| `old_bed_frame` | 46,481 | 0.47 MB | fine, single instance |

I did not simplify or convert anything (out of scope); if the user wants lighter files, decimating `island_tree_01`, `potted_plant_01` and `fire_hydrant` would help the most.

## Lazy loading: bytes per area

Shared HDRIs are fetched once for the whole world; texture sets used by two areas are fetched once (so the areas overlap, and the sum of
the rows is more than the 41.0 MB total).

| area | HDRI | textures | models | total to fetch | tris (all its models once) |
|---|---|---|---|---|---|
| shared | 4.89 MB | 0.00 MB | 0.00 MB | **4.89 MB** | 0 |
| apartment | 1.55 MB | 7.78 MB | 5.11 MB | **14.44 MB** | 301,400 |
| bakery | 1.55 MB | 4.75 MB | 1.39 MB | **7.69 MB** | 53,596 |
| street | 1.54 MB | 9.21 MB | 2.09 MB | **12.85 MB** | 118,600 |
| park | 0.00 MB | 3.34 MB | 9.86 MB | **13.21 MB** | 1,379,549 |

Suggested order: `shared` (sky for day/dusk/night, 4.9 MB) + `apartment` (14.4 MB) first; `bakery`, `street`, `park` on demand when the
camera/character goes there. Inside `park` the tree alone is 8.6 MB, so load it after the rest of the park and show a procedural tree until then.
Texture sets per area are in `areas.<name>.textures`; `hdri.interior` is shared by apartment and bakery.

## Character (not delivered yet)

`web/assets/character/` does not exist on `origin/assets/cc0` (latest commit `bc7d7d7`, checked again at the end of this stream).
The manifest therefore has `character.url = null` and all nine clip slots (`idle, walk, sit, sit_desk, lie, lie_phone, eat, look_window, serve`) set to `null`.
When the Quaternius library arrives: merge `origin/assets/cc0`, inspect the rigged GLB and the animation GLBs (clip names, rig compatibility),
set `character.url` and map each slot to the clip name; slots with no suitable clip stay `null` and `character.js` keeps its procedural pose for them.
Generic animation libraries usually cover idle/walk/sit/lie; `sit_desk`, `lie_phone`, `eat`, `look_window`, `serve` may need retargeting or procedural poses (unknown until the files exist). `tests/test_assets_manifest.py` ignores the `character/` folder.

## What the world still lacks (build procedurally, list in STATUS.md)

| missing | why it matters | suggestion |
|---|---|---|
| Building facades, windows, doors, roofs, balconies, shop front | no building model at all; only textures (`brick_4`, `white_stucco`, `brushed_concrete`) | procedural boxes with the brick/stucco sets, window frames with emissive panes at night |
| Apartment shell (walls, floor, ceiling, window, door, skirting, radiator) | only furniture | procedural room with `herringbone_parquet` floor + `white_stucco` walls; window cut-out for the day/night HDRI |
| Mattress, duvet, blanket | bed is a bare frame | procedural boxes with `denim_fabric` |
| Bakery counter, till, oven, bread rack, shop sign, chalkboard | only `wooden_display_shelves_01`, `CoffeeCart_01`, basket, croissant | procedural counter in wood + glass case; the coffee cart can stand in as the serving spot |
| Baker NPC (and any other person) | no human models | character stream: procedural baker built from primitives or reuse the Quaternius rig with a different material/clothes; never a real face |
| Bread loaves, baguettes, rolls, pastries | only one croissant | instance the croissant, add procedural baguette/round loaf (lathe/capsule shapes) |
| Car, bicycle, scooter, any traffic | none | simple procedural car silhouettes (a few boxes) if wanted |
| Street furniture: kerb, road markings, crossing, bollards, signs, bins other than the trash can, shutters | only lamp, hydrant, trash can, planter, bench | procedural, textures `asphalt_02`, `cobblestone_01`, `brushed_concrete` |
| Desk chair for `sit_desk` | only the 2 m gothic `WoodenChair_01` (usable at scale 0.68, but odd) | preferred: a small procedural desk chair (seat ~0.45 m) |
| Park: hedges/bushes, flowers, park benches (long), paths, fountain, water, ground cover | `grass_medium_01` is a tuft strip, bench is a small hall bench, tree is very heavy | procedural hedges/ground with `grass_path_2`, simple procedural tree for low/medium |
| Sky objects: sun/moon discs, stars, clouds, birds | HDRIs are static (day, dusk, night) | blend between the three HDRIs by Rome time; add sun/moon light and a simple moon mesh |
| Kitchen items (kettle, pans, plates, cups, bowls, food for the `eat` action) | only a stove; the coffee cart has mugs | procedural small props |
| Books, paper, pictures, rugs, curtains, windows, radiators, plants other than the one pot | no small decor | procedural, textured with the available sets |
| Phone device model | phone is UI (phone stream) | procedural |
| Dedicated emissive/light geometry | lamps carry no light | add lights in code |

## Licence audit

All 58 asset files are covered by a row in `web/assets/CREDITS.md` and every row is Poly Haven (CC0 1.0, public domain):
5/5 HDRIs, 9/9 texture sets (3 maps each), 26/26 models (two removed models, Fir Tree 01 and Jacaranda Tree, are struck through and have no file).
`tests/test_assets_manifest.py` checks this mechanically (every file, including any under `web/assets/character/`, must be named in CREDITS.md by file name, slug or source URL; struck-through rows are ignored). Re-measure models with `tools/measure_glb.mjs`.
I did **not** edit CREDITS.md. Gaps to report to the asset owner:

1. CREDITS.md is per asset (set), not per file, and has no separate **licence column**: the licence (CC0) is stated once in the header.
   The contract asked for file, source URL, author, licence per file. Acceptable in practice (a texture set = 3 files, a HDRI = 1 file),
   but a literal reading is not met.
2. The GLB files carry no licence metadata (`asset.copyright` and `extras` are empty, generator glTF-Transform v4.5.1), so the credits file is the only record.
3. Cosmetic: "Brown Floor Tilles" (typo, slug is `brown_floor_tiles`), "Brushed Concrete " (trailing space), `WoodenTable_01`/`WoodenChair_01`/`Shelf_01`/`CoffeeCart_01` slugs are CamelCase (the lookup is case-insensitive).
4. Not verifiable offline: the author names and the CC0 status of each page on polyhaven.com (blocked in this sandbox). The audit only checks that every file is listed.
5. Baked-in brand-like text in textures (not a licence issue for CC0, but visible on camera): `CoffeeCart_01` (coffee machine and can labels), `electric_stove` (maker name on the panel),
   `classic_laptop` (label on the lid), `wall_clock` (brand on the dial). They are Poly Haven CC0 assets with fictional/vintage marks; if the project wants no brand text on screen, keep those props
   small/out of close-ups or cover them.
6. No character/animation files yet (origin/assets/cc0 is still at bc7d7d7). When the Quaternius files land under `web/assets/character/`, the owner must add their CREDITS.md rows; `tests/test_assets_manifest.py` fails until every file there is credited.
