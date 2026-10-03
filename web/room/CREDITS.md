# Room assets: sources and licences

`room_clean.glb` is SUB-01's bedroom, built in Blender 4.2 from simple modelled parts plus a few scanned props.
The build scripts are in `room_build/` at the repository root. Everything in the file is CC0, or original work made for
this project and released under CC0.

## Modelled for this project (CC0)
The walls, floor, window with aluminium sashes, curtains, desk, monitor, keyboard, mouse, speakers, mug, pen cup, office
chair, storage bed, mattress, pillow, duvet, bookshelf and books, fridge, door, hook rail and tote bag, air conditioner,
rug, doormat and poster frames are all built from code in `room_build/build_room.py`. So are the lived-in things added in
#75: the hoodie on the door hook, the backpack, the floor cushion, the electric fan, the slippers, the laundry pinch
hanger with socks and a towel, the manga stack, the game controller (a generic shape, no maker's design), the
headphones and their wall hook, the cat figure on the window sill, the cork pinboard, the wall socket, the power strip
and the cables. The soft goods (#98) are built by `room_build/props_soft.py`: the socks (heel, toe, ribbed cuff) and
the terry hand towel on the pinch hanger, the mattress with its fitted sheet, the pillow in its case, the duvet (a
Blender cloth simulation, turned back over itself at the head end, then box-quilted), the curtains with their pencil
pleats and hems, the rug with its bound edge, the tufted floor cushion, the hoodie and the canvas tote on the door
hooks, the backpack, and two clothes: jeans in a heap by the bed's foot and a T-shirt thrown on the bed (a second cloth
simulation). The ambient occlusion is baked with Cycles into `room_ao` (second UV set). The office chair
is its own node, `chair` (origin on the floor under the gas lift), so it can be moved: it has its own materials and its
own AO (`chair_ao`, self-occlusion only), and the room's AO is baked without it.

The headphones are their own node, `headphones` (origin where the band rests on the hook), left out of the room's AO,
so that the page can take them off the hook. The things hanging on the door (hook rail, hooks, tote, hoodie) are the node
`hangers`, whose origin is the door's hinge, so that they swing with the page's opening door leaf.

The posters (`posters.png`, packed into the GLB) and the pinboard (`pinboard.png`: a calendar page, notes and doodles)
are original graphics drawn by `room_build/tex_prep.py`. Their Japanese
text is set in **Noto Sans JP** (© Adobe, SIL Open Font License 1.1). Only rendered pixels are used; the font file is not
shipped.

## The hard surfaces at game quality (#98 G5, CC0)
`room_build/props_hard.py` rebuilds the hard surfaces with more detail and `room_build/tex_hard.py` draws their textures
(both original work for this project, CC0): the desk and its steel frame, the monitor, the tenkeyless keyboard with real
keycaps, the mouse, the speakers, the mug, the pen cup, the office chair, the storage bed frame, the bookshelf and its
books, the fridge, the door with its handle and hinges, the window frame and aluminium sashes, the air conditioner, the
fan, the headphones and the controller. Edge wear sits in the vertex colours of every bevel, roughness micro-variation in
small generated maps (plastic, painted metal, brushed steel, plaster, oak) and the decals (dust, scuffs, scratches, a
coffee ring, stickers: a cat, a mountain, a 東京 badge, a star, a record, a smile, waves, an onigiri; no brands) are
alpha-blended quads from `decals.png`. The keycap legends (`keycaps.png`) and the book spines (`spines.png`: generic
titles, no real books) are original drawings; their Latin text is set in **DejaVu Sans** (Bitstream Vera licence, free
to use and redistribute), the Japanese text in Noto Sans JP as above. Only rendered pixels are shipped.

## Poly Haven (https://polyhaven.com), CC0 1.0
Textures (each recoloured or regraded in `tex_prep.py`):

| use | asset | authors |
|---|---|---|
| floor (#98 G5) | `wooden_floor_01` (graded, worn patches and scratches added in `tex_hard.py`) | Charlotte Baglioni, Rico Cilliers |
| floor (until #98) | `wood_floor` | Dimitrios Savva |
| wall plaster | `white_stucco` | Amal Kumar |
| desk, shelf, bed, door wood | `oak_veneer_01` | Jenelle van Heerden |
| bed sheet, mattress cover, pillow; the floor cushion and the T-shirt (recoloured) | `cotton_jersey` | colormass, Rico Cilliers |
| duvet | `waffle_pique_cotton` | colormass, Rico Cilliers |
| curtains; the tote's canvas (recoloured) | `rough_linen` | colormass, Rico Cilliers |
| rug | `poly_wool_herringbone` | colormass, Rico Cilliers |
| chair fabric, desk mat (normal map) | `jersey_melange` | colormass, Rico Cilliers |
| socks (normal map) | `knitted_fleece` | colormass, Rico Cilliers |
| hand towel | `terry_cloth` | colormass, Rico Cilliers |
| hoodie | `jogging_melange` | colormass, Rico Cilliers |
| the hoodie's ribbed hem and cuffs (normal map) | `ribbed_corduroy` | colormass, Rico Cilliers |
| backpack (normal map) | `bi_stretch` | colormass, Rico Cilliers |
| jeans | `denim_fabric_05` | colormass, Rico Cilliers |

Models:

| use | asset | authors |
|---|---|---|
| desk lamp | `desk_lamp_arm_01` | Yann Kervran, Kuutti Siitonen |
| floor plant | `potted_plant_02` (soil replaced by a simple disc) | Rico Cilliers |
| desk succulent | `potted_plant_04` | James Ray Cock |
| wall clock | `wall_clock` | PierreB3D |
| alarm clock (window sill) | `alarm_clock_01` | Yann Kervran, James Ray Cock |
| box on the bookshelf | `cardboard_box_01` | Rahul Chaudhary |
| sticky notes | `office_notepads` (one stack) | Ulan Cabanilla |

Poly Haven assets are CC0: https://polyhaven.com/license

## The prop sweep
Every prop is placed from its real bounding box (an imported file's origin can be far from its mesh), and before
anything is joined the build measures every prop: none may reach into the window wall or the back wall (the desk lamp
keeps 1 cm off both), and each one's lowest vertex must lie within 2 mm of its support (desk, floor, sill, shelf; wall
items within 2 mm of the wall). No prop may enter the places the page hard-codes (his place at the window, the delivery
bag's and the tea bottle's spots on the desk), his walking graph (the page's waypoints, links and standing places, 22 cm
each side) or the door's swing. The report lists every prop and every offender (`room_build/out/sweep.txt`); any
offender stops the build.

## Rebuilding
From `room_build/`, with Blender 4.2 and Node 22:

    python ph.py tex 2k wooden_floor_01
    python ph.py tex 1k white_stucco oak_veneer_01 cotton_jersey waffle_pique_cotton rough_linen poly_wool_herringbone jersey_melange
    python ph.py tex 1k knitted_fleece terry_cloth jogging_melange ribbed_corduroy bi_stretch denim_fabric_05
    python ph.py model 1k desk_lamp_arm_01 potted_plant_02 potted_plant_04 wall_clock alarm_clock_01 cardboard_box_01 office_notepads
    # fonts/NotoSansJP.ttf (from google/fonts, ofl/notosansjp) is needed for the poster text
    python tex_prep.py                       # (runs tex_hard.py too: the hard surfaces' textures and atlases)
    blender -b -P build_room.py -- --sweep   # a few minutes (the two cloth simulations): only the prop sweep (out/sweep.txt), no bake, no export
    blender -b -P build_room.py          # the cloth simulations plus the two AO bakes
    npm install && node post.mjs out/room_raw.glb out/ao_raw.png ../web/room/room_clean.glb out/ao_chair.png
    python shots_soft.py --glb ../web/room/room_clean.glb --tag after   # fixed-camera renders (docs/design/room-soft)
    python shots.py --out ../docs/design/room-hard/after      # fixed-camera screenshots of the hard surfaces (from the repository root: python room_build/shots.py)

## His movement and the things he handles (#63)
No animation clips were added. The clips are the ones already in `web/room/` (`boy_*.glb`, the same rig). Everything new is
procedural code in `web/room.html`, written for this project and released under CC0:
- additive layers on top of the clips (breathing, weight shifts with the feet planted, head and neck gaze, idle variants,
  the lean on the window sill, eating, drinking, the door, carrying the bag);
- small props modelled in code from three.js primitives: the delivery bag, a bento box (its top is drawn on a canvas),
  chopsticks, a bread roll and the bakery's paper bag, a bottle of green tea, headphones, and the door leaf that opens
  (it uses the room's own `door` material from `room_clean.glb`).

The standing pose is the first frame of `boy_door.glb`'s clip. GLB size change: none (0 bytes).

## Food (#63, part 2): Kenney "Food Kit" 2.0, CC0 1.0
`food.glb` packs these models from Kenney's Food Kit (https://kenney.nl/assets/food-kit, created by Kenney, www.kenney.nl;
licence: Creative Commons Zero, as stated in the kit's `License.txt`): `bowl-broth` (ramen), `bowl-soup` (curry),
`bowl`, `plate-rectangle`, `sushi-salmon`, `sushi-egg`, `maki-salmon`, `pizza-box`, `pizza`, `rice-ball` (onigiri),
`croissant`, `bag`, `bag-flat`, `chopstick`. Unmodified apart from scale and, for the konbini's bag, a white material
set in `web/room.html`. Rebuild (from `room_build/`, with the kit unzipped somewhere):

    node build_food.mjs "<kit>/Models/GLB format" ../web/room/food.glb      # 84 KB

## His motion: clips generated with NVIDIA ARDY (#98 G3)
`boy_m_*.glb` (listed in `boy_m_manifest.json`) are motions generated from text prompts with **ARDY**
(https://github.com/nv-tlabs/ardy, NVIDIA; the paper's authors are credited there), checkpoint
`nvidia/ARDY-Core-RP-20FPS-Horizon40`, on one RunPod GPU pod (`room_build/ardy/`: `job.sh`, `gen.py`, `specs.json` and
`specs_v2.json` with the prompts; `README.md` to rebuild), then retargeted onto `boy.glb`'s rig by
`room_build/ardy_to_boy.mjs`. The character is the same original one; the clips move his bones only. Licences:
- ARDY's code: Apache-2.0.
- The ARDY checkpoint: the **NVIDIA Open Model License** (https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/):
  commercially usable; "NVIDIA claims no ownership rights in outputs. You are responsible for outputs and their subsequent
  uses." The generated clips are outputs, so they may ship in this public, commercial web app; the model itself is not
  redistributed here. Attribution, as the licence asks for distributed models (kept here for clarity): "Licensed by NVIDIA
  Corporation under the NVIDIA Open Model License".
- ARDY's text encoder is LLM2Vec (McGill-NLP, MIT) on top of Meta Llama 3 8B Instruct (**Llama 3 Community License**,
  https://llama.meta.com/llama3/license). Only the text prompts went through it, offline, on the pod; nothing of it is
  shipped. The weights were taken from the public `NousResearch/Meta-Llama-3-8B-Instruct` re-upload, whose four
  safetensors shards have the same SHA-256 as `meta-llama/Meta-Llama-3-8B-Instruct`'s (verified on the pod, `job.sh`);
  no Hugging Face token was used. "Built with Meta Llama 3."
- The clips' retargeting, `boy_motion.js` (the procedural layer: breathing, weight shifts, foot and hand IK, eyes, the pop
  killer) and the scripts above are made for this project, CC0.
No Mixamo or other non-redistributable animation is used.

## Map card
The map of his neighbourhood (room card and `/life`) is © OpenStreetMap contributors (ODbL,
https://www.openstreetmap.org/copyright). It is drawn from `web/tokyo_area.json`, one static extract made by
`python room_build/osm_area.py` (one Overpass API query, run by hand); no map tiles are loaded.

## The earlier room
`room.glb` (shown with `?room=old`) is the earlier AI-generated single mesh (Meshy, via Higgsfield).

## The view out of the window (#98 G7)
`web/room/window_view.js` draws the outside on the glass marker (`SURF_window`): a parallax shader that casts each view
ray from the room's camera through the glass onto photographic plates behind it (the neighbourhood by day and at night,
the far skyline, a utility pole, a real sky), so the view has true depth from every camera. The plates in
`web/room/window/` are cut out and prepared by `room_build/window_cards.py` from these sources (all free for any use;
each licence was read from the Commons API's `extmetadata` / Poly Haven's `/info` at fetch time and is recorded with the
source's URL and checksum in `web/room/window/plates.json`):

| plate | source | author | licence |
|---|---|---|---|
| `mid.webp`: the neighbourhood by day (an elevated view over the ward next to Kichijōji) | [Suginami City 2024-05-06.jpg](https://commons.wikimedia.org/wiki/File:Suginami_City_2024-05-06.jpg) | ウィキ太郎 | Public domain |
| `mid_n.webp`: the neighbourhood at night, with its real lit windows (`mid_l.webp` marks them) | [Blue illuminated buildings in Tokyo.jpg](https://commons.wikimedia.org/wiki/File:Blue_illuminated_buildings_in_Tokyo.jpg) | Syced | CC0 |
| `far.webp`: the far skyline at twilight (the water and the expressway cropped away) | [Illuminated buildings at twilight in Minato-ku, Tokyo, view from Rainbow Bridge (2016-12-10 by xegxef @Pixabay 2086645).jpg](https://commons.wikimedia.org/wiki/File:Illuminated_buildings_at_twilight_in_Minato-ku,_Tokyo,_view_from_Rainbow_Bridge_(2016-12-10_by_xegxef_@Pixabay_2086645).jpg) | xegxef | CC0 |
| `sky.webp` row 0: clear day | [Kloofendal 43d Clear (Pure Sky)](https://polyhaven.com/a/kloofendal_43d_clear_puresky) | Greg Zaal (All) | CC0 |
| `sky.webp` row 1: partly cloudy day | [Kloofendal 48d Partly Cloudy (Pure Sky)](https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky) | Greg Zaal (Original), Jarod Guest (Sky edits) | CC0 |
| `sky.webp` row 2: overcast | [Kloofendal Overcast (Pure Sky)](https://polyhaven.com/a/kloofendal_overcast_puresky) | Greg Zaal (All) | CC0 |
| `sky.webp` row 3: sunset | [Belfast Sunset (Pure Sky)](https://polyhaven.com/a/belfast_sunset_puresky) | Greg Zaal (Processing), Dimitrios Savva (Photography), Jarod Guest (Sky edits) | CC0 |
| `sky.webp` row 4: dusk (blue hour) | [Qwantani Dusk 2 (Pure Sky)](https://polyhaven.com/a/qwantani_dusk_2_puresky) | Greg Zaal (Photography), Jarod Guest (Processing) | CC0 |
| `sky.webp` row 5: night | [Kloppenheim 02 (Pure Sky)](https://polyhaven.com/a/kloppenheim_02_puresky) | Greg Zaal (Original), Jarod Guest (Sky edits) | CC0 |

Wikimedia Commons CC0: https://creativecommons.org/publicdomain/zero/1.0/ · the Suginami photograph was released into the
public domain by its author (Commons `{{PD-self}}`). The Rainbow Bridge photograph is a Pixabay picture from 2016, when
Pixabay's licence was CC0; the Commons copy carries that licence. Poly Haven assets are CC0: https://polyhaven.com/license.
Only the skies' upper hemispheres are used (±70° of azimuth, -2..50° of elevation, with the sun or the moon kept out of
the crop; the shader draws its own). The photographs contain no readable signage; the skyline's landmark tower appears as
photographed. The utility pole and its cables (`near.webp`) and the rain's noise texture are drawn from code, original work
for this project, CC0. The sources themselves (~120 MB) are not committed: `python room_build/window_cards.py --fetch`
re-downloads them (Wikimedia rate-limits shared addresses; the script waits and retries).

The weather shown is **not real weather**: the server has no weather feed, so `weatherAt()` is a deterministic daily
pattern over Tokyo time (about a fifth of the hours wet, a third overcast), the same for every viewer and never presented
as a forecast or an observation.
