# life-c: the layers that keep him alive between clips

Two procedural layers in `web/room/boy_mh.js` run over whatever clip is playing:

- **breathing** (`breathe()`): a continuous additive layer;
- **gaze** (`gaze()`): his head turns toward what he looks at. The code is in, but it stays inert until the page's `gaze` hook lands in a later commit, after its own validation.

Neither is hand-authored motion. The breath is a recorded human signal (G14's clip). The gaze's timing and range are measured human values, listed with their sources below. The few numbers that are engineering choices are marked as such.

## Breathing

**Clips:** G14's `web/room/mh_v5/room_breath.glb` (awake) and `room_breath_lie.glb` (asleep). Sources and method are in `docs/design/motion-c/breath/README.md`.
- The signal is PhysioNet CEBSDB b004, a thoracic respiration band on a healthy volunteer at rest. Licence ODC-By 1.0.
- The awake loop is 58.8 s: 14 breaths, 14.7/min, with the person's own irregularity.
- The lying loop is the same signal slowed 1.3× and deepened 1.25×, to 11.3/min. G14 marks this as derived, not measured.

**In the page:**
- **Tracks:** every rotation track of the clip, made additive against its own first frame, which is the rest pose.
  - After `char_v5.js` renames them, these are Spine01, Spine, neck, Head, LeftShoulder and RightShoulder.
  - The head track counter-turns, so the head stays put.
- **Context:**
  - Awake, the awake loop plays at full context weight.
  - Asleep in bed, the lying loop takes over.
  - The two weights cross-fade with a 0.8 s time constant.
- **Clock:** each loop runs on its own clock in `breathe()`. The page stops every action when it snaps him to a place or starts a pose. Before this change, that stopped the breath or sent it back to its start, so a change of clip never restarted a breath.
- **Frame timing:** `breathe()` does not re-evaluate the mixer. Calling `mixer.update(0)` there put back every bone the layers before it had set in that frame: the hand pins, the chair roll and the lift. The page's own `mixer.update(dt)` applies the breath on the next frame, 33 ms late on a breath of about 4 s.

**Depth (calibrated, measured in the page):**
- **Awake:** at full weight on v5 in the room, the upper-arm heads rose **7.5 mm** at a median breath (range 3.4–9.2 mm). G14 designed the clip for **3.0 mm**. De Groote et al. 1997 measure the sternum moving 3–5 mm cranially in tidal breathing.
  - The awake weight is therefore `BR.GA = 0.40`.
  - Measured with it: **2.99 mm** at a median breath (range 1.37–3.69 mm), head 1.1 mm, 14 breaths in the loop (14.3/min).
- **Lying:** `BR.GL = 0.35`, measured as 1.25× the awake depth.
  - Shoulders 3.7 mm at a median breath (range 1.75–4.7 mm), along the body, 11.8/min.
  - In the world over 20 s asleep: head 2.0 mm, shoulders 4.5 mm along the body. With the breath off, both are 0.
- **Open question for G14:** the gains are a calibration of the clip's depth on this body, not a change of its shape or timing. If his standalone 3.0 mm and this 7.5 mm should agree, the clip's amplitude is the place to fix it, and the gains go back to 1.

**Debug:** `window.NOBREATH = true` turns the layer off, for measuring what it does.

## Gaze

**Head timing and range, from measured human values:**
- **Latency:** the head starts **63 ms** after the gaze target changes.
  - Source: Goossens & Van Opstal 1997, *Human eye-head coordination in two dimensions under different sensorimotor conditions*, Exp Brain Res 114:542–560, Table 2, eye–head latency, visual targets, pooled: 63 ± 36 ms.
  - v5 has no eyes, so the head is the gaze.
- **Speed and profile:** a minimum-jerk turn. Its duration is set so that the peak speed matches the measured peak speed of a 30° head turn: **72°/s yaw, 66°/s pitch**.
  - Source: Boulanger et al. 2026, arXiv:2608.17904, median of 62 adults.
  - For a minimum-jerk profile, peak speed = 1.875 · amplitude / duration. The shortest turn is 0.2 s.
- **Range:** head and neck together reach **±77°** of axial rotation, about 155° in all. Source: Ferrario, Sforza et al. 2002, 3D head–neck range of motion.

**Engineering choices (not sourced):**
- `NECK_OK` 45°: past this, the upper spine takes the excess turn.
- `SMALL` 4°: below this, the head eases in, since the eyes alone would cover it.
- The turn is split 40% neck, 60% head.
- Pitch is limited to −40/+30°.

## Measurements

`breath_frames.jpg` has three rows: desk, window and asleep. Each row shows his chest at the end of a breath out, then at the top of the next breath in, then the pixels that changed between them. At the window and in bed the change is a thin band at the shoulders, and the duvet follows his chest. At the desk most of the difference is his own mouse micro-motion, because the camera follows his spine.


The scripts live in the session's scratchpad. They are not part of the test suite.
- The breath depth sweeps the whole loop at a frozen frame of the window and sleeping scenes, mixer only, with the breath on and off.
- The world-space check runs the sleeping scene for 20 s with the breath and 20 s without, in one page.
- The desk scene is not deterministic even with the breath off on both sides (his random micro-motion), so an on/off comparison across page loads means nothing there.
