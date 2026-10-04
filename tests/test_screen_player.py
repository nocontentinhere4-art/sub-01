"""#89 client player (2026-10-04): YouTube refuses playback to the server's IP, so the video his brain picked plays in
the VIEWER's browser, in the official embed (youtube-nocookie.com / tiktok.com/player) in the side panel; the server
publishes "now watching" and never opens the player. Here: the client module in node with a stubbed iframe, the
live server's now-watching status and error report (only the video on screen, rate-limited, nothing personal), and
the page's hook.

    python -m pytest tests/test_screen_player.py -q
"""
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_server import Live  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def test_the_client_player_in_node_with_a_stubbed_iframe():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, str(ROOT / "tests" / "js" / "screen_player_check.js")], capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["src_youtube"].startswith("https://www.youtube-nocookie.com/embed/qpkTV1VolHU?autoplay=1&mute=1&")
    assert "start=42" in out["src_youtube"] and "enablejsapi=1" in out["src_youtube"]
    assert out["src_tiktok"].startswith("https://www.tiktok.com/player/v1/6718335390845095173?autoplay=1&muted=1")
    assert out["rejects"] == [None, None, None, None]                  # only checked ids, only the two players
    assert out["errors"] == {"yt": 150, "yt_other_event": None, "yt_wrong_origin": None, "tt": 1001, "garbage": None}
    assert out["iframe"]["referrer"] == "strict-origin-when-cross-origin" and out["iframe"]["playing"]
    assert out["listening"] == [["listening", "https://www.youtube-nocookie.com"]]
    assert out["same_iframe_kept"] and out["ignored"] and out["f1_removed"] and out["hidden"]
    assert out["reported"][0] == ["/api/screen/video_error", {"id": "qpkTV1VolHU", "code": 150}, "POST"]
    assert all(set(body) == {"id", "code"} for _, body, _ in out["reported"])    # nothing else leaves the page
    assert out["reports_in_a_minute"] == 3 and out["reports_after_a_minute"] == 4   # once per video, 3 a minute
    assert out["canvas"] == {"w": 1024, "h": 600, "drew": True}


class FakeBrowser:
    """The live server's view of the browser service."""

    def __init__(self, screens):
        self.screens, self.restarting, self.calls = screens, False, []

    async def video_error(self, device, vid, code):
        self.calls.append((device, vid, code))
        return True


def _nw(vid="qpkTV1VolHU", title="Grandmaster blunders", started=None):
    return {"source": "youtube", "id": vid, "title": title, "channel": "chess channel", "duration_s": 720,
            "started_at": started or time.time() - 30, "device": "desk",
            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}


def _status(nw):
    return {"title": nw["title"], "url": f"https://www.youtube.com/watch?v={nw['id']}", "host": "youtube.com",
            "kind": "page", "why": "x", "t": 0, "id": 3, "device": "desk", "card": True, "now_watching": nw,
            "embed": "https://www.youtube-nocookie.com/embed/" + nw["id"]}


def test_the_screen_status_publishes_now_watching_with_the_elapsed_time(tmp_path):
    live = Live("m", True, time_scale=1e6, data_dir=tmp_path)
    live.browser = FakeBrowser({"desk": _status(_nw())})
    st = live.screen_status("desk")
    assert st["now_watching"]["id"] == "qpkTV1VolHU" and 29 <= st["now_watching"]["elapsed_s"] <= 32
    view = live.screens_view()
    assert view["now_watching"]["desk"]["id"] == "qpkTV1VolHU" and view["now_watching"]["phone"] is None
    # a title the public page never shows is never played to viewers either
    live.browser = FakeBrowser({"desk": _status(_nw(title="casino jackpot slots"))})
    st = live.screen_status("desk")
    assert "now_watching" not in st and "embed" not in st


def test_a_viewers_error_report_counts_only_for_the_video_on_screen_and_is_rate_limited(tmp_path):
    live = Live("m", True, time_scale=1e6, data_dir=tmp_path)
    live.browser = FakeBrowser({"desk": _status(_nw())})
    assert run(live.video_error("abcDEF12345", 150)) == {"ok": False}        # not on screen
    assert run(live.video_error("qpkTV1VolHU", 150)) == {"ok": True}
    assert run(live.video_error("qpkTV1VolHU", 150)) == {"ok": False}        # once per video
    assert live.browser.calls == [("desk", "qpkTV1VolHU", 150)]
    for i in range(10):
        vid = f"aaaaaaaaa{i:02d}"
        live.browser.screens["desk"] = _status(_nw(vid))
        run(live.video_error(vid, 5))
    assert len(live.browser.calls) == live.VIDEO_ERRORS_PER_MIN              # all viewers together, per minute


def test_the_error_endpoint_takes_only_an_id_and_a_code(tmp_path):
    from aiohttp.test_utils import TestClient, TestServer
    import live_server as LS
    seen = []

    class L:
        async def video_error(self, vid, code):
            seen.append((vid, code))
            return {"ok": True}

    async def main():
        app = LS.web.Application()
        live = L()

        async def video_error(request):                      # the handler as registered by build_app
            return await LS_handler(request, live)
        app.router.add_post("/api/screen/video_error", video_error)
        async with TestClient(TestServer(app)) as c:
            ok = await c.post("/api/screen/video_error", json={"id": "qpkTV1VolHU", "code": 150})
            bad = [await c.post("/api/screen/video_error", json=b) for b in (
                {"id": "x\"><script>", "code": 1}, {"id": "qpkTV1VolHU", "code": "150"}, {"id": "qpkTV1VolHU"}, [1, 2])]
            return ok.status, [r.status for r in bad]
    LS_handler = LS.video_error_handler
    status, bad = run(main())
    assert status == 200 and bad == [400, 400, 400, 400] and seen == [("qpkTV1VolHU", 150)]


def test_the_room_page_plays_the_official_embed_from_the_status():
    html = (ROOT / "web" / "room.html").read_text()
    assert 'import { createScreenPlayer, nowWatching, playingCanvas } from "./room/screen_player.js";' in html
    assert "player.show(st, st._rx)" in html and "playingCanvas(document, img, nw" in html
    js = (ROOT / "web" / "room" / "screen_player.js").read_text()
    assert "youtube-nocookie.com" in js and "www.youtube.com/embed" not in js and "iframe_api" not in js
    assert "mute=1" in js and "muted=1" in js and "unMute" not in js and "document.cookie" not in js
