# Realistic hard props: the bottle and lived-in clutter (#98, preview)

`before_after.jpg`: the whole room (top) and the desk (bottom), before (left) and after (right). Locked cameras
(`python room_build/shots.py --shots overview,desk_close`, the page's loop frozen), 13:00, 1280 px. "Before" is this
branch with `props_clutter.glb` blocked, so it shows main plus G10d's Tripo props (`feature/tripo-props-2`, merged here
for the preview). The page's `?debug` surface markers (magenta dots) are hidden by `shots.py` before each shot.

## What is new (`room_build/props_clutter.py` -> `web/room/props_clutter.glb`, 2.0 MB, 77k triangles, 26 draw calls)
| prop | where | source | size | triangles |
|---|---|---|---|---|
| water bottle (the one he drinks from) | the page's bottle spot (`BOTTLE_AT`) | modelled: powder-coated steel, bare steel foot, knurled cap with a loop, two small dents | 500 ml, 65 x 222 mm | 5.5k |
| notebook, pen and pencil | the desk's back left corner | Poly Haven scans `binder_notebook`, `stationery_supplies`; the cover's stamped round emblem and the maker's name printed on the pen and the pencil are cloned out of their maps by the build | A5 binder 171 x 200 mm | 7.0k |
| wired earbuds | behind the keyboard's left end, off the mat | modelled; the lead laid as a loose cable (its bend eases between random curves, it turns back at the strip's edges, rides over itself where it crosses), 3 mm thick; the buds' wires are soft curves into the split | buds 17 mm | 4.0k |
| phone charger and cable | brick in the power strip; cable along the skirting, up through the desk's grommet, along the right edge | modelled | USB-C brick 30 mm | 2.3k |
| glass of water | the window sill, by the cat | modelled: transmissive glass (IOR 1.5, a volume tinting the thick base and the rounded rim faintly green), 2 mm walls; alpha-blended water with a meniscus | 250 ml tumbler, 68 x 96 mm | 1.6k |
| apple | the fridge's top | Poly Haven scan `food_apple_01` | 98 mm | 6.0k |
| small succulent | the bookshelf's middle level, on the stack of books lying flat | Poly Haven scan `potted_plant_04` at 86 % (the gap is 15.7 cm) | 14 cm pot, 23 cm tall | 8.9k |
| crumpled paper | the floor by the desk's end, near the bin | modelled: a sheet crushed into a ball, the inside of 46 tilted planes (flat facets, crisp ridges) cut by eleven V folds | 50-60 mm balls | 9.6k |
| mug of tea | the sill over the bed's head, between the cat and the alarm clock (the bedside: the bed's head is against the window wall, so the sill and the headboard are his night stand; the glass and the clock were there already) | modelled, glazed stoneware | 77 x 89 mm | 1.6k |
| phone, charging | face down on the headboard's cap, past the window; its cable down the bed's side to a new wall socket by the floor | modelled (no logo; a generic two-lens camera) | 69 x 140 x 8 mm | 0.9k + 1.1k cable + 0.6k socket |
| three paperbacks and a magazine | the floor at the bed's foot, by the backpack, spines to the room; the magazine leans on the bed base | modelled: soft covers round rounded spines, their front boards curling a little at the fore edge, cream page blocks showing at the head, tail and fore edge; plain covers and an abstract cover drawn in code (no text) | bunko 105 x 148 mm, B5 182 x 257 mm | 0.6k |
| closed laptop | the bookshelf's top level (the succulent moved down) | modelled, bead-blasted aluminium, no logo | 13-inch, 298 x 208 x 16 mm | 0.9k |
| keys and a wallet | on the shoeboxes by the door: the keys lying flat in a shallow wooden bowl | Poly Haven scan `wooden_bowl_02` (its height x 0.55: a 4 cm catch-all); keys, ring, fob and wallet modelled | bowl 13 cm, wallet 112 x 92 mm | 4.7k + 3.4k + 0.3k |
| rubber boots | the front right corner, past the sneakers (the strip by the door is the shoeboxes' and the skateboard's) | Poly Haven scan `rubber_boots`, the clean pair; the maker's word on each shaft painted out of its maps | 373 mm tall | 9.6k |
| laundry hamper | in front of the bookshelf, its lid off and leaning on it | Poly Haven scan `wicker_basket_02` at 1.3 times its size (at 1.7 its strips read coarse); its own weave given depth: its AO and a cavity term from its normal map multiplied into the colour map, the normal map at double strength (a weave drawn in code read flat and printed: dropped) | 27 cm across, 26 cm tall | 9.1k |

