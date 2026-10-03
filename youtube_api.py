"""YouTube through its official Data API v3 and its official embed player (#89 live follow-up).

Why: youtube.com/robots.txt disallows /results for every crawler, so the browser's YouTube and Shorts sources (the
results page) were refused by our own robots check all day, and the phone never showed a short. The compliant path is
YouTube's own API for search and its embed player (youtube-nocookie.com/embed/<id>, allowed by its robots.txt) to
play a video.

- Only with YOUTUBE_API_KEY set (Railway variable; never in git or logs). The key goes in the X-Goog-Api-Key header,
  never in a URL, so no log line that prints a URL can carry it. Without it, nothing is asked and the screens panel
  says so.
- Quota: search.list costs SEARCH_UNITS (100) of the free 10,000 units a day (Pacific day, when Google resets it);
  we stop at DAILY_UNITS (default 9,000, YOUTUBE_DAILY_UNITS can lower it) and cache each query's results for
  CACHE_S. Free quota only: nothing is paid, no cap is raised.
- Search: type=video, safeSearch=strict, videoEmbeddable=true; Shorts: videoDuration=short and "#shorts".
Results go through the browser's guard (safe_results, video_text_ok) like every other result.
"""
import html
import json
import os
import time
import urllib.parse

KEY_ENV = "YOUTUBE_API_KEY"
SEARCH = "https://www.googleapis.com/youtube/v3/search"
SEARCH_UNITS = 100
FREE_UNITS = 10_000
DAILY_UNITS = 9_000
CACHE_S = 6 * 3600
EMBED = "https://www.youtube-nocookie.com/embed/{id}?autoplay=1&mute=1&playsinline=1&controls=0&rel=0&loop=1&playlist={id}"
VIEWER_EMBED = "https://www.youtube-nocookie.com/embed/{id}?autoplay=0&mute=1&playsinline=1&rel=0"
NOTE_NO_KEY = "YouTube: YOUTUBE_API_KEY not set (YouTube's search pages are closed to robots), so no YouTube search"
OEMBED = "https://www.youtube.com/oembed?"


# #89 teen interests: without a key, the public uploads of well-known channels per topic, read from the channel's own
# Shorts / Videos page (youtube.com/@handle/shorts: allowed by robots.txt, which disallows /feeds/videos.xml, the RSS).
# Each handle was checked to exist and to list public videos on 2026-10-04.
CHANNELS = {
    "cars": ["TopGear", "carwow", "DougDeMuro", "Formula1"],
    "games": ["IGN", "PlayStation", "Markiplier"],
    "football": ["PremierLeague", "433", "FIFA", "UEFA"],
    "music": ["Genius", "COLORSxSTUDIOS", "NPRMusic", "The_FirstTake"],
    "anime": ["Crunchyroll", "TOHOanimation", "AniplexUSA"],
    "tech": ["mkbhd", "LinusTechTips", "UnboxTherapy", "Mrwhosetheboss"],
    "sneakers": ["Complex", "highsnobiety", "hypebeast"],
    "creators": ["MrBeast", "DudePerfect", "MarkRober"],
    "memes": ["DailyDoseOfInternet", "MrBeast", "DudePerfect"],
    "movies": ["Netflix", "A24"],
    "tokyo": ["abroadinjapan", "ParisInTokyo"],
    "science": ["veritasium", "kurzgesagt"],
}
CHANNEL_CACHE_S = 3 * 3600
NOTE_CHANNELS = "YouTube: no API key, so public uploads of known channels (their own Shorts / Videos pages)"


def channel_url(handle, short=True):
    return f"https://www.youtube.com/@{handle}/{'shorts' if short else 'videos'}"


def channels_for(topic):
    """The topic's channels; a topic without any (or none given) gets the creators'."""
    return CHANNELS.get(topic or "") or CHANNELS["creators"]


def key():
    return (os.environ.get(KEY_ENV) or "").strip() or None


def headers():
    k = key()
    return {"X-Goog-Api-Key": k} if k else {}


def daily_units():
    try:
        return max(0, min(DAILY_UNITS, int(os.environ.get("YOUTUBE_DAILY_UNITS") or DAILY_UNITS)))
    except ValueError:
        return DAILY_UNITS


def search_url(q, short=True, n=10):
    """The search.list URL (no key in it: the key travels in the header)."""
    p = {"part": "snippet", "type": "video", "maxResults": str(n), "safeSearch": "strict", "videoEmbeddable": "true",
         "relevanceLanguage": "en", "q": f"{q} #shorts" if short else q}
    if short:
        p["videoDuration"] = "short"
    return SEARCH + "?" + urllib.parse.urlencode(p)


