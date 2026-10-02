"""What a young man in Kichijōji browses (#56, scope extension): an interest profile, a daily rhythm, and variety.

The owner: "He focuses too much on one topic. He should be like a real person: watch YouTube and TikTok videos, search
for things he saw, memecoins and stocks for example. No guy like him would spend all day on Wikipedia."

- PROFILE: seed weights per topic (edit them here, in one place) with a few searches each and the words that mark a
  page as being about it. His tastes (#38, tastes.py) move a topic's weight between 0.5x and 1.6x over days; they
  never collapse it to one topic.
- RHYTHM by Tokyo hour: morning news and the weather, short videos at lunch, his interests in the afternoon, YouTube
  and games in the evening, Shorts on the phone late at night. The rhythm only tilts the weights and the feed; his
  boredom and the brain vote still choose.
- Variety: no quota is imposed from outside (owner, "NO RESTRICTIONS"). A topic that already filled a large share of
  today's pages weighs less (`saturation`), Wikipedia too, and after 3-4 pages in a row on one topic the leave
  option pulls harder (`streak_pull`, added to the vote's leave pull), so he does not get stuck on one topic.
- Novelty (#89, owner): a topic seen in the last RECENT_S (2 h) weighs RECENT_W (x0.15); a query is not typed
  again for QUERY_GAP_S (a day; a page or video is never reopened within 7 days, novelty.py); `pick(discover=True)` (most shorts, and follow-ups over their quarter) takes a
  topic not seen in the last 2 h, from the profile or from discovery: headlines he saw on front pages (`offer`,
  "trending") and a wide DISCOVERY pool of things outside his usual topics.
Pure: no network, no AI. browse.py keeps a Variety per screen session and asks `pick` what to look up next.
"""
import math
import random
import re
import time

# topic: seed weight, searches he might type, words that mark a page as being about the topic
PROFILE = {
    "music": (1.0, ["new japanese indie songs", "city pop playlist", "lo-fi hip hop", "Tokyo live house tonight",
                    "best albums this year", "vaporwave"],
              r"music|songs?|album|playlist|band|concert|live house|lo-?fi|city pop|singer|rapper|spotify|bandcamp"),
    "anime": (1.0, ["new anime this season", "Chainsaw Man", "One Piece latest chapter", "Studio Ghibli",
                    "manga recommendations", "Frieren"],
              r"anime|manga|ghibli|one piece|crunchyroll|otaku|cosplay|frieren|chainsaw man|jujutsu"),
    "games": (1.0, ["Nintendo Switch new games", "speedrun world record", "Elden Ring", "indie games",
                    "retro games Akihabara", "Pokemon"],
              r"games?|gaming|nintendo|playstation|xbox|steam|esports?|speedrun|pokemon|elden ring|gamer"),
    "sports": (0.8, ["J League results", "Yomiuri Giants", "Shohei Ohtani", "Premier League highlights",
                     "Japan national football team", "Tokyo marathon"],
               r"football|soccer|baseball|j ?league|ohtani|giants|swallows|premier league|world cup|marathon|npb"),
    "food": (1.1, ["best ramen in Kichijoji", "Tokyo ramen ranking", "melon pan recipe", "convenience store snacks",
                   "Tokyo street food", "onigiri recipe"],
             r"ramen|sushi|recipe|bakery|bread|food|restaurant|izakaya|onigiri|snack|konbini|curry|noodles?"),
    "fashion": (0.7, ["streetwear Harajuku", "new sneaker releases", "Uniqlo collaboration", "vintage clothes Koenji",
                      "Nike Air Max"],
                r"streetwear|sneakers?|fashion|harajuku|uniqlo|outfit|nike|adidas|vintage clothes|koenji"),
    "tech": (1.0, ["new iPhone", "best budget headphones", "mechanical keyboards", "Raspberry Pi projects",
                   "AI news", "gadgets Akihabara"],
             r"iphone|android|gadgets?|headphones|keyboard|laptop|raspberry pi|tech|ai news|smartphone|camera"),
    "memes": (0.9, ["internet memes this week", "funny cat videos", "YouTube creators Japan", "viral videos",
                    "reddit todayilearned"],
              r"memes?|viral|funny|youtubers?|creators?|streamer|reddit|internet culture|tiktok"),
    "crypto": (0.7, ["memecoin news", "bitcoin price", "solana memecoins", "crypto market today", "dogecoin news"],
               r"crypto|bitcoin|ethereum|solana|memecoins?|dogecoin|token|blockchain|altcoin|dex|coin"),
    "markets": (0.6, ["Nikkei 225 today", "stock market news", "Toyota stock", "yen dollar exchange rate",
                      "Nasdaq today"],
                r"stocks?|nikkei|nasdaq|dow jones|s&p 500|shares|markets?|earnings|yen|exchange rate|topix"),
    "tokyo": (1.0, ["Tokyo weather today", "events in Tokyo this weekend", "Kichijoji", "Inokashira Park",
                    "Tokyo travel tips", "Shimokitazawa"],
              r"tokyo|kichijoji|shibuya|shinjuku|harajuku|akihabara|inokashira|weather|festival|matsuri|japan"),
    "science": (0.7, ["how the brain works", "sleep science", "space news", "deep sea creatures",
                      "why do cats purr"],
                r"science|brain|sleep|space|nasa|physics|biology|research|study|planet|dinosaur"),
    "wikipedia": (0.35, ["random article"], r"wikipedia"),
}
WIKI_HOST = re.compile(r"(^|\.)wikipedia\.org$", re.I)
_TOPIC_RX = {k: re.compile(r"\b(" + v[2] + r")\b", re.I) for k, v in PROFILE.items()}

