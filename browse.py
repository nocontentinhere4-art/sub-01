"""What is on his screens: a real headless browser on the open web, for the computer and for the phone.

While the life simulation is at the computer ("research") or on the phone, a headless Chromium really loads web pages:
it searches (Bing, SafeSearch strict) for words from the chat or from what he read last, opens results, follows links
that match his interests, scrolls, and takes a screenshot every few seconds. The page shows the screenshots on the
monitor and on the phone in his hand. The desk uses a desktop viewport, the phone a mobile one.

Read-only by construction: it never types, logs in, submits forms, downloads, buys or touches a wallet; it only loads
pages and scrolls. Because the screens are shown live to everyone, a guard skips pages before they are shown:
adult, gore, self-harm, extremism and drug sites/pages, gambling, and crypto trading sites (no buy pressure). Requests
to private or internal addresses (localhost, cloud metadata, LAN) are blocked for every resource, not only pages.

Brain decides (`decide=True`, the default in browse_service.py): when he has finished a page, step() does not move on
by itself; it returns the page (title, visible text, up to 40 safe links) so that the live server can have an AI list
options (eyes.py) and the brain model pick one (brain_vote.py); act() then carries the chosen action out. Bot checks
(CAPTCHA, "unusual traffic") are never solved: such pages are left.

Optional: needs `pip install playwright` + a Chromium (`playwright install --with-deps chromium`). Without it the
server runs as before (Wikipedia reading only).
"""
import asyncio
import ipaddress
import os
import random
import re
import socket
import time
import urllib.parse

KEEP = 60                              # visits kept in the log
SCROLL_EVERY_S = 7.0                   # seconds between scroll + screenshot on a page
SCROLLS = (3, 7)                       # scrolls per page before moving on
NAV_TIMEOUT_MS = 20000
DECIDE_WAIT_S = 90                     # waiting longer than this for the brain's choice: wander on as before
PAGE_LINKS = 40
VIDEO_LINK = re.compile(r"(youtube\.com/watch|youtu\.be/|vimeo\.com/\d|nicovideo\.jp/watch|dailymotion\.com/video|"
                        r"/videos?/|/watch\b)", re.I)
LINKS_JS = """() => [...document.querySelectorAll('a[href]')].map(a => {
  const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
  return [a.href, (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().slice(0, 120), r.width * r.height,
          r.bottom > 0 && r.top < innerHeight * 3 && cs.visibility !== 'hidden' && cs.display !== 'none'];
})"""
DESK = {"viewport": {"width": 1280, "height": 800}, "device_scale_factor": 1}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
         "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/17.6 Mobile/15E148 Safari/604.1"}
DESK_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/129.0.0.0 Safari/537.36")

# --- guard ---------------------------------------------------------------------------------------------------------
BAD_HOST = re.compile(
    r"porn|xxx|xvideo|xhamster|redtube|youporn|sex|nsfw|onlyfans|fansly|hentai|escort|camgirl|chaturbate|stripchat|"
    r"livejasmin|adult|nude|naked|erotic|fetish|"
    r"casino|poker|betting|bet365|sportsbet|stake\.com|gambl|slots|lottery|"
    r"binance|coinbase|kraken|bybit|okx|kucoin|bitget|mexc|gate\.io|htx|huobi|crypto\.com|dexscreener|dextools|"
    r"pump\.fun|gmgn|birdeye|raydium|jup\.ag|jupiter|uniswap|pancakeswap|coinmarketcap|coingecko|tradingview|"
    r"phantom\.app|metamask|solscan|etherscan|"
    r"4chan|8kun|kiwifarms|bestgore|liveleak|theync|"
    r"railway\.app|up\.railway", re.I)
# words that must not be on a page shown live (title anywhere; body when repeated)
BAD_WORDS = re.compile(
    r"\b(porn\w*|xxx|nsfw|nude|nudes|naked|hentai|onlyfans|escort\w*|camgirl\w*|fetish\w*|erotic\w*|"
    r"gore|beheading|dismember\w*|suicide|self[- ]?harm|rape|raped|child abuse|"
    r"terrorist\w*|jihad\w*|neo-?nazi\w*|white power|"
    r"cocaine|heroin|meth|fentanyl|"
    r"casino\w*|sportsbook|gambling|"
    r"memecoin\w*|altcoin\w*|airdrop\w*|presale|pump and dump|100x)\b", re.I)
