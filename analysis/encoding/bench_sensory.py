"""CPU cost of the sensory model and the brain tick with it (docs/encoding/REPORT.md § cost).

The live tick's brain part (TICK = 50 ms of simulation, the sustained sensory drive added as run_brain does) runs for
DURATION_S per condition while a worker thread makes predictions on real screenshots, like the live server's
executor:  off (no predictions) | live (one every SENSE_EVERY_S) | flat out (back to back, the worst case).
Reports tick p50 / p95 / max, CPU ms per prediction (thread time) and the share of one core.

Also prints, for each example picture, the top predicted regions (the "what it's seeing" card).
Run: python analysis/encoding/bench_sensory.py [--models out/encoding_work/models] [--images a.jpg b.jpg ...]
"""
import argparse
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import sensory  # noqa: E402
from brain_sim import Brain  # noqa: E402

TICK = 0.05
DURATION_S = 30.0


def run(sn, images, mode):
    b = Brain()
    atlas = json.load(open(ROOT / "out" / "atlas_names.json"))
    idx = np.array([atlas.index(n) for n in b.names])
    stop = threading.Event()
    n_pred = [0]

    def worker():
        i = 0
        while not stop.is_set():
            sn.see(images[i % len(images)], "desk", text="")
            n_pred[0] += 1
            i += 1
            if mode == "live":
                stop.wait(sensory.SENSE_EVERY_S)
    th = threading.Thread(target=worker, daemon=True) if mode != "off" else None
    if th:
        th.start()
    ticks, steps = [], int(TICK / b.dt)
    c0, t_end = time.process_time(), time.time() + DURATION_S
    next_t = time.time()
    while time.time() < t_end:
        t0 = time.perf_counter()
        d = sn.drive_now()
        if d is not None:
            b.stim += d[idx] * (TICK / 2.0)
        for _ in range(steps // 5):
            b.step(5)
        ticks.append(time.perf_counter() - t0)
        next_t += TICK
        time.sleep(max(0.0, next_t - time.time()))
    cpu = time.process_time() - c0
    stop.set()
    if th:
        th.join()
    t = np.array(ticks[10:]) * 1000
    return {"mode": mode, "ticks": len(t), "tick_ms_p50": round(float(np.median(t)), 2),
            "tick_ms_p95": round(float(np.percentile(t, 95)), 2), "tick_ms_max": round(float(t.max()), 2),
            "late_ticks_over_50ms": int((t > 50).sum()), "predictions": n_pred[0],
            "process_cpu_share_of_one_core": round(cpu / DURATION_S, 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=str(ROOT / "out" / "encoding_work" / "models"))
    ap.add_argument("--images", nargs="*", default=[])
    a = ap.parse_args()
    sn = sensory.Sensory(a.models, download_ok=False).start(background=False)
    assert sn.ready, sn.why
    images = [open(p, "rb").read() for p in a.images] or [open(ROOT / "web" / "room" / "x.jpg", "rb").read()]
    sn.ms = []
    for p, img in zip(a.images, images):
        sn.prev_thumb.clear()
        v = sn.see(img, "desk")
        print(Path(p).name, "->", [(r["label"], r["drive"]) for r in v["top"][:5]], json.dumps(v["networks"]))
    one = list(sn.ms)
    out = {"cpu_ms_per_prediction": {"mean": round(float(np.mean(one)), 1), "max": max(one), "n": len(one)}}
    for mode in ("off", "live", "flat_out"):
        sn.ms = []
        r = run(sn, images, mode)
        if sn.ms:
            r["cpu_ms_per_prediction_mean"] = round(float(np.mean(sn.ms)), 1)
        out[mode] = r
        print(json.dumps(r), flush=True)
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
