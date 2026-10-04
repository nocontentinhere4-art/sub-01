# Realistic hard props: the bottle and lived-in clutter (#98, preview)

`before_after.jpg`: the whole room (top) and the desk (bottom), before (left) and after (right). Locked cameras
(`python room_build/shots.py --shots overview,desk_close`, the page's loop frozen), 13:00, 1280 px. "Before" is this
branch with `props_clutter.glb` blocked, so it shows main plus G10d's Tripo props (`feature/tripo-props-2`, merged here
for the preview). The magenta dots are the page's `?debug` markers.

## What is new (`room_build/props_clutter.py` -> `web/room/props_clutter.glb`, 1.0 MB, 38k triangles, 22 draw calls)
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

## The page (`web/room.html`)
One block after G10d's: it adds the GLB and moves its `bottle` node into `PROP.bottle` at y -0.08, so the bottle keeps
its place, its origin and his drinking animation; `?props=old` shows the old props.

## Tripo
0 credits used. This container has no Tripo API key, and Poly Haven or a lathe-modelled part covered every item.

## Checks run
`tests/test_props_clutter.py` (new), `tests/test_room_glb.py`, `tests/test_tripo_props*.py`, the full `pytest tests/`
and G8's visual harness, run locally (pushed with `[skip ci]`).
