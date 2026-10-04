"""Stage 1b of the boy.glb rebuild:  python make_textures.py   (numpy + Pillow + scipy; after build_mesh.py)

Turns the Blender bakes in work/ into the textures assemble.mjs packs, and finds the eyes:
  tex_skin.png      face / neck / hands colour, cleaned (the old texture's painted dark slivers by the nose and a green
                    smear on the cheek are inpainted), with the eye openings cut out in the alpha channel (MASK) so that
                    the eyeballs behind them show;
  tex_skin_n.png    tangent normal map (pores), sanitised; tex_skin_orm.png: R = ambient occlusion, G = roughness;
  tex_hair*.png, tex_cloth*.png  the same for the hair and the clothes;
  tex_eye.png       a procedural eyeball (sclera, dark brown iris with fibres, limbal ring, pupil), tex_lid.png the eyelid;
  spec.json         eyeball centres and forward directions (metres, glTF y up) and the material settings.
"""
import json, os
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
WORK, OUT = os.path.join(HERE, "work"), os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

def load(name, size=None):
    im = Image.open(os.path.join(WORK, name)).convert("RGB")
    if size and im.size[0] != size: im = im.resize((size, size), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255
def save(name, arr):
    a = np.clip(arr * 255 + 0.5, 0, 255).astype(np.uint8); Image.fromarray(a).save(os.path.join(OUT, name)); print("wrote", name, a.shape)
def sanitize_normal(n):
    """flat where the tangent frame was degenerate (z < 0.45 or non-unit)"""
    v = n * 2 - 1; ln = np.linalg.norm(v, axis=2); bad = (v[:, :, 2] < 0.45) | (np.abs(ln - 1) > 0.25)
    bad = ndi.binary_dilation(bad, iterations=1)
    n = n.copy(); n[bad] = (0.5, 0.5, 1.0); return n
def orm(ao, rough):
    a = np.zeros(rough.shape[:2] + (3,), np.float32); a[:, :, 0] = ao; a[:, :, 1] = rough; a[:, :, 2] = 0; return a
def blur(a, r):
    return np.asarray(Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))).astype(np.float32) / 255

def pad_full(img, covered):
    """every uncovered texel takes the nearest covered texel's value: no black gutters, so mip levels and bilinear
    filtering at island borders never pull black into the surface (the torn strip at the wrist, the grey sock seams)"""
    idx = ndi.distance_transform_edt(~covered, return_distances=False, return_indices=True)
    return img[idx[0], idx[1]]
def covered_of(bake): return bake.max(2) > 0.002                       # Blender bakes with use_clear: black outside the islands + margin

# ------------------------------------------------------------------ skin
skin = load("bake_skin.png"); S = skin.shape[0]
cov_skin = covered_of(skin); skin = pad_full(skin, cov_skin)
pos = np.load(os.path.join(WORK, "pos_skin.npy"))[::-1]           # Blender images are bottom-up; PIL arrays top-down
nrm = np.load(os.path.join(WORK, "nrm_skin.npy"))[::-1]
cov = np.abs(np.linalg.norm(nrm, axis=2) - 1) < 0.15                # baked texels
nrm = nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
r, g, b = skin[:, :, 0], skin[:, :, 1], skin[:, :, 2]; lum = skin.mean(2)
mx, mn = skin.max(2), skin.min(2); sat = (mx - mn) / np.maximum(mx, 1e-3)
X, Y, Z = pos[:, :, 0], pos[:, :, 1], pos[:, :, 2]                   # Blender object space, cm, z up, he faces -y
head = cov & (Z > 140)

# --- the eyes: the sclera is the only white in the face; grow each eye opening from it over the non-skin pixels
sclera = head & (lum > 0.58) & (sat < 0.16) & (Z > 148) & (Z < 168)
sclera = ndi.binary_opening(sclera, iterations=1)
lab, nlab = ndi.label(sclera); sizes = ndi.sum(sclera, lab, range(1, nlab + 1))
print("sclera blobs", sorted(sizes.astype(int), reverse=True)[:6])
eyes = {}
for side, sign in (("left", 1), ("right", -1)):                     # glTF/Blender +x is his left
    cand = [i + 1 for i, sz in enumerate(sizes) if sz > 30 and np.sign(X[lab == i + 1].mean()) == sign]
    assert cand, "no sclera found for the %s eye" % side
    mask = np.isin(lab, cand)
    c3 = pos[mask].mean(0)
    near = head & (np.linalg.norm(pos - c3, axis=2) < 1.7)            # within 1.7 cm of the sclera centre in 3D
    # the opening = sclera + iris; the near-black lash line stays on the skin so the painted lids keep their shape
    iris = (lum >= 0.1) & (lum < 0.45) & (r - b > 0.04) & (sat > 0.2)
    white = (sat < 0.22) & (lum > 0.42)
    opening = near & (iris | white)
    # grow from the sclera through non-skin pixels only (keeps the eyebrow out), then fill the pupil and smooth
    grown = sclera & near
    for _ in range(60):
        nxt = ndi.binary_dilation(grown) & opening
        if (nxt == grown).all(): break
        grown = nxt
    grown = ndi.binary_fill_holes(grown); grown = ndi.binary_opening(grown, iterations=2); grown = ndi.binary_closing(grown, iterations=2)
    grown = ndi.binary_fill_holes(grown)
    lab2, n2 = ndi.label(grown)
    if n2 > 1: grown = lab2 == (np.argmax(ndi.sum(grown, lab2, range(1, n2 + 1))) + 1)
    P = pos[grown]; N = nrm[grown]
    centre = P.mean(0); fwd = N.mean(0); fwd /= np.linalg.norm(fwd)
    ext = P.max(0) - P.min(0)
    ys, xs = np.nonzero(grown)
    print("%s eye: %d px, centre %s cm, forward %s, opening extent %s cm, uv px %d..%d x %d..%d" % (side, grown.sum(), centre.round(2), fwd.round(2), ext.round(2), xs.min(), xs.max(), ys.min(), ys.max()))
    # the opening's frame on the skin: PCA of its texels in the plane across the forward axis -> the long axis (across the
    # eye, towards the nose = "inner") and the short one (up), half-lengths; assemble.mjs builds the lid rim, the lashes
    # and the caruncle on this ellipse
    Pp = P - centre; Pp = Pp - np.outer(Pp @ fwd, fwd)
    _, _, Vt_ = np.linalg.svd(Pp, full_matrices=False); A_ = Vt_[0]; B_ = Vt_[1]
    if A_[0] * sign > 0: A_ = -A_                                      # A points inwards (towards the nose: X -> 0)
    if B_[2] < 0: B_ = -B_                                             # B points up
    B_ = np.cross(fwd, A_); B_ /= np.linalg.norm(B_)
    if B_[2] < 0: B_ = -B_; A_ = np.cross(B_, fwd); A_ /= np.linalg.norm(A_)
    if A_[0] * sign > 0: A_ = -A_
    a_half = float(np.percentile(np.abs(Pp @ A_), 98)); b_half = float(np.percentile(np.abs(Pp @ B_), 98))
    eyes[side] = {"mask": grown, "surface": centre, "forward": fwd, "width": float(np.hypot(ext[0], ext[1])), "A": A_, "B": B_, "a": a_half, "b": b_half}
    print("  opening ellipse: a %.2f cm (across), b %.2f cm (up)" % (a_half, b_half))
RADIUS = 1.5                                                           # cm; over the real 1.2 so the ball fills the opening's corners
INSET = 0.12                                                           # the cornea apex sits this far behind the painted surface
def to_gltf(v):   # Blender z up (x, y, z) cm -> glTF y up metres (x, z, -y)
    return [float(v[0]) / 100, float(v[2]) / 100, float(-v[1]) / 100]
