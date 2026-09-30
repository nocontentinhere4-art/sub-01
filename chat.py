"""Public chat for SUB-01: message filter, rate limit, duplicate check and the message -> stimulus rules.

Everything here is a transparent rule table; no external API and no language model.
The filter runs first: blocked messages are never shown, stored or turned into stimuli.
"""
import re
import time
import unicodedata
from collections import deque

MAX_LEN = 280
RATE_S = 10.0

# --- filter --------------------------------------------------------------------------
URL = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|net|org|io|xyz|fun|app|gg|co|me|ly|sol|to|ru|info|biz|link|"
                 r"site|online|club|finance|exchange|money|pro|tech|dev|ai)\b|t\.me/|discord\.gg)", re.I)
SOL_ADDR = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
ETH_ADDR = re.compile(r"\b0x[a-fA-F0-9]{8,}")
TICKER = re.compile(r"\$[A-Za-z][A-Za-z0-9]{1,11}\b")
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
PHONE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
MONEY = re.compile(r"\b(send|give|pay|tip|donate|lend|transfer|spare)\b.{0,20}\b(sol|eth|btc|usdc|usdt|crypto|money|"
                   r"cash|funds|coins?|tokens?|dollars?|bucks|euros?|\d+)\b|\$\s?\d|\d\s?(sol|usd|eur|€)\b|"
                   r"\b(donations?|donate|giveaway|airdrop|venmo|paypal|cash ?app|zelle|wallet|seed phrase|private key)\b",
                   re.I)
# small built-in list of slurs and insults (matched on a normalised, de-leeted copy of the text)
SLURS = ("nigger", "nigga", "faggot", "fag", "kike", "spic", "chink", "gook", "wetback", "tranny", "retard",
         "dyke", "cunt", "whore", "slut", "bitch", "bastard", "idiot", "moron", "imbecile", "stupid", "dumbass",
         "loser", "asshole", "dickhead", "motherfucker", "fuck you", "fuck off", "stfu", "kys", "kill yourself",
         "shut up", "piece of shit", "worthless", "pathetic", "ugly")
SLUR_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in SLURS) + r")(s|es|ed|ing|y|ic)?\b")
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})


def normalise(text):
    t = unicodedata.normalize("NFKC", text).lower().translate(LEET)
    t = re.sub(r"[^a-z\s]", "", t)
    return re.sub(r"(.)\1{2,}", r"\1\1", re.sub(r"\s+", " ", t)).strip()


def dedupe_key(text):
    return re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", text).lower())


def blocked(text):
    """Reason string if the message must be dropped, else None."""
    if URL.search(text):
        return "links are not allowed"
    if SOL_ADDR.search(text) or ETH_ADDR.search(text):
        return "addresses are not allowed"
    if TICKER.search(text):
        return "tickers are not allowed"
    if EMAIL.search(text) or PHONE.search(text):
        return "no personal data"
    if MONEY.search(text):
        return "no requests for money"
    if SLUR_RE.search(normalise(text)):
        return "insults are not allowed"
    return None


# --- message -> stimulus rule table ----------------------------------------------------
POSITIVE = {"love", "loved", "lovely", "happy", "glad", "good", "great", "nice", "beautiful", "wonderful", "amazing",
            "thanks", "thank", "joy", "calm", "peace", "hope", "sweet", "smile", "friend", "kind", "cute", "yay",
            "awesome", "cool", "best", "fun", "hug", "warm", "gm", "gn", "sleep well", "sweet dreams", "welcome"}
HOSTILE = {"hate", "kill", "die", "dead", "death", "attack", "threat", "danger", "dangerous", "hurt", "pain",
           "war", "gun", "blood", "angry", "rage", "destroy", "scared", "fear", "afraid", "scream", "fire",
           "crash", "dump", "rug", "rugged", "panic", "nightmare", "monster", "hunt", "fight"}
QUESTION_START = ("who", "what", "why", "how", "when", "where", "which", "do", "does", "did", "are", "is", "can",
                  "could", "will", "would", "should")
SELF = re.compile(r"\b(sub[\s-]?01|you|your|yours|you're|youre|yourself|u)\b", re.I)

RULES = [  # (condition, {group: drive at gain 1}) - shown on the page as "networks hit"
    ("every message", {"language": 6.0, "somatomotor": 3.0}),
    ("positive words", {"reward": 8.0}),
    ("hostile / threat words", {"fear": 8.0, "salience": 6.0}),
    ("question", {"attention": 6.0, "control": 5.0}),
    ("mentions SUB-01 / you", {"default": 6.0}),
]


def words(text):
    return set(re.findall(r"[a-z']+", text.lower()))


def stimulus(text):
    """-> ({group: drive}, [groups hit], emotion tag). Drives are before the sleep-stage gain."""
    w = words(text)
    low = " " + " ".join(re.findall(r"[a-z']+", text.lower())) + " "
    pos = bool(w & POSITIVE) or any(f" {p} " in low for p in POSITIVE if " " in p)
    hos = bool(w & HOSTILE)
    q = "?" in text or text.strip().lower().split(" ", 1)[0] in QUESTION_START
    fired = [True, pos, hos, q, bool(SELF.search(text))]
    stim = {}
    for on, (_, groups) in zip(fired, RULES):
        if on:
            for g, a in groups.items():
                stim[g] = stim.get(g, 0.0) + a
    emotion = "threat" if hos else "positive" if pos else "neutral"
    return stim, list(stim), emotion


# --- limits --------------------------------------------------------------------------
class RateLimiter:
    """1 message per RATE_S per client key. Keys (IPs) are forgotten as soon as the window passes."""

    def __init__(self, window=RATE_S, clock=time.monotonic):
        self.window, self.clock, self.last = window, clock, {}

    def allow(self, key):
        now = self.clock()
        self.last = {k: t for k, t in self.last.items() if now - t < self.window}   # purge old IPs
        if key in self.last:
            return False
        self.last[key] = now
        return True


class Dedupe:
    """Drops a message identical (after normalising) to one of the recent accepted ones."""

    def __init__(self, n=200):
        self.recent = deque(maxlen=n)

    def seen(self, text):
        k = dedupe_key(text)
        if k in self.recent:
            return True
        self.recent.append(k)
        return False


def check(text, key, limiter, dedupe):
    """Full pipeline for one incoming message -> (ok, reason). Filter first, then limits."""
    text = (text or "").strip()
    if not text:
        return False, "empty"
    reason = blocked(text)
    if reason:
        return False, reason
    if len(text) > MAX_LEN:
        return False, f"max {MAX_LEN} characters"
    if not limiter.allow(key):
        return False, f"one message every {RATE_S:.0f} s"
    if dedupe.seen(text):
        return False, "duplicate"
    return True, None
