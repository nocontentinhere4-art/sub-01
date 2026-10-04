# SUB-01 film for X (v2)

`sub01_x_film.mp4` (not in git: ~30 MB, built locally): 29.6 s, 1080×1350 (4:5, the X mobile frame), H.264 + AAC.

The model for it is the format that took Eon Systems' fruit-fly emulation to 120M+ impressions on X (March 2026):
real footage, the body doing things next to its brain lighting up, one line of text. Not slides.

| time | what |
|---|---|
| 0–2.4 s | hook: the real fibres (923k traced from the MRI), zoom out. "We turned a real human MRI into a brain model." (the first frame carries the whole first line: it is the thumbnail) |
| 2.4–5 s | "Then we gave it a body." the room, dolly in on him at the desk |
| 5–20 s | split screen, one day: room on top, his brain model under it with the clock and the AWAKE / DEEP SLEEP / REM chip. Wakes 07:54, desk 14:02, ramen 19:10, window 19:41, phone in bed 23:18, asleep 23:56, REM 04:12 |
| 20–24.4 s | time-lapse 06:00 → 01:00, the brain in a circle, "Every day. 24/7. Nobody controls him." |
| 24.4–29.6 s | "It's a model. Not a mind." then SUB–01 · watch him live · soon |

All footage is the project's own: the room is `web/room.html` rendered frame by frame on a RunPod RTX A5000 by
`tools/gpu_preview_render.py` (shot lists `shots.json`, `shots_bed.json`, pod script `film_job.sh`; two runs,
~$0.04 together, tagged `gpu-preview-xfilm*` in the ledger). The brain is `brain_film.html`: the brain page's own fibre
and cortex shaders, driven by activity recorded from the running model (`record_act.py`: the demo server for the day,
an accelerated night for NREM and REM). `compose.html` + `compose.js` lay out every frame; `soundtrack2.py`
synthesises the sound to the cuts; `build.sh` encodes.

Wording follows the project rules: no mind or feeling claims, no price talk, the scanned person and the dataset are not
named, "AI · fictional character · simulated brain" stays in the corner.

## Post copy (draft)

> We turned a real human MRI scan into a brain model and gave it a body.
>
> It lives in a tiny room in Tokyo. Nobody controls him: it wakes, reads, eats, scrolls and sleeps when its brain
> model says so. At night, REM sleep replays the day.
>
> It's a model, not a mind. Live soon.

First reply (keeps the main post clean): how it works in 3 lines + the link once the site is public.
