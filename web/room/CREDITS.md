# Room assets: sources and licences

`room_clean.glb` is SUB-01's bedroom, built in Blender 4.2 from simple modelled parts plus a few scanned props.
The build scripts are in `room_build/` at the repository root. Everything in the file is CC0, or original work made for
this project and released under CC0.

## Modelled for this project (CC0)
The walls, floor, window with aluminium sashes, curtains, desk, monitor, keyboard, mouse, speakers, mug, pen cup, office
chair, storage bed, mattress, pillow, duvet, bookshelf and books, fridge, door, hook rail and tote bag, air conditioner,
rug, doormat and poster frames are all built from code in `room_build/build_room.py`. The duvet's drape comes from a
Blender cloth simulation. The ambient occlusion is baked with Cycles into `room_ao` (second UV set). The office chair
is its own node, `chair` (origin on the floor under the gas lift), so it can be moved: it has its own materials and its
own AO (`chair_ao`, self-occlusion only), and the room's AO is baked without it.

The posters (`posters.png`, packed into the GLB) are original graphics drawn by `room_build/tex_prep.py`. Their Japanese
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

## Rebuilding
From `room_build/`, with Blender 4.2 and Node 22:

    python ph.py tex 2k wood_floor
    python ph.py tex 1k white_stucco oak_veneer_01 cotton_jersey waffle_pique_cotton rough_linen poly_wool_herringbone jersey_melange
    python ph.py model 1k desk_lamp_arm_01 potted_plant_02 potted_plant_04 wall_clock alarm_clock_01 cardboard_box_01 office_notepads
    # fonts/NotoSansJP.ttf (from google/fonts, ofl/notosansjp) is needed for the poster text
    python tex_prep.py
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

## Map card
The map of his neighbourhood (room card and `/life`) is © OpenStreetMap contributors (ODbL,
https://www.openstreetmap.org/copyright). It is drawn from `web/tokyo_area.json`, one static extract made by
`python room_build/osm_area.py` (one Overpass API query, run by hand); no map tiles are loaded.

## The earlier room
`room.glb` (shown with `?room=old`) is the earlier AI-generated single mesh (Meshy, via Higgsfield).
