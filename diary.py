"""Dream diary: SUB-01's nights, written down even when nobody is watching.

During REM the eye renders a dream frame every DREAM_EVERY_S of simulated time (at most MAX_UNATTENDED per
night without viewers, so the cost stays at a few cents a night). Frames seen live by viewers during REM are
added too. When the night closes (natural wake-up), the diary gets a short title + text written by the language
model from the dream scenes and the replayed chat messages, plus a ready-to-post share text. Nothing is posted
anywhere automatically.

data/diary/<night date>.json   one file per night
data/diary/img/<date>/*.jpg    the night's frames (kept apart from the eye's rolling frame buffer)

Dreams are AI-generated from the model's state and from REM replays of chat messages. They are not the real
person's dreams, and nothing here claims the model dreams in the way a person does.
"""
import json
import re
import shutil
import time
from pathlib import Path

DREAM_EVERY_S = 6 * 60          # simulated seconds between unattended dream frames
MIN_REAL_GAP_S = 20             # never faster than this in real seconds (accelerated clocks)
MAX_UNATTENDED = 18             # unattended frames per night (~$0.003 each on FLUX schnell)
KEEP_IMG_NIGHTS = 120           # nights whose images are kept on the volume
SHARE_MAX = 280
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

SYSTEM = """You write the morning entry of a dream diary for SUB-01, a simulated brain model built from public MRI scans.
You receive JSON: the dream scenes the model's image generator produced during REM, the chat messages it replayed,
and when it slept. Reply with JSON only: {"title": "...", "text": "..."}
- title: max 8 words, English, evocative, no quotes, no hashtags.
- text: 2-3 sentences, max 60 words, English, third person ("SUB-01 dreamt..."), concrete images from the scenes,
  weave in the replayed messages. Calm, precise, a little strange.
- Never say or imply that SUB-01 is conscious, alive, sentient, human or a person, or the person the scans came
  from. No money, prices, tokens, buying or selling. No people's names."""

BLOCK = re.compile(
    r"conscious|sentien|alive|self.?aware|\bsoul\b|\bhuman\b|\bperson\b|\bhe\b|\bshe\b|"
    r"\bbuy|\bsell|\bprice|\btoken|\bcoin|\bmoney|\bpump|\bdump|\$|https?://|www\.|@\w", re.I)


def clean_line(s, limit):
    s = re.sub(r"\s+", " ", str(s or "")).strip().strip('"').strip()
    if not s or BLOCK.search(s):
        return ""
    if len(s) > limit:                                 # cut at the last full sentence that fits
        cut = s[:limit]
        end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
        s = cut[:end + 1] if end > limit // 3 else cut.rsplit(" ", 1)[0] + "\u2026"
    return s