# Tokyo hour -> (name, tilt per topic, feed on the phone, how much video sources are favoured)
RHYTHM = [
    (6, 11, "morning", {"tokyo": 1.8, "markets": 1.5, "crypto": 1.3, "science": 1.2, "sports": 1.2}, None, 0.0),
    (11, 14, "lunch", {"memes": 1.6, "food": 1.7, "music": 1.3, "anime": 1.2}, "shorts", 0.6),
    (14, 18, "afternoon", {"tech": 1.3, "science": 1.2, "fashion": 1.2, "anime": 1.1, "games": 1.1}, None, 0.2),
    (18, 23, "evening", {"games": 1.8, "music": 1.4, "anime": 1.4, "sports": 1.4, "memes": 1.2}, None, 0.7),
    (23, 30, "late night", {"memes": 1.6, "music": 1.4, "anime": 1.3, "games": 1.2}, "shorts", 0.8),
    (30, 30, "early", {}, None, 0.0),
]
STREAK_FROM = 3                    # pages in a row on one topic before the leave option pulls harder
SATURATION = 4.0                   # how fast a topic's weight falls with its share of today's pages
FREE_SHARE = 0.15                  # shares below this cost nothing
WIKI_FREE = 0.10
RECENT_S = 2 * 3600                # a topic seen this recently weighs RECENT_W (#89)
RECENT_W = 0.15
QUERY_GAP_S = 86400                # a query is not typed again within a day (pages: 7 days, novelty.py)
FOLLOW_SHORTS = 0.3                # shorts on his own interest / what he saw; the rest discovery (>= 60 % new topics)
TRENDING_KEEP = 40
# discovery: subjects outside his usual topics (one query each, each its own topic "discover:<words>")
DISCOVERY = ["axolotl facts", "how glass is made", "bonsai for beginners", "deep sea anglerfish", "origami crane",
             "Antarctica research station life", "how lighthouses work", "volcano eruption footage", "bee dance",
             "kintsugi repair", "Iceland northern lights", "how vinyl records are made", "street magic tricks",
             "octopus intelligence", "skateboard tricks", "parkour Tokyo", "calligraphy shodo", "Japanese carpentry joints",
             "train driver cab view", "how sushi knives are forged", "sumo training morning", "capybara onsen",
             "tsunami stone markers", "lucid dreaming tips", "speed cubing", "mechanical watch movement",
             "drone racing", "chess blunders", "how elevators work", "giant squid", "jellyfish aquarium",
             "glassblowing", "blacksmith forging", "pottery wheel", "aurora timelapse", "storm chasing",
             "bioluminescent waves", "tardigrades", "mushroom foraging", "beekeeping", "ice cave", "desert night sky",
             "magnetic slime", "domino toppling", "marble run", "satisfying cleaning", "miniature cooking",
             "abandoned places Japan", "cherry blossom forecast", "taiko drumming", "kendama tricks", "yo-yo world champion",
             "beatbox", "a cappella cover", "street piano", "busking Shibuya", "breakdance battle", "jazz drummer solo",
             "orchestra behind the scenes", "film photography", "polaroid tips", "darkroom printing", "pixel art",
             "stop motion animation", "claymation", "3D printing fails", "robot dog", "Mars rover", "ISS live",
             "rocket launch", "solar eclipse", "meteor shower", "black hole image", "cats vs cucumbers",
             "shiba inu", "red panda", "penguin parade", "sea otters holding hands", "owl cafe", "deer in Nara",
             "snow monkeys", "how ramen noodles are made", "wagashi sweets", "latte art", "coffee roasting",
             "matcha ceremony", "fermented foods", "knife sharpening", "fixing old electronics", "restoring rusty tools",
             "tiny house tour", "capsule hotel tour", "Tokyo apartment tour", "night bus Japan", "ferry Seto Inland Sea",
             "Okinawa beaches", "Hokkaido snow festival", "Kyoto autumn leaves", "Fuji climbing", "onsen etiquette"]


