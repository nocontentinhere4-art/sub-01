#!/bin/bash
# Builds the X film from the takes: compose every frame, synthesise the soundtrack, encode for X (H.264 + AAC, 4:5).
# Needs: takes/room + takes/bed (frames of the GPU room renders), takes/brain_{hook,main,tl,end} (film_brain2.js),
# a static server of the repo root on 127.0.0.1:8899 (python3 -m http.server 8899 --bind 127.0.0.1, from the repo root).
set -euo pipefail
cd "$(dirname "$0")"
node compose.js
python3 soundtrack2.py soundtrack2.wav
ffmpeg -y -loglevel error -framerate 30 -i frames/%05d.jpg -i soundtrack2.wav -c:v libx264 -preset slow -crf 17 \
  -pix_fmt yuv420p -profile:v high -level 4.1 -c:a aac -b:a 192k -shortest -movflags +faststart sub01_x_film.mp4
ffprobe -v error -show_entries format=duration,size -of compact sub01_x_film.mp4
