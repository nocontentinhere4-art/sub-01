"""The browser on the owner's own PC (BROWSE_OPEN_WEB_ONLY=1, Dockerfile.browse): the open web only. No
request to YouTube or TikTok at all (pages, embeds, thumbnails, video files), no logged-in session, no video feed.

    python -m pytest tests/test_open_web_only.py -q
No network, no Chromium.
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import browse_service as BS  # noqa: E402
from test_chromium_memory import Route  # noqa: E402


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def guard():
    g = browse.Guard()

    async def resolves_public(host):
        return True
    g.resolves_public = resolves_public
    return g


VIDEO_URLS = [("https://www.youtube-nocookie.com/embed/qpkTV1VolHU", True, "document"),
              ("https://www.tiktok.com/player/v1/6718335390845095173", True, "document"),
              ("https://i.ytimg.com/vi/qpkTV1VolHU/hqdefault.jpg", False, "image"),
              ("https://rr1---sn-x.googlevideo.com/videoplayback?x=1", False, "xhr"),
              ("https://p16-sign-va.tiktokcdn.com/obj/x.jpeg", False, "image"),
              ("https://youtu.be/qpkTV1VolHU", True, "document")]


def test_off_by_default(monkeypatch):
    monkeypatch.setattr(browse, "OPEN_WEB_ONLY", False)
    g = guard()
    r = Route("https://www.youtube-nocookie.com/embed/qpkTV1VolHU")
    run(g.route(r))
    assert r.seen == "go"


def test_no_request_reaches_youtube_or_tiktok(monkeypatch):
    monkeypatch.setattr(browse, "OPEN_WEB_ONLY", True)
    g = guard()
    for url, nav, rtype in VIDEO_URLS:
        r = Route(url, nav=nav, rtype=rtype)
        run(g.route(r))
        assert r.seen == "abort", url
    for url in ("https://en.wikipedia.org/wiki/Tokyo", "https://www.notyoutube.com/", "https://mytiktok.com.example/"):
        r = Route(url)
        run(g.route(r))
        assert r.seen == "go", url


def test_no_sessions_and_no_video_feed(monkeypatch):
    monkeypatch.setattr(browse, "OPEN_WEB_ONLY", True)
    b = browse.Browser(decide=True, sessions={"tiktok": object(), "youtube": object()})
    assert b.sessions == {} and b.accounts() == {}
    sc = b.screens["phone"]
    sc.page, sc.ctx = SimpleNamespace(url="about:blank"), object()
    for kind in ("youtube", "shorts", "tiktok"):
        assert not run(b._public_videos(sc, kind, "skateboarding", "x"))
        assert b.feed_note == browse.NOTE_OPEN_WEB
    assert not run(b._play_video_id(sc, "qpkTV1VolHU", "x"))
    assert browse.NOTE_OPEN_WEB in b.last_skip


def test_the_flag_reaches_a_child_service():
    assert "BROWSE_OPEN_WEB_ONLY" in BS.ENV_KEEP
