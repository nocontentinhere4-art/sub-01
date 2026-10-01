# Body (twin/body.py)

A minimal body for a digital twin model of one real person's brain structure and recorded activity; not a mind, not
conscious, not the person. It gives the brain model a heart rate, breathing, blood glucose and hunger so that the
simulated life has a physiological reason to eat. The parameters are generic textbook adult values; nothing is fitted
to the recorded person and no body data from the dataset is used.

## Equations

**Autonomic balance and heart rate.** Sympathetic tone S and vagal tone V (both 0..1) relax to targets with time
constants 20 s (sympathetic, slow) and 5 s (vagal, fast) (Berger et al. 1989, Am J Physiol):

    S* = clip(S_stage + 0.30 (NE - 1) + 0.30 amygdala + 0.35 exertion + 0.3 hypo, 0, 1)
    V* = clip(V_stage - 0.6 (S* - S_stage), 0, 1)
    HR = HR_int - 45 V + 70 S + noise,     HR_int = 95 bpm

The additive sympatho-vagal form follows Berntson et al. (1991, Psychol Rev; 1993, Psychophysiology); the intrinsic rate
118.1 - 0.57 age (Jose and Collison 1970, Cardiovasc Res) gives ~95 bpm at 40 y. `hypo = max(0, (70-G)/20)` is a small
sympathoadrenal counter-regulation. Stage tone (S, V): awake (0.15, 0.75), NREM (0.04, 0.93), REM (0.20, 0.72)
(qualitative pattern: Somers et al. 1993 NEJM; Trinder et al. 2001 Psychophysiology). `NE` is the neuromodulator level
(1.0 = resting wake) and `amygdala` the activity excess over rest (0 = baseline), both supplied by the caller.
`noise` is an Ornstein-Uhlenbeck process (tau 30 s) with sd 1.5 (awake), 0.8 (NREM), 3.5 (REM) bpm.

**Breathing.** rate = base(stage) + 9 (S - S_stage) + noise; base 14.5 (awake), 12.0 (NREM), 14.5 (REM) per min, sd
1.0 / 0.35 / 2.2 (slow, regular in NREM, irregular in REM; Douglas et al. 1982 Am Rev Respir Dis; Gould et al. 1988),
clipped 6-35.

**Glucose.** Bergman minimal model (Bergman et al. 1979, Am J Physiol) with a two-compartment gut (stomach -> gut ->
plasma, Dalla Man et al. 2006, IEEE Trans Biomed Eng):

    dQsto/dt = -kgri Qsto;   dQgut/dt = kgri Qsto - kabs Qgut        (kgri 0.056, kabs 0.057 /min)
    Ra = F kabs Qgut / (BW Vg)                                         (mg/dl/min; BW 70 kg, Vg 1.88 dl/kg)
    dG/dt = -p1 (G - Gset) - X G - kex * exertion * G + Ra             (p1 0.03 /min)
    dX/dt = -p2 X + p3 (I - Ib)                                        (p2 0.02 /min, p3 2e-5)
    dI/dt = -n (I - Ib) + gamma max(G - Gset, 0)                       (n 0.27 /min, gamma 0.03, Ib 8 uU/ml)

Euler steps of <= 60 s. `F = 0.45` is the net fraction reaching plasma (0.9 absorbed minus first-pass splanchnic
uptake) and `p3`, `gamma` were tuned by hand to give a realistic mixed-meal curve; they are not literature values.
`Gset`, the fasting set-point, drifts from 88 toward 72 mg/dl with a 9 h time constant after the last meal (a
phenomenological stand-in for hepatic glycogen depletion; real fasting glucose is defended much more tightly).

Results (default parameters): 30 g carbohydrate -> peak 127 mg/dl at 40 min, 89 at 2 h, 83 at 3 h; 60 g -> peak ~160;
75 g -> peak 185 (too high compared with a healthy OGTT of ~140-160; the model is kept for typical meals of 30-60 g).
A 24 h loop with three meals stays between ~70 and ~160 mg/dl.

