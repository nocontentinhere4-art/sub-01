"""The feet sheet from build_clothes.py's renders: a 3/4 close-up | the side / from above | seated at the room's
distance (5 m). No text.
    python compose_feet.py [out_dir] [sheet.jpg]"""
import os, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out")
dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "docs", "design", "clothes-mh", "feet_sheet.jpg")
ims = [Image.open(f"{src}/feet_{k}.png").convert("RGB") for k in ("34", "side", "top", "room")]
w, h = ims[0].size; g = 6
sheet = Image.new("RGB", (2 * w + g, 2 * h + g), (20, 20, 22))
for k, im in enumerate(ims):
    sheet.paste(im.resize((w, h), Image.LANCZOS), ((k % 2) * (w + g), (k // 2) * (h + g)))
os.makedirs(os.path.dirname(dst), exist_ok=True)
sheet.save(dst, quality=90); print("wrote", dst, sheet.size)
