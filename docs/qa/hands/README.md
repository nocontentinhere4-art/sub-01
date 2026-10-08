# Natural hand reference (owner, 2026-10-08)

The owner filmed himself at his desk (typing, mouse, resting hands; 61 s, 120 fps) as the reference for natural hands.
**The video stays local and is never committed.** Only derived angles are here:
`owner_hands_ref.json`, from `extract_hands.py` (MediaPipe world landmarks, sampled at 30 fps, 1832 of 1849 frames with hands).

Per hand and finger: flexion at MCP / PIP / DIP (deg, p5 / p50 / p95), side bend out of the finger's flexion plane
(MediaPipe is noisy here: treat ~20-30 deg as the measurement floor, not as real bending), palm spread, and the wrist bend
between forearm and hand. Per frame data under `frames` for timing (how fast fingers move, how often they rest).

Use it as the target range for any hand on the character: a pose outside these ranges, or faster than they ever move,
reads as "twisted".
