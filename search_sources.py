"""Where he searches (#56): more free search sources, picked per query by topic, rotated and rate-limited per host.

Sources (no key, no login, nothing paid): Bing (SafeSearch strict), DuckDuckGo HTML (kp=1, strict), Wikipedia search,
Wikimedia Commons (images), arXiv listing search, Hacker News (the Algolia API), Open Library subject pages, YouTube
search pages (Restricted Mode, as #53), and two sites searched through their own search box (#40's `site_search`):
RecipeTin Eats (recipes) and Science News (news). Each query is routed by topic (science -> arXiv, a book -> Open
Library, how-to -> DuckDuckGo, ...) and the least used source among the fitting ones wins, so no engine gets heavy
traffic. Every host is limited to PER_HOST_HOUR requests per rolling hour, robots.txt is respected (fetched once a day
per host; Open Library's /search and AP News' search page are disallowed there, which is why Open Library is searched
by subject and the news site is Science News), and every count is kept per Tokyo day for /api/browsing.

Everything here is pure (parsing, routing, limits, query building): browse.py does the network through Chromium and
still runs the guard on every result, page and title. The parsers read saved HTML / JSON in tests (no network in CI).

Queries come from him (`interest_for`): his reading notes (mind.next_interest), what he was reading, words viewers
taught him, topics his tastes favour, and viewer wishes in chat ("look up ...", `wish`). On a page, `follow_ups` builds
up to 2 searches from the page's own words (names, an unknown term: "what is ...?").
"""
import base64
import html as htmlmod
import json
import random
import re
import time
import urllib.parse
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

PER_HOST_HOUR = 20                  # requests per rolling hour per host (searches, API calls, robots.txt)
MAX_RESULTS = 10
ROBOTS_TTL_S = 86400.0
ROBOTS_RETRY_S = 600.0              # a robots.txt that could not be read refuses the host for 10 min only
UA_TOKEN = "Mozilla"                # robots.txt rules are read for a generic browser ('*' unless Mozilla is named)


