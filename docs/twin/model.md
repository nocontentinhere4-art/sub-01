# Neural mass model (`twin/model.py`)

SUB-01 v2 is a digital twin model of one real person's brain structure and recorded activity (MyConnectome,
OpenNeuro ds000031). It is not a mind, not conscious and not the person. This section covers the simulated part:
the population dynamics that run on the person's connectome, and the BOLD signal computed from them.

`TwinBrain` replaces the old Stuart-Landau model (`brain_sim.Brain`, unchanged) behind the same interface.
`brain_sim.make_brain(kind)` builds either model. The environment variable `SUB01_MODEL` picks the default, which is
`twin`. `live_server.py` still calls `Brain()` directly, so whoever integrates the branches must switch it to
`make_brain()`. All numbers below come from `python -m twin.bench_model`, run on 1 BLAS thread in the build sandbox,
and are stored in `twin/data/model_bench.json`.

## Choice of model

I compared two published models, both with excitatory and inhibitory populations:

| | Wilson-Cowan with inhibitory plasticity (Abeysuriya et al. 2018) | Reduced Wong-Wang E-I with feedback inhibition control (Deco et al. 2014) |
|---|---|---|
| state per region | E, I (+ adaptation A here) | S_E, S_I |
| fastest time constant | tau_E = 10 ms, so dt = 1 ms works with Heun | tau_GABA = 10 ms, so a similar dt |
| intrinsic rhythm | yes: noise-driven alpha/beta near a Hopf point | no: noisy fixed point |
| BOLD fitting | used for MEG; Hellyer 2016 used it for BOLD | standard for BOLD functional connectivity (FC) |
| sleep slow waves | adaptation added: up/down states | needs extra currents |

I chose Wilson-Cowan for three reasons:
- It costs about the same per step as Wong-Wang.
- It produces the oscillating signal the live page draws (`wave`).
- Adding an adaptation current to the same equations gives NREM slow oscillations, so one model covers wake and sleep.

Wong-Wang would have been the more standard choice for fitting BOLD FC. It remains an option for the fit branch.

## Equations

For region k (k = 1..214), with E_k the excitatory rate, I_k the inhibitory rate and A_k the adaptation variable,
all normalised to 0..1:

```
tau_E dE_k/dt = -E_k + S_E( c_EE E_k + c_IE,k I_k - b_A A_k + P + p_k + h_k + dP(a)
                           + G sum_j W_kj E_j(t - L_kj / v) + gate(a) u_k(t) ) + tau_E sigma xi_k(t)
tau_I dI_k/dt = -I_k + S_I( c_EI E_k + c_II I_k + Q )
tau_A dA_k/dt = -A_k + E_k
S(x)          = 1 / (1 + exp(-beta g_k (x - theta)))
```

Where the terms come from:
- **E and I equations:** Wilson & Cowan (1972), in the whole-brain form of Abeysuriya et al. (2018). The model has
  delayed long-range E->E coupling and local E/I populations. Differences from Abeysuriya et al. (2018), all chosen
  here and not taken from that paper: (1) the I->I self-coupling c_II = -1 (their Eq. 2 is
  tau_I dI/dt = -I + S(c_EI E + noise), with no c_II and no Q; Wilson & Cowan 1972 do contain I->I); (2) the
  adaptation variable A; (3) the gain, excitability offset and external-input gate; (4) the noise, which is added
  to dE (sigma sqrt(dt) N(0,1) per step) and only to E, whereas they add Gaussian input noise inside the sigmoid to
  both populations; (5) rho = 0.14 instead of 0.15; (6) stochastic Heun instead of 4th-order Runge-Kutta.
- **Adaptation A:** spike-frequency adaptation as a slow negative feedback on E. It is the standard mechanism for
  up/down-state slow oscillations; Cakan et al. (2022) used it in a whole-brain sleep model.
- **g_k:** the `set_gain` vector, a per-region gain on the slope of the sigmoid (neural gain; Eldar et al. 2013).
  1 is the fitted baseline, so `set_gain(ones)` changes nothing (this is tested bit for bit).
