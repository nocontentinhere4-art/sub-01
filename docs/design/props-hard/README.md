# Realistic hard props: the bottle and lived-in clutter (#98, preview)

`before_after.jpg`: the whole room (top) and the desk (bottom), before (left) and after (right). Locked cameras
(`python room_build/shots.py --shots overview,desk_close`, the page's loop frozen), 13:00, 1280 px. "Before" is this
branch with `props_clutter.glb` blocked, so it shows main plus G10d's Tripo props (`feature/tripo-props-2`, merged here
for the preview). The magenta dots are the page's `?debug` markers.

## What is new (`room_build/props_clutter.py` -> `web/room/props_clutter.glb`, 0.9 MB, 38k triangles, 22 draw calls)
| prop | where | source | size | triangles |
|---|---|---|---|---|
| water bottle (the one he drinks from) | the page's bottle spot (`BOTTLE_AT`) | modelled: powder-coated steel, bare steel foot, knurled cap with a loop, two small dents | 500 ml, 65 x 222 mm | 5.5k |
| notebook, pen and pencil | the desk's back left corner | Poly Haven scans `binder_notebook`, `stationery_supplies` | A5 binder 171 x 200 mm | 7.0k |
| wired earbuds | behind the keyboard's left end, off the mat | modelled | buds 17 mm | 6.8k |
| phone charger and cable | brick in the power strip; cable along the skirting, up through the desk's grommet, along the right edge | modelled | USB-C brick 30 mm | 2.3k |
| glass of water | the window sill, by the cat | modelled (alpha-blended glass and water) | 250 ml tumbler, 68 x 95 mm | 0.7k |
| apple | the fridge's top | Poly Haven scan `food_apple_01` | 98 mm | 6.0k |
| small succulent | the bookshelf's top level | Poly Haven scan `potted_plant_04` | 27 cm | 8.9k |
| crumpled paper | the floor by the desk's end, near the bin | modelled | 50-60 mm balls | 0.6k |

Each prop is at most 10k triangles, textures are WebP at 512 px, soft contact discs sit under the bottle, the glass,
the apple and the plant. Nothing blocks the keyboard, the mouse, the monitor or his paths: `clutter_sweep.txt` checks
every prop against the page's hard-coded spots (bag, dish, bottle, his crouch at the bin), the keyboard, the mouse pad,
the monitor's foot and his walking graph (cables point by point).

## Real reference (`real_reference.jpg`, the owner's rule: every item beside a real photo)
Each pair: the render (left, a locked close-up camera, 13:00) and a real photo of the same kind of object (right). The
photos stay on this preview branch only (they are not in `web/`). Found through Openverse with the licence filter CC0 /
Public Domain Mark (Wikimedia Commons rate-limited this container); no brands visible, no faces.

| item | photo | via | licence |
|---|---|---|---|
| water bottle | [Water Bottles](https://www.flickr.com/photos/144661696@N05/34776192110) | flickr | CC0 1.0 |
| glass of water | [glass of water](https://www.flickr.com/photos/92423150@N03/54791320525) | flickr | Public Domain Mark 1.0 |
| notebook and pen | [Free notebook pen next laptop](https://www.rawpixel.com/image/5905412/photo-image-background-public-domain-wooden) | rawpixel | CC0 1.0 |
| wired earbuds | [Free coffee cup, keyboard, earphones](https://www.rawpixel.com/image/5911359/image-background-public-domain-wooden) | rawpixel | CC0 1.0 |
| USB-C charger and cable | [Free phone charger image](https://www.rawpixel.com/image/5923136/photo-image-phone-public-domain-white) | rawpixel | CC0 1.0 |
| apple | [Jon-A-Red Apple](https://www.flickr.com/photos/93936679@N05/23884044207) | flickr | CC0 1.0 |
| small succulent in a pot | [Original public domain image Wikimedia](https://www.rawpixel.com/image/3301215/free-photo-image-vase-jar-aloe) | rawpixel | CC0 1.0 |
| crumpled paper | [Free crumpled paper ball photo](https://www.rawpixel.com/image/5913876/image-paper-public-domain-note) | rawpixel | CC0 1.0 |

What the comparison caught and fixed: the notebook, apple and plant scans had their UVs overwritten by the box
projection (scrambled textures); they now keep their own. What still falls short of the photos: the paper balls read
as lumps rather than crisp crumpled sheets; the glass on the sill is faint against the bright window (alpha-blended,
no refraction); the earbuds' cable is thinner than it reads in a photo; the charger brick sits under the desk, out of
this close-up.

## The page (`web/room.html`)
One block after G10d's: it adds the GLB and moves its `bottle` node into `PROP.bottle` at y -0.08, so the bottle keeps
its place, its origin and his drinking animation; `?props=old` shows the old props.

## Tripo
0 credits used. This container has no Tripo API key, and Poly Haven or a lathe-modelled part covered every item.

## Checks run
`tests/test_props_clutter.py` (new), `tests/test_room_glb.py`, `tests/test_tripo_props*.py`, the full `pytest tests/`
and G8's visual harness, run locally (pushed with `[skip ci]`).
