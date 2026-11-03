#!/bin/bash
# Lyra 1 (NVIDIA, Apache-2.0 code; models under the NVIDIA Open Model License: commercial use allowed) on one RunPod
# H100/A100-80GB pod, run by analysis/runpod_job.py (--kind h100). Uploads are in /in (input.png, optionally prompt.txt);
# results go to /out (fetched, then the pod is deleted). One image -> six camera trajectories of video latents (GEN3C,
# Cosmos 7B) -> the 3DGS decoder -> a Gaussian .ply in the first camera's OpenCV frame (y down, z forward).
#
# Set-up follows Lyra-1/INSTALL.md with three cuts that keep a run inside the runner's 60-minute pod limit:
# - no conda: the image already has CUDA 12.4 (nvcc) and Python 3.10 comes from the image's conda as a bare env;
# - no Apex (only Lyra's training imports it) and no guardrail / Pixtral prompt-upsampler weights (the SDG script turns
#   both off itself);
# - the weights download in the background while pip builds, and google-t5/t5-11b only as its PyTorch weights (the
#   snapshot in download_gen3c_checkpoints.py also pulls the TensorFlow copy).
# Optional env: HF_TOKEN (only if a repo turns out gated), MOVE (total_movement_distance_factor, default 1.0).
set -uxo pipefail
T0=$(date +%s); stage(){ echo "=== $1 at $(( $(date +%s) - T0 )) s" | tee -a /out/stages.txt; }
cd /work
nvidia-smi --query-gpu=name,memory.total --format=csv | tee /out/gpu.txt
df -h /work | tail -1
export MAX_JOBS=$(nproc) HF_HUB_ENABLE_HF_TRANSFER=1 HF_HUB_DISABLE_TELEMETRY=1 PIP_NO_CACHE_DIR=1 CUDA_HOME=/usr/local/cuda
[ -n "${HF_TOKEN:-}" ] && export HUGGING_FACE_HUB_TOKEN=$HF_TOKEN

stage clone
git clone --depth 1 https://github.com/nv-tlabs/lyra /work/lyra
cd /work/lyra && git rev-parse HEAD | tee /out/lyra_commit.txt
cd /work/lyra/Lyra-1
mkdir -p checkpoints

stage weights-start                                   # base python of the image: just the hub client, in the background
python3 -m pip install -q "huggingface_hub[hf_transfer]>=0.29" 2>&1 | tail -1
cat > /work/dl.py <<'EOF'
import os, sys
from huggingface_hub import snapshot_download
C = "/work/lyra/Lyra-1/checkpoints"
jobs = [("nvidia/Gen3C-Cosmos-7B", "Gen3C-Cosmos-7B", ["README.md", "model.pt", "mean_std.pt", "image_mean_std.pt", "config.json", "*.jit"]),
        ("nvidia/Cosmos-Tokenize1-CV8x8x8-720p", "Cosmos-Tokenize1-CV8x8x8-720p", None),
        ("google-t5/t5-11b", "google-t5/t5-11b", ["*.json", "*.model", "pytorch_model.bin"]),
        ("nvidia/Lyra", "Lyra", ["lyra_static.pt"])]
for repo, sub, allow in jobs:
    print("downloading", repo, flush=True)
    snapshot_download(repo_id=repo, local_dir=f"{C}/{sub}", allow_patterns=allow)
    print("done", repo, flush=True)
open("/work/WEIGHTS_OK", "w").write("ok")
EOF
(python3 /work/dl.py > /out/download.log 2>&1 || echo "download failed" >> /out/download.log) &
DL=$!

stage env
/opt/conda/bin/conda create -y -q -p /work/env python=3.10 pip=25.0 > /dev/null
export PATH=/work/env/bin:$PATH
python -V
python -m pip install -q torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124 2>&1 | tail -2
python -m pip install -q -r requirements_gen3c.txt 2>&1 | tail -2
python -m pip install -q ninja packaging wheel setuptools 2>&1 | tail -1
stage lyra-deps                                       # flash-attn / causal-conv1d / mamba fetch prebuilt wheels when they match
python -m pip install -q --no-build-isolation -r requirements_lyra.txt 2>&1 | tail -3
ln -sf /work/env/lib/python3.10/site-packages/nvidia/*/include/* /work/env/include/ 2>/dev/null
ln -sf /work/env/lib/python3.10/site-packages/nvidia/*/include/* /work/env/include/python3.10 2>/dev/null
stage transformer-engine
python -m pip install -q --no-build-isolation "transformer-engine[pytorch]==1.12.0" 2>&1 | tail -3
stage moge-mamba
python -m pip install -q git+https://github.com/microsoft/MoGe.git 2>&1 | tail -1
python -m pip install -q --no-build-isolation "git+https://github.com/state-spaces/mamba@v2.2.4" 2>&1 | tail -2
PYTHONPATH=$(pwd) python -c "import torch, transformer_engine, mamba_ssm, gsplat, moge; print('imports ok', torch.__version__, torch.cuda.is_available())" 2>&1 | tee /out/imports.txt

stage weights-wait
wait $DL
cat /out/download.log | tail -8
[ -f /work/WEIGHTS_OK ] || { echo "weights missing"; exit 1; }
du -sh checkpoints/* | tee /out/weights.txt

stage sdg                                             # image -> six trajectories of video latents (Cosmos 7B)
mkdir -p assets/demo/static/diffusion_input/images
cp /in/input.png assets/demo/static/diffusion_input/images/input.png
PROMPT=$( [ -f /in/prompt.txt ] && cat /in/prompt.txt || echo "" )
CUDA_HOME=$CUDA_HOME PYTHONPATH=$(pwd) torchrun --nproc_per_node=1 cosmos_predict1/diffusion/inference/gen3c_single_image_sdg.py \
    --checkpoint_dir checkpoints \
    --num_gpus 1 \
    --input_image_path assets/demo/static/diffusion_input/images/input.png \
    --video_save_folder assets/demo/static/diffusion_output_generated \
    --foreground_masking \
    --multi_trajectory \
    --total_movement_distance_factor "${MOVE:-1.0}" \
    --offload_prompt_upsampler --offload_guardrail_models --disable_guardrail \
    ${PROMPT:+--prompt "$PROMPT"} 2>&1 | tail -40
ls -R assets/demo/static/diffusion_output_generated | head -40

stage decode                                          # latents -> 3D Gaussians
cat > configs/demo/sub01_static.yaml <<'EOF'
out_dir_inference: outputs/sub01/lyra_static
dataset_name: lyra_static_demo_generated
static_view_indices_fixed: ['5', '0', '1', '2', '3', '4']
target_index_subsample: 4
set_manual_time_idx: true
config_path: [configs/training/default.yaml, configs/training/3dgs_res_704_1280_views_121_multi_6_prune.yaml]
ckpt_path: checkpoints/Lyra/lyra_static.pt
save_gaussians: true
save_gaussians_orig: true
EOF
accelerate launch sample.py --config configs/demo/sub01_static.yaml 2>&1 | tail -30

stage pack
find outputs/sub01 -type f | head -50 | tee /out/files.txt
mkdir -p /out/lyra
find outputs/sub01 \( -name "*.ply" -o -name "*.mp4" \) -exec cp --parents {} /out/lyra/ \;
cp -r assets/demo/static/diffusion_output_generated /out/lyra/sdg 2>/dev/null; find /out/lyra/sdg -name "*.pt" -delete 2>/dev/null
cd /out && tar czf lyra_out.tar.gz lyra && ls -la /out
stage end
