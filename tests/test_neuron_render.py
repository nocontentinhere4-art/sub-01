"""Microscopy-grade neuron close-ups (#88 A, web/neuron_render/): the asset (the six NeuroMorpho.Org cells of #78 with
their radii, CC BY 4.0, credited), the renderer's plan (an action potential's arrival times along the axon, myelin only
beyond the initial segment on myelinated types, boutons on the unmyelinated axon, spines at the stated density), the
triangle budget at both levels of detail, the honest caption word for word, the published values documented with their
sources, and the close-up call site on /brain. The renderer's pure parts run in node with a THREE stub
(tests/js/neuron_render_check.js); the pixels are checked by hand with tests/neuron_render_shots.py."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

ASSET = ROOT / "web" / "neuron_render" / "cells.json"
JS = ROOT / "web" / "neuron_render" / "neuron_render.js"
DOC = ROOT / "docs" / "spiking" / "neuron_render.md"
API = ROOT / "docs" / "spiking" / "neuron_render_api.md"
CAPTION = ("Shapes are real reconstructed neurons (public databases); thickness, spines and myelin are drawn from published "
           "typical values. The simulated network uses point neurons (no dendrites are simulated); cells are enlarged and "
           "pulses slowed to be visible. A model, not a mind.")
TYPES = ("pyramidal", "basket", "medium_spiny", "relay", "ca1_pyramidal", "amygdala_principal")


@pytest.fixture(scope="module")
def asset():
    return json.loads(ASSET.read_text())


@pytest.fixture(scope="module")
def check():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(ROOT / "tests" / "js" / "neuron_render_check.js")], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_asset_has_radii_and_is_the_same_credited_cells(asset):
    import build_neuron_render as BNR
    old = json.loads((ROOT / "web" / "neurons_morph.json").read_text())
    assert ASSET.stat().st_size <= 400 * 1024
    assert set(asset["cells"]) == set(TYPES) == set(old["cells"]) == set(BNR.CELLS)
    md = re.sub(r"\s+", " ", (ROOT / "docs" / "spiking" / "morphology_credits.md").read_text())
    about = re.sub(r"\s+", " ", (ROOT / "web" / "about.html").read_text())
    for t, c in asset["cells"].items():
        assert c["nmo_id"] == old["cells"][t]["nmo_id"] and c["license"] == "CC BY 4.0"      # the same six cells, already credited
        assert c["nmo_id"] in md and c["nmo_id"] in about and c["paper"] in md
        assert c["radii"] in ("measured", "typical") and c["n_nodes"] <= BNR.CELLS[t][1] + 20
        assert 0 < c["n_paths"] and sum(len(p["p"]) // 4 for p in c["paths"]) == c["n_nodes"]
        for p in c["paths"]:
            assert p["k"] in (1, 2, 3) and p["o"] >= 0 and p["d0"] >= 0 and len(p["p"]) % 4 == 0 and len(p["p"]) >= 8
            radii = p["p"][3::4]
            assert min(radii) >= BNR.R_MIN and max(radii) < 20
        assert c["soma_r"] > 3 and abs(c["paths"][0]["p"][0]) < 1e-6                           # soma at the origin
    assert asset["cells"]["ca1_pyramidal"]["radii"] == "typical"                                # the 1995 file has one constant radius
    assert sum(c["radii"] == "measured" for c in asset["cells"].values()) == 5
    assert "not from the scanned person" in asset["note"] and "RRID:SCR_002145" in asset["cite"]


def test_plan_action_potential_myelin_boutons_spines(check):
    for t in TYPES:
        T = check["types"][t]
        assert T["monotone"], t                                      # the pulse never goes back in time or space along an axon
        assert T["dendrites_passive"], t                             # no pulse on dendrites (the network has none)
        assert T["myelin_before_ais"] == 0, t                        # myelin starts after the initial segment
        assert T["boutons_ok"], t
        if T["myelinated_type"] and T["axon_um"] > 300:
            assert T["myelin_um"] > 100 and T["ranvier"] >= 2, t     # internodes and nodes of Ranvier on long myelinated axons
        if not T["myelinated_type"]:
            assert T["myelin_um"] == 0 and T["ranvier"] == 0, t      # the medium spiny neuron's local axon is unmyelinated
        for lod in ("phone", "desktop"):
            G = T["geo"][lod]
            assert G["index_ok"] and G["hero_tri"] >= G["hero_tri_no_spines"] > 0 and G["mid_tri"] > 0 and G["line_segments"] > 0
            assert G["mid_spines"] == 0                              # spines, myelin and boutons only on the cells in full detail
            if T["spines_per_um"] >= 1:
                assert abs(G["spine_density"] - T["spines_per_um"]) < 0.25 * T["spines_per_um"], (t, lod, G)   # at the stated density
                assert G["spines"] >= 500 and G["spine_um"] > 300
            assert G["hero_tri"] - G["hero_tri_no_spines"] <= G["spine_tri_cap"] + 10
    assert check["types"]["pyramidal"]["geo"]["desktop"]["spines"] > check["types"]["pyramidal"]["geo"]["phone"]["spines"]
    assert check["kindOf"] == ["cortex", "striatum", "thalamus", None, "hippocampus", "amygdala"]


def test_triangle_budget_per_lod(check):
    for lod, cap in (("phone", 250000), ("desktop", 1000000)):
        L = check["lod"][lod]
        assert L["cap"] == cap
        for kind in ("cortex", "striatum", "thalamus", "hippocampus", "amygdala"):
            K = L[kind]
            assert K["triangles"] <= cap, (lod, kind, K)
            assert K["focus_keeps_spines"], (lod, kind)             # the cell in focus keeps its spines
            assert all(n >= 2 for n in K["mid_cells"])
            assert K["cells"] >= 40


def test_caption_and_constants(check):
    assert check["constants"]["caption"] == CAPTION
    assert check["constants"]["slowdown"] == 5000
    assert set(check["constants"]["kinds"]) == {"cortex", "striatum", "thalamus", "hippocampus", "amygdala"}
    src = JS.read_text()
    assert "no demo mode" in src and 'm.live === false) return' in src                 # no frames -> no activity


def test_values_documented_with_sources():
    doc = DOC.read_text()
    for needle in ("Tomassy", "Stedehouder", "Megías", "Hellwig", "Chomiak", "Hursh", "Benavides-Piccione", "g-ratio", "SLOWDOWN",
                   "spines/µm", "NeuroMorpho.Org", "not from the scanned person", "SwiftShader", "Lee WCA", "CC BY 2.5"):
        assert needle in doc, needle
    src = JS.read_text()
    for t in TYPES:
        assert re.search(rf"^\s*{t}:\s*{{ spines: [\d.]+, spineFree: \d+, myelin: ", src, re.M), t   # one table, one place
    assert API.exists() and "NeuronRender.open(" in API.read_text()


def test_brain_page_uses_the_renderer():
    html = (ROOT / "web" / "index.html").read_text()
    assert '<script src="/neuron_render/neuron_render.js"></script>' in html
    assert "NeuronRender.open(host" in html and "const N3_SHAPES = NeuronRender.CAPTION" in html
    assert "no live network: static cells, no activity" in html
    assert "n3close.onFrame(m)" in html                                                 # every spiking frame reaches the close-up
    assert "Neurons3D.closeup(" not in html                                             # the old line close-up is no longer wired
