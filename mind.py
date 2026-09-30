"""SUB-01's workspace: an architecture inspired by theories of consciousness (Global Workspace).

It is a model of brain activity, not a mind. Every cycle (~2 s real) a handful of candidates compete for one
shared "workspace": needs (hunger, boredom, sleep pressure), recent chat messages, stored memories, market
events, perceptions of the world and, during REM, dream replays. Salience is a transparent formula:

    salience = kind weight x NET_W x sum(brain rel activity of the candidate's networks)
             + need level / novelty / recency terms
             - inhibition of return (a recent winner is suppressed for ~30 s, repeated winners habituate)
             + small noise (seeded rng, so a run is reproducible)

Sleep gates the competition (asleep: only dreams and memories may win; NREM is mostly silence) and nothing wins
below the ignition threshold. The winner is broadcast: it proposes an action (the server asks
`life.request(act, t, reason)` and passes the answer back through `outcome()`), produces a short rule-based
inner-speech line (optionally rephrased by a language model off the event loop, always checked by `safe_text`),
flags memory encoding and gives the eye a focus text. A small self-model (doing / feeling / wanting / recent
history) and a diary (data/diary/YYYY-MM-DD.json) give continuity across days.

Nothing here claims or implies that SUB-01 is conscious, alive, sentient or a person, and nothing speaks as or
about the real person whose public scans were used.
"""
import hashlib
import json
import math
import random
import re
import time
from pathlib import Path

from chat import blocked
from life import DESIRES
from sleep import hhmm, local, stamp

# ---- tunables (all transparent) -----------------------------------------------------------------------
KIND_W = {"chat": 1.0, "need": 0.5, "memory": 0.35, "market": 0.6, "perception": 0.4, "dream": 0.8}
NET_W = 0.25                 # weight of one network's rel activity
CHAT_TAU_S = 45.0            # chat novelty decay (real seconds)
CHAT_TTL_S = 150.0           # a message leaves the competition after this
IOR_S = 30.0                 # inhibition of return window (real seconds)
IOR_STRENGTH = 1.5
HABITUATION = 0.6            # salience x 0.6^wins for chat/memory/dream/perception candidates
NOISE = 0.04
THRESHOLD = {"AWAKE": 0.35, "REM": 0.45, "NREM": 0.8}
SLEEP_MULT = {"NREM": 0.35, "REM": 1.0}          # dreams/memories while asleep
DREAM_REM_BOOST = 1.5
NEED_HI, NEED_LO = 0.7, 0.6                       # threshold crossing with hysteresis
SPEECH_MIN_S = 20.0          # ordinary (not "worth showing") lines at most this often
ACTION_COOLDOWN_S = {True: 60.0, False: 120.0}    # after accept / decline, don't re-propose the same act
ACTION_GAP_S = 45.0          # after any outcome, needs / market / perceptions wait this long before proposing
NEED_ACT = 0.5               # a need proposes an action only from this level
LLM_MIN_GAP_S = 30.0
LLM_PER_HOUR = 60
LLM_WAIT_S = 10.0            # hold the rule line this long waiting for the language model
HISTORY = 10
DIARY_CAP = 400              # entries per day
FLUSH_S = 60.0
MAX_CHARS = 120

NEED_NETS = {"hunger": ["reward", "limbic"], "boredom": ["default", "reward"], "sleep": ["default", "relay"]}
MARKET = {"pumping": (["salience", "reward", "attention"], 0.45, "the chart is climbing"),
          "dumping": (["salience", "fear", "attention"], 0.5, "the chart is sliding"),
          "choppy": (["salience", "attention"], 0.2, "the chart can't decide")}
PLACE_LABEL = {"bed": "the bed", "window": "the street outside the window", "table": "the table",
               "desk": "the desk and the chart", "door_in": "the front door", "door_out": "the front door",
               "street_home": "the street", "street_bakery": "the street by the bakery",
               "bakery_door": "the bakery door", "bakery_in": "the bakery", "counter": "the bakery counter",
               "street_park": "the street by the park", "park_gate": "the park gate", "bench": "the park"}
PLACE_KEY = {"bed": "bed", "window": "window", "table": "table", "desk": "desk", "counter": "bakery",
             "bakery_in": "bakery", "bakery_door": "bakery", "bench": "park", "park_gate": "park"}

# ---- safety ----------------------------------------------------------------------------------------------
CLAIM_RE = re.compile(
    r"\b(conscious\w*|sentien\w*|self[- ]?aware\w*|alive|sapient\w*|"
    r"i\s*(?:am|'m|’m)\s+(?:a\s+|an\s+)?(?:real\s+|living\s+)?(?:person|human|living|being|someone|people)|"
    r"human\s+being|(?:have|got)\s+(?:a\s+)?(?:soul|feelings|emotions)|my\s+soul|"
    r"coscien\w*|consapevol\w*|senzien\w*|viv[oa]|vivente|"
    r"sono\s+(?:una\s+|un\s+)?(?:persona|umano|umana|essere\s+umano|reale)|essere\s+umano|anima)\b", re.I)
