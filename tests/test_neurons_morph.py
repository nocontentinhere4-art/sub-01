"""Neurons with their real shape (#78): the morphology asset (real NeuroMorpho.Org reconstructions, CC BY 4.0,
simplified), its credits, the close-up renderer's caps (<= 300 cells, <= 60k segments, one draw call per cell type),
the level-of-detail switch, and no activity without a live network (the cerebellum, not in the model, never moves).
The renderer checks run web/neurons3d.js in node with a THREE stub (tests/js/neurons_morph_check.js)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

import build_morphologies as BM  # noqa: E402

ASSET = ROOT / "web" / "neurons_morph.json"
SHAPES = ("Shapes are real reconstructed neurons from public databases and are illustrative: the simulated network uses "
          "point neurons (no dendrites are simulated). Pulses are slowed down to be visible.")


@pytest.fixture(scope="module")
def morph():
    return json.loads(ASSET.read_text())


def test_asset_small_and_well_formed(morph):
    assert ASSET.stat().st_size <= 400 * 1024                                    # one small asset
    assert set(morph["cells"]) == set(BM.CELLS) == {"pyramidal", "basket", "medium_spiny", "relay", "purkinje"}
    for kind, c in morph["cells"].items():
        nid, budget, _, _ = BM.CELLS[kind]
        assert c["neuron_id"] == nid and c["nmo_id"] == f"NMO_{nid:05d}" and c["license"] == "CC BY 4.0"
        assert 0 < c["n_seg"] <= budget <= 300                                    # simplified to <= ~300 segments
        assert len(c["pos"]) == 6 * c["n_seg"] and len(c["kind"]) == c["n_seg"] and len(c["dist"]) == 2 * c["n_seg"]
        assert set(c["kind"]) <= {1, 2, 3} and min(c["dist"]) >= 0
        P = np.array(c["pos"]).reshape(-1, 6)
        assert np.abs(P).max() < 2000                                             # micrometres, soma at the origin
        assert c["species"] in ("human", "rat") and c["archive"] != "Allen Cell Types"
    cells = morph["cells"]
    assert cells["pyramidal"]["species"] == cells["basket"]["species"] == cells["purkinje"]["species"] == "human"
    assert cells["pyramidal"]["axon_len"] > 500 and cells["purkinje"]["axon_len"] == 0   # Purkinje: no axon reconstructed
    pyr = np.array(cells["pyramidal"]["pos"]).reshape(-1, 6)
    k = np.array(cells["pyramidal"]["kind"])
    assert pyr[k == 3][:, [1, 4]].mean() > 50 and pyr[k == 1][:, [1, 4]].min() < -300   # apical up, axon down
    pk = np.array(cells["purkinje"]["pos"]).reshape(-1, 6)
    assert np.ptp(pk[:, [2, 5]]) < 0.25 * np.ptp(pk[:, [0, 3]])                  # the fan lies in the x-y plane
    assert "not from the scanned person" in morph["note"]


def test_every_cell_is_credited(morph):
    flat = lambda t: re.sub(r"\s+", " ", t.replace("**", ""))
    md = flat((ROOT / "docs" / "spiking" / "morphology_credits.md").read_text())
    about = flat((ROOT / "web" / "about.html").read_text())
    assert "Creative Commons Attribution 4.0" in md and "RRID:SCR_002145" in md and "doi:10.1096/fba.2024-00048" in md
    assert "CC BY 4.0" in about and "NeuroMorpho.Org" in about and "Tecuatl" in about
    for c in morph["cells"].values():
        assert c["nmo_id"] in md and c["nmo_id"] in about and c["paper"] and c["paper"] in md
    assert "none of these cells is from the person whose MRI" in md and "none of these cells is from the scanned person" in about


def test_simplify_keeps_the_budget():
    """A synthetic tree with 400 branches and wiggly paths: pruned and RDP-simplified to the budget, tips kept."""
    rng = np.random.default_rng(3)
    pos, kids = {0: np.zeros(3)}, {0: []}
    nid = 1
    for b in range(400):
        parent = 0
        for s in range(20):
            pos[nid] = pos[parent] + rng.normal(0, 3, 3) + (np.array([1.0, 0, 0]) if b % 2 else np.array([0, 1.0, 0]))
            kids.setdefault(parent, []).append(nid)
            kids[nid] = []
            parent = nid
            nid += 1
    for budget in (50, 200, 300):
        segs, eps = BM.simplify(pos, kids, budget)
        assert 0 < len(segs) <= budget and eps > 0
    pts = np.array([[0, 0, 0], [1, 0.01, 0], [2, 0, 0], [3, 5, 0], [4, 0, 0]], float)
    assert BM.rdp(pts, 0.1) == [0, 2, 3, 4]


def _node_check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    out = subprocess.run([node, str(ROOT / "tests" / "js" / "neurons_morph_check.js")], capture_output=True, text=True,
                         check=True, timeout=120).stdout
    return json.loads(out)


def test_closeups_cap_segments_and_draw_calls():
    d = _node_check()
    for kind in ("cortex", "striatum", "thalamus", "cerebellum"):
        c = d[kind]
        assert 100 <= c["cells"] <= 300 and c["segments"] == c["drawn_segments"] <= 60_000
        assert c["drawCalls"] == len(c["types"]) <= 2                         # one draw call per cell type
    assert [t["type"] for t in d["cortex"]["types"]] == ["pyramidal", "basket"]
    assert d["striatum"]["types"][0]["type"] == "medium_spiny" and d["thalamus"]["types"][0]["type"] == "relay"
    assert d["cerebellum"]["types"][0]["type"] == "purkinje"
    assert d["slowdown"] == 500


def test_no_activity_without_a_live_network():
    d = _node_check()
    for kind in ("cortex", "striatum", "thalamus", "cerebellum"):
        c = d[kind]
        assert c["spiking_offline"] == 0 and c["live_offline"] is False and c["rate_offline"] == 0   # offline: still
        assert c["spiking_other_region"] == 0                                    # another region's spikes: not here
    for kind in ("cortex", "striatum", "thalamus"):
        assert d[kind]["spiking_after"] > 0 and d[kind]["live_after"] and d[kind]["rate_after"] > 0.5
    cb = d["cerebellum"]                                                         # not in the model: never any activity
    assert cb["simulated"] is False and cb["spiking_after"] == 0 and cb["live_after"] is False and cb["rate_after"] == 0


def test_level_of_detail_switch():
    d = _node_check()
    assert d["lod"] == ["brain", "closeup", "closeup", "brain"]                  # zoom in: shapes; zoom out: points
    assert d["kinds"] == ["cortex", "striatum", "thalamus", None, "cortex"]


def test_brain_page_wording():
    html = (ROOT / "web" / "index.html").read_text()
    assert SHAPES in html                                                        # word for word (#78)
    assert "the cerebellum is not in the simulated network: shapes only, no activity" in html
    assert "no live network: shapes only, no activity" in html
    assert re.search(r'id="n3close".*data-k="cortex".*data-k="striatum".*data-k="thalamus".*data-k="cerebellum"', html)
    for text in (html.lower(), (ROOT / "web" / "neurons3d.js").read_text().lower()):
        assert "his real neurons" not in text and "scanned person's neurons" not in text
