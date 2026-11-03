# ARDY clips, third pass: a proposal (#98 G3, no GPU spent yet)

Clips that would add the most life to the room's character, for the owner to choose from. Each is one text prompt to
NVIDIA ARDY (`room_build/ardy/gen.py`, same pod recipe as `specs.json` / `specs_v2.json`: three seeds, the cleanest
sample by foot skating and jitter, optional end-effector pins), retargeted onto `boy.glb` by `room_build/ardy_to_boy.mjs`
and played by the layer in `web/room/boy_motion.js` either as a swapped idle or as a one-shot over the current clip
(`motion.play`). The pod is an RTX A5000 on RunPod through `analysis/runpod_job.py` (one pod at a time, deleted at
the end, every minute in the ledger).

## Cost basis (the four runs so far)

| run | minutes | USD | what |
|---|---|---|---|
| 1–2 | 4.2 + 6.6 | 0.049 | bootstrap fixes (the gated encoder's shards, a bool export) |
| 3 | 7.0 | 0.032 | all 14 clips of `specs.json`, 3 seeds each |
| 4 | 7.0 | 0.031 | the 7 clips of `specs_v2.json`, up to 6 seeds each |

So one pod run costs about 7 minutes (≈ 5 of them the bootstrap: clone, pip, 6 GB of encoder shards and the checkpoint;
the generation itself is ~8 s per clip and seed on an A5000) for about $0.03. The whole list below fits in **one run
of roughly 9 pod-minutes, ≈ $0.04**; run one clip at a time it would still be ≈ $0.03 each (the bootstrap dominates).
Spent so far: $0.112 of the $10 cap.

## The clips

| # | clip | where it plays | prompt | seeds | est. pod-min (alone / in the batch) |
|---|---|---|---|---|---|
| 1 | **drink from a bottle** | at the desk (research, chat), standing by the fridge | *A person stands relaxed, raises their right hand to their mouth as if drinking from a bottle, tips the head back a little, drinks for a few seconds, then lowers the hand back to the side.* Pins: the right hand's height during the drink. A seated variant: *A person sitting on a chair at a desk lifts a bottle in the right hand to the mouth, drinks, and puts it back on the desk.* | 3 + 3 | 6.0 / 0.7 |
| 2 | **drink from a mug** | at the desk, morning | *A person sitting at a desk picks up a mug with the right hand, brings it to the mouth with both hands, sips slowly, and sets it down.* | 3 | 5.6 / 0.4 |
| 3 | **stretch** (standing and seated) | the stand / sill interludes (today keyed by the page), at the desk after a long sit | *A person standing still stretches both arms up over the head, arches the back a little, holds the stretch, and relaxes.* / *A person sitting on a chair leans back, stretches both arms up and out, holds for a moment, and relaxes back to sitting.* | 3 + 3 | 6.0 / 0.7 |
| 4 | **pick up the phone** | the desk (phone_sit), the bed's edge | *A person sitting on a chair reaches down and forward with the right hand, picks up a phone from the desk, brings it up in front of the chest, and looks at it.* Pins: the right hand at the desk top at the pick-up frame. | 3 | 5.6 / 0.4 |
| 5 | **yawn** | late evening at the desk, in bed before sleep (sitting on the edge) | *A person sitting on a chair yawns: the head tips back, the mouth opens, one hand comes up to cover the mouth, the shoulders rise and drop, then they settle.* (no face bones on the rig: the head, hand and shoulders carry it) | 3 | 5.6 / 0.4 |
| 6 | **look around** | standing idle, the window, waiting at the door | *A person standing relaxed looks around the room slowly: turns the head to the left, pauses, to the right, pauses, glances up, and faces forward again.* The layer's eyes follow the head. | 3 | 5.6 / 0.4 |
| 7 | **sit back** | at the desk after typing (the `lean` interlude, today keyed) | *A person sitting at a desk stops typing, leans back in the chair, lets the arms rest on the lap, looks at the screen for a while, then sits forward again.* Pins: the hips held on the seat. | 3 | 5.6 / 0.4 |
| 8 | **scratch the head** (optional) | any idle | *A person standing relaxed raises the right hand and scratches the back of the head for a couple of seconds, then lowers the arm.* | 3 | 5.6 / 0.4 |

"Alone" is one pod run for that clip (the bootstrap and ~0.4 min of generation); "in the batch" is the clip's share of a
single run of all of them: **≈ 9 minutes, ≈ $0.04** for the eight (fourteen prompts × three seeds, about 2 minutes of
generation after a 5-minute bootstrap, plus the export).

## What each brings, and what it costs at runtime

- Every clip is a rotation-only GLB of 15–60 KB (the existing ones: 13–61 KB); eight more add ≈ 300 KB to the room's
  motion assets and nothing to the frame time (one more clip action each).
- Drinking and the phone pick-up need the prop to follow the hand: the layer already holds the bowl in the left hand
  while eating; the same code holds a bottle, a mug or the phone in the right hand.
- The stretch and the look-around replace interludes the page keys today, so they also remove two authored poses that
  were tuned for the first clips (the stretch beside the desk is where the hand went into the chair).
- The ARDY licence point is unchanged: the clips are the model's outputs (NVIDIA Open Model License: no ownership
  claimed on outputs, commercial use allowed); the Llama text encoder stays offline on the pod.

## If the owner picks a subset

Any subset is one run (bootstrap-dominated): 1 clip ≈ 6 pod-min / $0.03, 4 clips ≈ 7 / $0.03, all 8 ≈ 9 / $0.04. Add
the chosen prompts to a `specs_v3.json` next to `specs.json`, run `job.sh` through `analysis/runpod_job.py`, then
`node room_build/ardy_to_boy.mjs` (see `room_build/ardy/README.md`).