**Hunger (0..1).** `0.6 * ghrelin_proxy + 0.4 * clip((100 - G)/30, 0, 1)`. The proxy relaxes toward 1 with tau 5 h and
is multiplied by exp(-carbs/35 g) at each meal (pre-meal rise and post-meal fall of ghrelin: Cummings et al. 2001,
Diabetes). Real hunger is mostly hormonal, habitual and cue-driven, not a glucose threshold; glucose only contributes
the smaller term here, and the proxy is a stand-in for the whole gut/hormone signal.

**Interoceptive drive.** `intero_drive()` returns `{"insula": amount}` (empty when fed and calm) =
2.0 * low-glucose (G < 85) + 1.0 * high HR (> 80 bpm) + 0.5 * hunger above 0.4, in `brain.stimulate` units. The group
`insula` (new in `brain_sim.GROUPS`) is the 8 `SalVentAttn_FrOperIns` Schaefer parcels, a frontal operculum / anterior
insula proxy (Craig 2002, Nat Rev Neurosci). The atlas (Schaefer-200 + 14 Harvard-Oxford subcortical) has no
hypothalamus, so there is no hypothalamic input; the amounts are choices, not fitted.

## Life integration
`Life(state, rng, body=None)`: `hunger` is now a read-only property of the body (the old +1/5 h rule and the -0.6 per
meal rule are removed). Eating one piece of bread calls `body.eat(30)` (`CARBS_PER_BREAD_G`: a ~60 g roll at ~50 %
carbohydrate, USDA FoodData Central). With an external `body`, its owner (live_server) must step it with
`body.update(dt_sim, levels, amygdala, stage, exertion=life.exertion())`; without one, Life makes its own body, steps it,
and saves it in `to_dict()["body"]` (a legacy save with only `hunger` seeds the ghrelin proxy). Snapshot keys are
unchanged. `update(..., levels=None, amygdala=0.0)` pass the neuromodulators to an owned body.

Interface additions to the contract: `Body.update(..., exertion=0.0)`, `Body(state, rng=None)`, `Body.from_dict`,
`brain_sim.GROUPS["insula"]`, `Life(body=)`. `Dockerfile` now copies `twin/` (life.py imports it).
Wiring still to do in live_server: create one Body, persist it, step it, pass `max(0, rel["fear"] - 1)` as
`amygdala`, call `brain.stimulate("insula", v)` for `intero_drive()`.

## Not realistic
- No hormones (insulin is a single lumped state; no glucagon, cortisol, leptin, real ghrelin), no liver/kidney, no fat
  or protein digestion; every meal is pure carbohydrate with the same absorption.
- No diabetes, no glucose-lowering drugs, no exercise beyond a crude uptake term; one fixed 70 kg body.
- Heart rate: no baroreflex, no respiratory sinus arrhythmia or beat-level HRV, no circadian HR, no blood pressure;
  the variability is generic coloured noise. REM mean HR comes out slightly above resting wake; real REM is similar to
  or a little above NREM with large surges.
- Breathing is a rate only (no depth, apnoea, CO2 chemoreflex).
- The brain feedback (insula drive) and every gain are design choices.
- Data and licences: no external data. All numbers are from the cited papers or hand-tuned.

## References
Bergman et al. 1979 Am J Physiol 236:E667; Dalla Man et al. 2006 IEEE Trans Biomed Eng 53:1794 and 2007 53:1740;
Berntson et al. 1991 Psychol Rev 98:459; Berntson et al. 1993 Psychophysiology 30:183; Berger et al. 1989 Am J Physiol
256:H142; Jose and Collison 1970 Cardiovasc Res 4:160; Somers et al. 1993 NEJM 328:303; Trinder et al. 2001
Psychophysiology 38:232 (autonomic activity across sleep); Douglas et al. 1982 Am Rev Respir Dis 125:286; Gould et al. 1988 Am Rev
Respir Dis 138:874; Cummings et al. 2001 Diabetes 50:1714; Craig 2002 Nat Rev Neurosci 3:655.
