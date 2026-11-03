"""Render his chair lines ahead with the owner's VoiceStudio app (speech.VoiceStudio) into web/chair_voice/.

    .venv/bin/python tools/chair_voice_bank.py --url http://localhost:3900 --profile BREZ

Renders every reaction (speech.REACTIONS, by class, so the settling lines get the whisper tag) and every rule comment
with no number in it, writes <key>.wav files and bank.json ({"<text>|<style>": {file, ms, text, style}}), and
re-renders nothing that is already there (delete the folder to start over). Production plays these (speech.BankVoice).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import speech                                       # noqa: E402


def lines():
    for cls, texts in speech.REACTIONS.items():
        for t in texts:
            yield t, cls
    for cls, texts in speech.RULE_COMMENTS.items():
        for t in texts:
            if "{" not in t:
                yield t, cls


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:3900")
    ap.add_argument("--profile", default="BREZ")
    a = ap.parse_args(argv)
    out = HERE / speech.BANK_DIR
    out.mkdir(parents=True, exist_ok=True)
    bank = speech.load_bank(HERE)
    v = speech.VoiceStudio(a.url, profile=a.profile)
    if not v.available():
        sys.exit(f"VoiceStudio is not answering at {a.url}")
    n = 0
    for text, cls in lines():
        k = f"{text}|{cls}"
        if k in bank and (out / bank[k]["file"]).exists():
            continue
        r = v.synthesize(text, cls)
        if not r:
            sys.exit(f"render failed for {text!r}")
        key = r["url"].rsplit("/", 1)[1][:-4]
        (out / f"{key}.wav").write_bytes(v.audio(key))
        bank[k] = {"file": f"{key}.wav", "ms": r["ms"], "text": text, "style": cls}
        n += 1
        print(f"{cls:7s} {r['ms']:5d} ms  {text}")
    (out / "bank.json").write_text(json.dumps(bank, indent=1, ensure_ascii=False) + "\n")
    print(f"{n} rendered, {len(bank)} lines in {out}")


if __name__ == "__main__":
    main()
