# Bed clips: status (G17)

Measured on **main's character** (0ac47f8, the hood with its lining from b2593d7), every frame. The full write-up is [README.md](README.md). The raw passes are in [contact/](contact/), and the before/after sheet is [owner.jpg](owner.jpg).

## C #7 and #6

| fix | target | before (0908653) | now |
|---|---|---|---|
| buttocks, just past the hip joint | ≤ +1 cm | +3.2 … +4.4 cm | +3.2 … +4.4 cm: **not met** |
| a hand through his face mid-roll | never | 8 cm, 78 frames | **0** (56 frames moved, up to 20 cm) |
| headphone cups in his hair | ≤ 0.5 cm | 1.9 cm | **0.2 cm** (in bed only: 0.8 cm wider per side; G10d's fit untouched) |
| headphones against the hood | no contact, any frame | standing / desk 0, lying awake ~1.0 cm | standing / desk **0**; lying awake ~1.0 cm at the lower cup's rim: **open** |

- **Buttocks**: the extra pelvis step works on its own, getting them to +2.4…+2.9 cm. But it makes the backs of his thighs his lowest skin, so the page floats his whole back: +1.8…+4.0 cm awake, +0.2…+0.6 cm asleep, with his knees bent 35–50°. It is off by default (`BED_BUTTOCKS=1` turns it on). ≤ +1 cm needs flatter-lying legs than either capture has.
- **Hood, lying awake**: raising the headphones 2.4–2.8 cm clears the hood but puts the cups 0.7–0.8 cm back into his hair. I kept the hair target. C, your call.
- **Hand in his face**: still up to 3 cm of a hand in his chest on 36 frames mid-roll (was 4.3 cm, 64 frames), from the wrist cap.

## The rest (unchanged)

| row | contract | listen | sleep | turn |
|---|---|---|---|---|
| back, mid / lower back (cm) | −1 … +0.5 | +0.3 … +0.5 | −0.6 … 0 | (on his side) |
| head on the pillow (cm) | −2 … 0 | +2.5 … +3.7 (the hood between) | −1.7 … −0.5 | −2.1 … +1.1 |
| toes inside the mattress end (cm) | > 0 | 3.3 | 3.4 | 2.8 |
| bed / bed frame / floor | 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| hands in his own body | 0 | 0 | 0 | chest 3 cm, 36 frames |
| headphones under the pillow | 0 | 0 | – | – |

Videos `listen.mp4` and `sleep_turn.mp4` are re-recorded on main's character with these clips.

Full pytest on this commit's tree: 1450 passed, 27 skipped, exit 0; `tests/visual/out/results.json` hard_failures `[]`.
