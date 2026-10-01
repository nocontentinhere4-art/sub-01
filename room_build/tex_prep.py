"""Prepare the room's textures: tinted diffuse maps, normal maps, roughness maps (glTF: G = roughness), and the poster atlas.
Output: tex_final/*.png|jpg  (the GLB build later converts everything to WebP)"""
import os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops, ImageEnhance
R = os.path.dirname(os.path.abspath(__file__)); T = f"{R}/tex"; O = f"{R}/tex_final"; os.makedirs(O, exist_ok=True)

def hexrgb(h): h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def tint(src, size, color, keep=0.55, gain=1.0, cavity=0.0):
    """recolour a texture: its luminance pattern (normalised to mean 1, contrast `keep`) times `color`;
    `cavity` mixes in the texture's AO map so the weave reads in the colour too"""
    im = Image.open(src).convert("L").resize((size, size), Image.LANCZOS)
    if cavity:
        ao = Image.open(os.path.join(os.path.dirname(src), "AO.jpg")).convert("L").resize((size, size), Image.LANCZOS)
        im = ImageChops.multiply(im, ao.point(lambda v: int(255 * (1 - cavity) + v * cavity)))
    px = im.load(); mean = sum(im.getdata()) / (size * size)
    c = hexrgb(color); out = Image.new("RGB", (size, size)); op = out.load()
    for y in range(size):
        for x in range(size):
            k = (1 + keep * (px[x, y] / mean - 1)) * gain
            op[x, y] = tuple(max(0, min(255, int(ch * k))) for ch in c)
    return out

def grade(src, size, sat=1.0, bright=1.0, warm=(1, 1, 1), contrast=1.0):
    im = Image.open(src).convert("RGB").resize((size, size), Image.LANCZOS)
    im = ImageEnhance.Color(im).enhance(sat); im = ImageEnhance.Brightness(im).enhance(bright); im = ImageEnhance.Contrast(im).enhance(contrast)
    r, g, b = im.split()
    return Image.merge("RGB", [ch.point(lambda v, k=k: min(255, int(v * k))) for ch, k in zip((r, g, b), warm)])

def mr(src_rough, size, scale=1.0, offset=0.0, metal=0):
    """glTF metallicRoughness: G = roughness, B = metalness"""
    r = Image.open(src_rough).convert("L").resize((size, size), Image.LANCZOS).point(lambda v: max(0, min(255, int(v * scale + offset * 255))))
    return Image.merge("RGB", [Image.new("L", (size, size), 0), r, Image.new("L", (size, size), metal)])

def nor(src, size, strength=1.0):
    im = Image.open(src).convert("RGB").resize((size, size), Image.LANCZOS)
    if strength == 1.0: return im
    r, g, b = im.split()
    f = lambda v: max(0, min(255, int(128 + (v - 128) * strength)))
    return Image.merge("RGB", [r.point(f), g.point(f), Image.new("L", (size, size), 255)])

def save(im, name, q=92):
    p = f"{O}/{name}"; (im.save(p, quality=q) if p.endswith(".jpg") else im.save(p)); print("wrote", name, im.size)

