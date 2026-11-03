"""Render his chair lines ahead with the owner's VoiceStudio app (speech.VoiceStudio) into web/chair_voice/.

    .venv/bin/python tools/chair_voice_bank.py --url http://localhost:3900 --profile BREZ

Renders every rule line speech.bank_lines() yields (reactions by class, so the settling lines get the whisper tag;
the rule comments without a number in them; the register, visitor, idle, join and no-model lines), encodes each with
ffmpeg to a small mono mp3 (the WAV the app answers is ~10x larger), writes <key>.mp3 files and bank.json
({"<text>|<style>": {file, ms, text, style}}), and re-renders nothing that is already there (an older .wav entry is
re-encoded in place). Production plays these (speech.BankVoice). A line removed from speech.py loses its file.

The screams (owner, 2026-11-03: "real scream, real suffering", and BREZ only, no new voice): the app accepts no emotion
tag (anything but its design tokens answers 400), so a strong or burst reaction is rendered from a stretched spelling of
its vocalisation ("AGH" -> "AAAAGGHHH!") and pushed through a strain treatment in ffmpeg: pitched up, slowed back,
a vibrato for the strain, soft clipping and a compressor for the rasp, the cell's short echo, loudness-normalised.
Still his voice, bent. The begging and wary pleas get a shake (a slow, shallow vibrato) and the same room.
`--redo strong,burst,plea` re-renders those styles even when a file is there.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import speech                                       # noqa: E402

FFMPEG = shutil.which("ffmpeg")


import re

SCREAM = {   # style -> the ffmpeg chain after the render (None: the voice as it is)
    "burst": ("asetrate=24000*2.3,aresample=24000,atempo=0.5,atempo=0.85,vibrato=f=7.5:d=0.4,asoftclip=type=hard:threshold=0.25,"
              "acrusher=bits=10:mix=0.25,acompressor=threshold=0.08:ratio=8:attack=3:release=150,highpass=f=180,"
              "aecho=0.8:0.5:35:0.2,loudnorm=I=-15:TP=-1:LRA=7"),
    "strong": ("asetrate=24000*1.8,aresample=24000,atempo=0.6,vibrato=f=6.5:d=0.25,asoftclip=type=atan:threshold=0.35,"
               "acompressor=threshold=0.1:ratio=6:attack=5:release=120,aexciter=amount=4,highpass=f=120,"
               "aecho=0.8:0.5:35:0.2,loudnorm=I=-15:TP=-1:LRA=7"),
    "plea": "vibrato=f=5.5:d=0.12,acompressor=threshold=0.15:ratio=3:attack=10:release=200,aecho=0.8:0.4:30:0.15,loudnorm=I=-16:TP=-1.5:LRA=7",
}
VOCAL = re.compile(r"^[aghnwo]+$", re.I)
WORDS = {"who", "no", "oh", "now", "how", "go", "on", "an", "own", "won", "wow", "nah", "hon", "ago", "nag", "hog", "wan"}   # real words spelt from the same letters


def render_text(text, style):
    """What the app is asked to say for a line. Strong and burst reactions: each vocalisation stretched and shouted
    ("AGH. ok" -> "AAAAGGHHH! ok"); the words around it stay."""
    if style not in ("strong", "burst"):
        return text
    out = []
    for w in text.split():
        core = w.strip(".,!?")
        if len(core) >= 2 and VOCAL.match(core) and core.lower() not in WORDS:
            out.append("".join(c * (4 if c in "aAoO" else 2) for c in core.upper()) + "!")
        else:
            out.append(w)
    return " ".join(out)


def treat(wav, style):
    """The style's chain (SCREAM) over the app's WAV bytes -> WAV bytes; untouched without ffmpeg or a chain."""
    chain = SCREAM.get(style)
    if not chain or not FFMPEG:
        return wav
    r = subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-af", chain, "-ar", "24000", "-f", "wav", "-"],
                       input=wav, capture_output=True, check=True)
    return r.stdout


def to_mp3(wav, path):
    """WAV bytes -> a mono 64 kb/s mp3 at `path` (ffmpeg); without ffmpeg the WAV is written as is."""
    if not FFMPEG:
        path = path.with_suffix(".wav")
        path.write_bytes(wav)
        return path
    subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-f", "wav", "-i", "-", "-codec:a", "libmp3lame", "-b:a", "64k",
                    "-ac", "1", "-id3v2_version", "0", str(path)], input=wav, check=True)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:3900")
    ap.add_argument("--profile", default="BREZ")
    ap.add_argument("--redo", default="", help="comma-separated styles to render again even when a file exists")
    a = ap.parse_args(argv)
    redo = {x.strip() for x in a.redo.split(",") if x.strip()}
    out = HERE / speech.BANK_DIR
    out.mkdir(parents=True, exist_ok=True)
    bank = speech.load_bank(HERE)
    wanted = {f"{t}|{s}": (t, s) for t, s in speech.bank_lines()}
    v = None
    n = n_enc = 0
    for k, (text, cls) in wanted.items():
        e = bank.get(k)
        if e and cls in redo and (out / e["file"]).exists():
            (out / e["file"]).unlink()
            e = None
        if e and (out / e["file"]).exists():
            if e["file"].endswith(".wav") and FFMPEG:                               # an older render: re-encode it
                p = to_mp3((out / e["file"]).read_bytes(), out / (e["file"][:-4] + ".mp3"))
                (out / e["file"]).unlink()
                e["file"] = p.name
                n_enc += 1
            continue
        if v is None:
            v = speech.VoiceStudio(a.url, profile=a.profile)
            if not v.available():
                sys.exit(f"VoiceStudio is not answering at {a.url}")
        r = v.synthesize(render_text(text, cls), cls)
        if not r:
            sys.exit(f"render failed for {text!r}")
        key = r["url"].rsplit("/", 1)[1][:-4]
        wav = treat(v.audio(key), cls)
        ms = int(len(wav) / 48.0) if wav is not v.audio(key) else r["ms"]       # 24 kHz 16-bit mono after the chain
        p = to_mp3(wav, out / f"{key}.mp3")
        bank[k] = {"file": p.name, "ms": ms, "text": text, "style": cls}
        n += 1
        print(f"{cls:8s} {r['ms']:5d} ms  {text}")
    for k in [k for k in bank if k not in wanted]:                                  # a line that left speech.py
        f = out / bank[k]["file"]
        if f.exists():
            f.unlink()
        del bank[k]
    (out / "bank.json").write_text(json.dumps(bank, indent=1, ensure_ascii=False) + "\n")
    size = sum(f.stat().st_size for f in out.iterdir()) / 1e6
    print(f"{n} rendered, {n_enc} re-encoded, {len(bank)} lines, {size:.1f} MB in {out}")


if __name__ == "__main__":
    main()