BOT_WALL = re.compile(r"attention required|just a moment|access denied|are you a (robot|human)|verify you are human|"
                      r"captcha|403 forbidden|404 not found|page not found|enable javascript|unusual traffic|"
                      r"before you continue|consent", re.I)
# bot checks recognised in the page text or by their challenge frames: he leaves these pages, never solves them
# (only on short pages: a real bot check is a page of its own, not a sentence inside an article)
WALL_MAX_CHARS = 2000
BODY_WALL = re.compile(r"unusual traffic from your (computer|network)|verify you are (a )?human|"
                       r"checking (if the site connection is secure|your browser)|"
                       r"complete the security check|please solve (this|the) (captcha|puzzle)", re.I)
# a visible, checkbox-sized challenge frame (the invisible reCAPTCHA v3 badge and tiny widgets do not count)
WALL_FRAMES = """() => [...document.querySelectorAll('iframe[src*="recaptcha"], iframe[src*="hcaptcha"], '
  + 'iframe[src*="challenges.cloudflare.com"], iframe[src*="captcha-delivery"]')].some(f => {
    if (f.closest('.grecaptcha-badge')) return false;
    const r = f.getBoundingClientRect(), cs = getComputedStyle(f);
    return r.width >= 200 && r.height >= 60 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.1; })"""
LOGIN_LINK = re.compile(r"log ?in|sign ?(in|up)|register|account|cart|checkout|basket|subscribe|donate|password|"
                        r"privacy|cookie|terms|legal|imprint|impressum|careers|advertis", re.I)
SKIP_EXT = re.compile(r"\.(pdf|zip|rar|7z|exe|dmg|apk|mp3|mp4|mov|avi|mkv|iso|tar|gz|docx?|xlsx?|pptx?)(\?|$)", re.I)
HIDE_BANNERS = """#onetrust-banner-sdk,#onetrust-consent-sdk,.fc-consent-root,#CybotCookiebotDialog,.qc-cmp2-container,
#usercentrics-root,#didomi-host,.truste_overlay,.truste_box_overlay{display:none !important}"""
# fixed/sticky overlays about cookies, consent, sign-ups, or covering most of the screen are hidden (never clicked)
UNBLOCK_JS = """() => {
  for (const el of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    const t = (el.innerText || '').toLowerCase();
    if (t.length < 1500 && /cookie|consent|gdpr|we use|accept all|newsletter|subscribe|sign up|log in to|open in app|get the app/.test(t))
      el.style.setProperty('display', 'none', 'important');
  }
  for (const el of [document.documentElement, document.body]) if (el) { el.style.setProperty('overflow', 'auto', 'important'); }
}"""
SEEDS = [                              # where he starts when nothing else pulls him (no search engine needed)
    "https://en.wikipedia.org/wiki/Special:Random", "https://news.ycombinator.com/", "https://www.bbc.com/news",
    "https://www3.nhk.or.jp/nhkworld/", "https://apod.nasa.gov/apod/astropix.html", "https://www.japantimes.co.jp/",
    "https://www.timeout.com/tokyo", "https://github.com/trending", "https://www.theverge.com/",
    "https://www.atlasobscura.com/", "https://www.openculture.com/", "https://www.nationalgeographic.com/",
    "https://www.theguardian.com/international", "https://arstechnica.com/", "https://www.quantamagazine.org/",
    "https://www.metmuseum.org/art/collection", "https://www.archive.org/", "https://www.spoon-tamago.com/",
]
FAMILIAR = ["Kichijoji", "Inokashira Park", "Tokyo bakery", "how dreams work", "sleep science", "ramen", "Ghibli Museum",
            "night city photography", "lo-fi music", "how the brain works", "Japanese convenience store", "Tokyo trains"]