spec_eyes = {"radius": RADIUS / 100}
for side, e in eyes.items():
    c = e["surface"] - e["forward"] * (RADIUS + INSET)
    gdir = lambda v: [float(v[0]), float(v[2]), float(-v[1])]
    spec_eyes[side] = {"center": to_gltf(c), "forward": gdir(e["forward"]),
                       "opening": {"center": [float(x) for x in (np.array(to_gltf(e["surface"])) - np.array(to_gltf(c)))], "A": gdir(e["A"]), "B": gdir(e["B"]), "a": e["a"] / 100, "b": e["b"] / 100}}
# the eye openings become holes in the skin (MASK alpha): one pixel of lid kept all round, and never wider than the
# eyeball behind them (a hole past the ball's silhouette would show the inside of the head)
hole = np.zeros((S, S), bool)
for e in eyes.values():
    c = e["surface"] - e["forward"] * (RADIUS + INSET); d = pos - c
    lateral = np.linalg.norm(d - (d @ e["forward"])[:, :, None] * e["forward"], axis=2)
    inner = np.abs(X) > abs(e["surface"][0]) - 0.24 * e["width"]       # the inner corner (towards the nose) stays painted: the ball sits deeper there
    outer = np.abs(X) < abs(e["surface"][0]) + 0.18 * e["width"] - 0.6 * np.abs(Z - e["surface"][2])   # a rounded outer corner (a plane cut left a straight vertical sclera edge)       # and the outer corner: the lid closes over the ball there too (no sclera wedge past the lashes)
    hole |= ndi.binary_erosion(e["mask"], iterations=6) & (lateral < RADIUS * 0.75) & inner & outer
hole = blur(hole.astype(np.float32), 2.5) > 0.5                              # the morphology's square corners rounded off
lab_hh, n_hh = ndi.label(hole)
if n_hh > 2:                                                                  # one hole per eye: no stray specks
    sz_hh = ndi.sum(hole, lab_hh, range(1, n_hh + 1)); keep_hh = np.argsort(sz_hh)[-2:] + 1; hole = np.isin(lab_hh, keep_hh)
alpha = 1 - blur(hole.astype(np.float32), 1.6)                                # a 3-texel ramp: the MASK cutoff at 0.5 cuts a smooth edge, not texel stairs
for side, e in eyes.items():                                                  # the rim, the lashes and the caruncle follow the hole's own ellipse
    eh = hole & ndi.binary_dilation(e["mask"], iterations=2)
    if eh.sum() < 50: continue
    Ph = pos[eh]; ch = Ph.mean(0); Pp = Ph - ch; Pp = Pp - np.outer(Pp @ e["forward"], e["forward"])
    A_, B_ = e["A"], e["B"]
    e["a"] = float(np.percentile(np.abs(Pp @ A_), 99)); e["b"] = float(np.percentile(np.abs(Pp @ B_), 99)); e["hole_centre"] = ch
    print("  %s hole ellipse: a %.2f b %.2f cm, centre offset from the opening %.2f cm" % (side, e["a"], e["b"], float(np.linalg.norm(ch - e["surface"]))))
    th_ = np.arctan2(Pp @ B_, Pp @ A_); rr_ = np.hypot(Pp @ A_, Pp @ B_); NB = 48
    bins_ = ((th_ + np.pi) / (2 * np.pi) * NB).astype(int) % NB; outline = np.full(NB, np.nan)
    for b_ in range(NB):
        if (bins_ == b_).sum() >= 3: outline[b_] = np.percentile(rr_[bins_ == b_], 97)
    ok_ = np.isfinite(outline); outline = np.interp(np.arange(NB), np.nonzero(ok_)[0], outline[ok_], period=NB) if ok_.sum() >= 8 else np.where(ok_, outline, (e["a"] + e["b"]) / 2)
    outline = np.convolve(np.pad(outline, 2, mode="wrap"), np.ones(5) / 5, mode="valid")        # smoothed round the loop (bin 0 is the -pi direction: the outer corner side; bin NB/2 is +A, inner)
    spec_eyes[side]["opening"] = {"center": [float(x) for x in (np.array(to_gltf(ch)) - np.array(spec_eyes[side]["center"]))], "A": gdir(A_), "B": gdir(B_), "a": e["a"] / 100, "b": e["b"] / 100,
                                  "outline": [float(x) / 100 for x in outline], "outline0": -np.pi}

# --- clean the painted defects on the face: thin dark lines (not the nostrils, brows or lashes, which are blobs) and green smears
face = head & (Y < 0) & ~ndi.binary_dilation(hole, iterations=6)
dark = face & (lum < 0.3)
lines = dark & ~ndi.binary_opening(dark, structure=np.ones((5, 5)))        # survives opening = a blob (nostril, brow, lash line)
brow_or_lash = ndi.binary_dilation(ndi.binary_opening(dark, structure=np.ones((5, 5))), iterations=3)
lines &= ~brow_or_lash
green = face & (g > r * 0.97) & (lum > 0.3)
# the painted slivers by the nose and under the eyes are small dark blobs; the nostrils (under the nose tip) and the
# brows / lashes (next to the eye openings) are kept
eye_z = np.mean([e["surface"][2] for e in eyes.values()]); near_eyes = np.zeros((S, S), bool)
for e in eyes.values(): near_eyes |= ndi.binary_dilation(e["mask"], iterations=10)
grey_dark = face & (lum < 0.5) & (r - b < 0.13) & (Y < -6) & (np.abs(X) < 5.5) & (Z > eye_z - 7.5) & (Z < eye_z + 1.5)   # nose and cheeks
blobs = grey_dark & ~lines; lb, nb = ndi.label(blobs); slivers = np.zeros((S, S), bool)
for i in range(1, nb + 1):
    bm = lb == i; n = bm.sum()
    if n > 900 or (bm & near_eyes).any(): continue
    px, pz = X[bm].mean(), Z[bm].mean()
    if abs(px) < 1.6 and eye_z - 6.5 < pz < eye_z - 2.5: continue            # nostrils
    slivers |= bm
print("sliver blobs removed:", int(slivers.sum()), "px")
bad = ndi.binary_dilation(lines | green | slivers, iterations=2) & face
print("inpainting %d line px and %d green px" % (lines.sum(), green.sum()))
# the face, upscaled once by an AI upscaler (Higgsfield, ByteDance 4K; README.md) from the crop work/face_crop.png of this
# very atlas: a cleaner, sharper version of the same painted face. Blended in over the head skin only, if present.
skin_src = skin.copy()
# the face crop (the head island's box in the atlas) is written for the upscaler; the result is blended back only when
# it was made from this very layout (the UV packing can move the island between builds)
lab_h, n_h = ndi.label(ndi.binary_dilation(head, iterations=2)); face_isl = lab_h == (np.argmax(ndi.sum(head, lab_h, range(1, n_h + 1))) + 1)   # the face island
ys_, xs_ = np.nonzero(face_isl); CROP = [int(max(0, xs_.min() - 16)), int(max(0, ys_.min() - 16)), 0, 0]
CROP[2] = int(min(S, xs_.max() + 17) - CROP[0]); CROP[3] = int(min(S, ys_.max() + 17) - CROP[1])
l, t, w_, h_ = CROP
Image.fromarray(np.clip(skin[t:t + h_, l:l + w_] * 255 + 0.5, 0, 255).astype(np.uint8)).save(os.path.join(WORK, "face_crop.png"))
json.dump({"crop": CROP}, open(os.path.join(WORK, "face_crop.json"), "w")); print("face crop", CROP)
UP = os.path.join(WORK, "face_up4k.png"); UPJ = os.path.join(WORK, "face_up4k.json")
if os.path.exists(UP) and os.path.exists(UPJ) and json.load(open(UPJ))["crop"] == CROP:
    up = np.asarray(Image.open(UP).convert("RGB").resize((w_, h_), Image.LANCZOS)).astype(np.float32) / 255
    region = np.zeros((S, S), bool); region[t:t + h_, l:l + w_] = True
    m_up = blur((region & face_isl).astype(np.float32), 3)
    full = skin.copy(); full[t:t + h_, l:l + w_] = up
    skin_src = skin * (1 - m_up[:, :, None]) + full * m_up[:, :, None]; print("blended the upscaled face crop")
