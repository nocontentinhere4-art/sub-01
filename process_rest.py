"""Stream SUB-01's resting-state fMRI runs from OpenNeuro and keep only region time series.

For each run: download BOLD -> mean image -> rigid to the 2022 T1 -> atlas (already
in T1 space) resampled into BOLD space -> mean signal per region -> detrend,
band-pass 0.01-0.1 Hz, z-score -> out/rest/<run>.npz (float16, T x regions).
The raw BOLD file is deleted right after. Usage: python process_rest.py [N_RUNS]
"""
import json
import sys
import urllib.request
from pathlib import Path

import nibabel as nib
import numpy as np
from dipy.align import affine_registration
from dipy.align.imaffine import AffineMap
from scipy import signal

S3 = "https://s3.amazonaws.com/openneuro.org/"
OUT = Path("out/rest")
OUT.mkdir(parents=True, exist_ok=True)
TMP = Path("data/tmp")
TMP.mkdir(exist_ok=True)


def atlas_in_t1():
    """Atlas already warped into the 2022 T1 (1 mm) by atlas_subject.py."""
    return nib.load("out/labels_t1.nii.gz")


def process(key, labels_t1, n_regions):
    name = Path(key).name.replace("_bold.nii.gz", "")
    dst = OUT / f"{name}.npz"
    if dst.exists():
        return "cached"
    tr = json.loads(urllib.request.urlopen(S3 + key.replace(".nii.gz", ".json")).read())["RepetitionTime"]
    tmp = TMP / Path(key).name
    urllib.request.urlretrieve(S3 + key, tmp)
    try:
        bold = nib.load(tmp)
        data = bold.get_fdata(dtype=np.float32)
        mean = data.mean(-1)
        t1 = labels_t1  # only its grid/affine is used for the T1 intensity below
        t1_int = nib.load("out/t1_brain_1mm.nii.gz").get_fdata()   # skull-stripped: no face in the repo
        _, t1_to_bold = affine_registration(t1_int * (labels_t1.get_fdata() > 0), mean, moving_affine=t1.affine,
                                            static_affine=bold.affine, nbins=32,
                                            pipeline=["center_of_mass", "translation", "rigid"],
                                            level_iters=[10000, 1000, 100])
        amap = AffineMap(t1_to_bold, domain_grid_shape=mean.shape, domain_grid2world=bold.affine,
                         codomain_grid_shape=labels_t1.shape, codomain_grid2world=labels_t1.affine)
        lab = amap.transform(labels_t1.get_fdata(), interpolation="nearest").astype(int)
        flat = data.reshape(-1, data.shape[-1])
        lab = lab.ravel()
        ts = np.full((data.shape[-1], n_regions), np.nan, np.float32)
        for k in range(1, n_regions + 1):
            vox = flat[lab == k]
            if len(vox) >= 5:
                ts[:, k - 1] = vox.mean(0)
        ts = ts[5:]                                                    # drop scanner warm-up volumes
        ok = ~np.isnan(ts).any(0)
        x = signal.detrend(ts[:, ok], axis=0)
        b, a = signal.butter(2, [0.01 * 2 * tr, min(0.1 * 2 * tr, 0.99)], btype="band")
        x = signal.filtfilt(b, a, x, axis=0)
        x = (x - x.mean(0)) / (x.std(0) + 1e-6)
        ts[:, ok] = x
        np.savez_compressed(dst, ts=ts.astype(np.float16), tr=tr, key=key)
        return f"{ts.shape[0]} volumes, TR {tr:.2f}s, {ok.sum()} regions with signal"
    finally:
        tmp.unlink(missing_ok=True)                                    # never keep the raw file


def main():
    n_runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    names = json.load(open("out/atlas_names.json"))
    labels_t1 = atlas_in_t1()
    keys = Path("rest_runs.txt").read_text().split()
    for key in keys[:n_runs]:
        print(Path(key).name, "->", process(key, labels_t1, len(names)), flush=True)


if __name__ == "__main__":
    main()