MONEY_RE = re.compile(
    r"\b(buy\w*|bought|sell\w*|sold|invest\w*|money|cash|profit\w*|gains?|earn\w*|rich|wealth\w*|moon\w*|lambo|"
    r"\d+x|guarantee\w*|promis\w*|financ\w*|price\s+(?:will|is\s+going|goes|going|to)|tokens?|coins?|crypto\w*|"
    r"wallet|usd|dollars?|euros?|"
    r"compr(?:a|o|i|are|ate|ato|iamo|ando)|vend(?:i|o|e|ere|ete|uto|iamo|ita)|investi\w*|soldi|denar\w*|"
    r"guadagn\w*|profitt\w*|ricc[oaih]\w*|garant\w*|promett\w*|promess\w*|"
    r"prezzo\s+(?:salir|scender|andr|arriv|vol)\w*)\b", re.I)
PERSON_RE = re.compile(
    r"\b(mri|fmri|scans?|scanned|scanner|scansion\w*|risonanz\w*|donor\w*|donat(?:ore|rice)|volunteer\w*|"
    r"volontari\w*|real\s+person|persona\s+reale|(?:the|that)\s+person\s+(?:whose|who|behind)|"
    r"la\s+persona\s+(?:da|di|che|dietro)|whose\s+brain|his\s+brain|her\s+brain|il\s+suo\s+cervello|"
    r"my\s+(?:mother|father|mom|mum|dad|childhood|wife|husband|family|parents|brother|sister|kids?|children|job)|"
    r"(?:mia|mio|miei|mie)\s+(?:madre|padre|mamma|papà|infanzia|moglie|marito|famiglia|genitori|fratell\w*|"
    r"sorell\w*|figli\w*|lavoro)|when\s+i\s+was\s+(?:a\s+)?(?:kid|child|young|little|boy|girl)|"
    r"quando\s+ero\s+(?:piccol|bambin|giovan|ragazz)\w*|mi\s+chiamo|my\s+name)\b", re.I)


def safe_text(s):
    """True if a generated line may be shown: passes the chat filter, makes no claim of being conscious /
    alive / sentient / a person, says nothing about buying, selling, money or promises, does not refer to the
    real person behind the scans, and is one line of at most MAX_CHARS characters."""
    if not isinstance(s, str):
        return False
    s2 = s.strip()
    if not s2 or len(s2) > MAX_CHARS or "\n" in s2:
        return False
    if blocked(s2):
        return False
    return not (CLAIM_RE.search(s2) or MONEY_RE.search(s2) or PERSON_RE.search(s2))


# ---- language ----------------------------------------------------------------------------------------------
IT_WORDS = {"il", "lo", "la", "gli", "le", "un", "una", "che", "non", "di", "da", "per", "con", "sei", "sono",
            "ciao", "vai", "pane", "compra", "mangia", "come", "stai", "cosa", "perché", "perche", "dove", "anche",
            "molto", "grazie", "buongiorno", "buonanotte", "dormi", "ti", "mi", "ma", "si", "del", "della", "al",
            "alla", "questo", "quello", "fuori", "parco", "grafico", "finestra", "telefono", "ho", "hai", "fame",
            "andiamo", "dai", "bello", "bella", "oggi", "domani", "adesso", "ora", "tu", "io", "fai", "prendi",
            "forno", "guarda", "candele", "prezzo", "sempre", "notte", "giorno", "sogni", "anch", "ancora"}
EN_WORDS = {"the", "a", "an", "is", "are", "you", "go", "get", "and", "to", "of", "what", "how", "i", "it",
            "bread", "buy", "eat", "hello", "hi", "hey", "your", "do", "does", "this", "that", "some", "now",
            "please", "look", "good", "morning", "night", "chart", "window", "phone", "park"}


def lang_of(text):
    w = re.findall(r"[a-zàèéìòù']+", (text or "").lower())
    it = sum(x in IT_WORDS for x in w) + len(re.findall(r"[àèéìòù]", (text or "").lower()))
    en = sum(x in EN_WORDS for x in w)
    return "it" if it > en and it >= 1 else "en"


