"""Shared pieces of the encoding-model pipeline (analysis/encoding/*): paths, the 214-region MNI atlas, downloads.

The atlas is SUB-01's own (out/atlas_names.json): Schaefer 2018 200 parcels / 7 networks (MIT) + the 14 deep nuclei of
Harvard-Oxford sub-maxprob-thr25 (CC BY-SA 4.0), deep nuclei over cortex, exactly as atlas_subject.py builds it in his
T1 -- here in MNI152 (FSL, 2 mm), the space the public fMRI below is distributed in.
"""
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(os.environ.get("ENC_WORK", ROOT / "out" / "encoding_work"))
OUT = ROOT / "out" / "encoding"
NILEARN = WORK / "nilearn"
DEEP = ["Thalamus", "Caudate", "Putamen", "Pallidum", "Hippocampus", "Amygdala", "Accumbens"]
S3 = "https://s3.amazonaws.com/openneuro.org"


def names214():
    return json.load(open(ROOT / "out" / "atlas_names.json"))


def atlas_mni(ref=None):
    """(label image, names) on the 2 mm FSL MNI152 grid, or resampled (nearest) onto `ref` (a NIfTI image)."""
    import nibabel as nib
    from nilearn import datasets, image
    sch = datasets.fetch_atlas_schaefer_2018(n_rois=200, yeo_networks=7, resolution_mm=2, data_dir=str(NILEARN))
    ho = datasets.fetch_atlas_harvard_oxford("sub-maxprob-thr25-2mm", data_dir=str(NILEARN))
    s_img = nib.load(sch.maps)
    h_img = ho.maps if not isinstance(ho.maps, (str, Path)) else nib.load(ho.maps)
    h_img = image.resample_to_img(h_img, s_img, interpolation="nearest", force_resample=True, copy_header=True)
    names = [str(x.decode() if isinstance(x, bytes) else x) for x in sch.labels if str(x) != "Background"]
    lab = np.asarray(s_img.dataobj).astype(np.int16)
    sub = np.asarray(h_img.dataobj).astype(np.int16)
    for i, nm in enumerate(list(ho.labels)):
        if any(k in nm for k in DEEP):
            names.append(nm)
            lab[sub == i] = len(names)               # deep nuclei take priority over cortex (as atlas_subject.py)
    assert names == names214(), "MNI atlas names differ from out/atlas_names.json"
    img = nib.Nifti1Image(lab, s_img.affine)
    if ref is not None:
        img = image.resample_to_img(img, ref, interpolation="nearest", force_resample=True, copy_header=True)
    return img, names


def region_means(data4d, labels, n=214):
    """(T, n) mean BOLD per label 1..n of a 4D array (x, y, z, T); a label with no voxel gives NaN."""
    lab = np.asarray(labels).reshape(-1)
    keep = lab > 0
    X = data4d.reshape(-1, data4d.shape[-1])[keep]                 # (V, T)
    li = lab[keep] - 1
    cnt = np.bincount(li, minlength=n).astype(float)
    out = np.zeros((n, X.shape[1]))
    np.add.at(out, li, X)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = out / cnt[:, None]
    out[cnt == 0] = np.nan
    return out.T, cnt


def load_regions(vol, lab_for, chunk=48):
    """(T, 214) region means of a 4D NIfTI file without holding it in memory: a .nii.gz is first decompressed next
    to itself (and deleted), the .nii is memory-mapped and reduced `chunk` volumes at a time. `lab_for(img)` gives
    the label image on the data's grid. Returns (ts, voxel counts, img, path of the .nii)."""
    import nibabel as nib
    vol = Path(vol)
    if vol.suffix == ".gz":
        raw = vol.with_suffix("")
        with open(raw, "wb") as f:
            subprocess.run(["gzip", "-dc", str(vol)], stdout=f, check=True)
        vol.unlink()
        vol = raw
    img = nib.load(str(vol), mmap=True)
    lab = np.asarray(lab_for(img).dataobj).astype(int)
    parts, cnt = [], None
    for t0 in range(0, img.shape[3], chunk):
        ts, cnt = region_means(np.asarray(img.dataobj[..., t0:t0 + chunk], dtype=np.float32), lab)
        parts.append(ts)
    return np.concatenate(parts).astype(np.float32), cnt, img, vol


def fetch(url, dest, tries=4):
    """Download `url` to `dest` with curl (resumable, retried); returns dest."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    for k in range(tries):
        r = subprocess.run(["curl", "-sSfL", "-C", "-", "-o", str(part), url])
        if r.returncode == 0:
            part.rename(dest)
            return dest
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"download failed: {url}")


def zscore(x, axis=0):
    x = np.asarray(x, float)
    m = np.nanmean(x, axis=axis, keepdims=True)
    s = np.nanstd(x, axis=axis, keepdims=True)
    return (x - m) / np.where(s > 0, s, 1.0)
