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
| black cotton hoodie | `assets/hoodie_black/` | a relaxed fit (1.9 cm off the body, the sleeves 1.5 cm and sagging under the arm); hood down (a soft double layer rolled behind the neck and falling down the back), two drawstrings with aglets, kangaroo pocket with sloped openings, a twin-needle topstitch along its top, a stitch line down each side and rolled hems at the openings; ribbed cuffs and hem (gathered); folds shaped as real ones (narrow valleys, round crests): diagonal creases at the inner elbows, soft folds down the upper arms, sagging folds across the belly, stacking above the cuffs, folds falling to the hem, the fleece blousing over the band |
| dark track trousers | `assets/track_trousers/` | roomy at the thigh (2.4 cm off the body, less on the inner thigh; 4.5 mm under the buttocks, the backs of the thighs and the crotch, where he sits), a smooth front drape over the crotch (a height field spanning the dip between the thighs, so it never copies the body's shape there), a short J-shaped fly of topstitching and the centre seam, two soft drag folds from the crotch down the inner thighs, easing over the knee and tapering down the shin to the elastic ribbed ankle cuffs, with stacking above them; long soft folds down the front of the thigh, drag lines from the crotch, soft knee folds; one off-white side stripe per leg (one plain stripe: no maker's design) |
| white crew socks | `assets/socks_white/` | smooth white cotton, the feet and lower shins 2 mm out; over the toes one soft rounded toe box with no toes of its own (a closing of the skin: the front smoothed, then each vertex just past the outermost skin hit of a 16 mm disk of rays, smoothed again and closed once more so nothing enters the skin); slight compression folds at the ankle (1.5 mm); soft creases across the toe box and just behind the strap, where a worn sock bunches; a ribbed cuff under the trouser hem |
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

