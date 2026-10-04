"""What his screens show -> the predicted response of a human cortex, region by region (our 214 regions).

A clean-room encoding model (docs/encoding/REPORT.md): ridge regressions with HRF delays from image features
(OpenCLIP ViT-B-32 trained on LAION-2B, MIT) and text features (all-MiniLM-L6-v2, Apache-2.0) to the BOLD response
of public fMRI participants (Emo-FilM, OpenNeuro ds004892, CC0: CC BY Blender films; the Alice dataset, ds002322, CC0:
a public-domain story), cross-validated by participant and by stimulus. Inspired by the idea of Meta's TRIBE
(d'Ascoli et al. 2025) -- nothing of it (code, weights, outputs) is used.

Runtime: every SENSE_EVERY_S while he looks at a screen, the latest screenshot (desk / phone) goes through the
image encoder (int8 ONNX, ~45 ms on one core, in a worker thread), the page title / reading text through the text
encoder, and the fitted weights give a predicted response per region in units of its training spread (z). Only
regions whose held-out prediction beat the controls get a drive: drive_i = GAIN x weight_i x clip(z_i). The live
server holds it as a sustained stimulus (it settles at `drive` with the brain's 2 s stimulus decay), scaled by the
sleep engine's gain. Without the model files (or with SUB01_SENSORY=0) nothing here runs and the old keyword ->
network rules drive the brain as before.

Model files: downloaded once into SUB01_MODELS_DIR (default <data-dir>/models) from the pinned Hugging Face commits
in SOURCES, each checked against its sha256; the image tower is cut out of the CLIP graph in a child process (the
full graph is never loaded in the server). SUB01_SENSORY_DOWNLOAD=0 never downloads (then the files must be there).

Wording on the pages: LABEL. A model of an average human cortex, not his mind, and not what he "understands".
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ENC_DIR = HERE / "out" / "encoding"            # the fitted weights (small, in git)
SENSE_EVERY_S = 4.0                             # a new prediction at most this often per screen
STALE_S = 12.0                                  # a prediction older than this stops driving the brain
GAIN = float(os.environ.get("SUB01_SENSORY_GAIN", "3.0"))   # drive per unit z (a chat rule gives 6-8 a group)
ZCLIP = 2.5
FEATURE_CLIP = 3.0                              # input features past 3 SD of the training stimuli are held there
TOP_N = 8
LABEL = ("predicted response of a human cortex to this image, learned from public fMRI data; a model, not a mind")
UNFAMILIAR = "far from the films the model learned from: a rougher guess (half the drive)"
UNFAMILIAR_SCALE = 0.5                          # the drive of such a picture
TEXT_LABEL = ("predicted response of a human cortex to this text, learned from public fMRI data (people listening "
              "to a story); a model, not a mind")
HF = "https://huggingface.co/{repo}/resolve/{rev}/{path}"
SOURCES = {   # pinned files; every one is in docs/encoding/LICENSES.md (tests/test_sensory.py checks)
    "clip": {"repo": "onnx-community/CLIP-ViT-B-32-laion2B-s34B-b79K-ONNX",
             "rev": "de693d0c5a5b263ae94ece9bf751e0cda14305d8", "path": "onnx/model_int8.onnx",
             "sha256": "2ac8410fe198fbd003cd97460bdd68653d99c33f53311881cd306190067aee9b",
             "file": "clip_int8.onnx", "licence": "MIT"},
    "minilm": {"repo": "sentence-transformers/all-MiniLM-L6-v2",
               "rev": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41", "path": "onnx/model_quint8_avx2.onnx",
               "sha256": "b941bf19f1f1283680f449fa6a7336bb5600bdcd5f84d10ddc5cd72218a0fd21",
               "file": "minilm_quint8_avx2.onnx", "licence": "Apache-2.0"},
    "minilm_tokenizer": {"repo": "sentence-transformers/all-MiniLM-L6-v2",
                         "rev": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41", "path": "tokenizer.json",
                         "sha256": "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
                         "file": "minilm_tokenizer.json", "licence": "Apache-2.0"},
}
VISION_FILE = "clip_vision_int8.onnx"           # the image tower of SOURCES["clip"], cut by extract_vision()
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
SCENE_FULL = 32.0                               # = browse.SCENE_FULL: a full cut between two screenshots
TEXT_MAX_TOKENS = 128

NETS = {"Vis": "visual", "SomMot": "somatomotor", "DorsAttn": "dorsal attention", "SalVentAttn": "salience",
        "Limbic": "limbic", "Cont": "control", "Default": "default mode"}
PARTS = {"Temp": "temporal", "TempOcc": "temporo-occipital", "TempPole": "temporal pole", "Par": "parietal",
         "ParOcc": "parieto-occipital", "ParOper": "parietal operculum", "PrCv": "ventral precentral",
         "PrC": "precentral", "FEF": "frontal eye field", "FrOperIns": "frontal operculum / insula",
         "PFCl": "lateral prefrontal", "PFCm": "medial prefrontal", "PFCv": "ventral prefrontal", "PFCd": "dorsal prefrontal",
         "PFCdPFCm": "dorsomedial prefrontal", "PFClv": "ventrolateral prefrontal", "PFC": "prefrontal",
         "OFC": "orbitofrontal", "Cing": "cingulate", "pCun": "precuneus", "pCunPCC": "precuneus / posterior cingulate",
         "PCC": "posterior cingulate", "Med": "medial", "Post": "posterior", "Ins": "insula", "Aud": "auditory",
         "IPL": "inferior parietal", "IPS": "intraparietal", "SPL": "superior parietal", "PHC": "parahippocampal",
         "Rsp": "retrosplenial", "Striate": "striate", "ExStr": "extrastriate", "TempPar": "temporo-parietal"}


def region_label(name):
    """'7Networks_LH_Default_Temp_3' -> 'left default mode · temporal 3'; subcortical names as they are."""
    if not name.startswith("7Networks_"):
        return name.lower().capitalize()
    bits = name.split("_")[1:]
    side = {"LH": "left", "RH": "right"}.get(bits[0], bits[0])
    net = NETS.get(bits[1], bits[1])
    rest = [PARTS.get(b, b) for b in bits[2:]]
    num = rest.pop() if rest and rest[-1].isdigit() else ""
    return f"{side} {net}" + (f" · {' '.join(rest)}" if rest else "") + (f" {num}" if num else "")


def network_of(name):
    if not name.startswith("7Networks_"):
        for k, g in (("Accumbens", "reward"), ("Caudate", "reward"), ("Putamen", "reward"), ("Amygdala", "fear"),
                     ("Hippocampus", "memory"), ("Thalamus", "relay"), ("Pallidum", "motor loop")):
            if k in name:
                return g
        return "subcortical"
    return NETS.get(name.split("_")[2], "cortex")


# --- model files ---------------------------------------------------------------------------------------------
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def download(src, dest, timeout=60):
    """One pinned file -> dest, checked against its sha256 (a mismatch is deleted and raises)."""
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(HF.format(**src), headers={"User-Agent": "sub01-sensory"})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
        while block := r.read(1 << 20):
            f.write(block)
    if sha256(part) != src["sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError(f"{dest.name}: sha256 mismatch")
    os.replace(part, dest)
    return dest


def extract_vision(src, dest):
    """Cut the image tower (pixel_values -> image_embeds) out of the full CLIP graph; runs in a child process so the
    server never holds the full graph (~0.8 GB while cutting)."""
    import onnx
    onnx.utils.extract_model(str(src), str(dest), ["pixel_values"], ["image_embeds"])


def ensure_models(models_dir, download_ok=True, log=print):
    """Make sure the encoder files are in `models_dir`. Returns {"vision": path|None, "text": (model, tokenizer)|None,
    "why": reason when something is missing}."""
    d = Path(models_dir)
    d.mkdir(parents=True, exist_ok=True)
    out, why = {"vision": None, "text": None}, []
    vis, marker = d / VISION_FILE, d / (VISION_FILE + ".source")
    if not (vis.exists() and marker.exists() and marker.read_text().strip() == SOURCES["clip"]["sha256"]):
        src = d / SOURCES["clip"]["file"]
        try:
            if not src.exists():
                if not download_ok:
                    raise FileNotFoundError(f"{src.name} missing (downloads off)")
                log(f"sensory: downloading {SOURCES['clip']['repo']} ({SOURCES['clip']['path']})")
                download(SOURCES["clip"], src)
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--extract", str(src), str(vis)],
                           check=True, timeout=600, env={k: v for k, v in os.environ.items() if k in (
                               "PATH", "HOME", "LANG", "PYTHONPATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS")})
            marker.write_text(SOURCES["clip"]["sha256"])
            src.unlink(missing_ok=True)                    # the image tower is all we keep (89 MB of 153)
        except Exception as e:
            why.append(f"image model: {str(e)[:120]}")
    if vis.exists() and marker.exists():
        out["vision"] = vis
    files = []
    for key in ("minilm", "minilm_tokenizer"):
        p = d / SOURCES[key]["file"]
        try:
            if not p.exists():
                if not download_ok:
                    raise FileNotFoundError(f"{p.name} missing (downloads off)")
                log(f"sensory: downloading {SOURCES[key]['repo']} ({SOURCES[key]['path']})")
                download(SOURCES[key], p)
            files.append(p)
        except Exception as e:
            why.append(f"text model: {str(e)[:120]}")
    if len(files) == 2:
        out["text"] = tuple(files)
    out["why"] = "; ".join(why)
    return out


# --- encoders (the same code computes the training features: analysis/encoding/features_*.py) -----------------
def _session(path, threads=1):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.inter_op_num_threads = 1
    so.log_severity_level = 3
    return ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])


def clip_pixels(img):
    """PIL image -> (3, 224, 224) float32 as CLIPImageProcessor: shortest edge 224 (bicubic), centre crop, normalise."""
    from PIL import Image
    img = img.convert("RGB")
    w, h = img.size
    s = 224 / min(w, h)
    img = img.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BICUBIC)
    w, h = img.size
    l, t = (w - 224) // 2, (h - 224) // 2
    x = np.asarray(img.crop((l, t, l + 224, t + 224)), np.float32) / 255.0
    return ((x - CLIP_MEAN) / CLIP_STD).transpose(2, 0, 1)


def low_level(img, prev=None):
    """[mean luminance, RMS contrast] of the picture (0..1) and its change from `prev` (0..1, browse.scene_change's
    measure: 64x36 grey thumbnails, SCENE_FULL = a full cut). `prev` is the previous 64x36 grey thumbnail or None
    (then the change is unknown: nan, held at the training mean by Encoding.predict)."""
    g = np.asarray(img.convert("L").resize((64, 36)), np.float32)
    change = np.nan if prev is None else min(1.0, float(np.abs(g - prev).mean()) / SCENE_FULL)   # nan: unknown
    return np.array([g.mean() / 255.0, g.std() / 255.0, change], np.float32), g


class VisionEncoder:
    def __init__(self, path, threads=1):
        self.s = _session(path, threads)

    def embed(self, pixels):
        """(N, 3, 224, 224) -> (N, 512) unit image embeddings."""
        return self.s.run(["image_embeds"], {"pixel_values": np.asarray(pixels, np.float32)})[0]


class TextEncoder:
    def __init__(self, model, tokenizer, threads=1):
        from tokenizers import Tokenizer
        self.s = _session(model, threads)
        self.tok = Tokenizer.from_file(str(tokenizer))
        self.tok.enable_truncation(TEXT_MAX_TOKENS)
        self.tok.enable_padding()

    def embed(self, texts):
        """list of str -> (N, 384) unit sentence embeddings (mean pooling, as sentence-transformers)."""
        enc = self.tok.encode_batch([t or "" for t in texts])
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        h = self.s.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask,
                                                "token_type_ids": np.zeros_like(ids)})[0]
        v = (h * mask[..., None]).sum(1) / np.maximum(mask.sum(1, keepdims=True), 1)
        return (v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)).astype(np.float32)


# --- the fitted encoding model ------------------------------------------------------------------------------
class Encoding:
    """One fitted model (out/encoding/<kind>.npz, written by analysis/encoding/fit.py): features -> region z."""

    def __init__(self, path):
        z = np.load(path, allow_pickle=False)
        self.W, self.mu, self.sd = z["W"], z["mu"], z["sd"]
        self.pred_mu, self.pred_sd = z["pred_mu"], z["pred_sd"]
        self.weight, self.r, self.ceiling = z["weight"], z["r"], z["ceiling"]
        self.zero = z["runtime_zero"].astype(bool)          # nuisance features held at their training mean
        self.names = [str(x) for x in z["names"]]
        self.ref = z["ref"].astype(np.float32) if "ref" in z.files else None
        self.ref_floor = float(z["ref_floor"]) if "ref_floor" in z.files else None

    def predict(self, x):
        f = np.clip((np.asarray(x, np.float64) - self.mu) / self.sd, -FEATURE_CLIP, FEATURE_CLIP)
        f[self.zero | np.isnan(f)] = 0.0                    # nuisance / unknown features at their training mean
        return (f @ self.W - self.pred_mu) / self.pred_sd   # z per region (0 = the training average)

    def familiarity(self, emb):
        """(nearest cosine to the training stimuli, familiar?) -- far from all of them, the prediction is a guess."""
        if self.ref is None:
            return None, None
        sim = float((self.ref @ (emb / max(np.linalg.norm(emb), 1e-9))).max())
        return round(sim, 3), sim >= self.ref_floor


class Sensory:
    """The live server's sensory model. `start()` loads (downloads once) in a thread; `see` / `read` are blocking
    (run them in an executor); `drive_now()` is what the brain tick adds."""

    def __init__(self, models_dir, enc_dir=ENC_DIR, download_ok=True, enabled=True):
        self.models_dir, self.enc_dir = Path(models_dir), Path(enc_dir)
        self.download_ok, self.enabled = download_ok, enabled
        self.state, self.why = ("off", "SUB01_SENSORY=0") if not enabled else ("loading", "")
        self.vision = self.text = None
        self.enc = {}
        self.names = None
        self.prev_thumb = {}
        self.drive = None                               # (214,) current drive, None = nothing seen recently
        self.drive_t = 0.0
        self.last = None                                # public view of the last prediction
        self.ms = []                                    # CPU ms per prediction (thread time), the last 50
        self.lock = threading.Lock()
        self.busy = False

    @classmethod
    def from_env(cls, data_dir):
        return cls(os.environ.get("SUB01_MODELS_DIR") or Path(data_dir) / "models",
                   download_ok=os.environ.get("SUB01_SENSORY_DOWNLOAD", "1") != "0",
                   enabled=os.environ.get("SUB01_SENSORY", "1") != "0")

    @property
    def ready(self):
        return self.state == "on"

    def start(self, background=True):
        if not self.enabled:
            return self
        if background:
            threading.Thread(target=self.load, name="sensory-load", daemon=True).start()
        else:
            self.load()
        return self

    def load(self):
        try:
            for kind in ("vision", "text"):
                p = self.enc_dir / f"{kind}.npz"
                if p.exists():
                    self.enc[kind] = Encoding(p)
            if not self.enc:
                raise FileNotFoundError("no fitted weights in out/encoding/")
            self.names = json.load(open(HERE / "out" / "atlas_names.json"))
            files = ensure_models(self.models_dir, self.download_ok, log=lambda m: print(m, flush=True))
            if files["vision"] and "vision" in self.enc:
                self.vision = VisionEncoder(files["vision"])
            if files["text"] and "text" in self.enc:
                self.text = TextEncoder(*files["text"])
            if not (self.vision or self.text):
                raise FileNotFoundError(files["why"] or "no encoder")
            self.state, self.why = "on", files["why"]
            print("sensory: on (" + ", ".join(k for k in ("vision", "text") if getattr(self, k)) + ")"
                  + (f"; {files['why']}" if files["why"] else ""), flush=True)
        except Exception as e:
            self.state, self.why = "fallback", f"keyword rules (sensory model unavailable: {str(e)[:160]})"
            print("sensory:", self.why, flush=True)

    # blocking parts (worker thread) ------------------------------------------------------------------------------
    def see(self, jpeg, device="desk", text="", t=None):
        """A screenshot (+ the page title) -> sets the drive and the public view; returns the view."""
        from PIL import Image
        if not (self.ready and self.vision):
            return None
        c0 = time.thread_time()
        img = Image.open(io.BytesIO(jpeg))
        ll, thumb = low_level(img, self.prev_thumb.get(device))
        self.prev_thumb[device] = thumb
        emb = self.vision.embed(clip_pixels(img)[None])[0]
        z = self.enc["vision"].predict(np.concatenate([emb, ll]))
        w = self.enc["vision"].weight
        drive = w * np.clip(z, -ZCLIP, ZCLIP)
        if text and self.text and "text" in self.enc:          # the words on the screen (its title) add theirs
            zt = self.enc["text"].predict(np.concatenate([self.text.embed([text])[0], np.zeros(2, np.float32)]))
            drive = drive + self.enc["text"].weight * np.clip(zt, -ZCLIP, ZCLIP)
        sim, familiar = self.enc["vision"].familiarity(emb)
        if familiar is False:                                    # far from every film frame: trusted less
            drive = drive * UNFAMILIAR_SCALE
        view = self._set(GAIN * drive, z, w, "image", device, t, change=None if np.isnan(ll[2]) else float(ll[2]),
                         similarity=sim, familiar=familiar,
                         note=None if familiar in (None, True) else UNFAMILIAR)
        self._cpu(c0)
        return view

    def read(self, text, t=None):
        """A text he reads -> its predicted drive (an impulse for the brain, like a reading stimulus) and the view."""
        if not (self.ready and self.text and text):
            return None, None
        c0 = time.thread_time()
        z = self.enc["text"].predict(np.concatenate([self.text.embed([text])[0], np.zeros(2, np.float32)]))
        w = self.enc["text"].weight
        drive = GAIN * w * np.clip(z, -ZCLIP, ZCLIP)
        self._cpu(c0)
        return drive, self._view(drive, z, w, "text", None, t)

    def _cpu(self, c0):
        self.ms = (self.ms + [round(1000 * (time.thread_time() - c0), 1)])[-50:]

    def _set(self, drive, z, w, kind, device, t, **extra):
        view = self._view(drive, z, w, kind, device, t, **extra)
        with self.lock:
            self.drive, self.drive_t, self.last = drive, time.time(), view
        return view

    def _view(self, drive, z, w, kind, device, t, **extra):
        order = [i for i in np.argsort(-drive) if drive[i] > 0][:TOP_N]
        nets = {}
        for i, nm in enumerate(self.names):
            if w[i] > 0:
                nets.setdefault(network_of(nm), []).append(float(drive[i]))
        return {"kind": kind, "device": device, "t": round(t if t is not None else time.time(), 1),
                "label": LABEL if kind == "image" else TEXT_LABEL,
                "top": [{"i": int(i), "name": self.names[i], "label": region_label(self.names[i]),
                         "net": network_of(self.names[i]), "z": round(float(z[i]), 2),
                         "drive": round(float(drive[i]), 2)} for i in order],
                "networks": {k: round(float(np.mean(v)), 2) for k, v in sorted(nets.items())},
                "regions_driven": int((w > 0).sum()), **extra}

    # the tick (cheap) ---------------------------------------------------------------------------------------------
    def drive_now(self, now=None):
        """The current (214,) drive, or None when nothing was seen for STALE_S."""
        now = time.time() if now is None else now
        with self.lock:
            if self.drive is None or now - self.drive_t > STALE_S:
                return None
            return self.drive

    def clear(self):
        with self.lock:
            self.drive = None
        self.prev_thumb.clear()

    def due(self, now=None):
        now = time.time() if now is None else now
        return self.ready and self.vision is not None and not self.busy and now - self.drive_t >= SENSE_EVERY_S

    def status(self):
        v = {"state": self.state, "why": self.why, "label": LABEL,
             "vision": bool(self.vision), "text": bool(self.text),
             "cpu_ms": {"mean": round(float(np.mean(self.ms)), 1), "max": max(self.ms), "n": len(self.ms)}
             if self.ms else None, "every_s": SENSE_EVERY_S, "gain": GAIN}
        for k, e in self.enc.items():
            v[k + "_model"] = {"regions_driven": int((e.weight > 0).sum()),
                               "median_r_driven": round(float(np.median(e.r[e.weight > 0])), 3) if (e.weight > 0).any()
                               else None}
        v["last"] = self.last if self.last and time.time() - self.last["t"] < 120 else None
        return v


def to_brain(vec214, atlas_names, brain_names):
    """Reorder a 214-vector onto the brain's regions (brain_sim drops regions no fibre reached)."""
    pos = {n: i for i, n in enumerate(atlas_names)}
    return np.array([vec214[pos[n]] for n in brain_names])


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--extract":
        extract_vision(sys.argv[2], sys.argv[3])
    else:
        print("usage: python sensory.py --extract <clip.onnx> <vision.onnx>")