def rhythm(hour):
    """-> {name, tilt, feed, video} for a Tokyo hour (0..24)."""
    h = float(hour) % 24
    h2 = h + 24 if h < 6 else h
    for a, b, name, tilt, feed, video in RHYTHM:
        if a <= h2 < b:
            return {"name": name, "tilt": dict(tilt), "feed": feed, "video": video}
    return {"name": "early", "tilt": {}, "feed": None, "video": 0.0}


def tokyo_hour(t=None):
    from datetime import datetime
    try:
        from sleep import TZ
    except Exception:                                       # pragma: no cover
        from zoneinfo import ZoneInfo
        TZ = ZoneInfo("Asia/Tokyo")
    d = datetime.fromtimestamp(time.time() if t is None else t, TZ)
    return d.hour + d.minute / 60


def topic_of(text, host=""):
    """The profile topic a page / query is about (most matching words), or None."""
    if WIKI_HOST.search((host or "").rstrip(".")):
        best = topic_of(text)
        return best or "wikipedia"
    t = text or ""
    scores = {k: len(rx.findall(t)) for k, rx in _TOPIC_RX.items() if k != "wikipedia"}
    k = max(scores, key=lambda x: scores[x]) if scores else None
    return k if k and scores[k] > 0 else None


def taste_multiplier(topic, pref):
    """Tastes move a topic's weight between 0.5x and 1.6x: the mean learned preference of its words."""
    words = set(re.findall(r"[a-z]{4,}", " ".join(PROFILE[topic][1]).lower()))
    vals = [pref[f"kw:{w}"] for w in words if f"kw:{w}" in (pref or {})]
    v = sum(vals) / len(vals) if vals else 0.0
    return round(max(0.5, min(1.6, 1.0 + 0.6 * math.tanh(2.0 * v))), 3)


