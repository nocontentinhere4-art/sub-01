"""Text features of the Alice story (ds002322) on the scans' 2 s grid, with the runtime text encoder of sensory.py
(all-MiniLM-L6-v2, Apache-2.0, int8 ONNX).

Per 2 s bin [g, g + 2) of the story (g = 20 + 2k s from the audio start: the first preprocessed volume):
  - emb (384): the sentence embedding of the words heard in the last WINDOW_S (onsets in [g + 2 - WINDOW_S, g + 2));
    at runtime the same encoder embeds the page title / the reading's text;
  - words: words starting in the bin (speech rate) and envelope: the audio's RMS in the bin (LibriVox reading, public
    domain). Both are nuisance regressors: fitted so the semantic weights are not credited with loudness, and held at
    their mean at runtime (he reads in silence).
Output: out/encoding_work/features/alice.npz {g (T,), emb (T, 384), nuis (T, 2), text (T,) str}
"""
import csv
import sys
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import S3, WORK, fetch  # noqa: E402
import sensory  # noqa: E402

WINDOW_S = 8.0
TR, T0, N = 2.0, 20.0, 372
WAV = "DownTheRabbitHoleFinal_mono_exp120_NR16_pad.wav"


def envelope(path, edges):
    with wave.open(str(path)) as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        x = np.frombuffer(w.readframes(n), dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float32)
    x = x.reshape(-1, ch).mean(1) / np.abs(x).max()
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        seg = x[int(max(0, a) * sr):int(max(0, b) * sr)]
        out.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
    return np.array(out), len(x) / sr


def main():
    out = WORK / "features"
    out.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(WORK / "alice" / "annotations.tsv"), delimiter="\t"))
    words = [(float(r["Word Onset"]), r["Words"]) for r in rows if r["Word Onset"].strip()]
    wav = fetch(f"{S3}/ds002322/stimuli/{WAV}", WORK / "alice" / WAV)
    g = T0 + TR * np.arange(N)
    env, dur = envelope(wav, np.append(g, g[-1] + TR))
    texts, rate = [], []
    for a in g:
        b = a + TR
        texts.append(" ".join(w for t, w in words if b - WINDOW_S <= t < b))
        rate.append(sum(1 for t, _ in words if a <= t < b))
    files = sensory.ensure_models(WORK / "models")
    enc = sensory.TextEncoder(*files["text"], threads=2)
    emb = np.concatenate([enc.embed(texts[i:i + 64]) for i in range(0, N, 64)])
    np.savez_compressed(out / "alice.npz", g=g, emb=emb, nuis=np.stack([rate, env], 1).astype(np.float32),
                        text=np.array(texts))
    print(f"alice: {N} bins, audio {dur:.0f} s, words {len(words)} (last onset {words[-1][0]:.0f} s), "
          f"bins with words {int((np.array(rate) > 0).sum())}", flush=True)


if __name__ == "__main__":
    main()
