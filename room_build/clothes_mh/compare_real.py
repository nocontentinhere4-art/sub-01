"""The owner's rule: every item next to a real one. Side-by-side sheets of build_clothes.py's renders and real photos
of the same kind of clothes (CC0 only; sources in README.md), each cropped to the clothes: no faces, no logos.
For the preview branch only, never for web/.
    python compare_real.py [out_dir]
Writes docs/design/clothes-mh/real_feet.jpg and real_clothes.jpg. The photos are downloaded to out/refs/ (not committed)."""
import os, sys, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
DOCS = os.path.join(HERE, "..", "..", "docs", "design", "clothes-mh")
REFS = {  # id: (image URL, landing page, licence)
    "socks": ("https://upload.wikimedia.org/wikipedia/commons/e/ee/Sandals_Worn_wth_White_Ankle_Socks.jpg",
              "https://commons.wikimedia.org/w/index.php?curid=41275340", "CC0 1.0 (Oddman47, Wikimedia Commons)"),
    "slide": ("https://pd.w.org/2025/08/30768afec383f9f51.48963621-2048x1536.jpg",
              "https://wordpress.org/photos/photo/30768afec3/", "CC0 1.0 (Alina Kakshapati, WordPress Photo Directory)"),
    "hoodie": ("https://pd.w.org/2024/02/83465bb8b29634fb2.56218161-1536x2048.jpeg",
               "https://wordpress.org/photos/photo/83465bb8b2/", "CC0 1.0 (Midhun P, WordPress Photo Directory)"),
    "joggers": ("https://cdn.stocksnap.io/img-thumbs/960w/LY5QEUV2DY.jpg",
                "https://stocksnap.io/photo/active-male-LY5QEUV2DY", "CC0 1.0 (StockSnap)"),
}
# (render, its crop, photo, its crop): crops as fractions (left, top, right, bottom); the photos' crops keep only clothes
FEET = [("feet_34.png", (0.18, 0.22, 0.82, 0.72), "socks", (0.56, 0.0, 1.0, 1.0)),
        ("feet_top.png", (0.25, 0.25, 0.80, 0.80), "slide", (0.20, 0.0, 0.54, 0.34))]
CLOTHES = [("seated.png", (0.12, 0.19, 0.82, 0.45), "hoodie", (0.38, 0.60, 1.0, 0.80)),
           ("standing.png", (0.22, 0.48, 0.78, 0.86), "joggers", (0.20, 0.40, 0.80, 0.82))]
H = 640; G = 6


def ref(k):
    d = os.path.join(SRC, "refs"); os.makedirs(d, exist_ok=True); p = os.path.join(d, k + ".jpg")
    if not os.path.exists(p):
        rq = urllib.request.Request(REFS[k][0], headers={"User-Agent": "sub01-clothes-compare/1.0"})
        open(p, "wb").write(urllib.request.urlopen(rq, timeout=60).read())
    return Image.open(p).convert("RGB")


def crop(im, f):
    w, h = im.size; c = im.crop((int(f[0] * w), int(f[1] * h), int(f[2] * w), int(f[3] * h)))
    return c.resize((max(1, int(c.width * H / c.height)), H), Image.LANCZOS)


def sheet(pairs, name):
    rows = [(crop(Image.open(os.path.join(SRC, r)).convert("RGB"), rc), crop(ref(p), pc)) for r, rc, p, pc in pairs]
    W = max(a.width + b.width for a, b in rows) + G
    s = Image.new("RGB", (W, len(rows) * (H + G) - G), (20, 20, 22))
    for k, (a, b) in enumerate(rows):               # render on the left, the real photo on the right
        s.paste(a, (0, k * (H + G))); s.paste(b, (a.width + G, k * (H + G)))
    os.makedirs(DOCS, exist_ok=True); out = os.path.join(DOCS, name); s.save(out, quality=88); print("wrote", out, s.size)


if __name__ == "__main__":
    sheet(FEET, "real_feet.jpg"); sheet(CLOTHES, "real_clothes.jpg")
