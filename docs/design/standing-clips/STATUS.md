# G22 — standing and in-between clips on the Mixamo-rigged character: status

Branch `preview/standing-clips` (off `origin/preview/mixamo-pipeline`). No raw capture is committed: the FBX are read from
`claude/loving-davinci-6hqmjx` into a temp dir by the re-bake and deleted after.

## State (2026-10-07, WIP)
- [x] Bake: `room_build/kimodo/standing_bake.py` (+ `standing_exp.mjs`, `standing_clips.json`); one command
      `room_build/kimodo/standing_rebake.sh <character.glb>` → `web/room/mx_standing/<Clip>.glb` + `standing_clips.meta.json` (9 clips, ~4 min).
- [x] Page entry: `room.html?char=mixamo&clip=<Clip>` (`web/room/standing_preview.js`); the default page is unchanged (no `clip` → nothing runs).
- [x] Contact in the room: `CLIP=<Clip> room_build/kimodo/contact_pass.mjs <port> x clip` (every frame, whole room, walls, phone).
- [x] Self contact: `room_build/kimodo/standing_selfcontact.mjs` (every frame; `rig/autorig/qa.html` `QA.selfContact`).
- [x] Seat points swept per clip in the room (`seatAt`): his knee is 0.49 m up with the foot flat and the cushion
      top 0.505 m, so he sits 18–24 cm forward of the chair's pivot (the seat pan's front edge otherwise runs 2–4 cm
      into his thighs); Gaming and Angry_Gesture then measure 0 contacts at the desk.
- [x] Spots: standing on the rug; Gaming / Angry_Gesture at the desk (chair rolled back + 0.28 m aside, clear of the
      props beside the desk); Stand_To_Sit / Sit_To_Stand with the chair where the page has it for them (`chairAt(1)`);
      Scared / Standing_Clap with the chair in the open (at the desk they need more roll-back than the bed allows).
- [x] Phone: the page's phone on the right hand, lifted onto his curled fingers (no hand skin inside it or over its screen).
- [ ] Contact table per clip (re-running after the spot changes)
- [ ] Render sheet `docs/design/standing-clips/sheet.jpg`
- [ ] Full pytest + visual gate