def video_url(vid, short=True):
    return f"https://www.youtube.com/shorts/{vid}" if short else f"https://www.youtube.com/watch?v={vid}"


def embed_url(vid):
    return EMBED.format(id=vid)


def viewer_embed(vid):
    return VIEWER_EMBED.format(id=vid)


def oembed_url(video):
    return OEMBED + urllib.parse.urlencode({"url": video, "format": "json"})


def parse_search(text, short=True):
    """search.list JSON -> results [{url, title, channel, thumb, video, short, embed, id}] (unguarded)."""
    try:
        d = json.loads(text or "")
    except ValueError:
        return []
    out = []
    for it in (d.get("items") or []) if isinstance(d, dict) else []:
        vid = ((it or {}).get("id") or {}).get("videoId")
        sn = (it or {}).get("snippet") or {}
        if not isinstance(vid, str) or not vid.replace("-", "").replace("_", "").isalnum() or len(vid) != 11:
            continue
        thumbs = sn.get("thumbnails") or {}
        thumb = ((thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url") or "")
        out.append({"id": vid, "url": video_url(vid, short), "title": html.unescape(str(sn.get("title") or ""))[:140],
                    "channel": html.unescape(str(sn.get("channelTitle") or ""))[:60],
                    "thumb": thumb if thumb.startswith("https://i.ytimg.com/") else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "video": True, "short": short, "embed": embed_url(vid), "host": "youtube.com"})
    return out


def parse_oembed(text, video):
    """YouTube's public oEmbed JSON -> {title, channel} or None."""
    try:
        d = json.loads(text or "")
    except ValueError:
        return None
    if not isinstance(d, dict) or not d.get("title"):
        return None
    return {"title": str(d["title"])[:140], "channel": str(d.get("author_name") or "")[:60]}


def pacific_day(t):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.fromtimestamp(t, ZoneInfo("America/Los_Angeles")).date().isoformat()


class Quota:
    """Units spent on the Data API this Pacific day, and each query's cached results."""

    def __init__(self, state=None, clock=time.time):
        self.clock = clock
        s = state or {}
        self.day = s.get("day")
        self.used = int(s.get("used") or 0) if isinstance(s.get("used"), (int, float)) else 0
        self.searches = int(s.get("searches") or 0) if isinstance(s.get("searches"), (int, float)) else 0
        self.errors = [str(e)[:80] for e in (s.get("errors") or [])][-5:]
        self.cache = {k: v for k, v in (s.get("cache") or {}).items()
                      if isinstance(v, dict) and isinstance(v.get("t"), (int, float)) and isinstance(v.get("r"), list)}
        self._roll()

    def _roll(self):
        d = pacific_day(self.clock())
        if d != self.day:
            self.day, self.used, self.searches, self.errors = d, 0, 0, []
        now = self.clock()
        for k in [k for k, v in self.cache.items() if now - v["t"] > CACHE_S]:
            del self.cache[k]

    @staticmethod
    def _k(q, short):
        return ("s:" if short else "v:") + " ".join(str(q).lower().split())

    def cached(self, q, short=True):
        self._roll()
        c = self.cache.get(self._k(q, short))
        return list(c["r"]) if c else None

    def allow(self, units=SEARCH_UNITS):
        self._roll()
        return self.used + units <= daily_units()

    def spend(self, q, short, results, units=SEARCH_UNITS):
        self._roll()
        self.used += units
        self.searches += 1
        self.cache[self._k(q, short)] = {"t": self.clock(), "r": results[:10]}
        while len(self.cache) > 200:
            self.cache.pop(next(iter(self.cache)))

    def error(self, why):
        self._roll()
        self.errors = (self.errors + [str(why)[:80]])[-5:]

    def to_dict(self):
        self._roll()
        return {"day": self.day, "used": self.used, "searches": self.searches, "errors": self.errors,
                "cache": dict(list(self.cache.items())[-100:])}

    def public(self):
        """For /api/screens and /api/browsing: the key set or not, units used today; never the key."""
        self._roll()
        return {"key_set": bool(key()), "pacific_day": self.day, "units_used": self.used, "units_cap": daily_units(),
                "free_units": FREE_UNITS, "searches": self.searches, "errors": list(self.errors)}