class Variety:
    """Today's pages per topic (Tokyo day), Wikipedia's share, and the current run of pages on one topic."""

    def __init__(self, state=None, clock=time.time):
        from search_sources import tokyo_day
        self._day_of = tokyo_day
        self.clock = clock
        s = state or {}
        self.day = s.get("day")
        self.topics = {k: int(v) for k, v in (s.get("topics") or {}).items() if isinstance(v, int)}
        self.pages = int(s.get("pages") or 0)
        self.wiki = int(s.get("wiki") or 0)
        self.last = s.get("last")
        self.streak = int(s.get("streak") or 0)
        self.seen_t = {k: float(v) for k, v in (s.get("seen_t") or {}).items() if isinstance(v, (int, float))}
        self.queries = {k: float(v) for k, v in (s.get("queries") or {}).items() if isinstance(v, (int, float))}
        self.trending = [x for x in (s.get("trending") or []) if isinstance(x, str)][-TRENDING_KEEP:]
        self._roll()

    def recent(self, topic, within=RECENT_S):
        """Seen in the last `within` seconds (across days)."""
        return bool(topic) and self.clock() - self.seen_t.get(topic, -1e18) < within

    def mark(self, topic=None, query=None):
        """A topic / query was used now (a pick, a page)."""
        now = self.clock()
        if topic:
            self.seen_t[topic] = now
        if query:
            self.queries[" ".join(str(query).lower().split())] = now
        for d in (self.seen_t, self.queries):
            for k in [k for k, t in d.items() if now - t > QUERY_GAP_S]:
                del d[k]

    def query_used(self, q):
        return self.clock() - self.queries.get(" ".join(str(q).lower().split()), -1e18) < QUERY_GAP_S

    def offer(self, titles):
        """Headlines seen on a front page (news, forums): candidates for discovery ("trending")."""
        for t in titles or []:
            t = " ".join(str(t).split())[:80]
            if 3 <= len(t.split()) <= 12 and t not in self.trending and not self.query_used(t):
                self.trending.append(t)
        self.trending = self.trending[-TRENDING_KEEP:]

    def _roll(self):
        day = self._day_of(self.clock())
        if day != self.day:
            self.day, self.topics, self.pages, self.wiki, self.last, self.streak = day, {}, 0, 0, None, 0

    def note(self, title, text="", host=""):
        """A page was shown: count its topic; returns the topic (None: no profile topic)."""
        self._roll()
        topic = topic_of(f"{title} {text[:1500]}", host)
        self.pages += 1
        if WIKI_HOST.search((host or "").rstrip(".")):
            self.wiki += 1
        if topic:
            self.topics[topic] = self.topics.get(topic, 0) + 1
            self.mark(topic)
        if topic and topic == self.last:
            self.streak += 1
        else:
            self.last, self.streak = topic, 1 if topic else 0
        return topic

    def share(self, topic):
        self._roll()
        return self.topics.get(topic, 0) / self.pages if self.pages else 0.0

    def wiki_share(self):
        self._roll()
        return self.wiki / self.pages if self.pages else 0.0

    def entropy(self):
        """Shannon entropy (bits) of today's topic mix; pages with no profile topic count as one 'other' bucket."""
        self._roll()
        counts = list(self.topics.values()) + [max(0, self.pages - sum(self.topics.values()))]
        n = sum(counts)
        return round(-sum(c / n * math.log2(c / n) for c in counts if c), 3) if n else 0.0

    def to_dict(self):
        self._roll()
        return {"day": self.day, "topics": dict(self.topics), "pages": self.pages, "wiki": self.wiki,
                "last": self.last, "streak": self.streak, "seen_t": dict(self.seen_t), "queries": dict(self.queries),
                "trending": list(self.trending)}

    def public(self):
        d = self.to_dict()
        for k in ("seen_t", "queries", "trending"):
            d.pop(k, None)
        d.update(recent_topics=sorted(k for k in self.seen_t if self.recent(k)), trending_n=len(self.trending),
                 top_share=round(max(self.topics.values()) / self.pages, 3) if self.pages and self.topics else 0.0,
                 wiki_share=round(self.wiki_share(), 3), entropy_bits=self.entropy())
        return d


def saturation(share, free=FREE_SHARE):
    """A topic that already filled much of today weighs less (novelty, not a quota): 1 below `free`, then falling."""
    return math.exp(-SATURATION * max(0.0, share - free))


