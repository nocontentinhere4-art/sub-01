"""Short videos on his phone (#56 part 2): YouTube Shorts and TikTok, one place per site.

- YouTube Shorts: a results search for "<query> #shorts" (Restricted Mode: the PREF f2=8000000 cookie every context
  carries); the Shorts in its ytInitialData are parsed by search_sources.parse_youtube (/shorts/<id> links).
- TikTok: a tag page (www.tiktok.com/tag/<tag>; robots.txt disallows /search and /search/video, allows /tag), logged
  out unless #60's session exists (browse.Browser._use picks the context; view_only.py filters private pages and
  actions on both). Comments, likes, follow and login boxes are hidden (HIDE_TIKTOK); a login wall is left; a page
  whose caption fails the guard is left.
- Every short plays muted (Chromium --mute-audio + browse.VIDEO_JS) for at most SHORTS_MAX_S, then the next shorts
  in the queue are the vote's options (local options: no paid call).
Pure helpers; browse.Browser._shorts drives the feed.
"""
import re
import urllib.parse

from search_sources import _dedup, _result, parse_html, strip_tags

SHORTS_MAX_S = 45.0                    # a short is watched at most this long (real seconds), then the next one
TIKTOK_SHARE = 0.35                    # feeds that start on TikTok (else YouTube Shorts)
TIKTOK_VIDEO = re.compile(r"^https://www\.tiktok\.com/@([\w.]{2,30})/video/(\d{8,25})$")


def parse_tiktok(text, base="https://www.tiktok.com/"):
    """A TikTok tag page as Chromium renders it (logged out): its video links, the caption next to each, the
    creator. Nothing when the page is only a login wall."""
    out = []
    for a in parse_html(text).find_all("a"):
        url = urllib.parse.urljoin(base, a.attrs.get("href", "")).split("?")[0]
        m = TIKTOK_VIDEO.match(url)
        if not m:
            continue
        box = a.parent
        cap = ""
        for _ in range(3):                                   # the caption sits next to the link in the item
            if box is None:
                break
            d = next((n for n in box.iter() if n.attrs.get("data-e2e") in ("video-desc", "challenge-item-desc")
                      or "desc" in " ".join(n.cls()).lower()), None)
            if d is not None and d.text():
                cap = d.text()
                break
            box = box.parent
        cap = cap or a.attrs.get("title") or a.text()
        out.append(_result(url, strip_tags(cap) or f"a video by @{m.group(1)}", f"@{m.group(1)}", video=True,
                           short=True, channel=f"@{m.group(1)}", hashtags=re.findall(r"#\w+", cap)[:6]))
    return _dedup(out)


def tiktok_tag(q):
    return re.sub(r"[^a-z0-9]", "", (q or "").lower())[:40]


def tiktok_url(q):
    return f"https://www.tiktok.com/tag/{tiktok_tag(q)}"


TIKTOK_HOST = re.compile(r"(^|\.)tiktok\.com$", re.I)
HIDE_TIKTOK = """[data-e2e*="comment"],[class*="CommentList"],[class*="DivCommentContainer"],[data-e2e="browse-like"],
[data-e2e="follow-button"],[class*="DivActionItemContainer"],[class*="LoginModal"],[id*="login"]{display:none !important}"""


def feed_order(rng, share=TIKTOK_SHARE):
    """Which feed to try first: TikTok `share` of the time, else YouTube Shorts; the other one is the fallback."""
    return ["tiktok", "shorts"] if rng.random() < share else ["shorts", "tiktok"]


def watch_seconds(w):
    """A short's watch time: never longer than SHORTS_MAX_S."""
    return min(float(w), SHORTS_MAX_S)


def is_tiktok(host):
    return bool(TIKTOK_HOST.search((host or "").rstrip(".")))


def caption_ok(page_title):
    """A TikTok page's caption (its title without " | TikTok"): the guard and the chat filter (browse.video_text_ok)."""
    from browse import video_text_ok
    return video_text_ok(re.sub(r"\s*\|\s*TikTok$", "", page_title or ""))


async def settle(page, host, page_title):
    """On a TikTok page before it is shown: hide comments, likes, follow and login boxes; None if it may be shown,
    else why it must be left."""
    if not is_tiktok(host):
        return None
    await page.add_style_tag(content=HIDE_TIKTOK)
    return None if caption_ok(page_title) else "guard"
