# Room "game look" scorecard (issue #98, G8)

How close `/room` is to a current-generation game look, area by area, scored 1–5 against written criteria, from the
fixed-camera shots of `tests/visual/` (headless Chromium, software WebGL, the same poses and light every run). The
reference described under each area is what a 5 would look like; it is a description, not a shipped image.
Shots referred to are in a run's `tests/visual/out/` (`python -m tests.visual.harness`); a contact sheet of the run this
scorecard was made from is `docs/qa/shots/`. The defect list with routing is `docs/qa/defects.md`.

Scale: 1 placeholder · 2 clearly amateur · 3 decent indie · 4 game-quality with nits · 5 indistinguishable from a
current game at the page's camera distances.

## Scores on `main` (5f12ea9, 2026-10-02)

| area | score | one line |
|---|---|---|
| character face | 2 | photo-projected texture on a faceted low-poly head; good from the overview, falls apart in any close-up |
| character body (clothes, hands, feet) | 2 | glossy black hoodie and trousers (PVC look), faceted sleeves and socks, mitten hands; the phone grip mesh is good |
| character motion | 3 | sits, lies, walks, eats, holds the phone, breathes and glances; forearms through the desk, toes under the floor, sleeps on the duvet in his slides |
| soft goods (duvet, pillow, curtains, hanger socks, towel, cushion, hoodie on the door) | 2 | good fabric textures on hard, un-sculpted shapes: box pillow, tube socks, slab towel |
| hard surfaces (furniture, desk items, shelf, fridge, door) | 4 | the strongest area: lamp, speakers, keyboard, mug, plant, controller, chair read as real objects; walls are bare |
| lighting (day, dusk, night, lamp, screens) | 3 | convincing day and dusk; the night room is almost black, the lamp blows the hoodie out, the monitor is pure white; no contact shadows or AO on him |
| window and outside | 2 | a nice sky gradient, sun and moon; the city is flat grey cuboids on one plane, no haze, depth or reflection |
| **overall** | **2.6** | a clean, well-propped room with a placeholder-grade character and soft goods |

Measured on the same run (see `tests/visual/out/results.json`): bed/chair penetration 0 in every scene; 50 skinned
vertices (of ~17,700 sampled) inside the desk top in the sitting pose, left forearm mostly; left toes 1.2 cm below the
floor when standing; night (23:00, lights off) mean luminance 10/255 with 12 % pure-black pixels at 1280 and 18 % at
390; the only blown-out pixels are the monitor's white page (4 % at 1280, 9 % at 390); animate() 0.16–0.27 ms/frame;
55 draw calls, 171k triangles; no z-fighting flagged; no JS errors; the character's 2048² texture has anisotropy 1
(room textures 8).

## Criteria and reference, per area

### Character face
Criteria: (a) smooth silhouette of the head and jaw at the close-up distance (0.5 m), no visible facets; (b) separate
eyes with a wet highlight and lids that can blink; (c) brows, lashes and lips as geometry or alpha cards, not only paint;
(d) skin with a normal/roughness map, subsurface tint on ears and nose; (e) hair as cards with an anisotropic highlight
and a believable hairline; (f) the face identity kept (the owner keeps this character).
Reference (a 5): a stylised young man as in a current anime-adjacent 3D game: ~8–12k triangles for the head alone, a
1k–2k face texture of its own, hair cards with a specular band, eyes that catch the window.
On main: a ~31k-triangle whole body with one 2048 texture; flat triangles visible on cheeks, jaw and neck in
`closeup_face_14.png`; hair as spiky black shards without specular; eyes painted but readable; identity fine. **2**.

### Character body
Criteria: (a) cloth reads as cloth: matte cotton hoodie, soft trouser folds, roughness ≥ 0.8, no baked specular; (b)
clean silhouette with no faceting on sleeves and legs; (c) hands with fingers (even without finger bones, a sculpted
hand); (d) feet, socks and slides with round cross-sections; (e) a normal map for seams, cuffs, drawstrings.
Reference: a hoodie-and-sweatpants character from a current life-sim: matte fabrics, visible seams, soft folds at the
elbows and ankles, five fingers, socks that wrinkle at the ankle.
On main: glossy black hoodie and trousers with baked highlights (`door_8_1280_char.png`), faceted sleeves, faceted white
socks (`closeup_feet_14.png`), mitten hands in bed (`closeup_bed_14.png`); the `hand_phone.glb` grip is good
(`closeup_grip_14.png`). **2**.

