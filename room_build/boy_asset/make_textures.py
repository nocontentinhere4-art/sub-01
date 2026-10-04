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

# ------------------------------------------------------------------ skin
skin = load("bake_skin.png"); S = skin.shape[0]
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
    old_l = skin_out.mean(2); hair_bleed = (proj.mean(2) < 0.3) & (old_l > 0.45) & ~ndi.binary_dilation(hole, iterations=12)
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
# the hands: the old bake has a lighter wedge on the back of each wrist (baked light); flatten the low-frequency luminance
hands = cov & (Z < 125) & (skin_out.mean(2) > 0.3)
if hands.any():
    hl = skin_out.mean(2); w_h = blur(hands.astype(np.float32), 12); lo_h = blur(hl * hands, 12) / np.maximum(w_h, 1e-3)
    mean_h = float(np.median(hl[hands])); gain_h = np.clip(mean_h / np.maximum(lo_h, 1e-3), 0.8, 1.25)
    hm_ = blur(hands.astype(np.float32), 3)[:, :, None]; skin_out = np.clip(skin_out * (gain_h[:, :, None] * hm_ + (1 - hm_)), 0, 1)
rgba = np.concatenate([skin_out, alpha[:, :, None]], 2)
Image.fromarray(np.clip(rgba * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "tex_skin.png")); print("wrote tex_skin.png (RGBA)")
save("tex_skin_n.png", sanitize_normal(load("nrm_skin.png")))
save("tex_skin_orm.png", orm(np.clip(blur(load("ao_skin.png", S)[:, :, 0], 1.5) * 0.5 + 0.5, 0, 1), load("rough_skin.png")[:, :, 0]))   # AO softened: skin is translucent

# --- eyelid colour: the skin around the eyes, a little darker
ring = np.zeros((S, S), bool)
for e in eyes.values(): ring |= ndi.binary_dilation(e["mask"], iterations=14) & ~ndi.binary_dilation(e["mask"], iterations=4)
ring &= face & (r - b > 0.1) & (lum > 0.4)
lid_col = skin[ring].mean(0) if ring.any() else np.array([0.85, 0.65, 0.58]); print("lid colour", lid_col.round(3))

# ------------------------------------------------------------------ hair
hair = load("bake_hair.png"); H = hair.shape[0]
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
save("tex_hair.png", hair_out)
save("tex_hair_n.png", sanitize_normal(np.asarray(Image.open(os.path.join(WORK, "nrm_hair.png")).convert("RGB").resize((H, H), Image.LANCZOS)).astype(np.float32) / 255))
save("tex_hair_orm.png", orm(np.clip(load("ao_hair.png", H)[:, :, 0] * 0.8 + 0.2, 0, 1), rh))

# ------------------------------------------------------------------ cloth (hoodie, pants, socks, slides)
cloth = load("bake_cloth.png"); C = cloth.shape[0]
# the old material was metallic (metallicFactor 1, no map), which rendered the clothes much darker than their painted
# colour; the new dielectric materials are graded to the look the owner knows: blacks stay black, the hoodie's grey
# stays mid-grey, the socks and the stripe stay white (measured on the same frame, render/compare.mjs)
cl = cloth.mean(2); k = np.interp(cl, [0.0, 0.12, 0.3, 0.5, 0.75, 1.0], [0.18, 0.22, 0.58, 0.66, 1.0, 1.0])
cloth_g = np.clip(cloth * k[:, :, None], 0, 1)
# the pants: Meshy painted glossy highlights into the albedo (the "PVC" look); flatten them towards the cloth's dark
# base tone, keeping the white stripe. The region map comes from the build (material index + 1, baked per texel).
REG = os.path.join(WORK, "region_cloth.npy")
if os.path.exists(REG):
    reg = np.asarray(Image.fromarray(np.load(REG)[::-1]).resize((C, C), Image.NEAREST))     # Blender images are bottom-up
    pants = ndi.binary_erosion(reg == 4, iterations=1)
    pl = cloth_g.mean(2); stripe = pl > 0.55
    base_tone = np.percentile(pl[pants & ~stripe], 25) if (pants & ~stripe).any() else 0.05
    flat = np.where(pl > base_tone, base_tone + (pl - base_tone) * 0.3, pl)
    gain = np.where(pants & ~stripe, flat / np.maximum(pl, 1e-4), 1.0)
    cloth_g = np.clip(cloth_g * gain[:, :, None], 0, 1); print("pants de-lit: base tone %.3f, %d px" % (base_tone, int((pants & ~stripe).sum())))
