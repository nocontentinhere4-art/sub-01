# char-fix: the collar (hood lining) on v5

v5's head is a separate bust grafted on the body. Between the neck and the hood there was nothing: the hood is one thin
shell standing 6-9 cm off the neck at the sides and back, so looking down the collar you saw the shell's back faces and
into the body. The owner's one-piece Tripo character (`docs/design/char-owner-tripo/`) is the reference: its lining
runs from the hood's rim down into a groove that meets the neck 1.5-3 cm below it (0.7-2.5 cm off the neck at the rim,
a fold about 2 cm thick).

`hood_lining` is that inner surface on v5, a part of its own on the same skeleton: for each 3 deg round the neck, from
the hood's top rim down the inside of its wall (3 mm inside it, facing the neck) to the wall's innermost lip, then a
sagging groove down to the neck 2.5 cm below the lip, 2 mm into it (closed all round). Skinned from the hood's nearest
vertices at the top and the neck's at the bottom. Its fabric is a 7.6 cm patch of the hood's own texture (base colour
and normal map), mirrored-tiled at real scale. The face, the neck and the hood's outer shape are untouched.

`hood_patches` fills the hood's own holes round the collar: every open-edge loop of its mesh there (10 of them, 237
triangles; the loop along the hood's top rim, behind the lining, stays open), a fan about each loop's centre in the
same fabric, skinned from the nearest hood vertices (`patches.py`).

Rebuild (from `room_build/`; the dumps under `charfix/v5` are made by `dump.mjs` from `web/room/char_v5.glb`, the
fabric patch by hand from its texture as described in `lining.py`):

    node charfix/dump.mjs ../web/room/char_v5.glb charfix/v5
    python3 charfix/lining.py            # -> lining.npz, then its raw files and spec_collar.json
    python3 charfix/patches.py           # -> the patches' raw files
    node charfix/add_parts.mjs <char_v5.glb> <out.glb> spec_collar.json