### Character motion
Criteria: (a) no frozen poses: breathing, weight shifts, glances; (b) transitions walk–sit–lie without pops; (c) no
interpenetration with the bed, chair, desk or floor; (d) seated and lying poses that look relaxed (arms, hands, head);
(e) the camera shows what he does (face visible at the desk at least sometimes).
Reference: a character in a current life-sim at a desk: typing hands, a slouch that changes, feet on the floor, a
turn of the head to the window; asleep: under the duvet, on his side, slow breathing.
On main: breathing, glances and idle variants exist; bed/chair penetration 0; forearms through the desk top and toes
through the floor (measured); sleeps on top of the duvet, arms stiff, slides on (`closeup_bed_14.png`); the follow
camera at the desk looks at the back of his head (`desk_14_1280.png`) and jumps to the monitor while he is still
walking there (the server never sends `path`; `walking_8_1280_clean.png`). **3**.

### Soft goods
Criteria: (a) sculpted forms: a pillow with a dent, a duvet with folds and a soft edge over the frame, socks and a towel
that hang and bend; (b) fabric normal maps at ≥ 300 texels/m; (c) no hard box or cylinder silhouettes on cloth; (d)
curtains with irregular folds and a hem.
Reference: bedding from a current interior-design game: a crumpled duvet, a dented pillow, a towel folded over a rail.
On main: duvet and sheet textures are good (374 and 311 texels/m) but the pillow is a hard rounded box
(`closeup_duvet_14.png`); the hanger socks are 10-sided straight cylinders with flat-cut ends and a second cylinder for
the foot, the towel a flat box, the pegs boxes (`closeup_socks_14.png`); the hoodie and tote on the door are slabs. **2**.

### Hard surfaces
Criteria: (a) bevelled edges and correct scale on furniture; (b) PBR materials (wood grain, brushed metal, plastic)
with normal and roughness maps; (c) desk clutter with real shapes; (d) baked AO in corners; (e) trim: skirting,
window reveal, door frame.
Reference: a desk set from a current game: a lamp whose joints read, speakers with a grille, a keyboard with key caps.
On main: the Poly Haven props and the modelled desk items hold up at close range (`closeup_desk_19.png`); AO is baked;
walls are bare white with no skirting, books are coloured blocks, the mouse a blob, the bin a cylinder. **4**.

### Lighting
Criteria: (a) every hour readable: shapes visible at night, whites not clipped in the morning; (b) a key, fill and
rim: window light by day, lamp and ceiling light in the evening, screen glow on his face; (c) soft shadows with contact
under him and the props; (d) exposure that follows the time of day without flattening the room; (e) colour grading.
Reference: a bedroom at night in a current game: moonlight and city glow through the window, a dim blue fill on the
floor, the phone lighting his face, the rest dark but legible.
On main: 08:00, 14:00 and 19:00 look good (`door_8_1280_clean.png`, `desk_14_1280_clean.png`,
`eating_19_1280_clean.png`; ≤ 0.2 % blown pixels without the monitor in frame); the monitor's white page is unlit 255
white and reads as a blown rectangle; the lamp blows the hood out to white (`eating_19_1280_char.png`); 23:00 with the
lights off is almost black (`sleeping_23_1280_clean.png`); no contact shadows under him; no AO on the character. **3**.

### Window and outside
Criteria: (a) a city with depth: two or three parallax layers, haze, rooftops and windows with structure; (b) the sky
with clouds that move and a sun or moon of the right size; (c) glass with reflection and a sill that catches light;
(d) weather states (rain) that reach the room; (e) night windows and a tower light.
Reference: the view from an apartment window in a current Tokyo-set game: dense low-rise blocks, a tower, haze towards
the horizon, a glint on the glass.
On main: the sky gradient, sun, moon and stars are pleasant (`phone_23_1280_clean.png`); the city by day is flat grey
cuboids and two grey towers on one plane (`closeup_socks_14.png`, `closeup_grip_14.png`); no glass reflection; rain is
a uniform in the shader. **2**.

## How to re-score
Run `python -m tests.visual.harness --out tests/visual/out` on the branch (or `--full`), read `report.md`, compare
the same shots against the criteria above, and change only the scores whose evidence changed. Every re-score gets a
dated row in `docs/qa/history.md`.
