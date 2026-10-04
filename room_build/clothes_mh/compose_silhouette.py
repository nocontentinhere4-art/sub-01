"""The silhouette sheet from g2_silhouette.py's renders: rows front, side, back; columns before (3157f95) | loose (b13af33) |
slim (now) | a real photo (CC0: the front a slim young man in black joggers, the face cropped off; the back a black hoodie);
a last row: the slim clothes in the desk, walk and lying poses. Small labels name the columns.
    python compose_silhouette.py"""
import os
from PIL import Image, ImageDraw
import compare_real as CR

HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(HERE, "out", "silhouette")
OUT = os.path.join(HERE, "..", "..", "docs", "design", "clothes-mh", "silhouette.jpg")
w, h, g, lab = 420, 640, 6, 26
PHOTOS = {"front": ("joggers", (0.22, 0.2, 0.86, 1.0)), "back": ("hoodie", (0.27, 0.1, 0.66, 0.98))}


def photo(k, crop):
    im = CR.ref(k); W, H = im.size
    c = im.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
    s = min(w / c.width, h / c.height); c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
    t = Image.new("RGB", (w, h), (184, 186, 191)); t.paste(c, ((w - c.width) // 2, (h - c.height) // 2)); return t


cols = ["before (3157f95)", "loose (b13af33)", "slim (now)", "real photo (CC0)"]
sheet = Image.new("RGB", (4 * w + 3 * g, lab + 4 * h + 3 * g), (20, 20, 22)); d = ImageDraw.Draw(sheet)
for c, name in enumerate(cols): d.text((c * (w + g) + 8, 7), name, fill=(235, 235, 235))
for r, v in enumerate(("front", "side", "back")):
    y = lab + r * (h + g)
    for c, ver in enumerate(("before", "loose", "slim")):
        sheet.paste(Image.open(os.path.join(SRC, f"{ver}_{v}.png")).convert("RGB").resize((w, h)), (c * (w + g), y))
    if v in PHOTOS: sheet.paste(photo(*PHOTOS[v]), (3 * (w + g), y))
y = lab + 3 * (h + g)
for c, v in enumerate(("desk", "walk", "lying")):
    sheet.paste(Image.open(os.path.join(SRC, f"motion_{v}.png")).convert("RGB").resize((w, h)), (c * (w + g), y))
d.text((3 * (w + g) + 8, y + 8), "slim, in motion:\ndesk, walk, lying\n(corrective shapes on)", fill=(235, 235, 235))
os.makedirs(os.path.dirname(OUT), exist_ok=True); sheet.save(OUT, quality=88); print("wrote", OUT, sheet.size)
