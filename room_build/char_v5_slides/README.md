# v5 slides as their own mesh (delivered to preview/room-v5 as web/room/char_v5.glb)

From the uncompressed v5 build with finger bones (`char_idle.glb` + `char_walk.glb`, as in `../char_v5_fingers/`):

1. `slides.py`, `footfill3.py`: find the slide triangles of the body: black triangles on the foot and toe bones (and low
   on the heel) below the trouser cuff, plus the thin white footbed rim and grey sole edges. Tripo never modelled the
   foot under the strap, so `footfill3.py` replaces the original sock and toe pieces below 6 cm with a generated white
   sock: an ankle tube fitted to the original sock and tucked into it under the trouser cuff, plus a 26 cm foot with a
   rounded heel and toe and a flat-ish sole on the footbed. The foot stays under the strap and inside the slide's sole,
   so nothing shows through with the slides on. It is skinned from the 4 nearest original foot vertices.
2. `splitslides.mjs`: the slide triangles become a skinned mesh `slides` (own compact vertices, same skin and material),
   and the body gets the foot volumes.
3. `MATTE=0.8 node room_build/build_char_tripo.mjs`, then `dequant_slides.mjs`: meshopt quantizes positions and folds the
   dequantization into each skin's inverse bind matrices. The slides get real float positions in metres again (with
   matching inverse bind matrices), so a page that clones their geometry with `bindMatrix` (boy_mh.js parks a pair by
   the bed) gets life-size slides.

## Natural feet (delivered to preview/bed-music)

`footfill_natural.py` replaces `footfill3.py`'s lofted foot. The foot is one implicit surface with measured adult-male
proportions: the ankle tapers into the heel, there is an instep and a medial arch, the ball is wider than the heel, the
toe end is squared off and obliquely cut, and the toes show as soft ridges. It stays at least 2.5 mm inside the slide's
strap and footbed, so the look with the slides on is unchanged. The sock below the ankle is skinned to the Foot bone.

The steps are the same as above: run it with `DARKK=195 python3 footfill_natural.py`, then `splitslides.mjs`,
`build_char_tripo.mjs` and `dequant_slides.mjs`.

Lying check: `node room_build/char_bed_shots.mjs <char.glb> <room_bed_lie.glb> <outdir> 1` renders the end pose of the
clip on a stand-in mattress from the foot end and from a low side, with the slides hidden. The clip is
`web/room/mh_v5/room_bed_lie.glb` on main.

Proportions, renders and what is left: `docs/design/bed-music/feet/README.md` on preview/bed-music.
