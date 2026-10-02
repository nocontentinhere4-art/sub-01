"""What is on his screens: a real headless browser on the open web, for the computer and for the phone.

While the life simulation is at the computer ("research") or on the phone, a headless Chromium really loads web pages:
it searches (Bing, SafeSearch strict) for words from the chat or from what he read last, opens results, follows links
that match his interests, scrolls, and takes a screenshot every few seconds. The page shows the screenshots on the
monitor and on the phone in his hand. The desk uses a desktop viewport, the phone a mobile one.

Read-only except for one thing (#29): it may type a filtered query into a site's own search box and press Enter
(`site_search`). The field is checked here, in the browser's process, right before typing (search_field_ok): a
search input (type=search, role=searchbox, or a GET form whose action looks like search) that is not a password,
email, comment, message, login or payment field, in a form without a password field. Nothing else is ever typed; it
never logs in, signs up, submits other forms, downloads, buys or touches a wallet. Cookie / consent banners are
dismissed with their reject or "necessary only" button (choose_dismiss; never an accept button), other modals with
their close button; a sign-in wall is left, never passed. Because the screens are shown live to everyone, a guard
skips pages before they are shown: adult, gore, self-harm, extremism and drug sites/pages, gambling, crypto trading
and wallets (no buy pressure), login / sign-up / checkout pages and bot walls. Everything else that is legal and
safe-for-work is allowed. Requests to private or internal addresses (localhost, cloud metadata, LAN) are blocked for
every resource, not only pages. A chain of pages ends after MAX_CHAIN (30) pages; the brain can leave earlier.

Brain decides (`decide=True`, the default in browse_service.py): when he has finished a page, step() does not move on
by itself; it returns the page (title, visible text, up to 40 safe links) so that the live server can have an AI list
options (eyes.py) and the brain model pick one (brain_vote.py); act() then carries the chosen action out (click,
search, site_search, next_page, open_comments, open_video, play_video, back, scroll, leave). Bot checks
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
MAX_CHAIN = 30                         # pages in a row before he wanders off to something new (#29)
SITE_SEARCH_NAV_MS = 8000              # wait for the results page after Enter (some sites update in place)
LINKS_JS = """() => [...document.querySelectorAll('a[href]')].map(a => {
  const r = a.getBoundingClientRect(), cs = getComputedStyle(a);
  return [a.href, (a.innerText || a.title || a.getAttribute('aria-label') || '').trim().slice(0, 120), r.width * r.height,
          r.bottom > 0 && r.top < innerHeight * 3 && cs.visibility !== 'hidden' && cs.display !== 'none',
          (a.getAttribute('rel') || '').toLowerCase(), a.classList.contains('external'),
          (a.getAttribute('aria-label') || '').trim().slice(0, 60)];
})"""
# link kinds the eyes may propose as their own actions: the next page of a list, a comment thread
NEXT_TEXT = re.compile(r"^(next|next page|next ?[›»→>]+|older( posts| entries| stories)?|more|more stories|"
                       r"load more|show more|[›»→]|page suivante)$", re.I)
COMMENTS_TEXT = re.compile(r"^\d[\d,.]*k?\s+(comments?|replies|answers)$|^(comments?|discuss|discussion|"
                           r"(view|read|show|see|all) (all )?(\d+ )?comments?|join the discussion)$", re.I)
COMMENTS_HREF = re.compile(r"/comments/|[#?&]comments?\b|/item\?id=\d+$|#disqus|/discussion", re.I)


def link_kind(href, label, rel="", aria=""):
    """'next' for pagination / "next" links, 'comments' for a comment thread, else None."""
    t = " ".join((label or aria or "").split())
    if "next" in rel.split() or NEXT_TEXT.match(t) or (re.match(r"^next\b", aria or "", re.I) and len(t) <= 12):
        return "next"
    if COMMENTS_TEXT.match(t) or (COMMENTS_HREF.search(href or "") and re.search(r"comment|discuss|repl", t, re.I)):
        return "comments"
    return None
DESK = {"viewport": {"width": 1280, "height": 800}, "device_scale_factor": 1}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2, "is_mobile": True, "has_touch": True,
         "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                       "Version/17.6 Mobile/15E148 Safari/604.1"}
DESK_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/129.0.0.0 Safari/537.36")

# actions that open a link of the page, and the link flag each one needs (None: any guarded link)
LINK_ACTIONS = {"click": None, "open_video": "video", "play_video": "video", "next_page": "next",
                "open_comments": "comments"}

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
# links whose URL path leads to an account, a form or a purchase, whatever their text says
LOGIN_HREF = re.compile(r"/(log-?in|sign-?in|sign-?up|signin|signup|register|join|account|my-?account|checkout|cart|"
                        r"basket|subscribe|donate|password|auth|oauth2?|sso)(/|\?|$|\.)", re.I)
# place names that contain a blocked fragment ("sex" in Sussex): removed before the host check
HOST_FALSE_HITS = re.compile(r"sussex|essex|middlesex|wessex", re.I)
# a sign-in wall: the page is mostly a login / sign-up prompt (he leaves; he never signs in to get past it)
LOGIN_WALL = re.compile(r"(log|sign) ?in to (continue|view|see|read|keep reading)|sign up to (continue|read|see|view)|"
                        r"create (a free |an )?account to (continue|read|view)|you must be (logged|signed) in|"
                        r"please (log|sign) in", re.I)
LOGIN_WALL_MAX_CHARS = 3000

# --- the only typing: a site's own search box (#29) ------------------------------------------------------------------
# descriptor of every visible text-like field: tag, type, role, name, id, placeholder, aria, autocomplete, form facts
FIELD_JS = """el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el), f = el.form || el.closest('form');
  return {i: +el.getAttribute('data-sub01-field'), tag: el.tagName.toLowerCase(),
          type: (el.getAttribute('type') || '').toLowerCase(), role: (el.getAttribute('role') || '').toLowerCase(),
          name: el.getAttribute('name') || '', id: el.id || '', placeholder: el.getAttribute('placeholder') || '',
          aria: el.getAttribute('aria-label') || '', title: el.getAttribute('title') || '',
          autocomplete: (el.getAttribute('autocomplete') || '').toLowerCase(),
          editable: el.isContentEditable && el.tagName !== 'INPUT' && el.tagName !== 'TEXTAREA',
          readonly: !!(el.readOnly || el.disabled),
          visible: r.width > 20 && r.height > 8 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.1,
          form: !!f, form_action: f ? (f.getAttribute('action') || '') : '', form_role: f ? (f.getAttribute('role') || '') : '',
          form_method: f ? (f.getAttribute('method') || 'get').toLowerCase() : '',
          form_id: f ? ((f.id || '') + ' ' + (typeof f.className === 'string' ? f.className : '') + ' ' + (f.getAttribute('name') || '')) : '',
          form_password: f ? !!f.querySelector('input[type=password]') : false,
          form_fields: f ? f.querySelectorAll('input:not([type=hidden]):not([type=submit]):not([type=button]), textarea, select').length : 0};
}"""
# every text-like field of the page, numbered (data-sub01-field) and described by FIELD_JS
FIELDS_JS = ("() => { const describe = " + FIELD_JS + ";\n  return [...document.querySelectorAll('input, textarea, "
             "[contenteditable=\"\"], [contenteditable=\"true\"], [role=searchbox], [role=textbox]')].map((el, i) => "
             "{ el.setAttribute('data-sub01-field', String(i)); return describe(el); }); }")
SEARCH_WORDS = re.compile(r"search|query|find|look ?up|recherche|suche|buscar|検索", re.I)
SEARCH_NAMES = re.compile(r"^(q|s|k|p|query|search|search_?query|searchterm|term|keywords?|text|wd|search-field)$", re.I)
# anything that is a personal, account, message or payment field, whatever else it claims to be
FORBIDDEN_FIELD = re.compile(r"pass(word|wd)?|e-?mail|user(name)?|log-?in|sign-?(in|up)|register|account|comment|"
                             r"message|reply|subject|chat|feedback|review|phone|address|wallet|coupon|promo|token|"
                             r"captcha|birth|credit|iban|cvc|cvv|"
                             r"(?<![a-z])(name|post|body|tel|card|cc|pay|otp|code|age|zip)(?![a-z])", re.I)
FORBIDDEN_TYPES = ("password", "email", "tel", "url", "number", "hidden", "file", "checkbox", "radio", "submit",
                   "button", "image", "reset", "date", "datetime-local", "month", "week", "time", "color", "range")
FORBIDDEN_AUTOCOMPLETE = re.compile(r"email|username|password|cc-|tel|name|address|postal|one-time|bday|street", re.I)


def search_field_ok(f):
    """True only for a site's search box (see the module docstring). `f` is one FIELDS_JS descriptor. Everything
    that is not clearly a search input is refused: textareas, editable divs, password / email / comment / message /
    login / payment fields, fields in a form with a password field, and POST forms."""
    if not isinstance(f, dict) or not f.get("visible") or f.get("readonly") or f.get("editable"):
        return False
    if f.get("tag") != "input" or f.get("type", "") not in ("", "search", "text"):
        return False
    if f.get("type") in FORBIDDEN_TYPES or FORBIDDEN_AUTOCOMPLETE.search(f.get("autocomplete", "") or ""):
        return False
    own = " ".join(str(f.get(k, "")) for k in ("name", "id", "placeholder", "aria", "title"))
    if FORBIDDEN_FIELD.search(re.sub(r"search\w*", " ", own, flags=re.I)):
        return False
    if f.get("form_password") or (f.get("form") and f.get("form_method", "get") not in ("get", "")):
        return False
    if f.get("form") and int(f.get("form_fields") or 0) > 3:          # a search box stands (nearly) alone in its form
        return False
    form = f"{f.get('form_action', '')} {f.get('form_role', '')} {f.get('form_id', '')}"
    if f.get("form") and (LOGIN_HREF.search(f.get("form_action", "") or "")
                          or FORBIDDEN_FIELD.search(re.sub(r"search\w*", " ", form, flags=re.I))):
        return False
    return (f.get("type") == "search" or f.get("role") == "searchbox"
            or (bool(f.get("form")) and bool(SEARCH_WORDS.search(form)))
            or (f.get("form_role") == "search")
            or (bool(SEARCH_NAMES.match(f.get("name", "") or "")) and bool(SEARCH_WORDS.search(own))))


# --- cookie / consent banners and modals (#29) ----------------------------------------------------------------------
REJECT_BUTTON = re.compile(r"\b(reject|decline|refuse|deny|disagree)\b|"
                           r"\b(necessary|essential|required|functional)\b.*\bonly\b|\bonly\b.*\b(necessary|essential|required)\b|"
                           r"continue without (accepting|agreeing|consent)|do not (accept|agree|consent)|"
                           r"(don't|do not) (allow|sell)|use necessary cookies", re.I)
ACCEPT_BUTTON = re.compile(r"\b(accept|agree|allow|consent|got it|ok|okay|i understand|yes|continue|enable)\b", re.I)
CLOSE_BUTTON = re.compile(r"^(close|×|✕|✖|x|dismiss|no,? thanks?|not now|maybe later|skip|no thanks, continue|"
                          r"close (dialog|modal|banner|this))$", re.I)
BUTTONS_JS = """() => {
  const consentRe = /cookie|consent|gdpr|privacy|tracking|partners|personal data|your choices/i;
  const out = [], seen = new Set();
  const inFrame = window !== window.top && /consent|cmp|privacy|cookie|sp_message|gdpr/i.test(location.href);
  for (const el of document.querySelectorAll('button, [role=button], a, input[type=button], input[type=submit]')) {
    if (out.length >= 80) break;
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (r.width < 4 || r.height < 4 || cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (el.tagName === 'A') { const h = el.getAttribute('href') || ''; if (h && h !== '#' && !h.startsWith('javascript')) continue; }
    let box = el.parentElement, overlay = null;
    while (box && box !== document.body) {
      const bs = getComputedStyle(box);
      if (bs.position === 'fixed' || bs.position === 'sticky' || box.getAttribute('role') === 'dialog'
          || box.getAttribute('aria-modal') === 'true' || box.tagName === 'DIALOG') { overlay = box; }
      box = box.parentElement;
    }
    if (!overlay && !inFrame) continue;
    const text = ((overlay || document.body).innerText || '').slice(0, 3000);
    const label = (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim().slice(0, 80);
    const aria = (el.getAttribute('aria-label') || '').trim().slice(0, 60);
    const i = out.length; el.setAttribute('data-sub01-btn', String(i));
    out.push({i, label, aria, consent: inFrame || consentRe.test(text), modal: true});
  }
  return out;
}"""


def choose_dismiss(buttons):
    """Index of the button to press to get rid of a banner or modal, or None (then it is hidden, not clicked).
    Consent banners: the reject / "necessary only" button; if there is none, a close button. Other modals: their
    close button. An accept / agree / allow button is never pressed, whatever else it says."""
    def label(b):
        return " ".join(str(b.get("label") or "").split())

    def close(b):
        return bool(CLOSE_BUTTON.match(label(b)) or re.match(r"^(close|dismiss)\b", str(b.get("aria") or ""), re.I))

    for b in buttons:
        t = label(b)
        if b.get("consent") and REJECT_BUTTON.search(t) and len(t) <= 60:
            if ACCEPT_BUTTON.search(t) and not re.search(r"only|reject|decline|refuse|without|do not|don't", t, re.I):
                continue
            return b["i"]
    for b in buttons:
        if close(b) and (CLOSE_BUTTON.match(label(b)) or not ACCEPT_BUTTON.search(label(b))):
            return b["i"]
    return None


def display_ok(text):
    """Text that may be shown on the public screen card: no links, addresses, tickers, money, slurs or blocked
    topics (the chat filter's rules, without its phone-number rule, which catches year ranges)."""
    import chat
    from research import BLOCK as TOPIC_BLOCK
    t = text or ""
    return not (chat.URL.search(t) or chat.SOL_ADDR.search(t) or chat.ETH_ADDR.search(t) or chat.TICKER.search(t)
                or chat.EMAIL.search(t) or chat.MONEY.search(t) or chat.SLUR_RE.search(chat.normalise(t))
                or BAD_WORDS.search(t) or BAD_HOST.search(t) or TOPIC_BLOCK.search(t))


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
    # encyclopaedia, forums (read-only), Q&A
    "https://en.wikipedia.org/wiki/Special:Random", "https://news.ycombinator.com/", "https://news.ycombinator.com/ask",
    "https://old.reddit.com/r/askscience/", "https://old.reddit.com/r/AskHistorians/", "https://old.reddit.com/r/Cooking/",
    "https://old.reddit.com/r/japanpics/", "https://old.reddit.com/r/space/", "https://old.reddit.com/r/Breadit/",
    "https://old.reddit.com/r/todayilearned/", "https://cooking.stackexchange.com/questions?tab=Votes",
    "https://japanese.stackexchange.com/", "https://astronomy.stackexchange.com/", "https://lobste.rs/",
    "https://www.metafilter.com/",
    # news and magazines
    "https://www.bbc.com/news", "https://www3.nhk.or.jp/nhkworld/", "https://www.japantimes.co.jp/",
    "https://www.theguardian.com/international", "https://apnews.com/", "https://www.npr.org/",
    "https://arstechnica.com/", "https://www.theverge.com/", "https://www.quantamagazine.org/",
    "https://www.atlasobscura.com/", "https://www.openculture.com/", "https://www.nationalgeographic.com/",
    "https://www.smithsonianmag.com/", "https://www.newscientist.com/", "https://www.sciencenews.org/",
    # science and space
    "https://apod.nasa.gov/apod/astropix.html", "https://www.nasa.gov/", "https://earthobservatory.nasa.gov/",
    "https://www.esa.int/", "https://phys.org/",
    # museums and archives
    "https://www.metmuseum.org/art/collection", "https://www.archive.org/", "https://artsandculture.google.com/",
    "https://www.britishmuseum.org/collection", "https://www.rijksmuseum.nl/en/rijksstudio",
    "https://www.tnm.jp/?lang=en",
    # maps and places
    "https://www.openstreetmap.org/#map=15/35.7030/139.5795", "https://www.timeout.com/tokyo",
    "https://www.japan-guide.com/", "https://www.spoon-tamago.com/",
    # recipes and food
    "https://www.justonecookbook.com/", "https://www.seriouseats.com/", "https://www.allrecipes.com/",
    "https://www.kingarthurbaking.com/recipes",
    # music and video pages
    "https://bandcamp.com/", "https://www.npr.org/series/tiny-desk-concerts/", "https://pitchfork.com/",
    "https://www.youtube.com/@NHKWORLDJAPAN", "https://vimeo.com/channels/staffpicks",
    # blogs and tech
    "https://github.com/trending", "https://xkcd.com/", "https://waitbutwhy.com/", "https://www.kottke.org/",
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
    if (not host or BAD_HOST.search(HOST_FALSE_HITS.sub("", host))
            or host.rstrip(".").lower() in ("localhost", "metadata", "metadata.google.internal")):
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
        self.chain = 0                                      # pages shown in a row since he last wandered off

    def status(self):
        return dict(self.info, id=self.shot_id, device=self.name, chain=self.chain) if self.info and self.shot else None


CHROMIUM_ARGS = ["--disable-dev-shm-usage", "--mute-audio", "--disable-extensions", "--disable-background-networking",
                 "--disable-sync", "--no-first-run", "--renderer-process-limit=2", "--js-flags=--max-old-space-size=256",
                 "--disable-gpu", "--disable-software-rasterizer"]
CHROMIUM_ENV = ("PATH", "HOME", "LANG", "TZ", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH", "FONTCONFIG_PATH")


def launch_kwargs(sandbox, proxy=None, environ=None):
    """playwright `chromium.launch` arguments; `--no-sandbox` only when `sandbox` is False."""
    environ = os.environ if environ is None else environ
    kw = {"args": CHROMIUM_ARGS + ([] if sandbox else ["--no-sandbox"]),
          "chromium_sandbox": bool(sandbox),
          "env": {k: v for k, v in environ.items() if k in CHROMIUM_ENV}}
    if environ.get("BROWSE_CHROMIUM"):
        kw["executable_path"] = environ["BROWSE_CHROMIUM"]
    if proxy:
        kw["proxy"] = {"server": proxy}
    return kw


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
        self.last_skip = None                               # why the last page was left unshown (guard, bot wall...)
        self.typed = []                                     # every text typed: [{t, device, host, field, query}]
        self.dismissed = []                                 # banners / modals pressed away: [{t, host, label, kind}]
        self.sandbox = None                                 # Chromium's own sandbox on? (None: not launched yet)
        self.no_sandbox = False                             # a sandboxed launch failed once: stay without it

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
            # Chromium's own sandbox stays on unless we run as root, where Chromium refuses it (the image drops to
            # uid 1000, #18). If a sandboxed launch fails (no user namespaces in the runtime), relaunch without it.
            # The browser gets a minimal environment: none of the server's secrets (API tokens, site password).
            root = hasattr(os, "geteuid") and os.geteuid() == 0
            sandbox = not (root or self.no_sandbox)
            try:
                self.browser = await self.pw.chromium.launch(**launch_kwargs(sandbox, self.proxy))
            except Exception as e:
                if not sandbox:
                    raise
                self.no_sandbox = True
                print("browse: !!! CHROMIUM SANDBOX FAILED TO START, falling back to --no-sandbox !!!",
                      repr(e)[:300], flush=True)
                sandbox = False
                self.browser = await self.pw.chromium.launch(**launch_kwargs(False, self.proxy))
            if root:
                print("browse: !!! running as root: Chromium sandbox OFF (--no-sandbox) !!!", flush=True)
            self.sandbox = sandbox
            for sc in self.screens.values():
                sc.ctx = sc.page = None
                sc.info, sc.history, sc.awaiting, sc.scrolls_left, sc.chain = None, [], None, 0, 0
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
                sc.info, sc.history, sc.awaiting, sc.chain = None, [], None, 0
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
                moved_on = False
                if self.decide and sc.awaiting is not None:      # the brain is choosing: hold the page
                    if not self._fresh_chat(heard) and time.time() - sc.awaiting_since < DECIDE_WAIT_S:
                        return None
                    sc.awaiting, moved_on = None, True          # a new chat message, or no answer: move on
                if sc.scrolls_left > 0 and sc.info and not moved_on:
                    sc.scrolls_left -= 1
                    await sc.page.evaluate("() => window.scrollBy({top: innerHeight * 0.7, behavior: 'smooth'})")
                    await sc.page.wait_for_timeout(900)
                    if not await self._shoot(sc):                   # turned into a bot check: left
                        sc.next_at = time.time() + 15
                        return None
                elif self.decide and sc.chain >= MAX_CHAIN and sc.info and not moved_on:
                    ok = await self._next(sc, list(heard), interest)    # a long chain ends: something new
                    if ok and sc.info:
                        sc.info = dict(sc.info, why=f"after {MAX_CHAIN} pages in a row, wandered off; "
                                                    f"{sc.info.get('why', '')}")
                    if not ok:
                        sc.next_at = time.time() + 15
                        return None
                elif (self.decide and sc.info and sc.info.get("kind") in ("page", "search") and sc.page is not None
                      and sc.page.url.startswith("http") and not self._fresh_chat(heard) and not moved_on):
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
        search = sc.info.get("kind") == "search"
        return self.pick_links(raw, page.url, text, sc, search)

    def pick_links(self, raw, url, text, sc, search=False):
        """Numbered, guarded links for the eyes. Pagination ("next"), comment threads and (on Wikipedia) external
        sources are kept even when they are small or low on the page, so the brain can follow them (#29)."""
        cur = urllib.parse.urlsplit(url)
        wiki = (cur.hostname or "").endswith("wikipedia.org")
        seen, cand = set(), []
        for href, label, area, visible, *extra in raw:
            rel, external, aria = (list(extra) + ["", False, ""])[:3]
            label = " ".join(str(label or "").split())
            kind = link_kind(href, label, rel or "", aria or "")
            if kind == "next" and len(label) < 4:
                label = "next page"
            u = urllib.parse.urlsplit(href)
            ext = bool(external) and wiki and not (u.hostname or "").endswith(("wikipedia.org", "wikimedia.org",
                                                                                "wikidata.org"))
            if (len(label) < 4 or not url_ok(href) or LOGIN_LINK.search(label) or LOGIN_HREF.search(href)
                    or not display_ok(label) or href in seen):
                continue
            if (u.netloc, u.path, u.query) == (cur.netloc, cur.path, cur.query) or (
                    search and u.netloc == cur.netloc and kind != "next"):
                continue                                        # same page; on a results page only the results
            seen.add(href)
            cand.append({"visible": bool(visible), "area": area, "href": href, "text": label, "host": u.hostname or "",
                         "kind": kind, "external": ext})
        cand.sort(key=lambda c: (not c["visible"], -c["area"]))
        special = [c for c in cand if c["kind"]][:4] + [c for c in cand if c["external"] and not c["kind"]][:8]
        ids = {id(c) for c in special}
        keep = special + [c for c in cand if id(c) not in ids][:max(0, PAGE_LINKS - len(special))]
        keep.sort(key=lambda c: cand.index(c))
        links = []
        for i, c in enumerate(keep):
            link = {"id": f"L{i + 1}", "href": c["href"], "text": c["text"][:100],
                    "host": c["host"].removeprefix("www."), "area": round(c["area"]),
                    "video": bool(VIDEO_LINK.search(c["href"]))}
            if c["kind"] == "next":
                link["next"] = True
            elif c["kind"] == "comments":
                link["comments"] = True
            if c["external"]:
                link["external"] = True
            links.append(link)
        return {"device": sc.name, "url": url, "title": sc.info.get("title", ""), "host": sc.info.get("host", ""),
                "kind": sc.info.get("kind"), "text": " ".join(text.split())[:1500], "links": links,
                "can_back": len(sc.history) >= 2, "search_box": bool(sc.info.get("search_box")),
                "chain": sc.chain, "max_chain": MAX_CHAIN}

    async def act(self, device, action, why="", interest=None):
        """Carry out the action the brain chose for the page it was given; returns the new screen status or None."""
        sc = self.screens[device]
        kind, why = action.get("action"), why or "his brain picked it"
        async with self.lock:
            page, sc.awaiting = sc.awaiting, None                  # claimed under the lock (no race with step)
            if page is None or sc.page is None:
                return None
            try:
                ok = False
                self.last_skip = None
                if kind in LINK_ACTIONS:
                    want = action.get("href")                       # matched by URL: link ids are per capture
                    link = next((l for l in page["links"] if l["href"] == want), None)
                    flag = LINK_ACTIONS[kind]                       # the link must really be of that kind
                    href = link["href"] if link and (flag is None or link.get(flag)) else None
                    ok = bool(href) and await self._open(sc, href, f"{action.get('label', '')} — {why}", "page")
                    if ok and kind == "play_video":
                        await self._play_muted(sc)
                elif kind == "search" and action.get("target"):
                    from eyes import query_ok                       # checked again here, in the browser's process
                    q = query_ok(action["target"])
                    ok = bool(q) and await self._search(sc, q, f"searched “{q}” — {why}")
                elif kind == "site_search" and action.get("target"):
                    from eyes import query_ok                       # the query filter, again in this process
                    q = query_ok(action["target"])
                    ok = bool(q) and await self._site_search(
                        sc, q, f"searched {page.get('host', 'the site')} for “{q}” — {why}")
                elif kind == "back" and len(sc.history) >= 2:
                    saved = list(sc.history)
                    sc.history = saved[:-2]
                    ok = await self._open(sc, saved[-2], f"went back — {why}", "page")
                    if not ok:
                        sc.history = saved
                elif kind == "scroll":
                    sc.scrolls_left = self.rng.randint(1, 3)
                    if sc.info:
                        sc.info = dict(sc.info, why=f"kept reading — {why}")
                    ok = True
                if not ok:                                      # leave, or the chosen page could not be shown
                    missed = None
                    if kind in tuple(LINK_ACTIONS) + ("search", "site_search", "back"):
                        missed = f"could not show “{action.get('label', '')}” ({self.last_skip or 'refused'})"
                    ok = await self._next(sc, [], interest)
                    if ok and missed and sc.info:               # the card must not pretend the choice was shown
                        sc.info = dict(sc.info, why=f"{missed}; {sc.info.get('why', '')}", missed=missed)
                sc.next_at = time.time() + SCROLL_EVERY_S
                self.failures = 0
                return sc.status() if ok else None
            except Exception as e:
                print(f"browse ({device}) act:", repr(e)[:160], flush=True)
                return None

    async def _next(self, sc, heard, interest):
        """Pick where to go: a fresh chat message -> search; a result from the last search; a link that matches
        his interests; else a search on what he read last or something familiar; sometimes a seed site. A new chain
        of pages starts here."""
        sc.chain = 0
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

    async def _site_search(self, sc, q, why):
        """Type `q` into the page's own search box and press Enter. The field is re-checked right before typing,
        in this process (search_field_ok); any other field is refused and nothing is typed."""
        page = sc.page
        fields = [f for f in await page.evaluate(FIELDS_JS) if search_field_ok(f)]
        if not fields:
            self.last_skip = "no search box"
            return False
        f = fields[0]
        box = page.locator(f'[data-sub01-field="{int(f["i"])}"]').first
        again = await box.evaluate(FIELD_JS)                     # the element itself, just before typing
        if not search_field_ok(again):                             # changed under us: type nothing
            self.last_skip = "not a search box"
            return False
        host = urllib.parse.urlsplit(page.url).hostname or ""
        field = " ".join(x for x in (again.get("type") or "text", again.get("name"), again.get("placeholder"))
                         if x)[:60]
        self.typed = (self.typed + [{"t": time.time(), "device": sc.name, "host": host.removeprefix("www."),
                                     "field": field, "query": q}])[-100:]
        print(f"browse: site_search on {host} (input {field!r}): {q!r}", flush=True)
        await box.fill(q)
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=SITE_SEARCH_NAV_MS):
                await box.press("Enter")                           # Enter only: no other button is pressed
        except Exception:                                          # results shown in place (no navigation)
            pass
        return await self._settle(sc, why, "page", min_text=80)

    async def _play_muted(self, sc):
        """A video page: start its first video muted (Chromium also runs with --mute-audio)."""
        try:
            await sc.page.evaluate("""() => { const v = document.querySelector('video');
                if (v) { v.muted = true; v.volume = 0; const p = v.play(); if (p && p.catch) p.catch(() => {}); } }""")
        except Exception:
            pass

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
                self.last_skip = "did not load"
                return await self._leave(sc)
        return await self._settle(sc, why, kind, title, min_text, shoot)

    async def _settle(self, sc, why, kind, title=None, min_text=80, shoot=True):
        """A page has loaded: banners away, then the guard, bot walls and sign-in walls; then shown."""
        page = sc.page
        await page.wait_for_timeout(1800)
        if not url_ok(page.url):                                       # redirected somewhere it must not be
            self.last_skip = "did not load" if page.url.startswith("chrome-error:") else "guard"
            return await self._leave(sc)
        await self._dismiss(sc)
        await page.add_style_tag(content=HIDE_BANNERS)
        await page.evaluate(UNBLOCK_JS)
        if not url_ok(page.url):
            return await self._leave(sc)
        page_title = (await page.title() or "").strip()
        body = await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 20000)")
        reason = ("guard" if not text_ok(page_title, body) else "empty" if len(body.strip()) < min_text
                  else "bot wall" if BOT_WALL.search(page_title) or await self._walled(page, body)
                  else "sign-in wall" if LOGIN_HREF.search(urllib.parse.urlsplit(page.url).path + "?")
                  or await self._login_walled(page, body) else None)
        if reason:
            print(f"browse: skipped {urllib.parse.urlsplit(page.url).hostname} ({reason}: {page_title[:40]!r})", flush=True)
            self.last_skip = reason
            return await self._leave(sc)
        host = urllib.parse.urlsplit(page.url).hostname or ""
        sc.info = {"title": (title or page_title or host)[:140], "url": page.url, "host": host.removeprefix("www."),
                   "why": why.replace("opened “”", f"opened {host.removeprefix('www.')}"), "t": time.time(), "kind": kind,
                   "search_box": kind == "page" and await self._has_search_box(page)}
        sc.scrolls_left = self.rng.randint(*SCROLLS) if kind == "page" else 0
        if shoot and not await self.show(sc):
            return False
        return True

    async def _has_search_box(self, page):
        try:
            return any(search_field_ok(f) for f in await page.evaluate(FIELDS_JS))
        except Exception:
            return False

    async def _login_walled(self, page, body):
        """A sign-in / sign-up wall: a visible password field or a 'log in to continue' prompt on a short page."""
        if len(body.strip()) >= LOGIN_WALL_MAX_CHARS:
            return False
        if LOGIN_WALL.search(body):
            return True
        return await page.evaluate("""() => [...document.querySelectorAll('input[type=password]')].some(el => {
            const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
            return r.width > 20 && r.height > 8 && cs.visibility !== 'hidden' && cs.display !== 'none'; })""")

    async def _dismiss(self, sc, rounds=2):
        """Cookie / consent banners: press reject or "necessary only"; modals: press close (choose_dismiss). Never an
        accept button; with nothing safe to press the banner is only hidden (UNBLOCK_JS)."""
        page = sc.page
        host = (urllib.parse.urlsplit(page.url).hostname or "").removeprefix("www.")
        for _ in range(rounds):
            pressed = False
            for frame in list(page.frames):
                if frame != page.main_frame and not url_ok(frame.url):
                    continue
                try:
                    buttons = await frame.evaluate(BUTTONS_JS)
                    k = choose_dismiss(buttons)
                    if k is None:
                        continue
                    b = next(x for x in buttons if x["i"] == k)
                    await frame.evaluate("i => { const el = document.querySelector(`[data-sub01-btn=\"${i}\"]`); "
                                         "if (el) el.click(); }", k)
                except Exception:
                    continue
                kind = "reject" if b.get("consent") and REJECT_BUTTON.search(b.get("label") or "") else "close"
                self.dismissed = (self.dismissed + [{"t": time.time(), "host": host, "label": (b.get("label") or
                                                     b.get("aria") or "")[:40], "kind": kind}])[-100:]
                print(f"browse: {kind} banner on {host}: {(b.get('label') or b.get('aria') or '')[:40]!r}", flush=True)
                pressed = True
                await page.wait_for_timeout(700)
                break
            if not pressed:
                return

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
            sc.chain += 1
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
