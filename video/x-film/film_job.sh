#!/bin/bash
# Pod side of the X film (video/x-film): the repo's own room renderer (tools/gpu_preview_render.py) on the RunPod GPU,
# one side only, the shot list in /in/shots.json; the frames go back as one near-lossless MP4 plus the segment JSON.
set -uxo pipefail
cd /work
echo "gpu: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq ffmpeg fonts-dejavu-core libegl1 libgles2 libgl1 libvulkan1 mesa-vulkan-drivers 2>&1 | tail -2
pip install -q playwright pillow 2>&1 | tail -1
python3 -m playwright install --with-deps chromium 2>&1 | tail -2
mkdir -p /work/new /work/frames
tar -xzf /in/new.tar.gz -C /work/new
R=/work/new/tools/gpu_preview_render.py
GPU_ARGS=""
for cand in "channel=chromium,--use-gl=angle,--use-angle=gl-egl" \
            "channel=chromium,--use-angle=vulkan,--use-vulkan=native,--enable-features=Vulkan" \
            "--use-gl=angle,--use-angle=gl-egl" "channel=chromium,--use-gl=egl"; do
  r=$(python3 $R --probe --gpu-args="$cand" 2>&1 | tail -1)
  echo "probe [$cand] -> $r"
  case "$r" in *NVIDIA*|*nvidia*) GPU_ARGS="$cand"; break;; esac
done
if [ -z "$GPU_ARGS" ]; then echo "NO GPU WEBGL"; exit 1; fi
python3 $R --web /work/new/web --side new --size "$SIZE" --fps "$FPS" --shots /in/shots.json --frames /work/frames \
  --gpu-args="$GPU_ARGS" --require-gpu --port 8872 || exit 1
ffmpeg -y -loglevel error -framerate "$FPS" -i /work/frames/new_%05d.jpg -c:v libx264 -preset slow -crf 12 -pix_fmt yuv420p /out/room.mp4 || exit 1
cp /work/frames/new_meta.json /out/room.json
ls -la /out