STOP = set("the a an and or but if of to in on at for with from by is are was were be been it this that these those "
           "i you he she we they me my your his her our their what why how who when where which not no yes so very "
           "just can will would could should do does did have has had il lo la gli le un una e o ma di da con su "
           "per tra fra che chi non si sono sei era ciao hello hi lol ok".split())


def words(text):
    return [w for w in re.findall(r"[a-zA-ZÀ-ÿ]{4,}", (text or "").lower()) if w not in STOP]


def host_ok(host):
    """Hostname is public and not on the block list (DNS is checked separately, see Guard.resolves_public)."""
    if not host or BAD_HOST.search(host) or host.rstrip(".").lower() in ("localhost", "metadata", "metadata.google.internal"):
        return False
    try:                                                    # literal IPs: only public ones
        ip = ipaddress.ip_address(host.strip("[]"))
        return ip.is_global
    except ValueError:
        return not host.endswith((".local", ".internal", ".localhost", ".lan", ".home", ".corp"))


def url_ok(url):
    try:
        u = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    return (u.scheme in ("http", "https") and u.port in (None, 80, 443) and not u.username
            and host_ok(u.hostname or "") and not SKIP_EXT.search(u.path))


def text_ok(title, body):
    """Title must be clean; the body may mention a word once (news) but not be about it."""
    if BAD_WORDS.search(title or ""):
        return False
    return len(BAD_WORDS.findall((body or "")[:6000])) < 3


class Guard:
    """Blocks requests to private/internal addresses (SSRF) for every resource the browser loads."""

    def __init__(self, via_proxy=False):
        self.cache = {}                                     # host -> (ok, expires)
        self.via_proxy = via_proxy                          # behind a proxy, DNS is resolved by the proxy

    async def resolves_public(self, host):
        if self.via_proxy:
            return True
        now = time.time()
        if host in self.cache and self.cache[host][1] > now:
            return self.cache[host][0]
        try:
            ip = ipaddress.ip_address(host.strip("[]"))
            ok = ip.is_global
        except ValueError:
            try:
                infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
                ok = bool(infos) and all(ipaddress.ip_address(i[4][0].split("%")[0]).is_global for i in infos)
            except OSError:
                ok = False
        self.cache[host] = (ok, now + 300)
        if len(self.cache) > 5000:
            self.cache.clear()
        return ok

    async def route(self, route):
        req = route.request
        url = req.url
        if url.startswith(("data:", "blob:")):
            return await route.continue_()
        u = urllib.parse.urlsplit(url)
        if (u.scheme not in ("http", "https") or u.port not in (None, 80, 443) or not host_ok(u.hostname or "")
                or req.resource_type in ("media", "websocket", "eventsource", "manifest")
                or (req.is_navigation_request() and SKIP_EXT.search(u.path))
                or not await self.resolves_public(u.hostname)):
            return await route.abort()
        if req.method not in ("GET", "HEAD") and req.is_navigation_request():
            return await route.abort()                      # never submits anything
        await route.continue_()


class Screen:
    """One device (desk or phone): its browser context, current page and latest screenshot."""

    def __init__(self, name):
        self.name = name
        self.ctx = None
        self.page = None
        self.shot = None                                    # latest JPEG bytes
        self.shot_id = 0
        self.info = None                                    # {title, url, host, why, t, kind}
        self.scrolls_left = 0
        self.next_at = 0.0
        self.pending_link = None                            # result to open next (after a search page)
        self.history = []                                   # urls shown on this screen, newest last (for "back")
        self.awaiting = None                                # page handed to the brain for a decision
        self.awaiting_since = 0.0

    def status(self):
        return dict(self.info, id=self.shot_id, device=self.name) if self.info and self.shot else None


