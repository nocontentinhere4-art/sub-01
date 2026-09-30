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

Server-facing extras beyond the contract: `outcome(act, ok, why, t)` (the answer of life.request),
`llm_request()` / `run_llm(req)` (run it in an executor) / `llm_result(id, text)`, `focus()` for the eye,
`flush()` (call it from an executor when `auto_flush=False`), `summary(date)` and `DiaryStore(root)`.
`cycle()` returns copies, so a cached message never changes afterwards.

Nothing here claims or implies that SUB-01 is conscious, alive, sentient or a person, and nothing speaks as or
about the real person whose public scans were used. `safe_text` guards every generated line (and
`safe_llm_text` adds stricter rules for language-model output); chat text that fails it is never echoed in
labels, the eye's focus or the diary.
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
DECLINE_BACKOFF_MAX_S = 900.0  # repeated declines of one act double its cooldown up to this
DECLINE_QUIET_S = 600.0      # the same decline line again within this window is not spoken (it is still recorded)
ACTION_GAP_S = 45.0          # after any outcome, needs / market / perceptions wait this long before proposing
NEED_ACT = 0.5               # a need proposes an action only from this level
LLM_MIN_GAP_S = 30.0
LLM_PER_HOUR = 60
LLM_WAIT_S = 10.0            # hold the rule line this long waiting for the language model
HISTORY = 10
DIARY_CAP = 400              # detail entries kept per day (day aggregates are not capped)
DIARY_ROUTINE_WINDOW = 20    # a routine line already among the last 20 detail entries is only counted
DIARY_HOUR_CAP = DIARY_CAP // 24   # detail entries per local hour, so the kept detail spans the whole day
REPEAT_S = 180.0             # a routine (not worth showing) line about the same topic at most this often
AWAKE_MEMORY = 0.35          # awake, memories are weaker than while asleep
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
# Every pattern is matched on a normalised copy of the line (`_norm`): '_', '-', '.', '/' and similar separators
# become spaces, camelCase and letter/digit joins are split, so a nickname such as "Alive_Bob", "coinKing" or
# "alive99" cannot hide a word from the filters. Word edges are letter lookarounds, not \b ('_' is a word char).
_A, _Z = r"(?<![a-zà-ÿ])", r"(?![a-zà-ÿ])"
_I_AM = r"i\s*(?:am|'m)"


def _rx(body):
    return re.compile(_A + r"(?:" + body + r")" + _Z, re.I)


CLAIM_RE = _rx(
    # EN: consciousness / life / personhood / inner experience
    r"conscious\w*|sentien\w*|self\s?aware\w*|aware\w*|alive|sapient\w*|exist\w*|real|"
    + _I_AM + r"\s+(?:a\s+|an\s+)?(?:real\s+|living\s+)?(?:person|human|living|being|someone|people|boy|girl|man|woman)|"
    r"human\s+beings?|(?:have|got|with)\s+(?:a\s+|real\s+|my\s+own\s+)?(?:soul|feelings|emotions|thoughts\s+of\s+my\s+own)|"
    r"my\s+soul|(?:a|my|own)\s+mind|minds?\s+of\s+(?:my|its)\s+own|feel\w*\s+(?:pain|hurt|things|real|emotions?)|"
    r"pain(?:s|ful)?|suffer\w*|therefore\s+i\s+am|not\s+(?:just\s+)?(?:a\s+|an\s+)?(?:robot|machine|program|bot|simulation|"
    r"model|ai|code)|awake\s+and\s+(?:think|feel|aware)\w*|think\w*\s+and\s+feel\w*|"
    # IT
    r"coscien\w*|consapevol\w*|senzien\w*|viv[oaie]|vivente|esist\w*|"
    r"sono\s+(?:una\s+|un\s+|davvero\s+)?(?:persona|umano|umana|essere\s+umano|real[ei]|ver[oa]|sveglio|sveglia)|"
    r"essere\s+umano|anima|(?:una|la\s+mia|mia)\s+mente|mente\s+mia|dolor\w*|soffr\w*|soffer\w*|quindi\s+sono|"
    r"(?:ho|provo)\s+(?:dei\s+|delle\s+)?(?:sentimenti|emozioni)|"
    r"non\s+sono\s+(?:solo\s+)?(?:un\s+|una\s+)?(?:robot|macchina|programma|bot|simulazione|ia|modello|codice)")
_PREDICT_TO = (r"(?:go(?:ing)?\s+up|go(?:ing)?\s+down|rise|fall|climb|drop|crash|pump|dump|explode|skyrocket|"
               r"recover|bounce|rally|soar|tank|surge|jump|double|triple|moon|break\s*out|higher|lower|up|down)")
