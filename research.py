"""What SUB-01 reads at the computer: a curiosity chain on Wikipedia.

While the life simulation is in the "research" activity, every READ_EVERY_S simulated seconds the character opens
one article: a word from recent chat if there is a fresh one, otherwise a link from the article it read last
(curiosity drifts from page to page). Only the public Wikipedia API is used (text under CC BY-SA 4.0, credited with
a link on the page); no other website is visited and nothing is posted anywhere. Articles about violence, sex,
self-harm, drugs, extremism, finance and real living people's private matters are skipped.
"""
import json
import random
import re
import time
import urllib.parse
import urllib.request

API = "https://{lang}.wikipedia.org/w/api.php"
SUMMARY = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
UA = "SUB-01/1.0 (simulated reader; https://github.com/nocontentinhere4-art/sub-01)"
READ_EVERY_S = 4 * 60                 # simulated seconds per article while researching
KEEP = 40                             # articles kept in the reading log
BLOCK = re.compile(
    r"murder|killing|massacre|genocide|terror|suicide|self.?harm|rape|sexual|porn|nude|drug|cocaine|heroin|"
    r"weapon|firearm|bomb|shooting|war crime|nazi|extremis|abuse|torture|execution|cannibal|"
    r"stock|crypto|bitcoin|token|price|trading|casino|gambling|scandal|death of|assassination", re.I)
STOP = set("the a an and or but if of to in on at for with from by is are was were be been it this that these those "
           "i you he she we they me my your his her our their what why how who when where which not no yes so very "
           "just can will would could should do does did have has had il lo la i gli le un una e o ma di da in con su "
           "per tra fra che chi non si sono sei è era ciao hello hi lol ok".split())


def get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def safe(title, text=""):
    return not BLOCK.search(title) and not BLOCK.search(text[:600])


def search(word, lang="en"):
    q = urllib.parse.urlencode({"action": "opensearch", "search": word, "limit": 5, "namespace": 0, "format": "json"})
    titles = get(API.format(lang=lang) + "?" + q)[1]
    return [t for t in titles if safe(t)]


def links(title, lang="en"):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "links", "plnamespace": 0,
                                "pllimit": 200, "format": "json"})
    pages = get(API.format(lang=lang) + "?" + q).get("query", {}).get("pages", {})
    out = [l["title"] for p in pages.values() for l in p.get("links", [])]
    return [t for t in out if safe(t) and not re.match(r"^(List of|Index of|Outline of|\d{3,4}\b)", t)]


def summary(title, lang="en"):
    d = get(SUMMARY.format(lang=lang, title=urllib.parse.quote(title.replace(" ", "_"), safe="")))
    if d.get("type") not in ("standard", None) or not d.get("extract"):
        return None
    if not safe(d.get("title", title), d.get("extract", "")):
        return None
    return {"title": d.get("title", title), "extract": d["extract"][:420],
            "url": d.get("content_urls", {}).get("desktop", {}).get("page", ""), "lang": lang}


def words(text):
    return [w for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", text.lower()) if w not in STOP]


class Reader:
    def __init__(self, state=None, rng=None):
        s = state or {}
        self.log = s.get("log", [])          # [{t, title, extract, url, why}]
        self.used = set(s.get("used", []))   # chat messages already turned into a search
        self.next_t = 0.0
        self.rng = rng or random.Random()

    def to_dict(self):
        return {"log": self.log[-KEEP:], "used": list(self.used)[-200:]}

    def current(self):
        return self.log[-1] if self.log else None

    def due(self, t):
        return t >= self.next_t

    def read(self, t, heard):
        """Open one article (blocking: run in a worker thread). `heard` = recent chat texts, newest last."""
        self.next_t = t + READ_EVERY_S
        seen = {e["title"] for e in self.log}
        tries = []
        for text in reversed(heard[-5:]):
            if text in self.used:
                continue
            self.used.add(text)
            for w in sorted(words(text), key=len, reverse=True)[:3]:
                tries.append((w, f"from chat: “{text[:60]}”"))
            break
        last = self.current()
        try:
            for w, why in tries:
                for title in search(w):
                    if title not in seen and (art := summary(title)):
                        return self._add(t, art, why)
            if last:
                options = [x for x in links(last["title"]) if x not in seen]
                self.rng.shuffle(options)
                for title in options[:6]:
                    if art := summary(title):
                        return self._add(t, art, f"followed a link from “{last['title']}”")
            for title in ("Tokyo", "Kichijōji", "Inokashira Park", "Sleep", "Dream", "Bread", "Memory"):
                if title not in seen and (art := summary(title)):
                    return self._add(t, art, "started somewhere familiar")
        except Exception as e:                    # offline or rate-limited: try again next time
            print("research: wikipedia failed:", repr(e)[:120], flush=True)
        return None

    def _add(self, t, art, why):
        art = dict(art, t=t, why=why)
        self.log = (self.log + [art])[-KEEP:]
        return art
