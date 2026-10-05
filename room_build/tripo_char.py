"""The character with Tripo (paid API: https://openapi.tripo3d.ai/v3): multiview to model, rig, retarget. One guarded task
per run, as in room_build/tripo_gen.py: the proxy supplies the key (nothing is read, printed or stored here), and a run
refuses if its <name>.task or <name>.glb already exists in --out, so a re-run never pays twice.

    python room_build/tripo_char.py balance
    python room_build/tripo_char.py model    <name> --out DIR      # multiview to model from docs/design/char-tripo/refs
    python room_build/tripo_char.py rigcheck <name> <model_task>   # free
    python room_build/tripo_char.py rig      <name> <model_task> --out DIR
    python room_build/tripo_char.py retarget <name> <rig_task> <preset> [--in-place] --out DIR

Multiview slots are named by what the picture shows, the way Tripo reads them: "left" is the view with his nose pointing
to image-left (his left side towards the camera), "right" the one with his nose pointing to image-right.
Costs (2026-10, credits): multiview 30, HD texture +10, detailed geometry +20; rig 25; retarget 10 per clip; rig check 0.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

API = "https://openapi.tripo3d.ai/v3"
DONE = ("success", "failed", "cancelled", "banned", "expired", "unknown")
REFS = Path(__file__).resolve().parent.parent / "docs/design/char-tripo/refs"
VIEWS = {"front": "body_front.png", "left": "body_side_left.png", "back": "body_back.png", "right": "body_side_right.png"}


def req(method, url, body=None):
    r = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=120) as f:
            return json.load(f)
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.code} {e.read().decode()[:500]}")


def upload(path):
    up = json.loads(subprocess.run(["curl", "-sS", "-F", f"file=@{path}", f"{API}/files"],
                                   capture_output=True, text=True, check=True).stdout)
    return up["data"]["file_token"]


def wait(tid):
    while True:
        d = req("GET", f"{API}/tasks/{tid}")["data"]
        if d["status"] in DONE:
            return d
        time.sleep(10)


def run(name, out, endpoint, body_fn):
    task, glb = out / f"{name}.task", out / f"{name}.glb"
    if task.exists() or glb.exists():
        sys.exit(f"{name}: already submitted or generated ({task.name} / {glb.name} exist); not paying again")
    tid = req("POST", f"{API}/{endpoint}", body_fn())["data"]["task_id"]
    task.write_text(tid)
    print(name, tid, flush=True)
    d = wait(tid)
    (out / f"{name}.json").write_text(json.dumps({k: d.get(k) for k in ("task_id", "type", "status", "credits_consumed",
                                                                         "input", "create_time")}, indent=1))
    print(name, d["status"], "credits", d.get("credits_consumed"), flush=True)
    if d["status"] != "success":
        sys.exit(1)
    o = d["output"]
    url = o.get("model_url") or o.get("pbr_model_url") or o.get("model")
    urllib.request.urlretrieve(url, glb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=("balance", "model", "rigcheck", "rig", "retarget"))
    ap.add_argument("args", nargs="*")
    ap.add_argument("--out", default=".")
    ap.add_argument("--in-place", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.kind == "balance":
        print(req("GET", f"{API}/account/balance")["data"])
    elif a.kind == "model":
        run(a.args[0], out, "generation/multiview-to-model", lambda: {
            "inputs": [{k: upload(REFS / v)} for k, v in VIEWS.items()],
            "model": "v3.1-20260211", "geometry_quality": "detailed", "face_limit": 150000,
            "texture": True, "pbr": True, "texture_quality": "detailed", "texture_version": "v3.5-20260815"})
    elif a.kind == "rigcheck":
        tid = req("POST", f"{API}/animations/rig-check", {"input": a.args[1]})["data"]["task_id"]
        d = wait(tid)
        print(a.args[0], tid, d["status"], d.get("output"))
    elif a.kind == "rig":
        run(a.args[0], out, "animations/rig", lambda: {"input": a.args[1], "model": "v1.0-20240301",
                                                       "rig_type": "biped", "spec": "tripo", "out_format": "glb"})
    else:
        run(a.args[0], out, "animations/retarget", lambda: {"input": a.args[1], "animation": a.args[2], "out_format": "glb",
                                                            "bake_animation": True, "animate_in_place": a.in_place})


if __name__ == "__main__":
    main()
