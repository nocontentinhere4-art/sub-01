"""What is really on his screens (#89), and the simulated dopamine-like bursts when something new plays.

ScreensStatus keeps an honest, always-visible summary for /brain and /life (GET /api/screens):
- the browser: up, down (and why, since when) or off (no playwright / BROWSE=0);
- the last 10 pages, each with its kind and host;
- today's share by kind (Tokyo day): tiktok, shorts (YouTube Shorts), youtube, news, forum, finance, wikipedia,
  search (results pages), other;
- notes from the feed, e.g. "TikTok blocked from the server today → YouTube Shorts".

DopamineBursts: when a new short starts, a phasic dopamine-like burst whose size is a reward-prediction error,
    rpe = novelty + predicted interest - expectation,
- novelty: 1 for a topic not seen in the last NOVEL_S, else 0.3;
- predicted interest: his tastes' prediction for the title's words (tastes.py, -1..1) mapped to 0..1;
- expectation: a running mean of (novelty + interest) over recent clips (a Rescorla-Wagner value);
habituating over a scroll session (clips less than SESSION_GAP_S apart): x 1 / (1 + HABITUATION x (n - 1)), the
"doomscrolling" curve. Other videos give half the burst, pages a quarter; nothing new playing gives nothing. It is a
simulated dopamine-like reward signal in the model (it drives the reward regions and the DA level), not a feeling.
"""
import math
import re
import time
import urllib.parse

from readings import kind_of

KINDS = ("tiktok", "shorts", "youtube", "news", "forum", "finance", "wikipedia", "search", "other")
LAST_N = 10
NOVEL_S = 30 * 60
SESSION_GAP_S = 5 * 60
HABITUATION = 0.12
ALPHA = 0.15
SCALE = {"tiktok": 1.0, "shorts": 1.0, "youtube": 0.5, "video": 0.5}
PAGE_SCALE = 0.25
DA_LABEL = "simulated dopamine-like reward signal in the model"


def screen_kind(st):
    """One of KINDS for a screen status (None for a restarting browser or an empty status)."""
    st = st or {}
    if st.get("restarting") or not st.get("url"):
        return None
    if st.get("kind") == "search":
        return "search"
    url = str(st.get("url"))
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    k = kind_of(st)
    if k == "short":
        return "tiktok" if host.endswith("tiktok.com") else "shorts"
    if k == "video":
        return "youtube" if re.search(r"(^|\.)(youtube\.com|youtu\.be)$", host) else "other"
    if k == "wiki":
        return "wikipedia"
    if k in ("news", "forum", "finance"):
        return k
    return "other" if k else None


def tokyo_day(t):
    from search_sources import tokyo_day as d
    return d(t)


def hhmm(t):
    from datetime import datetime
    try:
        from sleep import TZ
    except Exception:                                       # pragma: no cover
        from zoneinfo import ZoneInfo
        TZ = ZoneInfo("Asia/Tokyo")
    return datetime.fromtimestamp(t, TZ).strftime("%H:%M")


class ScreensStatus:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.state, self.why, self.since = "starting", "", clock()
        self.last = []                       # [{t, kind, host, title, device}]
        self.day, self.counts = None, {}
        self.url = {}                        # device -> url shown last (a page counts once)
        self.notes = []                      # [{t, text}]
        self.restarts = 0

    def _roll(self):
        d = tokyo_day(self.clock())
        if d != self.day:
            self.day, self.counts, self.notes = d, {}, []

    def set_off(self, why):
        self.state, self.why, self.since = "off", why, self.clock()

    def browser_down(self, why):
        if self.state != "down":
            self.state, self.why, self.since = "down", str(why)[:120], self.clock()
            self.restarts += 1
            return True                      # first report of this outage (log it once)
        return False

    def browser_up(self):
        if self.state != "up":
            self.state, self.why, self.since = "up", "", self.clock()

    def note(self, text):
        self._roll()
        text = str(text)[:140]
        if not self.notes or self.notes[-1]["text"] != text:
            self.notes = (self.notes + [{"t": self.clock(), "text": text}])[-5:]

    def seen(self, st):
        """A screen status: the browser is up; a new page is counted once. Returns its kind when it is new."""
        st = st or {}
        if st.get("restarting"):
            self.browser_down("restarting")
            return None
        self.browser_up()
        kind = screen_kind(st)
        dev = st.get("device") or "desk"
        if kind is None or self.url.get(dev) == st.get("url"):
            return None
        self.url[dev] = st.get("url")
        self._roll()
        self.counts[kind] = self.counts.get(kind, 0) + 1
        host = (urllib.parse.urlsplit(str(st.get("url"))).hostname or "").removeprefix("www.")
        self.last = (self.last + [{"t": self.clock(), "kind": kind, "host": host, "device": dev,
                                   "title": str(st.get("title") or host)[:90]}])[-LAST_N:]
        return kind

    def public(self, display_ok=None):
        self._roll()
        total = sum(self.counts.values())
        ok = display_ok or (lambda s: True)
        return {"browser": {"state": self.state, "why": self.why, "since": hhmm(self.since), "restarts": self.restarts},
                "last": [dict(x, t=hhmm(x["t"]), title=x["title"] if ok(x["title"]) else x["host"])
                         for x in reversed(self.last)],
                "today": {"tokyo_day": self.day, "total": total, "counts": dict(self.counts),
                          "share": {k: round(self.counts.get(k, 0) / total, 3) for k in KINDS} if total else {}},
                "notes": [dict(n, t=hhmm(n["t"])) for n in self.notes]}


class DopamineBursts:
    """Phasic dopamine-like bursts when something new plays (see the module docstring)."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.expect = 0.6
        self.n, self.last_t = 0, None
        self.topics = {}                     # topic -> last time seen
        self.trace = []                      # [{t, size, ...}] newest last

    def on_new(self, kind, topic, interest=0.0):
        """A new clip / page started. kind: screens kind; topic: its topic (str or None); interest: tastes'
        prediction (-1..1). Returns the burst (size >= 0) or None for nothing new."""
        if kind is None or kind == "search":
            return None
        t = self.clock()
        novelty = 0.3 if topic and t - self.topics.get(topic, -1e18) < NOVEL_S else 1.0
        if topic:
            self.topics[topic] = t
            if len(self.topics) > 500:
                self.topics.pop(next(iter(self.topics)))
        try:
            v = float(interest)
        except (TypeError, ValueError):
            v = 0.0
        v = (max(-1.0, min(1.0, v)) + 1) / 2 if math.isfinite(v) else 0.5
        rpe = novelty + v - self.expect
        self.expect += ALPHA * (novelty + v - self.expect)
        short = kind in ("tiktok", "shorts")
        if short:
            self.n = self.n + 1 if self.last_t is not None and t - self.last_t < SESSION_GAP_S else 1
            self.last_t = t
        hab = 1.0 / (1.0 + HABITUATION * (self.n - 1)) if short else 1.0
        size = round(max(0.0, rpe) * hab * SCALE.get(kind, PAGE_SCALE), 4)
        b = {"t": t, "size": size, "rpe": round(rpe, 3), "novelty": novelty, "interest": round(v, 3),
             "expect": round(self.expect, 3), "n": self.n if short else 0, "habituation": round(hab, 3), "kind": kind,
             "label": ("new short" if short else "new video" if kind == "youtube" else "new page")
                      + " — novelty + predicted interest"}
        self.trace = (self.trace + [b])[-120:]
        return b
