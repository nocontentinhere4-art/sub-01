"""Assemble docs/twin_report.md from docs/twin/*.md, web/twin_score.json, twin/data/cpu_live.json and the sources file.

    python twin/build_report.py

The component sections are included unchanged (headings demoted, figure paths made relative to docs/); the tables are
generated from the committed result files so the report cannot drift from them. A digital twin model of one real
person's brain structure and recorded activity; not a mind, not conscious, not the person.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WHAT = ("a digital twin model of one real person's brain structure and recorded activity; "
        "not a mind, not conscious, not the person")
SECTIONS = [("model", "Neural mass model"), ("fit", "Fit to the recorded activity and held-out scores"),
            ("neurochem", "Neuromodulators and receptor-weighted gain"), ("sleep", "Sleep circuit"),
            ("body", "Body: heart, breathing, glucose, hunger"), ("plasticity", "Plasticity and one memory a night")]

NOT_REALISTIC = """\
The component sections list their own limits (links in each section's last part). This is the short, consolidated list.

**What the model does and does not match**
- The held-out match to the recorded resting-state fMRI is **weak and static**: r = {fc_r} for functional connectivity
  (FC) on {n_runs} runs the fit never saw, against a test-retest ceiling of {ceiling}, and below the plain correlation of
  the connectome with the recorded FC ({sc_fc}). The twin reproduces how much FC fluctuates over time (FCD distance
  {fcd}) but not which regions co-fluctuate. It is not a faithful copy of this person's functional connectivity.
- It beats a shuffled connectome and the old Stuart-Landau model, but both are near a floor, so that shows the
  twin's FC is not noise, not that it is competitive with good whole-brain fits. Mean simulated FC is {fc_sim} against
  {fc_rec} recorded (the recordings have no global-signal regression).
- The shuffled connectome keeps the weight distribution but not each region's strength or the wiring's geometry. The
  twin was **not** compared with geometry- or strength-preserving null connectomes, so it is not shown that the
  person's specific wiring, beyond its overall strengths and distances, is what gives the (weak) match.
- Three global parameters are fitted (G, velocity, noise). Nothing regional, no receptor or hemodynamic fit. The live
  limit G <= 3.5 (so the sleep stages stay stable) costs static FC (r 0.15 without it).
- The held-out score is for the resting model with all neuromodulator levels at 1.0 and the original weights. It was
  **not re-measured** with the neuromodulator gain, the sleep stages, the body feedback or the plasticity switched on, and
  there is no recording of this person to test those against.
- The live page can replay the person's **recorded** fMRI as slow drive (`real_baseline.py`, on by default,
  `--no-real-baseline` turns it off). That is a replay of a recording, not the wiring producing the activity; the
  score above does not use it.

**Wiring and brain**
- Streamline counts from single-subject tractography are not synaptic strengths; the connectome misses many
  interhemispheric fibres and is undirected. One conduction velocity. One E/I population per parcel, no thalamic modes,
  no spindles. Sleep and neuromodulation are parameter changes (gain, excitability, adaptation, gate), not receptor kinetics.
- The sleep stages change excitability, coupling and noise, and the neuromodulator gain follows the same sleep circuit,
  so the effect of sleep is partly counted twice; the overlap was not separated or fitted.
- In REM the sleep engine's coupling lowers mean activity below wake (real REM cortex is about as active as wake).
  Deep-NREM up states are stronger than real ones. The `f_hz` rhythm of the old model is ignored by the twin.
- Simulated BOLD fluctuations are about 50 times smaller than recorded ones unless the recorded signal is fed in.
- With `--time-scale` above 1 the sleep engine, neuromodulators, body and plasticity run in simulated time, but the
  brain model still advances 50 ms of model time per tick: it samples the day, it does not simulate it.

**Neuromodulators, sleep, body**
- Receptor maps are group post-mortem autoradiography of other people, 44 cortical areas interpolated to 200 parcels,
  no subcortical data (cortical mean used), no D2 or transporter maps. The commercially usable licence set excludes the
  richer PET maps (non-commercial licences). Trades as "reward" and "threat", and the dopamine / noradrenaline rules
  built on them, are a design metaphor, not a measurement of anyone's brain chemistry. 5-HT and ACh only follow the
  sleep circuit. Levels are ordinal anchors, not concentrations.