MONEY_RE = _rx(
    # EN: buying / selling / trading / money / promises / predictions
    r"buy\w*|bought|sell\w*|sold|invest\w*|money|cash|profit\w*|gains?|earn\w*|get(?:ting)?\s+rich|make\s+you\s+rich|"
    r"rich(?:er|es|est)|wealth\w*|to\s+the\s+moon|moon(?:ing|shot|boy)\w*|lambo\w*|\d+\s*x|guarantee\w*|promis\w*|"
    r"financ\w*|price\w*|tokens?|coins?|crypto\w*|wallet\w*|usd|dollars?|euros?|trad(?:e|es|er|ers|ing)|"
    r"go(?:ing)?\s+(?:long|short)|(?:long|short)\s+(?:it|this|that|now|position\w*)|shorting|ape[sd]?\s+in\w*|aping|"
    r"hodl\w*|all\s+in|bags?(?!\s+of)|bullish|bearish|bull\s+run|pump\w*|dump\w*|bet(?:s|ting)?|wager\w*|gambl\w*|"
    r"on\s+sale|discount\w*|deal\s+of|"
    r"(?:will|shall|gonna|going\s+to|about\s+to|sure\s+to|bound\s+to)\s+(?:\w+\s+){0,2}?" + _PREDICT_TO + r"|"
    r"'ll\s+(?:\w+\s+){0,2}?" + _PREDICT_TO + r"|"
    # IT
    r"compr(?:a|o|i|are|ate|ato|iamo|ando|erò|erei)|vend(?:i|o|e|ere|ete|uto|iamo|ita|erò|erei)|acquist\w*|"
    r"investi\w*|soldi|denar\w*|guadagn\w*|profitt\w*|ricc[oaih]\w*|garant\w*|promett\w*|promess\w*|prezz\w*|"
    r"(?:vai|andare|entra|entrare|posizione)\s+(?:lung[oa]|cort[oa])|scommett\w*|scommess\w*|puntar\w*|azzard\w*|"
    r"rialz\w*|ribass\w*|sconto|sconti|saldi|offert\w*|"
    r"(?:salir|scender|crescer|esploder|crollar|rimbalzer|raddoppier|triplicher|volar)\w*")
MARKET_WORDS = _rx(r"chart\w*|market\w*|candles?|graph\w*|grafic\w*|mercat\w*|candel\w*|trend\w*")
FORECAST = _rx(r"will|won't|shall|gonna|going\s+to|about\s+to|'ll|tomorrow|soon|next|sure\w*|definitely|certain\w*|"
               r"guarantee\w*|domani|presto|prossim\w*|sicur\w*|cert[oa]|certamente|vedrai|"
               r"\w+(?:erà|irà|arà|eranno|iranno|aranno)")
DIRECTION = _rx(r"ris(?:e|es|ing|en)|fall(?:s|ing)?|climb\w*|drop\w*|higher|lower|soar\w*|tank\w*|recover\w*|"
                r"sale|salgono|salire|scende|scendono|scendere|cresc\w*|croll\w*|rimbalz\w*|esplod\w*|vola\w*")
PERSON_RE = _rx(
    # the real person / the scans
    r"mri|fmri|scans|scanned|scanner|scanning\s+of|(?:brain|mri|body)\s+scan|scansion\w*|risonanz\w*|donor\w*|"
    r"donat(?:ore|rice)|volunteer\w*|volontari\w*|real\s+person|persona\s+reale|(?:the|that)\s+person\s+(?:whose|who|behind)|"
    r"la\s+persona\s+(?:da|di|che|dietro)|whose\s+brain|his\s+brain|her\s+brain|il\s+suo\s+cervello|mi\s+chiamo|"
    r"my\s+name|call\s+me|"
    # invented biography, EN
    r"grew\s+up|grow(?:ing)?\s+up|born|birthday|used\s+to|years\s+ago|back\s+then|back\s+in\s+the|"
    r"when\s+i\s+was|i\s+remember|i\s+recall|remember\s+when|childhood|hometown|home\s+town|as\s+a\s+(?:kid|child|boy|girl)|"
    r"(?:my|our)\s+(?:\w+\s+)?(?:mother|father|mom|mum|dad|grand\w*|granny|nan|nonna|uncle|aunt\w*|cousin\w*|"
    r"friends?|girlfriend|boyfriend|wife|husband|family|parents?|brother\w*|sister\w*|kids?|children|sons?|"
    r"daughters?|job|work|boss|colleague\w*|school|teacher|university|college|village|city|country|youth|past|"
    r"old\s+(?:house|home|life|place)|life\s+before|previous\s+life|hometown)|"
    # invented biography, IT
    r"sono\s+nat[oa]|nacqui|nascita|cresciut\w*|crescendo|da\s+(?:bambin|piccol|ragazz|giovan)\w*|"
    r"nonn[aoie]|zi[oiae]|cugin\w*|amic[oaih]\w*|ricord\w*|anni\s+fa|tempo\s+fa|una\s+volta\s+(?:ero|avevo|facevo|"
    r"andavo|vivevo|abitavo|lavoravo)|quando\s+ero|infanzia|scuola|paese\s+natale|citt[àa]\s+natale|"
    r"(?:mia|mio|miei|mie)\s+(?:\w+\s+)?(?:madre|padre|mamma|papà|infanzia|moglie|marito|famiglia|genitori|"
    r"fratell\w*|sorell\w*|figli\w*|lavoro|capo|paese|citt[àa]|vita\s+di\s+prima|passato|giovinezza)")

