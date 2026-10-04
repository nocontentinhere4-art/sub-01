# Room soft props, second pass: sheets

Preview branch only. Neither sheet is installed in `web/` or meant to be merged.

- `before_after.jpg`: the committed room before this pass (left) and after it (right), with locked cameras and the
  page's day light (`room_build/shots_soft.py`: `overview_1280_day`, `backpack_day`, `sneakers_day`, `tote_day`).
- `real_vs_render.jpg`: each item next to a real photo of the same kind of object, from a similar angle
  (`shots_soft.py`: `ref_backpack`, `ref_sneakers`, `ref_cloth`, `ref_tote`). From top to bottom:
  backpack, sneakers, rumpled cloth (the throw), canvas tote. Real photo on the left, render on the right.

## Reference photos (all public domain or CC0)

| row | photo | author | source | licence | changes |
|---|---|---|---|---|---|
| backpack | "Hands Backpack" | Mike Moloney | https://stocksnap.io/photo/hands-backpack-PGVWO7IJWP | CC0 1.0 | resized |
| sneakers | "Smelly Canvas Sneakers" | Fun with My Shoes (Flickr) | https://www.flickr.com/photos/183535671@N03/48578718317 | Public Domain Mark 1.0 | resized; the maker's name on the insole blurred |
| rumpled cloth | "Bed Bedroom" | Kristin Hardwick | https://stocksnap.io/photo/bed-bedroom-U8QOG5XQA4 | CC0 1.0 | resized |
| canvas tote | "20230522-FS-KM-006" | Forest Service Photography (Flickr) | https://www.flickr.com/photos/140082569@N07/53122829296 | Public Domain Mark 1.0 | cropped to the canvas bags (no face in the frame); resized |

Licences were read from the Openverse API (`license`, `license_url`) and the source pages when the photos were
fetched (2026-10-04). No photo shows a face. Wikimedia Commons and Pexels refused this environment's requests, so
none of the photos come from there.

## How the items hold up (an honest read of the sheet)

- **Sneakers:** the closest. The shape, the proportions and the sole edge are right. Still missing: the outsole's
  tread, the canvas weave on the upper (it reads as smooth), and laces as dark as the canvas.
- **Backpack:** the shape, the size and the parts (zips, pocket, handle, straps) are right. The fabric is not:
  a real polyester pack is creased and soft all over, with metal zip pulls and a slight sheen. Ours is too smooth and
  too clean.
- **Rumpled cloth (the throw):** the folds read as cloth, but the edge is paper-thin (a real fleece throw has a 4–6 mm
  rolled hem) and the cloth is too smooth.
- **Tote:** the canvas folds and the weave compare well. The reference shows bags in use rather than hanging, so it
  is a weak match for the drape.

Next steps: crease the backpack's panels (a short cloth pass, or wrinkle normal maps), metal sliders and pulls, a hemmed
edge on the throw, a tread on the soles. Tripo is allowed for this work (cap: 400 credits). Credits spent so far: **0**.

## Pass 3

Requested by the coordinator after the owner's review. Sheets:
- `before_after_pass3.jpg`: the committed room on main (left) and this pass (right), with locked cameras. Rows: the
  overview, the hoodie, the jeans, the sneakers, the floor cushion, the chair, the desk lamp, and the carton on the
  bookshelf.
- `real_vs_render_pass3.jpg`: the hoodie, the jeans, the sneakers and the cushion (throw and joggers), each next to a
  real photo from a similar angle.

What changed:
- **Triangle budget, no cap raise.** The desk lamp scan was cut from 24.1k to 6.0k triangles and the carton scan from
  17.0k to 3.0k (edge-collapse decimation, UVs and textures kept; `decimate()` in `build_room.py`). The lamp and carton
  rows of the sheet show no change at that distance. The room went from 198.3k to **171.2k** triangles, 56 draw
  calls, 6.0 MB. That leaves about 29k triangles for G5 and G10d.
- **Hoodie:** rebuilt as cloth simulations in turn. The body hangs from its neckline, so the weight pulls the
  shoulders into a slope with folds running down from the neck. The sleeves hang from the shoulders down the sides.
  The hood is caught on the hook a hand's width above the neck and folds over it. Two drawstrings hang down.
- **Jeans** (the blue blob by the bed): a flat jeans pattern (waist, seat, two legs), bunched along the legs and
  dropped as stiff denim with self-collision, so it lies in a heap of real folds.
- **Sneakers:** now an upright pair, toes to the wall. The left one is pulled out 5 cm, so the two fit the 17 cm strip
  without touching (checked in the build). The canvas is lighter grey. The opening now follows the mesh rings
  (outer edge, padded rim, inner lip, insole), so its edge is clean.
- **T-shirt over the chair:** a softer drape. The sleeve hangs down; no stiff corner.
- **Joggers:** grey cotton joggers (darker ribbed waistband and cuffs) dropped as cloth onto the floor cushion and the
  throw. The slippers were already gone after pass 2.

Reference photos added (CC0):

| row | photo | author | source | licence | changes |
|---|---|---|---|---|---|
| hoodie | "Dark Grey" | Patryk Sobczak | https://stocksnap.io/photo/dark-grey-B1CD3921D5 | CC0 1.0 | resized; seen from behind, hood up, no face |
| jeans | "Dirty jeans grass floor" | (rawpixel, public domain) | https://www.rawpixel.com/image/6035981/photo-image-public-domain-plant-blue | CC0 1.0 | resized |

The sneaker and rumpled-cloth photos are the pass-2 ones above. I found no joggers photo with a clear licence: the
one candidate was a retailer's product shot marked public domain on Flickr, which I don't trust, so the cushion row is
compared with the rumpled-clothes photo.

An honest read:
- **Hoodie:** it now hangs like a real one (sloped shoulders, folds from the neck, the hem resting on the door). The
  sleeves are still too flat and board-like, and the fabric lacks the knit's texture at close range.
- **Jeans:** the heap and the folds read as heavy cloth. With no waistband, pockets or seams, it doesn't read as
  *jeans* up close.
- **Sneakers:** much closer to the photo. Still missing the tread and the canvas weave.
- **Joggers and throw:** both read as cloth, but they're too smooth next to real fabric.

Tripo credits spent: **0**.
