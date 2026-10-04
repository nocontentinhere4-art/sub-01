"""Tileable fabric textures for the clothes, baked with numpy inside Blender (Blender's Python has no Pillow).

For each fabric: a colour map (sRGB) and an OpenGL tangent-space normal map that tile over one UV tile, which the
garments' box-projected UVs map to `tile` decimetres of cloth. The normal map is Poly Haven's photo-scanned fabric normal
(CC0) combined ("whiteout" blend) with a procedural knit when the fabric is knitted: jersey wales (columns of V stitches,
a whole number of them per tile so the map tiles) plus a little periodic fuzz noise. The colour is the fabric's base
colour, toned by a photo-scanned melange where it is heathered and darkened a little in the stitches' grooves, so
the knit still reads at a distance where the normal map has been mip-mapped away.
"""
import math, zlib
import numpy as np
import bpy


def load(path):
    im = bpy.data.images.load(path, check_existing=True); im.colorspace_settings.name = "Non-Color"
    w, h = im.size; a = np.empty(w * h * 4, np.float32); im.pixels.foreach_get(a)
    return a.reshape(h, w, 4)[:, :, :3]


def resize(a, n):
    """bilinear, wrapping (the source tiles)"""
    h, w = a.shape[:2]
    ys = (np.arange(n) + 0.5) * h / n - 0.5; xs = (np.arange(n) + 0.5) * w / n - 0.5
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int); fy = (ys - y0)[:, None, None]; fx = (xs - x0)[None, :, None]
    y0m, y1m, x0m, x1m = y0 % h, (y0 + 1) % h, x0 % w, (x0 + 1) % w
    return (a[y0m][:, x0m] * (1 - fy) * (1 - fx) + a[y0m][:, x1m] * (1 - fy) * fx + a[y1m][:, x0m] * fy * (1 - fx) + a[y1m][:, x1m] * fy * fx)


def periodic_noise(n, f0, seed):
    """band-limited noise that tiles (an FFT band around f0 cycles per tile)"""
    rng = np.random.default_rng(seed); w = rng.standard_normal((n, n))
    F = np.fft.fft2(w); fy = np.fft.fftfreq(n)[:, None] * n; fx = np.fft.fftfreq(n)[None, :] * n
    r = np.sqrt(fx * fx + fy * fy); band = np.exp(-((r - f0) / (0.5 * f0)) ** 2)
    out = np.real(np.fft.ifft2(F * band)); return out / (np.abs(out).max() + 1e-9)


def knit_height(n, cols, rows, seed=1):
    """jersey: wales of V stitches, `cols` across and `rows` down one tile (both whole numbers: it tiles), plus fuzz"""
    v, u = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
    t = rows * v; pp = 0.5 - np.abs((t % 1.0) - 0.5)                        # Blender's ping-pong, period one stitch
    h = np.sin(2 * math.pi * (cols * u + pp))
    return h + 0.6 * periodic_noise(n, cols / 0.6, seed)


def height_normal(h, strength):
    gx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5; gy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * 0.5
    nrm = np.stack([-gx * strength, -gy * strength, np.ones_like(h)], -1)
    return nrm / np.linalg.norm(nrm, axis=-1, keepdims=True)


def whiteout(n1, n2):
    n = np.stack([n1[..., 0] + n2[..., 0], n1[..., 1] + n2[..., 1], n1[..., 2] * n2[..., 2]], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def save(a, path, srgb):
    h, w = a.shape[:2]; im = bpy.data.images.new(path.split("/")[-1], w, h, alpha=False)
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    rgba = np.concatenate([np.clip(a, 0, 1), np.ones((h, w, 1), np.float32)], -1).astype(np.float32)
    im.pixels.foreach_set(rgba.ravel()); im.filepath_raw = path; im.file_format = "JPEG"
    bpy.context.scene.render.image_settings.quality = 92; im.save(); bpy.data.images.remove(im)


def lin2srgb(c):
    c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def bake(name, spec, tex_dir, out_dir):
    """spec: tile (dm), rgb (linear), normal (Poly Haven id), nstr, melange (id or None), mel_amt, cols (stitches per
    tile, 0: none), rows, kstr (knit normal strength), dots ((nubs per tile, strength) or None), size (px).
    Returns (colour path, normal path)."""
    n = spec["size"]; rgb = np.array(spec["rgb"], np.float32)
    nm = resize(load(f"{tex_dir}/{spec['normal']}/nor_gl.jpg"), n) * 2 - 1
    nm[..., :2] *= spec["nstr"]; nm /= np.linalg.norm(nm, axis=-1, keepdims=True)
    tone = np.ones((n, n), np.float32)
    if spec.get("melange"):
        lum = resize(load(f"{tex_dir}/{spec['melange']}/Diffuse.jpg"), n).mean(-1)
        tone *= 1 + spec["mel_amt"] * (lum / lum.mean() - 1)
    if spec.get("cols"):
        h = knit_height(n, spec["cols"], spec["rows"], seed=zlib.crc32(name.encode()) % 1000)
        nm = whiteout(nm, height_normal(h, spec["kstr"]))
        tone *= 1 - 0.18 * (1 - (h - h.min()) / (h.max() - h.min()))          # the grooves are a little darker
    if spec.get("dots"):
        # a footbed's moulded nubs: low round bumps on a staggered grid, a whole number per tile (it tiles)
        k, amp = spec["dots"]; v, u = np.meshgrid((np.arange(n) + 0.5) / n, (np.arange(n) + 0.5) / n, indexing="ij")
        h = np.zeros((n, n), np.float32)
        for dv, du in ((0.0, 0.0), (0.5, 0.5)):
            fu = (u * k + du) % 1.0 - 0.5; fv = (v * k + dv) % 1.0 - 0.5
            h = np.maximum(h, np.clip(1 - (fu * fu + fv * fv) / 0.09, 0, 1) ** 1.5)
        nm = whiteout(nm, height_normal(h, amp))
        tone *= 1 + 0.06 * (h - 0.5)                                          # the tops catch a little more wear
    col = lin2srgb(rgb[None, None, :] * tone[..., None])
    cp, npth = f"{out_dir}/{name}_color.jpg", f"{out_dir}/{name}_normal.jpg"
    save(col, cp, True); save(nm * 0.5 + 0.5, npth, False)
    return cp, npth