- **Integration:** stochastic Heun with additive noise (sigma sqrt(dt) N(0,1) added to E each step), dt = 1 ms.
  Every conduction delay is at least one step, so the delayed input is fixed within a step.
  - Explicit Euler at dt = 1 ms inflated the E standard deviation by about 20 %, because it adds artificial growth to
    the about 18 Hz oscillation. Heun at 1 ms matches Heun at 0.5 ms: mean E 0.122 vs 0.122, SD 0.051 vs 0.052,
    same peak frequency. `test_heun_step_size_converged` checks this.
  - E is clipped to [0, 1].

**Inhibitory balance.** c_IE,k is computed so that each region's deterministic fixed point is at E = rho. This is the
fixed point that the inhibitory synaptic plasticity rule of Vogels et al. (2011), dc_IE/dt = -eta I (E - rho), would
reach without fluctuations. Hellyer et al. (2016) and Abeysuriya et al. (2018) use this rule. I solve it analytically,
so construction has no warm-up cost:

```
I* = S(c_EI rho + c_II I* + Q)          (bisection)
x* = theta + ln(rho / (1 - rho)) / beta
c_IE,k = (x* - c_EE rho - P - p_k - isp_frac G rho sum_j W_kj + b_wake rho) / I*      (clipped to <= 0)
h_k = -(1 - isp_frac) G rho sum_j W_kj    (homeostatic intrinsic offset; 0 by default)
```

With noise and oscillation the time-averaged rate settles about 12 % below rho: mean E is 0.123 instead of 0.14, and
every region stays within 0.03 of it. Simulating the plasticity rule itself (`isp_refine()`, or the `isp_seconds`
parameter) only reaches 0.128. The reason is that the rule's real fixed point is <I (E - rho)> = 0, not <E> = rho, and
E and I covary during the oscillation. A fit can store a refined `c_ie` vector in `params.json`.

I first tried `isp_frac = 0`, which balances the network input through the intrinsic offset instead. That makes the
network's slow mode easier to push towards instability, but it was bistable in the awake state. 20 s of heavy
stimulation left it stuck in a high-activity state (E about 0.45). With `isp_frac = 1` it recovers within 4 s
(E 0.123 -> 0.31 during stimulation -> 0.128 after 8 s). So the default is the full inhibitory-plasticity balance.

## Parameters

| symbol | key | value | unit | source |
|---|---|---|---|---|
| tau_E, tau_I | tau_e, tau_i | 0.010, 0.020 | s | Abeysuriya et al. 2018 (Table 1) |
| c_EE, c_EI | c_ee, c_ei | 3.5, 3.75 | - | Abeysuriya et al. 2018 (Table 1) |
| c_II | c_ii | -1 | - | chosen here, not in Abeysuriya et al. 2018 (see below) |
| P | P | 0.31 | input units | Abeysuriya et al. 2018 (Table 1) |
| Q | Q | 0 | input units | not in Abeysuriya et al. 2018 (no I input there) |
| beta, theta | beta, theta | 4, 1 | - | Abeysuriya et al. 2018 (Table 1 has mu = 1, sigma = 0.25, so beta = 1/sigma = 4) |
| rho | rho | 0.14 | rate (0..1) | 0.15 in Abeysuriya et al. 2018; see below |
| G | G | 3.0 | - | pre-fit default; fitted later |
| v | velocity | 6 | m/s | as brain_sim; typical 5-10 m/s; fitted later |
| sigma | noise | 0.06 | rate / sqrt(s) | chosen (see Defaults) |
| tau_A | tau_a | 0.25 | s | chosen: about 1 Hz up/down cycle |
| b_A awake / deep NREM | b_wake, b_nrem | 0 / 3.0 | - | chosen (sleep mapping) |
| dP deep NREM | p_nrem | -0.15 | input units | chosen (sleep mapping) |
| external gate deep NREM | gate_nrem | 0.5 | - | chosen (thalamic gating) |
| stimulus gain, saturation, decay | stim_gain, stim_max, stim_tau | 0.08, 20, 2 | input/unit, units, s | chosen; the 2 s decay matches brain_sim |
| drive gain | drive_gain | 0.08 | input per drive unit | same scale as stimuli (both shifted `a` in the old model) |
| dt | dt | 0.001 | s | stability check above |

