"""Figures for docs/encoding/REPORT.md from out/encoding/scores.json (matplotlib + nilearn, offline).

  fig_scores.png    held-out r per region for the model vs its controls (one dot a region, the median marked)
  fig_ceiling.png   held-out r vs noise ceiling per region (significant regions in blue)
  fig_map_<kind>.png  held-out r on the brain (significant regions only), glass-brain view
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, ROOT, atlas_mni  # noqa: E402

DOCS = ROOT / "docs" / "encoding"
BLUE, GREY, INK, INK2, GRID = "#2a78d6", "#a3a29c", "#0b0b0b", "#52514e", "#e6e5df"
SURF = "#fcfcfb"


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def scores_fig(sc, plt):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.0), facecolor=SURF)
    sets = {"vision": [("real", "model\n(CLIP + low-level)"), ("low_level_only", "low-level\nonly"),
                       ("shuffled", "shuffled\nfeatures"), ("shifted", "time-shifted\nstimulus")],
            "text": [("semantic", "model\n(text, runtime)"), ("real", "+ nuisance\n(rate, loudness)"),
                     ("nuisance_only", "nuisance\nonly"), ("shuffled", "shuffled\nfeatures"),
                     ("shifted", "time-shifted\nstimulus")]}
    rng = np.random.default_rng(0)
    for ax, kind in zip(axes, ("vision", "text")):
        style(ax)
        for x, (k, lab) in enumerate(sets[kind]):
            r = np.array(sc[kind][k]["r"])
            main = x == 0
            ax.scatter(x + rng.uniform(-0.18, 0.18, len(r)), r, s=9, color=BLUE if main else GREY,
                       alpha=0.75 if main else 0.55, lw=0)
            ax.plot([x - 0.3, x + 0.3], [np.median(r)] * 2, color=INK, lw=2, solid_capstyle="round")
            ax.text(x + 0.33, np.median(r), f"{np.median(r):.3f}", va="center", fontsize=8, color=INK2)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(range(len(sets[kind])), [lab for _, lab in sets[kind]], fontsize=8)
        n = sc[kind]["n_subjects"]
        ax.set_title(f"{'Images → cortex (3 films)' if kind == 'vision' else 'Text → cortex (Alice story)'} · "
                     f"{n} participants", fontsize=10, color=INK, loc="left")
        ax.set_ylabel("held-out r per region", fontsize=9, color=INK2)
    fig.tight_layout()
    fig.savefig(DOCS / "fig_scores.png", dpi=150)


def ceiling_fig(sc, plt):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), facecolor=SURF)
    for ax, kind in zip(axes, ("vision", "text")):
        style(ax)
        s = sc[kind]["semantic" if kind == "text" else "real"]
        r, c, q = (np.array(s[k]) for k in ("r", "ceiling", "q"))
        sig = q < 0.05
        ax.scatter(c[~sig], r[~sig], s=10, color=GREY, lw=0, alpha=0.7, label="not significant")
        ax.scatter(c[sig], r[sig], s=14, color=BLUE, lw=0, label=f"q < 0.05 ({sig.sum()} regions)")
        ax.plot([0, 1], [0, 1], color=INK2, lw=0.8, ls="--")
        ax.text(0.80, 0.93, "r = ceiling", fontsize=8, color=INK2, ha="right")
        ax.set_xlim(0, 1)
        ax.set_ylim(min(-0.1, r.min() - 0.02), 1)
        ax.set_xlabel("noise ceiling (√ split-half r of the participant halves)", fontsize=9, color=INK2)
        ax.set_ylabel("held-out r", fontsize=9, color=INK2)
        ax.set_title("Images → cortex" if kind == "vision" else "Text → cortex (runtime part)", fontsize=10,
                     color=INK, loc="left")
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(DOCS / "fig_ceiling.png", dpi=150)


def map_fig(sc, kind):
    import nibabel as nib
    from nilearn import plotting
    lab, _ = atlas_mni()
    s = sc[kind]["semantic" if kind == "text" else "real"]
    r, q = np.array(s["r"]), np.array(s["q"])
    vals = np.where(q < 0.05, r, 0.0)
    L = np.asarray(lab.dataobj).astype(int)
    vol = np.zeros(L.shape, np.float32)
    vol[L > 0] = vals[L[L > 0] - 1]
    img = nib.Nifti1Image(vol, lab.affine)
    title = ("images → cortex: held-out r (q < 0.05)" if kind == "vision" else
             "text → cortex: held-out r of the runtime part (q < 0.05)")
    d = plotting.plot_glass_brain(img, display_mode="lyrz", colorbar=True, cmap="Blues", vmin=0,
                                  vmax=max(0.05, float(vals.max())), plot_abs=False, title=title, threshold=1e-6)
    d.savefig(str(DOCS / f"fig_map_{kind}.png"), dpi=130)
    d.close()


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    DOCS.mkdir(parents=True, exist_ok=True)
    sc = json.load(open(OUT / "scores.json"))
    scores_fig(sc, plt)
    ceiling_fig(sc, plt)
    for kind in ("vision", "text"):
        map_fig(sc, kind)


if __name__ == "__main__":
    main()