# ---- rule-based inner speech -------------------------------------------------------------------------------
TPL = {
    "chat_buy_bread": {"en": ["bread... yes, I should get some", "someone said bread. now I want bread"],
                       "it": ["ah, devo prendere il pane", "pane... sì, ci vorrebbe"]},
    "chat_eat": {"en": ["bread talk. there's some at home", "right, a bite of bread"],
                 "it": ["pane... ne ho un po' a casa", "giusto, un pezzo di pane"]},
    "chat_phone": {"en": ["the phone, just for a minute", "a little scroll wouldn't hurt"],
                   "it": ["il telefono, solo un attimo", "una scrollata non fa male"]},
    "chat_park": {"en": ["some air at the park, why not", "the park sounds good"],
                  "it": ["un po' d'aria al parco, perché no", "il parco, bella idea"]},
    "chat_chart": {"en": ["that chart again...", "everyone talks about the chart"],
                   "it": ["di nuovo quel grafico...", "tutti parlano del grafico"]},
    "chat_window": {"en": ["let me look outside", "a look at the street"],
                    "it": ["guardo fuori un attimo", "un'occhiata alla strada"]},
    "chat_threat": {"en": ["that one made me tense", "hm, that sounded harsh"],
                    "it": ["questo mi ha messo in allerta", "mh, suonava duro"]},
    "chat_positive": {"en": ["that was nice to read", "kind words, {nick}"],
                      "it": ["che bello leggerlo", "parole gentili, {nick}"]},
    "chat_question": {"en": ["a question... let me think", "hm, good question, {nick}"],
                      "it": ["una domanda... ci penso", "mh, bella domanda, {nick}"]},
    "chat_neutral": {"en": ["a new message", "{nick} wrote something"],
                     "it": ["un messaggio nuovo", "{nick} ha scritto qualcosa"]},
    "need_hunger": {"en": ["I'm getting hungry", "time to eat something"],
                    "it": ["ho fame", "ci vorrebbe qualcosa da mangiare"]},
    "need_boredom": {"en": ["this is getting boring", "I need something to do"],
                     "it": ["che noia", "devo fare qualcosa"]},
    "need_sleep": {"en": ["getting sleepy", "bed soon, I think"],
                   "it": ["ho sonno", "tra poco a letto"]},
    "market_pumping": {"en": ["green candles again", "the chart's climbing"],
                       "it": ["candele verdi di nuovo", "il grafico sale"]},
    "market_dumping": {"en": ["red candles everywhere", "the chart's sliding"],
                       "it": ["candele rosse ovunque", "il grafico scende"]},
    "market_choppy": {"en": ["that chart again...", "the chart can't decide"],
                      "it": ["di nuovo quel grafico...", "il grafico non si decide"]},
    "perc_bed": {"en": ["back in bed"], "it": ["di nuovo a letto"]},
    "perc_window": {"en": ["the street is quiet"], "it": ["la strada è tranquilla"]},
    "perc_table": {"en": ["at the table"], "it": ["al tavolo"]},
    "perc_desk": {"en": ["back at the desk"], "it": ["di nuovo alla scrivania"]},
    "perc_bakery": {"en": ["smells like fresh bread in here"], "it": ["che profumo di forno"]},
    "perc_park": {"en": ["the park is calm"], "it": ["il parco è tranquillo"]},
    "perc_street": {"en": ["out on the street"], "it": ["fuori per strada"]},
    "perc_baker": {"en": ["the baker is at the counter"], "it": ["il fornaio è al bancone"]},
    "perc_open": {"en": ["the bakery is open"], "it": ["il forno è aperto"]},
    "perc_closed": {"en": ["the bakery is closed now"], "it": ["il forno adesso è chiuso"]},
    "time_dawn": {"en": ["first light outside"], "it": ["fuori comincia a fare chiaro"]},
    "time_morning": {"en": ["morning already"], "it": ["è già mattina"]},
    "time_afternoon": {"en": ["afternoon light"], "it": ["luce del pomeriggio"]},
    "time_evening": {"en": ["evening is coming"], "it": ["sta arrivando la sera"]},
    "time_night": {"en": ["it's dark out"], "it": ["fuori è buio"]},
    "dream": {"en": ["dreaming of \"{snip}\"", "everything melts into \"{snip}\""],
              "it": ["sogno \"{snip}\"", "tutto si scioglie in \"{snip}\""]},
    "dream_plain": {"en": ["a strange dream"], "it": ["un sogno strano"]},
    "memory": {"en": ["I keep thinking about \"{snip}\"", "\"{snip}\" comes back to me"],
               "it": ["mi torna in mente \"{snip}\"", "ripenso a \"{snip}\""]},
    "memory_plain": {"en": ["an old message comes back"], "it": ["mi torna in mente un vecchio messaggio"]},
    "ok_buy_bread": {"en": ["off to the bakery", "ok, bread it is"],
                     "it": ["ah, devo prendere il pane", "vado al forno"]},
    "ok_eat": {"en": ["some bread first", "a bit of bread, then"], "it": ["un po' di pane, subito", "mangio un po' di pane"]},
    "ok_phone": {"en": ["just a quick scroll"], "it": ["solo una scrollata veloce"]},
    "ok_park": {"en": ["going out for some air"], "it": ["esco a prendere un po' d'aria"]},
    "ok_chart": {"en": ["let me check the chart"], "it": ["do un'occhiata al grafico"]},
    "ok_window": {"en": ["a look out of the window"], "it": ["un'occhiata fuori dalla finestra"]},
    "ok_other": {"en": ["ok, let's do that"], "it": ["ok, facciamolo"]},
    "no_closed": {"en": ["the bakery's closed, tomorrow morning then"], "it": ["il forno è chiuso, ci vado domattina"]},
    "no_dark": {"en": ["too dark for the park now"], "it": ["è buio, il parco domani"]},
    "no_has_bread": {"en": ["I already have bread at home"], "it": ["ho già il pane a casa"]},
    "no_full": {"en": ["not hungry right now"], "it": ["non ho fame adesso"]},
    "no_tired": {"en": ["too tired for that now"], "it": ["troppo stanco, adesso no"]},
    "no_asleep": {"en": ["not now... sleeping"], "it": ["adesso no... dormo"]},
    "no_busy": {"en": ["after this, maybe"], "it": ["dopo, forse"]},
    "no_other": {"en": ["not now: {why}"], "it": ["non ora: {why}"]},
    "no_plain": {"en": ["not now"], "it": ["non ora"]},
}

DECLINE = [  # (pattern on the reason life.request passed back, template)
    (r"clos|chius|opens|apre", "no_closed"),
    (r"dark|night|buio|notte", "no_dark"),
    (r"(already|has|have|got)\b.*bread|pane", "no_has_bread"),
    (r"not hungry|full|sazi|fame", "no_full"),
    (r"tired|energy|stanc|sonno", "no_tired"),
    (r"asleep|sleep|dorm", "no_asleep"),
    (r"busy|walking|already doing|in progress|occupat|cammina", "no_busy"),
]