- The sleep circuit is a generic young-adult calibration, nothing fitted to this person; the REM parameters were tuned by
  hand; no light input, no spontaneous awakenings.
- The body is a textbook adult sketch (no hormones, no liver, one fixed 70 kg body, no baroreflex or heart-rate
  variability, breathing rate only). Its parameters are not fitted to the person. In the integrated run the low
  noradrenaline of REM lowers the sympathetic term, so the heart rate in REM (about 54 bpm in the headless night) is
  at or below NREM (56), whereas the body section's stand-alone numbers (REM above NREM) assume a fixed REM tone. The
  hunger drive to the insula proxy has no hypothalamus (the atlas has none) and its gain is a choice.

- Under the dense synthetic flow of `--demo` (a trade about every 0.7 s) the market-driven noradrenaline sits at 1.5 to 2.1
  and the heart rate at about 100 to 120 bpm: the trade-to-noradrenaline and noradrenaline-to-heart-rate mappings were not
  tuned together and saturate under dense flow. The heart rate follows market activity by design; it is not a model of a person's response.

**Plasticity and memory**
- Plasticity is a toy: a bounded covariance (Hebbian) rule on fibre-bundle weights, tiny rates, hard caps (5 % per edge,
  2 % in total), unfitted. After one night the weights move by about 4e-4 (relative Frobenius). A "memory" is a hash-stamped
  log entry plus a 1 % weight change among the regions that responded most to one chat message, not recollection.
- "Responded most" is the model's own activity increase over 2 s of model time after the message, measured once and
  noisy; the winner is partly chance and partly the stage gain. The sender is never stored; the message text is public chat.
- The sha256 is a fingerprint of the weights after the night; nothing is published anywhere (`publish_hash` is a no-op).

**Running it**
- Persistence is local files in the data directory (a Railway volume); if it is lost, so are the weights and memories.
- CPU numbers come from a shared sandbox core, not from a Railway vCPU.
- With `--model sl` the panel shows the old Stuart-Landau model's own held-out score (no static or FC-dynamics match),
  never the twin's, and plasticity is off (that model has no weight hook, so there is no drift and no memory).
- State is saved every minute (and on Ctrl-C); a kill, including the SIGTERM of a redeploy, can lose up to a minute of sleep,
  body and weight state (a REM consolidation is saved at once).
- No consciousness, experience, feeling or intention is claimed or modelled. Chat messages are stimuli, not conversation."""


def table(rows, head):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def section(slug, title, n):
    text = (DOCS / "twin" / f"{slug}.md").read_text()
    text = re.sub(r"\A# .*\n", "", text, count=1)
    text = re.sub(r"(?m)^(#{2,5}) ", lambda m: "#" * (len(m.group(1)) + 1) + " ", text)    # demote
    text = re.sub(r"\]\((?!https?:|#|twin/)([^)]+\.png)\)", r"](twin/\1)", text)
    text = re.sub(r"(?m)^(#{3,6}) \d+\. ", r"\1 ", text)
    return f"## {n}. {title}\n\nSource file: `docs/twin/{slug}.md`.\n{text.rstrip()}\n"


def main():
    sc = json.loads((ROOT / "web" / "twin_score.json").read_text())
    h, b = sc["heldout"], sc["baselines"]
    sh, old = b["shuffled_connectome"], b["old_model"]
    unc = sc["robustness"]["without_live_constraint"]
    cpu_path = ROOT / "twin" / "data" / "cpu_live.json"
    cpu = json.loads(cpu_path.read_text()) if cpu_path.exists() else None
    out = [f"# SUB-01 v2: the digital twin, assembled\n\n*{WHAT[0].upper() + WHAT[1:]}.* "
           "Chat messages are stimuli, not conversation. Nothing here is a claim of consciousness, experience or intent, "
           "and no individual is named.\n"]
    out.append("""\
## Overview

SUB-01 v2 replaces the old rhythm generator with a model whose pieces are each built from published equations and
documented, and wires them into the live server (`live_server.py`, branch `feature/twin-integration`):

