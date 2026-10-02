"""The whole-brain neuron forest (#88 B): every sampled model neuron drawn as a small real cell (NeuroMorpho.Org,
CC BY 4.0) of its region's type, <= 40 segments, enlarged and labelled so; pyramidal cells along the local cortical
surface normal; instanced (one draw call per cell type + one for the somata); fewer cells on phones; static and
labelled offline (no fake activity); a spike lights only its own cells. The right panel's cards stop above the dock.
The renderer checks run web/neurons3d.js in node with a THREE stub (tests/js/neuron_forest_check.js)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
HONEST = ("Shapes are real reconstructed neurons (public databases); thickness, spines and myelin are drawn from "
          "published typical values. The simulated network uses point neurons (no dendrites are simulated); cells are "
          "enlarged and pulses slowed to be visible. A model, not a mind.")


@pytest.fixture(scope="module")
def check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    out = subprocess.run([node, str(ROOT / "tests" / "js" / "neuron_forest_check.js")], capture_output=True, text=True,
                         check=True, timeout=180).stdout
    return json.loads(out)


def test_every_cell_is_a_simplified_real_cell(check):
    for t, s in check["simplified"].items():
        assert 30 <= s["segments"] <= 40, t                                       # <= 40 segments, most of them used
        assert s["axon"] >= 2 and s["dendrite"] >= 20, t                          # an axon for the spike, real dendrites
        assert s["axon"] <= 14, t                                                 # the axon gets <= 35 % of them


def test_caps_instancing_and_lod(check):
    d, p, m = check["desktop"], check["phone"], check["mini"]
    for r in (d, p, m):
        assert r["max_segments_per_cell"] <= 40 and r["segments"] <= 40 * r["cells"]
        assert r["drawCalls"] == r["state_drawCalls"] == len(r["types"]) + 1 <= 7   # a call per type + the somata
        assert r["enlarge"] == 14
    assert d["cells"] <= 3000 and p["cells"] <= 1500 and m["cells"] <= 800         # fewer cells on phones
    assert d["cells"] > p["cells"] > m["cells"] and d["segments"] <= 120_000 and p["segments"] <= 60_000
    assert {t["type"] for t in d["types"]} == {"pyramidal", "basket", "medium_spiny", "relay", "ca1_pyramidal",
                                               "amygdala_principal"}
    assert d["cells"] - d["shaped"] < 30                                          # pallidum only: somata, no shape


def test_pyramidal_cells_follow_the_cortical_surface_normal(check):
    d = check["desktop"]
    assert d["pyramidal_on_cortex"] == d["pyramidal_aligned"] > 1000 and d["pyramidal_min_dot"] > 0.999
    for t, s in d["spread"].items():                                              # the rest: no common direction
        assert s["mean_len"] < (0.75 if t in ("ca1_pyramidal", "amygdala_principal") else 0.2), t


def test_normals_point_out_of_the_brain(check):
    """The page's normals agree with those of a heavily smoothed copy of the mesh (a blob: there outward is plain)."""
    v = np.fromfile(ROOT / "web" / "cortex.bin", dtype=np.float32).reshape(-1, 3).astype(np.float64)
    f = np.fromfile(ROOT / "web" / "cortex_idx.bin", dtype=np.uint32).reshape(-1, 3)
    n = len(v)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    A = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    A.data[:] = 1.0
    W = sparse.diags(1 / np.maximum(1, np.asarray(A.sum(1)).ravel())) @ A
    s = v.copy()
    for _ in range(60):
        s = 0.5 * s + 0.5 * (W @ s)
    fn = np.cross(s[f[:, 1]] - s[f[:, 0]], s[f[:, 2]] - s[f[:, 0]])
    sn = np.zeros_like(s)
    for k in range(3):
        np.add.at(sn, f[:, k], fn)
    ctr = np.where(s[:, :1] < 0, s[s[:, 0] < 0].mean(0), s[s[:, 0] >= 0].mean(0))
    if (np.einsum("ij,ij->i", sn, s - ctr) > 0).mean() < 0.5:
        sn = -sn                                                                  # the blob's own outward side
    smp = np.array(check["normals_sample"]).reshape(-1, 4)
    idx, pn = smp[:, 0].astype(int), smp[:, 1:]
    assert (np.einsum("ij,ij->i", pn, sn[idx]) > 0).mean() > 0.9


def test_offline_static_live_only_its_own_cells(check):
    d = check["desktop"]
    off, live = d["offline"], d["live"]
    assert off["visible"] and off["fade"] == 1 and off["uLive"] == 0 and off["spiking"] == 0   # static, never fake
    assert live["regions"] == [12] and 0 < live["spiking"] and live["uploaded"] and live["state_live"]
    assert live["uLive"] > 0.9 and live["rate_byte_12"] == 230


def test_page_wording_and_panel_layout():
    html = (ROOT / "web" / "index.html").read_text()
    js = (ROOT / "web" / "neurons3d.js").read_text()
    assert HONEST in html                                                         # the issue's caption, word for word
    assert "cells enlarged ~${st.enlarge}× for visibility" in html and "static cells, no activity" in html
    assert "maxCells: MINI ? 800 : innerWidth < 600 ? 1500 : 3000" in html and "cortexIdx" in html
    for text in (html.lower(), js.lower()):
        assert "his real neurons" not in text and "scanned person's neurons" not in text and "from his brain" not in text
    # the right column: cards stop above the dock however tall it grows (#88: the toggles overlapped them at 1920 px)
    assert re.search(r"#cards \{[^}]*max-height:calc\(100vh - var\(--dock-h\)", html)
    assert 'setProperty("--dock-h"' in html and "ResizeObserver" in html
    assert re.search(r"#layers \{[^}]*flex-wrap:wrap", html)
    assert "body.n3 #cards" not in html
