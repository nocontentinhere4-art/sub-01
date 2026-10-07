# G22 — standing and in-between clips on the Mixamo-rigged character: status

Branch `preview/standing-clips` (off `origin/preview/mixamo-pipeline`). No raw capture is committed: the FBX are read from
`claude/loving-davinci-6hqmjx` into a temp dir by the re-bake and deleted after.

## State (2026-10-07, WIP)
- [x] Bake: `room_build/kimodo/standing_bake.py` (+ `standing_exp.mjs`, `standing_clips.json`); one command
      `room_build/kimodo/standing_rebake.sh <character.glb>` → `web/room/mx_standing/<Clip>.glb` + `standing_clips.meta.json` (9 clips, ~4 min).
- [x] Page entry: `room.html?char=mixamo&clip=<Clip>` (`web/room/standing_preview.js`); the default page is unchanged (no `clip` → nothing runs).
- [x] Contact in the room: `CLIP=<Clip> room_build/kimodo/contact_pass.mjs <port> x clip` (every frame, whole room, walls, phone).
- [x] Self contact: `room_build/kimodo/standing_selfcontact.mjs` (every frame; `rig/autorig/qa.html` `QA.selfContact`).
- [ ] Contact table per clip (running)
- [ ] Render sheet `docs/design/standing-clips/sheet.jpg`
- [ ] Full pytest + visual gate
