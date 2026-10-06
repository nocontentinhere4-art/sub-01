# Breath (v5), from a recorded human respiration signal

For G10d's continuous additive breathing layer, under every clip.

- `breath_curve_b004.json`: a 58.8 s seamless loop at 30 fps (1765 values).
  - 0 = end of expiration (the loop starts and ends there); 1 = this subject's median tidal breath depth.
  - 14 breaths in the loop, 14.7/min, interval CV 14 %, depth 0.36-0.97 per breath, inspiration ~1/3 of each cycle.
  - It keeps the person's own irregularity; nothing is metronomic.
- `breath_v5.glb`: the same curve as a small v5 clip.
  - Six rotation tracks in v5 names: Spine01, Spine02, NeckTwist01, Head, L_Clavicle, R_Clavicle. char_v5.js's fixClip renames them.
  - Frame 0 is exactly the rest pose: make it additive with `THREE.AnimationUtils.makeClipAdditive(clip, 0)`.
  - Measured on v5 at a median breath: shoulders (upper arm heads) +3.0 mm up, upper chest 0.3 mm, head 1.2 mm (the neck counter-turns so the head stays put).
  - Loop seam: 0.0 deg on every bone. Built by `tools/motion/breathclip.mjs`.

## Source (measured data, not keyed)
- **Signal:** PhysioNet **CEBSDB v1.0.0**, *Combined measurement of ECG, Breathing and Seismocardiograms*.
  - Record **b004**, channel RESP (thoracic piezoresistive band), a healthy volunteer at rest, 5 kHz.
  - Resampled to 30 Hz, drift removed, one trough-to-trough stretch of ~59 s, closed with a 1 s cross-fade.
  - Open Access; licence **Open Data Commons Attribution License v1.0** (ODC-By 1.0).
  - Attribution, as the PhysioNet page asks: García-González MA, Argelagós-Palau A, Fernández-Chimeno M, Ramos-Castro J.
    *A comparison of heartbeat detectors for the seismocardiogram.* Computing in Cardiology Conference (CinC), 2013.
    And the standard PhysioNet citation: Pollard T, Moody BE, Lehman L, Gow B, Fernandes C, Xie C, Johnson A, Mark RG,
    Heldt T. *PhysioNet as a global platform for biomedical research.* Nature Health (2026),
    https://doi.org/10.1038/s44360-026-00096-z. Dataset: https://physionet.org/content/cebsdb/1.0.0/ (DOI 10.13026/C2KW23).
  - Chosen over b001-b006 for the calmest rate (14.6/min at rest; b001 21.5, b002/b003/b005 ~16.5, b006 14.4 but CV 32 %).
- **Amplitude:** De Groote A, Wantier M, Chéron G, Estenne M, Paiva M. *Chest wall motion during tidal breathing.*
  J Appl Physiol 1997; 83(5):1531-1537.
  - Seated subjects; at the sternum the inspiratory displacement is mainly cranial and ventral, 3-5 mm, and laterally 1-2 mm.
  - v5's skin has no rib-cage expansion, so the cranial part is carried by the clavicles (3.0 mm up), and a 0.65 deg
    thoracic extension adds the small chest motion.