## On G2's body, for the room's clips
The clothes are built on G2's final body (`room_build/mh/build_g2.mjs` on `preview/mh-motion`): the same MakeHuman
macro targets with the same weights (male, 20 years, muscle 0.5, weight 0.4, proportions 0.75, ethnicity 1/3 each, the
hand targets), so `build_clothes.py`'s body is G2's vertex for vertex (checked against `boy_g2.glb`: < 0.0001 mm after
G2's uniform scale to 1.75 m and feet at y = 0).

`assets/g2/boy_g2_dressed.glb` is G2's own `boy_g2.glb` with the four garments added to it, skinned to its skin: the
same 163 joints, rest pose, node names and inverse bind matrices (unchanged; the build checks the joint order against
`boy_g2_rest.json`). Each garment vertex takes the four strongest of its weights (the mix of its three body vertices'
`default_weights`, as MakeHuman does), so G2's clips (`clips_g2`) drive the clothes as they drive the body. The body's
triangles under the clothes are dropped (MakeHuman's delete_verts; their base-mesh vertex numbers are in
`assets/g2/hidden_body_vertices.json`); nothing else in G2's file changes. Materials: the baked colour and normal maps,
sheen as `KHR_materials_sheen`.

`g2_clip_check.py` plays G2's clips on the dressed GLB in three.js, bound by node name as the room page does:
`docs/design/clothes-mh/g2_clips.jpg`, three rows: walking and standing (the trousers' front); on the bed's edge (4 s)
and lying (12 s) on the bed; sitting down onto the chair and typing on a chair.

**Corrective shapes** (`g2_correctives.py`, after the build): pose-driven morph targets on the hoodie and the trousers in
`boy_g2_dressed.glb` (no cloth simulation). Each is made in its pose (the garments skinned as three.js does, put right
there, and the fix carried back to the rest pose through the inverse of each vertex's skinning, so morph-then-skin
gives the fixed pose), then a last pass in that pose puts any vertex still inside the body 3 mm outside.

| shape | made in | what it does | driver (from joint world positions) | weight |
|---|---|---|---|---|
| `seated` | `desk_type_ik` 3 s | the hoodie's front below the chest lies on the body and the lap as a soft shell with 2-3 horizontal folds 6 cm apart (round crests 22 mm, narrow valleys 4 mm off the body or the trousers), the hem on the thighs; the trousers out of the body at the hip, the crotch and the knees | hip bend: angle between the thigh (`UpLeg`->`Leg`) and the trunk downwards (`neck`->`Hips`), both legs averaged | smoothstep(40°, 80°) |
| `elbow_L`, `elbow_R` | `desk_type_ik` 3 s | the sleeve round a bent elbow out of the arm, its bunching held within 1.5 cm | elbow bend: angle between `Arm`->`ForeArm` and `ForeArm`->`Hand` | smoothstep(55°, 95°) |
| `lying` | `room_bed_lie` 12 s | the hoodie's back on the mattress (not below 5 mm under its top), the upper back, shoulders and lowered hood pressed onto the body (6 mm, the hood 4 mm, under the neck) | chest up: y of normalise((`LeftArm`-`RightArm`) x (`neck`-`Hips`)) | smoothstep(0.6, 0.92) |

The drivers are also in the file (`extras.correctives`); the room page sets `mesh.morphTargetInfluences` on
`hoodie_black` and `track_trousers` each frame after the animation, as `g2_clip_check.py` does (about 20 lines of
JavaScript there). Rest pose, walking and standing: all weights 0.

**Fit in motion** (`g2_pose_check.py`, `docs/design/clothes-mh/g2_poses.jpg`, numbers in `out/pose_check.json`): the
dressed GLB posed by G2's clips at COORD A's moments (seated typing `desk_type_ik` at 3 s, `room_walk` at 0.3 s,
on the bed's edge and lying, `room_bed_lie` at 4 s and 12 s, and `room_sit_down` at its end), skinned exactly as three.js does, with the chair seat (top 0.505 m, G2's measured contact; for `room_sit_down`
at its chair, seat centre (-0.26, -0.13)) and the mattress (top 0.66 m; x -1.0..0.75, z 0.74..1.99 in the clip's frame) in place; any offending garment vertex is drawn red. It measures cloth inside the body
(an odd number of skin crossings on two of three rays), separately where that skin is shown (hands, neck, face), and
cloth below the seat or mattress top or the floor. To sit on the chair, the trousers lie 4.5 mm off the skin under the
buttocks, the backs and insides of the thighs and the crotch (the source suit's crotch hung up to 5 cm low); the hoodie
lies close under the arms; the cuffs sit 2 mm outside the wrists.

## Next to real clothes (preview only)
The owner's rule: every item next to a real one. `build_clothes.py` shoots each comparison render at its photo's
angle under a similar soft overcast daylight (the photos are outdoors); `compare_real.py` sets crops of them beside
the photos, cropped to the clothes (no faces, no logos): `docs/design/clothes-mh/real_feet.jpg` (the sock seen from
the front at shin height beside white ankle socks; the slides as their wearer sees them, looking down the shins,
beside a black one-strap slide seen the same way; the hoodie and the body are left out of that one render, where the
photo shows only a hem) and `real_clothes.jpg` (the hoodie from behind with the right arm raised beside a black
hoodie the same way; the trousers from a low camera in front beside black track trousers with a side stripe). These
sheets stay on the preview branch, never in `web/`. The script downloads the photos; they are not committed.

No CC0 or public-domain photo of black slides worn with white socks was found (Wikimedia Commons' slide-sandal
category has none under CC0; Pexels, Unsplash and StockSnap search pages refuse scripted access), so the socks and the
slide are compared on separate photos. A photo of grey slides was rejected for a visible brand logo.

| photo | source | licence |
|---|---|---|
| white ankle socks in sandals | [Wikimedia Commons](https://commons.wikimedia.org/w/index.php?curid=41275340) ([file](https://upload.wikimedia.org/wikipedia/commons/e/ee/Sandals_Worn_wth_White_Ankle_Socks.jpg)), Oddman47 | CC0 1.0 |
| a black one-strap slide, from above | [WordPress Photo Directory](https://wordpress.org/photos/photo/30768afec3/) ([file](https://pd.w.org/2025/08/30768afec383f9f51.48963621-2048x1536.jpg)), Alina Kakshapati | CC0 1.0 |
| a black hoodie from behind, an arm raised | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Man_taking_a_selfie_(Unsplash).jpg) ([file](https://upload.wikimedia.org/wikipedia/commons/4/48/Man_taking_a_selfie_%28Unsplash%29.jpg)), from Unsplash | CC0 1.0 |
| black track trousers with a side stripe | [StockSnap](https://stocksnap.io/photo/active-male-LY5QEUV2DY) ([file](https://cdn.stocksnap.io/img-thumbs/960w/LY5QEUV2DY.jpg)) | CC0 1.0 |

## Rebuild
From `room_build/clothes_mh/`, with Blender 4.2:

    mkdir -p g2 && for f in boy_g2.glb boy_g2_rest.json clips_g2/desk_type.glb clips_g2/desk_type_ik.glb clips_g2/room_walk.glb clips_g2/room_sit_down.glb clips_g2/room_bed_lie.glb clips_g2/room_stand_up.glb; do
      git show origin/preview/mh-motion:room_build/mh/glb/$f > g2/$(basename $f); done   # G2's body and three clips (not committed here)

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
    python g2_clip_check.py        # docs/design/clothes-mh/g2_clips.jpg: G2's clips on the dressed body (three.js)
    blender -b -P g2_correctives.py   # the corrective shapes into assets/g2/boy_g2_dressed.glb (after build_clothes.py)
    blender -b -P g2_pose_check.py # docs/design/clothes-mh/g2_poses.jpg + out/pose_check.json: the fit in three clip poses
    python web_check.py            # docs/design/clothes-mh/web_check.jpg (three.js, the room's lights; Playwright + Chromium)

The build verifies every written `.mhclo`: read back and refitted on the body with MakeHuman's rule, it must give the
garment back (it does to < 0.01 mm). The sheet's body is G2's body (above), shown as a neutral
clay mannequin (no face, hair or skin detail: G2's, G6's and the hair session's work); the desk and the stool are grey
boxes.
