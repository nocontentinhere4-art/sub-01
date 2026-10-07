# Rig-change checklist: char_mixamo.glb

Run by `room_build/kimodo/rig_change.mjs` (from `rig/autorig.sh`), 2026-10-07.

| item | status | measured |
|---|---|---|
| char_mixamo.js plays the clips by bone name | PASS | Seated_Idle: 65/65 bones, world rotations within 0.03° of the performer's (finger5-2.L); Typing: 65/65 bones, world rotations within 0.03° of the performer's (finger1-1.R); Laying_Sleeping: 65/65 bones, world rotations within 0.04° of the performer's (finger2-1.R) |
| the forward lean, measured with no fit | MEASURED | Seated_Idle: hips→neck 3.9° from vertical (performer 7.9°); Typing: hips→neck 4.4° from vertical (performer 5.1°). No 10° fit is applied on this rig. |
| hoodie stretch per seated clip | MEASURED | Seated_Idle: torso edges p95 92.2 %, 23.21 % of edges past ±30 %; whole body p95 56 %; Typing: torso edges p95 96.3 %, 24.43 % of edges past ±30 %; whole body p95 57.5 % |
| the 0.8 s hands-to-thighs blend vs his thighs | PASS | Seated_Idle→Typing: hands in thighs 0/28 frames; Typing→Seated_Idle: hands in thighs 0/28 frames. Armrests and desk edge: PENDING (the room page). |
| soles vs the floor (clip frame) | MEASURED | Seated_Idle: L -0.6…-0.5 cm, R -1…-1 cm; Typing: L -1.4…-0.9 cm, R -2.1…-1.7 cm (contract 0…+1 cm once the page plants him) |
| 1. sit-down landing (thigh vs the cushion front) | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): Stand_To_Sit in the room |
| 2. rising (calf under the cushion edge) | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): Sit_To_Stand in the room |
| 3. first step away (calf through the chair base) | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): Sit_To_Stand + the walk in the room; no Mixamo walk capture exists |
| the seat-point sweeps (SEAT_AT) | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): the room's chair |
| the chair-ride distances for the rare events | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): the room's desk |
| the mouse-mode body (Seated_Idle vs Typing) with G14's resolver | PENDING | needs room.html playing this character (a ?char=mixamo switch in pickRig / V5, G10d's): the page's resolver |
