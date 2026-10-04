"""python make_video.py <frames root> <out.mp4>: the four frame folders preview.mjs wrote (<root>/pv_main_default,
pv_new_default, pv_main_close, pv_new_close) as one 1280 x 720 H.264 video at 30 fps: main on the left, this branch on
the right, the default camera above, the close camera below, each idle named while it plays (timeline.json)."""
import json, os, subprocess, sys

root, out = sys.argv[1], sys.argv[2]
here = os.path.dirname(os.path.abspath(__file__))
tl = json.load(open(os.path.join(here, "timeline.json")))
fps, font = tl["fps"], "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
views = ["main_default", "new_default", "main_close", "new_close"]
inputs = []
for v in views:
    inputs += ["-framerate", str(fps), "-i", os.path.join(root, f"pv_{v}", "f%05d.jpg")]


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def text(t, x, y, size=20, enable=None, box=True):
    s = f"drawtext=fontfile={font}:text='{esc(t)}':x={x}:y={y}:fontsize={size}:fontcolor=white"
    if box:
        s += ":box=1:boxcolor=black@0.55:boxborderw=6"
    if enable:
        s += f":enable='{enable}'"
    return s


# what plays when: each segment's label, from its first frame to its last
labels, t, place = [], 0.0, None
for where, label, variant, secs in tl["segments"]:
    n = round(secs * fps) / fps
    if label:
        labels.append((t, t + n, label, variant))
    t += n
total = t
draw = [text("main (before)", 10, 8), text("this branch (after)", 650, 8),
        text("default camera", 10, 330, 14), text("default camera", 650, 330, 14),
        text("close", 10, 690, 14), text("close", 650, 690, 14)]
for a, b, label, variant in labels:
    draw.append(text(label, "(w-text_w)/2", 352, 22, f"between(t,{a:.3f},{b - 0.001:.3f})"))
graph = ("[0:v][1:v][2:v][3:v]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[g];[g]"
         + ",".join(draw) + ",format=yuv420p[v]")
cmd = ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[v]", "-r", str(fps),
       "-c:v", "libx264", "-preset", "slow", "-crf", os.environ.get("CRF", "23"), "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print(f"{out}: {total:.1f} s, {os.path.getsize(out) / 1e6:.1f} MB")
