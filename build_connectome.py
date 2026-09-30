"""Build the structural connectome of the MyConnectome brain (ses-2022).

Steps: DWI mask + CSD fit -> whole-brain tractography -> atlas (Schaefer 200
+ subcortical) warped MNI -> T1 -> DWI -> connectivity matrix + fibre lengths.
Outputs go to out/.
"""
import time
from pathlib import Path

import nibabel as nib
import numpy as np
from dipy.align import affine_registration, syn_registration
from dipy.core.gradients import gradient_table
from dipy.data import default_sphere
from dipy.direction import peaks_from_model
from dipy.reconst.csdeconv import ConstrainedSphericalDeconvModel, auto_response_ssst
from dipy.reconst.dti import TensorModel
from dipy.segment.mask import median_otsu
from dipy.tracking import utils
from dipy.tracking.local_tracking import LocalTracking
from dipy.tracking.stopping_criterion import ThresholdStoppingCriterion
from dipy.tracking.streamline import Streamlines, length
from nilearn import datasets, image

D = Path("data")
DWI = "sub-01_ses-2015_acq-g79_dir-pe0_dwi"  # 2015 scan covers temporal/occipital lobes
OUT = Path("out")
OUT.mkdir(exist_ok=True)
t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)



def main():
    # --- DWI --------------------------------------------------------------------
    dwi_img = nib.load(D / f"{DWI}.nii.gz")
    data = dwi_img.get_fdata(dtype=np.float32)
    bvals = np.loadtxt(D / f"{DWI}.bval")
    bvecs = np.loadtxt(D / f"{DWI}.bvec")
    bvals = np.where(bvals < 50, 0, np.round(bvals / 500) * 500)
    gtab = gradient_table(bvals, bvecs=bvecs)
    b0_idx = np.where(gtab.b0s_mask)[0]
    _, mask = median_otsu(data, vol_idx=b0_idx, median_radius=3, numpass=2)
    mean_b0 = data[..., b0_idx].mean(-1)
    nib.save(nib.Nifti1Image(mean_b0, dwi_img.affine), OUT / "mean_b0.nii.gz")
    log(f"DWI loaded {data.shape}, mask voxels {mask.sum()}")

    # FA for the stopping criterion (lowest shell only, tensor model assumption)
    lo = (bvals <= np.unique(bvals)[1])
    tenfit = TensorModel(gradient_table(bvals[lo], bvecs=bvecs[:, lo] if bvecs.shape[0] == 3 else bvecs[lo])).fit(data[..., lo], mask=mask)
    fa = np.nan_to_num(tenfit.fa)
    nib.save(nib.Nifti1Image(fa.astype(np.float32), dwi_img.affine), OUT / "fa.nii.gz")
    log("FA done")

    # CSD on the b=3000 shell (+ b0) for sharper fibre orientations
    hi = (bvals == 0) | (bvals == 3000)
    gtab_hi = gradient_table(bvals[hi], bvecs=bvecs[:, hi] if bvecs.shape[0] == 3 else bvecs[hi])
    response, _ = auto_response_ssst(gtab_hi, data[..., hi], roi_radii=10, fa_thr=0.7)
    csd = ConstrainedSphericalDeconvModel(gtab_hi, response, sh_order_max=6)
    peaks = peaks_from_model(csd, data[..., hi], default_sphere, relative_peak_threshold=0.5,
                             min_separation_angle=25, mask=mask, npeaks=3, parallel=True, num_processes=16)
    log("CSD peaks done")

    # --- Tractography -----------------------------------------------------------
    stop = ThresholdStoppingCriterion(fa, 0.15)
    seed_mask = (fa > 0.25) & mask
    seeds = utils.seeds_from_mask(seed_mask, dwi_img.affine, density=2)
    tracks = LocalTracking(peaks, stop, seeds, dwi_img.affine, step_size=0.75, max_cross=1)
    streamlines = Streamlines(s for s in tracks if len(s) > 1)
    lens = np.array(list(length(streamlines)))
    keep = lens > 20
    streamlines = Streamlines([s for s, k in zip(streamlines, keep) if k])
    log(f"tractography: {len(streamlines)} streamlines > 20 mm")

    # --- Atlas: MNI -> T1 -> DWI --------------------------------------------------
    schaefer = datasets.fetch_atlas_schaefer_2018(n_rois=200, yeo_networks=7, resolution_mm=1)
    ho_sub = datasets.fetch_atlas_harvard_oxford("sub-maxprob-thr25-1mm")
    mni = datasets.load_mni152_template(resolution=1)

    t1_img = nib.load(D / "sub-01_ses-2022_T1w.nii.gz")
    t1_small = image.resample_img(t1_img, target_affine=np.diag([1.0, 1.0, 1.0]), interpolation="continuous",
                                  force_resample=True, copy_header=True)
    t1 = t1_small.get_fdata()

    # MNI template -> subject T1 (affine + SyN), same modality
    _, mni_to_t1_aff = affine_registration(mni.get_fdata(), t1, moving_affine=mni.affine,
                                           static_affine=t1_small.affine, nbins=32,
                                           pipeline=["center_of_mass", "translation", "rigid", "affine"],
                                           level_iters=[10000, 1000, 100])
    _, mapping = syn_registration(mni.get_fdata(), t1, moving_affine=mni.affine, static_affine=t1_small.affine,
                                  prealign=mni_to_t1_aff, level_iters=[10, 10, 5])
    log("MNI->T1 registration done")

    # subject T1 -> mean b0 (rigid, cross-modal MI)
    _, t1_to_dwi = affine_registration(t1, mean_b0, moving_affine=t1_small.affine, static_affine=dwi_img.affine,
                                       nbins=32, pipeline=["center_of_mass", "translation", "rigid"],
                                       level_iters=[10000, 1000, 100])
    log("T1->DWI registration done")


    def atlas_to_dwi(atlas_img):
        a = image.resample_to_img(atlas_img, mni, interpolation="nearest", force_resample=True, copy_header=True)
        in_t1 = mapping.transform(a.get_fdata(), interpolation="nearest")
        from dipy.align.imaffine import AffineMap
        amap = AffineMap(t1_to_dwi, domain_grid_shape=mean_b0.shape, domain_grid2world=dwi_img.affine,
                         codomain_grid_shape=in_t1.shape, codomain_grid2world=t1_small.affine)
        return amap.transform(in_t1, interpolation="nearest").astype(np.int32)


    cort = atlas_to_dwi(nib.load(schaefer.maps) if isinstance(schaefer.maps, str) else schaefer.maps)
    sub_img = ho_sub.maps if not isinstance(ho_sub.maps, str) else nib.load(ho_sub.maps)
    sub = atlas_to_dwi(sub_img)

    # Harvard-Oxford subcortical: keep deep grey nuclei, drop WM/cortex/ventricles/brainstem
    sub_names = list(ho_sub.labels)
    keep_sub = [i for i, n in enumerate(sub_names) if any(k in n for k in
                ["Thalamus", "Caudate", "Putamen", "Pallidum", "Hippocampus", "Amygdala", "Accumbens"])]
    labels = cort.copy()
    names = [n.decode() if isinstance(n, bytes) else str(n) for n in schaefer.labels]
    names = [n for n in names if n != "Background"]
    for j, i in enumerate(keep_sub):
        labels[sub == i] = 201 + j          # deep nuclei take priority over cortex
        names.append(sub_names[i])
    head = mean_b0 > 0.1 * np.percentile(mean_b0[mask], 50)   # looser than the tracking mask
    labels = labels * head
    # grow cortical labels ~3 mm into unlabelled voxels so streamlines ending at the
    # grey/white boundary get assigned to the region they reach
    from scipy import ndimage
    for _ in range(2):
        grown = ndimage.grey_dilation(labels, size=(3, 3, 3))
        labels = np.where((labels == 0) & head, grown, labels)
    nib.save(nib.Nifti1Image(labels.astype(np.int32), dwi_img.affine), OUT / "labels_dwi.nii.gz")
    n = len(names)
    log(f"atlas in DWI space: {n} regions, present {len(np.unique(labels)) - 1}")

    # --- Connectivity -------------------------------------------------------------
    M, grouping = utils.connectivity_matrix(streamlines, dwi_img.affine, labels.astype(np.uint16),
                                            return_mapping=True, mapping_as_streamlines=True)
    M = M[1:n + 1, 1:n + 1].astype(float)
    np.fill_diagonal(M, 0)
    L = np.zeros_like(M)
    for (a, b), sl in grouping.items():
        if a and b and a != b and a <= n and b <= n:
            L[a - 1, b - 1] = L[b - 1, a - 1] = np.mean(list(length(sl)))
    cent = np.array([nib.affines.apply_affine(dwi_img.affine, np.argwhere(labels == k + 1).mean(0))
                     if (labels == k + 1).any() else [np.nan] * 3 for k in range(n)])
    np.savez(OUT / "connectome.npz", weights=M, lengths=L, names=np.array(names), centroids=cent)
    log(f"connectome saved: {n}x{n}, edges {(M > 0).sum() // 2}, streamlines in matrix {int(M.sum() / 2)}")


if __name__ == "__main__":
    main()