else:
    print("no upscaled face for this layout: upload work/face_crop.png to the upscaler, save the result as work/face_up4k.png and copy face_crop.json to face_up4k.json")
# inpaint with the blurred skin around (pixels that are skin-coloured and not bad)
good = face & ~bad & (r - b > 0.1) & (lum > 0.35)
w = blur(good.astype(np.float32), 6); col = np.stack([blur(skin_src[:, :, k] * good, 6) for k in range(3)], 2) / np.maximum(w, 1e-4)[:, :, None]
skin_clean = skin_src.copy(); skin_clean[bad] = col[bad]
# the painted skin has pink / rose blotches (AI bake artefacts; the upscaler sharpened them). Keep every pixel's
# luminance (the painted shading: nose, cheeks, jaw) but replace its low-frequency chroma (sigma 10 px) by the broad
# skin tone (sigma 70 px) over the skin, leaving the features alone: eyes and lashes, brows, nostrils (dark), lips.
def chroma_equalise(img, region, feat, s_lo=10, s_hi=70):
    out = img.copy(); w = (region & ~feat).astype(np.float32)
    wl = blur(w, s_lo); wh = blur(w, s_hi)
    lo = np.stack([blur(img[:, :, k] * w, s_lo) for k in range(3)], 2) / np.maximum(wl, 1e-3)[:, :, None]
    hi = np.stack([blur(img[:, :, k] * w, s_hi) for k in range(3)], 2) / np.maximum(wh, 1e-3)[:, :, None]
    lo_c = lo / np.maximum(lo.mean(2, keepdims=True), 1e-3); hi_c = hi / np.maximum(hi.mean(2, keepdims=True), 1e-3)
    gain = np.clip(hi_c / np.maximum(lo_c, 1e-3), 0.7, 1.4)
    m_ = blur((region & ~feat).astype(np.float32), 2)[:, :, None]
    out = np.clip(img * (gain * m_ + (1 - m_)), 0, 1); return out
