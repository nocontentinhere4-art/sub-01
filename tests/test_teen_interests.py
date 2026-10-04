"""#89 teen interests (owner, 2026-10-04: "he's a young guy like us: YouTube, TikTok, really interesting things,
cars... look up what young people do online and have him do the same"). Live, 08:24 Tokyo: seven King Arthur Baking
pages in a row, "One Piece latest chapter" searched on Science News, 0 % short video.

    python -m pytest tests/test_teen_interests.py -q
No network: the page and HTTP are stubbed; the parsers, routing, the guard and the variety rules are the real ones.
"""
import asyncio
import random
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import interests as I  # noqa: E402
import search_sources as S  # noqa: E402
import youtube_api as YT  # noqa: E402
from browse import Browser  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def run(coro):
    return asyncio.run(coro)


class Clock:
    def __init__(self, t=1_790_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


# --- research and profile ------------------------------------------------------------------------------------------
def test_the_research_note_cites_real_sources():
    doc = (ROOT / "docs" / "research" / "teen_online.md").read_text()
    for src in ("pewresearch.org", "ofcom.org.uk", "commonsensemedia.org"):
        assert src in doc
    for word in ("YouTube", "TikTok", "gaming", "music", "football", "cars", "anime", "sneakers"):
        assert word.lower() in doc.lower()


def test_the_profile_is_a_young_guys_and_food_waits_for_hunger():
    w = I.weights(hour=15)
    top = sorted((k for k in w if k != "wikipedia"), key=lambda k: -w[k])[:5]
    assert {"games", "cars"} <= set(top) and w["food"] == 0
    picks = [I.pick(hour=h, rng=random.Random(i))["topic"] for i in range(400) for h in (9, 12.5, 15, 20, 1)]
    assert "food" not in picks and not {"crypto", "markets"} & set(picks)
    assert sum(I.pick(hour=12.5, rng=random.Random(i), hungry=True)["topic"] == "food" for i in range(400)) > 20


# --- searches land on search results that fit -----------------------------------------------------------------------
def test_one_piece_goes_to_an_anime_site_never_science_news():
    order = S.route("One Piece latest chapter", rng=random.Random(0))
    assert order[0] == "mal" and "news" not in order
    assert "news" not in S.route("Tokyo weather today", rng=random.Random(0))
    assert "recipes" not in S.route("melon pan recipe", rng=random.Random(0))
    assert S.route("melon pan recipe", rng=random.Random(0), hungry=True)[0] == "recipes"


def test_topic_sites_results_are_parsed():
    html = """<a href="/">Home</a><a href="https://www.carscoops.com/search/?s=supra">search</a>
    <article><a href="https://www.carscoops.com/2026/09/final-toyota-gr-supra-auction/">The Final Toyota GR Supra MkV
    Is Going Up For Grabs</a></article><a href="https://www.carscoops.com/2026/09/honda-prelude/">The new Honda
    Prelude is here</a><a href="https://other.example/supra-news-today-long-title">Supra news on another site</a>"""
    rs = S.parse_links(html, "https://www.carscoops.com/?s=supra")
    assert [r["url"] for r in rs] == ["https://www.carscoops.com/2026/09/final-toyota-gr-supra-auction/"]


def test_a_channels_videos_tab_is_parsed():
    page = ('<script>var ytInitialData = {"contents":[{"lockupViewModel":{"contentId":"ucWPA74zEbo",'
            '"contentType":"LOCKUP_CONTENT_TYPE_VIDEO","metadata":{"lockupMetadataViewModel":{"title":{"content":'
            '"New Audi A6 Allroad vs New Audi Q7! | 4K"}}}}},{"lockupViewModel":{"contentId":"PLx","contentType":'
            '"LOCKUP_CONTENT_TYPE_PLAYLIST"}}]};</script>')
    rs = S.parse_youtube(page, "https://www.youtube.com/@TopGear/videos")
    assert [(r["url"], r["title"]) for r in rs] == [("https://www.youtube.com/watch?v=ucWPA74zEbo",
                                                     "New Audi A6 Allroad vs New Audi Q7! | 4K")]


# --- short video without a key: known channels' public uploads -------------------------------------------------------
SHORTS = ('<script>var ytInitialData = {"contents":[' + ",".join(
    '{"shortsLockupViewModel":{"onTap":{"innertubeCommand":{"reelWatchEndpoint":{"videoId":"abcDEF1234%d"}}},'
    '"overlayMetadata":{"primaryText":{"content":"GR86 track day %d"}}}}' % (i, i) for i in range(5)) + "]};</script>")


def test_without_a_key_the_phone_plays_a_topic_channels_shorts(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    b = Browser(decide=True, rng=random.Random(0))
    sc = b.screens["phone"]
    sc.mode, sc.page, sc.ctx = "shorts", SimpleNamespace(url="about:blank"), object()
    fetched, opened = [], []

    async def _fetch(sc_, url, hops=3, headers=None):
        fetched.append(url)
        if url.endswith("/robots.txt"):
            return 200, "User-agent: *\nDisallow: /results\nDisallow: /feeds/videos.xml\n"
        return 200, SHORTS

    async def _open(sc_, url, why, kind, title=None, min_text=80, shoot=True, revisit=False, referer=None):
        opened.append(url)
        sc_.info = {"title": title, "url": url, "host": "www.youtube-nocookie.com", "why": why, "t": 0, "kind": kind}
        return True

    async def _ok(*a, **k):
        return True
    b._fetch, b._open, b._play_muted, b._shoot = _fetch, _open, _ok, _ok
    assert run(b._public_videos(sc, "shorts", "Toyota GR Supra", "short videos"))
    channel = [u for u in fetched if "/@" in u][0]
    assert channel.endswith("/shorts") and channel.split("/@")[1].split("/")[0] in YT.CHANNELS["cars"]
    assert opened[0].startswith("https://www.youtube-nocookie.com/embed/abcDEF1234")
    assert sc.info["url"].startswith("https://www.youtube.com/shorts/") and b.feed_note == YT.NOTE_CHANNELS
    n = len([u for u in fetched if "/@" in u])
    run(b._public_videos(sc, "shorts", "Toyota GR Supra", "again"))
    assert len([u for u in fetched if "/@" in u]) <= n + 1                 # pages cached; the next channel at most


def test_the_rss_feed_is_not_used_because_robots_disallows_it():
    rp = S.Robots()
    rp.load("www.youtube.com", 200, "User-agent: *\nDisallow: /results\nDisallow: /feeds/videos.xml\n")
    assert not rp.allowed("https://www.youtube.com/feeds/videos.xml?channel_id=UCx")
    assert rp.allowed(YT.channel_url("TopGear")) and rp.allowed(YT.channel_url("TopGear", short=False))
    assert all(YT.channels_for(t) for t in ("cars", "games", "football", "anime", "music", "tech", "memes"))


def test_desk_time_has_youtube_slots_that_hold_for_twenty_minutes():
    share = sum(S.desk_video(i * S.DESK_SLOT_S, 0.5) for i in range(2000)) / 2000
    assert 0.45 < share < 0.7
    t = 1_790_000_000.0 - (1_790_000_000.0 % S.DESK_SLOT_S)
    assert len({S.desk_video(t + k * 60, 0.5) for k in range(20)}) == 1


# --- the variety guard -----------------------------------------------------------------------------------------------
def _page_links(b, sc, url, raw):
    return [l["href"] for l in b.pick_links(raw, url, "text", sc)["links"]]


def test_no_fourth_page_in_a_row_on_one_site_and_a_daily_cap():
    b = Browser(decide=True)
    b.variety = I.Variety(clock=Clock())
    sc = b.screens["desk"]
    sc.info = {"title": "x", "host": "nintendolife.com", "kind": "page"}
    for i in range(3):
        b.variety.note(f"Zelda news {i}", "", "www.nintendolife.com")
    raw = [("https://www.nintendolife.com/news/2026/10/a-long-zelda-story", "A long Zelda story to read", 9000, True),
           ("https://www.pcgamer.com/games/zelda-pc-port-news", "An unofficial Zelda PC port", 9000, True)]
    assert _page_links(b, sc, "https://www.nintendolife.com/news/x", raw) == [raw[1][0]]
    for i in range(browse.HOST_DAY_CAP):
        b.variety.note(f"PC news {i}", "", "www.pcgamer.com")
    assert not b.host_ok("www.pcgamer.com") and b.host_ok("youtube.com")
    assert run(b._open(sc, "https://www.pcgamer.com/another", "x", "page")) is False
    assert b.last_skip == "enough of this site today"
    assert I.streak_pull(b.variety) > 0                                     # the leave option pulls harder


def test_cooking_sites_only_while_hungry():
    b = Browser(decide=True)
    assert not b.host_ok("www.kingarthurbaking.com")                        # the live loop: 7 pages in a row
    b.hungry = True
    assert b.host_ok("www.kingarthurbaking.com")
    assert not set(browse.SEED_TOPICS["food"]) & set(browse.SEEDS)


def test_every_page_is_checked_against_robots_txt():
    b = Browser(decide=True)
    sc = b.screens["desk"]
    sc.public = (object(), object())

    async def _fetch(sc_, url, hops=3, headers=None):
        return (200, "User-agent: *\nDisallow: /\n") if url.endswith("/robots.txt") else (404, "")
    b._fetch = _fetch
    assert run(b._open(sc, "https://old.reddit.com/r/cars/", "x", "page")) is False and b.last_skip == "robots.txt"


def test_live_interest_says_hungry_and_desk_video(monkeypatch):
    live = SimpleNamespace(clock=SimpleNamespace(now=lambda: 1_790_000_000.0),
                           life=SimpleNamespace(activity="order_food", hunger=0.6), memory=SimpleNamespace(items=[]),
                           tastes=SimpleNamespace(top=lambda n=8: {"favoured": []}, pref={}))
    d = S.live_interest(live, None, random.Random(0))
    assert d["hungry"] is True
    live.life = SimpleNamespace(activity="research", hunger=0.2)
    monkeypatch.setattr(S, "desk_video", lambda t, tilt=0.5: True)
    d = S.live_interest(live, None, random.Random(0))
    assert d["hungry"] is False and d["feed"] == "video"


def test_with_the_key_a_search_with_no_fitting_site_becomes_a_youtube_search(monkeypatch):
    """Live 2026-10-04 08:50-08:58 Tokyo, key set: "tardigrades — Hacker News", "capybara onsen — Science News".
    Now such a query is a YouTube search (the API), never a news site's search page."""
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key-not-real")
    b = Browser(decide=True, rng=random.Random(0))
    b.YT_SEARCH_SHARE = 0.0                                  # only the no-fitting-site path here
    sc = b.screens["desk"]
    searched, videos = [], []

    async def _search_on(sc_, name, q, why, origin):
        searched.append(name)
        return False

    async def _public_videos(sc_, kind, q, why, origin="", short=True):
        videos.append((kind, q, short))
        return True
    b._search_on, b._public_videos = _search_on, _public_videos
    assert run(b._search(sc, "capybara onsen", "", "interests"))
    assert videos == [("youtube", "capybara onsen", False)] and "news" not in searched and "hn" not in searched
    b.YT_SEARCH_SHARE = 1.0                                  # and a share of all searches go to YouTube first
    run(b._search(sc, "Toyota GR Supra", "", "interests"))
    assert videos[-1][1] == "Toyota GR Supra" and searched.count("carscoops") == 0


def test_login_walled_social_pages_are_never_opened_or_offered():
    """Live 2026-10-04 09:0x Tokyo: Serious Eats' Instagram page, a "See photos, videos and more… Sign up / Log in"
    modal, was on his monitor."""
    b = Browser(decide=True)
    b.hungry = True
    for h in ("www.instagram.com", "www.facebook.com", "x.com", "twitter.com", "www.threads.net"):
        assert not b.host_ok(h), h
    assert b.host_ok("www.tiktok.com") and b.host_ok("www.youtube-nocookie.com")
    sc = b.screens["desk"]
    sc.info = {"title": "Serious Eats", "host": "seriouseats.com", "kind": "page"}
    raw = [("https://www.instagram.com/seriouseats/", "Follow Serious Eats on Instagram", 9000, True),
           ("https://www.seriouseats.com/best-ramen-recipe-tonkotsu", "The best tonkotsu ramen at home", 9000, True)]
    assert _page_links(b, sc, "https://www.seriouseats.com/", raw) == [raw[1][0]]
    assert browse.LOGIN_WALL.search("See photos, videos and more from Serious Eats. Sign up  Log in")


def test_the_first_thing_at_the_desk_is_a_video():
    b = Browser(decide=True, rng=random.Random(0))
    sc = b.screens["desk"]
    asked = []

    async def _public_videos(sc_, kind, q, why, origin="", short=True):
        asked.append((kind, short))
        sc_.info = {"url": "https://www.youtube.com/watch?v=abcDEF12345", "title": q, "host": "youtube.com",
                    "kind": "page", "why": why, "t": 0, "embed": "x"}
        b.watched = True
        return True
    b._public_videos = _public_videos
    assert run(b._next(sc, [], {"query": "", "from": "", "hour": 9}))
    assert asked == [("youtube", False)]

    async def _search(sc_, q, why="", origin=""):
        asked.append(("search", q))
        return True
    b._search = _search
    b.rng = SimpleNamespace(random=lambda: 0.5, choice=random.Random(0).choice)
    run(b._next(sc, [], {"query": "", "from": "", "hour": 9}))
    assert asked[-1][0] == "search"                          # after that, the usual mix
