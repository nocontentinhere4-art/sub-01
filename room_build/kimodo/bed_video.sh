#!/bin/bash
# bed_video.sh <port> <activity> <seconds> <out.mp4> [views] [fps] : a short screen video of him on the bed (bed_shots.mjs frames,
# the views side by side), e.g. LIFE='{"turn":1}' bed_video.sh 8765 sleep 17.4 turn.mp4 pagez,side 10
set -e
P=$1; A=$2; SEC=$3; OUT=$(realpath -m "$4"); V=${5:-pagez,side}; FPS=${6:-10}; D=$(mktemp -d)
T=$(python3 -c "print(','.join(f'{i/$FPS:.3f}' for i in range(int($SEC*$FPS))))")
cd "$(dirname "$0")/.." && node kimodo/bed_shots.mjs $P $A "$D/f" "$T" "$V" > /dev/null
python3 - "$D/f.json" "$D" <<'PY'
import json, sys
from PIL import Image
shots = json.load(open(sys.argv[1])); ts = sorted({s[0] for s in shots}); vs = []
for s in shots:
    if s[1] not in vs: vs.append(s[1])
by = {(s[0], s[1]): s[2] for s in shots}; w, h = Image.open(shots[0][2]).size
for k, t in enumerate(ts):
    im = Image.new("RGB", (w * len(vs), h))
    for j, v in enumerate(vs): im.paste(Image.open(by[(t, v)]).convert("RGB"), (j * w, 0))
    im.save(f"{sys.argv[2]}/v{k:04d}.png")
PY
ffmpeg -loglevel error -y -framerate $FPS -i "$D/v%04d.png" -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -c:v libx264 -pix_fmt yuv420p -crf 26 "$OUT"; rm -rf "$D"; ls -la "$OUT"
