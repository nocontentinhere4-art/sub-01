"""Proposed replacement for chat.incitement (review G24). Not wired in; tests/review/test_incite_review.py measures it
against the current code on tests/review/titles_corpus.py.

What changes, and why (each fixes a measured false positive or miss):
- Titles are cut into segments at " - ", " | ", brackets and sentence punctuation, and a group word only counts when it
  ends its segment. "Kill Japanese Beetles", "Shoot Women's Portraits", "Kill Russians in Arma 3" no longer match.
- The verb must open its segment, optionally after a short call ("let's", "we must", "time to"). An imperative
  call does this, a news or sport sentence ("Lazio slaughter Roma", "Ukraine strikes kill Russians") does not.
- Inside a segment, "-", "_", "/" and "#" join words like a space does, and CamelCase hashtags are split
  ("#KillAllMuslims", "kill-all-jews"). A lone "2" reads as "to" ("death 2 jews").
- Accents are folded (NFKD) instead of deleted. chat.normalise turns "judíos" into "judos".
- Singular group words, "every", "all of the", more verbs (nuke, bomb, stab, massacre, behead, wipe out, eliminate,
  purge), "-ing" forms, and the postfix form "<group> must die / should be killed / deserve death".
- Italian and Spanish calls ("uccidete tutti gli ebrei", "morte agli immigrati", "matar a todos los judios").
"""
import re
import unicodedata

import chat

_EN_GROUPS = ("jew", "muslim", "christian", "arab", "black", "white", "asian", "mexican", "immigrant", "migrant",
              "refugee", "gay", "gay people", "lesbian", "trans people", "transgender", "hindu", "sikh", "gypsy",
              "gypsies", "roma", "african", "chinese", "japanese", "korean", "indian", "palestinian", "israeli",
              "ukrainian", "russian", "atheist", "boer", "afrikaner", "woman", "women", "jewish people", "muslim people")
_SLURS = tuple(w for w in chat.HATE_SLURS)
_IT_GROUPS = ("ebrei", "ebreo", "musulmani", "islamici", "cristiani", "arabi", "neri", "negri", "immigrati", "migranti",
              "profughi", "stranieri", "zingari", "rom", "froci", "gay", "donne", "africani", "cinesi", "terroni")
_ES_GROUPS = ("judios", "judio", "musulmanes", "cristianos", "arabes", "negros", "inmigrantes", "migrantes",
              "refugiados", "gitanos", "maricones", "gays", "mujeres", "moros", "sudacas", "indios", "chinos")


def _alt(words, plural=True):
    return r"(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")" + (
        r"(?:s|es)?" if plural else "")


G = _alt(_EN_GROUPS + _SLURS)
GIT, GES = _alt(_IT_GROUPS, False), _alt(_ES_GROUPS, False)
CALL = r"(?:(?:lets|let us|we must|we should|we need to|time to|go|just|i want to|i will|we will)\s+)?"
VERB = (r"(?:kill|killing|burn|burning|gas|gassing|hang|hanging|lynch|lynching|shoot|shooting|exterminate|"
        r"exterminating|slaughter|murder|genocide|nuke|bomb|bombing|stab|massacre|behead|wipe out|eliminate|purge)")
DET = r"(?:(?:all|all of|every|every single|each)\s+)?(?:(?:the|those|these|them|em)\s+)?"
EN_CALL = r"^" + CALL + VERB + r"\s+" + DET + G + r"$"
EN_DEATH = r"\bdeath\s+to\s+" + DET + G + r"$"
EN_POST = (r"^(?:all\s+)?(?:the\s+)?" + G + r"\s+(?:must|should|need to|will|deserve to)\s+(?:all\s+)?"
           r"(?:die|burn|hang|be (?:killed|gassed|shot|burned|burnt|hanged|exterminated|wiped out))$|^(?:all\s+)?"
           r"(?:the\s+)?" + G + r"\s+deserves?\s+(?:death|to die)$")
IT = (r"^(?:uccidi|uccidete|ammazza|ammazzate|bruciate|brucia|impiccate|sterminate|sparate a)\s+(?:tutt[ie]\s+)?"
      r"(?:(?:i|gli|le|quei|quegli)\s+)?" + GIT + r"$|\bmorte\s+(?:a|ai|agli|alle)\s+(?:tutt[ie]\s+)?(?:(?:i|gli|le)\s+)?"
      + GIT + r"$")
ES = (r"^(?:matar|maten|mata|matad|quemen|quemar|quemad|exterminar|exterminen)\s+(?:a\s+)?(?:tod[oa]s\s+)?"
      r"(?:(?:los|las)\s+)?" + GES + r"$|\bmuerte\s+a\s+(?:tod[oa]s\s+)?(?:(?:los|las)\s+)?" + GES + r"$")
INCITE2 = re.compile("|".join((EN_CALL, EN_DEATH, EN_POST, IT, ES)))
SEGMENT = re.compile(r"\s[-|–—]\s|[()\[\]{}!?.,:;\"]+|\s{2,}")


def _fold(s):
    s = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", s))
    return "".join(c for c in s if not unicodedata.combining(c))


def segments(text):
    t = _fold(text or "")
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)                # #KillAllMuslims -> Kill All Muslims
    for seg in SEGMENT.split(t):
        seg = re.sub(r"[-_/#]+", " ", seg.replace("'", "").replace("\u2019", ""))
        seg = re.sub(r"(?<=\s)2(?=\s)", "to", " " + seg + " ")
        seg = chat.normalise(seg)                              # lower, de-leet, letters only
        if seg:
            yield seg


def incitement(text):
    return any(INCITE2.search(s) for s in segments(text))