class Browser:
    """Drives both screens. `step(device, ...)` is called by the live server every couple of seconds."""

    def __init__(self, state=None, rng=None, proxy=None, ignore_tls=False, decide=False):
        s = state or {}
        self.decide = decide                                # True: the brain picks the next action (act())
        self.log = s.get("log", [])                         # visits shown: [{t, device, title, url, host, why}]
        self.used = set(s.get("used", []))                  # chat texts already searched
        self.rng = rng or random.Random()
        self.pw = None
        self.browser = None
        self.screens = {"desk": Screen("desk"), "phone": Screen("phone")}
        self.proxy = proxy or os.environ.get("BROWSE_PROXY") or None
        self.ignore_tls = ignore_tls or os.environ.get("BROWSE_IGNORE_TLS") == "1"   # sandbox proxies only
        self.guard = Guard(via_proxy=bool(self.proxy))
        self.lock = asyncio.Lock()
        self.failures = 0

    def to_dict(self):
        return {"log": self.log[-KEEP:], "used": list(self.used)[-200:]}

    @staticmethod
    def available():
        try:
            import playwright.async_api  # noqa: F401
            return True
        except ImportError:
            return False

    # --- lifecycle -----------------------------------------------------------------------------------------------
    async def _ensure(self, device):
        if self.browser is None or not self.browser.is_connected():
            from playwright.async_api import async_playwright
            if self.pw is None:
                self.pw = await async_playwright().start()
            # Chromium's own sandbox stays on unless we run as root (Docker default), where Chromium refuses it.
            # The browser gets a minimal environment: none of the server's secrets (API tokens, site password).
            root = hasattr(os, "geteuid") and os.geteuid() == 0
            kw = {"args": ["--disable-dev-shm-usage", "--mute-audio", "--disable-extensions",
                           "--disable-background-networking", "--disable-sync", "--no-first-run",
                           "--renderer-process-limit=2", "--js-flags=--max-old-space-size=256",
                           "--disable-gpu", "--disable-software-rasterizer"]
                          + (["--no-sandbox"] if root else []),
                  "chromium_sandbox": not root,
                  "env": {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TZ", "TMPDIR",
                                                                      "PLAYWRIGHT_BROWSERS_PATH", "FONTCONFIG_PATH")}}
            if os.environ.get("BROWSE_CHROMIUM"):
                kw["executable_path"] = os.environ["BROWSE_CHROMIUM"]
            if self.proxy:
                kw["proxy"] = {"server": self.proxy}
            self.browser = await self.pw.chromium.launch(**kw)
            for sc in self.screens.values():
                sc.ctx = sc.page = None
        sc = self.screens[device]
        if sc.ctx is None:
            opts = dict(DESK if device == "desk" else PHONE, accept_downloads=False, java_script_enabled=True,
                        locale="en-US", timezone_id="Asia/Tokyo", ignore_https_errors=self.ignore_tls,
                        permissions=[], color_scheme="light", service_workers="block")
            if device == "desk":
                opts["user_agent"] = DESK_UA
            sc.ctx = await self.browser.new_context(**opts)
            await sc.ctx.route("**/*", self.guard.route)
            sc.page = await sc.ctx.new_page()
            sc.ctx.on("page", lambda p: asyncio.ensure_future(p.close()) if p != sc.page else None)   # no pop-ups
            sc.page.on("dialog", lambda d: asyncio.ensure_future(d.dismiss()))
            sc.page.set_default_timeout(NAV_TIMEOUT_MS)
        return sc

    async def close(self, device=None):
        """Close one screen (he put the phone down) or everything (asleep / shutting down)."""
        for name, sc in self.screens.items():
            if device in (None, name) and sc.ctx is not None:
                try:
                    await sc.ctx.close()
                except Exception:
                    pass
                sc.ctx = sc.page = None
                sc.scrolls_left, sc.next_at, sc.pending_link = 0, 0.0, None
        if device is None and self.browser is not None:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if device is None and self.pw is not None:          # the driver itself may be dead: start a fresh one next time
            try:
                await self.pw.stop()
            except Exception:
                pass
            self.pw = None

    # --- one step ------------------------------------------------------------------------------------------------
    async def step(self, device, heard=(), interest=None):
        """Scroll the current page or open the next one; returns the new screen status when a screenshot was taken."""
        sc = self.screens[device]
        if time.time() < sc.next_at:
            return None
        async with self.lock:
            try:
                sc = await self._ensure(device)
                if self.decide and sc.awaiting is not None:      # the brain is choosing: hold the page
                    if not self._fresh_chat(heard) and time.time() - sc.awaiting_since < DECIDE_WAIT_S:
                        return None
                    sc.awaiting = None                          # a new chat message, or no answer: as before
                if sc.scrolls_left > 0 and sc.info:
                    sc.scrolls_left -= 1
                    await sc.page.evaluate("() => window.scrollBy({top: innerHeight * 0.7, behavior: 'smooth'})")
                    await sc.page.wait_for_timeout(900)
                    if not await self._shoot(sc):                   # turned into a bot check: left
                        sc.next_at = time.time() + 15
                        return None
                elif (self.decide and sc.info and sc.info.get("kind") in ("page", "search") and sc.page is not None
                      and not self._fresh_chat(heard)):
                    page = await self.page_info(sc)
                    if page["links"] or page["can_back"]:
                        sc.awaiting, sc.awaiting_since = page, time.time()
                        return {"decide": page, "device": sc.name}
                    ok = await self._next(sc, list(heard), interest)
                    if not ok:
                        sc.next_at = time.time() + 15
                        return None
                else:
                    ok = await self._next(sc, list(heard), interest)
                    if not ok:
                        sc.next_at = time.time() + 15
                        return None
                sc.next_at = time.time() + SCROLL_EVERY_S * (0.8 + 0.5 * self.rng.random())
                self.failures = 0
                return sc.status()
            except Exception as e:
                self.failures += 1
                print(f"browse ({device}):", repr(e)[:160], flush=True)
                sc.next_at = time.time() + min(120, 10 * self.failures)
                dead = re.search(r"Connection closed|Target crashed|Browser has been closed|driver", repr(e))
                if dead or self.failures >= 3:                 # crashed renderer or driver: restart everything cleanly
                    await self.close()
                return None

    def _fresh_chat(self, heard):
        return any(text not in self.used for text in list(heard)[-5:])

    async def page_info(self, sc):
        """What the eyes may see: title, visible text and up to PAGE_LINKS links that pass the guard (numbered)."""
        page = sc.page
        text = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 6000)")
        raw = await page.evaluate(LINKS_JS)
        cur = urllib.parse.urlsplit(page.url)
        search = sc.info.get("kind") == "search"
        seen, cand = set(), []
        for href, label, area, visible in raw:
            label = " ".join(label.split())
            if (len(label) < 4 or not url_ok(href) or LOGIN_LINK.search(label) or BAD_WORDS.search(label)
                    or href in seen):
                continue
            u = urllib.parse.urlsplit(href)
            if (u.netloc, u.path) == (cur.netloc, cur.path) or (search and u.netloc == cur.netloc):
                continue                                        # same page; on a results page only the results
            seen.add(href)
            cand.append((bool(visible), area, href, label, u.hostname or ""))
        cand.sort(key=lambda c: (not c[0], -c[1]))
        links = [{"id": f"L{i + 1}", "href": h, "text": t[:100], "host": host.removeprefix("www."), "area": round(a),
                  "video": bool(VIDEO_LINK.search(h))} for i, (_, a, h, t, host) in enumerate(cand[:PAGE_LINKS])]
        return {"device": sc.name, "url": page.url, "title": sc.info.get("title", ""), "host": sc.info.get("host", ""),
                "kind": sc.info.get("kind"), "text": " ".join(text.split())[:1500], "links": links,
                "can_back": len(sc.history) >= 2}

    async def act(self, device, action, why="", interest=None):
        """Carry out the action the brain chose for the page it was given; returns the new screen status or None."""
        sc = self.screens[device]
        page, sc.awaiting = sc.awaiting, None
        if page is None or sc.page is None:
            return None
        kind, why = action.get("action"), why or "his brain picked it"
        async with self.lock:
            try:
                ok = False
                if kind in ("click", "open_video"):
                    href = next((l["href"] for l in page["links"] if l["id"] == action.get("target")), None)
                    ok = bool(href) and await self._open(sc, href, f"{action.get('label', '')} — {why}", "page")
                elif kind == "search" and action.get("target"):
                    ok = await self._search(sc, action["target"], f"searched “{action['target']}” — {why}")
                elif kind == "back" and len(sc.history) >= 2:
                    sc.history.pop()
                    ok = await self._open(sc, sc.history.pop(), f"went back — {why}", "page")
                elif kind == "scroll":
                    sc.scrolls_left = self.rng.randint(1, 3)
                    if sc.info:
                        sc.info = dict(sc.info, why=f"kept reading — {why}")
                    ok = True
                if not ok:                                      # leave, or the chosen page could not be shown
                    ok = await self._next(sc, [], interest)
                sc.next_at = time.time() + SCROLL_EVERY_S
                self.failures = 0
                return sc.status() if ok else None
            except Exception as e:
                print(f"browse ({device}) act:", repr(e)[:160], flush=True)
                return None

    async def _next(self, sc, heard, interest):
        """Pick where to go: a fresh chat message -> search; a result from the last search; a link that matches
        his interests; else a search on what he read last or something familiar; sometimes a seed site."""
        if sc.pending_link:
            url, why = sc.pending_link
            sc.pending_link = None
            if await self._open(sc, url, why, "page"):
                return True
        for text in reversed(heard[-5:]):
            if text in self.used:
                continue
            self.used.add(text)
            q = " ".join(sorted(words(text), key=len, reverse=True)[:3])
            if q:
                return await self._search(sc, q, f"from chat: “{text[:60]}”")
            break
        r = self.rng.random()
        if sc.info and sc.info.get("kind") == "page" and r < 0.55:
            link = await self._pick_link(sc, interest)
            if link and await self._open(sc, link[0], f"followed “{' '.join(link[1].split())[:50]}” from {sc.info['host']}",
                                         "page"):
                return True
        if r < 0.8:
            topic = interest or self.rng.choice(FAMILIAR)
            return await self._search(sc, topic, f"curious about “{topic[:50]}”")
        return await self._open(sc, self.rng.choice(SEEDS), "opened a site he likes", "page")

    async def _search(self, sc, q, why):
        """Search the web (Bing, SafeSearch strict); if it shows no results (bot check), search Wikipedia instead and
        leave by one of the article's external sources. Either way the next step opens a page on the open web."""
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "adlt": "strict", "setlang": "en"})
        results = []
        if await self._open(sc, url, why, "search", title=f"{q} — search", min_text=0, shoot=False):
            results = await self._links(sc, "#b_results li.b_algo h2 a, li.b_algo a.tilk")
            results = [(u, t) for u, t in results if "bing.com" not in u and "microsoft.com" not in u]
            if results and not await self.show(sc):                   # only a results page is worth showing
                results = []
        if not results:
            wiki = "https://en.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"search": q})
            if not await self._open(sc, wiki, why, "search", title=f"{q} — Wikipedia"):
                return False
            if "/wiki/Special:Search" in sc.page.url:           # a results list: open the first hit next
                results = await self._links(sc, ".mw-search-result-heading a")
            else:                                               # an article: leave by one of its sources
                results = await self._links(sc, "#bodyContent a.external.text, #bodyContent .references a.external")
                results = [(u, t) for u, t in results if "wikipedia.org" not in u and "wikimedia" not in u
                           and "archive.org" not in u and "doi.org" not in u]
                self.rng.shuffle(results)
            sc.scrolls_left = self.rng.randint(1, 3)
        else:
            sc.scrolls_left = 0
        if results and not self.decide:                     # brain decides: it picks among the results itself
            u, t = results[min(len(results) - 1, int(self.rng.random() ** 2 * 4))]   # mostly the top results
            sc.pending_link = (u, f"searched “{q[:40]}”, opened “{t[:50]}”")
        return True

    async def _links(self, sc, selector):
        found = await sc.page.evaluate("""sel => [...document.querySelectorAll(sel)]
            .map(a => [a.href, (a.innerText || '').trim()]).filter(x => x[0].startsWith('http'))""", selector)
        return [(u, " ".join(t.split()[:12])) for u, t in found if url_ok(u) and not BAD_WORDS.search(t)]

    async def _pick_link(self, sc, interest):
        links = await sc.page.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => {
            const r = a.getBoundingClientRect(); return [a.href, (a.innerText || a.title || '').trim().slice(0, 120), r.width * r.height]; })""")
        want = set(words(interest or "")) | set(words(sc.info.get("title", "")))
        cur = urllib.parse.urlsplit(sc.page.url)
        cand = []
        for href, text, area in links:
            if len(text) < 12 or not url_ok(href) or LOGIN_LINK.search(text) or BAD_WORDS.search(text):
                continue
            u = urllib.parse.urlsplit(href)
            if (u.netloc, u.path) == (cur.netloc, cur.path):
                continue
            score = 1 + 3 * len(want & set(words(text))) + (0.5 if u.netloc != cur.netloc else 0) + min(1, area / 20000)
            cand.append((score * (0.5 + self.rng.random()), href, text))
        cand.sort(reverse=True)
        return (cand[0][1], cand[0][2]) if cand else None

    async def _open(self, sc, url, why, kind, title=None, min_text=80, shoot=True):
        """Load a page; if the guard rejects it, leave it (blank) so nothing of it is shown, scrolled or followed."""
        if not url_ok(url):
            return False
        page = sc.page
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        except Exception as e:
            if "Timeout" not in repr(e):
                print(f"browse: could not open {url[:80]}: {repr(e)[:100]}", flush=True)
                return await self._leave(sc)
        await page.add_style_tag(content=HIDE_BANNERS)
        await page.wait_for_timeout(2200)
        await page.evaluate(UNBLOCK_JS)
        if not url_ok(page.url):                                       # redirected somewhere it must not be
            return await self._leave(sc)
        page_title = (await page.title() or "").strip()
        body = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 20000)")
        reason = ("guard" if not text_ok(page_title, body) else "empty" if len(body.strip()) < min_text
                  else "bot wall" if BOT_WALL.search(page_title) or await self._walled(page, body) else None)
        if reason:
            print(f"browse: skipped {urllib.parse.urlsplit(page.url).hostname} ({reason}: {page_title[:40]!r})", flush=True)
            return await self._leave(sc)
        host = urllib.parse.urlsplit(page.url).hostname or ""
        sc.info = {"title": (title or page_title or host)[:140], "url": page.url, "host": host.removeprefix("www."),
                   "why": why.replace("opened “”", f"opened {host.removeprefix('www.')}"), "t": time.time(), "kind": kind}
        sc.scrolls_left = self.rng.randint(*SCROLLS) if kind == "page" else 0
        if shoot and not await self.show(sc):
            return False
        return True

    @staticmethod
    def wall_text(body):
        return len(body.strip()) < WALL_MAX_CHARS and bool(BODY_WALL.search(body))

    async def _walled(self, page, body=None):
        """A bot check (CAPTCHA, 'unusual traffic', browser challenge) fills the page."""
        if body is None:
            body = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 20000)")
        if len(body.strip()) >= WALL_MAX_CHARS:
            return False
        return self.wall_text(body) or await page.evaluate(WALL_FRAMES)

    async def show(self, sc):
        """Screenshot the current page and log the visit (only pages that passed the guard get here).
        False when the page turned out to be a bot check (then nothing is shown or logged)."""
        if not await self._shoot(sc):
            return False
        i = sc.info
        self.log = (self.log + [{"t": i["t"], "device": sc.name, "title": i["title"], "url": i["url"], "host": i["host"],
                                 "why": i["why"]}])[-KEEP:]
        if not sc.history or sc.history[-1] != i["url"]:
            sc.history = (sc.history + [i["url"]])[-20:]
        return True

    async def _leave(self, sc):
        sc.scrolls_left = 0
        if sc.info:
            sc.info = dict(sc.info, kind="left")                       # nothing on it is followed or scrolled
        try:
            await sc.page.goto("about:blank")
        except Exception:
            pass
        return False

    async def _shoot(self, sc):
        if await self._walled(sc.page):                                 # a page can turn into a bot check later
            print(f"browse: left {urllib.parse.urlsplit(sc.page.url).hostname} (bot wall)", flush=True)
            await self._leave(sc)
            return False
        sc.shot = await sc.page.screenshot(type="jpeg", quality=72 if sc.name == "desk" else 68)
        sc.shot_id += 1
        return True