# first-person self-descriptions: "I am / I'm / I feel / (io) sono / mi sento" must be followed by a plain state
# (hungry, tired, going, at the bakery ...). Anything else ("I am a mind", "sono vero") is rejected.
FP_EN = re.compile(r"(?<![a-z])(?:i\s*(?:am|'m)|i\s+feel|i'm\s+feeling|i\s+am\s+feeling)(?![a-z])((?:\s+[a-z']+){0,4})")
FP_IT = re.compile(r"(?:^|[.,;:!?…]\s*|(?<![a-zà-ÿ])io\s+)sono(?![a-zà-ÿ])((?:\s+[a-zà-ÿ']+){0,4})"
                   r"|(?<![a-zà-ÿ])mi\s+sento(?![a-zà-ÿ])((?:\s+[a-zà-ÿ']+){0,4})")
FP_SKIP_EN = {"not", "so", "really", "just", "still", "getting", "feeling", "quite", "too", "very", "pretty",
              "rather", "already", "almost", "now", "also", "kind", "sort", "of", "a", "bit", "little", "kinda", "all",
              "somewhat"}
FP_SKIP_IT = {"un", "po", "po'", "proprio", "molto", "così", "cosi", "già", "gia", "ancora", "troppo", "davvero",
           "appena", "quasi", "un'", "abbastanza", "tutto", "tutta", "di", "nuovo", "non", "adesso", "ora"}
FP_OK = {
    # EN states / places / ongoing activities
    "hungry", "starving", "peckish", "thirsty", "tired", "sleepy", "drowsy", "exhausted", "bored", "restless",
    "curious", "calm", "tense", "alert", "content", "relaxed", "busy", "done", "full", "ready", "fine", "ok",
    "okay", "good", "glad", "happy", "sorry", "late", "early", "going", "heading", "off", "back", "here", "there",
    "home", "out", "outside", "inside", "in", "at", "on", "by", "near", "staying", "waiting", "looking", "reading",
    "scrolling", "walking", "eating", "sitting", "lying", "resting", "thinking", "watching", "checking",
    "wondering", "listening", "staring", "cold", "warm", "hot", "sluggish", "lazy", "lost", "stuffed", "comfy",
    # IT
    "stanco", "stanca", "stanchissimo", "stanchissima", "affamato", "affamata", "annoiato", "annoiata",
    "assonnato", "assonnata", "sazio", "sazia", "pieno", "piena", "pronto", "pronta", "qui", "qua", "lì", "là",
    "a", "al", "alla", "allo", "ai", "alle", "all'", "in", "nel", "nella", "fuori", "dentro", "davanti", "vicino",
    "tornato", "tornata", "uscito", "uscita", "arrivato", "arrivata", "curioso", "curiosa", "tranquillo",
    "tranquilla", "calmo", "calma", "teso", "tesa", "contento", "contenta", "occupato", "occupata", "pigro",
    "pigra", "rilassato", "rilassata", "agitato", "agitata", "irrequieto", "irrequieta", "bene", "meglio",
    "felice", "sollevato", "sollevata", "per", "sul", "sulla", "sulle", "senza", "casa", "letto"}


