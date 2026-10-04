"""One still sheet from build_clothes.py's renders: standing | seated at the desk | the hood and the knit over the
elbow close-up. No text.
    python compose_sheet.py [out_dir] [sheet.jpg]"""
import os, sys, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "docs", "design", "clothes-mh", "clothes_sheet.jpg")
st, se = Image.open(f"{src}/standing.png").convert("RGB"), Image.open(f"{src}/seated.png").convert("RGB")
ch, ce = Image.open(f"{src}/close_hood.png").convert("RGB"), Image.open(f"{src}/close_elbow.png").convert("RGB")
w, h = st.size; g = 6
sheet = Image.new("RGB", (3 * w + 2 * g, h), (20, 20, 22))
sheet.paste(st, (0, 0)); sheet.paste(se, (w + g, 0))
ch = ch.resize((w, (h - g) // 2), Image.LANCZOS) if ch.size != (w, (h - g) // 2) else ch
ce = ce.resize((w, h - g - ch.size[1]), Image.LANCZOS)
sheet.paste(ch, (2 * (w + g), 0)); sheet.paste(ce, (2 * (w + g), ch.size[1] + g))
os.makedirs(os.path.dirname(dst), exist_ok=True)
sheet.save(dst, quality=88); print("wrote", dst, sheet.size)
