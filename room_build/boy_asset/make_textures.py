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
    eyes[side] = {"mask": grown, "surface": centre, "forward": fwd, "width": float(np.hypot(ext[0], ext[1]))}
RADIUS = 1.5                                                           # cm; over the real 1.2 so the ball fills the opening's corners
INSET = 0.12                                                           # the cornea apex sits this far behind the painted surface
def to_gltf(v):   # Blender z up (x, y, z) cm -> glTF y up metres (x, z, -y)
    return [float(v[0]) / 100, float(v[2]) / 100, float(-v[1]) / 100]
spec_eyes = {"radius": RADIUS / 100}
for side, e in eyes.items():
    c = e["surface"] - e["forward"] * (RADIUS + INSET)
    spec_eyes[side] = {"center": to_gltf(c), "forward": [float(e["forward"][0]), float(e["forward"][2]), float(-e["forward"][1])]}
# the eye openings become holes in the skin (MASK alpha): one pixel of lid kept all round, and never wider than the
# eyeball behind them (a hole past the ball's silhouette would show the inside of the head)
hole = np.zeros((S, S), bool)
for e in eyes.values():
    c = e["surface"] - e["forward"] * (RADIUS + INSET); d = pos - c
    lateral = np.linalg.norm(d - (d @ e["forward"])[:, :, None] * e["forward"], axis=2)
    inner = np.abs(X) > abs(e["surface"][0]) - 0.32 * e["width"]       # the inner corner (towards the nose) stays painted: the ball sits deeper there
    hole |= ndi.binary_erosion(e["mask"], iterations=4) & (lateral < RADIUS * 0.8) & inner
alpha = 1 - blur(hole.astype(np.float32), 1.0)
alpha = np.where(hole, np.minimum(alpha, 0.3), np.maximum(alpha, 0.7))      # keep the blurred edge inside the cutoff band

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
save("tex_skin_n.png", sanitize_normal(load("nrm_skin.png")))
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
    socks_col = np.clip(np.array([0.92, 0.915, 0.90])[None, None, :] * (1 + 0.035 * fbm(4) + 0.03 * fbm(1.0))[:, :, None], 0, 1)
    slides_col = np.clip(np.array([0.05, 0.05, 0.053])[None, None, :] * (1 + 0.12 * fbm(1.5) + 0.05 * fbm(10))[:, :, None], 0, 1)
    cloth_g = np.where(hoodie_r[:, :, None], hoodie_col, np.where(pants_r[:, :, None], pants_col, np.where(socks_r[:, :, None], socks_col, np.where(slides_r[:, :, None], slides_col, cloth_g))))
    # the feet: the mesh is one shell there (the slide's strap and the pants' cuff are bulges of the sock, Meshy's remesh),
    # so a label per triangle draws the sock's edge as a zigzag of triangle edges. The old atlas drew it inside the
    # triangles: its texels are bimodal at the feet (0.1-0.3 the slide and the cuff, 0.9+ the sock), so the sock is
    # painted where the old atlas is white, the cuff above 8.5 cm and the slide below elsewhere, whatever the triangle's label
    PZ = os.path.join(WORK, "posz_cloth.npy")
    if os.path.exists(PZ):
        zc = np.asarray(Image.fromarray(np.load(PZ)[::-1].astype(np.float32), "F").resize((C, C), Image.BILINEAR))
        feet = (reg > 0) & (zc < 14.0)
        # inside the sock-labelled faces (the build re-reads every foot face from its own old texels) the sock is whole:
        # the old paint's grey seams and padding do not cut it; inside the slide's and the cuff's faces only a solid white
        # patch of the old paint (the sock's edge crossing the triangle) is sock, never a sliver of padding
        white_t = feet & (cl > 0.9) & (np.abs(cloth[:, :, 0] - cloth[:, :, 2]) < 0.12) & ~socks_r
        white_t = ndi.binary_closing(ndi.binary_opening(white_t, iterations=2), iterations=1)
        lab_k, n_k = ndi.label(white_t)
        if n_k:
            sz = ndi.sum(white_t, lab_k, range(1, n_k + 1)); white_t &= np.isin(lab_k, np.nonzero(sz >= 150)[0] + 1)
        sock_tex = (socks_r & feet) | white_t
        sock_soft = blur(sock_tex.astype(np.float32), 1.0)[:, :, None]
        foot_dark = np.where((zc > 8.5)[:, :, None], pants_col, slides_col)
        cloth_g = np.where(feet[:, :, None], foot_dark * (1 - sock_soft) + socks_col * sock_soft, cloth_g)
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
ao_c = np.clip(load("ao_cloth.png", C)[:, :, 0] * 0.85 + 0.15, 0, 1)
if os.path.exists(REG): ao_c = np.where(reg == 5, np.maximum(ao_c, 0.7), ao_c)   # the socks' own sole is baked INSIDE the slides (black AO): the page shows it with the slides hidden
save("tex_cloth_orm.png", orm(pad_full(ao_c, cov_cloth), pad_full(load("rough_cloth.png")[:, :, 0], cov_cloth)))

