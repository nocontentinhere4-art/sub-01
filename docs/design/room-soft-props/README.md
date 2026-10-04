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
