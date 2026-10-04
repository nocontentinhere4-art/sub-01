"""The encoding model (sensory.py, analysis/encoding/, docs/encoding/): licences, reproducible scores, the fallback
without model files, and the brain tick with the sensory drive staying under its 50 ms budget.

The encoder files (~110 MB, downloaded at runtime) are not in git: the tests that need them are skipped unless they
are in SUB01_MODELS_DIR (or out/encoding_work/models). Everything else runs on a fresh clone."""
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis" / "encoding"))
import sensory  # noqa: E402

ENC = ROOT / "out" / "encoding"
MANIFEST = ENC / "MANIFEST.json"
LICENSES = ROOT / "docs" / "encoding" / "LICENSES.md"
ALLOWED = {"CC0-1.0", "PDDL-1.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0", "MIT", "Apache-2.0", "BSD-3-Clause",
           "Public-Domain"}
MODELS = Path(os.environ.get("SUB01_MODELS_DIR", ROOT / "out" / "encoding_work" / "models"))


def have_models():
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError:
        return False
    return (MODELS / sensory.VISION_FILE).exists() and (MODELS / sensory.SOURCES["minilm"]["file"]).exists()


# --- licences ------------------------------------------------------------------------------------------------------
def test_manifest_covers_every_asset_with_a_commercial_licence():
    man = json.load(open(MANIFEST))
    assets = {a["id"]: a for a in man["assets"]}
    for a in man["assets"]:
        assert a["licence"] in ALLOWED, a
        assert a.get("url", "").startswith("https://"), a
        assert a.get("commercial_use") is True, a
        assert a.get("agreement_required") is False, a
    # every file shipped in out/encoding/ is an asset of the manifest
    for f in ENC.iterdir():
        if f.name != "MANIFEST.json":
            assert f.name in assets, f"{f.name} has no manifest entry"
    # every pinned model file the server downloads is listed with the same commit and sha256
    for key, src in sensory.SOURCES.items():
        a = assets[src["file"]]
        assert a["sha256"] == src["sha256"] and src["rev"] in a["url"], key
    # every dataset / film / model used to fit is listed
    for need in ("ds004892", "ds002322", "BigBuckBunny", "Sintel", "TearsOfSteel", "schaefer2018",
                 "harvard_oxford_sub", "alice_text", "librivox_alice"):
        assert any(need in i for i in assets), need


def test_licences_doc_names_every_manifest_entry_and_excludes():
    doc = LICENSES.read_text()
    man = json.load(open(MANIFEST))
    for a in man["assets"]:
        assert a["url"] in doc, f"{a['id']}: no link in LICENSES.md"
    for excluded in ("TRIBE", "Narratives", "NonCommercial", "HCP", "NSD", "CNeuroMod"):
        assert excluded in doc, excluded


def test_no_noncommercial_film_is_used():
    import fit
    nc = {"AfterTheRain", "Chatter", "Spaceman", "TheSecretNumber", "ToClaireFromSonny"}
    import extract_emofilm
    assert not nc & set(extract_emofilm.FILMS)
    scores = json.load(open(ENC / "scores.json"))
    assert not nc & set(scores["vision"]["stimuli"])
    assert fit.CFG["text"]["runtime_zero"] == ["words", "envelope"]


# --- scores --------------------------------------------------------------------------------------------------------
def test_cross_validated_scores_reproduce():
    import fit
    assert fit.check(["vision", "text"])


def test_report_numbers_match_scores():
    scores = json.load(open(ENC / "scores.json"))
    report = (ROOT / "docs" / "encoding" / "REPORT.md").read_text()
    for kind in ("vision", "text"):
        h = scores[kind]["headline"]
        main = h["semantic" if kind == "text" else "real"]
        assert f"{main['median_r']:.3f}" in report, kind
        assert f"{h['shuffled']['median_r']:.3f}" in report and f"{h['shifted']['median_r']:.3f}" in report, kind


def test_runtime_weights_only_on_regions_that_beat_the_controls():
    scores = json.load(open(ENC / "scores.json"))
    for kind in ("vision", "text"):
        e = sensory.Encoding(ENC / f"{kind}.npz")
        s = scores[kind]["semantic" if kind == "text" else "real"]
        q, r = np.array(s["q"]), np.array(s["r"])
        on = e.weight > 0
        assert (q[on] < 0.05).all() and (r[on] > np.array(scores[kind]["shuffled"]["r"])[on]).all()
        assert (r[on] > np.array(scores[kind]["shifted"]["r"])[on]).all()
        assert e.weight.max() <= 1.0 and e.W.shape == (len(e.names), 214)


# --- runtime: fallback, mapping, tick budget --------------------------------------------------------------------------
def test_falls_back_cleanly_without_model_files(tmp_path):
    sn = sensory.Sensory(tmp_path / "models", download_ok=False).start(background=False)
    assert sn.state == "fallback" and not sn.ready and "keyword rules" in sn.why
    assert sn.drive_now() is None and not sn.due()
    assert sn.see(b"not a jpeg") is None and sn.read("hello") == (None, None)
    st = sn.status()
    assert st["state"] == "fallback" and st["last"] is None


