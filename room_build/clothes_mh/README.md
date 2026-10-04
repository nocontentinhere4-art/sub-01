# His clothes on the MakeHuman base body (preview)

His clothes as **MakeHuman clothes**: each garment is an `.obj` mesh, an `.mhmat` material and an `.mhclo` proxy file
that binds every garment vertex to three vertices of the hm08 base mesh (barycentric weights plus an offset, scaled
by measured body distances, MakeHuman's own rule in `shared/proxy.py`). So the clothes follow any body shape made
from that base, whatever targets G2's rebuilt body uses, and they deform with the default skeleton: a garment
vertex's skin weights are the weighted mix of its three body vertices' weights, as MakeHuman does on export. Each
`.mhclo` also lists the body vertices the garment hides (`delete_verts`), so no skin can poke through at the elbows,
the knees or anywhere else under the cloth.

| garment | folder | what it is |
|---|---|---|
| black cotton hoodie | `assets/hoodie_black/` | hood down (a soft double layer rolled behind the neck and falling down the back), two drawstrings with aglets, kangaroo pocket with sloped openings, ribbed cuffs and hem (gathered), weight folds: diagonal creases at the inner elbows, stacking above the cuffs, folds falling to the hem, the fleece blousing over the band |
| dark track trousers | `assets/track_trousers/` | relaxed fit, one off-white side stripe per leg (one plain stripe: no maker's design), elastic ribbed ankle cuffs with stacking above them, soft knee folds |
| white crew socks | `assets/socks_white/` | the feet and lower shins 2 mm out; over the toes one smooth sock shape (a closing of the skin: the front smoothed, then each vertex just past the outermost skin hit of a 5 mm disk of rays), only a hint of the toe line; a ribbed top |
| black slides | `assets/slides_black/` | a 1.8 cm EVA footbed (flat edge, 2 mm radius) from the foot's footprint and a wide padded strap over the instep |

`assets/summary.json` gives each garment's vertex and face counts and how many body vertices it hides.

Fabric: every material has a baked, tileable **colour map** (sRGB) and **normal map** (OpenGL tangent space),
made by `fabric_bake.py`: Poly Haven's photo-scanned fabric normal, combined with a procedural jersey stitch for the
knits (columns of V stitches, a whole number per tile: 41 on the hoodie's 9 cm tile, about 2.2 mm apart, plus fuzz),
and a colour toned by a photo-scanned melange and darkened in the stitch grooves so the knit still reads where the
normal map is mip-mapped away. The `.obj` UVs are a box projection in fabric units (one UV tile = the material's tile),
one `g` group per material (fleece, rib, cord, aglet; track, stripe; sock, sockrib; eva); each garment folder holds
its groups' `<group>_color.jpg` and `<group>_normal.jpg`, and `assets/textures/` all of them. The sheet renders with
exactly these maps.

**Web check** (`web_check.py`, `docs/design/clothes-mh/web_check.jpg`): the posed figure exported to glTF (the maps,
sheen as `KHR_materials_sheen`) and rendered by three.js r169 with the room page's lights: daylight (sun 0xfff0dc,
sky fill, hemisphere) and the evening desk lamp (0xffb468, distance 2.2, decay 1.8), ACES, the room environment, at
2.3 m and at the room's 5 m. Top: day; bottom: the lamp.

## Sources and licences (every one CC0)
| what | source | licence |
|---|---|---|
| base mesh `hm08` (`3dobjs/base.obj`), the `asian-male-young` macro target, the default skeleton `rigs/default.mhskel` and its weights `default_weights.mhw` | [makehumancommunity/makehuman](https://github.com/makehumancommunity/makehuman), `makehuman/data/` | CC0 1.0 (`LICENSE.ASSETS.md`: "explicitly released as CC0 in september 2020") |
| the starting shapes of the hoodie's body and sleeves and of the trousers' legs | MakeHuman system asset `clothes/male_casualsuit02` (in `makehuman_system_assets_cc0.zip`, files.makehumancommunity.org/asset_packs) | CC0 1.0 (stated in the `.mhclo` header: released as CC0 in September 2020 by Data Collection AB, Joel Palmius, Jonas Hauquier) |
| fabric normal maps and tones: `jersey_melange`, `jogging_melange` (hoodie), `ribbed_corduroy` (cuffs, hem, sock tops), `bi_stretch` (trousers), `knitted_fleece` (socks), `hessian_380` (the slides' footbed grain) | [Poly Haven](https://polyhaven.com) (colormass, Rico Cilliers) | CC0 1.0 |
| everything else (the hood, pocket, cords, cuffs, folds, socks, slides, the bindings) | made by `build_clothes.py` | CC0 1.0 |

No brand, logo or maker's design is used.

## Rebuild
From `room_build/clothes_mh/`, with Blender 4.2:

    git clone --depth 1 https://github.com/makehumancommunity/makehuman   # the base mesh, targets, skeleton (CC0 assets)
    curl -O https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
    unzip makehuman_system_assets_cc0.zip -d mh_sys
    python ../ph.py tex 1k jersey_melange jogging_melange ribbed_corduroy bi_stretch knitted_fleece hessian_380
    blender -b -P build_clothes.py -- --mh makehuman/makehuman/data --sys mh_sys --tex ../tex [--quick]
    python compose_sheet.py        # docs/design/clothes-mh/clothes_sheet.jpg from out/*.png
    python web_check.py            # docs/design/clothes-mh/web_check.jpg (three.js, the room's lights; Playwright + Chromium)

The build verifies every written `.mhclo`: read back and refitted on the body with MakeHuman's rule, it must give the
garment back (it does to < 0.01 mm). The sheet's body is the plain base mesh with the young-male target, a neutral
clay mannequin (no face, hair or skin detail: G2's, G6's and the hair session's work); the desk and the stool are grey
boxes.
