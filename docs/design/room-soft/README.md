# Room soft goods at game quality (#98, G4)

Before/after renders of every soft item in the room, made by `room_build/shots_soft.py` (the same three.js r169 and
the same lights as `web/room.html`, 13:00 for "day" and 21:00 with the room light on for "night"; headless Chromium
draws in software, so the look is the page's, not its speed). Each image is `before | after` side by side: "before" is
`room_clean.glb` from `main` before this pass, "after" is the rebuilt model.

| item | file |
|---|---|
| the room, 1280 px, day / night | `overview_1280_day.jpg`, `overview_1280_night.jpg` |
| the room, 390 px (phone), day / night | `overview_390_day.jpg`, `overview_390_night.jpg` |
| the laundry pinch hanger | `hanger_day.jpg` |
| the socks (the owner's complaint: "stretched cones") | `socks_day.jpg`, `socks_night.jpg` |
| the hand towel | `towel_day.jpg` |
| the bed | `bed_day.jpg`, `bed_night.jpg` |
| the pillow | `pillow_day.jpg` |
| the duvet's turned-back head end and quilting | `duvet_fold_day.jpg` |
| the mattress and its fitted sheet | `mattress_day.jpg` |
| the curtains | `curtain_day.jpg`, `curtain_night.jpg`, `curtain_a_day.jpg` |
| the rug | `rug_day.jpg` |
| the floor cushion | `cushion_day.jpg` |
| the door hooks (hoodie and tote) | `door_day.jpg`, `door_night.jpg`, `hoodie_day.jpg`, `tote_day.jpg` |
| the backpack | `backpack_day.jpg` |
| the jeans on the floor (new) | `jeans_day.jpg` |
| the T-shirt on the bed (new) | `tee_day.jpg` |

## What changed (all in `room_build/props_soft.py`)
- **Socks**: no longer two cylinders. Each sock is a swept tube pinched at the clip, its cuff edges drooping below the
  clip, ribbing round the cuff, a flat leg, a heel bulging at the bend, a foot dangling forward with a rounded toe;
  colour per vertex (one dark pair with two light stripes, one cream pair with grey heels and toes); a knitted-fleece
  normal map, roughness 0.95, sheen. Their feet point away from the ring's centre, clear of the window wall.
- **Towel**: terry cloth (Poly Haven `terry_cloth`, recoloured), pinched by two clips: it sags between them, the corners
  outside the clips droop and fold forward, soft vertical folds grow to a wavy hem, a dobby border near the hem.
- **Duvet**: the cloth simulation now folds the head end back over itself (a real fold, self-collision), then the
  surface is box-quilted (6 × 5 channels, stitch lines sunk, puffs raised, a flat piped border), wrinkled a little,
  thickened to 3 cm with a rounded rim. The page's lying pose expects the top at about 0.86 m: unchanged.
- **Pillow**: a superellipse body in its case, flatter underneath, the side seam's piping, the case's envelope flap,
  a dent where his head rests, small wrinkles.
- **Mattress**: a soft rounded slab; the fitted sheet covers the top and the sides down to its elastic hem (a 3 mm
  step) with the ticking showing below it; faint wrinkles on top.
- **Curtains**: a pencil-pleat heading (ten pleats) merging into four soft folds, double hems and heading (thicker),
  a wavy hem edge, a slight flare; a lighter linen with sheen so the panels read as lit through. Real light transmission
  is not used: `post.mjs` strips `KHR_materials_transmission` on purpose (a whole extra render pass on phones).
- **Rug**: a 13 mm wool pile, faintly uneven, with a sewn binding tape round the edge.
- **Floor cushion**: tufted at five points (the cover pulled in, gathers round each tuft), a piped side seam, a
  mustard cotton.
- **Hoodie**: the hood bunched round the hook, shoulders dropping into a body hanging in soft folds, a kangaroo
  pocket, a ribbed hem (corduroy-rib normal map), sleeves hanging at the sides with ribbed cuffs, two drawstrings;
  sweatshirt fleece (Poly Haven `jogging_melange`).
- **Tote**: natural canvas, hanging by two handles looped over the hook's tip; the top edge peaks at the handles and
  droops between them, the sides crease, the bottom gusset gives it depth.
- **Backpack**: a polyester-weave normal map, a fuller front and rounded top, the lid's and the pocket's zips with
  pulls, a stretch bottle pocket on the side, a grab handle, a shoulder strap's end with its buckle on the floor.
- **Clothes (new)**: a pair of jeans in a heap by the bed's foot (the seat with its waistband, one leg folded back,
  the other crossing over it; Poly Haven `denim_fabric_05`), and a T-shirt thrown on the bed's far foot corner (a flat
  tee cut from a grid, dropped as cloth onto the duvet; it hangs over the far side). Both are registered with the prop
  sweep (on the floor, off his walking graph and the places the page uses).

Textures: Poly Haven, CC0 (`web/room/CREDITS.md`). No Higgsfield credits were spent.
