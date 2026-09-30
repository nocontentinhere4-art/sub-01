"""Figure docs/twin/receptor_maps.png: the receptor maps used by twin/neurochem.py across the 214 regions.

Digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the
person. Maps are group post-mortem autoradiography (Zilles & Palomero-Gallagher 2017, CC BY 4.0), not this person's.
    python -m twin.plot_receptors
"""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from twin.neurochem import RECEPTOR_EFFECTS, RECEPTORS, REL_CAP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "twin" / "receptor_maps.png"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]   # one-hue blue ramp
INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"
NETS = ["Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default"]
LABEL = {"D1": "D1 (DA, +)", "5HT2": "5-HT2 (5-HT, +)", "5HT1a": "5-HT1A (5-HT, -)", "a1": "alpha1 (NE, +)",
         "a2": "alpha2 (NE, -)", "M1": "M1 (ACh, +)", "a4b2": "alpha4beta2 (ACh, +)"}


def main():
    rows = list(csv.DictReader(open(ROOT / "twin" / "data" / "receptors_214.csv")))
    names = [r["name"] for r in rows]
    recs = list(RECEPTOR_EFFECTS)
    M = np.array([RECEPTORS[r] * REL_CAP for r in recs])              # relative density, 1 = cortical mean
    net = np.array([n.split("_")[2] if n.startswith("7Networks") else "Subcort" for n in names])
    hemi = np.array([n.split("_")[1] if n.startswith("7Networks") else ("LH" if n.startswith("Left") else "RH")
                     for n in names])
    # order: network, then hemisphere; subcortical last
    order = [i for nw in NETS for h in ("LH", "RH") for i in range(200) if net[i] == nw and hemi[i] == h]
    order += list(range(200, 214))
    cmap = LinearSegmentedColormap.from_list("seq", SEQ)
    plt.rcParams.update({"font.size": 9, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.edgecolor": MUTED})
    fig = plt.figure(figsize=(13, 9.2), facecolor=SURF)
    gs = fig.add_gridspec(3, 7, height_ratios=[1.25, 1.0, 1.05], hspace=0.55, wspace=0.25)

    # (a) full heatmap
    ax = fig.add_subplot(gs[0, :])
    ax.set_facecolor(SURF)
    im = ax.imshow(M[:, order], aspect="auto", cmap=cmap, vmin=0, vmax=REL_CAP, interpolation="nearest")
    ax.add_patch(Rectangle((199.5, -0.5), 14, len(recs), facecolor="none", edgecolor=INK2, hatch="///",
                           linewidth=0.8))
    ax.text(207, len(recs) / 2 - 0.5, "no data:\nneutral\nfallback", ha="center", va="center", fontsize=7.5,
            color=INK, bbox=dict(facecolor=SURF, edgecolor="none", pad=1.5))
    pos = 0
    ticks, tl = [], []
    for nw in NETS + ["Subcort"]:
        k = int((net == nw).sum())
        ticks.append(pos + k / 2 - 0.5)
        tl.append(nw if nw != "Subcort" else "Subcort.")
        pos += k
        ax.axvline(pos - 0.5, color=SURF, lw=2)
    ax.set_xticks(ticks, tl)
    ax.tick_params(axis="x", length=0)
    ax.set_yticks(range(len(recs)), [LABEL[r] for r in recs])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("(a) Receptor density in the 214 model regions (grouped by Schaefer-7 network, LH then RH)",
                 loc="left", fontsize=10.5, color=INK)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("relative density (1 = cortical mean)", color=INK2)
    cb.outline.set_visible(False)

    # (b) per-network means
    ax = fig.add_subplot(gs[1, :4])
    nm = np.array([[M[j, net == nw].mean() for nw in NETS] for j in range(len(recs))])
    ax.imshow(nm, aspect="auto", cmap=cmap, vmin=0.5, vmax=1.5)
    for j in range(len(recs)):
        for k in range(len(NETS)):
            ax.text(k, j, f"{nm[j, k]:.2f}", ha="center", va="center", fontsize=7.5,
                    color=SURF if nm[j, k] > 1.15 else INK)
    ax.set_xticks(range(len(NETS)), NETS)
    ax.set_yticks(range(len(recs)), [LABEL[r] for r in recs])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_title("(b) Network means (cortex only)", loc="left", fontsize=10.5)

    # (c) notes panel
    ax = fig.add_subplot(gs[1, 4:])
    ax.axis("off")
    txt = ("Source: Zilles & Palomero-Gallagher 2017, Front. Neuroanat. 11:78\n"
           "(CC BY 4.0): in-vitro receptor autoradiography, 44 cortical areas,\n"
           "post-mortem group data, fmol/mg protein, mean over all layers.\n"
           "Mapped to Schaefer-200 by inverse-distance weighting from\n"
           "approximate MNI area centroids (twin/build_receptors.py).\n"
           "Relative density capped at 2x the cortical mean.\n\n"
           "Not this person's receptors. No D2, DAT, 5-HTT or NET map\n"
           "(no permissive licence reachable). Subcortical regions have no\n"
           "data and get the cortical mean (no regional specificity).\n\n"
           "Sign in brackets: + excitatory gain, - inhibitory (twin/neurochem.py).")
    ax.text(0, 1, txt, va="top", ha="left", fontsize=8.3, color=INK2, linespacing=1.45)

    # (d) top-view dot maps on MNI centroids (cortex)
    xyz = np.array([[float(r["mni_x"]), float(r["mni_y"]), float(r["mni_z"])] for r in rows[:200]])
    zo = np.argsort(xyz[:, 2])
    for j, r in enumerate(recs):
        ax = fig.add_subplot(gs[2, j])
        ax.scatter(xyz[zo, 0], xyz[zo, 1], c=M[j, :200][zo], cmap=cmap, vmin=0, vmax=REL_CAP, s=16,
                   edgecolors=SURF, linewidths=0.6)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(LABEL[r], fontsize=8.5)
        if j == 0:
            ax.text(-75, -112, "top view, anterior up", fontsize=7, color=MUTED)
    fig.text(0.125, 0.335, "(c) Cortical maps on Schaefer MNI centroids", fontsize=10.5, color=INK)
    fig.savefig(OUT, dpi=130, facecolor=SURF, bbox_inches="tight")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