On the sources:
- **Abeysuriya values (checked by the reviewer against the PLOS Computational Biology full text, Table 1 and
  Eqs. 1-4):** c_EE 3.5, c_EI 3.75, c_IE(0) -2.5, mu 1, sigma 0.25, P 0.31, tau_E 0.01 s, tau_I 0.02 s, rho 0.15.
  The paper has no I->I coupling and no input to I.
  - The reviewer's linear analysis of one isolated node with exactly the paper's equations (c_II = 0, c_IE = -2.5)
    gives a Hopf bifurcation at P = 0.335 (paper: 0.34) and 10-11.3 Hz near it (paper: about 11 Hz), so the
    sigmoid, time constants and signs are implemented as published.
  - **c_II = -1 is an addition made here.** With c_II = 0 and the balanced c_IE the deep-NREM and light-NREM
    settings saturate (mean E 0.99 and 0.51 in a 10 s test) because the sleep engine's coupling x2 / x3 is not
    compensated by inhibition; c_II = -1 keeps all four stages in a usable range. The price is that the awake
    regional rhythm is at about 18 Hz (beta) instead of about 10 Hz (c_II = 0 gave a 10.4 Hz awake rhythm).
  - The model's own isolated-node Hopf point (G = 0, balanced at rho, c_II = -1) is at rho of about 0.138; at
    E = 0.15 the node oscillates at about 9.8 Hz with eigenvalue real part +5/s.
- **Why rho = 0.14:** I set rho to 0.14, just at the Hopf point. Each node is then a noise-driven oscillator with
  waxing and waning amplitude rather than a fixed limit cycle.
- **Changing parameters:** all keys can be overridden by `TwinBrain(params=...)` or by `twin/params.json`, which the
  fit writes. `load_params()` accepts `{"params": {...}}` or a flat dict, plus `excitability` (n,) and `c_ie` (n,).

## Connectome and delays

`out/connectome.npz` holds streamline counts and fibre lengths (mm) from the person's diffusion MRI: 214 regions
(Schaefer-200 + 14 Harvard-Oxford subcortical). All 214 regions are kept.

**Normalisation.** The weights are W = C / sqrt(s_i s_j), where C is the streamline-count matrix (zero diagonal) and
s_i is the row sum of C. The leading eigenvalue is exactly 1, and W stays symmetric. I did not keep brain_sim's
log1p with mean in-strength normalisation for the following reason:
- A linear noise-driven network, FC = norm((I - kW)^-1 (I - kW)^-T), can be compared with the mean recorded FC over
  131 runs (`resting_fc` and `empirical_fc` in the bench).
- With log1p weights the leading mode is dominated by hub regions. At a mean FC of about 0.3, its correlation with the
  recorded FC is 0.07-0.11.
- With raw counts and degree normalisation the correlation is 0.20-0.24, at least as good as the connectome itself:
  r(SC, recorded FC) = 0.215.
- `sc_power` (default 1) lets the fit try counts**p.

**Delays.** Each edge has delay round(L_kj / v / dt) steps, at least 1; with v = 6 m/s the maximum is 60 ms. The
delayed coupling is one sparse matrix-vector product per step:
- The history is a ring buffer of length 2H in which each sample is written twice. The last H samples are then
  always one contiguous view.
- Edge (i <- j) with delay d reads column (H-1-d) n + j of that view. The sparse matrix (20,408 non-zeros) is
  therefore built once.
- Every edge keeps its own delay: there is no delay binning and no per-region Python loop.
- The batched simulator puts B parameter sets, each with its own velocity, into one block matrix.

## Hemodynamics (BOLD)

I use the Balloon-Windkessel model (Buxton et al. 1998; Friston et al. 2000) with the revised BOLD output equation of
Stephan et al. (2007). I copied no code; I checked the values against the SPM12 source (`spm_fx_fmri.m`,
`spm_gx_fmri.m`): kappa = 0.64/s, gamma = 0.32/s, tau = 2 s, alpha = 0.32, E0 = 0.4, V0 = 4 (%), epsilon = 1,
nu0 = 40.3/s, r0 = 25/s, TE = 0.04 s, with k1 = 4.3 nu0 E0 TE, k2 = epsilon r0 E0 TE, k3 = 1 - epsilon.

- **Integration:** the hemodynamic states are integrated in log space (Stephan et al. 2008), every 10 ms, and the
  log states are clipped to [-3, 3].