# hoodie and pants: skin-coloured texels (the old atlas's padding pulled skin into cloth islands next to the hands and
# the ankles: the cream wedge on the inner cuff) are filled from the cloth around
if os.path.exists(REG):
    rr_c, gg_c, bb_c = cloth_g[:, :, 0], cloth_g[:, :, 1], cloth_g[:, :, 2]; lc = cloth_g.mean(2)
    for rid, nm in ((3, "hoodie"), (4, "pants")):
        regm = ndi.binary_erosion(reg == rid, iterations=1)
        bad_c = regm & (rr_c - bb_c > 0.06) & (lc > 0.3); good_c = regm & ~ndi.binary_dilation(bad_c, iterations=2)
        if bad_c.any() and good_c.any():
            wg = blur(good_c.astype(np.float32), 6); fl = np.stack([blur(cloth_g[:, :, k] * good_c, 6) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
            cloth_g = np.where(bad_c[:, :, None], fl, cloth_g); print("%s: %d skin-coloured px filled" % (nm, int(bad_c.sum())))
# socks: dark texels inside the sock region (slide / pants bleed from the old atlas: the smear on the toe) become sock
if os.path.exists(REG):
    socks = ndi.binary_erosion(reg == 5, iterations=1); sl_ = cloth_g.mean(2)
    bad_s = socks & (sl_ < 0.5); good_s = socks & (sl_ >= 0.55)
    if bad_s.any() and good_s.any():
        wg = blur(good_s.astype(np.float32), 5); fl = np.stack([blur(cloth_g[:, :, k] * good_s, 5) for k in range(3)], 2) / np.maximum(wg, 1e-3)[:, :, None]
        cloth_g = np.where(bad_s[:, :, None], fl, cloth_g); print("socks: %d dark px filled" % int(bad_s.sum()))
# alpha: 1 everywhere, 0 in the reserved band (u, v < 0.015: both corners of the v axis, as the UV packing starts at 0 and glTF
# flips v): the invisible full-body proxy that assemble.mjs appends to the slides primitive points there (white, so that
# room.html's slidesInit never takes the proxy's feet for slides)
band = int(C * 0.015) + 2
alpha_c = np.ones((C, C), np.float32); cloth_g = cloth_g.copy()
for sl in (np.s_[:band, :band], np.s_[C - band:, :band]):
    alpha_c[sl] = 0; cloth_g[sl] = 1.0
Image.fromarray(np.clip(np.concatenate([cloth_g, alpha_c[:, :, None]], 2) * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA").save(os.path.join(OUT, "tex_cloth.png")); print("wrote tex_cloth.png (RGBA)")
save("tex_cloth_n.png", sanitize_normal(load("nrm_cloth.png")))
save("tex_cloth_orm.png", orm(np.clip(load("ao_cloth.png", C)[:, :, 0] * 0.85 + 0.15, 0, 1), load("rough_cloth.png")[:, :, 0]))

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
        "hair":   {"base": "hair", "baseQ": 82, "normal": "hair_n", "normalScale": 0.3, "orm": "hair_orm", "doubleSided": True},
        "hoodie": {"base": "cloth", "baseQ": 86, "normal": "cloth_n", "normalScale": 1.0, "orm": "cloth_orm", "sheen": [0.2, 0.2, 0.2], "sheenRoughness": 0.8, "doubleSided": True},   # the hood's inside shows at the open collar
        "pants":  {"base": "cloth", "normal": "cloth_n", "normalScale": 0.7, "orm": "cloth_orm", "doubleSided": True},
        "socks":  {"base": "cloth", "normal": "cloth_n", "normalScale": 1.0, "orm": "cloth_orm", "sheen": [0.5, 0.5, 0.5], "sheenRoughness": 0.9, "doubleSided": True},
        "slides": {"base": "cloth", "normal": "cloth_n", "normalScale": 0.5, "orm": "cloth_orm", "alphaMask": True, "doubleSided": True},   # MASK: the proxy's texels are alpha 0
        "eye":    {"base": "eye", "baseQ": 90, "roughness": 0.35},
        "cornea": {"color": [1, 1, 1, 0.08], "roughness": 0.05, "clearcoat": 1.0, "clearcoatRoughness": 0.03, "blend": True},
        "lid":    {"base": "lid", "roughness": 0.75},
    },
}
json.dump(spec, open(os.path.join(OUT, "spec.json"), "w"), indent=1)
print("wrote spec.json", json.dumps(spec["eyes"]))