def taste_multipliers(pref):
    """Topic -> taste multiplier (computed where the tastes live, passed to the browser with the interest)."""
    return {t: round(taste_multiplier(t, pref or {}), 3) for t in PROFILE}


def weights(variety=None, pref=None, hour=12.0, mult=None):
    """Topic -> weight now: seed x tastes x the hour's tilt x saturation. `mult`: precomputed taste multipliers."""
    r = rhythm(hour)
    out = {}
    for topic, (seed, _, _) in PROFILE.items():
        m = (mult or {}).get(topic) if mult else taste_multiplier(topic, pref or {})
        m = max(0.5, min(1.6, float(m))) if isinstance(m, (int, float)) else 1.0
        w = seed * m * r["tilt"].get(topic, 1.0)
        if variety is not None:
            w *= saturation(variety.wiki_share(), WIKI_FREE) if topic == "wikipedia" else saturation(
                variety.share(topic))
            if variety.last == topic and variety.streak >= STREAK_FROM:
                w *= 0.5                                    # he just had several pages of it
            if variety.recent(topic):
                w *= RECENT_W                               # #89: seen in the last 2 hours
        out[topic] = w
    return out


def discovery_topic(q):
    return "discover:" + "-".join(re.findall(r"[a-z0-9]+", str(q).lower())[:6] or ["x"])


def pick(variety=None, pref=None, hour=12.0, rng=None, mult=None, discover=False):
    """One search from the profile: {"query", "topic", "from": "interests", "rhythm"}. Queries typed in the last
    week are left out. discover=True: a topic not seen in the last 2 h, from the profile or from discovery (trending
    headlines he saw, the DISCOVERY pool); "new": True on the result."""
    rng = rng or random.Random()
    w = weights(variety, pref, hour, mult)
    fresh = (lambda q: not variety.query_used(q)) if variety is not None else (lambda q: True)
    topics = [k for k in w if k != "wikipedia" and any(fresh(q) for q in PROFILE[k][1])]
    if discover and variety is not None:
        topics = [k for k in topics if not variety.recent(k)]
    out = None
    if discover and (not topics or rng.random() < 0.5):
        trend = [t for t in (variety.trending if variety is not None else []) if fresh(t)
                 and not (variety and variety.recent(topic_of(t) or discovery_topic(t)))]
        pool = [q for q in DISCOVERY if fresh(q) and not (variety and variety.recent(discovery_topic(q)))]
        if not pool and not trend and variety is not None:  # all typed today: the one typed longest ago
            old = [q for q in DISCOVERY if not variety.recent(discovery_topic(q))]
            pool = sorted(old, key=lambda q: variety.queries.get(q.lower(), 0))[:5]
        if trend and (rng.random() < 0.5 or not pool):
            q = rng.choice(trend)
            variety.trending.remove(q)
            out = {"query": q, "topic": topic_of(q) or discovery_topic(q), "source": "trending"}
        elif pool:
            q = rng.choice(pool)
            out = {"query": q, "topic": discovery_topic(q), "source": "discovery"}
    if out is None:
        topics = topics or [k for k in w if k != "wikipedia"]
        total = sum(w[k] for k in topics)
        x = rng.random() * total
        for k in topics:
            x -= w[k]
            if x <= 0:
                break
        qs = [q for q in PROFILE[k][1] if fresh(q)] or PROFILE[k][1]
        out = {"query": rng.choice(qs), "topic": k, "source": "profile"}
    if variety is not None:
        out["new"] = not variety.recent(out["topic"])
        variety.mark(out["topic"], out["query"])
    return dict(out, **{"from": "interests", "rhythm": rhythm(hour)["name"]})


def streak_pull(variety):
    """Extra pull of the leave option after STREAK_FROM pages in a row on one topic (0..1)."""
    if variety is None or not variety.last or variety.streak < STREAK_FROM:
        return 0.0
    return round(min(1.0, 0.35 + 0.2 * (variety.streak - STREAK_FROM)), 3)
