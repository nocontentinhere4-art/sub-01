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

## The character, version 2 (`boy2*.glb`, #76; shown with `?boy=new`)
A fictional young Japanese man of about 20, made with **MakeHuman / MPFB 2** (https://static.makehumancommunity.org,
MPFB 2.0.17 for Blender 4.2, an add-on under GPL 3; models exported from it are CC0). He is MakeHuman's generic average
body set to male, about 20, "Asian" macro, slim; no face sliders were moved to look like anyone, and he is not modelled
on any real person. The parts come from the MakeHuman community asset packs
(https://static.makehumancommunity.org/assets/assetpacks.html); all are CC0 except the hoodie and the slides, which are
**CC-BY 4.0 by Elvaerwyn** (attribution below, changes listed in the table):

| part | asset | pack | author | licence |
|---|---|---|---|---|
| body (base mesh, macro targets), game-engine rig with fingers, weights | MakeHuman base mesh, `game_engine` rig | MPFB 2 / makehuman_system_assets | MakeHuman team (Data Collection AB) | CC0 |
| skin | `young_asian_male` (re-tinted) | makehuman_system_assets | MakeHuman team | CC0 |
| eyes | `low-poly` eyes, `brown` material (hue shifted to dark brown) | makehuman_system_assets | MakeHuman team | CC0 |
| eyebrows, eyelashes | `eyebrow001`, `eyelashes01` | makehuman_system_assets | MakeHuman team | CC0 |
| hair | `culturalibre_hair_05` (darkened, decimated; original by swift502, CC0, blendswap.com/blend/24099) | hair01 | culturalibre | CC0 |
| hoodie | `elvs_hooded_sweat_jacket1` "Hooded sweat jacket" (re-dyed navy, fitted to a male chest, decimated; makehumancommunity.org/node/1450) | shirts02 | **Elvaerwyn** | **CC-BY** |
| T-shirt under the hoodie | painted on the skin of the chest (original work) | | this project | CC0 |
| joggers | `toigo_wool_pants` (re-dyed heather grey, loosened and tapered at the ankles) | pants01 | Margaret Toigo | CC0 |
| socks | `joepal_crude_low_socks` (white) | underwear04 | Joel Palmius | CC0 |
| slides | `elvs_male_flip_flop_sandals1` "Male flip flop sandals" (black, decimated; makehumancommunity.org/node/1453) | shoes02 | **Elvaerwyn** | **CC-BY** |
| fabric weave (colour variation, roughness, relief) | `jersey_melange` (hoodie), `jogging_melange` (joggers), `cotton_jersey` (socks) | Poly Haven | colormass, Rico Cilliers | CC0 |
| blink (eyelids and lashes) | `eyeBlinkLeft`, `eyeBlinkRight` face units | faceunits01 | Mika Suominen | CC0 |

Hoodie and slides: © Elvaerwyn, CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/), from the MakeHuman community
asset packs shirts02 and shoes02; modified as listed above.

`room_build/build_boy.py` (headless Blender + MPFB) assembles him, poses him into the old rig's rest pose, deletes the
skin under the clothes, bakes 2048² atlases for the skin, eyes and clothes (colour, normal map, and occlusion/roughness;
the skin's pores and the fabrics' weave are baked in) and a 1024² one for the hair, brows and lashes (colour and
alpha, alpha tested), and exports the bind pose. `room_build/boy_post.mjs` gives him the old skeleton's bone names and frames (so
every clip of the old rig plays on him), plus finger, eye and socket bones, a `blink` morph, and writes `boy2.glb`, a
`boy2_<clip>.glb` for every `boy_<clip>.glb`, and `boy2_hands.glb` (finger poses). The clips themselves are the old
ones (below), retargeted; the finger poses are original work for this project (CC0).

Rebuild, from `room_build/` (Blender 4.2 with the MPFB extension, its user data folder holding the packs above):

    python ph.py tex 1k jersey_melange jogging_melange cotton_jersey
    node boy_ref.mjs                     # the old rig's rest pose and palms -> out/boy_ref.json
    blender -b -P build_boy.py           # -> out/boy2_raw.glb, out/boy2_bind.json, out/boy2_*.png (about 2 minutes)
    node boy_post.mjs                    # -> ../web/room/boy2*.glb
    python boy_shots.py                  # screenshots of web/boy_test.html (old/new, frame strips) -> out/shots/

`web/boy_test.html` plays every clip and finger pose (`?cmp` puts the old one next to him).

## The first character
`boy.glb` and the clips `boy_*.glb` (shown by default) are the earlier AI-generated character (Meshy, via Higgsfield;
generated content under those services' terms, not a Creative Commons licence), and `hand_phone.glb` the
phone-gripping hand (GPT Image + Tripo, via Higgsfield); the clips are Meshy library animations re-rigged on its
skeleton. The second character plays the same clips, retargeted.

## His movement and the things he handles (#63)
No animation clips were added. The clips are the ones already in `web/room/` (`boy_*.glb`, the same rig). Everything new is
procedural code in `web/room.html`, written for this project and released under CC0:
- additive layers on top of the clips (breathing, weight shifts with the feet planted, head and neck gaze, idle variants,
  the lean on the window sill, eating, drinking, the door, carrying the bag);
- small props modelled in code from three.js primitives: the delivery bag, a bento box (its top is drawn on a canvas),
  chopsticks, a bread roll and the bakery's paper bag, a bottle of green tea, headphones, and the door leaf that opens
  (it uses the room's own `door` material from `room_clean.glb`).

The standing pose is the first frame of `boy_door.glb`'s clip. GLB size change: none (0 bytes).

## Map card
The map of his neighbourhood (room card and `/life`) is © OpenStreetMap contributors (ODbL,
https://www.openstreetmap.org/copyright). It is drawn from `web/tokyo_area.json`, one static extract made by
`python room_build/osm_area.py` (one Overpass API query, run by hand); no map tiles are loaded.

## The earlier room
`room.glb` (shown with `?room=old`) is the earlier AI-generated single mesh (Meshy, via Higgsfield).
