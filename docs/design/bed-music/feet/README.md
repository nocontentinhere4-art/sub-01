# v5 feet: natural socked feet (for lying on the bed awake)

AI-generated content: the character and its textures come from Tripo (tripo3d.ai) and are used under Tripo's terms of
service. He is an original fictional ~20-year-old man, not a real person, with no brands or logos. Preview only.

`web/room/char_v5.glb` is rebuilt with new socked feet. With the slides off (lying on the bed with no duvet) the feet
used to read as two white mitten-like blobs. Only the generated sock below 6 cm changed.

Unchanged:

- the `slides` mesh: the same 19,854 triangles, the float positions in metres and the box;
- the rig: 79 joints with the MakeHuman finger names;
- the `idle` and `walk` clips;
- the knit carried across the ankle band.

The body has 323,965 triangles (before: 321,168).

## Shape: measured, not eyeballed

The proportions come from an adult male foot for a 1.75 m man. Length is 26 cm (about 0.15 of height). The ball is
the widest part, at about 70% of the length from the heel, and the heel is narrower.

Profiles along the foot, in cm from the heel. The half-widths are scaled to this foot's own ball width (Tripo's toes):

| u (cm) | 0 | 1.5 | 4 | 7 | 10 | 13 | 16 | 19 | 21 | 23 | 25 | 26 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| half width | 2.4 | 3.1 | 3.3 | 3.3 | 3.5 | 3.9 | 4.5 | 5.0 | 4.9 | 4.4 | 3.4 | 2.4 |
| top above the sole | 3.2 | 5.5 | 9.0 | 9.5 | 9.0 | 7.4 | 6.0 | 4.2 | 3.3 | 2.6 | 2.2 | 1.8 |

Features of the shape:

- **Ankle into heel:** the leg is Tripo's own sock ring, narrowed toward the heel at the back (the Achilles). The heel
  therefore bulges out below it, instead of a tube meeting a lump.
- **Arch and instep:** the instep rises to the ankle crease. The sole is flat on the outer side, and the inner arch
  lifts about 1.4 cm under the mid-foot.
- **Ball and toes:** the ball is wider than the heel (9.1–9.4 cm against 6.6 cm). The toe end is flattened and squared
  off obliquely, with the big-toe side the longest. Five soft toe ridges sit near the tips.

The foot is one smooth implicit surface (foot and leg blended), meshed by marching cubes, smoothed and reduced to about
7,000 triangles per foot.

It stays inside the slide: it keeps at least 2.5 mm off the strap's underside, the strap's walls and the footbed, so
nothing shows through the strap with the slides on.

The sock below the ankle is skinned to the Foot bone. Tripo's own weights had given the heel to the calf twist bones,
which tore the heel off the foot when the foot points, as it does lying down.

## Renders

- `bed_lying_feet.webp`: him lying on his back. The pose is the end of `room_bed_lie` from main, applied by bone name.
  The slides are hidden and there is no duvet. Views: from the foot end (wide and close), and from a low side (wide and
  close). The mattress is a plain grey box under him, standing in for the room's bed.
- `bed_before_after.webp`: the same close views, with main (95abd03) above and this build below.
- `feet_three_view.webp`: the old three-view sheet (front, low side, walk frame), slides on and slides off.
- `feet_close.webp`: close views (front, low side, top, under), slides on and slides off.

## Left

- The sole is flat and quite boxy at the heel's back corner from the low side.
- Just under the trouser cuff, Tripo's own sock above the join has a ragged edge, seen close from a low side.
- In the walk frame (slides on) there is a faint grey patch on the sock at the back of the heel, where the knit texture
  meets the plain sock colour.