# floor: warm brown planks
save(grade(f"{T}/wood_floor/Diffuse.jpg", 2048, sat=1.0, bright=1.0, warm=(1.04, 1.0, 0.94)), "floor_diff.jpg")
save(nor(f"{T}/wood_floor/nor_gl.jpg", 2048), "floor_nor.jpg")
save(mr(f"{T}/wood_floor/Rough.jpg", 1024, 0.9, 0.02), "floor_mr.jpg")
# walls: warm off-white plaster, only its relief and a whisper of its colour
save(tint(f"{T}/white_stucco/Diffuse.jpg", 512, "#e8e0d2", keep=0.35), "wall_diff.jpg")
save(nor(f"{T}/white_stucco/nor_gl.jpg", 1024, 0.6), "wall_nor.jpg")
# oak (desk, shelf, bed): natural oak, slightly warm
save(grade(f"{T}/oak_veneer_01/Diffuse.jpg", 1024, sat=0.95, bright=1.02, warm=(1.03, 1.0, 0.95)), "oak_diff.jpg")
save(nor(f"{T}/oak_veneer_01/nor_gl.jpg", 1024, 0.7), "oak_nor.jpg")
save(mr(f"{T}/oak_veneer_01/Rough.jpg", 512, 0.85, 0.05), "oak_mr.jpg")
# door: the same veneer, darker (walnut-ish)
save(grade(f"{T}/oak_veneer_01/Diffuse.jpg", 1024, sat=1.05, bright=0.72, warm=(1.06, 0.97, 0.88)), "door_diff.jpg")
# fabrics (the textures cover ~27 cm): sheet, duvet, curtain, rug, chair
save(tint(f"{T}/cotton_jersey/Diffuse.jpg", 512, "#ece7de", keep=0.5, cavity=0.6), "sheet_diff.jpg")
save(nor(f"{T}/cotton_jersey/nor_gl.jpg", 512, 0.8), "sheet_nor.jpg")
save(tint(f"{T}/waffle_pique_cotton/Diffuse.jpg", 512, "#4a5670", keep=0.6, cavity=0.6), "duvet_diff.jpg")
save(nor(f"{T}/waffle_pique_cotton/nor_gl.jpg", 512, 1.0), "duvet_nor.jpg")
save(tint(f"{T}/rough_linen/Diffuse.jpg", 512, "#b8ad99", keep=0.6, cavity=0.6), "curtain_diff.jpg")
save(nor(f"{T}/rough_linen/nor_gl.jpg", 512, 0.9), "curtain_nor.jpg")
save(tint(f"{T}/poly_wool_herringbone/Diffuse.jpg", 512, "#8d8478", keep=0.9, cavity=0.6), "rug_diff.jpg")
save(nor(f"{T}/poly_wool_herringbone/nor_gl.jpg", 512, 1.0), "rug_nor.jpg")
save(nor(f"{T}/jersey_melange/nor_gl.jpg", 512, 1.0), "fabric_nor.jpg")

# ---------- posters (one atlas, 1024 x 512): A 2:3 | B 2:3 | C square + D 2:1 ----------
JP = f"{R}/fonts/NotoSansJP.ttf"; SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
def font(path, size, wght=None):
    f = ImageFont.truetype(path, size)
    if wght:
        try: f.set_variation_by_axes([wght])
        except Exception: pass
    return f
S = 2   # draw at 2x, then downsample (clean edges)
A = Image.new("RGB", (1024 * S, 512 * S), "#000"); d = ImageDraw.Draw(A)
def vgrad(box, top, bot):
    x0, y0, x1, y1 = box; t, b = hexrgb(top), hexrgb(bot)
    for y in range(y0, y1):
        k = (y - y0) / max(1, y1 - y0 - 1); d.line([(x0, y), (x1 - 1, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3)))
# A: city pop night - striped sun over a skyline, 東京
w, h = 341 * S, 512 * S
vgrad((0, 0, w, h), "#1b1f4a", "#e0566b")
cx, cy, r = w // 2, int(h * 0.50), int(w * 0.33)
sun = Image.new("L", (w, h), 0); sd = ImageDraw.Draw(sun); sd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
for i in range(7):                               # the stripes cut through the lower half of the sun
    y = cy + int(r * (0.1 + i * 0.14)); sd.rectangle((0, y, w, y + int(4 * S + i * 1.6 * S)), fill=0)
