"""His voice in the chair: short reactions and the odd comment, from the measured state, through a voice provider.

What is said is fiction: a character's lines, written from numbers the simulation measured (chair.py), never a
reading of what any neuron "felt". Two kinds of line:
  reaction  a sound or a word or two, decided from the open response card as the bins come in (fast, no model call):
            none (no distinguishable response yet), small (rate under 2x baseline), strong (2-4x), burst (over 4x or
            a burst), and a settling line once when the undershoot is deep. One reaction per stimulus, upgraded when
            the response grows (the smaller one is cancelled if it has not played).
  comment   one short line in his register, written by the language model from the structured measured state (the
            card, the recent history, whether the network is reacting or settling) through `ask` (live_server passes
            the mind's metered call, so the mind's daily cap and hourly call limit apply), at most one every
            COMMENT_EVERY_S and one per COMMENT_EVERY_N stimuli; with no model (no key, over the cap) a rule line.
            A comment written for a state that is no longer current (another shock landed meanwhile) is dropped.

The queue plays one line at a time (no overlap): a reaction interrupts a comment; a line older than its life is
dropped unplayed; a comment never plays while a reaction is pending. The voice provider turns a line into audio when
one is configured and reports "unavailable" otherwise; the page then shows the line as a caption only and moves no
mouth (the character has no jaw bone or face rig). There is no voice service in this repository today (NoVoice).
"""
import json
import random
import time

COMMENT_EVERY_S = 45.0
COMMENT_EVERY_N = 4
COMMENT_WORDS = 16
REACTION_LIFE_S, COMMENT_LIFE_S = 3.0, 12.0
MAX_QUEUE = 4
PRIORITY = {"reaction": 2, "comment": 1}

# his sounds, by response class. Short, lowercase, no claims. (Fiction: a character strapped in a chair.)
REACTIONS = {
    "none": ["...", "hm", "that it?", "nothing much"],
    "small": ["tss", "hh", "mm", "ok ok"],
    "strong": ["agh", "hng", "ah", "nope nope"],
    "burst": ["AGH", "ghh", "hhhah", "AH"],
    "settle": ["...hh", "give me a sec", "whew", "ok. ok."],
}
RULE_COMMENTS = {
    "none": ["that barely showed on the trace", "the line didn't even move", "you can see it: nothing"],
    "small": ["small one. the trace twitched", "that lit up a corner, not much more"],
    "strong": ["that one went {ratio}x over baseline", "most of the map lit for that one"],
    "burst": ["{recruit} of the regions fired for that. you can see it", "that was a burst. the trace is still coming down"],
    "settle": ["still coming back down from the last one", "the baseline is a way off yet"],
}
SYSTEM_COMMENT = (
    "You write one short line SUB-01 says, a fictional character of about 20 in a brain-simulation art project, "
    "strapped in a chair while visitors send simulated shocks to his simulated brain. You get the measured numbers "
    "(the response card and the recent history), never a feeling. He can comment on the numbers, be dry, rattled, "
    "short. Lowercase is fine, light slang is fine. At most 16 words. No emojis, no links, no quotes. Never say he "
    "feels pain or anything else as a fact; never say he is alive, conscious or human; never mention coins or money."
)
CLASS_RATIO = {"small": 1.2, "strong": 2.0, "burst": 4.0}


def classify(card):
    """Response class from a card (open or closed): by peak ratio against baseline, or 'none'."""
    if not card or not card.get("baseline"):
        return "none"
    r = card.get("peak_ratio") or 0.0
    if card.get("burst") or r >= CLASS_RATIO["burst"]:
        return "burst"
    if r >= CLASS_RATIO["strong"]:
        return "strong"
    if r >= CLASS_RATIO["small"]:
        return "small"
    return "none"


class VoiceProvider:
    name = "none"

    def available(self):
        return False

    def status(self):
        return {"available": self.available(), "provider": self.name}

    def synthesize(self, text, style):
        """-> {"url": ..., "ms": ...} or None when unavailable. Blocking; the hub runs it off the loop."""
        return None


class NoVoice(VoiceProvider):
    """No voice service is configured: lines are captions."""
    name = "none"


BANK_DIR = "web/chair_voice"              # the pre-rendered lines (tools/chair_voice_bank.py): served as static files
BANK_URL = "/chair_voice/"


def load_bank(root=None):
    """{"<text>|<style>": {"file", "ms", "text", "style"}} from the bank's index, or {} when there is none."""
    import os
    from pathlib import Path
    root = Path(root or os.path.dirname(os.path.abspath(__file__)))
    try:
        return json.loads((root / BANK_DIR / "bank.json").read_text())
    except (OSError, ValueError):
        return {}


