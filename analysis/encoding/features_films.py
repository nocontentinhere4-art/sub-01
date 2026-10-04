"""Image features of the three Blender open movies as Emo-FilM showed them (code/BBL_experiment_Movies_without_credits
_exp_files.xlsx: the cut from LOWER_LIM to UPPER_LIM of each file), 2 frames a second, with the runtime encoder of
sensory.py (OpenCLIP ViT-B-32 / LAION-2B, int8 ONNX) and its low-level measures (luminance, contrast, change from the
frame SENSE_EVERY_S earlier, as the live server compares screenshots taken SENSE_EVERY_S apart).

Films (CC BY 3.0, Blender Foundation): download.blender.org -- Big Buck Bunny 640x360 m4v (9:56), Sintel 720p mkv
(14:48), Tears of Steel 720p mov (12:14); the lengths match the experiment sheet's LENGTH column.

Output: out/encoding_work/features/<film>.npz {t (N,) film time of each frame (s, 0 = first shown frame),
        emb (N, 512), ll (N, 3)}
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common import WORK, fetch  # noqa: E402
import sensory  # noqa: E402

FPS = 2
FILMS = {   # name in the dataset: (url, file, cut start s, cut length s)
    "BigBuckBunny": ("https://download.blender.org/peach/bigbuckbunny_movies/BigBuckBunny_640x360.m4v.zip",
                     "BigBuckBunny_640x360.m4v", 0, 8 * 60 + 10),
    "Sintel": ("https://download.blender.org/durian/movies/Sintel.2010.720p.mkv.zip",
               "Sintel.2010.720p.mkv", 23, 12 * 60 + 2),
    "TearsOfSteel": ("https://download.blender.org/demo/movies/ToS/tears_of_steel_720p.mov",
                     "tears_of_steel_720p.mov", 0, 9 * 60 + 48),
}
H = 360                                   # frames decoded at this height (keeps the aspect), then sensory.clip_pixels


def frames(path, start, length):
    """Yield PIL images at FPS from [start, start + length) of the film."""
    from PIL import Image
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    w0, h0 = [int(x) for x in probe.strip().split(",")[:2]]
    w = int(round(w0 * H / h0 / 2) * 2)
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", str(path), "-t", str(length),
           "-vf", f"fps={FPS},scale={w}:{H}:flags=bicubic", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * H * 3
    while (buf := p.stdout.read(n)) and len(buf) == n:
        yield Image.frombytes("RGB", (w, H), buf)
    p.wait()


def main():
    out = WORK / "features"
    out.mkdir(parents=True, exist_ok=True)
    files = sensory.ensure_models(WORK / "models", download_ok=True)
    enc = sensory.VisionEncoder(files["vision"], threads=2)
    lag = int(sensory.SENSE_EVERY_S * FPS)
    for name, (url, fname, start, length) in FILMS.items():
        dest = out / f"{name}.npz"
        if dest.exists():
            continue
        path = WORK / "films" / fname
        if not path.exists():
            z = fetch(url, WORK / "films" / Path(url).name)
            if z.suffix == ".zip":
                subprocess.run(["unzip", "-o", "-q", str(z), "-d", str(WORK / "films")], check=True)
        embs, lls, thumbs, batch = [], [], [], []
        for img in frames(path, start, length):
            ll, th = sensory.low_level(img, thumbs[-lag] if len(thumbs) >= lag else None)
            thumbs.append(th)
            lls.append(ll)
            batch.append(sensory.clip_pixels(img))
            if len(batch) == 32:
                embs.append(enc.embed(np.stack(batch)))
                batch = []
        if batch:
            embs.append(enc.embed(np.stack(batch)))
        emb, ll = np.concatenate(embs), np.stack(lls)
        t = (np.arange(len(emb)) + 0.5) / FPS
        np.savez_compressed(dest, t=t, emb=emb, ll=ll)
        print(name, emb.shape, f"{len(emb) / FPS:.0f} s of {length} s", flush=True)


if __name__ == "__main__":
    main()