# ------------------------------------------------------------------ the eyeball and the lid
E = 512
yy, xx = np.mgrid[0:E, 0:E]; u = (xx + 0.5) / E - 0.5; v = (yy + 0.5) / E - 0.5; rr = np.hypot(u, v); ang = np.arctan2(v, u)
rng = np.random.default_rng(7)
IRIS, PUPIL, LIMBUS = 0.123, 0.042, 0.108                              # uv radii (see assemble.mjs: r = 0.5 * polar / (pi * 0.55)): iris 1.15 cm, pupil 0.4 cm
eye = np.zeros((E, E, 3), np.float32)
sclera_col = np.array([0.88, 0.85, 0.83]); veins = blur(rng.random((E, E)).astype(np.float32), 1.2)
eye[:] = sclera_col * (1 - 0.06 * np.clip((rr - 0.2) / 0.3, 0, 1))[:, :, None]           # a little darker towards the back
eye *= (1 - 0.3 * np.clip((v - 0.06) / 0.16, 0, 1))[:, :, None]                            # the upper lid's shadow (v > 0.5 is up)
eye[:, :, 0] += 0.06 * np.clip((rr - 0.17) / 0.12, 0, 1) * (veins > 0.62)                 # faint red veins
fib = 0.5 + 0.5 * np.sin(ang * 70 + 3 * np.sin(ang * 11)) * np.clip((rr - PUPIL) / (IRIS - PUPIL), 0, 1)
iris_in = np.array([0.30, 0.16, 0.08]); iris_out = np.array([0.11, 0.06, 0.035])                 # dark brown, as painted
t = np.clip((rr - PUPIL) / (IRIS - PUPIL), 0, 1)[:, :, None]
iris = iris_in * (1 - t) + iris_out * t; iris = iris * (0.75 + 0.5 * fib[:, :, None]) + 0.03 * blur(rng.random((E, E)).astype(np.float32), 0.8)[:, :, None]
iris *= (1 - 0.6 * np.clip((rr - LIMBUS) / (IRIS - LIMBUS), 0, 1))[:, :, None]            # limbal ring
in_iris = rr < IRIS; soft = np.clip((IRIS - rr) / 0.006, 0, 1)[:, :, None]
eye = eye * (1 - soft) + iris * soft
pupil = np.clip((PUPIL - rr) / 0.005, 0, 1)[:, :, None]; eye = eye * (1 - pupil) + np.array([0.02, 0.015, 0.012]) * pupil
# a painted catch-light (the window's reflection), upper-left of the pupil, as the old painted eyes had: the real
# specular from the cornea comes on top of it in the room
cl = np.exp(-((u + 0.045) ** 2 + (v - 0.05) ** 2) / (2 * 0.016 ** 2))[:, :, None]; eye = eye * (1 - cl) + np.array([0.95, 0.95, 0.97]) * cl
cl2 = np.exp(-((u - 0.03) ** 2 + (v + 0.04) ** 2) / (2 * 0.008 ** 2))[:, :, None] * 0.5; eye = eye * (1 - cl2) + np.array([0.9, 0.9, 0.95]) * cl2
save("tex_eye.png", eye)
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
        "hoodie": {"base": "cloth", "baseQ": 86, "normal": "cloth_n", "normalScale": 1.0, "orm": "cloth_orm", "sheen": [0.2, 0.2, 0.2], "sheenRoughness": 0.8, "doubleSided": True},   # the hood's inside shows at the open collar
        "pants":  {"base": "cloth", "normal": "cloth_n", "normalScale": 0.7, "orm": "cloth_orm", "doubleSided": True},
        "socks":  {"base": "cloth", "normal": "cloth_n", "normalScale": 1.0, "orm": "cloth_orm", "sheen": [0.5, 0.5, 0.5], "sheenRoughness": 0.9, "doubleSided": True},
        "slides": {"base": "cloth", "normal": "cloth_n", "normalScale": 0.5, "orm": "cloth_orm", "doubleSided": True},
        "eye":    {"base": "eye", "baseQ": 90, "roughness": 0.35},
        "cornea": {"color": [1, 1, 1, 0.08], "roughness": 0.05, "clearcoat": 1.0, "clearcoatRoughness": 0.03, "blend": True},
        "lid":    {"base": "lid", "roughness": 0.75},
    },
}
json.dump(spec, open(os.path.join(OUT, "spec.json"), "w"), indent=1)
print("wrote spec.json", json.dumps(spec["eyes"]))
