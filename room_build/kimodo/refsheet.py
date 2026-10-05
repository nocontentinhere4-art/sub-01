"""Reference sheet: rows of [real photo | our frames from a matching camera], labelled.
python refsheet.py out.jpg "title" "ref.jpg|label|ours1.jpg|label1|ours2.jpg|label2" ... (one argument per row)"""
import sys
from PIL import Image, ImageDraw, ImageFont
out, title, rows = sys.argv[1], sys.argv[2], sys.argv[3:]
H = 380; pad = 10
try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except Exception: font = ImageFont.load_default()
built = []
for r in rows:
    parts = r.split("|"); cells = []
    for i in range(0, len(parts), 2):
        im = Image.open(parts[i]).convert("RGB"); im = im.resize((int(im.width * H / im.height), H)); cells.append((im, parts[i + 1]))
    built.append(cells)
W = max(sum(c[0].width for c in row) + pad * (len(row) + 1) for row in built)
sheet = Image.new("RGB", (W, 40 + len(built) * (H + 34 + pad)), (24, 26, 31)); d = ImageDraw.Draw(sheet)
d.text((pad, 10), title, fill=(235, 235, 235), font=font)
y = 40
for row in built:
    x = pad
    for im, lab in row:
        sheet.paste(im, (x, y + 28)); d.text((x, y + 4), lab, fill=(210, 210, 210), font=font); x += im.width + pad
    y += H + 34 + pad
sheet.save(out, quality=88); print(out, sheet.size)
