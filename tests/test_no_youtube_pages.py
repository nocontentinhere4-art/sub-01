"""#89 live bugs (2026-10-04): at 10:58 and 11:02 Tokyo his monitor showed the full youtube.com/watch page (Sign in,
sponsored cards, a pre-roll ad with "Skip", "Something went wrong"); at 11:54 every video became a card because
YouTube refuses playback to the server's IP ("bot wall" in the player). YouTube's Terms forbid automated access to its
pages, and we never work around a refusal. So the server's browser never loads YouTube (pages or the nocookie embed)
nor TikTok's player: the brain picks the video as before (Data API, videos.list playability), the server publishes
"now watching" and the video plays in the VIEWER's browser in the official embed; the viewer's player reports a dead
video and the brain moves on.

    python -m pytest tests/test_no_youtube_pages.py -q
"""
import asyncio
import json
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import youtube_api as YT  # noqa: E402
from browse import Browser  # noqa: E402

VIDEO_SITE = re.compile(r"^https?://([\w-]+\.)*(youtube\.com|youtu\.be|youtube-nocookie\.com)(/|$)|"
                        r"^https?://(www\.)?tiktok\.com/(player|embed)/", re.I)


def run(coro):
    return asyncio.run(coro)


class Page:
    """The server screen's page: records every navigation and every local card set on it."""

    def __init__(self):
        self.url, self.visited, self.cards = "about:blank", [], []

    async def goto(self, url, **k):
        self.visited.append(url)
        self.url = url

    async def set_content(self, html, **k):
        self.cards.append(html)
        self.url = "about:blank"

    async def wait_for_timeout(self, ms):
        pass

    async def evaluate(self, js, *a):
        return None


def _browser(monkeypatch, key=True, playable=True, device="desk"):
    if key:
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key-not-real")
    else:
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    b = Browser(decide=True, rng=random.Random(0))
    sc = b.screens[device]
    sc.page, sc.ctx = Page(), object()
    api = []

    async def _fetch(sc_, url, hops=3, headers=None):
        api.append(url)
        if "/youtube/v3/videos?" in url:
            vid = url.split("id=")[1].split("&")[0]
            return 200, json.dumps({"items": [{"id": vid, "snippet": {"title": f"Grandmaster blunders {vid}",
                                                                        "channelTitle": "Some Channel"},
                                               "contentDetails": {"duration": "PT12M"},
                                               "status": {"embeddable": playable, "privacyStatus": "public"}}]})
        return 404, ""                                          # robots.txt: none

    async def _use(sc_, url):
        pass

    async def _settle(sc_, why, kind, title=None, min_text=80, shoot=True, revisit=False):
        sc_.info = {"title": title or sc_.page.url, "url": sc_.page.url, "host": "x", "why": why, "t": 0, "kind": kind}
        return True

    async def show(sc_):
        return True
    b._fetch, b._use, b._settle, b.show = _fetch, _use, _settle, show
    return b, sc, api


def test_a_watch_link_is_published_for_the_viewer_and_the_server_loads_no_video_site(monkeypatch):
    b, sc, api = _browser(monkeypatch)
    assert run(b._open(sc, "https://www.youtube.com/watch?v=qpkTV1VolHU", "followed a link", "page"))
    assert sc.page.visited == []                                # no navigation at all: a local card
    assert any("/youtube/v3/videos?" in u for u in api)                   # checked as playable first
    nw = sc.info["now_watching"]
    assert (nw["source"], nw["id"], nw["duration_s"], nw["device"]) == ("youtube", "qpkTV1VolHU", 720, "desk")
    assert nw["thumb"] == "https://i.ytimg.com/vi/qpkTV1VolHU/hqdefault.jpg" and sc.watch_until > 0
    assert sc.info["url"] == "https://www.youtube.com/watch?v=qpkTV1VolHU" and "in your browser" in sc.page.cards[-1]
    for link, vid in (("https://youtu.be/abcDEF12345", "abcDEF12345"),
                      ("https://www.youtube.com/shorts/abcDEF12346", "abcDEF12346"),
                      ("https://m.youtube.com/watch?feature=share&v=abcDEF12347", "abcDEF12347")):
        assert run(b._open(sc, link, "a link", "page")) and sc.info["now_watching"]["id"] == vid
    assert sc.page.visited == [] and not [u for u in api if VIDEO_SITE.match(u)]   # only the API and robots.txt


