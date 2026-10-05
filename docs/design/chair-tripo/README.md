# Office chair made by the owner on Tripo (preview/chair-tripo, G10d): preview only, nothing live

Based on preview/room-upgrade (fc52140). The owner's chair replaces the code-built one by default; `?chair=code` brings
the code-built chair back for comparison.

`chair_owner_raw.fbx`: the owner's Tripo export (79.9k tris, one mesh). `raw_clay.jpg`: six views in neutral grey.
`owner_marked_defects.jpg`: the owner circled the letter-shaped holes and dents on the backrest, the headrest and the back
of the frame; those must go. Tripo's own texture atlas is not used: it has the same letters, so the owner asked for
materials made here instead, matched to a real chair.

## Sheets
- `defects_before_after.jpg`: the backrest close up from the front, the back, 3/4 front and 3/4 back. Top: as exported.
  Bottom: repaired.
- `materials.jpg`: the finished chair in a neutral studio (3/4 front, 3/4 back, side), close-ups of the mesh, the seat
  fabric and the base, and the parts map.
- `real_reference.jpg`: the chair next to two real chairs (CC0 photos) at about the same angles.
- `chair_in_room.jpg`: the room at 14:00. By the desk from behind (3/4) and straight behind, turned to the room and pulled
  out (3/4 front, high and low; turned for the shot only, the way he leaves it when he gets up), and the wide view.
- `chair_seated.jpg`: him in it, at the desk (typing and mouse) and reading, from two cameras each.

## The pipeline
All four steps are deterministic: running them again gives the same files byte for byte.

```
node room_build/fbx2ply.mjs docs/design/chair-tripo/chair_owner_raw.fbx raw.ply      # FBX -> PLY (three.js FBXLoader)
python room_build/chair_owner_repair.py raw.ply repaired.ply --report repair.json      # the letters covered over
python room_build/chair_owner_parts.py repaired.ply parts.ply [--preview colours.ply]  # the parts, box UVs
node room_build/build_chair_owner.mjs parts.ply <ambientCG folder> web/room/chair_owner.glb
```

`<ambientCG folder>` holds `Fabric030/` and `Plastic006/`, the 1K JPG sets from https://ambientcg.com/a/Fabric030 and
https://ambientcg.com/a/Plastic006 (CC0).

## The repair (geometry)
The letters are real holes through the cushions, with inverted, non-manifold walls, so cutting them out and capping them
does not hold. Each area is covered over instead:
1. a smooth surface (a thin-plate spline) is fitted to the cushion's outer envelope, leaving out the letters' pits;
2. the raised fringes that stick out past that surface are deleted, only where the new surface will cover them;
3. a new surface is laid 1.2 mm over the old one. Over its last 2.2 cm it follows the original surface and tucks 0.8 mm
   under it, so there is no step at the edge;
4. it gets texture coordinates from the faces under it.

Nothing outside the five areas is changed.

| area | faces deleted | new faces | fit residual |
|---|---|---|---|
| backrest, front (upper) | 204 | 4986 | 0.09 mm |
| back of the mesh panel (down to the lower cross-bar: the third line of letters behind it) | 223 | 4090 | 0.19 mm |
| lumbar pad | 33 | 2544 | 0.12 mm |
| headrest, front | 0 (dents only) | 1064 | 0.16 mm |
| headrest, back (the small plate and two pits in its recess, and a spike) | 3 | 748 | 0.33 mm |

79,893 -> 92,862 faces before the decimation. Left as they are: small rough patches at the left and right edges of the
mesh panel's back. They are in the original, outside the marked areas, and are not letters. The mesh panel and the
plastic are drawn from both sides, so their small openings show the dark inside, not the room.