LLM_SYSTEM = """You write one short inner-speech line for SUB-01, a simulated character driven by a model of brain
activity (it is not a mind and not a person). You receive the current state as JSON.
Reply with the line only: first person, at most 100 characters, in the language given by "lang"
(it = Italian, en = English), about "about", consistent with "action" (if the action was declined, mention why).
Rules: never mention money, prices, buying, selling, investing, tokens or coins; never make promises or
predictions; never say or imply that you are conscious, alive, sentient, human or a person; never mention scans,
MRI or any real person, and never invent memories of a past life or family; no names except the given nickname;
no quotes, emojis or hashtags."""


def _snip(text, n=30):
    text = re.sub(r"\s+", " ", (text or "").strip())
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _h(text):
    return hashlib.sha1((text or "").encode()).hexdigest()[:8]


def _clamp(x):
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def _phase(h):
    return ("night" if h < 6 else "dawn" if h < 8 else "morning" if h < 12 else "afternoon" if h < 18
            else "evening" if h < 21 else "night")


def _date_str(date):
    return date if isinstance(date, str) else date.isoformat()


class DiaryStore:
    """data/diary/YYYY-MM-DD.json: one list of entries per day (times, workspace winners, lines, actions; only
    public chat nicknames, no other personal data)."""

    def __init__(self, root):
        self.dir = Path(root) / "diary"
        self.dir.mkdir(parents=True, exist_ok=True)

    def load(self, date):
        f = self.dir / f"{_date_str(date)}.json"
        if not f.exists():
            return []
        try:
            d = json.loads(f.read_text())
        except (ValueError, OSError):
            return []
        return d.get("entries", []) if isinstance(d, dict) else list(d)

    def save(self, date, entries):
        f = self.dir / f"{_date_str(date)}.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"date": _date_str(date), "entries": entries}, indent=1, ensure_ascii=False))
        tmp.replace(f)

    def dates(self):
        return sorted(p.stem for p in self.dir.glob("????-??-??.json"))


