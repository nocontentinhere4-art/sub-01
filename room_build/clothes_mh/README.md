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
| white crew socks | `assets/socks_white/` | smooth white cotton, the feet and lower shins 2 mm out; over the toes one soft rounded toe box with no toes of its own (a closing of the skin: the front smoothed, then each vertex just past the outermost skin hit of a 16 mm disk of rays, smoothed again and closed once more so nothing enters the skin); slight compression folds at the ankle (1.5 mm); a ribbed cuff under the trouser hem |
| black slides | `assets/slides_black/` | generic pool slides in matte black rubber: a contoured footbed 2.3 cm under the heel and 1.5 cm at the toe (flat to the ball, then a toe spring), shaped to the sock's underside so the foot sits 1 mm into it, a heel cup and side rims, a 6 mm rounded top edge and a 3 mm bottom edge, about 1 cm wider than the foot and 1.2 cm longer at the toe; faint moulded nubs 3 mm apart on the footbed; one padded strap 7.5 cm front to back from just behind the toes over the forefoot (9 mm thick on top, rounded front and back edges, 2 mm off the sock), moulded into the footbed's sides |

`assets/summary.json` gives each garment's vertex and face counts and how many body vertices it hides.

Fabric: every material has a baked, tileable **colour map** (sRGB) and **normal map** (OpenGL tangent space),
made by `fabric_bake.py`: Poly Haven's photo-scanned fabric normal, combined with a procedural jersey stitch for the
knits (columns of V stitches, a whole number per tile: 41 on the hoodie's 9 cm tile, about 2.2 mm apart, plus fuzz),
and a colour toned by a photo-scanned melange and darkened in the stitch grooves so the knit still reads where the
normal map is mip-mapped away. The `.obj` UVs are a box projection in fabric units (one UV tile = the material's tile),
one `g` group per material (fleece, rib, cord, aglet; track, stripe; sock, sockrib; rubber, footbed, strap); each garment folder holds
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
| fabric normal maps and tones: `jersey_melange`, `jogging_melange` (hoodie), `ribbed_corduroy` (cuffs, hem, sock tops), `bi_stretch` (trousers), `knitted_fleece` (socks) | [Poly Haven](https://polyhaven.com) (colormass, Rico Cilliers) | CC0 1.0 |
| the slides' rubber grain and tone: `Rubber004` (1K, normal and colour) | [ambientCG](https://ambientcg.com/view?id=Rubber004) | CC0 1.0 |
| everything else (the hood, pocket, cords, cuffs, folds, socks, slides, the bindings) | made by `build_clothes.py` | CC0 1.0 |

No brand, logo or maker's design is used.

## Next to real clothes (preview only)
The owner's rule: every item next to a real one. `compare_real.py` sets crops of the renders beside real photos of
the same kind of clothes, cropped to the clothes (no faces, no logos): `docs/design/clothes-mh/real_feet.jpg` (the
socks in the 3/4 close-up beside white ankle socks in sandals; the slide from above beside a black one-strap slide)
and `real_clothes.jpg` (the hoodie seated beside a seated hoodie; the trousers beside black track trousers with a
side stripe). These sheets stay on the preview branch, never in `web/`. The photos are downloaded by the script and
not committed.

| photo | source | licence |
|---|---|---|
| white ankle socks in sandals | [Wikimedia Commons](https://commons.wikimedia.org/w/index.php?curid=41275340) ([file](https://upload.wikimedia.org/wikipedia/commons/e/ee/Sandals_Worn_wth_White_Ankle_Socks.jpg)), Oddman47 | CC0 1.0 |
| a black one-strap slide, from above | [WordPress Photo Directory](https://wordpress.org/photos/photo/30768afec3/) ([file](https://pd.w.org/2025/08/30768afec383f9f51.48963621-2048x1536.jpg)), Alina Kakshapati | CC0 1.0 |
| a hoodie, seated | [WordPress Photo Directory](https://wordpress.org/photos/photo/83465bb8b2/) ([file](https://pd.w.org/2024/02/83465bb8b29634fb2.56218161-1536x2048.jpeg)), Midhun P | CC0 1.0 |
| black track trousers with a side stripe | [StockSnap](https://stocksnap.io/photo/active-male-LY5QEUV2DY) ([file](https://cdn.stocksnap.io/img-thumbs/960w/LY5QEUV2DY.jpg)) | CC0 1.0 |

## Rebuild
From `room_build/clothes_mh/`, with Blender 4.2:

    git clone --depth 1 https://github.com/makehumancommunity/makehuman   # the base mesh, targets, skeleton (CC0 assets)
    curl -O https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
    unzip makehuman_system_assets_cc0.zip -d mh_sys
    python ../ph.py tex 1k jersey_melange jogging_melange ribbed_corduroy bi_stretch knitted_fleece
    curl -L -o rubber.zip "https://ambientcg.com/get?file=Rubber004_1K-JPG.zip" && unzip rubber.zip -d rubber004 \
      && mkdir -p ../tex/rubber004 && cp rubber004/Rubber004_1K-JPG_NormalGL.jpg ../tex/rubber004/nor_gl.jpg \
      && cp rubber004/Rubber004_1K-JPG_Color.jpg ../tex/rubber004/Diffuse.jpg
    blender -b -P build_clothes.py -- --mh makehuman/makehuman/data --sys mh_sys --tex ../tex [--quick] [--feet]
    python compose_sheet.py        # docs/design/clothes-mh/clothes_sheet.jpg from out/*.png
    python compose_feet.py         # docs/design/clothes-mh/feet_sheet.jpg: 3/4 close-up, side, from above, seated at 5 m
    python compare_real.py         # docs/design/clothes-mh/real_feet.jpg, real_clothes.jpg: next to real photos (CC0)
    python web_check.py            # docs/design/clothes-mh/web_check.jpg (three.js, the room's lights; Playwright + Chromium)

The build verifies every written `.mhclo`: read back and refitted on the body with MakeHuman's rule, it must give the
garment back (it does to < 0.01 mm). The sheet's body is the plain base mesh with the young-male target, a neutral
clay mannequin (no face, hair or skin detail: G2's, G6's and the hair session's work); the desk and the stool are grey
boxes.
