# Walk scenes (prototype)

A stop on his walks as a 3D Gaussian-splat scene he walks into, instead of only the map and the real walking videos
(`web/walk_feed.json`). First stop: the bakery. Page: `/walk_scene.html?scene=bakery` (not linked from the room; nothing
on the live site changes until the owner approves the previews).

Plan, from the Lyra evaluation (project thread "Lyra per le strade fuori casa", 2026-10-04): the way there stays map +
video; three or four short stops (bakery, a bench in Inokashira Park, the crossing by his building) are splat scenes a
few metres deep. Lyra 2 is not usable (NVIDIA internal research-only model licence); Lyra 1 is (NVIDIA Open Model
License, commercial use allowed). World Labs Marble is the fallback if Lyra 1's quality is not enough.

## Files
- `web/walk_scene.html`: three.js r180 + [Spark](https://github.com/sparkjsdev/spark) 2.3.1 (MIT) for the splats; the
  room's rig (`room/boy.glb`) with its ARDY walk and idle clips; a follow camera; a soft contact shadow (splats cannot
  receive a shadow map). `?free` orbit camera, `?grid` a 1 m grid on the street (tuning), `?t=<s>` frozen frame.
- `web/walk/<scene>.json`: the splat file, its frame (`opencv` for Lyra) / scale / offset so the street is y = 0, his
  path, where he faces on arrival, camera and light for him.
- `web/walk/bakery_placeholder.spz`: a crude stand-in street (`placeholder.py`) in Lyra's frame and scale, so the page,
  the path and the camera could be built before the real scene exists. Replaced by `bakery.spz` after the Lyra run.
- `lyra/job.sh`: the pod script. `scenes/bakery/`: the input image and prompt.

## Make the real scene (needs network access to RunPod and Hugging Face)
The input image: Higgsfield `gpt_image_2_5`, 16:9, prompt in `scenes/bakery/prompt.txt` (0.25 credits, 2026-10-04).
Lyra wants an eye-level photo with clear depth; save it as `scenes/bakery/input.png`.

    python analysis/runpod_job.py --kind h100 --wait-min 20 --disk 200 --max-min 60 \
        --image pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel \
        --script walk_scenes/lyra/job.sh --upload walk_scenes/scenes/bakery/input.png \
        --fetch lyra_out.tar.gz stages.txt download.log imports.txt gpu.txt --dest data/walk/bakery --tag lyra-bakery
    tar xzf data/walk/bakery/lyra_out.tar.gz -C data/walk/bakery
    npx @playcanvas/splat-transform --spz-version 3 -w data/walk/bakery/lyra/<...>/gaussians_orig/gaussians_0.ply \
        -N -F web/walk/bakery.spz      # drop NaNs and floaters; Spark 2.3 reads SPZ v3 (v4 fails: "Invalid gzip header")

Then set `"splat": "walk/bakery.spz"` in `web/walk/bakery.json`, open `?scene=bakery&free&grid`, and fix `scale` /
`offset` until the street lies on the grid and a door is ~2 m tall; then the path. The runner logs the pod's cost to
`data/analysis/costs.jsonl` (RunPod H100 ~ $2.4-3/h; one run is expected to fit in its 60-minute limit: set-up ~25-35
min of pip builds while ~50 GB of weights download, then 6 x 121-frame Cosmos 7B trajectories and the 3DGS decoder).
`stages.txt` has each stage's start time, for the case where the set-up does not fit: then the next step is a network
volume holding the environment and weights (the runner has no volume support yet).

## Budgets (the room's, as a guide)
- Phone: ~0.5 M splats or fewer per scene (estimate, to be measured on the real scene), file ~5-10 MB as .spz.
- The page keeps the room's DPR cap (1.5) and draws no shadow maps.

## Credits
Lyra (NVIDIA, code Apache-2.0, models NVIDIA Open Model License), GEN3C / Cosmos-Predict1 (NVIDIA Open Model License),
T5 (Apache-2.0), MoGe (MIT), Spark (MIT, World Labs), splat-transform (MIT, PlayCanvas). The input image is generated
(Higgsfield), not a photo of a real shop.