| piece | file | what it does in the live loop |
|---|---|---|
| neural mass model | `twin/model.py` (`TwinBrain`, via `brain_sim.make_brain`) | 214 delayed Wilson-Cowan E/I regions on the connectome, fitted G / velocity / noise (`twin/params.json`); the old model stays available with `--model sl` |
| neuromodulators | `twin/neurochem.py` | `on_trade` for every trade; `update(dt, sleep_levels=engine.modulators)`; `region_gain(levels)` -> `brain.set_gain` |
| sleep | `sleep.py` | sleep-wake circuit; exposes `modulators`, `H`, `C`, `pressure`; sets the rhythm parameters |
| body | `twin/body.py` | stepped in sim time with the levels, the amygdala excess and the stage; `intero_drive()` stimulates the insula proxy; `life.py` takes hunger from it and calls `eat` |
| plasticity | `twin/plasticity.py` | `hebbian` while awake; chat responses recorded; `consolidate` once in the first REM of each night; `brain.set_weights(W)` about once per sim minute |
| fit + score | `twin/fit.py`, `web/twin_score.json` | held-out numbers shown on the pages |

Per tick (50 ms of model time) `Live.tick()` does: sleep engine -> neuromodulators (tonic from the sleep circuit, phasic
from trades) -> trades into the brain -> gain -> body (in sim time, up to about 180 s per call at `--time-scale 3600`) and
its drive -> 50 integration steps -> chat-response probes and Hebbian update -> REM consolidation -> the `twin` object in
the tick message (score, levels, vitals, sleep H / C / pressure, memories, drift). State is kept in the data directory
(`twin_state.json`, `weights.npz`, `memories.json`, `pending_responses.json`); `out/connectome.npz` is only read. The
pages (`/brain`, `/`) show a compact Twin panel (`web/twin_panel.js`) fed by that object.

How a chat message becomes a memory: it is filtered, becomes a stimulus, and the model's activity over the next 2 s of
model time is compared with the 2 s before; the 8 regions with the largest increase and their summed increase are
recorded (`record_response`). In the first REM episode of the night the message with the largest response is consolidated:
the weights among its regions are raised by 1 %, and a record with the sha256 of the weights is appended.

The Twin panel on `/brain` (left) and on the life page `/` (right), from a local `--demo` run after one accelerated
synthetic night (`twin/screenshots.py`; the memory shown is from that synthetic chat):

