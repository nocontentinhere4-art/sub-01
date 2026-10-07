import sys; from PIL import Image, ImageDraw
out, w = sys.argv[1], int(sys.argv[2]); files = sys.argv[3:]
ims = [Image.open(f).convert("RGB") for f in files]; th = 300
tiles = []
for f, im in zip(files, ims):
    im = im.resize((int(im.width * th / im.height), th)); d = ImageDraw.Draw(im); d.rectangle([0, 0, im.width, 16], fill=(0, 0, 0)); d.text((3, 2), f.split("/")[-1][:60], fill=(255, 255, 0)); tiles.append(im)
cols = w; rows = (len(tiles) + cols - 1) // cols; tw = max(t.width for t in tiles)
S = Image.new("RGB", (tw * cols, th * rows), (30, 30, 30))
for i, t in enumerate(tiles): S.paste(t, ((i % cols) * tw, (i // cols) * th))
S.save(out, quality=85)