def test_other_youtube_pages_are_never_opened(monkeypatch):
    b, sc, _ = _browser(monkeypatch)
    for u in ("https://www.youtube.com/@MrBeast", "https://www.youtube.com/", "https://www.youtube.com/results?q=x"):
        assert run(b._open(sc, u, "x", "page")) is False
    assert sc.page.visited == [] and "YouTube page" in b.last_skip


def test_without_a_key_or_when_not_playable_the_link_is_not_played(monkeypatch):
    b, sc, _ = _browser(monkeypatch, key=False)
    assert run(b._open(sc, "https://www.youtube.com/watch?v=qpkTV1VolHU", "x", "page")) is False
    assert sc.page.visited == [] and sc.info is None
    b, sc, _ = _browser(monkeypatch, playable=False)
    assert run(b._open(sc, "https://www.youtube.com/watch?v=qpkTV1VolHU", "x", "page")) is False
    assert sc.info is None and b.yt.is_bad("https://www.youtube.com/watch?v=qpkTV1VolHU")


def test_the_viewers_player_error_sets_the_video_aside_and_the_brain_moves_on(monkeypatch):
    b, sc, _ = _browser(monkeypatch)
    url = "https://www.youtube.com/watch?v=qpkTV1VolHU"
    assert run(b._open(sc, url, "x", "page"))
    assert not b.video_error("desk", "abcDEF12345", 150)        # not the video on screen: ignored
    assert not b.video_error("phone", "qpkTV1VolHU", 150)       # nor another screen's
    assert b.video_error("desk", "qpkTV1VolHU", 150)            # not embeddable after all
    assert b.yt.is_bad(url) and b.yt.bad_by.get("Some Channel") == 1 and sc.watch_until < browse.time.time()
    assert "could not play it (error 150)" in sc.info["why"] and b.yt.player_up()
    st = run(b._open(sc, "https://www.youtube.com/watch?v=abcDEF12345", "x", "page"))
    assert st and b.video_error("desk", "abcDEF12345", 5)       # the player itself (HTML5 error): not the channel's
    assert b.yt.bad_by.get("Some Channel") == 1
    assert not hasattr(browse, "EMBED_ERROR_JS") and not hasattr(Browser, "_embed_error")   # no player, no Skip


def test_two_player_level_errors_pause_youtube_and_nothing_is_looked_up_meanwhile(monkeypatch):
    b, sc, api = _browser(monkeypatch)
    for vid in ("aaaaaaaaaa1", "aaaaaaaaaa2"):
        assert run(b._open(sc, f"https://www.youtube.com/watch?v={vid}", "x", "page"))
        assert b.video_error("desk", vid, 153)                  # player configuration error in the viewer's page
    assert not b.yt.player_up() and b.yt.public()["player"] == "paused"
    api.clear()
    assert not run(b._public_videos(sc, "youtube", "chess", "test", short=False))
    assert api == [] and b.feed_note.startswith("YouTube: its embed player refuses")
    assert not run(b._open(sc, "https://www.youtube.com/watch?v=aaaaaaaaaa9", "link", "page"))
    assert api == [] and "paused" in b.last_skip


def test_the_watch_runs_on_the_clock_without_screenshots_of_a_player(monkeypatch):
    b, sc, _ = _browser(monkeypatch)
    shots = []

    async def _shoot(sc_):
        shots.append(1)
        return True
    b._shoot = _shoot
    assert run(b._open(sc, "https://www.youtube.com/watch?v=qpkTV1VolHU", "x", "page"))
    assert run(b._watch(sc)) and shots == []
    v = sc.info["video"]
    assert v["watching"] and v["scene_estimated"] and v["client"] and 0 < v["scene"] < 1
    assert sc.info["now_watching"]["watch_s"] == v["seconds"] <= 720


