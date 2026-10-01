"""Pack the code and data a pod needs into environment variables (no GitHub credentials on the pod).

`pack()` -> {"SUB01_PACK_0": b64, ...}; `start_cmd()` unpacks them and runs a module; `create_body()` is the RunPod
create-pod JSON. Only the two allowed GPU types can ever be requested.
"""
import base64
import glob
import io
import json
import lzma
import os
import tarfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
IMAGE = "runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404"
GPUS = ("NVIDIA RTX A5000", "NVIDIA RTX 4000 Ada Generation")
MAX_CHARS = 900_000
REST_PREFIX = "out/rest/"
STATIC_FILES = ["spiking/region_volumes.json", "real_baseline.py", "out/connectome.npz", "out/atlas_names.json"]

UNPACK_PY = ("import os,base64,io,tarfile; ks=sorted((k for k in os.environ if k.startswith('SUB01_PACK_')), "
             "key=lambda k:int(k.rsplit('_',1)[1])); tarfile.open(fileobj=io.BytesIO(base64.b64decode("
             "''.join(os.environ[k] for k in ks))), mode='r:xz').extractall('/app')")


def default_files(root=ROOT):
    """Relative paths of the default set; spiking/*.py is globbed now, not at import time."""
    code = sorted(Path(p).relative_to(root).as_posix() for p in glob.glob(str(Path(root) / "spiking" / "*.py")))
    return code + [f for f in STATIC_FILES if f != "out/rest/qc.json"]


DEFAULT_FILES = default_files


def rest_subset(k=2, seed=0, rest_dir=None, max_trs=None):
    """k QC-kept resting-state runs re-saved with float16 ts, plus a qc.json listing only those as kept.

    Returns {arcname: bytes}; `max_trs` crops each run to its first volumes (keeps the pack small).
    """
    rest_dir = Path(rest_dir) if rest_dir else ROOT / "out" / "rest"
    qc = json.loads((rest_dir / "qc.json").read_text())
    rows = qc.get("runs", qc) if isinstance(qc, dict) else qc
    if isinstance(rows, dict):
        kept = sorted(r for r, v in rows.items() if not isinstance(v, dict) or v.get("kept", True))
    else:
        kept = sorted(r["run"] for r in rows if r.get("kept", True))
    kept = [r for r in kept if (rest_dir / f"{r}.npz").exists()]
    rng = np.random.default_rng(seed)
    pick = sorted(kept[i] for i in rng.permutation(len(kept))[:k])
    out, qc_out = {}, {}
    for stem in pick:
        d = np.load(rest_dir / f"{stem}.npz")
        ts = np.nan_to_num(d["ts"].astype(np.float32))
        if max_trs:
            ts = ts[:max_trs]
        buf = io.BytesIO()
        np.savez_compressed(buf, ts=ts.astype(np.float16), tr=d["tr"])
        out[f"{REST_PREFIX}{stem}.npz"] = buf.getvalue()
        qc_out[stem] = {"kept": True}
    out[f"{REST_PREFIX}qc.json"] = json.dumps(qc_out, indent=1).encode()
    return out


def _tar_xz(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz", preset=9 | lzma.PRESET_EXTREME) as tf:
        for name, data in members.items():
            ti = tarfile.TarInfo(name)
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def pack(files=None, extra=None, chunk=96_000, root=ROOT, k=2, max_trs=None, verbose=False):
    """tar.xz + base64 chunked env vars. `files`: relative paths (default set + rest_subset); `extra`: {arc: bytes}."""
    root = Path(root)
    members = {}
    if files is None:
        for rel in default_files(root):
            members[rel] = (root / rel).read_bytes()
        members.update(rest_subset(k=k, rest_dir=root / "out" / "rest", max_trs=max_trs))
    else:
        for rel in files:
            members[str(rel)] = (root / rel).read_bytes()
    members.update(extra or {})
    b64 = base64.b64encode(_tar_xz(members)).decode()
    env = {f"SUB01_PACK_{i}": b64[j:j + chunk] for i, j in enumerate(range(0, len(b64), chunk))}
    total = len(b64)
    if verbose:
        print(f"pack: {len(members)} files, {total} characters in {len(env)} variables", flush=True)
    if total > MAX_CHARS:
        raise ValueError(f"pack is {total} characters (limit {MAX_CHARS}); lower k or max_trs")
    return env


def packed_chars(env):
    return sum(len(v) for k, v in env.items() if k.startswith("SUB01_PACK_"))


def unpack(env, dest):
    """What the pod runs at start (same logic as UNPACK_PY); returns the extracted file names."""
    ks = sorted((k for k in env if k.startswith("SUB01_PACK_")), key=lambda k: int(k.rsplit("_", 1)[1]))
    raw = base64.b64decode("".join(env[k] for k in ks))
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:xz") as tf:
        names = tf.getnames()
        tf.extractall(dest, filter="data")
    return names


def start_cmd(module="spiking.session"):
    """The pod's docker start command: unpack, serve /out on 8000, run the module, keep results readable 10 min."""
    script = (f"mkdir -p /app /out && cd /app\n"
              f"python3 -c \"{UNPACK_PY}\"\n"
              f"python3 -c 'import numpy, aiohttp' 2>/dev/null || pip install -q numpy aiohttp > /out/pip.log 2>&1\n"
              f"(python3 -m http.server 8000 -d /out >/dev/null 2>&1 &)\n"
              f"python3 -m {module} > /out/session.log 2>&1; echo $? > /out/exit_code; sleep 600")
    return ["bash", "-c", script]


def create_body(env, name, gpu="NVIDIA RTX A5000", module="spiking.session"):
    """RunPod create-pod JSON: one on-demand secure-cloud GPU, no volume, port 8000 proxied."""
    assert gpu in GPUS, f"GPU type not allowed: {gpu}"
    return {"name": name, "imageName": IMAGE, "gpuTypeIds": [gpu], "gpuCount": 1, "interruptible": False,
            "cloudType": "SECURE", "containerDiskInGb": 30, "volumeInGb": 0, "ports": ["8000/http"],
            "env": dict(env), "dockerStartCmd": start_cmd(module)}


if __name__ == "__main__":
    e = pack(verbose=True)
    print("total characters:", packed_chars(e))
