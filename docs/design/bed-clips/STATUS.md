# Bed clips: status (G17)

The full write-up, with the per-frame contact table, sheets and videos, is [README.md](README.md). Raw contact passes are in [contact/](contact/).

## Done

- Laying_Nodding (lying awake with the music, the headphones on the Head bone), Laying_Sleeping (the sleep loop) and the turn onto his side and back (`room_sleep_turn`) are fitted to the 1.90 m bed and wired into `boy_mh.js`.
- The turn is a rare event in his sleep. It starts at the loop's wrap and ends on the loop's first frame (0.11° off), with his lowest skin held, so nothing steps.
- **One command re-bakes all three**: `room_build/kimodo/bed_rebake.sh <character.glb>`. It covers the v5 rig and a Mixamo-named rig; the Mixamo branch still has to be verified on the real character.
- `contact_pass.mjs` measures the bed rows of docs/qa/contact.md on every frame, plus a join "jump" row.

## Loops against the contract

| row | contract | listen | sleep |
|---|---|---|---|
| head on the pillow (cm) | −2 … 0 | −1.4 … −0.9 | −1.8 … −0.5 |
| toes inside the mattress end (cm) | > 0 | 4.1 | 4.2 |
| bed / bed frame / floor | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| hands in his own body | 0 | 0 | 0 |
| duvet through him | 0 | – | 0 |

## Open

These fail, and are stated in README "Open":
- **Back**: his back touches only from the small of the back to the mid back. The buttocks just past the hip joint are +3…+4.4 cm up, and the shoulder blades at the pillow's edge +1.6…+2.8 cm.
- **Headphones** (G10d's fit): up to 2.9 cm into his hair, and 0.5 cm under the pillow's surface in 26 of 87 frames.
- **Turn**:
  - a hand by his face, 4.7 cm into his head;
  - mid-roll, his head 3.2 cm into the pillow;
  - the duvet a 28–31 cm tent over his rising arm.
- **Joins**: one fixed here (the arrival into sleep). Three are the page's and identical on the base:
  - 44 cm in the first frame of getting up from the music (the base's step jumps 29.5 cm there);
  - his legs in the mattress during the lie-down;
  - a 1.27 m jump at the bed's edge.
