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


# Topic table (EN + IT keywords -> networks). Shown on the page next to RULES; the construct uses it to decide which
# districts a message lands on. "kw" entries ending in * are prefixes (mangi* = mangio, mangiare, mangiato...);
# "first" entries only count as the first word of the message. Drives are at gain 1, before the sleep-stage gain.
REGION_RULES = [
    {"topic": "food / bread", "networks": {"reward": 6.0, "limbic": 3.0},
     "kw": ["bread", "pane", "bakery", "baker", "forno", "panetteria", "food", "cibo", "eat", "eating", "mangi*",
            "hungry", "fame", "breakfast", "colazione", "lunch", "pranzo", "dinner", "cena", "pizza", "pasta",
            "cake", "torta", "dolce", "coffee", "caffe", "cornetto", "croissant", "cookie", "biscotti*"]},
    {"topic": "outside / park", "networks": {"limbic": 5.0, "memory": 4.0, "visual": 2.0},
     "kw": ["park", "parco", "outside", "fuori", "walk", "walking", "passeggi*", "garden", "giardino", "tree", "trees",
            "albero", "alberi", "sun", "sunny", "sole", "sunset", "tramonto", "air", "aria", "nature", "natura",
            "flowers", "fiori", "bench", "panchina"]},
    {"topic": "market / chart", "networks": {"salience": 6.0, "attention": 4.0},
     "kw": ["market", "mercato", "chart", "charts", "grafico", "candle", "candles", "candela", "candele", "price",
            "prezzo", "pump", "pumping", "dump", "dumping", "volume", "trade", "trades", "trading", "trader",
            "bull", "bear", "bullish", "bearish"]},
    {"topic": "phone / social", "networks": {"visual": 4.0, "default": 3.0, "attention": 2.0},
     "kw": ["phone", "telefono", "cellulare", "tiktok", "social", "scroll", "scrolling", "video", "videos",
            "instagram", "feed", "followers", "meme", "memes"]},
    {"topic": "greetings / people", "networks": {"default": 6.0, "language": 3.0},
     "kw": ["hello", "hi", "hey", "ciao", "salve", "buongiorno", "buonasera", "buonanotte", "goodnight", "gm", "gn",
            "morning", "evening", "friend", "friends", "amico", "amici", "everyone", "everybody", "tutti", "ragazzi",
            "people", "gente", "family", "famiglia", "welcome", "benvenuto"]},
    {"topic": "feelings", "networks": {"limbic": 6.0, "default": 3.0},
     "kw": ["feel", "feeling", "feelings", "senti", "sento", "sad", "triste", "happy", "felice", "lonely", "tired", "stanco", "stanca",
            "sleepy", "sonno", "calm", "calmo", "worried", "preoccupat*", "angry", "arrabbiat*", "emotion", "emozione", "emozioni", "mood", "anxious", "ansia",
            "love", "amore", "joy", "gioia", "fear", "paura", "scared", "afraid"]},
    {"topic": "questions", "networks": {"attention": 6.0, "control": 5.0}, "question": True,
     "first": ["who", "what", "why", "how", "when", "where", "which", "do", "does", "did", "are", "is", "can",
               "could", "will", "would", "should", "chi", "cosa", "perche", "come", "quando", "dove",
               "quale", "quali", "quanto", "quanti", "puoi", "sai"]},
]
REGION_RULE_ROWS = [[r["topic"] + " (" + ", ".join((r.get("kw") or r.get("first"))[:6]) + ", ...)",
                     list(r["networks"])] for r in REGION_RULES]
_TOKEN = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


def _fold(text):
    """Lower-case letters without accents (perche == perché), for the topic table."""
    return unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()


def _kw_hit(tokens, kws):
    for k in kws:
        if k.endswith("*"):
            p = k[:-1]
            if any(t.startswith(p) for t in tokens):
                return True
        elif k in tokens:
            return True
    return False


def topics(text):
    """[(topic, {group: drive})] for every REGION_RULES row the text matches."""
    toks = _TOKEN.findall(_fold(text))
    tokset = set(toks)
    out = []
    for r in REGION_RULES:
        hit = _kw_hit(tokset, r.get("kw", ()))
        if r.get("question") and ("?" in text or (toks and toks[0] in r["first"])):
            hit = True
        if hit:
            out.append((r["topic"], r["networks"]))
    return out


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
    for _, nets in topics(text):          # topic table: per network the strongest drive wins (never summed twice)
        for g, a in nets.items():
            stim[g] = max(stim.get(g, 0.0), a)
    emotion = "threat" if hos else "positive" if pos else "neutral"
    return stim, list(stim), emotion


def topical_networks(text):
    """Networks a message lands on for the construct: the topic-table and content rules, without the universal
    'every message' row (language + somatomotor) unless nothing else hit."""
    nets = list(stimulus(text)[0])
    base = set(RULES[0][1])
    return [g for g in nets if g not in base] or ["language"]


# --- nicknames -----------------------------------------------------------------------
NICK_MAX = 20
NICK_OK = re.compile(r"^[\w -]+$")


def check_nick(nick):
    """Optional nickname -> (ok, reason). Empty = anonymous (ok). <= 20 chars, letters / digits / space / _ -, and it
    must pass the same filter as messages; it cannot imitate SUB-01."""
    nick = (nick or "").strip() if isinstance(nick, str) else None
    if nick is None:
        return False, "nickname must be text"
    if not nick:
        return True, None
    if len(nick) > NICK_MAX:
        return False, f"nickname: max {NICK_MAX} characters"
    if not NICK_OK.match(nick):
        return False, "nickname: letters, digits, space, _ and - only"
    reason = blocked(nick)
    if reason:
        return False, "nickname: " + reason
    if re.search(r"sub\s*[-_]?\s*0?1|system|admin|moderator", nick, re.I):
        return False, "nickname: reserved"
    return True, None


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