def test_falls_back_without_fitted_weights(tmp_path):
    sn = sensory.Sensory(tmp_path / "models", enc_dir=tmp_path / "none", download_ok=False).start(background=False)
    assert sn.state == "fallback" and "no fitted weights" in sn.why


def test_off_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("SUB01_SENSORY", "0")
    sn = sensory.Sensory.from_env(tmp_path).start()
    assert sn.state == "off" and not sn.ready


class FakeVision:
    def embed(self, pixels):
        rng = np.random.default_rng(int(np.abs(pixels).sum() * 1000) % 2 ** 32)
        v = rng.normal(size=(len(pixels), 512)).astype(np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


def jpeg(color=(200, 40, 40), size=(640, 360)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, color)
    ImageDraw.Draw(im).rectangle([100, 80, 300, 260], fill=(20, 20, 220))
    b = io.BytesIO()
    im.save(b, "JPEG")
    return b.getvalue()


def ready_with_fakes(tmp_path):
    sn = sensory.Sensory(tmp_path, download_ok=False)
    sn.enc = {"vision": sensory.Encoding(ENC / "vision.npz")}
    sn.names = json.load(open(ROOT / "out" / "atlas_names.json"))
    sn.vision, sn.state = FakeVision(), "on"
    return sn


def test_prediction_view_and_drive(tmp_path):
    sn = ready_with_fakes(tmp_path)
    view = sn.see(jpeg(), "phone", t=1.0)
    d = sn.drive_now()
    assert d.shape == (214,) and np.isfinite(d).all()
    w = sn.enc["vision"].weight
    assert (d[w == 0] == 0).all()                                     # unreliable regions are never driven
    assert np.abs(d).max() <= sensory.GAIN * sensory.ZCLIP + 1e-9
    assert view["label"] == sensory.LABEL and "a model, not a mind" in view["label"]
    assert all(r["drive"] > 0 and r["label"] for r in view["top"])
    assert sn.drive_now(time.time() + sensory.STALE_S + 1) is None    # stale: the drive stops
    assert sn.status()["cpu_ms"]["n"] == 1


def test_region_labels():
    assert sensory.region_label("7Networks_LH_Vis_3") == "left visual 3"
    assert sensory.region_label("7Networks_RH_Default_pCunPCC_2") == "right default mode · precuneus / posterior cingulate 2"
    assert sensory.network_of("Left Amygdala") == "fear"


def tick_times(drive, n=60):
    """The live tick's brain part (TICK of simulation in 5-step blocks), with the sensory drive applied as run_brain
    does; seconds per tick."""
    from brain_sim import Brain
    b = Brain(slow=False)
    atlas = json.load(open(ROOT / "out" / "atlas_names.json"))
    idx = np.array([atlas.index(nm) for nm in b.names])
    TICK = 0.05
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        if drive is not None:
            b.stim += drive()[idx] * (TICK / 2.0)
        for _ in range(int(TICK / b.dt) // 5):
            b.step(5)
        out.append(time.perf_counter() - t0)
    return np.array(out[5:])


def test_tick_stays_under_budget_with_the_sensory_drive(tmp_path):
    sn = ready_with_fakes(tmp_path)
    sn.see(jpeg())
    base = tick_times(None)
    with_drive = tick_times(sn.drive_now)
    assert np.percentile(with_drive, 95) < 0.050
    assert np.median(with_drive) < np.median(base) * 1.5 + 0.002      # the drive itself is one vector add


@pytest.mark.skipif(not have_models(), reason="encoder files not downloaded (they are fetched at runtime)")
def test_real_encoders_cpu_cost_and_tick_while_predicting(tmp_path):
    import threading
    sn = sensory.Sensory(MODELS, download_ok=False).start(background=False)
    assert sn.ready and sn.vision and sn.text
    for _ in range(3):
        sn.see(jpeg(), text="a cat sleeping on a sofa")
    assert sn.status()["cpu_ms"]["mean"] < 400                         # one core; ~50-100 ms measured
    stop = threading.Event()

    def busy():                                                       # predictions back to back (worst case)
        while not stop.is_set():
            sn.see(jpeg((10, 120, 10)))
    th = threading.Thread(target=busy)
    th.start()
    try:
        t = tick_times(sn.drive_now)
    finally:
        stop.set()
        th.join()
    assert np.percentile(t, 95) < 0.050
    _, view = sn.read("The king and queen of hearts were seated on their throne when they arrived.")
    assert view["kind"] == "text" and "listening" in view["label"]


def test_live_server_wiring():
    src = (ROOT / "live_server.py").read_text()
    assert "sensory_mod.Sensory.from_env(data_dir).start()" in src
    assert re.search(r"not self\.sensory_sees\(\):\s*\n\s*self\.video_drive", src)       # the rule stays the fallback
    assert "run_in_executor(None, sn.see" in src and "run_in_executor(\n                    None, sn.read" in src
    assert '"/api/sensory"' in src
    page = (ROOT / "web" / "index.html").read_text()
    assert "What it's seeing → predicted cortex" in page and 'm.type === "sensory"' in page
