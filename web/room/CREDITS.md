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
and the cables. The duvet's drape comes from a
Blender cloth simulation. The ambient occlusion is baked with Cycles into `room_ao` (second UV set). The office chair
is its own node, `chair` (origin on the floor under the gas lift), so it can be moved: it has its own materials and its
own AO (`chair_ao`, self-occlusion only), and the room's AO is baked without it.

The headphones are their own node, `headphones` (origin where the band rests on the hook), left out of the room's AO,
so that the page can take them off the hook. The things hanging on the door (hook rail, hooks, tote, hoodie) are the node
`hangers`, whose origin is the door's hinge, so that they swing with the page's opening door leaf.

The posters (`posters.png`, packed into the GLB) and the pinboard (`pinboard.png`: a calendar page, notes and doodles)
are original graphics drawn by `room_build/tex_prep.py`. Their Japanese
text is set in **Noto Sans JP** (© Adobe, SIL Open Font License 1.1). Only rendered pixels are used; the font file is not
shipped.

## Poly Haven (https://polyhaven.com), CC0 1.0
Textures (each recoloured or regraded in `tex_prep.py`):

| use | asset | authors |
|---|---|---|
| floor | `wood_floor` | Dimitrios Savva |
| wall plaster | `white_stucco` | Amal Kumar |
| desk, shelf, bed, door wood | `oak_veneer_01` | Jenelle van Heerden |
| bed sheet, pillow | `cotton_jersey` | colormass, Rico Cilliers |
| duvet | `waffle_pique_cotton` | colormass, Rico Cilliers |
| curtains | `rough_linen` | colormass, Rico Cilliers |
| rug | `poly_wool_herringbone` | colormass, Rico Cilliers |
| chair fabric, desk mat (normal map) | `jersey_melange` | colormass, Rico Cilliers |

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

    python ph.py tex 2k wood_floor
    python ph.py tex 1k white_stucco oak_veneer_01 cotton_jersey waffle_pique_cotton rough_linen poly_wool_herringbone jersey_melange
    python ph.py model 1k desk_lamp_arm_01 potted_plant_02 potted_plant_04 wall_clock alarm_clock_01 cardboard_box_01 office_notepads
    # fonts/NotoSansJP.ttf (from google/fonts, ofl/notosansjp) is needed for the poster text
    python tex_prep.py
    blender -b -P build_room.py -- --sweep   # 20 s: only the prop sweep (out/sweep.txt), no bake, no export
    blender -b -P build_room.py          # about 9 minutes: most of it is the two AO bakes
    npm install && node post.mjs out/room_raw.glb out/ao_raw.png ../web/room/room_clean.glb out/ao_chair.png

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