Each prop is at most 10k triangles (the GLB joins them by material: each prop's count is in its scene extras), textures
are WebP at 512 px, soft contact discs sit under the props. `clutter_sweep.txt` checks every prop against the page's
hard-coded spots (bag, dish, bottle, his crouch at the bin), the keyboard, the mouse pad, the monitor's foot, his walking
graph (cables point by point), the room door's and the fridge door's swings and the sneakers' spot; and now against the
built room itself: each prop's triangles must not cut into `room_clean.glb` or `props_tripo2.glb` (decoded, less what
the page hides or cuts away), and its foot must rest on its support with no edge over air. Not done, and why: no shoe
rack (the shoeboxes already stand by the door and the strip there is full); the "nightstand" is the sill and the
headboard (there is no floor beside the bed's head).

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
projection (scrambled textures); they now keep their own. Then, after the owner's review of the first sheet: the paper
balls were lumps, now crisp crumpled facets; the glass was a faint alpha shape, now transmissive with a visible rim and a
water line (the page draws it without depth writes, so the water shows through, and it casts no shadow); the earbuds'
cable was thin and coiled like a spring, now 3 mm and lying in loose, uneven loops. What still falls short: the paper is
a little too even in tone (no grey creases where light cannot reach); the glass shows no caustic on the sill; the
charger brick sits under the desk, out of this close-up.

## Real reference, the room (`real_reference_room.jpg`)
The same rule for this round: the bottle and seven of the new props, render (left) and a real photo (right), photos on
this preview branch only. The keys, the wallet and the magazine have no pair: Openverse returned no usable CC0 photo of
keys, and every magazine photo was a cover with people or text. Through Openverse, CC0 / Public Domain Mark:

| item | photo | via | licence |
|---|---|---|---|
| water bottle | [Water Bottles](https://www.flickr.com/photos/144661696@N05/34776192110) | flickr | CC0 1.0 |
| mug | [Mug](https://collection.cooperhewitt.org/view/objects/asitem/id/194999) | Cooper Hewitt, Smithsonian | CC0 1.0 |
| phone | [Office Work](https://stocksnap.io/photo/office-work-QK8UF7C718) | StockSnap | CC0 1.0 |
| closed laptop | [Free close laptop image](https://www.rawpixel.com/image/5916881/image-background-public-domain-technology) | rawpixel | CC0 1.0 |
| paperbacks | [stack of paperbacks](https://www.rawpixel.com/image/5944049/free-public-domain-cc0-photo) | rawpixel | CC0 1.0 |
| rubber boots | [Shiny rubber](https://www.flickr.com/photos/146224661@N05/48832055747) | flickr | Public Domain Mark 1.0 |
| lidded woven basket | [oval tea basket lid; closed](https://www.rawpixel.com/image/7478334/photo-image-public-domain-blue-bag) | rawpixel | CC0 1.0 |
| small succulent | [Original public domain image Wikimedia](https://www.rawpixel.com/image/3301215/free-photo-image-vase-jar-aloe) | rawpixel | CC0 1.0 |

What it shows: the mug, the phone, the laptop and the boots read close to the photos.

`weak_spots_before_after.jpg` (before left, after right, the same cameras): the notebook's cover without its stamped
emblem (and the pen and pencil without their printed maker's name), then the three weak spots the room sheet showed: the
paperbacks have rounded spines and a visible page block (they were plain blocks); the key bowl is a shallow 4 cm bowl
with a key over its rim (it read as a ball); the hamper's weave is at real scale (the scaled scan had 13 mm strips).
`review3_before_after.jpg` (the owner's third read, before left, after right): the hamper back on its scanned weave,
at 1.3 times, with depth baked in (the drawn twill read flat); the keys lying flat in the bowl (the long key had stood
up out of it); the notebook's cover without its emblem. What still falls short: the bowl's burl grain is busy for its
size; from a low camera the flat keys hide below its rim.

## The page (`web/room.html`)
One block after G10d's: it adds the GLB and moves its `bottle` node into `PROP.bottle` at y -0.08, so the bottle keeps
its place, its origin and his drinking animation; `?props=old` shows the old props. See-through materials (alpha or
transmission) write no depth and cast no shadow; the glass takes the full environment reflection.

## Tripo
0 credits used. This container has no Tripo API key; Poly Haven scans or modelled parts covered every item, so G10d's pipeline was not needed.

## Checks run
`tests/test_props_clutter.py` (new), `tests/test_room_glb.py`, `tests/test_tripo_props*.py`, the full `pytest tests/`
and G8's visual harness, run locally (pushed with `[skip ci]`).