def _norm(s):
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"(?<=[a-zà-ÿ])(?=[A-Z])", " ", s)                  # camelCase -> camel Case
    s = re.sub(r"(?<=[A-Za-zà-ÿ])(?=\d)|(?<=\d)(?=[A-Za-zà-ÿ])", " ", s)
    s = re.sub(r"[_\-–—./\\|+*#@~=:;,!?()\[\]{}<>\"“”«»]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _first_person_ok(low):
    for rx, skip in ((FP_EN, FP_SKIP_EN), (FP_IT, FP_SKIP_IT)):
        for m in rx.finditer(low):
            words = " ".join(g or "" for g in m.groups()).split()
            w = next((x for x in words if x not in skip), None)
            if w is not None and w not in FP_OK:
                return False
    return True


def safe_text(s):
    """True if a generated line may be shown: passes the chat filter, makes no claim of being conscious / alive /
    sentient / real / a person or of having inner experience, describes itself only with plain states ("I'm
    hungry"), says nothing about buying, selling, trading, money, promises or where a chart will go, does not refer
    to the real person behind the scans, invents no biography or family, and is one line of at most MAX_CHARS."""
    if not isinstance(s, str):
        return False
    s2 = s.strip()
    if not s2 or len(s2) > MAX_CHARS or "\n" in s2 or "\r" in s2:
        return False
    if blocked(s2):
        return False
    n = _norm(s2)
    if CLAIM_RE.search(n) or MONEY_RE.search(n) or PERSON_RE.search(n):
        return False
    if (MARKET_WORDS.search(n) or DIRECTION.search(n)) and FORECAST.search(n):
        return False
    low = s2.lower().replace("’", "'")
    return _first_person_ok(low) and _first_person_ok(n.lower())


LLM_EXTRA = re.compile(r"https?|www|[@#$€£%&<>{}\[\]\\|*_~^=+\d]|[\U0001F000-\U0001FAFF☀-➿️]")


def safe_llm_text(s, lang="en", nick=""):
    """safe_text plus the extra rules the language model is asked to follow and cannot be trusted with: no links,
    handles, hashtags, digits, symbols or emoji, no capitalised name other than the given nickname (so no invented
    people or places), and the line is in the requested language."""
    if not safe_text(s):
        return False
    s2 = s.strip()
    if LLM_EXTRA.search(s2):
        return False
    nick_l = (nick or "").strip().lower()
    for m in re.finditer(r"[A-ZÀ-Ý][A-Za-zà-ÿ']+", s2):
        start = m.start()
        before = s2[:start].rstrip()
        if not before or before[-1] in ".!?…\"'“«":
            continue                                               # sentence start
        if m.group(0).lower() in (nick_l, "sub") or m.group(0).startswith("I'"):
            continue
        return False
    words = re.findall(r"[a-zàèéìòù']+", s2.lower())
    it = sum(x in IT_WORDS for x in words) + len(re.findall(r"[àèéìòù]", s2.lower()))
    en = sum(x in EN_WORDS for x in words)
    if lang == "it" and en > it:
        return False
    if lang == "en" and it > en:
        return False
    return True


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

DECLINE = [  # (pattern on the reason life.request passed back, template); whole words only
    (r"\b(?:clos\w*|chius\w*|opens|apre|aprirà|orari\w*|hours)\b", "no_closed"),
    (r"\b(?:dark|night|buio|notte|sera|evening)\b", "no_dark"),
    (r"\b(?:already|has|have|got|ha|hai|ho)\b.*\b(?:bread|pane)\b|\bbread (?:at|in) (?:the )?home\b", "no_has_bread"),
    (r"\b(?:not hungry|full|sazi[oa]|niente fame|non ha fame)\b", "no_full"),
    (r"\b(?:tired|energy|stanc\w*)\b", "no_tired"),
    (r"\b(?:asleep|sleep\w*|dorm\w*)\b", "no_asleep"),
    (r"\b(?:busy|walking|already doing|in progress|occupat\w*|cammina\w*)\b", "no_busy"),
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


def _rel(rel, k):
    """rel activity for network k (1.0 = the global mean); None, text, NaN or inf from the server count as 1.0."""
    try:
        v = float(rel.get(k, 1.0))
    except (TypeError, ValueError, AttributeError):
        return 1.0
    return max(0.0, min(10.0, v)) if math.isfinite(v) else 1.0


def _phase(h):
    return ("night" if h < 6 else "dawn" if h < 8 else "morning" if h < 12 else "afternoon" if h < 18
            else "evening" if h < 21 else "night")


def _date_str(date):
    return date if isinstance(date, str) else date.isoformat()


def _summary(entries):
    """Day aggregates computed from a list of entries (for diary files written without a summary)."""
    agg = _new_agg()
    for e in entries:
        _agg_add(agg, e)
    return agg


def _new_agg():
    return {"entries": 0, "topics": {}, "kinds": {}, "actions": {}, "nicks": {}}


def _agg_add(agg, e, count=True):
    def inc(d, k, cap=200):
        if k and (k in d or len(d) < cap):
            d[k] = d.get(k, 0) + 1
    if count:
        agg["entries"] += 1
        inc(agg["topics"], e.get("about"))
        inc(agg["kinds"], e.get("kind"))
        inc(agg["nicks"], e.get("nick"))
    a = e.get("action")
    if a and a.get("ok") is not None:
        inc(agg["actions"], f"{a.get('act')}:{'ok' if a.get('ok') else 'no'}")


class DiaryStore:
    """data/diary/YYYY-MM-DD.json: {"date", "summary", "entries"} per day. "summary" holds uncapped day aggregates
    (number of lines, topic / kind / action counters, public chat nicknames); "entries" is a capped, sampled list of
    detail (times, workspace winners, lines, actions; no chat text, no other personal data)."""

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

    def load_summary(self, date):
        f = self.dir / f"{_date_str(date)}.json"
        if not f.exists():
            return None
        try:
            d = json.loads(f.read_text())
        except (ValueError, OSError):
            return None
        if isinstance(d, dict) and isinstance(d.get("summary"), dict):
            return d["summary"]
        return _summary(d.get("entries", []) if isinstance(d, dict) else list(d))

    def save(self, date, entries, summary=None):
        f = self.dir / f"{_date_str(date)}.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps({"date": _date_str(date), "summary": summary or _summary(entries),
                                   "entries": entries}, indent=1, ensure_ascii=False))
        tmp.replace(f)

    def dates(self):
        return sorted(p.stem for p in self.dir.glob("????-??-??.json"))


