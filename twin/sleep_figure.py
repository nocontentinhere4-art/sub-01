"""Figure for docs/twin/sleep.md: one undisturbed 24 h run of the sleep circuit (sleep.py).

    python twin/sleep_figure.py            # -> docs/twin/hypnogram.png, prints the night's numbers

Panels share the time axis (12:00 -> 12:00 local clock): somnogen H, circadian drive C, MA vs VLPO potentials,
the hypnogram (with the NREM depth index) and the four neuromodulator levels the engine exports.
A digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious,
not the person.
"""
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sleep  # noqa: E402

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]      # validated categorical slots 1-4 (light)
STAGE_Y = {"AWAKE": 3, "REM": 2, "NREM": 1}


def simulate(step=30.0):
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=sleep.TZ).timestamp()
    e = sleep.SleepEngine(t0)
    rows, t = [], t0
    while t < t0 + 86400:
        t += step
        e.update(t)
        rows.append((t, e.H, e.C, e.V_m, e.V_v, e.stage, e.depth, e.modulators))
    return t0, rows


def summary(rows, step=30.0):
    asleep = [r for r in rows if r[5] != "AWAKE"]
    eps = []
    for r in asleep:
        if not eps or eps[-1][0] != r[5]:
            eps.append([r[5], r[0], r[0]])
        eps[-1][2] = r[0] + step
    rem = [(x[2] - x[1]) / 60 for x in eps if x[0] == "REM"]
    return {"onset": sleep.hhmm(asleep[0][0]), "wake": sleep.hhmm(asleep[-1][0] + step),
            "sleep_h": round(len(asleep) * step / 3600, 2),
            "rem_share": round(sum(r[5] == "REM" for r in asleep) / len(asleep), 3),
            "first_rem_after_min": round((next(x[1] for x in eps if x[0] == "REM") - asleep[0][0]) / 60),
            "episodes_min": [f"{x[0][0]}{(x[2] - x[1]) / 60:.0f}" for x in eps], "rem_min": [round(x) for x in rem]}


def main(out=ROOT / "docs" / "twin" / "hypnogram.png"):
    t0, rows = simulate()
    x = np.array([(r[0] - t0) / 3600 + 12 for r in rows])
    col = lambda i: np.array([r[i] for r in rows])
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(5, 1, figsize=(10, 10.5), sharex=True,
                           gridspec_kw={"height_ratios": [1, 0.8, 1.2, 1.1, 1.5], "hspace": 0.35})
    for a in ax:
        a.grid(True, color=GRID, lw=0.8)
        a.set_axisbelow(True)
    asleep = np.array([r[5] != "AWAKE" for r in rows])
    for a in ax:                                                  # shade the sleep period on every panel
        a.fill_between(x, 0, 1, where=asleep, transform=a.get_xaxis_transform(), color="#f1f0ec", lw=0)

    ax[0].plot(x, col(1), color=SERIES[0], lw=2)
    ax[0].set_ylabel("H (nM)")
    ax[0].set_title("Homeostatic somnogen H: rises while awake, cleared during sleep", loc="left", color=INK, fontsize=10)
    ax[1].plot(x, col(2), color=SERIES[0], lw=2)
    ax[1].set_ylabel("C")
    ax[1].set_title(f"Circadian drive C (local clock, peak {sleep.CIRC_PEAK_H:.2f} h)", loc="left", color=INK,
                    fontsize=10)
    ax[2].plot(x, col(3), color=SERIES[0], lw=2, label="V_m  monoaminergic (MA)")
    ax[2].plot(x, col(4), color=SERIES[1], lw=2, label="V_v  VLPO")
    ax[2].set_ylabel("mV")
    ax[2].legend(loc="center left", frameon=False, ncol=2)
    ax[2].set_title("Flip-flop: MA and VLPO inhibit each other (Phillips & Robinson 2007)", loc="left", color=INK,
                    fontsize=10)
    st = np.array([STAGE_Y[r[5]] for r in rows])
    ax[3].step(x, st, where="post", color=INK, lw=1.5)
    d = col(6)
    ax[3].fill_between(x, 1 - 0.9 * d, 1, where=d > 0, step="post", color=SERIES[0], alpha=0.35, lw=0,
                       label="NREM depth index (down = deeper)")
    rem = st == 2
    ax[3].fill_between(x, 1.75, 2.25, where=rem, step="post", color=SERIES[1], lw=0, label="REM")
    ax[3].set_yticks([0.1, 1, 2, 3], ["deep", "NREM", "REM", "AWAKE"])
    ax[3].set_ylim(-0.05, 3.3)
    ax[3].legend(loc="lower left", frameon=False, ncol=1)
    ax[3].set_title("Hypnogram (REM-on/REM-off flip-flop + REM pressure; ~90 min cycles)", loc="left", color=INK,
                    fontsize=10)
    for i, k in enumerate(sleep.MOD_KEYS):
        ax[4].plot(x, [r[7][k] for r in rows], color=SERIES[i], lw=2, label=k)
    ax[4].axhline(1.0, color=INK2, lw=0.8, ls=":")
    ax[4].set_ylabel("level (1 = resting wake)")
    ax[4].legend(loc="lower left", frameon=False, ncol=4)
    ax[4].set_title("Neuromodulator levels read from the circuit (engine.modulators)", loc="left", color=INK,
                    fontsize=10)
    ticks = np.arange(12, 37, 2)
    ax[4].set_xticks(ticks, [f"{int(h) % 24:02d}:00" for h in ticks])
    ax[4].set_xlim(12, 36)
    ax[4].set_xlabel(f"local time ({sleep.TZ_NAME}), undisturbed day, no input")
    fig.suptitle("SUB-01 sleep circuit: 24 h (a model, not the person)", x=0.125, y=0.925, ha="left", color=INK,
                 fontsize=12, fontweight="bold")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130, bbox_inches="tight", facecolor="white")
    s = summary(rows)
    print(s)
    return s


if __name__ == "__main__":
    main()
