"""#89 live check (2026-10-04 10:05 UTC): he opened "90min | PSG - WhatsApp channel" on whatsapp.com (an app wall);
three myanimelist.net pages in a row titled only "myanimelist.net" (a bot-check interstitial), one of them counted as
"finance". Here: messaging / app pages are never link targets; a bot check (a bare-host title or the usual challenge
texts) is left at once, not shown or counted, and its site is left alone for a while (never solved or waited out); an
anime page with in-game words is not finance.

    python -m pytest tests/test_browse_walls.py -q
No network, no Chromium.
"""
import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import readings  # noqa: E402
import screens as SC  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("url", [
    "https://www.whatsapp.com/channel/0029VaPSG", "https://whatsapp.com/channel/x", "https://wa.me/123456",
    "https://t.me/psg_channel", "https://telegram.me/x", "https://discord.gg/abcd", "https://discord.com/invite/abcd",
    "https://www.messenger.com/t/x", "https://m.me/page", "https://apps.apple.com/app/id1", "https://line.me/R/ti/p/x",
    "https://play.google.com/store/apps/details?id=x", "https://psg.onelink.me/abc", "https://x.app.link/open"])
def test_messaging_and_app_pages_are_walls(url):
    assert browse.app_wall(url)
    host = browse.urllib.parse.urlsplit(url).hostname
    if browse.APP_WALL_HOST.search(host):                      # a whole messaging host: never opened at all
        assert not browse.Browser(decide=False).host_ok(host)


@pytest.mark.parametrize("url", ["https://www.90min.com/posts/psg", "https://discord.com/blog/x",
                                 "https://play.google.com/books", "https://www.apple.com/iphone/"])
def test_ordinary_pages_are_not_app_walls(url):
    assert not browse.app_wall(url)


def test_open_and_the_link_picker_never_take_an_app_wall():
    b = browse.Browser(decide=False)
    sc = b.screens["desk"]
    sc.page, sc.ctx = SimpleNamespace(url="about:blank"), object()
    assert not run(b._open(sc, "https://www.whatsapp.com/channel/0029VaPSG", "x", "page"))
    assert "messaging or app" in b.last_skip
    raw = [("https://www.whatsapp.com/channel/0029VaPSG", "90min | PSG - WhatsApp channel", 9000, True),
           ("https://discord.gg/abc", "Join our Discord server now", 9000, True),
           ("https://www.90min.com/posts/psg-win", "PSG win again in a thriller at the Parc", 9000, True)]
    sc.info = {"url": "https://www.90min.com/", "host": "90min.com", "title": "90min", "kind": "page"}
    links = b.pick_links(raw, "https://www.90min.com/", "", sc)["links"]
    hrefs = [l["href"] for l in links]
    assert "https://www.90min.com/posts/psg-win" in hrefs and not [h for h in hrefs if browse.app_wall(h)]


@pytest.mark.parametrize("title, url, wall", [
    ("myanimelist.net", "https://myanimelist.net/anime/1/x", True),
    ("www.myanimelist.net", "https://myanimelist.net/anime/1/x", True),
    ("Just a moment...", "https://myanimelist.net/", True),
    ("Attention Required! | Cloudflare", "https://x.com/", True),
    ("Checking your browser before accessing", "https://a.org/", True),
    ("Pardon Our Interruption", "https://shop.example/", True),
    ("Access to this page has been denied.", "https://www.zillow.com/", True),
    ("Cowboy Bebop - MyAnimeList.net", "https://myanimelist.net/anime/1/Cowboy_Bebop", False),
    ("Airport security: what to expect", "https://www.bbc.com/travel/x", False)])
def test_bot_check_titles(title, url, wall):
    assert browse.challenge_title(title, url) is wall


@pytest.mark.parametrize("body", [
    "Please enable JS and disable any ad blocker",                                   # DataDome
    "Press & Hold to confirm you are a human (and not a bot).",                       # PerimeterX
    "Checking if the site connection is secure. Ray ID: 8c1f2a3b4d5e6f70 Performance & security by Cloudflare"])
def test_bot_check_bodies(body):
    assert browse.Browser.wall_text(body)


class Page:
    def __init__(self, url, title, body):
        self.url, self._title, self.body, self.frames, self.main_frame = url, title, body, [], None

    async def wait_for_timeout(self, ms):
        pass

    async def add_style_tag(self, **k):
        pass

    async def title(self):
        return self._title

    async def goto(self, url, **k):
        self.url = url

    async def evaluate(self, js, *a):
        if "innerText" in js:
            return self.body
        return False


def test_a_bot_check_is_left_not_counted_and_its_site_cools_down():
    b = browse.Browser(decide=False)
    sc = b.screens["desk"]
    sc.page, sc.ctx = Page("https://myanimelist.net/anime/5114/x", "myanimelist.net", "Loading... " * 20), object()
    shown = []

    async def show(sc_):
        shown.append(sc_.info["url"])
        return True

    async def leave(sc_):
        sc_.page.url = "about:blank"
        return False
    b.show, b._leave = show, leave
    assert not run(b._settle(sc, "followed a link", "page", min_text=10))
    assert b.last_skip == "bot wall" and shown == [] and b.walled["myanimelist.net"] > time.time()
    sc.page.url = "about:blank"
    assert not run(b._open(sc, "https://myanimelist.net/anime/1/Cowboy_Bebop", "x", "page"))
    assert "bot check" in b.last_skip                          # left alone: no second try at the same check
    st = b.to_dict()
    assert "myanimelist.net" in st["walled"]
    assert browse.Browser(state=st).walled["myanimelist.net"] > time.time()   # survives a restart
    b.walled["myanimelist.net"] = time.time() - 1              # after WALL_COOLDOWN_S it may be read again
    assert "myanimelist.net" not in b.to_dict()["walled"]