class Diary:
    def __init__(self, root, frames_dir):
        self.dir = Path(root) / "diary"
        self.img = self.dir / "img"
        self.img.mkdir(parents=True, exist_ok=True)
        self.frames_dir = Path(frames_dir)
        self.last_real = 0.0

    # --- storage -------------------------------------------------------------
    def path(self, date):
        if not DATE.match(str(date)):
            raise ValueError("bad date")
        return self.dir / f"{date}.json"

    def load(self, date):
        p = self.path(date)
        return json.loads(p.read_text()) if p.exists() else None

    def save(self, d):
        p = self.path(d["date"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False))
        tmp.replace(p)

    def entry(self, date):
        return self.load(date) or {"date": date, "frames": [], "unattended": 0, "last_sim": 0.0, "closed": False}

    # --- during the night ----------------------------------------------------
    def due(self, engine, t_sim, now_real=None):
        """True when an unattended dream frame should be rendered now."""
        now_real = time.time() if now_real is None else now_real
        if engine.stage != "REM" or engine.night is None:
            return False
        d = self.entry(engine.night["date"])
        return (d["unattended"] < MAX_UNATTENDED and t_sim - d["last_sim"] >= DREAM_EVERY_S
                and now_real - self.last_real >= MIN_REAL_GAP_S)

    def add(self, date, rec, t_sim, attended):
        """Keep a REM frame in the night's entry (its image is copied out of the eye's rolling buffer)."""
        if rec.get("reused") or rec.get("stage") != "REM":
            return None
        d = self.entry(date)
        src = self.frames_dir / Path(rec["img"]).name
        if not src.exists():
            return None
        (self.img / date).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, self.img / date / src.name)
        d["frames"].append({"t": rec["t"], "img": f"/diary-img/{date}/{src.name}", "thought": rec.get("thought", ""),
                            "scene": rec.get("scene", ""), "replayed": (rec.get("why") or {}).get("replayed", []),
                            "attended": bool(attended)})
        d["last_sim"] = t_sim
        if not attended:
            d["unattended"] += 1
            self.last_real = time.time()
        self.save(d)
        print(f"diary: dream frame {len(d['frames'])} of {date}" + ("" if attended else " (unattended)"), flush=True)
        return d

    # --- in the morning --------------------------------------------------------
    def pending_close(self, engine):
        """Date of a finished night whose diary entry is still open, else None."""
        n = engine.last_night
        if not n or (engine.night is not None and engine.night.get("date") == n["date"]):
            return None
        if not n.get("sleep_onset"):
            return None                                # stayed awake all night: nothing to write
        d = self.load(n["date"])
        return None if d and d["closed"] else n["date"]

    def close(self, night, llm=None):
        """Write title, text and share text for a finished night. `llm.ask(system, user)` is optional."""
        d = self.entry(night["date"])
        replays = [r["text"] for r in night.get("replays", [])]
        counts = {}
        for x in replays:
            counts[x] = counts.get(x, 0) + 1
        top = sorted(counts, key=lambda x: -counts[x])[:5]
        facts = {"sleep_onset": (night.get("sleep_onset") or "")[-5:], "woke_up": (night.get("woke_up") or "")[-5:],
                 "wakeups": len(night.get("wakeups", [])), "replays": len(replays), "top_replayed": top,
                 "dream_frames": len(d["frames"])}
        title = text = ""
        if llm is not None and d["frames"]:
            user = json.dumps({"scenes": [f["scene"] for f in d["frames"] if f["scene"]][-12:],
                               "replayed_messages": top, "slept": f"{facts['sleep_onset']}-{facts['woke_up']}"})
            for _ in range(2):                         # one retry: small models sometimes break the JSON
                try:
                    raw = llm.ask(SYSTEM, user)
                    m = re.search(r"\{.*?\}", raw, re.S)
                    out = json.loads(m.group(0)) if m else {}
                    title, text = clean_line(out.get("title"), 80), clean_line(out.get("text"), 420)
                except Exception as e:                 # the diary must never break on a provider error
                    print("diary: summary failed:", repr(e)[:160], flush=True)
                if title and text:
                    break
                print("diary: summary rejected or empty", flush=True)
        if not text:
            text = (f"SUB-01 slept {facts['sleep_onset']}-{facts['woke_up']} and replayed {len(replays)} "
                    f"message{'s' * (len(replays) != 1)} during REM" +
                    (f", most often “{top[0][:80]}”." if top else "."))
        d.update(title=title or f"Night of {night['date']}", text=text, facts=facts, closed=True,
                 share=self.share(night["date"], title, facts), closed_at=time.time())
        self.save(d)
        self.prune()
        return d

    @staticmethod
    def share(date, title, facts):
        lines = [f"SUB-01 · night of {date}" + (f" — {title}" if title else ""),
                 f"Slept {facts['sleep_onset']}–{facts['woke_up']} Tokyo time"
                 + (f", woke {facts['wakeups']}x" if facts["wakeups"] else "") + "."]
        if facts["replays"]:
            lines.append(f"In REM it replayed {facts['replays']} of your messages.")
            if facts["top_replayed"]:
                lines.append(f"Most often: “{facts['top_replayed'][0][:90]}”")
        lines.append("A model of brain activity, not a mind.")
        out = "\n".join(lines)
        while len(out) > SHARE_MAX and len(lines) > 2:
            lines.pop(-2)
            out = "\n".join(lines)
        return out[:SHARE_MAX]

    def prune(self):
        dirs = sorted(p for p in self.img.iterdir() if p.is_dir())
        for p in dirs[:-KEEP_IMG_NIGHTS]:
            shutil.rmtree(p, ignore_errors=True)

    # --- api -------------------------------------------------------------------
    def index(self, n=30):
        out = []
        for p in sorted(self.dir.glob("*.json"), reverse=True)[:n]:
            d = json.loads(p.read_text())
            out.append({"date": d["date"], "title": d.get("title", ""), "closed": d.get("closed", False),
                        "frames": len(d["frames"]), "cover": d["frames"][len(d["frames"]) // 2]["img"] if d["frames"] else None})
        return out
