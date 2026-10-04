"""The Alice dataset (OpenNeuro ds002322, CC0): 214-region BOLD of every participant with a preprocessed (SPM8, MNI) run.

Stimulus: chapter 1 of Lewis Carroll's "Alice's Adventures in Wonderland" (public domain) read by Kristen McQuillan
for LibriVox (public domain), with word onsets in code/annotations.tsv. The preprocessed data drop the first 10
volumes (TR 2 s), so preprocessed volume k is at 20 + 2k s from the scan start (the audio starts at the events' onset).

Output: out/encoding_work/alice/<sub>.npz {ts (T, 214) float32, t0_s (time of volume 0 from the audio start), tr}
        out/encoding_work/alice/annotations.tsv
Run: python analysis/encoding/extract_alice.py [--jobs 3]
"""
import argparse
import csv
import io
import re
import sys
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import S3, WORK, atlas_mni, fetch, load_regions  # noqa: E402

DS = "ds002322"
DEST = WORK / "alice"
DROPPED = 10                       # volumes discarded by the authors' preprocessing


def one(key):
    sub = re.search(r"sub-(\d+)", key).group(1)
    out = DEST / f"{sub}.npz"
    if out.exists():
        return sub, "cached"
    vol = WORK / "tmp" / Path(key).name
    fetch(f"{S3}/{key}", vol)
    raw = vol.with_suffix("")
    try:
        ts, cnt, img, raw = load_regions(vol, lambda im: atlas_mni(ref=im)[0])
        ev = urllib.request.urlopen(f"{S3}/{DS}/sub-{sub}/sub-{sub}_task-alice_events.tsv", timeout=60).read().decode()
        onset = float(list(csv.DictReader(io.StringIO(ev), delimiter="\t"))[0]["onset"])
        tr = 2.0
        np.savez_compressed(out, ts=ts.astype(np.float32), t0_s=DROPPED * tr - onset, tr=tr, vox=cnt)
    finally:
        vol.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
    return sub, f"T={ts.shape[0]} empty={int((cnt == 0).sum())} shape={img.shape} zooms={img.header.get_zooms()[:3]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    fetch(f"{S3}/{DS}/code/annotations.tsv", DEST / "annotations.tsv")
    x = urllib.request.urlopen(f"{S3}?list-type=2&prefix={DS}/derivatives/&max-keys=1000", timeout=60).read().decode()
    todo = [k for k in re.findall(r"<Key>([^<]+)</Key>", x) if k.endswith("_preprocessed.nii.gz")]
    print(len(todo), "preprocessed runs", flush=True)
    with ProcessPoolExecutor(a.jobs) as ex:
        for f in as_completed([ex.submit(one, k) for k in todo]):
            try:
                print(*f.result(), flush=True)
            except Exception as e:
                print("FAILED", repr(e)[:200], flush=True)


if __name__ == "__main__":
    main()
