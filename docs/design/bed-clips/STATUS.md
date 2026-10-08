# Bed clips: status (G17)

Measured on **main's character** (0ac47f8, the hood with its lining), every frame. The full write-up is [README.md](README.md). The raw passes are in [contact/](contact/), and the sheet is [owner.jpg](owner.jpg): side views before (0d8bac0) and after, the duvet, and six page-camera frames each of LISTEN and SLEEP.

## C #8

**1. He floats (buttocks): fixed with (a) + (b) together.**

| | C's pass | before (0d8bac0) | listen | sleep |
|---|---|---|---|---|
| buttocks (just past the hip joint) | ≤ +1 cm | +3.2 … +4.4 | +0.9 | +0.9 |
| back, lowest | ≥ −2.5 cm | −0.6 | −2.1 | −2.4 |
| hand in his face | none | – | 0 | 0 |
| head on the pillow (as before) | −2 … 0 | −1.7 … −0.5 asleep | −1.7 … −0.5 | −1.7 … −0.4 |
| bed (less its give) / bed frame / floor | 0 | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| toes inside the mattress end | ≤ 3.5 cm | 3.3 / 3.4 | 0.8 | 0.8 |

- **(a) Mattress sink.** The page rests his lowest skin, now his back, under the bed's top by `BED_SINK` (boy_mh.js): 1.8 cm awake on the quilt, 0.65 cm asleep. The fit sinks his back and hips 2.0 cm and 1.65 cm, and fits his heels and head for that height, so his legs and head stay where they were. It applies to the mattress only: the head is fitted against the pillow as before, and nothing goes into the bed frame or the floor.
- **(b) Flatter legs.** The hips and knees are blended 100% toward straight; 40–70% was not enough. His heels stay on the bed, and his toes come to 0.8 cm inside the end (C: ≤ 3.5). Two fixes came with it. The heel step had counted his buttocks among his legs, so it could not set the heels above his back. And asleep, his heels sit 0.6 cm higher (`heel_up`), so his calves stay within the mattress's 2 cm give.
- The pillow step now fits his head itself, not the hood (as the contact pass measures). With his neck straighter, the hood had touched the pillow first and his skull rode 2–7 cm over it.
- The turn (17.4 s): his face stays clear (0); up to 2.7 cm of a hand in his chest on 30 frames; his back at −2.6 cm at most, mid-roll; head −2.1 … +0.4.

**2. Duvet hump in SLEEP: smaller, ≤ 15 cm not reachable.** Over his legs the duvet's top is now 24.3–30.2 cm above the mattress (shins to thighs), against 25–35 before. Next to his hips it is 32–40 cm, where it comes down from his torso. The tent over his knees is gone because his knees lie flat. The cloth drapes tighter (bridging 12/8 → 6/4 cm) and is thinner (5 → 3.5 cm), and nothing of him comes through it. But his legs themselves are 19–26 cm deep lying down (v5's baggy track pants), so a top ≤ 15 cm above the mattress would have to go through them. The leg profile is in `contact/contact_sleep.json` (`legs_top_by_cm_from_headboard`, `legs_skin_top_by_cm`).

**#6 (unchanged, as C decided)**: the cups stay at 0.2 cm in his hair, and the 1 cm rim against the hood stays.

The page's own bed check (`penetration()`, the visual gate) gives his back and hips 2.5 cm, as C #8 allows. Everything else keeps 2 cm.

Videos `listen.mp4` and `sleep_turn.mp4` are re-recorded with these clips.