def test_the_guard_aborts_every_navigation_to_a_video_site_player(monkeypatch):
    g = browse.Guard()
    seen = []

    async def resolves_public(host):
        return True
    g.resolves_public = resolves_public

    class Route:
        def __init__(self, url, top=True):
            self.request = SimpleNamespace(url=url, resource_type="document", method="GET",
                                           is_navigation_request=lambda: True,
                                           frame=SimpleNamespace(parent_frame=None if top else object()))

        async def abort(self):
            seen.append(("abort", self.request.url))

        async def continue_(self):
            seen.append(("go", self.request.url))
    for u, top in (("https://www.youtube.com/watch?v=qpkTV1VolHU", True),
                   ("https://www.youtube-nocookie.com/embed/qpkTV1VolHU", True),
                   ("https://www.youtube-nocookie.com/embed/qpkTV1VolHU", False),     # an iframe on a news page
                   ("https://www.tiktok.com/player/v1/6718335390845095173", True),
                   ("https://www.tiktok.com/@scout2015/video/6718335390845095173", True),
                   ("https://example.org/story", True)):
        run(g.route(Route(u, top)))
    assert [a for a, _ in seen] == ["abort", "abort", "abort", "abort", "go", "go"]


def test_banner_closer_never_presses_anything_in_the_youtube_player():
    """CLOSE_BUTTON matches "Skip": the ad's Skip button in the embed must never be pressed by _dismiss."""
    import asyncio
    from types import SimpleNamespace
    import browse

    class Frame:
        def __init__(self, url):
            self.url, self.calls = url, []

        async def evaluate(self, js, *a):
            self.calls.append(js)
            return [{"i": 0, "label": "Skip", "consent": False}] if "consentRe" in js else None

    for url in ("https://www.youtube-nocookie.com/embed/abcdefghijk", "https://www.youtube.com/embed/abcdefghijk"):
        main = Frame(url)
        page = SimpleNamespace(url=url, frames=[main], main_frame=main)

        async def wait(ms):
            pass
        page.wait_for_timeout = wait
        b = browse.Browser(decide=False)
        asyncio.run(b._dismiss(SimpleNamespace(page=page, site=None), rounds=1))
        assert main.calls == [] and not b.dismissed
    # an ordinary page's "Skip" modal button is still closed as before
    main = Frame("https://example.org/a")
    page = SimpleNamespace(url=main.url, frames=[main], main_frame=main, wait_for_timeout=wait)
    b = browse.Browser(decide=False)
    asyncio.run(b._dismiss(SimpleNamespace(page=page, site=None), rounds=1))
    assert any("click" in c for c in main.calls)


def test_now_watching_carries_only_checked_ids_and_public_metadata():
    nw = browse.now_watching({"url": "https://www.youtube.com/shorts/abcDEF12345", "title": "t", "author": "c",
                              "sec": 41, "thumb": "https://evil.example/x.jpg"}, "phone")
    assert nw["source"] == "youtube" and nw["duration_s"] == 41
    assert nw["thumb"] == "https://i.ytimg.com/vi/abcDEF12345/hqdefault.jpg"     # never a foreign image URL
    tt = browse.now_watching({"url": "https://www.tiktok.com/@scout2015/video/6718335390845095173", "title": "t",
                              "author": "scout2015"}, "phone")
    assert tt["source"] == "tiktok" and tt["id"] == "6718335390845095173" and tt["duration_s"] is None
    assert browse.now_watching({"url": "https://example.org/v/1", "title": "t"}, "desk") is None
    assert set(nw) == {"source", "id", "title", "channel", "duration_s", "started_at", "device", "thumb"}


def test_with_a_key_the_replay_note_does_not_claim_there_is_no_key():
    assert "no API key" not in YT.NOTE_REPLAY_KEY and "API" in YT.NOTE_REPLAY_KEY