lum_c = skin_clean.mean(2); rr_, gg_, bb_ = skin_clean[:, :, 0], skin_clean[:, :, 1], skin_clean[:, :, 2]
mouth_z = eye_z - 7.2
lips = (rr_ - gg_ > 0.16) & (lum_c < 0.78) & (np.abs(X) < 2.9) & (np.abs(Z - mouth_z) < 1.3) & (Y < -6)
features = (lum_c < 0.42) | lips | ndi.binary_dilation(hole, iterations=10)
features = ndi.binary_dilation(features, iterations=3)
skin_clean = chroma_equalise(skin_clean, head, features)
print("skin chroma equalised; lips px", int(lips.sum()))
# a touch of local contrast on the face (the old bake is soft): unsharp mask, light
face_f = ndi.binary_dilation(face, iterations=8).astype(np.float32)
sharp = np.clip(skin_clean + 0.2 * (skin_clean - np.stack([blur(skin_clean[:, :, k], 2.5) for k in range(3)], 2)), 0, 1)
skin_out = skin_clean * (1 - face_f[:, :, None]) + sharp * face_f[:, :, None]
# the old painted face's warmth and contrast are the reference (the owner knows this face): per-channel means and the
# luminance spread over the face island are matched to the old bake's, so the equalised skin is neither paler nor flatter
USE_PROJ = os.path.exists(os.path.join(WORK, "skin_projected.png"))
fm = face_isl & (skin.mean(2) > 0.3) & (not USE_PROJ)
if fm.sum() < 100: fm = face_isl & (skin.mean(2) > 0.3)                  # (statistics only; the blend below is weighted 0 with the repaint)
old_mean = skin[fm].mean(0); new_mean = skin_out[fm].mean(0)
old_sd = skin[fm].mean(1).std(); new_sd = skin_out[fm].mean(1).std()
gain = old_mean / np.maximum(new_mean, 1e-3); k_sd = float(np.clip(old_sd / max(new_sd, 1e-3), 0.9, 1.4))
lm = skin_out.mean(2, keepdims=True); lm_mean = float(lm[fm].mean())
graded = np.clip((lm_mean + (skin_out - lm_mean) * k_sd) * gain, 0, 1)
gl = graded.mean(2, keepdims=True); graded = np.clip(gl + (graded - gl) * 1.12, 0, 1)                 # a little more colour than the flat bake
print("face match: old mean %s new mean %s gain %s, spread x%.2f" % (old_mean.round(3), new_mean.round(3), gain.round(3), k_sd))
hm = blur(face_isl.astype(np.float32), 3)[:, :, None] * (0 if USE_PROJ else 1); skin_out = skin_out * (1 - hm) + graded * hm
# --- the photoreal repaint (bl_views.py render -> three views repainted by the image model, aligned by face landmarks
# (align_paint.py), projected back through the cameras with a depth test (project_paint.py)): it replaces the painted
# face where the projection is confident; the rest of the skin (neck below the collar, ears' backs, hands) keeps the old
# paint, colour-matched to the new face so there is no step at the border
PROJ = os.path.join(WORK, "skin_projected.png"); PROJM = os.path.join(WORK, "skin_projected_mask.png")
if os.path.exists(PROJ) and os.path.exists(PROJM):
    proj = np.asarray(Image.open(PROJ).convert("RGB")).astype(np.float32) / 255
    pm = np.asarray(Image.open(PROJM).convert("L")).astype(np.float32) / 255
    sure = pm > 0.85
    sure = ndi.binary_erosion(sure, iterations=3)                                    # off the projection's ragged edge (hair pixels)
    sure = ndi.binary_opening(sure, iterations=2)
    lab_p, n_p = ndi.label(sure)
    if n_p > 1:                                                                      # the face island only: the biggest patch
        sizes_p = ndi.sum(sure, lab_p, range(1, n_p + 1)); sure = lab_p == (np.argmax(sizes_p) + 1)
    sure = ndi.binary_fill_holes(sure)                                               # the occluded hole under the chin: filled below from the old skin
    painted = pm > 0.85
    # the repaint's hair is fuller than the mesh hair: where it lands on skin that was skin-coloured (not a brow, lash
    # line or nostril, which were dark before too) the old skin stays
    old_l = skin_out.mean(2); old_pink = (skin_out[:, :, 0] - skin_out[:, :, 2] > 0.1) & ((skin_out.max(2) - skin_out.min(2)) / np.maximum(skin_out.max(2), 1e-3) > 0.15)
    hair_bleed = (proj.mean(2) < 0.3) & (old_l > 0.45) & old_pink & ~ndi.binary_dilation(hole, iterations=12) & (Z < eye_z + 2.5)   # above the brows the repaint's hair wins: the old atlas painted the bangs' roots scalp-pink
    hair_bleed = ndi.binary_dilation(hair_bleed, iterations=3)
    EARJ0 = os.path.join(WORK, "ears.json")
    if os.path.exists(EARJ0):
        E0 = json.load(open(EARJ0)); rel0 = pos - np.array(E0["head"])[None, None, :]; f0 = rel0 @ np.array(E0["fwd"]); l0 = rel0 @ np.array(E0["right"])
        ear_zone = (np.abs(l0) > E0["lat_min"] - 0.8) & (f0 > E0["f_lo"] - 1.0) & (f0 < E0["f_hi"] + 0.5) & (np.abs(Z - E0["z_c"]) < 1.4 * E0["hh"])
        sure &= ~ear_zone
    m_soft = blur((sure & painted & ~hair_bleed).astype(np.float32), 4)
    # colour-match the old skin to the repaint (medians over the painted face, chroma and level)
    ref = (sure & painted & (proj.mean(2) > 0.25) & (proj.mean(2) < 0.9))
    if ref.sum() > 1000:
        g_match = np.median(proj[ref], 0) / np.maximum(np.median(skin_out[ref], 0), 1e-3)
        skin_out = np.clip(skin_out * g_match, 0, 1); print("old skin matched to the repaint: gain", g_match.round(3))
    # the hole inside the face (never seen by a camera: under the chin / behind the collar) takes the matched old skin
    skin_out = skin_out * (1 - m_soft[:, :, None]) + proj * m_soft[:, :, None]
    print("photoreal face projected: %.1f%% of the atlas" % (100 * (m_soft > 0.5).mean()))
    # above the brows the skin is the forehead under the bangs. The repaint's fuller hair painted it grey-brown, and the
    # mesh shows it between the hair spikes as grey "strands" (the real strands are the hair primitive, black). The
    # forehead is skin: every texel up there that is not skin-coloured is filled from the skin around it
    fore = face_isl & (Z > eye_z + 4.0)
    sl_f = skin_out.mean(2); pink_f = skin_out[:, :, 0] - skin_out[:, :, 2] > 0.06
    bad_f = fore & ((sl_f < 0.6) | ~pink_f)                                      # dark: the repaint's hair shadow, tan: its hair edge
    good_f = face_isl & (Z > eye_z + 1.0) & ~ndi.binary_dilation(bad_f, iterations=2) & (sl_f > 0.5) & pink_f
    if bad_f.any() and good_f.sum() > 500:
        wg = blur(good_f.astype(np.float32), 10); fl = np.stack([blur(skin_out[:, :, k] * good_f, 10) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
        fl = np.where((wg > 0.02)[:, :, None], fl, np.median(skin_out[good_f], 0)[None, None, :])
        skin_out = np.where(ndi.binary_dilation(bad_f, iterations=1)[:, :, None], fl, skin_out); print("forehead: %d non-skin px filled" % int(bad_f.sum()))
    # the temples (beside the brows, under the sideburns): the same smudges, the same fill
    temple = face_isl & (Z > eye_z + 0.5) & (Z <= eye_z + 4.0) & (np.abs(X) > 5.0)
    sl_f = skin_out.mean(2); pink_f = skin_out[:, :, 0] - skin_out[:, :, 2] > 0.06
    bad_t = temple & ((sl_f < 0.55) | ~pink_f)
    if bad_t.any() and good_f.sum() > 500:
        wg = blur(good_f.astype(np.float32), 10); fl = np.stack([blur(skin_out[:, :, k] * good_f, 10) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
        fl = np.where((wg > 0.02)[:, :, None], fl, np.median(skin_out[good_f], 0)[None, None, :])
        skin_out = np.where(ndi.binary_dilation(bad_t, iterations=1)[:, :, None], fl, skin_out); print("temples: %d non-skin px filled" % int(bad_t.sum()))

# ------------------------------------------------------------------ strokes on the skin: brows and the hairline's baby hairs
# A 3D direction at a texel becomes a UV direction through the position buffer's gradients (least squares on the two
# texel steps), so the strokes follow real growth directions on the face whatever the UV layout does.
from PIL import ImageDraw
Pu = np.zeros_like(pos); Pu[:, :-1] = pos[:, 1:] - pos[:, :-1]; Pv = np.zeros_like(pos); Pv[:-1] = pos[1:] - pos[:-1]
def uv_dir(y, x, d3):
    pu, pv = Pu[y, x], Pv[y, x]; m11, m12, m22 = pu @ pu, pu @ pv, pv @ pv; det = m11 * m22 - m12 * m12
    if det < 1e-10: return None
    r1, r2 = pu @ d3, pv @ d3; du = (m22 * r1 - m12 * r2) / det; dv = (m11 * r2 - m12 * r1) / det    # texels per cm
    if not np.isfinite(du + dv) or np.hypot(du, dv) > 70 or np.hypot(du, dv) < 4: return None          # a degenerate step (an island edge) would throw a line across the atlas
    return du, dv
def strokes(img, pts, colour, alpha, width_px):
    """pts: (y, x, dy, dx, length_texels, alpha_mul); drawn on an RGBA layer, composited"""
    layer = Image.new("RGBA", (2 * S, 2 * S), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)              # drawn at 2x and brought down: anti-aliased hairs
    for (y, x, dy, dx, ln, am) in pts:
        n_ = np.hypot(dx, dy); ln = min(ln, 45)
        if n_ < 1e-6: continue
        ux, uy = dx / n_, dy / n_; px_, py_ = -uy, ux; bend = rng_s.uniform(-0.18, 0.18) * ln       # a gentle curve
        poly = [(2 * (x + ux * ln * t_ + px_ * bend * (t_ * (1 - t_)) * 2), 2 * (y + uy * ln * t_ + py_ * bend * (t_ * (1 - t_)) * 2)) for t_ in (0, 0.25, 0.5, 0.75, 1.0)]
        d.line(poly, fill=tuple(int(c * 255) for c in colour) + (int(255 * alpha * am),), width=2 * width_px)
    layer = layer.resize((S, S), Image.LANCZOS)
    lay = np.asarray(layer).astype(np.float32) / 255; a_ = lay[:, :, 3:4]
    return img * (1 - a_) + lay[:, :, :3] * a_
rng_s = np.random.default_rng(11)
brow_col = np.array([0.17, 0.11, 0.08]); n_brow = 0; strokes_all = []
for sgn in (1, -1):                                                        # +X is his left
    zone = face_isl & (Z > eye_z + 0.8) & (Z < eye_z + 4.8) & (X * sgn > 0.6) & (X * sgn < 6.8) & (Y < -4)
    dark_b = zone & (skin_out.mean(2) < 0.5)
    dark_b = ndi.binary_opening(dark_b, iterations=1)
    if dark_b.sum() < 200: print("no brow found on side", sgn); continue
    lab_b, n_b = ndi.label(dark_b); dark_b = lab_b == (np.argmax(ndi.sum(dark_b, lab_b, range(1, n_b + 1))) + 1)   # the brow: the biggest dark blob
    ys_b, xs_b = np.nonzero(dark_b); Xb, Zb = X[ys_b, xs_b] * sgn, Z[ys_b, xs_b]
    x_in, x_out = np.percentile(Xb, 2), np.percentile(Xb, 98)
    for k_ in range(int(len(ys_b) / 18)):                                  # strokes per brow ~ its texel count / 18
        j = rng_s.integers(len(ys_b)); y, x = int(ys_b[j]), int(xs_b[j]); xb = Xb[j]
        s_ = (xb - x_in) / max(x_out - x_in, 1e-3)                          # 0 inner end .. 1 outer end
        dens = min(1.0, s_ / 0.12) * min(1.0, (1 - s_) / 0.18)              # the ends thin out
        if rng_s.random() > 0.35 + 0.65 * dens: continue
        theta = np.radians(68 - 95 * s_ ** 1.1 + rng_s.normal(0, 9))        # inner: steeply up and out; outer: slightly down and out
        d3 = np.array([sgn * np.cos(theta), 0.0, np.sin(theta)])            # outward = +|X|, up = +Z
        uvd = uv_dir(y, x, d3)
        if uvd is None: continue
        ln_cm = rng_s.uniform(0.45, 0.85) * (0.7 + 0.5 * dens); du, dv = uvd; scale = np.hypot(du, dv)
        strokes_pts = [(y, x, dv, du, ln_cm * scale, 0.55 + 0.45 * dens * rng_s.random())]
        strokes_all.append((strokes_pts[0], brow_col * rng_s.uniform(0.8, 1.15))); n_brow += 1
print("brow strokes drawn:", n_brow)
for shade in (0.85, 1.1):                                                   # two passes: darker and lighter hairs
    skin_out = strokes(skin_out, [pt for pt, c_ in strokes_all if (c_.mean() < brow_col.mean()) == (shade < 1)], brow_col * shade, 0.55, 1)
HAIRV = os.path.join(WORK, "hair_verts.npy")
if os.path.exists(HAIRV):
    from scipy.spatial import cKDTree
    hv = np.load(HAIRV); tree = cKDTree(hv)
    cand = face_isl & (Z > eye_z + 3.0) & (Y < 2)                          # the forehead and the temples, not the nape
    ys_c, xs_c = np.nonzero(cand); dists, idx_h = tree.query(pos[ys_c, xs_c], k=1)
    near = (dists > 0.15) & (dists < 1.3)
    pick = np.nonzero(near)[0]; rng_s.shuffle(pick); pick = pick[:700]
    pts = []
    for j in pick:
        y, x = int(ys_c[j]), int(xs_c[j]); away = pos[y, x] - hv[idx_h[j]]; away /= max(np.linalg.norm(away), 1e-6)
        d3 = away * 0.7 + np.array([0, 0, -1.0]) * 0.5 + rng_s.normal(0, 0.25, 3); d3 /= np.linalg.norm(d3)
        uvd = uv_dir(y, x, d3)
        if uvd is None: continue
        du, dv = uvd; scale = np.hypot(du, dv); fall = 1 - (dists[j] - 0.15) / 1.15
        pts.append((y, x, dv, du, rng_s.uniform(0.25, 0.5) * scale, 0.25 + 0.5 * fall * rng_s.random()))
    skin_out = strokes(skin_out, pts, np.array([0.14, 0.10, 0.08]), 0.7, 1); print("baby hairs along the hairline:", len(pts))
EARJ = os.path.join(WORK, "ears.json")
if os.path.exists(EARJ):                                                   # the ears: the relief's tone (occluded concha darker, the thin helix and lobe warmer: light through them)
    EARS = json.load(open(EARJ)); relE = pos - np.array(EARS["head"])[None, None, :]
    fE = relE @ np.array(EARS["fwd"]); lE = relE @ np.array(EARS["right"])
    uE = (fE - EARS["f_c"]) / EARS["hw"]; vE = (Z - EARS["z_c"]) / EARS["hh"]; rE = np.hypot(uE, vE)
    smE = lambda x, a, b: np.clip((x - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((x - a) / (b - a), 0, 1))
    on_ear = cov & (np.abs(lE) > EARS["lat_min"] - 0.4) & (fE > EARS["f_lo"] - 0.5) & (fE < EARS["f_hi"]) & (rE < 1.15)
    rimE = np.exp(-((rE - 0.86) / 0.11) ** 2) * (1 - smE(uE, 0.3, 0.7)); lobeE = smE(-vE, 0.55, 0.9) * (1 - smE(rE, 0.9, 1.05))
    rcE = np.hypot(uE - 0.15, vE + 0.1) / 0.40; conchaE = np.maximum(0.0, 1 - rcE * rcE)
    warm = np.clip(0.55 * rimE + 0.6 * lobeE, 0, 1) * on_ear; dark_e = conchaE * on_ear
    skin_out[:, :, 0] = np.clip(skin_out[:, :, 0] * (1 + 0.07 * warm), 0, 1); skin_out[:, :, 1] = np.clip(skin_out[:, :, 1] * (1 - 0.02 * warm), 0, 1); skin_out[:, :, 2] = np.clip(skin_out[:, :, 2] * (1 - 0.06 * warm), 0, 1)
    skin_out = np.clip(skin_out * (1 - 0.10 * dark_e)[:, :, None], 0, 1); print("ear tint: %d texels" % int(on_ear.sum()))
    # the old paint smeared hair shadows over the ears: non-skin texels there are filled from the ear's own skin
    sl_e = skin_out.mean(2); pink_e = skin_out[:, :, 0] - skin_out[:, :, 2] > 0.06
    bad_e = on_ear & ((sl_e < 0.55) | ~pink_e); good_e = on_ear & ~ndi.binary_dilation(bad_e, iterations=2) & (sl_e >= 0.55) & pink_e
    if bad_e.any() and good_e.sum() > 300:
        wg = blur(good_e.astype(np.float32), 8); fl = np.stack([blur(skin_out[:, :, k] * good_e, 8) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
        fl = np.where((wg > 0.02)[:, :, None], fl, np.median(skin_out[good_e], 0)[None, None, :])
        skin_out = np.where(ndi.binary_dilation(bad_e, iterations=1)[:, :, None], fl, skin_out); print("ears: %d smudged px filled" % int(bad_e.sum()))
    sm_e = np.stack([blur(skin_out[:, :, k] * on_ear, 6) for k in range(3)], 2) / np.maximum(blur(on_ear.astype(np.float32), 6), 1e-3)[:, :, None]
    m_e = blur(ndi.binary_erosion(on_ear, iterations=3).astype(np.float32), 3)[:, :, None]
    skin_out = skin_out * (1 - m_e) + sm_e * m_e                           # smoothed AFTER the fill: the fill's patch edges and the old atlas's tiny ear islands both left pale outlines
# (the full-body repaint views were tried on the skin too, work/skin_body_projected.png: at 1536 px for 1.8 m the hands are
#  80 px and the repaint's hair shadows landed on the throat; the hands and the neck keep the evened old skin below)
# the hands: texels that are not skin (dark grey from the cuff, white from the socks: the old atlas's padding next to the
# hand island) are filled from the skin around them
hands_all = cov & (Z < 125)
hs = skin_out[:, :, 0] - skin_out[:, :, 2]; hl0 = skin_out.mean(2)
bad_h = hands_all & ((hl0 < 0.45) | (hs < 0.06) | (hl0 > 0.93)); good_h = hands_all & ~ndi.binary_dilation(bad_h, iterations=2)
if bad_h.any() and good_h.any():
    wg = blur(good_h.astype(np.float32), 6); fl = np.stack([blur(skin_out[:, :, k] * good_h, 6) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
    skin_out = np.where(ndi.binary_dilation(bad_h, iterations=1)[:, :, None], fl, skin_out); print("hands: %d non-skin px filled" % int(bad_h.sum()))
# the old bake has a lighter wedge on the back of each wrist (baked light); flatten the low-frequency luminance
hands = cov & (Z < 125) & (skin_out.mean(2) > 0.3)
if hands.any():
    hl = skin_out.mean(2); w_h = blur(hands.astype(np.float32), 12); lo_h = blur(hl * hands, 12) / np.maximum(w_h, 1e-3)
    mean_h = float(np.median(hl[hands])); gain_h = np.clip(mean_h / np.maximum(lo_h, 1e-3), 0.8, 1.25)
    hm_ = blur(hands.astype(np.float32), 3)[:, :, None]; skin_out = np.clip(skin_out * (gain_h[:, :, None] * hm_ + (1 - hm_)), 0, 1)
rgba = np.concatenate([skin_out, alpha[:, :, None]], 2)
Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "tex_skin.png")); print("wrote tex_skin.png (RGBA)")
skin_n = sanitize_normal(load("nrm_skin.png"))
if os.path.exists(EARJ):                                                      # the ear's per-triangle tangent seams (the extra subdivision + the relief) showed as thin contour lines: the bake is smoothed there, the relief's own bump stays
    ear_n = ndi.binary_erosion(on_ear, iterations=2); m_n = blur(ear_n.astype(np.float32), 2)[:, :, None]
    sm_n = np.stack([blur(skin_n[:, :, k], 2.0) for k in range(3)], 2); skin_n = skin_n * (1 - m_n) + sm_n * m_n
    v_ = skin_n * 2 - 1; v_ /= np.maximum(np.linalg.norm(v_, axis=2, keepdims=True), 1e-6); skin_n = (v_ + 1) / 2
save("tex_skin_n.png", skin_n)
save("tex_skin_orm.png", orm(pad_full(np.clip(blur(load("ao_skin.png", S)[:, :, 0], 1.5) * 0.5 + 0.5, 0, 1), cov_skin), pad_full(load("rough_skin.png")[:, :, 0], cov_skin)))   # AO softened: skin is translucent

# --- eyelid colour: the skin around the eyes, a little darker
ring = np.zeros((S, S), bool)
for e in eyes.values(): ring |= ndi.binary_dilation(e["mask"], iterations=14) & ~ndi.binary_dilation(e["mask"], iterations=4)
ring &= face & (r - b > 0.1) & (lum > 0.4)
lid_col = skin[ring].mean(0) if ring.any() else np.array([0.85, 0.65, 0.58]); print("lid colour", lid_col.round(3))

# ------------------------------------------------------------------ hair
hair = load("bake_hair.png"); H = hair.shape[0]
cov_hair = covered_of(hair); hair = pad_full(hair, cov_hair)
# the baked hair colour is near-black and flat: keep it, with a little variation from the roughness noise so strands read
rh = load("rough_hair.png")[:, :, 0]
var = (blur(rh, 1.0) - 0.5) * 0.08
hair_out = np.clip(hair * (1 + var[:, :, None]), 0, 1)
hr, hg, hb = hair_out[:, :, 0], hair_out[:, :, 1], hair_out[:, :, 2]; hl = hair_out.mean(2)
skinny = ((hr - hb > 0.07) & (hl > 0.22)) | (hl > 0.45)                       # pink scalp / skin bleed, or grey-white glints
skinny = ndi.binary_dilation(skinny, iterations=2)
good_h = ~skinny & (hl > 0.01)
wgt = blur(good_h.astype(np.float32), 6); fill = np.stack([blur(hair_out[:, :, k] * good_h, 6) for k in range(3)], 2) / np.maximum(wgt, 1e-3)[:, :, None]
hair_out = np.where(skinny[:, :, None], fill, hair_out); print("hair: %d skin-coloured px replaced" % int(skinny.sum()))
# near-black, as the old metallic-black hair read: any texel over 0.2 (pale streaks from the old atlas) is pulled down,
# the whole atlas darkened; the sheen goes through the roughness (see the ORM below)
hl2 = hair_out.mean(2, keepdims=True); hair_out = np.where(hl2 > 0.2, hair_out * (0.2 / np.maximum(hl2, 1e-3)), hair_out)
hair_out = np.clip(hair_out * 0.6, 0, 1)
save("tex_hair.png", hair_out)
save("tex_hair_n.png", sanitize_normal(np.asarray(Image.open(os.path.join(WORK, "nrm_hair.png")).convert("RGB").resize((H, H), Image.LANCZOS)).astype(np.float32) / 255))
save("tex_hair_orm.png", orm(pad_full(np.clip(load("ao_hair.png", H)[:, :, 0] * 0.8 + 0.2, 0, 1), cov_hair), pad_full(np.clip(rh + 0.42, 0, 1), cov_hair)))   # matte: ~0.75 after the page's 0.78

# ------------------------------------------------------------------ cloth (hoodie, pants, socks, slides)
cloth = load("bake_cloth.png"); C = cloth.shape[0]
cov_cloth = covered_of(cloth); cloth = pad_full(cloth, cov_cloth)
# the old material was metallic (metallicFactor 1, no map), which rendered the clothes much darker than their painted
# colour; the new dielectric materials are graded to the look the owner knows: blacks stay black, the hoodie's grey
# stays mid-grey, the socks and the stripe stay white (measured on the same frame, render/compare.mjs)
cl = cloth.mean(2); k = np.interp(cl, [0.0, 0.12, 0.3, 0.5, 0.75, 1.0], [0.18, 0.22, 0.41, 0.47, 1.0, 1.0])   # the hoodie as dark as the old render (lum 0.36 on the door frame)
cloth_g = np.clip(cloth * k[:, :, None], 0, 1)
# The clothes' albedo is rebuilt as fabric MATERIALS, the way game clothes are authored: a flat dyed base per garment
# with the fibre-scale variation of the cloth, and nothing else. Shading belongs to the lights, the baked AO and the
# knit / weave normal maps. The old atlas (Meshy) had the light baked in (the "PVC" highlights on the pants, the lighter
# wedges on the cuffs), its island padding bled skin into the cuffs, socks into the slides, the striped flap inside the
# cuff; a photoreal repaint of the whole body projected back (work/cloth_projected.png, kept for reference) baked the
# repaint's folds and lighting in just the same way and they did not sit on the mesh's folds. The old atlas keeps two
# jobs: the garment regions (through the build's region map) and the white stripe of the pants.
REG = os.path.join(WORK, "region_cloth.npy")
if os.path.exists(REG):
    reg = np.asarray(Image.fromarray(np.load(REG)[::-1]).resize((C, C), Image.NEAREST))     # Blender images are bottom-up
    rng_c = np.random.default_rng(3)
    def fbm(sig):                                                                # a blurred noise field, zero mean, unit spread
        n = blur(rng_c.random((C, C)).astype(np.float32), sig); return (n - n.mean()) / max(n.std(), 1e-6)
    hoodie_r = reg == 3; pants_r = reg == 4; socks_r = reg == 5; slides_r = reg == 6
    lc = cloth_g.mean(2)
    # the hoodie's tone: the graded old hoodie's median (lum 0.36 on the door frame in the old render), kept slightly cool
    hood_ref = hoodie_r & cov_cloth & (lc > 0.12) & (lc < 0.6) & (np.abs(cloth_g[:, :, 0] - cloth_g[:, :, 2]) < 0.05)
    hood_med = np.median(cloth_g[hood_ref], 0) if hood_ref.sum() > 1000 else np.array([0.128, 0.129, 0.135])
    hood_med = hood_med * 0.92 * np.array([0.985, 1.0, 1.02])              # measured ~0.13, a notch darker: the review asked for a hoodie no lighter than the old one (old 0.40 / new 0.38 sRGB on the chest at the room camera, after this)
    heather = 1 + 0.07 * fbm(18) + 0.035 * fbm(5) + 0.03 * fbm(0.8)              # heathered jersey: slubs, fibres
    hoodie_col = np.clip(hood_med[None, None, :] * heather[:, :, None], 0, 1)
    # the pants: black polyester, the white side stripe where the old atlas is white inside the pants region
    stripe = pants_r & (cl > 0.5) & (np.abs(cloth[:, :, 0] - cloth[:, :, 2]) < 0.12)
    stripe = ndi.binary_opening(stripe, iterations=1); stripe = ndi.binary_closing(stripe, iterations=1)
    lab_s, n_s = ndi.label(stripe)
    if n_s:
        sz = ndi.sum(stripe, lab_s, range(1, n_s + 1)); stripe &= np.isin(lab_s, np.nonzero(sz >= 40)[0] + 1)   # specks of padding are not the stripe
    stripe_soft = blur(stripe.astype(np.float32), 0.8)
    pants_col = np.array([0.026, 0.026, 0.030])[None, None, :] * (1 + 0.10 * fbm(2.5) + 0.05 * fbm(16))[:, :, None]
    stripe_col = np.array([0.88, 0.88, 0.87])[None, None, :] * (1 + 0.03 * fbm(2.5))[:, :, None]
    pants_col = np.clip(pants_col * (1 - stripe_soft[:, :, None]) + stripe_col * stripe_soft[:, :, None], 0, 1)
    # the socks: white ribbed cotton (the ribs are in the normal map), the slides: black EVA foam
    socks_col = np.ones((C, C, 3), np.float32) * np.array([0.93, 0.925, 0.91])[None, None, :]      # flat white cotton: the knit lives in the normal map alone
    slides_col = np.clip(np.array([0.05, 0.05, 0.053])[None, None, :] * (1 + 0.12 * fbm(1.5) + 0.05 * fbm(10))[:, :, None], 0, 1)
    cloth_g = np.where(hoodie_r[:, :, None], hoodie_col, np.where(pants_r[:, :, None], pants_col, np.where(socks_r[:, :, None], socks_col, np.where(slides_r[:, :, None], slides_col, cloth_g))))
    # the feet: the mesh is one shell there (the slide's strap and the pants' cuff are bulges of the sock, Meshy's remesh),
    # so a label per triangle draws the sock's edge as a zigzag of triangle edges. The old atlas drew it inside the
    # triangles: its texels are bimodal at the feet (0.1-0.3 the slide and the cuff, 0.9+ the sock), so the sock is
    # painted where the old atlas is white, the cuff above 8.5 cm and the slide below elsewhere, whatever the triangle's label
    PZ = os.path.join(WORK, "pos_cloth.npy")
    if os.path.exists(PZ):
        pc3 = np.load(PZ)[::-1].astype(np.float32)
        pc = np.stack([np.asarray(Image.fromarray(pc3[:, :, k], "F").resize((C, C), Image.BILINEAR)) for k in range(3)], 2)
        zc = pc[:, :, 2]
        feet = (reg > 0) & (zc < 14.0)
        # inside the sock-labelled faces (the build re-reads every foot face from its own old texels) the sock is whole:
        # the old paint's grey seams and padding do not cut it; inside the slide's and the cuff's faces only a solid white
        # patch of the old paint (the sock's edge crossing the triangle) is sock, never a sliver of padding
        white_t = feet & (cl > 0.9) & (np.abs(cloth[:, :, 0] - cloth[:, :, 2]) < 0.12) & ~socks_r
        white_t = ndi.binary_closing(ndi.binary_opening(white_t, iterations=2), iterations=1)
        lab_k, n_k = ndi.label(white_t)
        if n_k:
            sz = ndi.sum(white_t, lab_k, range(1, n_k + 1)); white_t &= np.isin(lab_k, np.nonzero(sz >= 150)[0] + 1)
        SV = os.path.join(WORK, "socks_verts.npy")
        if os.path.exists(SV):                                               # only next to the sock proper: the sock's edge crossing a slide or cuff triangle, never a far patch
            from scipy.spatial import cKDTree
            dsock, _ = cKDTree(np.load(SV)).query(pc[white_t], k=1); keep = np.zeros_like(white_t); keep[white_t] = dsock < 0.35; white_t = keep
        sock_tex = socks_r & feet                                             # the sock faces alone: the old paint's white patches inside slide faces broke the strap into "cow print" 
        FJ = os.path.join(WORK, "feet.json")
        if os.path.exists(FJ):                                               # the toe seam across the front, the heel seam up the back: a thread's shadow
            FEET_ = json.load(open(FJ)); seam = np.zeros((C, C), np.float32)
            for side, sgn in (("left", 1), ("right", -1)):
                ft = FEET_[side]; onside = (pc[:, :, 0] * sgn > 0)
                seam += onside * (zc < 4.5) * np.exp(-((pc[:, :, 1] - (ft["y_toe"] + 1.0)) / 0.10) ** 2)
                seam += onside * (zc < 9.0) * (pc[:, :, 1] > ft["y_heel"] - 2.5) * np.exp(-((pc[:, :, 0] - ft["x_mid"]) / 0.10) ** 2)
            socks_col = np.clip(socks_col * (1 - 0.18 * np.clip(seam, 0, 1))[:, :, None], 0, 1)
        sock_tex = ndi.binary_dilation(sock_tex, iterations=3) & ~(pants_r | slides_r)      # into the islands' margins (reg is baked without margin): else every sock seam drew a dark crack
        sock_soft = blur(sock_tex.astype(np.float32), 1.0)[:, :, None]
        foot_dark = np.where((zc > 8.5)[:, :, None], pants_col, slides_col)
        hem = np.zeros((C, C), np.float32)                                   # (a per-texel hem showed as dark cracks along the sock's UV island edges: the hem is a label line, build_mesh.py, 10 cm)
        if False and os.path.exists(FJ) and "ankle" in json.load(open(FJ)):     # (off, see build_mesh.py: the ankle is not round)
            ANK = json.load(open(FJ))["ankle"]
            for side, sgn in (("left", 1), ("right", -1)):
                if side not in ANK: continue
                A_ = ANK[side]; onside = (pc[:, :, 0] * sgn > 0) & (zc > 7.5) & (zc < 12.5)
                ang = np.arctan2(pc[:, :, 1] - A_["cy"], pc[:, :, 0] - A_["cx"]); b_ = (((ang + np.pi) / (2 * np.pi) * 16).astype(int)) % 16
                rad = np.hypot(pc[:, :, 0] - A_["cx"], pc[:, :, 1] - A_["cy"]); rs = np.array(A_["r_sock"])[b_]
                hem = np.maximum(hem, (onside & (rad > rs + 0.45)).astype(np.float32))
        hem = blur(hem, 0.8)[:, :, None]; sock_soft = sock_soft * (1 - hem)
        feet_d = ndi.binary_dilation(feet, iterations=3)
        cloth_g = np.where(feet_d[:, :, None], foot_dark * (1 - sock_soft) + socks_col * sock_soft, cloth_g)
        print("feet: %d sock texels drawn from the old atlas (of %d foot texels)" % (int(sock_tex.sum()), int(feet.sum())))
    cloth_g = pad_full(cloth_g, reg > 0)                                        # between the islands: the nearest garment, so the mips never pull in a foreign colour
    print("cloth materials: hoodie %s, stripe %d px, regions hoodie %d pants %d socks %d slides %d" % (hood_med.round(3), int(stripe.sum()), hoodie_r.sum(), pants_r.sum(), socks_r.sum(), slides_r.sum()))
    CPROJ = os.path.join(WORK, "cloth_projected.png"); CPROJM = os.path.join(WORK, "cloth_projected_mask.png")
    if os.path.exists(CPROJ) and os.path.exists(CPROJM):                        # the repaint as a tone reference only
        cp = np.asarray(Image.open(CPROJ).convert("RGB").resize((C, C), Image.LANCZOS)).astype(np.float32) / 255
        cpm = np.asarray(Image.open(CPROJM).convert("L").resize((C, C), Image.LANCZOS)).astype(np.float32) / 255
        ref_h = hoodie_r & (cpm > 0.8)
        if ref_h.sum() > 1000: print("  reference: the repaint's hoodie median %s (lit), ours %s (albedo)" % (np.median(cp[ref_h], 0).round(3), hood_med.round(3)))
save("tex_cloth.png", cloth_g)
save("tex_cloth_n.png", sanitize_normal(load("nrm_cloth.png")))
ao_c = load("ao_cloth.png", C)[:, :, 0]
ao_c = np.clip(np.where(reg == 3, ao_c ** 1.3, ao_c * 0.85 + 0.15), 0, 1) if os.path.exists(REG) else np.clip(ao_c * 0.85 + 0.15, 0, 1)   # the hoodie's folds read through its occlusion (the old atlas had them baked into the colour)
if os.path.exists(REG):                                                       # the socks' own sole is baked INSIDE the slides (black AO): the page shows it with the slides hidden;
    sock_d = ndi.binary_dilation(reg == 5, iterations=10) & ((reg == 5) | (reg == 0))   # the islands' margins too (reg is baked without margin): dark gutters there drew cracks along every sock seam
    ao_c = np.where(sock_d, np.maximum(ao_c, 0.92), ao_c)
save("tex_cloth_orm.png", orm(pad_full(ao_c, cov_cloth), pad_full(load("rough_cloth.png")[:, :, 0], cov_cloth)))

# ------------------------------------------------------------------ the eyeball and the lid
E = 1024
yy, xx = np.mgrid[0:E, 0:E]; u = (xx + 0.5) / E - 0.5; v = (yy + 0.5) / E - 0.5; rr = np.hypot(u, v); ang = np.arctan2(v, u)
rng = np.random.default_rng(7)
IRIS, PUPIL, LIMBUS = 0.123, 0.042, 0.108                              # uv radii (see assemble.mjs: r = 0.5 * polar / (pi * 0.55)): iris 1.15 cm, pupil 0.4 cm
eye = np.zeros((E, E, 3), np.float32)
sclera_col = np.array([0.88, 0.85, 0.83]); veins = blur(rng.random((E, E)).astype(np.float32), 1.2)
eye[:] = sclera_col * (1 - 0.06 * np.clip((rr - 0.2) / 0.3, 0, 1))[:, :, None]           # a little darker towards the back
eye *= (1 - 0.42 * np.clip((v - 0.05) / 0.17, 0, 1))[:, :, None]                           # the upper lid's shadow (v > 0.5 is up)
eye *= (1 - 0.12 * np.clip((-v - 0.16) / 0.1, 0, 1))[:, :, None]                            # and a lighter one from the lower lid
eye[:, :, 0] += 0.06 * np.clip((rr - 0.17) / 0.12, 0, 1) * (veins > 0.62)                 # faint red veins
tr_ = np.clip((rr - PUPIL) / (IRIS - PUPIL), 0, 1)
fib = 0.5 + 0.5 * np.sin(ang * 70 + 3 * np.sin(ang * 11)) * tr_                             # the radial fibres
fib = 0.65 * fib + 0.35 * (0.5 + 0.5 * np.sin(ang * 190 + 2 * np.sin(ang * 23 + 1.0)) * tr_)   # finer fibres between them
crypts = blur(rng.random((E, E)).astype(np.float32), 3.0); fib = fib * (0.8 + 0.4 * (crypts > 0.52))   # Fuchs' crypts: darker pits in a ring
collar = np.exp(-((rr - (PUPIL + 0.35 * (IRIS - PUPIL))) / 0.012) ** 2) * 0.35                # the collarette: a brighter frill round the pupil
iris_in = np.array([0.30, 0.16, 0.08]); iris_out = np.array([0.11, 0.06, 0.035])                 # dark brown, as painted
t = np.clip((rr - PUPIL) / (IRIS - PUPIL), 0, 1)[:, :, None]
iris = iris_in * (1 - t) + iris_out * t; iris = iris * (0.70 + 0.6 * fib[:, :, None] + collar[:, :, None]) + 0.03 * blur(rng.random((E, E)).astype(np.float32), 0.8)[:, :, None]
iris *= (1 - 0.6 * np.clip((rr - LIMBUS) / (IRIS - LIMBUS), 0, 1))[:, :, None]            # limbal ring
in_iris = rr < IRIS; soft = np.clip((IRIS - rr) / 0.006, 0, 1)[:, :, None]
eye = eye * (1 - soft) + iris * soft
pupil = np.clip((PUPIL - rr) / 0.005, 0, 1)[:, :, None]; eye = eye * (1 - pupil) + np.array([0.02, 0.015, 0.012]) * pupil
# a painted catch-light (the window's reflection), upper-left of the pupil, as the old painted eyes had: the real
# specular from the cornea comes on top of it in the room
cl = np.exp(-((u + 0.045) ** 2 + (v - 0.05) ** 2) / (2 * 0.016 ** 2))[:, :, None]; eye = eye * (1 - cl) + np.array([0.95, 0.95, 0.97]) * cl
cl2 = np.exp(-((u - 0.03) ** 2 + (v + 0.04) ** 2) / (2 * 0.008 ** 2))[:, :, None] * 0.5; eye = eye * (1 - cl2) + np.array([0.9, 0.9, 0.95]) * cl2
save("tex_eye.png", eye)
# the lashes: a card texture, 256 x 128, transparent, with tapered dark hairs rooted at the bottom edge and fanning up;
# assemble.mjs puts ~14 cards along each upper lid and 8 shorter ones along the lower lid
LW, LH = 256, 128; lash = np.zeros((LH, LW, 4), np.float32)
from PIL import ImageDraw as _ID
lim = Image.new("RGBA", (LW, LH), (0, 0, 0, 0)); ld = _ID.Draw(lim)
for k in range(9):
    x0 = 14 + k * 28 + rng.integers(-5, 6); tilt = rng.uniform(-0.25, 0.25); ln = rng.uniform(0.7, 1.0) * (LH - 8)
    pts = [(x0 + tilt * ln * (t_ / 10) ** 1.6 * 2.5, LH - 1 - ln * t_ / 10) for t_ in range(11)]
    for t_ in range(10):
        w = max(1, int(round(5 * (1 - t_ / 10) ** 1.3))); al = int(255 * (0.95 - 0.5 * (t_ / 10) ** 2))
        ld.line([pts[t_], pts[t_ + 1]], fill=(28, 18, 12, al), width=w)
lash = np.asarray(lim).astype(np.float32) / 255
Image.fromarray(np.clip(lash * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "tex_lash.png")); print("wrote tex_lash.png")
L = 128; yy, xx = np.mgrid[0:L, 0:L]; rl = np.hypot((xx + 0.5) / L - 0.5, (yy + 0.5) / L - 0.5)
lid = np.ones((L, L, 3), np.float32) * lid_col; edge = np.clip((rl - 0.34) / 0.11, 0, 1)[:, :, None]
lid = lid * (1 - 0.72 * edge) ; save("tex_lid.png", lid)

spec = {
    "eyes": spec_eyes,
    "lid": {"openAngle": 1.45, "capAngle": 1.3, "closedAngle": 0.55},
    "sizes": {"skin_n": 1024, "skin_orm": 1024, "hair_n": 512, "hair_orm": 512, "cloth_n": 1024, "cloth_orm": 1024},
    "materials": {
        "skin":   {"base": "skin", "baseQ": 90, "normal": "skin_n", "normalScale": 0.5, "orm": "skin_orm", "alphaMask": True, "sheen": [0.35, 0.25, 0.22], "sheenRoughness": 0.8, "doubleSided": True},
        "hair":   {"base": "hair", "baseQ": 82, "normal": "hair_n", "normalScale": 0.15, "orm": "hair_orm", "doubleSided": True},
        "hoodie": {"base": "cloth", "baseQ": 86, "normal": "cloth_n", "normalScale": 1.4, "orm": "cloth_orm", "sheen": [0.2, 0.2, 0.2], "sheenRoughness": 0.8, "doubleSided": True},   # the hood's inside shows at the open collar
        "pants":  {"base": "cloth", "normal": "cloth_n", "normalScale": 0.7, "orm": "cloth_orm", "doubleSided": True},
        "socks":  {"base": "cloth", "normal": "cloth_n", "normalScale": 0.5, "orm": "cloth_orm", "sheen": [0.35, 0.35, 0.35], "sheenRoughness": 0.9, "doubleSided": True},
        "slides": {"base": "cloth", "normal": "cloth_n", "normalScale": 0.5, "orm": "cloth_orm", "doubleSided": True},
        "eye":    {"base": "eye", "baseQ": 90, "roughness": 0.35},
        "cornea": {"color": [1, 1, 1, 0.08], "roughness": 0.05, "clearcoat": 1.0, "clearcoatRoughness": 0.03, "blend": True},
        "lid":    {"base": "lid", "roughness": 0.75},
        "lash":   {"base": "lash", "baseQ": 92, "blend": True, "roughness": 0.55, "doubleSided": True, "color": [0.55, 0.5, 0.5, 1]},
    },
    "lashes": {"upper": {"n": 20, "length": 0.0065, "width": 0.0026}, "lower": {"n": 5, "length": 0.0018, "width": 0.0016}, "rimDepth": 0.0010, "caruncle": 0.0008},
}
json.dump(spec, open(os.path.join(OUT, "spec.json"), "w"), indent=1)
print("wrote spec.json", json.dumps(spec["eyes"]))