class BankVoice(VoiceProvider):
    """His lines rendered ahead with the owner's app and committed as files: the reaction vocabulary and the rule
    comments without a number in them. Production plays these; anything not in the bank is a caption."""
    name = "bank"

    def __init__(self, bank, voice="BREZ"):
        self.bank, self.voice_name = bank, voice

    def available(self):
        return bool(self.bank)

    def status(self):
        return {"available": self.available(), "provider": self.name, "voice": self.voice_name, "lines": len(self.bank)}

    def synthesize(self, text, style):
        e = self.bank.get(f"{text}|{style}") or self.bank.get(f"{text}|")
        return {"url": BANK_URL + e["file"], "ms": int(e["ms"])} if e else None


class VoiceStudio(VoiceProvider):
    """The owner's local VoiceStudio app (github.com/debpalash/VoiceStudio, AGPL-3.0; the OmniVoice engine), through
    its local HTTP API: POST /generate (multipart form: text, instruct, seed, num_step, speed) answers WAV bytes with
    X-Audio-Id and X-Audio-Duration headers; GET /health says whether it is up. Only reachable where the app runs
    (loopback), so production stays on NoVoice unless VOICE_STUDIO_URL points somewhere that answers.

    The voice is a saved profile of the app when one is named (`profile`, by name or id, resolved through GET
    /profiles; the owner chose "BREZ", 2026-11-03), else a designed one: OmniVoice's `instruct` is a tag vocabulary
    (male, young adult, moderate pitch, whisper, accents; it has no emotion tags), and a fixed seed keeps the same
    designed voice across lines. The one expressive tag the engine supports, whisper, is used for the settling lines
    with either voice; nothing else is pretended.
    Renders are cached by (text, tags) and the reaction vocabulary is rendered ahead (warm) so a reaction does not
    wait on the engine; comments render on demand (a few seconds on this laptop's GPU)."""
    name = "voicestudio"
    TAGS = "male, young adult, moderate pitch"
    STYLE = {"settle": TAGS + ", whisper"}
    SEED = 7
    STEPS = 8                                # draft quality: a short line in ~1-2 s on an Apple GPU
    CACHE = 64

    def __init__(self, base_url, timeout=20.0, clock=time.time, profile=None, bank=None):
        import urllib.request
        self.base = base_url.rstrip("/")
        self.timeout, self.clock = timeout, clock
        self.bank = BankVoice(bank or {})          # the committed renders answer first, the app renders the rest
        self.profile, self.profile_id, self.profile_name = (profile or "").strip() or None, None, None
        self._ok, self._checked = False, -1e9
        self.cache = {}                      # (text, tags) -> {"wav": bytes, "ms": int, "id": str}
        self.order = []
        self.stats = {"renders": 0, "errors": 0, "hits": 0}
        self._urllib = urllib.request

    def available(self):
        now = self.clock()
        if now - self._checked > 30.0:
            self._checked = now
            try:
                with self._urllib.urlopen(self.base + "/health", timeout=3.0) as r:
                    self._ok = r.status == 200 and json.loads(r.read().decode()).get("status") == "ok"
            except Exception:
                self._ok = False
        return self._ok

    def status(self):
        return {"available": self.available(), "provider": self.name, "cached": len(self.cache),
                "voice": self.profile_name or (self.bank.voice_name if self.bank.available() else None)
                or ("profile " + self.profile if self.profile else "designed"), **self.stats}

    def resolve_profile(self):
        """The named profile's id (by name, case-insensitive, or its id), looked up once. None: not found, designed voice."""
        if self.profile is None or self.profile_id is not None:
            return self.profile_id
        try:
            with self._urllib.urlopen(self.base + "/profiles", timeout=5.0) as r:
                for p in json.loads(r.read().decode()):
                    if p.get("id") == self.profile or str(p.get("name", "")).lower() == self.profile.lower():
                        self.profile_id, self.profile_name = p["id"], p.get("name")
                        break
            if self.profile_id is None:
                print(f"voicestudio: no profile named {self.profile!r}: using the designed voice", flush=True)
                self.profile = None
        except Exception as e:
            print("voicestudio: profiles not read:", repr(e)[:80], flush=True)
        return self.profile_id

    def tags_for(self, style):
        if self.profile is not None:                                   # a profile is the voice; only whisper on top
            return "whisper" if style == "settle" else ""
        return self.STYLE.get(style, self.TAGS)

    def key(self, text, style):
        import hashlib
        return hashlib.sha1(f"{text}|{self.tags_for(style)}|{self.SEED}|{self.profile_id or ''}".encode()).hexdigest()[:16]

    def synthesize(self, text, style):
        """-> {"url": ..., "ms": int} or None. Blocking (the hub runs it off the loop)."""
        import uuid
        banked = self.bank.synthesize(text, style)
        if banked:
            self.stats["hits"] += 1
            return banked
        if self.profile is not None and self.profile_id is None:
            self.resolve_profile()
        k = self.key(text, style)
        if k in self.cache:
            self.stats["hits"] += 1
            return {"url": f"/api/chair/voice/{k}.wav", "ms": self.cache[k]["ms"]}
        if not self.available():
            return None
        boundary = "----sub01" + uuid.uuid4().hex
        fields = {"text": text, "seed": str(self.SEED), "num_step": str(self.STEPS), "speed": "1.0"}
        if self.tags_for(style):
            fields["instruct"] = self.tags_for(style)
        if self.profile_id:
            fields["profile_id"] = self.profile_id
        body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode() for n, v in fields.items()) + f"--{boundary}--\r\n".encode()
        req = self._urllib.Request(self.base + "/generate", data=body, method="POST",
                                   headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with self._urllib.urlopen(req, timeout=self.timeout) as r:
                wav = r.read()
                dur = r.headers.get("X-Audio-Duration")
                ms = int(float(dur) * 1000) if dur else None
        except Exception as e:
            self.stats["errors"] += 1
            print("voicestudio: render failed:", repr(e)[:100], flush=True)
            return None
        if ms is None:
            ms = int(len(wav) / 48.0)        # 24 kHz 16-bit mono: 48 bytes a millisecond
        self.stats["renders"] += 1
        self.cache[k] = {"wav": wav, "ms": ms, "text": text}
        self.order.append(k)
        while len(self.order) > self.CACHE:
            self.cache.pop(self.order.pop(0), None)
        return {"url": f"/api/chair/voice/{k}.wav", "ms": ms}

    def audio(self, key):
        c = self.cache.get(key)
        return c["wav"] if c else None

    def warm(self):
        """Render the reaction vocabulary ahead (a background thread at start). Stops at the first failure."""
        for cls, lines in REACTIONS.items():
            for text in lines:
                if self.synthesize(text, cls) is None:
                    return False
        return True


def voice_from_env(env=None, bank=None):
    """VOICE_STUDIO_URL set -> VoiceStudio (VOICE_STUDIO_PROFILE: a saved profile's name or id) with the bank in
    front; no app but a bank -> BankVoice; else NoVoice."""
    import os
    env = env or os.environ
    bank = load_bank() if bank is None else bank
    url = env.get("VOICE_STUDIO_URL", "").strip()
    if url:
        return VoiceStudio(url, profile=env.get("VOICE_STUDIO_PROFILE", ""), bank=bank)
    return BankVoice(bank) if bank else NoVoice()


class Speech:
    def __init__(self, ask=None, voice=None, clock=time.time, rng=None):
        self.ask = ask                       # callable(system, user) -> text or None (metered; may be None)
        self.voice = voice or NoVoice()
        self.clock = clock
        self.rng = rng or random.Random(11)
        self.queue = []                      # pending lines
        self.playing = None                  # {"id", "until", "kind"}
        self.n = 0
        self.said = {}                       # stimulus id -> the class already reacted to
        self.settled = set()
        self.last_comment_t = -1e9
        self.since_comment = 0
        self.last_delivered = None           # the newest stimulus id (a comment for an older one is stale)
        self.history = []                    # closed cards (last 6), for the comment's context
        self.pending_comment = None          # (stimulus id, future) while the model writes
        self.stats = {"reactions": 0, "comments": 0, "cancelled": 0, "dropped": 0, "model_calls": 0}

    def status(self):
        return {**self.voice.status(), "queue": len(self.queue), "playing": self.playing["id"] if self.playing else None}

    def reset(self):
        self.queue.clear()
        self.playing = None
        self.said.clear()
        self.settled.clear()
        self.pending_comment = None

    # --- deciding lines ---------------------------------------------------------------------------------------------
    def _line(self, kind, text, about, life, now, cls=None):
        self.n += 1
        item = {"id": f"s-{self.n}", "kind": kind, "text": text, "about": about, "t": now, "expires": now + life,
                "priority": PRIORITY[kind], "cls": cls}
        if kind == "reaction":                                    # one reaction per stimulus: the older one goes
            for q in [q for q in self.queue if q["kind"] == "reaction" and q["about"] == about]:
                self.queue.remove(q)
                self.stats["cancelled"] += 1
        self.queue.append(item)
        if len(self.queue) > MAX_QUEUE:                           # bounded: the oldest lowest-priority line goes
            victim = min(self.queue, key=lambda q: (q["priority"], q["t"]))
            self.queue.remove(victim)
            self.stats["dropped"] += 1
        return item

    def on_delivered(self, ev, now):
        self.last_delivered = ev.get("id")

    def on_trace(self, trace, now):
        """The open card as the bins come in: the reaction, upgraded while the response grows."""
        card = trace.get("card")
        if not card or not card.get("id"):
            return
        rid, cls = card["id"], classify(card)
        if card.get("baseline") and (card.get("peak_ratio") or 0) < CLASS_RATIO["small"]:
            t_ms = trace.get("t_ms", 0)
            if t_ms < card.get("t1_ms", 0):                       # the train is still on: too early to call it nothing
                return
        order = ("none", "small", "strong", "burst")
        prev = self.said.get(rid)
        if prev is None or order.index(cls) > order.index(prev):
            self.said[rid] = cls
            self._line("reaction", self.rng.choice(REACTIONS[cls]), rid, REACTION_LIFE_S, now, cls)
            self.stats["reactions"] += 1
        mr = card.get("min_ratio_after")
        if (mr is not None and mr < 0.6 and rid not in self.settled and trace.get("phase") in ("responding", "settling")
                and trace.get("t_ms", 0) >= card.get("t1_ms", 0) + 800):          # not on the heels of the reaction
            self.settled.add(rid)
            self._line("reaction", self.rng.choice(REACTIONS["settle"]), rid, REACTION_LIFE_S, now, "settle")

    def on_measured(self, card, now):
        self.history.append(card)
        del self.history[:-6]
        self.since_comment += 1
        if now - self.last_comment_t < COMMENT_EVERY_S or self.since_comment < COMMENT_EVERY_N:
            return
        self.last_comment_t, self.since_comment = now, 0
        self.stats["comments"] += 1
        cls = classify(card)
        rid = card.get("id")
        state = {"response": {k: card.get(k) for k in ("level", "peak_ratio", "peak_z", "onset_ms", "burst", "recruit",
                                                        "min_ratio_after", "recovered_ms", "distinguishable")},
                 "class": cls, "phase": "settling" if (card.get("recovered_ms") or 0) > 1000 else "reacting",
                 "recent": [{"level": c.get("level"), "peak_ratio": c.get("peak_ratio"), "burst": c.get("burst")}
                            for c in self.history[-5:-1]],
                 "note": "all numbers are measured on a simulated network against its own quiet baseline"}
        self.pending_comment = (rid, state, cls)

    def take_comment_job(self):
        """The hub calls this: -> (rid, system, user_json, cls) to run through `ask` off the loop, or None."""
        job, self.pending_comment = self.pending_comment, None
        if job is None:
            return None
        rid, state, cls = job
        return rid, SYSTEM_COMMENT, json.dumps(state), cls

    def finish_comment(self, rid, text, cls, now):
        """The model's answer (or None: a rule line). Dropped when another shock landed since."""
        if rid != self.last_delivered:
            self.stats["dropped"] += 1
            return
        if text:
            text = " ".join(str(text).strip().strip('"').split()[:COMMENT_WORDS])
            self.stats["model_calls"] += 1
        else:
            card = self.history[-1] if self.history else {}
            tpl = self.rng.choice(RULE_COMMENTS[cls])
            text = tpl.format(ratio=round(card.get("peak_ratio") or 0, 1), recruit=f"{int(100 * (card.get('recruit') or 0))}%")
        self._line("comment", text, rid, COMMENT_LIFE_S, now, cls)

    # --- playing ----------------------------------------------------------------------------------------------------
    def duration_ms(self, item):
        if item["kind"] == "reaction":
            return 700
        return 400 + 160 * len(item["text"].split())

    def tick(self, now):
        """-> the messages to broadcast now: say / say_cancel."""
        out = []
        live = [q for q in self.queue if q["expires"] > now]
        self.stats["dropped"] += len(self.queue) - len(live)              # a line older than its life is never said
        self.queue = live
        if self.playing and self.playing["until"] <= now:
            self.playing = None
        if not self.queue:
            return out
        self.queue.sort(key=lambda q: (-q["priority"], q["t"]))
        nxt = self.queue[0]
        if self.playing:
            if nxt["kind"] == "reaction" and self.playing["kind"] == "comment":       # interrupt the comment
                out.append({"type": "say_cancel", "id": self.playing["id"]})
                self.playing = None
                self.stats["cancelled"] += 1
            else:
                return out
        self.queue.pop(0)
        ms = self.duration_ms(nxt)
        self.playing = {"id": nxt["id"], "until": now + ms / 1000.0, "kind": nxt["kind"]}
        out.append({"type": "say", "id": nxt["id"], "kind": nxt["kind"], "text": nxt["text"], "ms": ms, "about": nxt["about"],
                    "cls": nxt["cls"], "voice": {"available": False, "url": None}})
        return out

    def voiced(self, msg, audio, now):
        """The hub rendered the line (off the loop): the audio and its true length go on the message and the clock."""
        if audio and audio.get("url"):
            msg["voice"] = {"available": True, "url": audio["url"]}
            if audio.get("ms"):
                msg["ms"] = int(audio["ms"])
                if self.playing and self.playing["id"] == msg["id"]:
                    self.playing["until"] = now + msg["ms"] / 1000.0
        return msg
