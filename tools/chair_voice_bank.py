"""Render his chair lines ahead with the owner's VoiceStudio app (speech.VoiceStudio) into web/chair_voice/.

    .venv/bin/python tools/chair_voice_bank.py --url http://localhost:3900 --profile BREZ

Renders every rule line speech.bank_lines() yields (reactions by class, so the settling lines get the whisper tag;
the rule comments without a number in them; the register, visitor, idle, join and no-model lines), encodes each with
ffmpeg to a small mono mp3 (the WAV the app answers is ~10x larger), writes <key>.mp3 files and bank.json
({"<text>|<style>": {file, ms, text, style}}), and re-renders nothing that is already there (an older .wav entry is
re-encoded in place). Production plays these (speech.BankVoice). A line removed from speech.py loses its file.

The screams (owner, 2026-11-03: "real scream, real suffering"; then, of the rendered and pitched tries, "he is laughing",
"go and search for real screams and do the same with him"): a text-to-speech engine cannot scream, so a strong or burst
reaction is built from a real one. tools/chair_screams/ holds recordings of real people screaming (public domain / CC0,
Freesound and Wikimedia Commons, listed in its index.json) converted into the BREZ voice with Seed-VC (zero-shot voice
conversion, the f0-conditioned model: the scream keeps its pitch, breath and break; only the timbre is his). The line's
leading vocalisation ("AGH", "ghh", "hhhah") is replaced by one of those; the words after it ("ok. hello") are rendered as
usual and follow after a short gap; a strong or burst line without one ("nope nope", the class's comments) stays
spoken. The breaths (speech.BREATHS: pant, sob, groan) are such recordings alone, their text the caption. Recordings go
round the index in bank order, so lines differ.
The begging and wary pleas get a shake (a slow, shallow vibrato) and the cell's short echo.
`--redo strong,burst,plea` re-renders those styles even when a file is there.
"""
import argparse
import hashlib
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
    "plea": "vibrato=f=5.5:d=0.12,acompressor=threshold=0.15:ratio=3:attack=10:release=200,aecho=0.8:0.4:30:0.15,loudnorm=I=-16:TP=-1.5:LRA=7",
}
SCREAMS_DIR = HERE / "tools" / "chair_screams"       # real screams converted into his voice: index.json lists file, class, source
GAP_MS = 140                                           # between the scream and the words after it
BREATH_STYLES = ("pant", "sob", "groan")               # a breath line is a recording alone; its text is the caption
VOCAL = re.compile(r"^[aghnwo]+$", re.I)
WORDS = {"who", "no", "oh", "now", "how", "go", "on", "an", "own", "won", "wow", "nah", "hon", "ago", "nag", "hog", "wan"}   # real words spelt from the same letters


def split_vocal(text):
    """(vocalisation, words): the leading vocalisation tokens of a line and the words after them ("AGH. ok. hello" ->
    ("AGH", "ok. hello"); "nope nope" -> ("", "nope nope"); "hhhah" -> ("hhhah", ""))."""
    toks = text.split()
    i = 0
    while i < len(toks):
        core = toks[i].strip(".,!?")
        if len(core) >= 2 and VOCAL.match(core) and core.lower() not in WORDS:
            i += 1
        else:
            break
    return " ".join(toks[:i]), " ".join(toks[i:])


def render_text(text, style):
    """What the app is asked to say for a line: for a strong or burst reaction the words after the vocalisation (the
    scream itself is a recording, see scream_for), else the line as it is."""
    if style in BREATH_STYLES:
        return ""
    if style not in ("strong", "burst"):
        return text
    return split_vocal(text)[1]


def load_screams():
    """{class: [(path, ms, source), ...]} from tools/chair_screams/index.json, in its order; {} without the folder."""
    try:
        idx = json.loads((SCREAMS_DIR / "index.json").read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for e in idx:
        out.setdefault(e["class"], []).append((SCREAMS_DIR / e["file"], int(e["ms"]), e.get("source", "")))
    return out


def scream_for(text, style, screams, counters):
    """The recording a line starts with, or None: every breath line; a strong or burst line with a vocalisation to replace.
    Lines take the class's screams in turn (counters), so a bank built in order spreads them."""
    pool = screams.get(style) or []
    if not pool:
        return None
    if style not in BREATH_STYLES and not split_vocal(text)[0]:        # a comment in the class, or "nope nope": spoken
        return None
    k = counters.get(style, 0)
    counters[style] = k + 1
    return pool[k % len(pool)]


def decode(path):
    """Any audio file -> 24 kHz 16-bit mono WAV bytes (ffmpeg)."""
    r = subprocess.run([FFMPEG, "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "24000", "-f", "wav", "-"],
                       capture_output=True, check=True)
    return r.stdout


def join_wavs(parts, gap_ms=GAP_MS):
    """WAV byte strings (24 kHz 16-bit mono) one after the other with a gap of silence between -> WAV bytes."""
    import io
    import wave
    pcm = []
    for i, w in enumerate(parts):
        with wave.open(io.BytesIO(w)) as f:
            pcm.append(f.readframes(f.getnframes()))
        if i < len(parts) - 1:
            pcm.append(b"\0\0" * int(24000 * gap_ms / 1000))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(24000)
        f.writeframes(b"".join(pcm))
    return buf.getvalue()


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
    screams, counters = load_screams(), {}
    if not screams:
        print(f"no screams in {SCREAMS_DIR}: strong and burst lines will be the rendered words alone", flush=True)
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
        scream = scream_for(text, cls, screams, counters)
        say = render_text(text, cls)
        parts = [decode(scream[0])] if scream else []
        if say.strip():
            r = v.synthesize(say, cls)
            if not r:
                sys.exit(f"render failed for {text!r}")
            key = r["url"].rsplit("/", 1)[1][:-4]
            parts.append(treat(v.audio(key), cls))
        elif scream:
            key = hashlib.sha1(f"{text}|{cls}|{scream[0].name}".encode()).hexdigest()[:16]
        else:                                                                       # a breath without its recording
            print(f"{cls:8s} skipped (no recording in {SCREAMS_DIR.name}): {text}", flush=True)
            continue
        wav = join_wavs(parts) if len(parts) > 1 else parts[0]
        ms = int(len(wav) / 48.0)                                                   # 24 kHz 16-bit mono
        p = to_mp3(wav, out / f"{key}.mp3")
        bank[k] = {"file": p.name, "ms": ms, "text": text, "style": cls}
        n += 1
        print(f"{cls:8s} {ms:5d} ms  {text}" + (f"   [{scream[0].name}]" if scream else ""))
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