![Twin panel on /brain](twin/screenshots/brain_twin_panel.png) ![Twin panel on /](twin/screenshots/life_twin_panel.png)
""")
    out.append("## Held-out scores\n")
    out.append(f"Label shown on the pages: *{sc['label']}*.\n")
    rows = [["**twin (fitted)**", f"**{h['fc_r']} ± {h['fc_r_sd']}**", f"**{h['fcd_ks']} ± {h['fcd_ks_sd']}**", h["mean_fc_sim"]],
            ["shuffled connectome, same model, own search", f"{sh['fc_r']} ± {sh['fc_r_sd']}", f"{sh['fcd_ks']} ± {sh['fcd_ks_sd']}", sh["mean_fc"]],
            ["old Stuart-Landau model, own search", f"{old['fc_r']} ± {old['fc_r_sd']}", f"{old['fcd_ks']} ± {old['fcd_ks_sd']}", old["mean_fc"]],
            ["twin without the live constraint (G 16)", f"{unc['fc_r']} ± {unc['fc_r_sd']}", f"{unc['fcd_ks']} ± {unc['fcd_ks_sd']}", unc["mean_fc"]]]
    out.append(table(rows, ["model", "r(FC), held-out", "KS(FCD), held-out (lower is better)", "simulated mean FC"]))
    out.append(f"\nHeld-out half: {h['n_runs']} runs from {h['n_sessions']} sessions, FCD on {h['n_runs_fcd']} runs; "
               f"mean ± SD over {h['replicates']} replicates of {h['simulated_runs_per_replicate']} simulated 10-minute runs.\n")
    ref = [["connectome (log streamline count) vs recorded FC, all pairs", b["sc_fc_direct_r"]],
           ["same, connected pairs only", b["sc_fc_direct_r_connected_pairs_log"]],
           ["test-retest ceiling (fit-half mean FC vs held-out mean FC)", b["test_retest_ceiling_r"]],
           ["recorded mean FC (held-out)", h["mean_fc_recorded"]],
           ["one recorded run vs another recorded run", sc["per_run"]["run_to_run"]["mean"]],
           ["one simulated run vs one recorded run", sc["per_run"]["sim_run_vs_single_run"]["mean"]]]
    out.append(table(ref, ["reference", "r"]))
    out.append("\nThe match is weak and static; see the fit section for what it does and does not show. "
               "Source: `web/twin_score.json` (written by `python -m twin.fit write`).\n")
    out.append("## CPU use of the live server\n")
    if cpu:
        rows = [["nobody watching" if not p["client_connected"] else "one viewer connected", p["wall_s"],
                 p["server_cpu_pct_of_one_core"], p["model_step_cpu_pct_of_one_core"], p["tick_logic_cpu_pct_of_one_core"],
                 p["ticks_per_s"]] for p in cpu["phases"]]
        out.append(table(rows, ["phase", "wall s", "whole server, % of one core", "model step only, %", "whole tick logic (model + neurochem + body + plasticity + life), %", "ticks/s"]))
        out.append(f"\n`live_server.py --demo`, real time, twin model, real-baseline replay on, no eye, `OMP_NUM_THREADS=1`; "
                   f"target <= {cpu['target_pct_of_one_core']:.0f} % of one core: **{'met' if cpu['meets_target'] else 'NOT met'}** "
                   f"(worst case {cpu['worst_server_cpu_pct']} %). Measured by `python twin/measure_cpu_live.py` "
                   f"({cpu['measured_at']}); numbers in `twin/data/cpu_live.json`. {cpu['machine']['note']}.\n")
    else:
        out.append("Not measured yet (run `python twin/measure_cpu_live.py`).\n")
    for i, (slug, title) in enumerate(SECTIONS, 1):
        out.append(section(slug, title, i))
    out.append("## 7. Sources and licences\n")
    out.append("Receptor data (full table, from `twin/data/RECEPTORS_SOURCES.md`):\n")
    src = (ROOT / "twin" / "data" / "RECEPTORS_SOURCES.md").read_text()
    src = re.sub(r"\A# .*\n", "", src, count=1)
    src = re.sub(r"(?m)^(#{2,5}) ", lambda m: "#" * (len(m.group(1)) + 2) + " ", src)
    out.append(src.rstrip() + "\n")
    out.append("Other data: MyConnectome, OpenNeuro ds000031 (public domain, PDDL): diffusion and resting-state MRI of one "
               "person, used for the connectome, the cortical surface and the fit; raw scans are not stored here. "
               "The live Solana log stream and the chat are runtime inputs. Code and parameters in `twin/` are from the "
               "papers cited in each section; no code was copied from the projects named there. "
               "The pages add no external requests beyond those they already had (CDN libraries, map and video embeds).\n")
    out.append("## 8. What is still not realistic\n")
    out.append(NOT_REALISTIC.format(
        fc_r=h["fc_r"], n_runs=h["n_runs"], ceiling=b["test_retest_ceiling_r"], sc_fc=b["sc_fc_direct_r"], fcd=h["fcd_ks"],
        fc_sim=h["mean_fc_sim"], fc_rec=h["mean_fc_recorded"]) + "\n")
    out.append("""\
## 9. How to run

```bash
python live_server.py --demo                        # twin model (default), synthetic trades, http://localhost:8765
python live_server.py --demo --model sl             # the old Stuart-Landau model, same pages
python live_server.py --demo --time-scale 600 --start 23:30   # an accelerated night: stages, REM memory, drift
python live_server.py --mint <token mint>           # real trades; add --eye for generated images
SUB01_MODEL=sl python live_server.py --demo         # model from the environment
python -m pytest tests -q                           # all tests (tests/test_integration.py: headless accelerated night)
OMP_NUM_THREADS=1 python twin/measure_cpu_live.py   # CPU use at real time -> twin/data/cpu_live.json
OMP_NUM_THREADS=1 python twin/screenshots.py        # Twin panel pictures -> docs/twin/screenshots/
python twin/build_report.py                         # rebuild this report
```

Pictures of the panel: `docs/twin/screenshots/brain_twin_panel.png` (`/brain`) and `life_twin_panel.png` (`/`).
""")
    (DOCS / "twin_report.md").write_text("\n".join(out))
    print("wrote", DOCS / "twin_report.md")


if __name__ == "__main__":
    main()