## The materials
`room_build/chair_owner_parts.py` splits the mesh into the parts of a real mesh chair (positions and facing in the
model's frame). Where a mesh panel meets its frame ring, the faces are cut along a smooth line a fixed distance in from
the panel's outline, so the change of material is a clean edge. Tripo's UVs belong to its atlas; each face gets a box
projection in metres instead, for tiling micro-textures.

| part | material | made of |
|---|---|---|
| backrest and headrest mesh (front and back, inside the frame rings) | `chair_mesh` | black knit drawn in the build: about 2.9 mm cells on a 4 cm tile, the darker gaps in the colour, the strands in the normal and roughness |
| seat cushion, lumbar pad | `chair_fabric` | black upholstery: ambientCG Fabric 030's weave (colour variation, normal, roughness), darkened, on a 12 cm tile |
| frame rings, spine, headrest arm, arm posts, seat pan, mechanism | `chair_plastic` | black matte plastic: a fine moulded grain drawn in the build (normal), ambientCG Plastic 006's mottled roughness (~0.7) |
| armrest tops | `chair_armpad` | the same plastic, softer and rougher |
| gas lift | `chair_lift` | black, a little glossy (as in the reference) |
| five-star base | `chair_base` | polished aluminium (as in both references) |
| casters | `chair_caster` | black nylon |

The mesh is opaque, not see-through. Tripo's backrest is a solid cushion shell, not a membrane: holes in it would show
its inside and the old surface left under the covers. The knit reads in the colour, the normal and the sheen.

The real chairs (`real_reference.jpg`, both CC0 1.0 from the WordPress Photo Directory). No CC0 or public-domain photo of a
black mesh chair with a headrest, shown whole from the front, could be found.
- "Ergonomic desk chair" by Ohidul Islam (https://wordpress.org/photos/photo/53365c4f26/): a grey mesh chair with a
  headrest in a white frame. Used for the parts and finishes: mesh back and headrest, polished aluminium base, black lift.
- A photo by Manjil Aryal (https://wordpress.org/photos/photo/54687c82e4/), cropped, with no logo in the crop: the black
  mesh and the black matte frame, seen from behind.

## In the room
`room_build/build_chair_owner.mjs` -> `web/room/chair_owner.glb`:
- scaled x1.278, so the seat cushion's top is 0.52 m. The chair is 1.25 m tall with the headrest;
- turned 180° (Tripo's model faces +z; the sitter in the room's chair faces -z);
- its gas lift on the pivot of the room's `chair` node, then moved 5 cm back.

Then it is welded and decimated a little: 54.1k triangles, 7 materials, 1.07 MB (of which the textures are 326 KB). The
page puts it whole into the room's own `chair` node, so CHAIR, chairHome, pulling, swivelling, riding and getting up are
unchanged.

**Why 5 cm back:** his skin was recorded in the chair's frame across every seated clip and tested against the chair. With
the gas lift exactly on the pivot, his reclined back in room_phone and room_read went through the backrest. From 5 cm back,
every seated clip is clear. The cost: the chair turns about a point 5 cm in front of its gas lift when it swivels. In the
typing pose he sits forward, so his back is a few centimetres off the backrest.

## Contacts (vertex by vertex, G2's body, every 2nd frame, 2 mm tolerance)
`python -m tests.visual.contacts --chair-sdf <sdf.npz>`. The chair is tested through a 5 mm signed-distance grid
(`python -m tests.visual.chair_sdf repaired.ply sdf.npz`), because the Tripo mesh is not closed. The sign of each cell is
a vote of the 16 nearest surface samples, not one sample's normal, which had flagged free space near the panel's edge.

| scenario | frames | chair | keyboard / mouse (hands) |
|---|---|---|---|
| desk typing | 150 | 0 | 0 |
| desk mouse | 120 | 0 | 0 |
| room_read | 262 | 1 thigh vertex, 3 mm (at the grid's resolution) | 2 fingertips, 1 frame, 4.9 mm |
| room_phone, room_phone_scroll | 326 each | the back of the head touches the headrest: 11 vertices, 3 mm | 0 |
| eating at the desk | 120 | 1 back vertex 4 mm, 3 thigh vertices 6 mm | right hand, 24 frames, 14 mm |
| bedtime: stretch, get up, to bed | 330 | **head and neck into the headrest: 910 vertices, 40 frames, 13 mm**; thighs 9 mm and a foot 15 mm on the way up | left hand pushing off, 6 frames, 14 mm |
| getting up to the window | 180 | feet and calves over a base leg 19 mm, right forearm on the armrest 11 mm, 2–4 frames | left hand pushing off, 1 frame, 14 mm |
| sitting down at the desk | 240 | forearms and hands on the armrests, up to 16 mm, 6 frames | mouse: right hand arriving, 2 frames, 17.6 mm |

The keyboard and mouse contacts are the clips' own and match the earlier report. The chair contacts in the transitions
(sitting down, getting up) come from the owner's armrests and base, where the code-built chair had none. They last a few
frames each.

**The headrest in the bedtime stretch:** he leans his head back through the headrest by 13 mm. Moving the chair further
back does not help. Tilting the backrest and headrest back 10° clears it, but that changes the owner's model, so it is not
done here. It is an option if the owner wants it.
