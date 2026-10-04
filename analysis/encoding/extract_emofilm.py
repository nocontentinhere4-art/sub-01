"""Emo-FilM (OpenNeuro ds004892, CC0): the 214-region BOLD of every participant watching the three Blender open movies.

Only the films whose own licence allows commercial use AND whose exact cut we can obtain are used: Big Buck Bunny,
Sintel, Tears of Steel (CC BY 3.0, Blender Foundation; download.blender.org). The other CC BY films of the set are on
Vimeo, which serves no download without an account; the five NonCommercial films are excluded (docs/encoding/LICENSES.md).

Input: derivatives/preprocessing/sub-*/ses-*/func/*_task-<film>_space-MNI_desc-ppres_bold.nii.gz (the authors'
FSL pipeline, motion + WM + CSF regressed, MNI152 2 mm, TR 1.3 s) and the scan's events (rest / film / rest onsets).
Each volume is downloaded, reduced to (T, 214) region means with the MNI atlas and deleted.

Output: out/encoding_work/emofilm/<sub>_<film>.npz  {ts (T, 214) float32, onset_s, duration_s, tr}
Run: python analysis/encoding/extract_emofilm.py [--jobs 3] [--subjects S01,S02]
"""
import argparse
import csv
import io
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import S3, WORK, atlas_mni, fetch, load_regions  # noqa: E402

DS = "ds004892"
FILMS = ["BigBuckBunny", "Sintel", "TearsOfSteel"]
DEST = WORK / "emofilm"


def keys(prefix):
    out, token = [], None
    while True:
        url = f"{S3}?list-type=2&prefix={prefix}&max-keys=1000" + (f"&continuation-token={token}" if token else "")
        x = urllib.request.urlopen(url, timeout=60).read().decode()
        out += re.findall(r"<Key>([^<]+)</Key>", x)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
        if not m:
            return out
        token = urllib.parse.quote(m.group(1), safe="")


def subjects():
    rows = urllib.request.urlopen(f"{S3}/{DS}/participants.tsv", timeout=60).read().decode()
    return [r["participant_id"].replace("sub-", "") for r in csv.DictReader(io.StringIO(rows), delimiter="\t")]


def film_onset(sub, ses, film):
    url = f"{S3}/{DS}/sub-{sub}/ses-{ses}/func/sub-{sub}_ses-{ses}_task-scan_acq-{film}_events.tsv"
    rows = list(csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=60).read().decode()), delimiter="\t"))
    f = [r for r in rows if r["trial_type"] == "film"][0]
    return float(f["onset"]), float(f["duration"])


def one(sub, ses, film, key):
    out = DEST / f"{sub}_{film}.npz"
    if out.exists():
        return out, "cached"
    vol = WORK / "tmp" / Path(key).name
    fetch(f"{S3}/{key}", vol)
    raw = vol.with_suffix("")
    try:
        ts, cnt, img, raw = load_regions(vol, lambda im: atlas_mni(ref=im)[0])
        onset, dur = film_onset(sub, ses, film)
        tr = float(img.header.get_zooms()[3])
        np.savez_compressed(out, ts=ts.astype(np.float32), onset_s=onset, duration_s=dur, tr=tr, vox=cnt)
    finally:
        vol.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
    return out, f"T={ts.shape[0]} empty={int((cnt == 0).sum())}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--subjects", default="")
    a = ap.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    subs = a.subjects.split(",") if a.subjects else subjects()
    todo = []
    for sub in subs:
        for k in keys(f"{DS}/derivatives/preprocessing/sub-{sub}/"):
            m = re.search(r"ses-(\d+)/func/.*_task-([A-Za-z]+)_space-MNI_desc-ppres_bold\.nii\.gz$", k)
            if m and m.group(2) in FILMS:
                todo.append((sub, m.group(1), m.group(2), k))
    print(f"{len(subs)} subjects, {len(todo)} runs", flush=True)
    with ProcessPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(one, *t): t for t in todo}
        for f in as_completed(futs):
            t = futs[f]
            try:
                p, info = f.result()
                print(t[0], t[2], info, flush=True)
            except Exception as e:                           # one bad run must not stop the others
                print(t[0], t[2], "FAILED", repr(e)[:200], flush=True)


if __name__ == "__main__":
    main()
