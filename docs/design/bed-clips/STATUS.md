# Bed clips: status (G17)

Re-measured on **main's character** (0ac47f8). The full write-up, with the tables, sheets and open items, is [README.md](README.md); the raw passes are in [contact/](contact/).

## Done, in C's order

1. Merged `origin/main`; `char_v5.glb` is main's.
2. `contacts()` and `penetration()` take his body mesh by name. The page's slides code is not used on v5: boy_mh.js parks the `slides` mesh.
3. `bed_rebake.sh` on main's GLB. The fit now sees every skinned part (`bed_exp.mjs`), including the socks.
4. Re-measured, every frame:

| row | contract | listen | sleep |
|---|---|---|---|
| back, mid / lower back (cm) | −1 … +0.5 | +0.3 … +0.5 | −0.6 … 0 |
| head on the pillow (cm) | −2 … 0 | +2.5 … +3.7 (the hood between) | −1.7 … −0.5 |
| toes inside the mattress end (cm) | > 0 | 3.3 | 3.4 |
| bed / bed frame / floor | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| hands in his own body | 0 | 0 | 0 |
| headphones under the pillow | 0 | 0 | – |

5. Open items, as far as they went:
   - **Side-hold hand in his head**: gone. It was his hand against the hood, which the instrument counted as head. Mid-roll, a hand still passes 8 cm through his face (78 frames).
   - **Duvet tent**: 31 → 25.5 cm over his arm.
   - **Buttocks +3.2…+4.4 cm**: the cause is found (the heel step undoes the pelvic tilt); not fixed.
   - **Cups in his hair**: 1.9 cm, against 1.8 cm on the base pose.
   - **Headphones round the neck through the hood**: fixed. His head is turned back from 57° to 9°.
   - **The page's jumps**: getting up from the music, 44 → 26.8 cm in a frame; the 1.27 m jump at the bed's edge is the page's and untouched.

Visual gate: see the final report for this push.
