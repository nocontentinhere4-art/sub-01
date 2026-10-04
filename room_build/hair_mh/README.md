# Short black hair for the MakeHuman default head (preview)

MakeHuman's own CC0 hair proxy **short02** (built from photo-based strand textures for this base head), re-cut to a
short textured-fringe cut and re-coloured black-brown, with see-through strand cards laid over it for the fringe
pieces, the top's texture and the taper. Fitted to the MakeHuman default base mesh (hm08).

## The comparison sheet (`hair_sheet.png`, preview branch only)

The sheet has three rows.

- **Top row:** front render, then its real photo; 3/4 render, then its real photo.
- **Middle row:** side render, then its real photo; back render, then its real photo.
- **Bottom row:** the head 2.2 m away through room.html's 30-degree lens, at 1:1 pixels and as the whole frame.

Each photo is cropped to the hair above the brows, with no identifiable face. The renders use a locked camera,
neutral light and plain stand-in skin, and there is no text on the sheet.

What each pairing compares:

| view | trait compared with the photo |
|---|---|
| front | hair colour and density at the hairline; our fringe is a textured fringe in pieces stopping above the brows, theirs a crop |
| 3/4 | the short tapered side under a longer top, a black mass with soft grey sheen |
| side | the side taper tight to the head, the ear clear, the longer top above the weight line |
| back | the crown whorl and the short tapered nape fading into the skin |

### Reference photos

All are under the Unsplash License (free to use, no permission needed); none is committed. The renderer reads them
from `ref/` in its source folder.

| sheet file | photo page | photographer | image |
|---|---|---|---|
| `ref/front.jpg` | https://unsplash.com/photos/a-man-in-a-white-shirt-looking-at-the-camera-ntLkvt6OZvQ | Anky Lau | images.unsplash.com/photo-1681097561932-36d0df02b379 |
| `ref/q34.jpg` | https://unsplash.com/photos/a-man-looking-at-something-Z9LaTWt2Xac | nguyen quan | images.unsplash.com/photo-1655495684052-e310039397fc |
| `ref/side.jpg` | https://unsplash.com/photos/man-in-black-coat-standing-near-trees-C_JB2G5mSYQ | Jeff Tumale | images.unsplash.com/photo-1577965283636-1fab49aea713 |
| `ref/back.jpg` | https://unsplash.com/photos/back-view-of-a-young-mans-shoulders-and-head-ENMjfGTcLHM | DIEGO SÁNCHEZ | images.unsplash.com/photo-1762106383160-24b6ef8f762d |

Download each with `?w=1200&q=85&fm=jpg`. The crop boxes are `REFS` in `preview.html`.

## What was done to the proxy

- **Fit** (`fit_proxy.py`): the `.mhclo` binding places each proxy vertex on the default base mesh.
- **Re-cut** (`proxy_cut.js`): the proxy is a helmet-like shell, long over the ears.
  - Every vertex is pulled in toward the scalp: about 3 mm on the tapered sides and back, at most about 1 cm on top.
  - Everything below the tapered hairline is walked up the scalp onto it, with vertex alpha feathering the edge, so
    the forehead and ears are free and the nape fades into the skin.
- **Re-colour:**
  - The photo texture is taken to natural black-brown (#1b1512 base); lit strands go grey rather than brown.
  - The green-screen spill is ignored.
  - The `www.makehuman.org` mark in the texture's unused corner is erased, because we ship no logos.
- **Over it** (`hair_gen.js` cards, `hair_tex.js` strand atlas):
  - see-through cards for the fringe's separate pieces, the top's choppy texture and a few flyaways;
  - sparse single hairs on the taper;
  - all lifted to lie on the shell.

  Under it is the painted scalp base, a dark layer with strokes along the growth direction.
- **Shading** (`hair_material.js`, `setupHair()`):
  - The cards use alpha-to-coverage, drawn last.
  - The shell is blended.
  - Both get two Kajiya-Kay lobes along the growth direction: a white primary toward the root and a dim, warm
    secondary toward the tip.
  - The preview resets the canvas alpha after each render, since alpha-to-coverage leaves partial alpha behind
    that would otherwise show the sheet's grey as outlines round each strand. room.html's canvas is opaque.

## Files and licences

| file | what | licence / source |
|---|---|---|
| `hair_mh.glb` | `hair_scalp`, `hair_shell`, `hair_cards`; metres, base-mesh frame (crown y = 0.849, MakeHuman feet at y = -0.845); call `setupHair(THREE, gltf.scene)` after loading | derived from CC0 sources below, released CC0 |
| `hair_shell.png`, `hair_shell_data.png` | the re-coloured short02 texture (mark removed) and its depth/ID map | derived from MakeHuman system asset `hair/short02` (header: "explicitly released as CC0 in september 2020", Data Collection AB, Joel Palmius, Jonas Hauquier), from `makehuman_system_assets_cc0.zip`, files.makehumancommunity.org/asset_packs |
| `hair_scalp.png` | the painted scalp base | made here, CC0 |
| base mesh `hm08` | the head the hair is fitted to | github.com/makehumancommunity/makehuman, `LICENSE.ASSETS.md`: CC0 1.0 |

Size: shell 3.3k triangles, cards 6.5k, scalp 0.65k. The GLB is 8.8 MB, too heavy for the web as it stands: it
embeds five 2048 px PNGs. Before it goes into the room, the textures should go to WebP/KTX2 at 1024.

## Known gaps against the photos

- The back reads too black and flat next to the studio-lit photo; the strand texture barely shows under our neutral key.
- The fringe pieces are long and spiky, where the real cut's texture is denser and finer.
- A few flyaways stick out of the top's silhouette.

## Rebuild

    git clone --depth 1 https://github.com/makehumancommunity/makehuman      # base.obj (CC0)
    curl -O https://files.makehumancommunity.org/asset_packs/makehuman_system_assets/makehuman_system_assets_cc0.zip
    unzip makehuman_system_assets_cc0.zip 'hair/short02/*' -d sys
    python3 extract_head.py makehuman/makehuman/data/3dobjs/base.obj src/head.json
    python3 fit_proxy.py makehuman/makehuman/data/3dobjs/base.obj sys/hair/short02/short02.mhclo src/proxy.json
    cp sys/hair/short02/short02_diffuse.png src/; mkdir -p src/ref   # + the four photos above, named as in the table
    # in a folder with three@0.169.0 and playwright-core installed:
    node room_build/hair_mh/render.mjs src/head.json src node_modules/three out/