def test_an_anime_page_with_in_game_words_is_not_finance():
    body = ("Trading cards and tokens in the gacha game. Fans trade shares of screenshots. "
            "The anime adaptation airs in spring.")
    assert not browse.is_finance("https://myanimelist.net/anime/52991/Sousou_no_Frieren", "Sousou no Frieren", body)
    info = browse.finance_note({"why": "w"}, "https://myanimelist.net/anime/52991/x", "Sousou no Frieren", body)
    assert "finance" not in info
    st = dict(info, url="https://myanimelist.net/anime/52991/x", title="Sousou no Frieren", kind="page")
    assert readings.kind_of(st) == "page" and SC.screen_kind(st) == "other"
    assert browse.is_finance("https://example.org/a", "Bitcoin and Solana prices", "crypto trading and memecoins")


# --- #89 live (2026-10-05 09:10 Tokyo, his phone): "We noticed that ads aren't being displayed" over the article -------

@pytest.mark.parametrize("body", [
    "Article text... We noticed that ads aren't being displayed. Please support us.",
    "Ad blocker detected. Please disable your ad blocker to continue.",
    "We've detected that you're using an ad blocker. Whitelist this site to keep reading.",
    "You've reached your free article limit. Subscribe to continue reading.",
    "This article is for subscribers only."])
def test_ad_block_and_paywall_overlays_are_walls(body):
    assert browse.overlay_wall(body)


@pytest.mark.parametrize("body", [
    "How ad blockers work, and why publishers worry about them.",
    "The best ad blockers for 2026 compared.", "Subscribe to our newsletter for weekly updates."])
def test_articles_about_ad_blockers_are_not_walls(body):
    assert not browse.overlay_wall(body)


def test_an_overlay_wall_is_left_and_its_site_cools_down_briefly():
    b = browse.Browser(decide=False)
    sc = b.screens["phone"]
    body = "Today in Tokyo. " * 40 + "We noticed that ads aren't being displayed. Please disable your ad blocker."
    sc.page, sc.ctx = Page("https://www.example-news.com/story/1", "A story", body), object()
    shown = []

    async def show(sc_):
        shown.append(sc_.info["url"])
        return True

    async def leave(sc_):
        sc_.page.url = "about:blank"
        return False
    b.show, b._leave = show, leave
    assert not run(b._settle(sc, "followed a link", "page"))
    assert b.last_skip == "overlay wall" and shown == []
    until = b.walled["example-news.com"]
    assert time.time() + browse.OVERLAY_COOLDOWN_S - 60 < until < time.time() + browse.WALL_COOLDOWN_S


def test_an_overlay_that_appears_after_the_page_loaded_is_left_at_the_next_screenshot():
    b = browse.Browser(decide=False)
    sc = b.screens["phone"]
    sc.page = Page("https://www.example-news.com/story/2", "A story", "Ad blocker detected. Please disable your ad blocker.")
    left = []

    async def leave(sc_):
        left.append(sc_.page.url)
    b._leave = leave
    assert run(b._shoot(sc)) is False and left and b.last_skip == "overlay wall"
    assert b.walled["example-news.com"] > time.time()


# region walls (live 2026-10-07 08:00 Tokyo: "Sorry, BBC iPlayer isn't available in your region" was shown in the card)
@pytest.mark.parametrize("title, wall", [
    ("Sorry, BBC iPlayer isn't available in your region", True),
    ("BBC iPlayer - iPlayer is not available in your country", True),
    ("Content unavailable in your location", True),
    ("Video not available in your country", True),
    ("Why Netflix shows aren't available in your country", False),          # an article about it
    ("Parental Controls – BBC iPlayer", False),
    ("BBC iPlayer - Home", False)])
def test_region_wall_titles(title, wall):
    assert browse.challenge_title(title, "https://www.bbc.co.uk/iplayer") is wall


@pytest.mark.parametrize("body", [
    "Sorry, BBC iPlayer isn't available in your region. BBC iPlayer only works in the UK. Sorry, it's due to rights issues.",
    "This video is not available in your country.",
    "The uploader has not made this video available in your country.",
    "This content is unavailable in your region.",
    "We're sorry, this service is not available outside the United States.",
    "This page is geo-blocked."])
def test_region_wall_bodies(body):
    assert browse.Browser.wall_text(body)


@pytest.mark.parametrize("body", [
    "Streaming services restrict what is available in your region by licence. " * 40,      # a long article about it
    "Opening hours: the museum shop is available in your visit's ticket price."])
def test_articles_about_region_locks_are_not_walls(body):
    assert not browse.Browser.wall_text(body)


def test_a_region_wall_is_left_not_shown_and_its_site_cools_down():
    b = browse.Browser(decide=False)
    sc = b.screens["desk"]
    sc.page, sc.ctx = Page("https://www.bbc.co.uk/iplayer/region", "BBC iPlayer",
                           "Sorry, BBC iPlayer isn't available in your region. BBC iPlayer only works in the UK."), object()
    shown = []

    async def show(sc_):
        shown.append(sc_.info["url"])
        return True

    async def leave(sc_):
        sc_.page.url = "about:blank"
        return False
    b.show, b._leave = show, leave
    assert not run(b._settle(sc, "followed a link", "page"))
    assert b.last_skip == "bot wall" and shown == []
    assert b.walled["bbc.co.uk"] > time.time() + browse.WALL_COOLDOWN_S - 60
