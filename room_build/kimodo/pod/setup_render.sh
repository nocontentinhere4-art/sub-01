#!/bin/bash
# GPU render pod: system libs, Node, Chromium; unpack the bundle; render every clip in parallel (MP4 + sheet + QA)
export DEBIAN_FRONTEND=noninteractive
(apt-get update -qq && apt-get install -y -qq ffmpeg fonts-dejavu-core libegl1 libgles2 libgl1 libvulkan1 mesa-vulkan-drivers xz-utils) >/dev/null 2>&1
cd /workspace && curl -sL https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz | tar xJ
export PATH=/workspace/node-v20.18.0-linux-x64/bin:$PATH
mkdir -p r && cd r && tar xzf ../bundle.tgz
npm i -s playwright-core@1.56 >/dev/null 2>&1
pip install -q playwright >/dev/null 2>&1
python3 -m playwright install --with-deps chromium >/dev/null 2>&1
export CHROME=$(ls -d /root/.cache/ms-playwright/chromium-*/chrome-linux*/chrome | head -1) GPU_ARGS="--use-gl=angle,--use-angle=gl-egl"
node render.mjs cfg/cfg_b3.json /tmp/p --probe 2>&1 | grep renderer
mkdir -p out
for n in b3 a c2 d2 e7 f g; do node render.mjs cfg/cfg_$n.json out --fps 30 > out/log_$n.txt 2>&1 & done
node render.mjs cfg/cfg_b_ref.json out --fps 0.25 --no-qa > out/log_ref.txt 2>&1 &
wait
echo ALL_DONE
