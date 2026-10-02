# Game look: a catalogue for the #98 workers (G2–G8)

Research only (G1, 2026-10-02). Every licence below was read at the linked page on that date; "unverified" means the
page could not be read. Grouped by the stream that would use it. **Top 3** per stream are marked ★. Nothing here is
merged code: it is what the other streams can act on today.

Rules that apply to everything listed (issue #98): shipped assets must be CC0 or explicitly free for commercial
redistribution and go in `web/room/CREDITS.md`; the room page stays ≥ 30 FPS on a mid-range phone; total room assets
≤ 12 MB (today 7.4 MB in `web/room/`); no Mixamo; the character keeps his identity and resembles no real person.

## 0. Where we start (measured on `main`, 2026-10-02)

| thing | today | why it matters |
|---|---|---|
| `boy.glb` | 982 KB, 31,088 triangles, 35,483 vertices, 24 bones, no morph targets | enough triangles for a game character; no fingers, no face rig |
| its material | **one** material, one 2048² WebP (462 KB) used as base colour **and** emissive at factor 1 (Meshy export); `roughnessFactor` 0.41; `KHR_materials_specular` `specularColorFactor` = [2,2,2]; no normal, roughness, metalness or AO map; double-sided | `room.html` zeroes the emissive and forces roughness 0.78 / `envMapIntensity` 0.5, so he is a baked-light albedo with a flat uniform roughness: no skin, eye, hair or cloth response. This is the single biggest lever for G2 |
| room | `room_clean.glb` 4.17 MB, 135k triangles, 42 primitives, 48 WebP textures (1k, floor 2k), AO baked to `room_ao` (UV2, 247 KB) | AO only: no bounced colour, no baked direct/indirect light |
| renderer | r169, `antialias:true`, DPR ≤ 1.5 adaptive, ACESFilmic, `PCFSoftShadowMap`, sun 2048² (manual update), lamp point-light shadow 512², `RoomEnvironment` PMREM, RectAreaLight window, no `EffectComposer` | no AO/SSAO, no bloom, no grade, no contact shadows; `RoomEnvironment` is a studio box, not this room |
| motion | 7 Meshy clips (sit idle, sleep, eat, text, idle, door, walk) + procedural layers in `room.html` (breathing, weight shift, gaze, arm IK by hand) | few clips, no finger motion, no blink |