class Mind:
    def __init__(self, state=None, rng=None, llm=None, clock_fn=None, store=None):
        s = state or {}
        self.rng = rng or random.Random()
        self.llm = llm                                   # llm(system, user) -> str, called only via run_llm()
        self.clock = clock_fn or time.monotonic          # real seconds: decay, inhibition, rate limits
        self.store = store
        self.n = s.get("cycle", 0)
        self.nmsg = s.get("nmsg", 0)
        self.lang = s.get("lang", "en")
        self.history = list(s.get("history", []))[-HISTORY:]
        self._diary = {k: list(v) for k, v in s.get("diary", {}).items()}
        self.yesterday = s.get("yesterday")
        self.msgs = []                                   # recent heard messages (<= 20)
        self.won = {}                                    # candidate id -> [real t of last win, wins]
        self.seen = {}                                   # perception key -> [value, real t changed]
        self.need_hi = {}                                # need -> above threshold
        self.need_news = {}                              # need -> crossed, not yet announced
        self.cooldown = {}                               # act -> real t until which it is not re-proposed
        self.next_proposal = -1e9                        # real t from which non-chat winners may propose again
        self.llm_times = []                              # real t of issued language-model requests
        self.pending = None                              # inner-speech line waiting for the server
        self.last_speech = (-1e9, "")
        self.last = None                                 # last broadcast
        self.last_r = -1e9
        self.self_model = {"doing": "", "feeling": "calm", "wanting": "nothing in particular",
                           "stage": "AWAKE", "history": self.history, "yesterday": self.yesterday}
        self.today = None
        self.dirty = set()
        self.last_flush = self.clock()
        self._req = 0
        if store is not None:
            for d in store.dates()[-2:]:
                if d not in self._diary:
                    self._diary[d] = store.load(d)

    # ---- inputs -------------------------------------------------------------------------------------------
    def hear(self, msg, t):
        """An accepted (already filtered) chat message -> its candidate id."""
        self.nmsg += 1
        cid = f"chat:{self.nmsg}"
        text = (msg.get("text") or "").strip()
        desire = next((act for pat, act in DESIRES if re.search(pat, text.lower())), None)
        nets = list(msg.get("networks") or ["language", "somatomotor"])
        self.msgs.append({"id": cid, "text": text, "nick": (msg.get("nick") or "").strip()[:20], "nets": nets,
                          "regions": list(msg.get("regions") or []), "emotion": msg.get("emotion", "neutral"),
                          "t": t, "r": self.clock(), "lang": lang_of(text), "desire": desire,
                          "question": "?" in text or "attention" in nets})
        del self.msgs[:-20]
        self.lang = self.msgs[-1]["lang"]
        return cid

    # ---- candidates ----------------------------------------------------------------------------------------
    def _novel(self, key, value, now, amount, tau):
        v = self.seen.get(key)
        if v is None or v[0] != value:
            self.seen[key] = v = [value, now if v is not None else now - 3 * tau]   # first sight: no burst
        return amount * math.exp(-(now - v[1]) / tau)

    def _candidates(self, t, ctx, now, stage):
        rel = ctx.get("rel") or {}
        needs = ctx.get("needs") or {}
        life = ctx.get("life") or {}
        out = []

        def add(cid, kind, label, source, nets, extra, content=None, habituate=True, scale=1.0):
            out.append({"id": cid, "kind": kind, "label": label, "source": source, "nets": nets,
                        "extra": extra, "content": content or {}, "habituate": habituate, "scale": scale})

        # needs
        lv = self._needs(needs, life)
        for name, level in lv.items():
            if level >= NEED_HI and not self.need_hi.get(name):
                self.need_hi[name] = True
                self.need_news[name] = True
            elif level < NEED_LO:
                self.need_hi[name] = False
                self.need_news.pop(name, None)
            label = {"hunger": "hungry", "boredom": "bored", "sleep": "sleepy"}[name]
            add(f"need:{name}", "need", f"{label} ({level:.0%})", "needs", NEED_NETS[name],
                1.4 * level * level + (0.3 if level >= NEED_HI else 0.0), {"need": name, "level": level}, False,
                min(1.0, 0.3 + level))                   # a low need barely uses the networks
        # chat
        self.msgs = [m for m in self.msgs if now - m["r"] < CHAT_TTL_S]
        for m in self.msgs:
            nov = math.exp(-(now - m["r"]) / CHAT_TAU_S)
            emo = {"threat": 0.15, "positive": 0.1}.get(m["emotion"], 0.0)
            label = f"“{_snip(m['text'], 36)}”" + (f" ({m['nick']})" if m["nick"] else "")
            add(m["id"], "chat", label, "chat:" + (m["nick"] or "anon"), m["nets"], nov + emo, {"msg": m})
        # memories (weighted like sleep.Memory: recency over a day x emotional tag)
        mems = ctx.get("memories") or []
        if mems:
            emo_w = {"threat": 3.0, "positive": 2.5, "neutral": 1.0}
            scored = []
            for m in mems[-200:]:
                mt = m.get("t", t)
                if mt > t:
                    continue
                w = math.exp(-max(0.0, t - mt) / 86400) * emo_w.get(m.get("emotion"), 1.0)
                scored.append((w, mt, m))
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            for w, mt, m in scored[:3]:
                add(f"mem:{int(mt)}:{_h(m.get('text'))}", "memory", f"memory: “{_snip(m.get('text'), 30)}”",
                    "memory", list(m.get("networks") or []) + ["memory"], 0.2 * min(w, 4.0), {"mem": m})
        # market
        mk = ctx.get("market") or "calm"
        if mk in MARKET:
            nets, base, label = MARKET[mk]
            add(f"market:{mk}", "market", label, "market", nets, base + self._novel("market", mk, now, 0.4, 30),
                {"market": mk}, False)
        else:
            self._novel("market", mk, now, 0.0, 30)
        # perceptions of the world
        h = local(t).hour + local(t).minute / 60
        place = life.get("place") or "bed"
        walking = bool(life.get("walking"))
        pkey = "street" if walking else PLACE_KEY.get(place, "street")
        plabel = "the street" if walking else PLACE_LABEL.get(place, place)
        add(f"perc:place:{pkey}", "perception", plabel, "world", ["visual", "attention"],
            self._novel("place", pkey, now, 0.6, 20), {"perc": pkey})
        ph = _phase(h)
        add(f"perc:time:{ph}", "perception", f"{ph} light" if ph != "night" else "dark outside", "world",
            ["visual"], 0.05 + self._novel("phase", ph, now, 0.8, 30), {"perc": "time", "phase": ph})
        baker = ((life.get("npc") or {}).get("baker") or {})
        if baker.get("present") and place in ("counter", "bakery_in", "bakery_door", "street_bakery"):
            add("perc:baker", "perception", "the baker at the counter", "world", ["visual", "attention", "language"],
                self._novel("baker", True, now, 0.5, 20), {"perc": "baker"})
        else:
            self._novel("baker", False, now, 0.0, 20)
        is_open = self._bakery_open(life, h)
        if lv.get("hunger", 0) > 0.5 and not life.get("bread"):
            add(f"perc:bakery:{'open' if is_open else 'closed'}", "perception",
                "bakery open" if is_open else "bakery closed", "world", ["visual", "reward"],
                self._novel("bakery", is_open, now, 0.5, 30), {"perc": "open" if is_open else "closed"})
        # dreams (REM replays)
        if stage != "AWAKE":
            for txt in list(dict.fromkeys(ctx.get("replays") or []))[-3:]:
                did = f"dream:{_h(txt)}"
                add(did, "dream", f"dream: “{_snip(txt, 30)}”", "dream", ["memory", "limbic", "visual"],
                    0.6 + (0.6 if did not in self.won else 0.0), {"text": txt})     # a new replay is novel
        return out, lv, is_open, h

    @staticmethod
    def _needs(needs, life):
        hunger = needs.get("hunger", life.get("hunger", 0.0))
        boredom = needs.get("boredom", life.get("boredom", 0.0))
        sl = next((needs[k] for k in ("sleep", "pressure", "tired") if k in needs), None)
        if sl is None:
            e = needs.get("energy", life.get("energy"))
            sl = 1.0 - _clamp(e) if e is not None else 0.0
        return {"hunger": _clamp(hunger), "boredom": _clamp(boredom), "sleep": _clamp(sl)}

    @staticmethod
    def _bakery_open(life, h):
        o = life.get("open")
        if isinstance(o, dict) and "bakery" in o:
            return bool(o["bakery"])
        if isinstance(o, bool):
            return o
        return 7 <= h < 20

    def _salience(self, c, rel, now, stage):
        net = NET_W * sum(max(0.0, float(rel.get(g, 1.0))) for g in c["nets"])
        s = KIND_W[c["kind"]] * net * c["scale"] + c["extra"]
        if stage != "AWAKE" and c["kind"] in ("dream", "memory"):
            s *= SLEEP_MULT.get(stage, 1.0) * (DREAM_REM_BOOST if stage == "REM" and c["kind"] == "dream" else 1.0)
        elif stage == "AWAKE" and c["kind"] == "memory":
            s *= 0.5
        w = self.won.get(c["id"])
        if w:
            s -= IOR_STRENGTH * max(0.0, 1.0 - (now - w[0]) / IOR_S)
            if c["habituate"]:
                s *= HABITUATION ** w[1]
        s += self.rng.gauss(0.0, NOISE)
        return max(0.0, s)

    # ---- the cycle ---------------------------------------------------------------------------------------------
    def cycle(self, t, ctx):
        now = self.clock()
        self.n += 1
        stage = ctx.get("stage") or "AWAKE"
        rel = ctx.get("rel") or {}
        life = ctx.get("life") or {}
        cands, lv, is_open, h = self._candidates(t, ctx, now, stage)
        for c in cands:
            c["salience"] = self._salience(c, rel, now, stage)
            c["gated"] = stage != "AWAKE" and c["kind"] not in ("dream", "memory")
        cands.sort(key=lambda c: c["salience"], reverse=True)
        open_ = [c for c in cands if not c["gated"]]
        win = open_[0] if open_ and open_[0]["salience"] >= THRESHOLD.get(stage, 0.35) else None
        broadcast = None
        if win:
            w = self.won.setdefault(win["id"], [now, 0])
            w[0], w[1] = now, w[1] + 1
            broadcast = self._broadcast(win, t, now, stage, life, lv, is_open, h, ctx)
        if len(self.won) > 200:
            self.won = {k: v for k, v in self.won.items() if now - v[0] < 600}
        self._update_self(t, stage, rel, life, lv)
        self._day(t)
        if self.store is not None and self.dirty and now - self.last_flush >= FLUSH_S:
            self.flush()
        return {"type": "mind", "cycle": self.n, "t": hhmm(t),
                "candidates": [{"id": c["id"], "kind": c["kind"], "label": c["label"],
                                "salience": round(c["salience"], 3), "source": c["source"],
                                "gated": c["gated"]} for c in cands[:12]],
                "winner": win["id"] if win else None, "broadcast": broadcast, "self": self.self_model,
                "threshold": THRESHOLD.get(stage, 0.35)}

    def _broadcast(self, c, t, now, stage, life, lv, is_open, h, ctx):
        kind, content = c["kind"], c["content"]
        lang, nick, act, reason, key, fmt, worthy, encode = self.lang, "", None, "", None, {}, False, False
        topic = kind
        if kind == "chat":
            m = content["msg"]
            first = self.won[c["id"]][1] == 1              # a message re-winning is rumination, not news
            lang, nick, worthy, encode = m["lang"], m["nick"], first, first
            act = m["desire"]
            if act == "buy_bread" and life.get("bread"):
                act = "eat"
            if act:
                key, reason = f"chat_{act}", "someone in the chat mentioned it"
                topic = {"buy_bread": "bread", "eat": "bread"}.get(act, act)
            else:
                key = ("chat_threat" if m["emotion"] == "threat" else "chat_positive" if m["emotion"] == "positive"
                       else "chat_question" if m["question"] else "chat_neutral")
                topic = "a message"
            fmt = {"nick": nick}
        elif kind == "need":
            name = content["need"]
            key, topic = f"need_{name}", name
            if self.need_news.pop(name, False):
                worthy = True
            if content["level"] < NEED_ACT:
                pass
            elif name == "hunger":
                act = "eat" if life.get("bread") else "buy_bread"
                reason = "hungry"
            elif name == "boredom":
                day = 8 <= h < 20
                act = self.rng.choice(["park", "phone", "window"] if day else ["phone", "window"])
                reason = "bored"
        elif kind == "market":
            mk = content["market"]
            key, act, reason, topic = f"market_{mk}", "chart", f"the market is {mk}", "the chart"
            encode = mk in ("pumping", "dumping")
        elif kind == "perception":
            p = content["perc"]
            key = f"time_{content['phase']}" if p == "time" else f"perc_{p}"
            topic = c["label"]
        elif kind == "dream":
            key, fmt, worthy, topic = "dream", {"snip": _snip(content["text"], 28)}, True, "a dream"
            lang = lang_of(content["text"])
        elif kind == "memory":
            key, fmt, topic = "memory", {"snip": _snip(content["mem"].get("text"), 28)}, "a memory"
            lang = lang_of(content["mem"].get("text"))
        if stage != "AWAKE" or (act and (act == life.get("activity") and not life.get("walking"))):
            act = None                                   # asleep, or already doing it
        if act and (self.cooldown.get(act, -1e9) > now or (kind != "chat" and now < self.next_proposal)):
            act = None
        line = self._line(key, lang, **fmt)
        b = {"id": c["id"], "kind": kind, "label": c["label"], "about": topic, "t": hhmm(t),
             "salience": round(c["salience"], 3), "action": {"act": act, "reason": reason} if act else None,
             "speech": line, "lang": lang, "encode": encode, "worthy": worthy, "nick": nick or None,
             "focus": self._focus_text(c, act)}
        viewers = int(ctx.get("viewers") or 0)
        b["llm"] = bool(worthy and self.llm is not None and viewers > 0 and self._llm_ok(now))
        self.last, self.last_r = b, now
        self.history.append({"t": b["t"], "kind": kind, "label": c["label"], "about": topic, "line": line,
                             "action": dict(b["action"]) if act else None})
        del self.history[:-HISTORY]
        self.self_model["history"] = self.history
        emit = worthy or act is not None or (now - self.last_speech[0] >= SPEECH_MIN_S
                                             and line != self.last_speech[1])
        if emit and not self._held(now):
            self.pending = {"text": line, "kind": "rule", "lang": lang, "about": topic,
                            "action": {"act": act, "ok": None, "reason": reason} if act else None,
                            "_llm": b["llm"], "_req": None, "_deadline": None, "_ctx": self._llm_ctx(b, c)}
            self._diary_add(t, {"t": b["t"], "stamp": stamp(t), "kind": kind, "label": c["label"], "about": topic,
                                "line": line, "lang": lang, "action": None, "nick": nick or None})
        return b

    # ---- action outcome (server -> mind) --------------------------------------------------------------------
    def outcome(self, act, ok, why, t=None):
        """The server asked life.request(act, ...) and got (ok, why): record it and compose the line."""
        now = self.clock()
        self.cooldown[act] = now + ACTION_COOLDOWN_S[bool(ok)]
        self.next_proposal = now + ACTION_GAP_S
        lang = self.last["lang"] if self.last else self.lang
        why = (why or "").strip()
        if ok:
            key = f"ok_{act}" if f"ok_{act}" in TPL else "ok_other"
            line = self._line(key, lang)
        else:
            key = next((k for pat, k in DECLINE if re.search(pat, why.lower())), "no_other")
            line = self._line(key, lang, why=_snip(why, 60)) if why else self._line("no_plain", lang)
        res = {"act": act, "ok": bool(ok), "reason": why}
        if self.history and self.history[-1].get("action") and self.history[-1]["action"].get("act") == act:
            self.history[-1]["action"].update(ok=bool(ok), why=why)
            self.history[-1]["line"] = line
        if self.last and self.last.get("action") and self.last["action"]["act"] == act:
            self.last["action"].update(ok=bool(ok), why=why)
            self.last["speech"] = line
        about = self.last["about"] if self.last else act
        llm = bool(self.pending and self.pending.get("_llm") and not self.pending.get("_req"))
        ctx = (self.pending or {}).get("_ctx") or {}
        ctx = dict(ctx, action=res, rule_line=line)
        worthy = bool(self.last and self.last.get("worthy"))
        if worthy or ok or (now - self.last_speech[0] >= SPEECH_MIN_S and line != self.last_speech[1]):
            self.pending = {"text": line, "kind": "rule", "lang": lang, "about": about, "action": res,
                            "_llm": llm, "_req": None, "_deadline": None, "_ctx": ctx}
        elif self.pending and (self.pending.get("action") or {}).get("act") == act:
            self.pending = None                          # a routine decline repeated too soon: stay quiet
        if t is not None:
            day = self._diary.get(local(t).date().isoformat())
            if day and day[-1].get("line") and day[-1].get("action") is None and day[-1]["about"] == about:
                day[-1].update(line=line, action=res)
                self.dirty.add(local(t).date().isoformat())
            else:
                self._diary_add(t, {"t": hhmm(t), "stamp": stamp(t), "kind": "action", "label": act,
                                    "about": about, "line": line, "lang": lang, "action": res, "nick": None})
        self.self_model["wanting"] = self._wanting(res)
        return line

    # ---- inner speech ----------------------------------------------------------------------------------------
    def _line(self, key, lang, **fmt):
        opts = TPL.get(key or "", {}).get(lang) or TPL.get(key or "", {}).get("en") or []
        if not fmt.get("nick"):
            opts = [o for o in opts if "{nick}" not in o] or opts
        if opts:
            line = self.rng.choice(opts).format(**{"nick": "", "snip": "", "why": "", **fmt}).strip()
            if safe_text(line):
                return line
            plain = {"dream": "dream_plain", "memory": "memory_plain"}.get(key, "no_plain")
            if plain in TPL:
                return TPL[plain][lang if lang in TPL[plain] else "en"][0]
        return "..."

    def _held(self, now):
        p = self.pending
        return bool(p and p.get("_req") and p.get("_deadline") and now < p["_deadline"])

    def speech_due(self):
        """Pending inner-speech line {"text","kind","lang","about","action"} or None (then cleared)."""
        now = self.clock()
        if not self.pending or self._held(now):
            return None
        p, self.pending = self.pending, None
        self.last_speech = (now, p["text"])
        return {k: v for k, v in p.items() if not k.startswith("_")}

    # ---- optional language model (run off the event loop by the server) ------------------------------------
    def _llm_ok(self, now):
        self.llm_times = [x for x in self.llm_times if now - x < 3600]
        if self.llm_times and now - self.llm_times[-1] < LLM_MIN_GAP_S:
            return False
        return len(self.llm_times) < LLM_PER_HOUR

    def _llm_ctx(self, b, c):
        m = c["content"].get("msg") or {}
        return {"lang": b["lang"], "about": b["about"], "kind": b["kind"], "label": c["label"],
                "message": _snip(m.get("text", ""), 140) if m else "", "nick": b["nick"] or "",
                "doing": self.self_model.get("doing", ""), "feeling": self.self_model.get("feeling", ""),
                "stage": self.self_model.get("stage", "AWAKE"), "action": b["action"], "rule_line": b["speech"]}

    def llm_request(self):
        """-> {"id","system","user"} when the pending line should be rephrased by the language model, else None.
        The server runs `run_llm(req)` in an executor and passes the answer to `llm_result(id, text)`."""
        now = self.clock()
        p = self.pending
        if not p or not p.get("_llm") or p.get("_req") or self.llm is None or not self._llm_ok(now):
            return None
        self._req += 1
        self.llm_times.append(now)
        p["_req"], p["_deadline"] = self._req, now + LLM_WAIT_S
        return {"id": self._req, "system": LLM_SYSTEM, "user": json.dumps(p["_ctx"], ensure_ascii=False)}

    def run_llm(self, req):
        try:
            return self.llm(req["system"], req["user"])
        except Exception:
            return None

    def llm_result(self, rid, text):
        """Language-model answer for request `rid`: used only if it passes safe_text, else the rule line stays."""
        p = self.pending
        if not p or p.get("_req") != rid:
            return False
        p["_req"], p["_deadline"], p["_llm"] = None, None, False
        line = self.clean(text)
        if line and safe_text(line):
            p["text"], p["kind"] = line, "llm"
            if self.last:
                self.last["speech"] = line
            return True
        return False

    @staticmethod
    def clean(text):
        if not isinstance(text, str):
            return ""
        line = next((x for x in text.strip().splitlines() if x.strip()), "").strip()
        line = re.sub(r"^(thought|line|inner speech|pensiero)\s*:\s*", "", line, flags=re.I)
        return line.strip().strip("\"'“”«»").strip()

    # ---- self-model ------------------------------------------------------------------------------------------
    def _update_self(self, t, stage, rel, life, lv):
        sm = self.self_model
        sm["stage"] = stage
        sm["doing"] = ("sleeping, dreaming" if stage == "REM" else "sleeping" if stage == "NREM"
                       else life.get("doing") or life.get("activity") or "")
        sm["feeling"] = self.feeling(rel, stage, lv)
        sm["wanting"] = self._wanting(None, lv)
        sm["focus"] = self.last["label"] if self.last and self.clock() - self.last_r < 60 else None

    @staticmethod
    def feeling(rel, stage="AWAKE", lv=None):
        """Words for the current brain rel activity (a description of the model's state, not an experience)."""
        if stage == "REM":
            return "dreaming"
        if stage == "NREM":
            return "deeply asleep"
        r = lambda k: float(rel.get(k, 1.0))
        words = []
        if r("fear") > 1.3:
            words.append("tense")
        elif r("salience") > 1.3:
            words.append("alert")
        if r("reward") > 1.25:
            words.append("content")
        if r("attention") > 1.2:
            words.append("curious")
        elif r("default") > 1.25:
            words.append("absorbed")
        if (lv or {}).get("sleep", 0) > 0.7:
            words.append("sleepy")
        if (lv or {}).get("boredom", 0) > 0.75:
            words.append("restless")
        return ", ".join(words[:2]) or "calm"

    def _wanting(self, res=None, lv=None):
        if lv:
            name, level = max(lv.items(), key=lambda kv: kv[1])
            if level >= 0.5:
                return {"hunger": "something to eat", "boredom": "something to do", "sleep": "sleep"}[name]
        if self.last and self.last.get("action"):
            return {"buy_bread": "bread", "eat": "something to eat", "phone": "the phone", "park": "some air",
                    "chart": "a look at the chart", "window": "a look outside"}.get(self.last["action"]["act"],
                                                                                   "nothing in particular")
        return "nothing in particular"

    def focus(self):
        """Short text for the eye: what currently holds the workspace (empty when nothing recent)."""
        if not self.last or self.clock() - self.last_r > 60:
            return ""
        return self.last["focus"]

    def _focus_text(self, c, act):
        s = {"chat": "a chat message", "need": "a need", "memory": "a memory", "market": "the market",
             "perception": "the surroundings", "dream": "a dream"}[c["kind"]]
        txt = f"attending to {s}: {c['label']}"
        if act:
            txt += f"; proposes: {act}"
        return txt[:160]

    # ---- diary / continuity -----------------------------------------------------------------------------------
    def _diary_add(self, t, entry):
        d = local(t).date().isoformat()
        day = self._diary.setdefault(d, [])
        if not day and self.store is not None:
            day.extend(self.store.load(d))
        day.append(entry)
        del day[:-DIARY_CAP]
        self.dirty.add(d)

    def _day(self, t):
        d = local(t).date().isoformat()
        if d == self.today:
            return
        self.today = d
        prev = sorted(k for k in set(self._diary) | set(self.store.dates() if self.store else []) if k < d)
        if prev:
            y = prev[-1]
            entries = self.diary(y)
            topics = {}
            for e in entries:
                topics[e.get("about", "")] = topics.get(e.get("about", ""), 0) + 1
            top = [k for k, _ in sorted(topics.items(), key=lambda kv: -kv[1]) if k][:3]
            self.yesterday = {"date": y, "entries": len(entries), "topics": top}
            self.self_model["yesterday"] = self.yesterday
        for k in [k for k in self._diary if k < d and k not in (prev[-1:] if prev else [])]:
            if k not in self.dirty:
                del self._diary[k]                     # keep today + the day before in memory

    def diary(self, date):
        d = _date_str(date)
        if d in self._diary:
            return list(self._diary[d])
        return self.store.load(d) if self.store is not None else []

    def flush(self):
        if self.store is None:
            return
        for d in sorted(self.dirty):
            self.store.save(d, self._diary.get(d, []))
        self.dirty.clear()
        self.last_flush = self.clock()

    def to_dict(self):
        keep = sorted(self._diary)[-2:]
        return {"cycle": self.n, "nmsg": self.nmsg, "lang": self.lang, "history": self.history,
                "diary": {k: self._diary[k] for k in keep}, "yesterday": self.yesterday}
