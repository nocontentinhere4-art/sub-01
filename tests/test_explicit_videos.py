"""Explicit music videos ("(Explicit Video)", "[Not Clean]", "(Uncensored)") are not shown, as music.py already drops
explicit Spotify tracks; youtube_api.EXPLICIT_VIDEOS_OK = True lets them back. The bare words count only in brackets
or as a suffix, so titles that merely mention them are still shown.

    python -m pytest tests/test_explicit_videos.py -q
No network, no Chromium.
"""
import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import youtube_api as YT  # noqa: E402

EXPLICIT = ["Artist - Song (Explicit Video)", "Artist - Song [Not Clean]", "Artist - Song (Uncensored)",
            "Artist - Song (Official Explicit Video)", "Artist - Song (Dirty Version)", "Artist - Song - Explicit",
            "Artist – Song | Explicit Version", "Artist - Song [Parental Advisory]"]
CLEAN = ["Artist - Song (Clean)", "Artist - Song (Clean Version)", "Explicit Content: a documentary review",
         "Nature's not clean water explained", "Dirty Dancing (Remastered)",
         "The history of the Parental Advisory sticker", "Explicitly Yours (Live at Budokan)"]


def run(coro):
    return asyncio.run(coro)


def card(title, n=1, **k):
    return dict({"url": f"https://www.youtube.com/watch?v=abcdefghij{n}", "title": title, "author": "Artist",
                 "hashtags": [], "host": "youtube.com"}, **k)


@pytest.mark.parametrize("title", EXPLICIT)
def test_explicit_titles_are_refused(title):
    assert YT.explicit_video(title) and not browse.video_text_ok(title)


@pytest.mark.parametrize("title", CLEAN)
def test_titles_that_only_mention_the_words_are_shown(title):
    assert not YT.explicit_video(title) and browse.video_text_ok(title)


def test_the_card_picker_drops_explicit_videos_and_hashtags():
    b = browse.Browser(decide=False)
    assert not b._card_ok(card("Artist - Song (Explicit Video)"))
    assert not b._card_ok(card("Artist - Song", 2, hashtags=["#explicit"]))
    assert b._card_ok(card("Artist - Song (Clean)", 3)) and b._card_ok(card("Explicit Content: a documentary review", 4))


def test_videos_list_drops_explicit_titles_and_tags():
    def item(vid, title, tags=()):
        return {"id": vid, "status": {"embeddable": True, "privacyStatus": "public"},
                "contentDetails": {"duration": "PT3M"}, "snippet": {"title": title, "channelTitle": "A", "tags": list(tags)}}
    text = json.dumps({"items": [item("aaaaaaaaaaa", "Song (Explicit Video)"),
                                 item("bbbbbbbbbbb", "Song (Official Video)", ["pop", "Explicit"]),
                                 item("ccccccccccc", "Song (Clean)", ["pop", "explicitly good"])]})
    assert list(YT.parse_videos(text)) == ["ccccccccccc"]


class Page:
    def __init__(self, url, title, body):
        self.url, self._title, self.body, self.frames, self.main_frame = url, title, body, [], None

    async def wait_for_timeout(self, ms):
        pass

    async def add_style_tag(self, **k):
        pass

    async def title(self):
        return self._title

    async def evaluate(self, js, *a):
        return self.body if "innerText" in js else False


def settle(title):
    b = browse.Browser(decide=False)
    sc = b.screens["desk"]
    sc.page, sc.ctx = Page("https://www.youtube.com/watch?v=dQw4w9WgXcQ", title, "A music video. " * 20), object()
    shown = []

    async def show(sc_):
        shown.append(sc_.info["title"])
        return True

    async def leave(sc_):
        return False
    b.show, b._leave = show, leave
    return b, shown, run(b._settle(sc, "followed a link", "page", min_text=10))


def test_an_explicit_watch_page_is_left_not_shown():
    b, shown, ok = settle("Artist - Song (Explicit Video) - YouTube")
    assert not ok and b.last_skip == "guard" and shown == []


def test_a_clean_watch_page_is_shown():
    b, shown, ok = settle("Artist - Song (Clean Version) - YouTube")
    assert ok and shown == ["Artist - Song (Clean Version) - YouTube"]


def test_the_owner_can_allow_explicit_videos(monkeypatch):
    monkeypatch.setattr(YT, "EXPLICIT_VIDEOS_OK", True)
    assert browse.video_text_ok("Artist - Song (Explicit Video)")
    assert browse.Browser(decide=False)._card_ok(card("Artist - Song (Explicit Video)"))