- **Neural input:** u = 0.25 (E / rho - 1), averaged over the 10 ms. The factor keeps u > -gamma, so blood flow stays
  positive.
- **Field strength:** MyConnectome was scanned at 3 T with TE 30 ms; the 1.5 T constants only scale the amplitude.
- **Impulse response** (u = 1 for 0.5 s): peak at 4.5 s (+1.7 %), undershoot -0.13 % at 12.6 s, back to baseline by
  35 s.
- **Output:** `bold()` returns the current percent signal change.

## Sleep, stimuli, drive and display

| live server input | what it does in the model |
|---|---|
| `b.a` (sleep engine: -5 awake/REM ... 0 deep NREM) | sets depth d = (a + 5) / 5, which scales adaptation b_A = 3 d, excitability dP = -0.15 d and the external gate 1 - 0.5 d (see below) |
| `set_rhythm(f, coupling, noise)` | G = G0 x coupling. sigma = sigma0 x noise / 0.5 (0.5 is the awake noise in sleep.py). f is stored but not imposed: rhythms emerge from the E/I time constants and adaptation |
| `stimulate(group, x)` | adds x to that group's stimulus, which decays with tau = 2 s. Input = 0.08 x 20 tanh(stim / 20) (saturating) |
| `b.drive` (recorded resting signal x 1.6 per z-unit x stage gain) | input = 0.08 x drive (slow excitability) |
| `set_gain(g)` | g_k multiplies the sigmoid slope (neuromodulation) |
| `set_weights(W)` | replaces W (same normalisation as `W0`), keeps the delay history and by default re-solves c_IE at the baseline G (slow homeostasis assumed to have converged); a refined c_IE from `params.json` / `isp_seconds` is kept as an additive correction |

The physiological reasons for the depth mapping:
- **Adaptation b_A = 3 d:** low acetylcholine in NREM unblocks K+ adaptation currents (McCormick 1992).
- **Excitability dP = -0.15 d:** lower cholinergic and noradrenergic tone.
- **External gate 1 - 0.5 d:** the thalamus transmits less sensory input in NREM (Steriade, McCormick & Sejnowski 1993).
- REM has a = -5 in sleep.py, so it is awake-like (high acetylcholine), with the sleep engine's lower coupling and
  higher noise.

**Display.** `step()` returns x = act cos(phi), which is a display signal, not a model variable.
- act = 2 tanh(0.75 (E / rho) / 2): the excitatory rate relative to rest, soft-limited below 2.
- phi is the phase of (E - E_1s) + i k (I - I_1s), where E_1s and I_1s are 1-second running means and k comes from
  the local Jacobian's eigenvector.
- So np.abs(x) follows the firing rate and x.real oscillates with the model's own E/I rhythm.
- `state()` returns group means of act, plus the Kuramoto order parameter of phi as `sync`.

Measured per stage, over 10 s after 3 s of settling (bench `stages`):

| stage | mean E | dominant frequency (region / global mean) | power < 4 Hz | sync | display mean of abs(x) | up-state fraction |
|---|---|---|---|---|---|---|
| AWAKE | 0.123 | 18 / 11 Hz | 1 % | 0.15 | 0.37 | 0 |
| NREM light | 0.115 | 5 / 3 Hz | 8 % | 0.40 | 0.27 | 0.08 |
| NREM deep | 0.331 | 0.9 / 0.9 Hz | 93 % | 0.94 | 0.30 | 0.34 |
| REM | 0.082 | 12 / 9.5 Hz | 5 % | 0.09 | 0.30 | 0 |

Deep NREM gives synchronous slow oscillations of about 0.9 Hz, alternating up and down states (Steriade et al. 1993
describe < 1 Hz). The awake rhythm is beta-range (about 18 Hz at the regional level). In Abeysuriya's model the
frequency may depend on coupling; here it is set by c_II, the balance and the delays, and the fit may move it.

**Reactivity.** A stimulus of 8 units to the reward group, compared over the 0-1 s window (bench `reactivity`,
10 trials):

| stage | specific response (rate change in the group minus the rest of the brain) |
|---|---|
| AWAKE | +0.063 (+51 % of the resting rate) |
| NREM light | +0.043 |
| NREM deep | +0.015 |
| REM | +0.072 |

