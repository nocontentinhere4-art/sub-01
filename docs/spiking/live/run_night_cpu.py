"""CPU check of the night phase on a synthetic day of choices (#55): builds the config and runs `python -m spiking.session`
on this machine (torch CPU, 20k by default; N=..., OUT=... in the environment). Results in docs/spiking/live/results.json."""
import json, os, sys, subprocess
import numpy as np
sys.path.insert(0, ".")
from spiking.live import label_words
rng = np.random.default_rng(5)
vocab = ["read about bread", "tokyo parks", "train timetable", "cat videos", "jazz records", "old maps"]
probs = np.array([0.8, 0.2, 0.3, 0.4, 0.2, 0.3])
V = {l: 0.0 for l in vocab}
ch = []
for t in range(int(sys.argv[1]) if len(sys.argv) > 1 else 120):
    k = int(rng.integers(2, 7)); off = list(rng.choice(6, size=k, replace=False))
    fol = int(rng.integers(k))
    r = float(rng.random() < probs[off[fol]]); resp = r - 0.5
    lab = vocab[off[fol]]; delta = resp - V[lab]; V[lab] += 0.2 * delta
    ch.append({"labels": [" ".join(label_words(vocab[i])) for i in off], "followed": fol, "delta": round(delta, 4), "response": resp})
cfg = {"session_id": "cpu-check", "day": "2026-10-02", "n_neurons": int(os.environ.get("N", 20000)), "seed": 1, "max_minutes": 55,
       "phases": ["choice_train", "choice_exam"], "choices": ch, "device": "cpu"}
print("config chars", len(json.dumps(cfg)))
env = dict(os.environ, SUB01_SESSION=json.dumps(cfg), SUB01_OUT=os.environ["OUT"])
env.pop("SUB01_SERVER_URL", None)
sys.exit(subprocess.call([sys.executable, "-m", "spiking.session"], env=env))