# --- a tiny HTML tree (stdlib only) ----------------------------------------------------------------------------------
BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th", "ul", "ol", "section",
         "article", "header", "footer", "dd", "dt", "figcaption", "blockquote", "table"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag, self.attrs, self.children, self.parent = tag, dict(attrs or {}), [], parent

    def cls(self):
        return (self.attrs.get("class") or "").split()

    def has_class(self, prefix):
        """A class equal to `prefix` or starting with it (CSS-module names carry a hash: title___vyz1w)."""
        return any(c == prefix or c.startswith(prefix + "_") for c in self.cls())

    def iter(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.iter()

    def find_all(self, tag=None, cls=None):
        return [n for n in self.iter() if (tag is None or n.tag == tag) and (cls is None or n.has_class(cls))]

    def find(self, tag=None, cls=None):
        return next((n for n in self.iter() if (tag is None or n.tag == tag) and (cls is None or n.has_class(cls))),
                    None)

    def text(self):
        out = []
        for c in self.children:
            if isinstance(c, Node):
                if c.tag in BLOCK:
                    out.append(" " + c.text() + " ")
                elif c.tag not in ("script", "style", "noscript", "template"):
                    out.append(c.text())
            else:
                out.append(c)
        return " ".join("".join(out).split())


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, [(k, v or "") for k, v in attrs], self.cur)
        self.cur.children.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(Node(tag, [(k, v or "") for k, v in attrs], self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:          # an end tag with no open element is ignored
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def parse_html(text):
    b = _Builder()
    try:
        b.feed(text or "")
        b.close()
    except Exception:                                       # broken markup: keep what was read
        pass
    return b.root


def _clean(s, n=200):
    return " ".join(htmlmod.unescape(str(s or "")).split())[:n]


def _result(url, title, snippet="", **extra):
    return dict({"url": url, "title": _clean(title, 140), "snippet": _clean(snippet, 240)}, **extra)


def _dedup(results, n=MAX_RESULTS):
    seen, out = set(), []
    for r in results:
        if r["url"] and r["title"] and r["url"] not in seen and r["url"].startswith(("http://", "https://")):
            seen.add(r["url"])
            out.append(r)
    return out[:n]


# --- parsers: page HTML or API JSON -> [{url, title, snippet}] -------------------------------------------------------
def bing_target(href):
    """Bing wraps results in bing.com/ck/a?...&u=a1<base64url>: the real target, or the href itself."""
    u = urllib.parse.urlsplit(href)
    if (u.hostname or "").endswith("bing.com") and u.path.startswith("/ck/"):
        v = urllib.parse.parse_qs(u.query).get("u", [""])[0]
        if v.startswith("a1"):
            try:
                return base64.urlsafe_b64decode(v[2:] + "=" * (-len(v[2:]) % 4)).decode("utf-8", "replace")
            except ValueError:
                return ""
        return ""
    return href


def parse_bing(text, base=""):
    out = []
    for li in parse_html(text).find_all("li", "b_algo"):
        h2 = li.find("h2")
        a = h2.find("a") if h2 else None
        if not a:
            continue
        cap = li.find("p", "b_lineclamp") or li.find("div", "b_caption")
        snippet = re.sub(r"^.{0,20}?\d{4}\s*·\s*", "", cap.text()) if cap else ""
        out.append(_result(bing_target(htmlmod.unescape(a.attrs.get("href", ""))), a.text(), snippet))
    return _dedup(out)


def ddg_target(href):
    """DuckDuckGo HTML links go through //duckduckgo.com/l/?uddg=<url>: the real target."""
    u = urllib.parse.urlsplit(urllib.parse.urljoin("https://html.duckduckgo.com/", href))
    if (u.hostname or "").endswith("duckduckgo.com"):
        return urllib.parse.parse_qs(u.query).get("uddg", [""])[0]
    return u.geturl()


def parse_ddg(text, base=""):
    out = []
    for res in parse_html(text).find_all("div", "result"):
        if res.has_class("result--ad") or "result--ad" in res.cls():
            continue                                        # ads are never results
        a = res.find("a", "result__a")
        if not a:
            continue
        sn = res.find(None, "result__snippet")
        out.append(_result(ddg_target(a.attrs.get("href", "")), a.text(), sn.text() if sn else ""))
    return _dedup(out)


def _mediawiki(text, base):
    out = []
    for li in parse_html(text).find_all("li", "mw-search-result"):
        head = li.find("div", "mw-search-result-heading")
        a = head.find("a") if head else None
        if not a:
            continue
        sn = li.find("div", "searchresult")
        out.append(_result(urllib.parse.urljoin(base, a.attrs.get("href", "")), a.text(), sn.text() if sn else ""))
    return _dedup(out)


def parse_wikipedia(text, base="https://en.wikipedia.org/"):
    return _mediawiki(text, base or "https://en.wikipedia.org/")


def parse_commons(text, base="https://commons.wikimedia.org/"):
    out = _mediawiki(text, base or "https://commons.wikimedia.org/")
    for r in out:                                           # "File:Inokasira Park.jpg" -> "Inokasira Park"
        name = r["title"].removeprefix("File:")
        r["title"] = re.sub(r"\.(jpe?g|png|gif|svg|tiff?|webp)$", "", name, flags=re.I).strip()
        r["image"] = True
    return out


def parse_arxiv(text, base="https://arxiv.org/"):
    out = []
    for li in parse_html(text).find_all("li", "arxiv-result"):
        t = li.find("p", "title")
        a = next((x for x in li.find_all("a") if "/abs/" in x.attrs.get("href", "")), None)
        if not t or not a:
            continue
        ab = li.find("span", "abstract-short") or li.find("p", "abstract")
        snippet = re.sub(r"\s*▽ More$", "", ab.text()) if ab else ""
        out.append(_result(urllib.parse.urljoin(base, a.attrs["href"]), t.text(), snippet))
    return _dedup(out)


def parse_hn(text, base=""):
    """The Algolia API's JSON: stories with their link (else the HN thread)."""
    try:
        hits = json.loads(text).get("hits") or []
    except (ValueError, AttributeError):
        return []
    out = []
    for h in hits:
        if not isinstance(h, dict) or not h.get("title"):
            continue
        thread = f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
        pts = h.get("points")
        out.append(_result(h.get("url") or thread, h["title"],
                           f"{pts} points on Hacker News" if isinstance(pts, int) else "Hacker News"))
    return _dedup(out)


def parse_openlibrary(text, base="https://openlibrary.org/"):
    """A subject's JSON (/subjects/<slug>.json): its works with their authors."""
    try:
        works = json.loads(text).get("works") or []
    except (ValueError, AttributeError):
        return []
    out = []
    for w in works:
        if not isinstance(w, dict) or not w.get("title") or not str(w.get("key", "")).startswith("/works/"):
            continue
        authors = ", ".join(a.get("name", "") for a in (w.get("authors") or [])[:2] if isinstance(a, dict))
        year = w.get("first_publish_year")
        out.append(_result(urllib.parse.urljoin("https://openlibrary.org/", w["key"]), w["title"],
                           " · ".join(x for x in (authors, str(year) if year else "") if x)))
    return _dedup(out)


YT_DATA = re.compile(r"(?:var ytInitialData|window\[\"ytInitialData\"\])\s*=\s*(\{.+?\});\s*</script>", re.S)


def parse_youtube(text, base=""):
    """A YouTube results page: the videos in its ytInitialData (title, channel, length)."""
    m = YT_DATA.search(text or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    found = []

    def walk(o, depth=0):
        if depth > 40 or len(found) >= 3 * MAX_RESULTS:
            return
        if isinstance(o, dict):
            if isinstance(o.get("videoRenderer"), dict):
                found.append(o["videoRenderer"])
            for v in o.values():
                walk(v, depth + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, depth + 1)
    walk(data)

    def runs(x):
        return "".join(r.get("text", "") for r in (x or {}).get("runs", []) if isinstance(r, dict))
    out = []
    for v in found:
        vid = v.get("videoId")
        if not vid or not re.fullmatch(r"[\w-]{6,20}", str(vid)):
            continue
        meta = [runs(v.get("ownerText")), (v.get("lengthText") or {}).get("simpleText", "")]
        out.append(_result(f"https://www.youtube.com/watch?v={vid}", runs(v.get("title")),
                           " · ".join(x for x in meta if x), channel=runs(v.get("ownerText")), video=True))
    return _dedup(out)


def parse_headlines(text, base):
    """A site's own search results (site_search): article links in headings on the same site."""
    host = urllib.parse.urlsplit(base).hostname or ""
    out = []
    for h in parse_html(text).iter():
        if h.tag not in ("h1", "h2", "h3", "h4"):
            continue
        a = h.find("a")
        if not a:
            continue
        url = urllib.parse.urljoin(base, a.attrs.get("href", ""))
        u = urllib.parse.urlsplit(url)
        if (u.hostname or "") != host or u.path in ("", "/") or u.query:
            continue
        box = h.parent
        sn = ""
        for _ in range(3):                                  # an excerpt next to the heading, if there is one
            if box is None:
                break
            p = box.find("p")
            if p and p.text() and p.text() != a.text():
                sn = p.text()
                break
            box = box.parent
        out.append(_result(url, a.text(), sn))
    return _dedup(out)


# --- sources ---------------------------------------------------------------------------------------------------------
def _q(params):
    return urllib.parse.urlencode(params)


def ol_slug(q):
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in BOOK_WORDS]
    return "_".join(words[:3])


BOOK_WORDS = {"book", "books", "novel", "novels", "read", "reading", "author", "authors", "by", "about", "the", "a",
              "of", "best", "good", "story", "stories", "literature"}

SOURCES = {
    # name: label shown on the card, how to reach the results, the parser, host(s) used
    "bing": {"label": "Bing", "url": lambda q: "https://www.bing.com/search?" + _q({"q": q, "adlt": "strict",
                                                                                   "setlang": "en"}),
             "parse": parse_bing},
    "ddg": {"label": "DuckDuckGo", "url": lambda q: "https://html.duckduckgo.com/html/?" + _q({"q": q, "kp": "1"}),
            "parse": parse_ddg},
    "wikipedia": {"label": "Wikipedia", "url": lambda q: "https://en.wikipedia.org/w/index.php?" + _q(
        {"search": q, "fulltext": "1", "ns0": "1"}), "parse": parse_wikipedia},
    "commons": {"label": "Wikimedia Commons", "url": lambda q: "https://commons.wikimedia.org/w/index.php?" + _q(
        {"search": q, "fulltext": "1", "ns6": "1"}), "parse": parse_commons},
    "arxiv": {"label": "arXiv", "url": lambda q: "https://arxiv.org/search/?" + _q({"query": q, "searchtype": "all"}),
              "parse": parse_arxiv},
    "hn": {"label": "Hacker News", "url": lambda q: "https://hn.algolia.com/?" + _q({"q": q, "type": "story"}),
           "api": lambda q: "https://hn.algolia.com/api/v1/search?" + _q({"query": q, "tags": "story",
                                                                           "hitsPerPage": "20"}),
           "parse": parse_hn},
    "openlibrary": {"label": "Open Library", "url": lambda q: f"https://openlibrary.org/subjects/{ol_slug(q)}",
                    "api": lambda q: f"https://openlibrary.org/subjects/{ol_slug(q)}.json?limit=12",
                    "parse": parse_openlibrary},
    "youtube": {"label": "YouTube", "url": lambda q: "https://www.youtube.com/results?" + _q({"search_query": q}),
                "parse": parse_youtube},
    # sites searched through their own search box (site_search): the home page is opened, the query typed there
    "recipes": {"label": "RecipeTin Eats", "site": "https://www.recipetineats.com/", "parse": parse_headlines},
    "news": {"label": "Science News", "site": "https://www.sciencenews.org/", "parse": parse_headlines},
}
GENERAL = ("ddg", "bing", "wikipedia")      # any query; the topic sources come first when they fit

# topic -> the sources that fit it, best first (a query can match several topics)
TOPICS = [
    ("science", re.compile(r"\b(brain|neuro\w*|neuron\w*|sleep|spindle\w*|dream\w*|memory|cortex|physics|quantum|"
                           r"particle\w*|galax\w*|black holes?|cosmolog\w*|astro\w*|genom\w*|genes?|protein\w*|cells?|"
                           r"evolution|climate|algorithm\w*|mathemat\w*|theorem|equation\w*|machine learning|"
                           r"neural network\w*|robot\w*|chemistry|molecul\w*|biolog\w*|ecolog\w*|research|study|"
                           r"studies|paper)\b", re.I), ("arxiv", "news", "wikipedia")),
    ("news", re.compile(r"\b(news|today|latest|this week|discover\w*|found|new study|scientists?|announce\w*)\b",
                        re.I), ("news", "ddg")),
    ("book", re.compile(r"\b(books?|novels?|authors?|poetry|poems?|fiction|manga|murakami|literature|reading list|"
                        r"haiku)\b", re.I), ("openlibrary", "wikipedia")),
    ("howto", re.compile(r"\b(how to|how do|how does|why do|why does|tips?|guide|tutorial|diy|make|fix|learn)\b",
                         re.I), ("ddg", "bing")),
    ("recipe", re.compile(r"\b(recipes?|cook\w*|bak\w*|bread|ramen|noodles?|soup|curry|cake|pastry|sourdough|"
                          r"onigiri|melon ?pan|dessert|dinner|lunch|breakfast|sauce|dumplings?|sushi|tempura|miso)\b",
                          re.I), ("recipes", "ddg")),
    ("images", re.compile(r"\b(photos?|pictures?|images?|paintings?|art|architecture|park|temple|shrine|map|maps|"
                          r"view|landscape|skyline|station|bridge|garden|museum)\b", re.I), ("commons", "wikipedia")),
    ("tech", re.compile(r"\b(programming|software|code|coding|python|rust|linux|computer\w*|startup\w*|internet|"
                        r"web|keyboard\w*|hacker\w*|open source|database\w*|compiler\w*|gpu)\b", re.I),
     ("hn", "ddg")),
    ("video", re.compile(r"\b(videos?|watch|music|songs?|lo-?fi|concert|documentary|walk|vlog|trailer|anime|"
                         r"ghibli)\b", re.I), ("youtube", "ddg")),
    ("encyclopedia", re.compile(r"\b(what is|who is|who was|history of|meaning of|definition|origin of|wiki)\b",
                                re.I), ("wikipedia", "ddg")),
]


def topics_of(q):
    return [name for name, rx, _ in TOPICS if rx.search(q or "")]


def host_of(name):
    s = SOURCES[name]
    return urllib.parse.urlsplit(s.get("site") or s["url"]("x")).hostname


def hosts_of(name):
    """Every host a search on this source touches (the results page and its API)."""
    s = SOURCES[name]
    out = {host_of(name)}
    if s.get("api"):
        out.add(urllib.parse.urlsplit(s["api"]("x")).hostname)
    return out


# --- per-host rate limits and per-source counts ----------------------------------------------------------------------
def tokyo_day(t):
    from datetime import datetime
    try:
        from sleep import TZ
    except Exception:                                       # pragma: no cover - sleep.py is always there
        from zoneinfo import ZoneInfo
        TZ = ZoneInfo("Asia/Tokyo")
    return datetime.fromtimestamp(t, TZ).date().isoformat()


class Limits:
    """At most `per_host` requests per rolling hour to each host; searches counted per source per Tokyo day.
    to_dict / from_dict keep it across browser restarts (the live server saves it with the browsing log)."""

    def __init__(self, per_host=PER_HOST_HOUR, clock=time.time, state=None):
        self.per_host, self.clock = per_host, clock
        s = state or {}
        self.hits = {h: [float(t) for t in ts if isinstance(t, (int, float))]
                     for h, ts in (s.get("hits") or {}).items() if isinstance(ts, list)}
        self.day = s.get("day")
        self.today = {k: int(v) for k, v in (s.get("today") or {}).items() if isinstance(v, int)}
        self.refused = {k: int(v) for k, v in (s.get("refused") or {}).items() if isinstance(v, int)}
        self.last = list(s.get("last") or [])[-20:]          # recent searches: [{t, source, query, from}]
        self._roll()

    def _roll(self):
        now = self.clock()
        for h in list(self.hits):
            self.hits[h] = [t for t in self.hits[h] if now - t < 3600]
            if not self.hits[h]:
                del self.hits[h]
        day = tokyo_day(now)
        if day != self.day:
            self.day, self.today, self.refused = day, {}, {}

    def used(self, host):
        self._roll()
        return len(self.hits.get(host, []))

    def allow(self, host):
        return self.used(host) < self.per_host

    def note(self, host):
        """One request to `host` (a results page, an API call, a robots.txt)."""
        self._roll()
        self.hits.setdefault(host, []).append(self.clock())

    def source_ok(self, name):
        return all(self.allow(h) for h in hosts_of(name))

    def count(self, name, query="", origin=""):
        self._roll()
        self.today[name] = self.today.get(name, 0) + 1
        self.last = (self.last + [{"t": round(self.clock()), "source": name, "query": query[:60],
                                   "from": origin[:60]}])[-20:]

    def refuse(self, name, why):
        self._roll()
        key = f"{name}: {why}"
        self.refused[key] = self.refused.get(key, 0) + 1

    def recent(self, name):
        """Searches on this source in the last hour (rotation: the least used fitting source goes first)."""
        self._roll()
        now = self.clock()
        return sum(1 for x in self.last if x.get("source") == name and now - x.get("t", 0) < 3600)

    def to_dict(self):
        self._roll()
        return {"day": self.day, "today": dict(self.today), "refused": dict(self.refused),
                "hits": {h: [round(t, 1) for t in ts] for h, ts in self.hits.items()}, "last": self.last[-20:]}

    def public(self):
        """For /api/browsing: searches per source on this Tokyo day, requests per host in the last hour."""
        self._roll()
        return {"tokyo_day": self.day, "per_source_today": dict(sorted(self.today.items(), key=lambda kv: -kv[1])),
                "total_today": sum(self.today.values()),
                "labels": {k: SOURCES[k]["label"] for k in self.today if k in SOURCES},
                "per_host_last_hour": {h: len(ts) for h, ts in sorted(self.hits.items())},
                "per_host_limit": self.per_host, "refused_today": dict(self.refused),
                "recent": [dict(x, label=SOURCES.get(x.get("source"), {}).get("label", x.get("source")))
                           for x in self.last[-10:]]}


# --- robots.txt ------------------------------------------------------------------------------------------------------
class Robots:
    """robots.txt per host, fetched once a day by the browser (`fetch` is async: url -> (status, text)). A missing
    file (404) allows everything; 401/403 refuses the host for the day; a file that cannot be read (network error,
    5xx) refuses it for ROBOTS_RETRY_S."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.cache = {}                                     # host -> (RobotFileParser or True/False, expires)

    def known(self, host):
        c = self.cache.get(host)
        return c is not None and c[1] > self.clock()

    def load(self, host, status, text):
        ttl = ROBOTS_TTL_S
        if status == 200:
            rp = RobotFileParser()
            rp.parse((text or "").splitlines())
            v = rp
        else:
            v = status in (404, 410)                        # no file: everything allowed; 401/403/5xx: refused
            if status not in (401, 403, 404, 410):
                ttl = ROBOTS_RETRY_S                        # could not be read (network, 5xx): asked again soon
        self.cache[host] = (v, self.clock() + ttl)
        if len(self.cache) > 500:
            self.cache.pop(next(iter(self.cache)))
        return v

    def allowed(self, url):
        host = urllib.parse.urlsplit(url).hostname or ""
        c = self.cache.get(host)
        if c is None:
            return None                                     # not fetched yet
        v = c[0]
        if isinstance(v, bool):
            return v
        return v.can_fetch(UA_TOKEN, url)

    async def check(self, url, fetch, limits=None):
        """True / False for `url`, fetching the host's robots.txt first when needed (one request, rate-limited)."""
        u = urllib.parse.urlsplit(url)
        host = u.hostname or ""
        if not self.known(host):
            if limits is not None and not limits.allow(host):
                return False
            if limits is not None:
                limits.note(host)
            try:
                status, text = await fetch(f"{u.scheme}://{u.netloc}/robots.txt")
            except Exception:
                status, text = 0, ""
            self.load(host, status, text)
        return bool(self.allowed(url))


# --- routing ---------------------------------------------------------------------------------------------------------
def route(q, limits=None, rng=None, video=False):
    """Sources to try for query `q`, best first: the topic's sources, then the general engines, the least used ones
    first among sources that fit equally (rotation), sources over their per-host limit left out."""
    rng = rng or random.Random()
    score = {"youtube": 1.2} if video else {}
    for _, rx, srcs in TOPICS:
        if rx.search(q or ""):
            for i, s in enumerate(srcs):
                score[s] = max(score.get(s, 0.0), 1.0 if i == 0 else 0.6)
    for s in GENERAL:
        score.setdefault(s, 0.35)
    if not ol_slug(q or ""):
        score.pop("openlibrary", None)
    ranked = []
    for s, w in score.items():
        if limits is not None and not limits.source_ok(s):
            continue
        used = limits.recent(s) if limits is not None else 0
        ranked.append((w / (1.0 + 0.5 * used) * (0.8 + 0.4 * rng.random()), s))
    ranked.sort(reverse=True)
    return [s for _, s in ranked]


# --- queries from him ------------------------------------------------------------------------------------------------
WISH = re.compile(r"^\s*(?:@?sub-?01[,:]?\s*)?(?:(?:can|could|would) you\s+|please\s+|pls\s+)?"
                  r"(?:look\s*up|search(?:\s+for)?|google|find(?:\s+out)?(?:\s+about)?|read\s+about|check\s+out|"
                  r"what\s+(?:is|are)|who\s+(?:is|was)|tell\s+me\s+about)\s+(.{2,80}?)\s*[?.!]*\s*$", re.I)
WISH_STRIP = re.compile(r"^(?:the|a|an|some|about)\s+|\s+(?:please|pls|for me|for us)$", re.I)


def wish(text):
    """A viewer's wish in chat ("look up melon pan", "what is a sleep spindle?") -> the query, else None. The query
    still goes through eyes.query_ok (the chat filter, blocked words) before anything is searched."""
    m = WISH.match(text or "")
    if not m:
        return None
    q = m.group(1)
    for _ in range(2):
        q = WISH_STRIP.sub("", q.strip())
    return q or None


ORIGINS = {"mind": "from his reading notes", "reading": "from what he was reading",
           "taught": "a word a viewer taught him", "tastes": "a topic his tastes favour",
           "chat": "a viewer's wish in chat", "follow_up": "a follow-up from the page",
           "familiar": "something familiar", "page": "picked on the page"}


def interest_text(interest):
    """The plain query of an interest (a string, or {"query", "from"} from interest_for)."""
    if isinstance(interest, dict):
        return str(interest.get("query") or "")
    return str(interest or "")


def interest_origin(interest):
    return ORIGINS.get(interest.get("from"), "") if isinstance(interest, dict) else ""


def interest_for(mind=(), reading=None, taught=(), tastes=(), rng=None, query_ok=None):
    """One query for the browser, drawn from his sources: the mind's memory-linked searches (weight 3), what he was
    reading (1), words viewers taught him (1.5), topics his tastes favour (1). -> {"query", "from"} or None."""
    rng = rng or random.Random()
    ok = query_ok or (lambda q: " ".join(str(q or "").split()) or None)
    pools = []
    m = [q for q in (ok(x.get("query") if isinstance(x, dict) else x) for x in (mind or [])) if q]
    if m:
        pools.append((3.0, "mind", m))
    if reading and (r := ok(reading)):
        pools.append((1.0, "reading", [r]))
    t = [q for q in (ok(x) for x in (taught or [])) if q]
    if t:
        pools.append((1.5, "taught", t))
    f = [q for q in (ok(x) for x in (tastes or [])) if q]
    if f:
        pools.append((1.0, "tastes", f))
    if not pools:
        return None
    total = sum(w for w, _, _ in pools)
    x = rng.random() * total
    for w, origin, qs in pools:
        x -= w
        if x <= 0:
            break
    return {"query": rng.choice(qs) if origin != "mind" else qs[min(len(qs) - 1, int(rng.random() ** 2 * len(qs)))],
            "from": origin}


def live_interest(live, art=None, rng=None):
    """interest_for from the live server's state (a few attributes, read defensively)."""
    from eyes import query_ok
    mind_q = []
    try:
        if getattr(live, "mind", None):
            live.mind_interest()                            # refreshes the cached next_interest() (every minute)
            mind_q = [x.get("query") for x in (live.interest[1] or []) if isinstance(x, dict)]
    except Exception:
        mind_q = []
    taught = []
    try:
        cutoff = live.clock.now() - 2 * 86400
        taught = [m.get("text") for m in live.memory.items if m.get("source") == "taught" and m.get("t", 0) > cutoff]
    except Exception:
        pass
    liked = []
    try:
        liked = [f["topic"] for f in live.tastes.top(n=8)["favoured"] if f.get("kind") == "word"][:5]
    except Exception:
        pass
    return interest_for(mind_q, art["title"] if art else None, taught[-10:], liked, rng=rng, query_ok=query_ok)


# --- follow-up searches from a page's own words ----------------------------------------------------------------------
ENTITY = re.compile(r"\b([A-Z][a-z]{2,}(?:[ -](?:of |de |no |the )?[A-Z][a-z]{2,}){1,2})\b")
CAP_STOP = {"The", "This", "That", "These", "Those", "There", "Their", "They", "When", "Where", "What", "Which",
            "While",
            "After", "Before", "From", "With", "About", "Read", "More", "Sign", "Log", "Share", "Subscribe", "Click",
            "Home", "Menu", "Search", "Contact", "Privacy", "Terms", "Cookie", "Cookies", "Accept", "Advertisement",
            "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
            "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "Related", "Comments", "Image", "Photo", "Video", "Getty", "Images", "Updated", "Published", "Our", "You",
            "Your", "His", "Her", "Its", "New", "But", "And", "For", "How", "Why", "Who"}
COMMON = set("""about above after again against almost already also although always among another around because
become becomes before behind being below between beyond cannot could during either enough especially every everything
example following however including instead itself little might nothing often others other people perhaps please
rather really should since something sometimes still through though together toward towards under until usually
various whether which while within without would years important different another although actually available
business children community company country development government information interest national number problem
program question research service several social system through university student students million billion
percent article articles comment comments website online content privacy policy cookies newsletter subscribe
advertisement related latest popular reading continue""".split())


def follow_ups(page, n=2, query_ok=None, seen=()):
    """Up to `n` searches made from the page's own words: entity names (capitalised runs: "Inokashira Park") and an
    unknown term ("what is hypnagogia?": a long word repeated on the page, not a common one, not in the title).
    -> [{"query", "label", "kind"}]."""
    ok = query_ok or (lambda q: " ".join(str(q or "").split()) or None)
    title = page.get("title", "") or ""
    text = f"{title}. {page.get('text', '') or ''}"[:4000]
    tl = title.lower()
    have = {s.lower() for s in seen}
    out = []
    counts = {}
    for m in ENTITY.finditer(text):
        parts = m.group(1).split(" ")
        while parts and parts[0] in CAP_STOP:                # "The Ghibli Museum" -> "Ghibli Museum"
            parts = parts[1:]
        while parts and parts[-1] in CAP_STOP:
            parts = parts[:-1]
        if len(parts) < 2 and not (parts and "-" in parts[0]):
            continue
        e = " ".join(parts)
        counts[e] = counts.get(e, 0) + 1
    ents = [e for e in sorted(counts, key=lambda e: (-counts[e], len(e)))
            if e.lower() not in tl]                         # not the page's own subject
    for e in ents:
        q = ok(e)
        if q and q.lower() not in have:
            out.append({"query": q, "label": f"look up {q}", "kind": "entity"})
            have.add(q.lower())
            break
    words_ = re.findall(r"\b[a-z][a-z-]{8,}\b", text)
    wc = {}
    for w in words_:
        w = w.strip("-")
        if w in COMMON or w in tl or w.endswith(PLAIN_SUFFIXES) or len(w) > 22:
            continue
        wc[w] = wc.get(w, 0) + 1
    terms = sorted((w for w in wc if wc[w] >= 2), key=lambda w: (-wc[w], -len(w)))
    for w in terms:
        q = ok(f"what is {w}")
        if q and w not in have and not any(w in x["query"].lower() for x in out):
            out.append({"query": q, "label": f"what is {w}?", "kind": "term"})
            break
    for e in ents[1:]:                                      # no unknown term: a second name
        if len(out) >= n:
            break
        q = ok(e)
        if q and q.lower() not in have and all(q.lower() != x["query"].lower() for x in out):
            out.append({"query": q, "label": f"look up {q}", "kind": "entity"})
            have.add(q.lower())
    return out[:n]


PLAIN_SUFFIXES = ("ing", "ings", "ly", "ed", "tion", "tions", "sion", "sions", "ment", "ments", "ness", "able", "ible",
                  "ity", "ities", "ance", "ence", "ers", "ful", "less", "ships", "ship")
FOLLOW_LABEL = re.compile(r"^(look up .+|what is .+\?)$", re.I)