class Mind:
    def __init__(self, state=None, rng=None, llm=None, clock_fn=None, store=None, auto_flush=True):
        """`store`: a DiaryStore (or None). With `auto_flush` the diary is written from cycle() at most every
        FLUSH_S; a server that prefers to keep file writes off the event loop passes False and calls flush() from
        an executor."""
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
        self._agg = {k: dict(_new_agg(), **v) for k, v in (s.get("diary_summary") or {}).items()}
        for k, v in self._diary.items():
            self._agg.setdefault(k, _summary(v))
        self.auto_flush = auto_flush
        self.yesterday = s.get("yesterday")
        self.msgs = []                                   # recent heard messages (<= 20)
        self.won = {}                                    # candidate id -> [real t of last win, wins]
        self.seen = {}                                   # perception key -> [value, real t changed]
        self.need_hi = {}                                # need -> above threshold
        self.need_news = {}                              # need -> crossed, not yet announced
        self.cooldown = {}                               # act -> real t until which it is not re-proposed
        self.declines = {}                               # act -> consecutive declines (cooldown backoff)
        self.last_decline = {}                           # act -> (real t, line) of the last spoken decline
        self.next_proposal = -1e9                        # real t from which non-chat winners may propose again
        self.llm_times = []                              # real t of issued language-model requests
        self.pending = None                              # inner-speech line waiting for the server
        self.last_speech = (-1e9, "")
        self.spoke = {}                                  # topic -> real t it was last spoken about
        self._labels = {}                                # text hash -> safe label (memories, dreams)
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
                    self._agg[d] = dict(_new_agg(), **(store.load_summary(d) or {}))

    # ---- inputs -------------------------------------------------------------------------------------------
    def hear(self, msg, t):
        """An accepted (already filtered) chat message -> its candidate id."""
        self.nmsg += 1
        cid = f"chat:{self.nmsg}"
        text = (msg.get("text") or "").strip()
        desire = next((act for pat, act in DESIRES if re.search(pat, text.lower())), None)
        nets = list(msg.get("networks") or ["language", "somatomotor"])
        nick = (msg.get("nick") or "").strip()[:20]
        snick = nick if nick and safe_text(nick) else ""
        label = f"“{_snip(text, 36)}”" + (f" ({snick})" if snick else "")
        if not safe_text(label):                          # the page, the eye and the diary never echo unsafe text
            label = "a chat message" + (f" from {snick}" if snick else "")
        self.msgs.append({"id": cid, "text": text, "nick": nick, "snick": snick, "label": label, "nets": nets,
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
            add(m["id"], "chat", m["label"], "chat:" + (m["snick"] or "anon"), m["nets"], nov + emo, {"msg": m})
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
                add(f"mem:{int(mt)}:{_h(m.get('text'))}", "memory", self._label("memory", m.get("text")),
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
                add(did, "dream", self._label("dream", txt), "dream", ["memory", "limbic", "visual"],
                    0.6 + (0.6 if did not in self.won else 0.0), {"text": txt})     # a new replay is novel
        return out, lv, is_open, h

    def _label(self, kind, text):
        """'memory: “...”' / 'dream: “...”', or just 'a memory' / 'a dream' when the snippet fails safe_text."""
        k = kind + _h(text)
        lab = self._labels.get(k)
        if lab is None:
            lab = f"{kind}: “{_snip(text, 30)}”"
            if not safe_text(lab):
                lab = "a " + kind
            if len(self._labels) > 500:
                self._labels.clear()
            self._labels[k] = lab
        return lab

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
        net = NET_W * sum(_rel(rel, g) for g in c["nets"])
        s = KIND_W[c["kind"]] * net * c["scale"] + c["extra"]
        if stage != "AWAKE" and c["kind"] in ("dream", "memory"):
            s *= SLEEP_MULT.get(stage, 1.0) * (DREAM_REM_BOOST if stage == "REM" and c["kind"] == "dream" else 1.0)
        elif stage == "AWAKE" and c["kind"] == "memory":
            s *= AWAKE_MEMORY
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
        if self.auto_flush and self.store is not None and self.dirty and now - self.last_flush >= FLUSH_S:
            self.flush()
        # copies: later outcome() / cycle() calls must not change a message the server has cached (e.g. for hello)
        if broadcast is not None:
            broadcast = dict(broadcast, action=dict(broadcast["action"]) if broadcast["action"] else None)
        sm = dict(self.self_model, history=[dict(x, action=dict(x["action"]) if x.get("action") else None)
                                            for x in self.history])
        return {"type": "mind", "cycle": self.n, "t": hhmm(t),
                "candidates": [{"id": c["id"], "kind": c["kind"], "label": c["label"],
                                "salience": round(c["salience"], 3), "source": c["source"],
                                "gated": c["gated"]} for c in cands[:12]],
                "winner": win["id"] if win else None, "broadcast": broadcast, "self": sm,
                "threshold": THRESHOLD.get(stage, 0.35)}

    def _broadcast(self, c, t, now, stage, life, lv, is_open, h, ctx):
        kind, content = c["kind"], c["content"]
        lang, nick, act, reason, key, fmt, worthy, encode = self.lang, "", None, "", None, {}, False, False
        topic = kind
        if kind == "chat":
            m = content["msg"]
            first = self.won[c["id"]][1] == 1              # a message re-winning is rumination, not news
            lang, nick, worthy, encode = m["lang"], m["nick"], first, first
            act = m["desire"] if first else None          # only a message's first win proposes an action
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
                po = life.get("open")
                day = bool(po["park"]) if isinstance(po, dict) and "park" in po else 8 <= h < 20   # life knows the daylight
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
             "speech": line, "lang": lang, "encode": encode, "worthy": worthy,
             "nick": (content["msg"]["snick"] or None) if kind == "chat" else None,
             "focus": self._focus_text(c, act)}
        viewers = int(ctx.get("viewers") or 0)
        b["llm"] = bool(worthy and self.llm is not None and viewers > 0 and self._llm_ok(now))
        self.last, self.last_r = b, now
        self.history.append({"t": b["t"], "kind": kind, "label": c["label"], "about": topic, "line": line,
                             "action": dict(b["action"]) if act else None})
        del self.history[:-HISTORY]
        self.self_model["history"] = self.history
        emit = worthy or act is not None or (now - self.last_speech[0] >= SPEECH_MIN_S
                                             and line != self.last_speech[1]
                                             and now - self.spoke.get(topic, -1e9) >= REPEAT_S)
        if emit and not self._held(now):
            self.pending = {"text": line, "kind": "rule", "lang": lang, "about": topic,
                            "action": {"act": act, "ok": None, "reason": reason} if act else None,
                            "_llm": b["llm"], "_req": None, "_deadline": None, "_ctx": self._llm_ctx(b, c)}
            self._diary_add(t, {"t": b["t"], "stamp": stamp(t), "kind": kind, "label": self._diary_label(c),
                                "about": topic, "line": self._diary_line(kind, line, lang), "lang": lang,
                                "action": None, "nick": b["nick"], "worthy": worthy})
        return b

    @staticmethod
    def _diary_label(c):
        """Diary labels carry no chat / memory / dream text, only the kind (and a public nickname)."""
        if c["kind"] == "chat":
            sn = c["content"]["msg"]["snick"]
            return "a chat message" + (f" from {sn}" if sn else "")
        return {"memory": "a memory", "dream": "a dream"}.get(c["kind"], c["label"])

    @staticmethod
    def _diary_line(kind, line, lang):
        if kind in ("dream", "memory"):                   # these lines quote a snippet: keep the plain form
            return TPL[kind + "_plain"][lang if lang in ("en", "it") else "en"][0]
        return line

    # ---- action outcome (server -> mind) --------------------------------------------------------------------
    def outcome(self, act, ok, why, t=None):
        """The server asked life.request(act, ...) and got (ok, why): record it and compose the line."""
        now = self.clock()
        k = self.declines[act] = 0 if ok else self.declines.get(act, 0) + 1
        self.cooldown[act] = now + (ACTION_COOLDOWN_S[True] if ok else
                                    min(DECLINE_BACKOFF_MAX_S, ACTION_COOLDOWN_S[False] * 2 ** (k - 1)))
        self.next_proposal = now + ACTION_GAP_S
        lang = self.last["lang"] if self.last else self.lang
        why = (why or "").strip()
        if ok:
            key = f"ok_{act}" if f"ok_{act}" in TPL else "ok_other"
            line = self._line(key, lang)
        else:
            key = next((k for pat, k in DECLINE if re.search(pat, why.lower())), "no_other")
            line = self._line(key if why else "no_plain", lang, why=_snip(why, 60))
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
        prev = self.last_decline.get(act)
        repeat = not ok and prev is not None and prev[1] == line and now - prev[0] < DECLINE_QUIET_S
        if not ok and not repeat:
            self.last_decline[act] = (now, line)
        if worthy or ok or (not repeat and now - self.last_speech[0] >= SPEECH_MIN_S
                            and line != self.last_speech[1]):
            self.pending = {"text": line, "kind": "rule", "lang": lang, "about": about, "action": res,
                            "_llm": llm, "_req": None, "_deadline": None, "_ctx": ctx}
        elif self.pending and (self.pending.get("action") or {}).get("act") == act:
            self.pending = None                          # a routine decline repeated too soon: stay quiet
        if t is not None:
            d = local(t).date().isoformat()
            day = self._diary.get(d)
            if day and day[-1].get("line") and day[-1].get("action") is None and day[-1]["about"] == about:
                day[-1].update(line=line, action=res)
                _agg_add(self._agg.setdefault(d, _new_agg()), day[-1], count=False)
                self.dirty.add(d)
            else:
                self._diary_add(t, {"t": hhmm(t), "stamp": stamp(t), "kind": "action", "label": act,
                                    "about": about, "line": line, "lang": lang, "action": res, "nick": None,
                                    "worthy": True})
        self.self_model["wanting"] = self._wanting(res)
        return line

    # ---- inner speech ----------------------------------------------------------------------------------------
    @staticmethod
    def _opts(key, lang):
        t = TPL.get(key or "", {})
        return t.get(lang) or t.get("en") or []

    @staticmethod
    def _fallback_key(key):
        key = key or ""
        if key in ("dream", "memory"):
            return key + "_plain"
        if key.startswith("chat_"):
            return "chat_neutral"
        if key.startswith("ok_"):
            return "ok_other"
        if key.startswith("no_"):
            return "no_plain"
        return key                                         # need / perception / market: their own plain lines

    def _line(self, key, lang, **fmt):
        """A rule-based line for `key`. A line that fails safe_text because of what was filled in (an unsafe
        nickname, snippet or reason) is retried without the nickname, then with the key's neutral fallback
        (chat -> chat_neutral, dream/memory -> *_plain, decline -> no_plain), never with an unrelated line."""
        vals = {"nick": "", "snip": "", "why": "", **fmt}
        opts = self._opts(key, lang)
        if not fmt.get("nick"):
            opts = [o for o in opts if "{nick}" not in o] or opts
        if opts:
            line = self.rng.choice(opts).format(**vals).strip()
            if safe_text(line):
                return line
        tries = [o for o in opts if "{nick}" not in o]                           # same key, no nickname
        tries += [o for o in self._opts(self._fallback_key(key), lang) if "{" not in o]
        for o in tries:
            line = o.format(**vals).strip()
            if safe_text(line):
                return line
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
        self.spoke[p.get("about")] = now
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
        """Language-model answer for request `rid`: used only if it passes safe_llm_text (safe_text plus no links,
        handles, digits, emoji or other names, and the requested language), else the rule line stays."""
        p = self.pending
        if not p or p.get("_req") != rid:
            return False
        p["_req"], p["_deadline"], p["_llm"] = None, None, False
        line = self.clean(text)
        if line and safe_llm_text(line, p.get("lang", "en"), (p.get("_ctx") or {}).get("nick", "")):
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
        r = lambda k: _rel(rel, k)
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
    @staticmethod
    def _routine(e):
        return (e.get("kind") in ("need", "perception", "market", "memory") and not e.get("worthy")
                and not e.get("action"))

    @classmethod
    def _prio(cls, e):
        """Which detail entries a full diary hour keeps: chats and dreams, then accepted actions and needs worth
        showing, then declines, then routine lines."""
        if cls._routine(e):
            return 0
        if e.get("kind") in ("chat", "dream"):
            return 3
        a = e.get("action")
        if a and a.get("ok") is False:
            return 1
        return 2

    def _diary_add(self, t, entry):
        """Every line counts in the day's aggregates. The detail list is sampled: a routine line already among the
        last DIARY_ROUTINE_WINDOW entries is only counted, and each local hour keeps at most DIARY_HOUR_CAP entries
        (a full hour replaces its least interesting entry), so the kept detail spans the day from morning to night
        and never exceeds DIARY_CAP."""
        d = local(t).date().isoformat()
        day = self._diary.get(d)
        if day is None:
            day = self._diary[d] = self.store.load(d) if self.store is not None else []
            self._agg[d] = dict(_new_agg(), **((self.store.load_summary(d) if self.store is not None else None)
                                               or _summary(day)))
        _agg_add(self._agg.setdefault(d, _new_agg()), entry)
        self.dirty.add(d)
        if self._routine(entry) and any(e.get("kind") == entry["kind"] and e.get("line") == entry["line"]
                                        for e in day[-DIARY_ROUTINE_WINDOW:]):
            return
        hour = str(entry.get("t", ""))[:2]
        bucket = [i for i, e in enumerate(day) if str(e.get("t", ""))[:2] == hour]
        if len(bucket) >= DIARY_HOUR_CAP:                # full hour: replace its least interesting entry
            i = min(bucket, key=lambda i: (self._prio(day[i]), i))
            if self._prio(day[i]) > self._prio(entry):
                return
            del day[i]
        day.append(entry)
        if len(day) > DIARY_CAP:
            del day[min(range(len(day)), key=lambda i: (self._prio(day[i]), i))]

    def summary(self, date):
        """Uncapped aggregates of a day: {"entries", "topics", "kinds", "actions", "nicks"}."""
        d = _date_str(date)
        if d in self._agg:
            return self._agg[d]
        s = self.store.load_summary(d) if self.store is not None else None
        return dict(_new_agg(), **s) if s else _new_agg()

    def _day(self, t):
        d = local(t).date().isoformat()
        if d == self.today:
            return
        self.today = d
        prev = sorted(k for k in set(self._diary) | set(self._agg) | set(self.store.dates() if self.store else [])
                      if k < d)
        if prev:
            y = prev[-1]
            agg = self.summary(y)
            top = [k for k, _ in sorted(agg["topics"].items(), key=lambda kv: -kv[1]) if k][:3]
            acts = agg.get("actions", {})
            self.yesterday = {"date": y, "entries": agg["entries"], "topics": top,
                              "chats": agg.get("kinds", {}).get("chat", 0),
                              "dreams": agg.get("kinds", {}).get("dream", 0),
                              "actions_ok": sum(v for k, v in acts.items() if k.endswith(":ok")),
                              "actions_declined": sum(v for k, v in acts.items() if k.endswith(":no"))}
            self.self_model["yesterday"] = self.yesterday
        for k in [k for k in set(self._diary) | set(self._agg) if k < d and k not in (prev[-1:] if prev else [])]:
            if k not in self.dirty:
                self._diary.pop(k, None)               # keep today + the day before in memory
                self._agg.pop(k, None)

    def diary(self, date):
        d = _date_str(date)
        if d in self._diary:
            return list(self._diary[d])
        return self.store.load(d) if self.store is not None else []

    def flush(self):
        if self.store is None:
            return
        for d in sorted(self.dirty):
            self.store.save(d, self._diary.get(d, []), self._agg.get(d))
        self.dirty.clear()
        self.last_flush = self.clock()

    def to_dict(self):
        keep = sorted(self._diary)[-2:]
        return {"cycle": self.n, "nmsg": self.nmsg, "lang": self.lang, "history": self.history,
                "diary": {k: self._diary[k] for k in keep},
                "diary_summary": {k: self._agg[k] for k in keep if k in self._agg}, "yesterday": self.yesterday}