sunc = Image.new("RGB", (w, h)); scd = ImageDraw.Draw(sunc)
for y in range(h): k = min(1, max(0, (y - (cy - r)) / (2 * r))); scd.line([(0, y), (w, y)], fill=(255, int(214 - 120 * k), int(90 - 40 * k)))
A.paste(sunc, (0, 0), sun)
random.seed(7); x = 0
while x < w:                                     # skyline
    bw = random.randint(18, 46) * S // 2; bh = random.randint(int(h * 0.12), int(h * 0.34)); d.rectangle((x, h - bh, x + bw, h), fill="#141631")
    for wy in range(h - bh + 8, h - 6, 10 * S // 2):
        for wx in range(x + 4, x + bw - 4, 8 * S // 2):
            if random.random() < 0.28: d.rectangle((wx, wy, wx + 2 * S, wy + 3 * S), fill="#ffcf7a")
    x += bw + random.randint(0, 3) * S
tx = int(w * 0.66)                               # a tower with a red light
d.polygon([(tx - 26, h), (tx + 26, h), (tx + 4, int(h * 0.36)), (tx - 4, int(h * 0.36))], fill="#141631"); d.ellipse((tx - 5, int(h * 0.36) - 12, tx + 5, int(h * 0.36) - 2), fill="#ff3b30")
fj = font(JP, 92 * S // 2 * 2 // 2, 900)
d.text((int(w * 0.08), int(h * 0.05)), "東", font=font(JP, 74 * S, 900), fill="#fff4e6"); d.text((int(w * 0.08), int(h * 0.05) + 80 * S), "京", font=font(JP, 74 * S, 900), fill="#fff4e6")
d.text((int(w * 0.62), int(h * 0.07)), "TOKYO", font=font(SANS, 15 * S), fill="#fff4e6"); d.text((int(w * 0.62), int(h * 0.07) + 20 * S), "NIGHT FM", font=font(SANS, 11 * S), fill="#ffd0a0")
d.text((int(w * 0.62), int(h * 0.07) + 36 * S), "87.6", font=font(SANS, 11 * S), fill="#ffd0a0")
# B: Mt Fuji, minimal
ox = 341 * S; w2 = 341 * S
d.rectangle((ox, 0, ox + w2, h), fill="#f1e9da")
d.ellipse((ox + int(w2 * 0.56), int(h * 0.16), ox + int(w2 * 0.86), int(h * 0.16) + int(w2 * 0.30)), fill="#d9472b")
base = int(h * 0.74); peak = int(h * 0.36)
d.polygon([(ox - 10, base), (ox + int(w2 * 0.38), peak), (ox + int(w2 * 0.62), peak), (ox + w2 + 10, base)], fill="#2d3b5c")
d.polygon([(ox + int(w2 * 0.30), peak + int((base - peak) * 0.22)), (ox + int(w2 * 0.38), peak), (ox + int(w2 * 0.62), peak), (ox + int(w2 * 0.70), peak + int((base - peak) * 0.22)),
           (ox + int(w2 * 0.6), peak + int((base - peak) * 0.16)), (ox + int(w2 * 0.52), peak + int((base - peak) * 0.25)), (ox + int(w2 * 0.44), peak + int((base - peak) * 0.15))], fill="#fbf7ef")
for i in range(6):                               # waves
    y = base + 14 * S + i * 15 * S; d.line([(ox + 20 * S, y), (ox + w2 - 20 * S, y)], fill="#2d3b5c", width=3 * S if i == 0 else 2 * S)
d.text((ox + 24 * S, 22 * S), "富士山", font=font(JP, 30 * S, 700), fill="#2d3b5c")
d.text((ox + 24 * S, 62 * S), "FUJI 3776 M", font=font(SANS, 10 * S), fill="#2d3b5c")
d.text((ox + 24 * S, h - 30 * S), "KICHIJOJI PRINT CLUB", font=font(SANS, 9 * S), fill="#2d3b5c")
# C: record sleeve (square): concentric arcs
ox = 683 * S; s3 = 341 * S
d.rectangle((ox, 0, ox + s3, s3), fill="#e8b23a")
for i in range(9):
    rr = int(s3 * (0.46 - i * 0.05)); col = ["#1f2a44", "#e8b23a"][i % 2]
    d.ellipse((ox + s3 // 2 - rr + int(s3 * 0.12), s3 // 2 - rr + int(s3 * 0.1), ox + s3 // 2 + rr + int(s3 * 0.12), s3 // 2 + rr + int(s3 * 0.1)), fill=col)
d.rectangle((ox, 0, ox + int(s3 * 0.36), s3), fill="#1f2a44")
d.text((ox + 18 * S, 20 * S), "CITY", font=font(SANS, 22 * S), fill="#e8b23a"); d.text((ox + 18 * S, 48 * S), "POP", font=font(SANS, 22 * S), fill="#e8b23a")
d.text((ox + 18 * S, s3 - 40 * S), "夜明け", font=font(JP, 20 * S, 700), fill="#f4ead8")
# D: a ticket / photo strip (2:1)
oy = 341 * S; d.rectangle((ox, oy, ox + s3, oy + 171 * S), fill="#f4efe6")
for i in range(3):
    px0 = ox + 12 * S + i * 108 * S; d.rectangle((px0, oy + 14 * S, px0 + 98 * S, oy + 120 * S), fill=["#7aa6c2", "#d98b6a", "#8fb58a"][i])
    d.ellipse((px0 + 30 * S, oy + 40 * S, px0 + 68 * S, oy + 78 * S), fill="#f4efe6")
d.text((ox + 14 * S, oy + 132 * S), "井の頭公園  2024.04", font=font(JP, 14 * S, 500), fill="#3a3a3a")
A = A.resize((1024, 512), Image.LANCZOS)
save(A, "posters.png")
