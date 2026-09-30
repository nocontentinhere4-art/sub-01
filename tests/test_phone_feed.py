"""web/phone_feed.json must be a list of {"url": https://www.tiktok.com/@user/video/<digits>, "note": str}."""
import json
import re
from pathlib import Path

FEED = Path(__file__).resolve().parent.parent / "web" / "phone_feed.json"
URL = re.compile(r"^https://www\.tiktok\.com/@[A-Za-z0-9._-]{1,64}/video/(\d{8,25})$")   # keep in sync with web/world/phone_util.js


def test_feed_format():
    feed = json.loads(FEED.read_text())
    assert isinstance(feed, list)
    ids = []
    for i, e in enumerate(feed):
        assert isinstance(e, dict), f"#{i} must be an object"
        m = URL.match(e.get("url", ""))
        assert m, f"#{i}: bad TikTok url {e.get('url')!r}"
        assert isinstance(e.get("note", ""), str) and len(e.get("note", "")) <= 140
        assert set(e) <= {"url", "note"}, f"#{i}: unknown keys"
        ids.append(m.group(1))
    assert len(ids) == len(set(ids)), "duplicate video"