So the same stimulus gets about a 4 times weaker specific response in deep NREM. In deep NREM, a stimulus mainly
triggers or joins a global up state, consistent with reduced specific propagation in sleep (Massimini et al. 2005).
The live server additionally scales stimuli by the sleep engine's stage gain.

## Batched simulator for the fit

`simulate_bold(params_list, seconds, tr, seed=0, W=None, burn=20, return_rates=False) -> (B, T, n)` float32.
- **Per-set parameters:** each set may have its own G, velocity, noise, excitability (n,) and c_ie (n,). Local constants
  (time constants, couplings, dt) are taken from the first set.
- **Weights:** W may be (n, n) or (B, n, n).
- **State:** awake rest, with no stimuli and no drive.
- **Sampling:** BOLD is sampled every `tr` s after `burn` s.

Throughput on 1 thread:

| batch size | simulated seconds per wall second |
|---|---|
| B = 1 | 12.8 |
| B = 8 | 3.2 per set, 25.6 in total |

`test_batched_matches_single` checks the batched path against the live path: same mean rate (±0.005) and BOLD
standard deviation within a factor of 1.6.

## Real-time budget

Live settings: dt = 1 ms, BOLD on, step(5) x 10 per 50 ms tick, plus `state()`. On 1 thread:

| stage | wall time per simulated second | share of one core |
|---|---|---|
| AWAKE | 0.10 s | 10 % |
| NREM deep | 0.09 s | 9 % |

This is under the 0.3 s (30 %) limit. `test_realtime_budget_single_thread` asserts it.

## Pre-fit defaults and how they compare with the data

**Defaults.** G = 3, v = 6 m/s, sigma = 0.06. I chose them for a regime that is neither saturated nor silent:
- mean E is 0.12 and the regional E standard deviation is 0.05;
- no up states while awake;
- it recovers from heavy stimulation.

**Resting FC.** With no drive, 900 s of simulated BOLD band-passed to 0.01-0.1 Hz (bench `resting_fc`):

| measure | value |
|---|---|
| r(simulated FC, recorded FC averaged over 131 runs) | 0.12 |
| r(connectome, recorded FC), for comparison | 0.215 |
| r(simulated FC, connectome) | 0.36 |
| split-half reliability of the simulated FC | 0.58 |
| mean simulated FC | 0.04 (recorded: 0.34) |
| BOLD standard deviation | 0.015 % (recorded BOLD is about 0.5-1 %) |

So the default model, without the recorded drive, is far from the recorded FC. The fit branch tunes this, and
`twin/params.json` is written by the fit, not here.

**Driven run.** When the recorded resting signal drives the model, as the live server does, the simulated BOLD
correlates r = 0.91 per region with the recording at a 5 s lag (one 300 s run). This only shows that the drive passes
through the model and the hemodynamics intact. The recording is itself the input, so it is not a prediction.

## Data and licences

- **MyConnectome** (OpenNeuro ds000031), public domain (PDDL): the connectome (weights and fibre lengths) and the
  resting-state runs used for the FC comparison and the drive.
- **SPM12:** source read only to check the hemodynamic constants; no code copied.
- **Neurolib, TVB:** looked at for orientation (MIT, GPL); no code copied.
- **Abeysuriya et al. (2018) Table 1:** checked against the open-access full text (see Parameters).

## What is not realistic

- **Regions:**
  - One E and one I population per parcel is a mean-field abstraction. Rates are normalised (0..1) and are not spikes/s.
  - Subcortical regions, including the thalamus, use the same cortical equations. There are no thalamic burst/tonic
    modes and no spindles.
- **Connections:**
  - Tractography streamline counts are not synaptic strengths.
  - There is no direction of connections and no distinction between E->E and E->I long-range targets.
  - There is one conduction velocity for all fibres.
- **Sleep and neuromodulation:**
  - Both are modelled as parameter changes (gain, excitability, adaptation, gate), not as receptor kinetics.
  - The sleep engine's coupling x3 in deep NREM drives up states to near-maximal rates (E about 0.9), higher than real
    cortical up states.
  - `f_hz` is ignored.
