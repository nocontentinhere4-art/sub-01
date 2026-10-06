# v5 slides as their own mesh (delivered to preview/room-v5 as web/room/char_v5.glb)

From the uncompressed v5 build with finger bones (`char_idle.glb` + `char_walk.glb`, as in `../char_v5_fingers/`):

1. `slides.py`, `footfill.py`: find the slide triangles of the body: black triangles on the foot and toe bones (and low
   on the heel) below the trouser cuff, plus the thin white footbed rim and grey sole edges. Tripo never modelled the
   foot under the strap, so `footfill.py` also builds a closed, sock-white volume per foot, lofted inside the original
   envelope (the strap's inside, the toes, the sock) and skinned from the 4 nearest original foot vertices.
2. `splitslides.mjs`: the slide triangles become a skinned mesh `slides` (own compact vertices, same skin and material),
   and the body gets the foot volumes.
3. `MATTE=0.8 node room_build/build_char_tripo.mjs`, then `dequant_slides.mjs`: meshopt quantizes positions and folds the
   dequantization into each skin's inverse bind matrices. The slides get real float positions in metres again (with
   matching inverse bind matrices), so a page that clones their geometry with `bindMatrix` (boy_mh.js parks a pair by
   the bed) gets life-size slides.
