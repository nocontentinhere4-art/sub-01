"""Render his chair lines ahead with the owner's VoiceStudio app (speech.VoiceStudio) into web/chair_voice/.

    .venv/bin/python tools/chair_voice_bank.py --url http://localhost:3900 --profile BREZ

Renders every rule line speech.bank_lines() yields (reactions by class, so the settling lines get the whisper tag;
the rule comments without a number in them; the register, visitor, idle, join and no-model lines), encodes each with
ffmpeg to a small mono mp3 (the WAV the app answers is ~10x larger), writes <key>.mp3 files and bank.json
({"<text>|<style>": {file, ms, text, style}}), and re-renders nothing that is already there (an older .wav entry is
re-encoded in place). Production plays these (speech.BankVoice). A line removed from speech.py loses its file.
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
    a = ap.parse_args(argv)
    out = HERE / speech.BANK_DIR
    out.mkdir(parents=True, exist_ok=True)
    bank = speech.load_bank(HERE)
    wanted = {f"{t}|{s}": (t, s) for t, s in speech.bank_lines()}
    v = None
    n = n_enc = 0
    for k, (text, cls) in wanted.items():
        e = bank.get(k)
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
        r = v.synthesize(text, cls)
        if not r:
            sys.exit(f"render failed for {text!r}")
        key = r["url"].rsplit("/", 1)[1][:-4]
        p = to_mp3(v.audio(key), out / f"{key}.mp3")
        bank[k] = {"file": p.name, "ms": r["ms"], "text": text, "style": cls}
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