- **Equations differ from the cited paper:** I->I coupling (c_II = -1), adaptation, gain/gate terms, noise placement
  and rho are choices made here (see Equations); c_II = 0 (the paper's form) is not usable for the sleep stages.
- **REM:** the sleep engine's coupling x0.6 is not compensated by inhibition, so mean E in REM (0.082) is below the
  awake value (0.123); real REM cortex is about as active as wake.
- **BOLD baseline:** the balloon input is u = 0.25 (E / rho - 1), so a mean rate below rho gives a constant negative
  BOLD offset (about -0.6 % at the default, up to -2 % for other parameters). Only the fluctuations
  are comparable with recorded data (which are z-scored), not the absolute level.
- **Balance:** the inhibitory balance is the analytic fixed point (mean rate about 12 % below target). It is not
  updated during the day; only `set_weights` re-solves it.
- **Fluctuations without the drive:**
  - Resting BOLD fluctuations are about 50 times smaller than recorded BOLD.
  - Mean simulated FC is much lower than recorded FC.
  - The infraslow dynamics of the real data are largely missing unless the recorded signal is fed in.
- **Hemodynamics:**
  - Constants are 1.5 T textbook values, identical in every region.
  - The neural input to the balloon model is the excitatory rate, a common proxy; synaptic activity would be another.
- **Display:** `x` is a display transform (rate envelope x cos of the E/I phase), chosen to fit the old page.

## References

- Abeysuriya RG, Hadida J, Sotiropoulos SN, et al. (2018) A biophysical model of dynamic balancing of excitation and
  inhibition in fast oscillatory large-scale networks. PLoS Comput Biol 14(2):e1006007.
- Buxton RB, Wong EC, Frank LR (1998) Dynamics of blood flow and oxygenation changes during brain activation: the
  balloon model. Magn Reson Med 39:855-864.
- Cakan C, Dimulescu C, Khakimova L, Obst D, Flöel A, Obermayer K (2022) Spatiotemporal patterns of adaptation-induced
  slow oscillations in a whole-brain model of slow-wave sleep. Front Comput Neurosci 15:800101.
- Deco G, Ponce-Alvarez A, Hagmann P, Romani GL, Mantini D, Corbetta M (2014) How local excitation-inhibition ratio
  impacts the whole brain dynamics. J Neurosci 34:7886-7898.
- Eldar E, Cohen JD, Niv Y (2013) The effects of neural gain on attention and learning. Nat Neurosci 16:1146-1153.
- Friston KJ, Mechelli A, Turner R, Price CJ (2000) Nonlinear responses in fMRI: the Balloon model, Volterra kernels,
  and other hemodynamics. NeuroImage 12:466-477.
- Hellyer PJ, Jachs B, Clopath C, Leech R (2016) Local inhibitory plasticity tunes macroscopic brain dynamics and
  allows the emergence of functional brain networks. NeuroImage 124:85-95.
- Massimini M, Ferrarelli F, Huber R, Esser SK, Singh H, Tononi G (2005) Breakdown of cortical effective connectivity
  during sleep. Science 309:2228-2232.
- McCormick DA (1992) Neurotransmitter actions in the thalamus and cerebral cortex and their role in neuromodulation
  of thalamocortical activity. Prog Neurobiol 39:337-388.
- Stephan KE, Weiskopf N, Drysdale PM, Robinson PA, Friston KJ (2007) Comparing hemodynamic models with DCM.
  NeuroImage 38:387-401.
- Stephan KE, Kasper L, Harrison LM, et al. (2008) Nonlinear dynamic causal models for fMRI. NeuroImage 42:649-662.
- Steriade M, Nuñez A, Amzica F (1993) A novel slow (< 1 Hz) oscillation of neocortical neurons in vivo.
  J Neurosci 13:3252-3265.
- Steriade M, McCormick DA, Sejnowski TJ (1993) Thalamocortical oscillations in the sleeping and aroused brain.
  Science 262:679-685.
- Vogels TP, Sprekeler H, Zenke F, Clopath C, Gerstner W (2011) Inhibitory plasticity balances excitation and
  inhibition in sensory pathways and memory networks. Science 334:1569-1573.
- Wilson HR, Cowan JD (1972) Excitatory and inhibitory interactions in localized populations of model neurons.
  Biophys J 12:1-24.
