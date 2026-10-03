# SUB-01 — handoff for new sessions (state on 2026-10-02)

Read this first. It replaces the local memory that cloud sessions cannot see.

## What SUB-01 is now
- A whole-brain model built from one real person's public MRI (MyConnectome, OpenNeuro ds000031, PDDL):
  real tractography fibres, real cortex, his real resting-state recordings.
- It "lives" as a **fictional young man in a Tokyo room** (Kichijoji). The character is invented and must never
  resemble, name or speak as the real scanned person. Never claim consciousness or that it is alive.
- **Data attribution (agreed with the dataset's researcher, 2026-10-02):** credit the data to the **MyConnectome
  project** (Poldrack et al. 2015, Nat Commun 6:8885; OpenNeuro ds000031) on `/about.html` and in the README. Do
  not state or highlight whose brain it is anywhere (site, diary, X posts, coin material); never use the person or
  the project's name to promote the site or the coin.
- Live on Railway (`sub01-production.up.railway.app`, behind `SITE_PASSWORD`), auto-deploys from `main`.
- Memecoin context: no financial advice, no buy pressure, no wallets or on-chain actions without explicit approval.

## Pages (all on `main`)
| path | file | what |
|---|---|---|
| `/` | `web/room.html` | his room in 3D (three.js r169; Higgsfield/Meshy GLBs in `web/room/`, meshopt + WebP, 3 MB), Tokyo day/night through the window, live screens (monitor + phone in his hands, arm IK), camera follows what he looks at, map when he is out, mini brain. `?debug&nolive&hour=21` previews a time of day |
| `/brain` | `web/index.html` | brain v2: full-screen real fibres coloured by sleep stage; chat messages travel along real fibres; `?mini` for the PiP |
| `/diary` | `web/diary.html` | dream diary written each morning (Tokyo) from unattended REM frames |
| `/world.html` | eye frames | what the eye (Replicate FLUX + Llama 3) "sees" |

## Runtime modules
- `brain_sim.py` (10 Hz delayed Stuart-Landau; `step` reads the delayed coupling with one sparse product per step on
  the ring buffer, `ring_coupling()`, #19: ~4 ms CPU per 50 ms tick instead of ~30, same as the old dense step to ~1e-15
  over 10 s (`tests/test_brain_step.py` asserts 1e-9); `analysis/bench_step.py` times both; the old step's 732 KB temporaries made the tick depend on glibc malloc state, which a vote in a worker thread shifted by ~2 ms; the new step allocates only region-sized arrays), `real_baseline.py` (replays his fMRI as drive), `sleep.py` (Asia/Tokyo),
  `chat.py` (filter), `eye.py` (Replicate), `diary.py`, `life.py` (needs-based life: research at the computer,
  order_food → simulated courier on a real OSM bike route, get_delivery, bakery/park outings with real routes),
  `research.py` (Wikipedia curiosity chain, sensitive topics skipped; its article seeds what he searches),
  `browse.py` (`BROWSE=1`, on in the Dockerfile: headless Chromium on the open web for the desk + phone screens;
  Bing SafeSearch strict with a Wikipedia → external-sources fallback; the only typing is a filtered query into a
  site's own search box (#29, checked in the browser process), never logs in/signs up/buys; guard skips
  adult, gore, self-harm, extremism, drugs, gambling, crypto-trading/wallet and login/sign-up/checkout sites/pages;
  every request to private/internal addresses is blocked; Chromium gets no secrets in its env), `live_server.py` (aiohttp; pages served
  with `Cache-Control: no-cache`; `/api/diary`, `/api/reading`, `/api/frames`, `/api/browsing`, `/api/screen/{desk,phone}.jpg`).
- State files under `--data-dir` go through `state_io.py` (#21): `save_json` (tmp + fsync + `os.replace`) and
  `load_json` (a missing or torn file gives defaults; a torn one is kept as `<name>.corrupt-<UTC time>` with one log line),
  so a kill mid-write cannot crash-loop the server. JSONL logs append with `append_jsonl` and are read skipping torn lines.
  New JSON state must use these too.
- `Dockerfile` must copy every runtime module (currently also `diary.py research.py browse.py`) and installs Chromium
  (`playwright install --with-deps --only-shell chromium`, image ~1.7 GB) and ffmpeg + DejaVu fonts for the clips (#59). BLAS is single-threaded (`OPENBLAS_NUM_THREADS=1`):
  multi-threaded BLAS spins when Chromium shares the CPU.
- Live feed: plain `/ws` = 20 ticks/s with per-region activity (brain page); the room connects with `/ws?rate=5&lite=1`
  (5/s, no `act`, trades/events of skipped ticks kept). Room: shadow maps updated by hand (~30/s), DPR capped at 1.5
  with adaptive resolution, nothing rendered while the tab is hidden; brain `?mini` draws 1/6 of the fibres at ≤30 fps.
- Room model: `web/room/room_clean.glb` (5.0 MB since #98 G5; 4.0 before) is a clean rebuild — modelled in Blender by `room_build/build_room.py`
  (headless Blender 4.2), Poly Haven CC0 props/textures, AO baked into a second UV set; credits in `web/room/CREDITS.md`.
  Monitor/window/lamp positions come from GLB nodes `SURF_monitor|window|lamp`. The old AI-baked room stays behind `?room=old`.
  #75: props are placed from their real bounding boxes, and a build-time sweep (`blender -b -P build_room.py -- --sweep`,
  report in `room_build/out/sweep.txt`) fails the build if any prop reaches into a wall or floats/sinks > 2 mm off its
  support, or enters room.html's spots (his place at the window, the delivery bag's and the tea bottle's desk spots, the door's
  swing, his walking graph; `KEEP`/`DOOR_SWING`/`WALK_*`, mirror room.html when its paths change); `tests/test_room_glb.py` checks the GLB's size (≤ 7 MB), its nodes and the lamp marker. Lived-in props are
  modelled in the build (no new downloads), all off the walking graph; the headphones on the wall hook are their own
  node `headphones` (no AO): the page hides them while he wears #82's pair. The hook rail, tote and hoodie are the node
  `hangers` (origin at the door hinge): `setDoor()` turns it with the opening leaf.
  #98 G5 (game-quality hard surfaces): `room_build/props_hard.py` builds the furniture, desk things, window, door, fridge,
  air conditioner, fan, headphones and controller (build_room.py calls it block by block and reads its constants back),
  `room_build/tex_hard.py` (run by tex_prep.py) draws the plank floor (Poly Haven `wooden_floor_01`), the roughness
  micro-variation maps and three atlases laid out in `room_build/hard_layout.py`: keycap legends, book spines, decals.
  Edge wear = tinted vertex colours on the bevels (post.mjs drops all-white COLOR_0); decals are one alpha-blended node
  `decals`, left out of the AO bake. Materials flagged `nouv` keep their own UVs through the final projection pass
  (that pass used to overwrite the posters' and pinboard's UVs). Screenshots: `python room_build/shots.py --out <dir>`
  (fixed cameras, `--glb` to shoot another file, `--cdn-dir` for a local three.js when the sandbox has no CDN). `web/room_phone.js`: the phone screen drawn on a canvas
  (status bar with his Tokyo time, rounded corners, off state, face glow); room.html routes the phone's `set`/`off` through it.
- Phone grip: while he uses the phone his `RightHand` bone is collapsed into the sleeve and `web/room/hand_phone.glb`
  (a hand gripping a phone, Higgsfield GPT Image + Tripo H3.1, 129 KB) is attached at the wrist; the live screen sits on its glass.
- Phone pose: one-handed grip; right arm/neck/head from `web/room/boy_text.glb` (Meshy `Texting_Walk_inplace` #676,
  re-rigged on the same skeleton via Higgsfield, 8 credits) blended into frozen sit/idle poses (`phone_sit`, `phone_stand`).
- Non-root (#18): the server and Chromium run as `sub01` (uid 1000), so Chromium can keep its own sandbox (no `--no-sandbox`).
  The image still starts as root (no `USER` line on purpose): `entrypoint.sh` (`/usr/local/bin/sub01-entrypoint`)
  `chown -R 1000:1000 /data` when anything in it is not uid 1000 yet (first start on the old root-owned volume; later
  starts change nothing), then drops privileges for good with `setpriv` (util-linux, already in Debian slim; no new
  package). Started as uid 1000 already (`docker run --user 1000`) it runs the CMD as is, and says loudly if `/data` is not
  writable. Chromium lives in `/ms-playwright` (`PLAYWRIGHT_BROWSERS_PATH`) so uid 1000 can start it. `browse.py`
  passes `--no-sandbox` only as root or when a sandboxed launch fails (no user namespaces in the runtime); both print a
  `!!!` line, and the fallback sticks until the service restarts. `/state` of `browse_service.py` shows `sandbox`, `uid`.
  - Railway: nothing to set. Do not set `RAILWAY_RUN_UID` (the image must start as root to hand the volume over). A
    custom start command or the separate browse service (`python browse_service.py ...`) must go through the
    entrypoint: prefix it with `/usr/local/bin/sub01-entrypoint`. Signs it did not: `!!! running as root` in the logs.
  - Whether the sandbox itself starts depends on the runtime (user namespaces): under Docker's default seccomp profile it
    does not and Chromium falls back to `--no-sandbox` as uid 1000 (`!!! CHROMIUM SANDBOX FAILED`); with
    `--security-opt seccomp=unconfined` it runs sandboxed (renderers in their own user namespace, seccomp filter on).
    Railway's runtime: check the first deploy's logs.
  - Check after a deploy: no `!!! running as root` line; `/api/browsing` keeps filling; files on `/data` keep updating.
  - **Rollback:** set `RUN_AS_ROOT=1` on the Railway service and redeploy: everything runs as root as before #18
    (Chromium back on `--no-sandbox`, loud line in the logs). `/data` stays owned by uid 1000, which root reads and writes
    anyway. Full revert: revert the #18 PR (Dockerfile ENTRYPOINT + `entrypoint.sh` + browse.py); no data migration.

## Costs, caps and health (#15, `docs/OPERATIONS.md`)
- `costs.py`: one view of every paid service per Tokyo day. The eye and the diary write `/data/costs.jsonl`; the eyes
  and the mind stay in their shared `/data/eyes_costs.jsonl`; RunPod stays in `/data/spiking/costs.jsonl`. It reads
  them all and counts each cost once. Caps per Tokyo day are checked before every paid call: `SUB01_CAP_EYE_USD` 1.00,
  `SUB01_CAP_DIARY_USD` 0.10, `SUB01_CAP_EYES_USD` 1.00 and `SUB01_CAP_MIND_USD` 1.00 (the existing shares),
  `SUB01_CAP_TOTAL_USD` 3.10 (their sum; RunPod excluded). Over a cap the eye keeps its last frame ("resting its
  eyes"), the diary writes its template, the eyes use local options, the mind rests.
- `GET /healthz`: public, 200 if the brain loop ticked within 5 s, else 503. Set it as Railway's healthcheck path.
  `GET /api/costs` and `/api/health` are admin-only (the password cookie, or the `SUB01_ADMIN_TOKEN` header). Tick
  times sit in a 1200-entry ring buffer (`Live.tick_s`).

## Reading memory (PR `feature/reading-memory`)
- What he reads is a stimulus: up to 8 keywords (title + extract) through chat.py's rules at 0.5x a chat message,
  + language/attention 1.5, times the sleep gain. Stored in `sleep.Memory` with `source="reading"`; REM replay
  weighs a reading 0.6x and caps the reading pool at 0.6x the chat pool (chat from people wins most nights).
- Curiosity: link titles scored by `chat.TOPICS` lexicon x the tick's relative network activity + novelty
  (7 days) + noise, softmax (`SUB01_CURIOSITY_TEMP`, 0.5); the "why" names only above-average networks.
- Shown: room reading card ("will it come back tonight?" Monte Carlo estimate), diary "read that day · replayed
  that night", eye dream prompts (replayed titles as images only). Wording: it does not understand the text.
- Screens: bot checks (CAPTCHA / "unusual traffic") are recognised and left, never solved or clicked.

## Teach him something (#31, PR `feature/teach-him`)
- A viewer sends `{"type":"teach","text","nick"}` on `/ws`: a word or a phrase of at most 6 words plus an optional
  nickname (max 16 characters). Both go through `chat.blocked` (no links, addresses, tickers, personal data, money
  requests, slurs). Limits are in `chat.TeachLimits`: one teach per viewer per Tokyo day, keyed by the chat limiter's
  key and kept in memory only, and at most 30 a day in total, counted from memory and from `teach.json`
  (state_io; day + count only, never viewer keys), so a restart cannot reopen the cap; a teach also saves `state.json`. A phrase already taught that day
  is refused.
- The taught item becomes a stimulus (the chat rules) and a `sleep.Memory` item with `source="taught"`. It keeps
  `nick` for display only (never a stimulus) and `replays`, which `sleep_tick` counts. In REM it weighs 1.5× a
  chat message, and the taught pool is capped at 1.0× everything else, so it gets at most half the replays.
- GPU session: `top_items` adds up to 5 of the day's taught items. Those with 2+ content words come first, because
  a single word cannot be cued with half of itself (`spiking/words.py`); then the most replayed. They are tested the
  next day like the others, and `memory_tests.jsonl` keeps `source: "taught"`.
- `GET /api/taught`: today's and yesterday's items with nick and replay count. With the pod manager enabled it adds
  `testable` and `result` (recalled, score, best lure, days_since) and the note "Recall by a simulated spiking
  network from a partial cue; a model, not a mind.". Without it, only replay counts, with no recall claim.
  Teach card on `/brain`.

## Free browsing (#29, PR `feature/free-browsing`)
- New actions: `site_search` (types only into a search input — `browse.search_field_ok` refuses password, email,
  comment, message, login, payment fields, textareas, editable divs, POST forms and forms with a password field; the
  field is re-checked just before typing; Enter only; every typed text is in the service's `/state` → `typed`),
  `next_page`, `open_comments`, `play_video` (muted; YouTube details stay in #17). Eyes list up to 6 options; a
  `leave` option is always offered; the brain vote stays the only decider.
- Chains of up to 30 pages (`browse.MAX_CHAIN`); leaving is boredom-, chain- and taste-driven in `brain_vote.py`
  (`LEAVE_BORED`, `LEAVE_CHAIN`, the leave option's taste is the opposite of the current page's).
- Cookie / consent banners: the reject or "necessary only" button (`browse.choose_dismiss`), never accept; modals
  closed; sign-in walls left (never signed in). ~58 seeds across forums (read-only), news, museums, maps, recipes,
  music, science and video pages; Wikipedia's external sources and pagination / comment links keep a place among the
  40 links. Costs unchanged: 1 eyes call per page, 30/hour, $1.00/Tokyo day.

## More of the internet (#56, PR `feature/more-search`)
- `search_sources.py` (pure: parsers, routing, limits, robots, queries; no network): searches go to Bing (SafeSearch
  strict), DuckDuckGo HTML (`kp=1`), Wikipedia search, Wikimedia Commons (images), arXiv listing search, Hacker News
  (the Algolia API for results, its page for the screen), Open Library (subject pages + their JSON: robots.txt
  disallows Open Library's `/search` and `/api`), YouTube results (Restricted Mode cookie as #53), and through their
  own search box (#40's `site_search` rules) RecipeTin Eats and Science News (robots.txt rules out AP News', Just One
  Cookbook's, King Arthur's and the Guardian's search pages). No keys, nothing paid.
- `route(q)`: topic regexes pick the fitting sources (science → arXiv, book → Open Library, how-to → DuckDuckGo,
  recipe → RecipeTin Eats, images → Commons, tech → HN, video → YouTube, "what is" → Wikipedia), the general engines
  follow; the least used fitting source in the last hour goes first. `Limits`: ≤ 20 requests per host per rolling hour
  (`PER_HOST_HOUR`; results pages, API calls and robots.txt all count), searches per source per Tokyo day, refusals
  (robots / rate limit / no results). Saved with the browsing log (`browsing.json` → `searches`) and restored on a
  browser restart. `Robots`: robots.txt fetched once a day per host through `Browser._fetch` (the guard: public
  hosts only, every redirect re-checked); also checked before typing into any site's search box.
- `browse.py`: `_search` tries the first 2 routed sources, then the old Wikipedia fallback. Results are parsed from
  the page HTML (or the JSON API) and every URL / title / snippet passes `Browser.safe_results` (url_ok, login links,
  display_ok, blocked words; videos also the chat filter) before the brain sees it. The card: "searched arXiv for
  “sleep spindles” — from his reading notes"; `info.search` = {source, engine, query, from}; the visit log carries it.
- Queries (`live_interest`, a one-line hook in `run_browse`): mind.next_interest() (weight 3, all 1–3 queries),
  what he was reading (1), words taught in the last 2 days (1.5), favoured taste words (1); each through
  `eyes.query_ok`. Chat wishes ("look up …", "what is …?", `search_sources.wish`) are searched as asked, filtered.
  `_next` searches more often (search 48 %, link 40 %, seed 12 %; was 25/55/20).
- `eyes.py`: a results page never costs a call: `result_options` builds the options from the result titles +
  snippets (lexicon networks), one refined search from the results' words, back, leave. On content pages
  `with_follow_ups` adds ≤ 2 searches from the page's own words (`follow_ups`: a name, "what is <term>?") in place
  of the last options (still ≤ 6, leave kept). `analysis/search_budget.py` (model, uniform vote): searches/hour
  31 → 52, eyes calls on results pages 9.1/h → 0, content pages with AI options 29 % → 45 %, cost unchanged
  ($0.076 per desk-hour at the 30/h cap: $1.00 lasts ~13 desk-hours).
- `/api/browsing` adds `searches` (per source today, per host last hour, refusals, the last 10 searches).
- Fixtures: `tests/data/search/` (saved 2026-10-02); `tests/test_more_search.py`. A source's markup can change:
  a parser that finds nothing makes the search fall through to the next source (and `refused_today` says so).

## What is really on his screens, shorts on the phone, dopamine-like bursts (#89, PR `feature/screens-live`)
- Diagnosis (live still showed Wikipedia, no TikTok): (1) `room.html` draws `life.reading` as a hand-made Wikipedia
  page whenever there is no desk screenshot, and since #81 that could be a browsed title; with no browser at all the
  server ran the full Wikipedia reader. (2) TikTok logged out from a datacenter IP: the tag page has no video links
  (client-rendered feed), so the TikTok feed was always empty. (3) YouTube `/watch` from a datacenter IP can hit
  google.com/sorry (429). (4) Phone time was rarely shorts. (5) `/life`'s phone showed TikTok only from
  `web/phone_feed.json`, which is empty: never TikTok, whatever the browser did.
- `screens.py`: `ScreensStatus` (browser up/down/off + why + since, the last 10 pages with kind and host, today's share
  by kind: tiktok, shorts, youtube, news, forum, finance, wikipedia, search, other; feed notes) → `GET /api/screens`,
  the always-visible "His screens" card on `/brain` and the "His screens" block on `/life`.
- `live_server.py`: `run_research` with `--browse` asked for
  but no browser running: at most one Wikipedia reading an hour (`WIKI_DOWN_EVERY_S`); browser outages logged once,
  restarted with backoff 5-80 s; `on_screen()` per status.
- Phone = shorts (`live_interest`: phone activity → feed "shorts"). TikTok first in half the feeds
  (`short_videos.TIKTOK_SHARE`). Logged out (no working `SUB01_SESSION_TIKTOK`): public TikTok videos found by the
  search engines (`site:tiktok.com`) are shown as embed cards from TikTok's public oEmbed (caption, creator,
  thumbnail; the video is not played; robots.txt disallows `/embed/v2`), else "TikTok blocked from the server today →
  YouTube Shorts" (`Browser.feed_note`, on the screens card). Cards are local pages: no links, no buttons.
- Dopamine-like bursts (`screens.DopamineBursts`): a new short gives rpe = novelty (1 / 0.3 for a topic seen in the
  last 30 min) + predicted interest (tastes, 0..1) − expectation (running mean, α 0.15), habituating over a scroll
  session (clips < 5 min apart: × 1/(1 + 0.12 (n−1))); videos ½, pages ¼, nothing new 0. Applied as
  `Neuromodulators.burst(0.5 × size)` (the DA level, the room's DA bar) and `reward` drive 8 × size × sleep gain;
  broadcast `{"type": "dopamine", ...}` with "simulated dopamine-like reward signal in the model"; the DA trace with
  spikes on `/brain`. `web/neurons3d.js` untouched.
- Room monitor (coordinator-approved, `drawReading()` only): a reading whose host is not Wikipedia is drawn as
  "host · kind" + title + excerpt ("youtube.com · short"), never inside the Wikipedia frame.
- Follow-up after the live data of 18:30 UTC (30 phone pages, all Wikipedia / abc / MediaWiki / bandcamp / npr / CC,
  the same pages reopened, footer links followed, "tiktok videos" ending on Wikipedia, `searches`/`accounts` null):
  - Why it looped: every general engine failed from Railway, so `_search` fell back to a Wikipedia search every time
    (titled "<query> — Wikipedia", hence "studio ghibli wikipedia — Wikipedia"), then followed whatever link scored
    best, including footers. Now there is no Wikipedia fallback: `search_sources.Limits` sets a source aside after
    `BLOCK_AFTER` (2) failures in a row for 1 h, doubling to 6 h (rate limits do not count); `route()` lists every
    source (the general engines first, then all the others, YouTube only for video searches, never Wikipedia for
    them); `_search` tries up to 4 working ones, then a seed site's front page (rotating, each at most every 6 h).
    Blocked sources: `/api/browsing` → `searches.blocked`, the screens panel ("sources set aside").
  - `novelty.py` (pure): `Visited` (saved as `browsing.json` → `visited`, restored by the service's `/init`): a URL,
    a video id (YouTube watch/shorts, TikTok) or a near-duplicate title (site suffixes and the word "wikipedia"
    removed) is never opened again within 7 days: `_open` (before loading), `_settle` (final URL and title),
    `pick_links` / `_pick_link` / `result_page` (never offered), shorts queues and TikTok cards. Exempt: results pages,
    seed front pages, going back. `footer_link`: about, contact, privacy, terms, legal, licences (and
    creativecommons.org deeds), cookies, help, sitemap, wiki Help/Special/Talk-namespace pages and the site's own home
    page are never offered (pagination and comment links stay).
  - A search with a video word (tiktok, shorts, reels, video, clips) goes to the shorts feed on the phone
    (`_shorts(force=True)`, the rest of the words as the topic, a discovery pick if nothing is left) and to YouTube at
    the desk; never Wikipedia or the general engines.
  - Novelty on the shorts feed (`interests.py`): a topic seen in the last 2 h weighs ×0.15; a query is not typed again
    within a day; `pick(discover=True)` takes a topic not seen in 2 h from the profile, "trending" (headlines he saw
    on front pages, `Variety.offer`) or the `DISCOVERY` pool; 70 % of shorts searches are discovery
    (`FOLLOW_SHORTS` 0.3); follow-ups on things he saw ≤ 25 % of searches (`Visited.follow_ok`), else replaced by a
    discovery pick. Per scroll session another clip on the same topic is shown only while new-topic clips stay ≥ 60 %
    (`Browser.new_share_ok`); otherwise a new search, or, once youtube.com's per-host cap (20/h, not raised) is
    reached, pages from a working source until it frees.
  - Shorts from the server's network: when a short's own page is a bot wall / does not load, it is shown as a card from
    its results-page entry (title, channel, YouTube's public thumbnail; `SV.youtube_card`, note "YouTube Shorts pages
    blocked from the server"). TikTok cards as before; TikTok set aside when no card can be built.
  - `searches: null` / `accounts: null`: both came only from the browser process, which starts only when he picks up a
    screen; after a redeploy while he slept nothing had been asked. `/api/browsing` (`Live.browsing_view`) now falls
    back to the counts saved in `browsing.json` and to the sessions read in the server (`local_accounts`), with
    `synced: false`; the loop syncs right after `/init`. `chromium alive: false` with the browser idle is the same
    thing: the screens panel now says "idle — he is not at a screen".
  - Screens panel: "now playing" with Spotify's official embed (from the music state; "Spotify keys not set: playing
    from the curated list" / "Spotify search down: …"), and the latest TikTok item in TikTok's official embed player
    ("TikTok (official embed)", `autoplay=0&muted=1`; only for captions that pass the filter). Both on `/brain` and
    `/life`.
  - Live visual check (coordinator): `/life`'s phone overlay shows only a real screen (the phone screenshot, or TikTok's
    official embed player for a public TikTok, `screen_status` → `embed`, with the screenshot of the oEmbed card as
    the fallback when the player does not load in 8 s); nothing at all when there is no screenshot (no blank box, no
    chart). `/brain`: `.card`'s `display:block` beat `[hidden]`, so the empty "Now playing" and "At his desk" cards
    showed placeholders; `#cards [hidden]` now hides them (the screens panel says "no music playing"). The neurons
    panel's "dopamine" now moves with each burst: `LiveClient.burst` → the spiking child's `burst` (display only, no
    weight change), decaying with `DA_SHOW_TAU_S` (30 s).
  - `tests/test_novelty.py` replays the live hosts and titles (Studio Ghibli ×3 + variants, the MediaWiki page ×3, the
    abc article ×2 → 3 pages opened; Contact Us, the ABC home page, CC licence deeds, privacy/terms/about never
    offered; "tiktok videos" → the shorts feed). `analysis/novelty_replay.py` runs the real choice path for 3
    simulated hours with the network stubbed the way Railway answered (general engines fail): 0 URL repeats, ~117
    unique URLs/h, Wikipedia 3 pages (random-article seed), shorts 19/h with 60 % new-topic clips (97 % of shorts
    searches on a new topic), follow-ups 21 %, 0 footer links; the YouTube per-host cap is what limits the shorts.
    Not a live browser.

## Readings from real browsing (#79, PR `feature/readings-from-browsing`)
- Before: `run_research` read Wikipedia every 4 simulated min at the desk, whatever the browser showed, and those
  were all his readings (the reading stimulus, reading memory, REM replay, the memory test, the diary).
- `readings.py` (pure) `BrowseReadings`: a page he stayed on (`MIN_DWELL_S`: shorts 15 s, videos 60 s, pages 45 s,
  simulated) becomes the reading, at most one per `READ_GAP_S` (= research.READ_EVERY_S, the old rate), the best
  page of each gap (longer stay, real text), stale after 30 min; Wikipedia only while it stays ≤ 10 % of the day's
  readings (`WIKI_MAX`). Kind: video, short, forum, news, finance, wiki, page; host kept. Safety: the title must pass
  `display_ok`; finance pages give only their topic word ("memecoins", "stocks"; no URL, ticker, price); logged-in
  pages only their public title; the excerpt keeps only sentences that pass `display_ok`.
- `live_server.py`: `take_reading()` (absorb, "on his mind" via `Reader.record`, tonight estimate, the `reading`
  broadcast with `host`/`kind`/`via`, old fields kept); memory items carry `host`, `kind`, `via`. `run_research`
  reads Wikipedia only when `wiki_fallback()`: no browser (BROWSE=0 / no playwright) or the browser down for more
  than `WIKI_FALLBACK_S` (300 s). Every reading is logged with its source. The diary's read list has `kind`/`verb`
  ("watched" for videos and shorts); `/brain` and `/diary` say "read or watched". `web/room.html` untouched (#63).
- `analysis/readings_day.py` (model, 8 h at the screens): before 15 readings/h, 100 % Wikipedia; after 11.4/h,
  Wikipedia 9.5 %, shorts 23 %, news 19 %, pages 19 %, forums 13 %, finance (topic word only) 12 %, videos 5 %.
- `/api/memory`: `pod_manager.top_items` gives readings `host`/`kind`; `session_config` writes them to
  `/data/spiking/item_meta.json` ({item: {host, kind}}, last 500), the pod's items stay as they were; the hub's
  `store_items` adds them to the reading rows of `memory_tests.jsonl`, and `/api/memory` items return them.

## Browse like a real young guy (#56 scope extension, part 2)
- Owner: "he focuses too much on one topic … no guy like him would spend all day on Wikipedia", then "NO
  RESTRICTIONS" (comment 2 replaces B.5 and D of comment 1).
- `interests.py` (pure): `PROFILE` (seed weight, searches, page words per topic: music, anime, games, sports, food,
  fashion, tech, memes, crypto, markets, tokyo, science, a little wikipedia; edit here), tastes move a topic 0.5–1.6x
  (`taste_multipliers`, computed in the live server, passed with the interest), `RHYTHM` by Tokyo hour (morning news
  + weather, lunch short videos, afternoon interests, evening YouTube + games, late night Shorts on the phone).
  `Variety` (per Tokyo day, saved in `browsing.json` → `searches.variety`): topic counts, Wikipedia share, the run of
  pages on one topic. No outside quota: `saturation` lowers a topic's weight past 15 % of the day (Wikipedia past
  10 %, also in `route`), and after 3+ pages on one topic `streak_pull` raises the leave option's pull
  (`eyes.leave_pull`, read by brain_vote's LEAVE_CHAIN) and the share of profile searches (`Browser.profile_share`).
  `analysis/variety_day.py` (model): topic entropy 2.96 → 3.48 bits (max 3.58), top topic 22 % → 14 %, Wikipedia
  28 % → 4 % of pages.
- Short videos on the phone (`short_videos.py`, one place per site; `Browser._shorts` drives it; `Screen.mode ==
  "shorts"` when the rhythm's feed or the phone app says so). Navigation goes through `_open`, so #60's per-site
  logged-in context (`_use`) and view_only.py's private / action filters apply when a session exists: a YouTube
  Shorts search (Restricted Mode cookie) or a TikTok tag page (logged out; robots.txt disallows TikTok's /search),
  shorts queued, each next short picked by the vote among the queued ones (local options, no paid call), muted,
  ≤ `SHORTS_MAX_S` (45 s). TikTok: comments / likes / follow / login boxes hidden (`HIDE_TIKTOK`), a login wall is
  left, captions + hashtags + creator names through `video_text_ok`. The TikTok parser's fixture is synthetic: check
  a live run.
- Seen things (`search_sources.seen_things`): video titles and channels on his screens ("saw it in a video"), page
  titles ("saw it on his screen"), walk places ("passed it on a walk"), the room eye's objects; each query carries
  its origin into the card's why.
- `research.py`: one source among many. `Reader.saw()` (one line in `run_browse`) keeps the last page / video the
  browser showed; `current()` returns the newer of that and the last Wikipedia article, so "on his mind" is what he
  really reads; `due()` waits while he browses.
- Finance (owner, "NO RESTRICTIONS"): exchanges, DEX / swap pages, launchpads, chart pages, forums and our own coin's
  pages are viewable read-only. Still blocked: the harmful categories (adult, gore, self-harm, extremism, illegal),
  gambling, wallet apps (metamask, phantom, walletconnect). `money_action` (buy, sell, swap, connect, sign, deposit,
  withdraw, stake, claim, mint, …; and buy/connect/claim/mint/create/launch/wallet URLs): never numbered, never offered,
  refused in `act` even when the brain picks such a link. `eyes.query_ok` refuses buy/sell wording; labels too.
  `finance_note`: finance pages add "He is just browsing; nothing here is financial advice." to the card (`advice`,
  and in `why`). `display_ok` (his words: mind notes, the card title, video titles) stays strict, finance talk
  included; `title_ok` (web titles, link labels, results) shows prices and tickers. mind.py's FINANCE rule stays and
  `next_interest` skips finance.

## YouTube and chess at the desk (#17, PR `feature/youtube-chess`)
- `life.py`: two more activities chosen by needs, `watch_video` (boredom, visual response, a chat wish; only with a
  browser: `Life.can_watch`) and `play_chess` (attention, a chat wish; at most one game per simulated hour,
  `CHESS_EVERY`, `last_chess` saved in life.json).
- YouTube builds on #40's `play_video`: every browser context carries the Restricted Mode cookie (`PREF f2=8000000`);
  in `watch_video` the desk opens a YouTube search for his interest (a URL through `eyes.query_ok`, nothing typed); the
  brain vote picks among the options as for any page. A chosen video plays muted and locked muted (`VIDEO_JS`
  overrides `muted`/`volume` on the element; Chromium also runs `--mute-audio`) for `brain_vote.watch_minutes`
  (2–10 simulated min, longer for a strong vote value, shorter when bored; the browser clamps to 10 s..600 s real),
  then the page goes back to the vote. While he watches, each screenshot (every 4 s) is compared with the previous one
  (`browse.scene_change`, 64x36 grey thumbnails) and `Live.video_drive` stimulates the visual network with
  `VIDEO_DRIVE` (6) x change x sleep gain. Titles and channel names pass `display_ok` and `chat.blocked`
  (`browse.video_text_ok`); comments, live chat and the like/subscribe buttons are hidden; `ServiceLogin` links are
  login links. No new paid calls (the eyes' existing cap covers the YouTube pages).
- `chess_game.py` (python-chess, PyPI name `chess`, pure Python): a simple move scorer (material + centre, one ply)
  ranks the legal moves; the top 5 are brain-vote options tagged with networks (capture → reward, check → attention +
  salience, a piece left en prise → threat, castling → control). `Live.chess_step` (task `run_chess`) runs the scorer,
  the vote and the opponent (depth-2 minimax, random tie-breaks) in worker threads on board copies, paces moves in
  simulated time (≥ 0.7 s real), keeps him at the desk until the game ends (≤ 90 simulated min), then ends the
  activity. One row per game in `/data/chess.jsonl`; `GET /api/chess`. Card wording (owner): "his brain model picks
  among 5 candidate moves from a simple move scorer".
- Shown on `/brain` ("At his desk" card: the board with the 5 candidates and the pick, or the muted video with its
  options); the room view follows #46.

## Brain decides what he clicks (PR `feature/brain-decides`)
- Eyes (`eyes.py`): after a page, an AI lists 3-5 options from the title, visible text and up to 40 numbered links
  (decision 2026-10-01: Claude Haiku 4.5 by default, hard cap $1.00 per Tokyo day). Claude `claude-haiku-4-5` if
  `ANTHROPIC_API_KEY` (`BRAIN_DECIDES_CLAUDE_MODEL`); else OpenRouter if `OPENROUTER_API_KEY` (set on Railway),
  `OPENROUTER_MODEL` default `anthropic/claude-haiku-4.5`, real cost per call logged; else Replicate Llama 3 70B.
  Request fields per model: no effort/thinking/fallbacks for Haiku 4.5; effort low for Opus/Sonnet (+ refusal
  fallbacks on the 5.5 family). cache_control on the fixed system prompt (about 344 tokens: below every model's
  cache minimum, so it caches nothing today). Links by number only, every target through the browse.py guard, search
  queries through the chat filter; max 1 call per page, `BRAIN_DECIDES_MAX_CALLS_PER_HOUR` (30) and
  `BRAIN_DECIDES_MAX_USD_PER_DAY` ($1.00, Tokyo day, from `/data/eyes_costs.jsonl`). No key / over a cap: local
  options; `/api/decisions` shows why. A chosen page that is not shown (guard, bot wall) or redirects says so.
- Vote (`brain_vote.py`): `Brain.clone()` + all options simulated 300 ms side by side (one sparse product per step,
  ~260 ms for 5 options + baseline on one core; identical to `Brain.step`); value = d_reward + 0.6 d_attention
  + 0.3 d_visual (videos) - 0.8 d_fear; + tastes + novelty; softmax, hotter when bored or sleepy. The live brain then
  gets the chosen stimulus. `BRAIN_DECIDES_SEED` makes it reproducible.
- Tastes (`tastes.py`, `/data/tastes.json`, `/api/tastes`): reward-prediction-error table over topics, 7-day decay.
  Interface `topics / predict / learn` for the spiking branch to replace with dopamine-modulated synapses.
- Chromium runs in `browse_service.py` (child process, memory watchdog `BROWSE_MEM_MB` 1200, exits if the parent
  dies), or as its own Railway service via `BROWSE_SERVICE_URL` + `BROWSE_SERVICE_TOKEN`. Down = "browser
  restarting" on the page; the brain loop does not stop (`supervised()` tasks). `/api/decisions` lists choices.

## Music on Spotify (#68, PR `feature/music`)
- Legal frame: **Spotify's official embed player only** (`open.spotify.com/embed/track/<id>`, compact 80 px). Each
  visitor presses play on their own device (30 s preview, or the full track when logged in to Spotify). The server never
  streams, downloads or relays audio: `music.py` only calls the Web API (search + track metadata) and oEmbed, both JSON
  (`http_json` refuses to read a non-JSON body); preview URLs are never read.
- `music.py`: with `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` (Railway; client-credentials flow, never logged or
  returned) the Web API's search (market JP; `audio-features` / `recommendations` are not used, restricted since
  Nov 2024). Without keys, or when the API fails: `music_curated.json` (9 genres x ~14 public tracks: Tokyo city pop,
  J-pop, lofi, hip-hop, anime, indie, electronic, jazz, piano), built by `analysis/build_music_list.py` from public
  playlists' embed metadata (explicit / 19+ tracks dropped); each picked ID is checked once with oEmbed (no key) and
  cached in `/data/music.json`. Queries: time of day (morning jazz/piano, evening hip-hop/city pop, late-night lofi),
  favoured taste words, words taught in the last 2 days, `mind.next_interest`, and chat wishes ("play …", "metti …",
  through `chat.blocked`; `music.wish`).
- His brain chooses: 3-5 candidates are `brain_vote` options (`action: "listen"`); their networks come from the genre
  tags + title + artist through `chat.networks_for` (no audio analysis). Music calls `brain_vote.vote`
  directly (the rate model; `brain_vote.Backend` / spiking only votes on browsing so far).
  The stay response while a track plays (a second `PageWatch`) goes to `tastes.learn` with the topics
  `net:*`, `kw:*` and `kw:<genre>`, so a music taste forms over days.
- `life.py`: `listen_music` (on the bed, 8-25 sim min; boredom, sleep pressure, evening, a chat wish; needs first: food
  outranks it and interrupts it). Background music is a flag, not an activity: `Life.music_bg_ok()` (reading or chess
  at the desk, the park bench, walking outside); `live_server` rolls once per activity (`MUSIC_BG_P` 0.4). The snapshot
  carries `life.music` = {title, artist, mode} for the room's headphones.
- `GET /api/music`: now playing (title, artist, album art, Spotify URL, embed URL, the vote's options and reason), today's
  tracks with why each was picked, the source, live wishes. `music` websocket messages on start and end; one row per
  track in `/data/music.jsonl`. Cards on `/brain` and `/life.html`; the room (headphones, head nod) waits for #63.
- Mind and diary: each track is a `music` item in the mind's memory (`day_notes()["listened"]`); the diary gets the
  day's genres and the one playing when he fell asleep ("it fell asleep after city pop"; genres only, no artist names).
- Wording: "his brain model leaned toward …", never "he loves this song".

## His spiking neurons in the day (#55, `docs/spiking/live_cpu.md`)
- `spiking/live.py`: a 20k-neuron spiking network runs in a child process (`python -m spiking.live`). It uses numpy and
  the same construction as `net.py` via `spiking/wiring.py`, no torch. It speaks the decision protocol shared with #58
  (decide / decision / reward, JSON lines) and streams `{"type":"spiking","net":"cpu"}` frames to the Neurons panel.
- `brain_vote.Backend`: the GPU pod's 1M network first (`pod_manager.day_live_decide`, #58), then the CPU child within
  2 s, then the rate model alone. `vote(..., spiking=)` adds `SPIKING_W` (0.3) x the lean, and the record says which
  network answered.
- Rewards: the tastes prediction error of the stay goes to the network that decided (CPU: the #39 rule, with a
  decaying learning rate). Weights are in `/data/spiking/live_weights.npz`.
- Every browse decision and its reward go to `/data/spiking/decisions-YYYY-MM-DD.jsonl`, which #58 reads at night.
- `/api/spiking/live` feeds the "In the day" part of the Neurons card. `SUB01_SPIKING_LIVE=0` turns the CPU network off.
- Measured: tick 8.8–9.5 ms vs 8.9–9.2 on main. The child uses ~0.4 CPU-s per decision and 1.4–2 % of a core
  between decisions (its idle pulse).

## His active neurons inside the 3D brain (#62, `docs/spiking/neurons3d.md`)
- `spiking/frames.py` (numpy, no torch): both spiking networks' frames go to the pages compact: `n3.rq` (1 byte a
  region of spike rate, log 0.1–100 Hz), `n3.sq` (3 bytes a recorded spike: region, slot 0–255, time; ≤ 400 a frame),
  `n3.race` (a decision race is running). `Budget` (one, in `SpikingHub.relay`; the CPU child's frames go through it
  too) keeps each viewer ≤ 3 KB/s of spiking frames: numbers once a second, spikes cut to fit, CPU frames dropped
  while the GPU streams. The room's lite feed gets none (it never drew them).
- `/brain`: a **neurons** layer button (`web/neurons3d.js` + `web/neurons3d.json`). Since #88 B a **forest of small
  real cells**, not dots: each sampled neuron is a NeuroMorpho.Org cell of its region's type simplified to ≤ 40
  segments, enlarged ~6× (labelled), pyramidal cells along the cortical surface normal; ≤ 600 cells desktop, ≤ 300
  phone, ≤ 240 mini (≥ 1 a region); one instanced draw call per type + the somata. Dim like a sparse stain (one muted
  hue a type, base ≤ 0.12; the first version saturated to white): only a recorded spike brightens a cell; fibres and
  cortex step back while neurons are on. Offline it reads "neurons offline", the cells stand still and nothing glows. `/brain?mini&neurons=1` for the room's PiP: the room follow-up
  only changes the iframe `src`. The Neurons panel (`/brain`, `/life`) reads the compact raster (one row a region).
- GPU frames carry per-region rates (`session.py` `frame()`: `"rq": quantise_rates(rr)`); a pod without it is tinted
  by network group rates, labelled. The panel also lists #70's real decisions per day (learned vs frozen twin).

## Neurons with their real shape (#78, `docs/spiking/neurons3d.md` § close-ups)
- `/brain` close-ups ("close-up: cortex · striatum · thalamus · hippocampus · amygdala", or zoom in with neurons on): 120–220 real
  reconstructed neurons (NeuroMorpho.Org, CC BY 4.0, `web/neurons_morph.json`, built by
  `analysis/build_morphologies.py`; credits `docs/spiking/morphology_credits.md` and `/about`), ≤ 60k segments,
  one instanced draw call per cell type. A sampled neuron's spike runs soma → axon in the shader, slowed ~500×.
- Illustrative shapes, never the scanned person's; the network uses point neurons. Only regions the model simulates
  get a close-up (no cerebellum / Purkinje: not one of the 214 regions).
- Whole-brain forest (#88 B, `docs/spiking/neurons3d.md` § forest): the same six cells, ≤ 40 segments each; the
  right panel's cards stop above the dock (`--dock-h`, a ResizeObserver). Agent A's close-up renderer
  (`web/neuron_render/`, #88 A) takes over the close-ups once it lands; until then the #78 lines are the fallback.

## Neurons at microscopy scale: the close-up renderer (#88 A, `docs/spiking/neuron_render.md`)
- `web/neuron_render/neuron_render.js` (classic script, `window.NeuronRender`; API in `docs/spiking/neuron_render_api.md`)
  draws one region's neurons as tapered tubes from the SWC radii (`web/neuron_render/cells.json`, the same six
  NeuroMorpho.Org cells as #78 rebuilt by `analysis/build_neuron_render.py`; radii measured for five, typical for the 1995
  CA1 cell), a soma with hillocks and a translucent nucleus, spines at published densities, myelin internodes + nodes of
  Ranvier on myelinated types, boutons, a tissue background, bloom and a mild depth of field; fluorescence (GFP green /
  tdTomato orange on black) or 3D-render style; its own overlay canvas on the brain's host, nothing drawn off screen.
- `/brain` close-ups (`closeupOpen` in `web/index.html`) now open it: `NeuronRender.open(host, {THREE, region, kind,
  label, style, live, onClose, onInfo})`, every spiking frame goes to `nr.onFrame(m)`; `nr.info()` gives the counts
  for the caption (cells, triangles vs cap, spines and the dendrite length they cover, boutons, nodes of Ranvier).
- Activity, never faked: a recorded spike of a sampled neuron flashes the soma and runs an action potential down the
  axon at the real speed / 10000 (saltatory where myelinated), boutons glow on arrival, dendrites glow with the region's
  rate; no frames for 10 s → static cells, "no live network". The caption carries the #88 sentence word for word.
- Budget: `LOD.phone` cap 250k triangles (3 hero + 12 mid + 60 line cells), `LOD.desktop` 1M; `budget()` trims mid
  cells, then spines of the last hero cells. Measured only under software WebGL here (`docs/screens/neuron_render/
  results.json`): the ≥ 30 FPS phone check needs a real device.
- Published values and their sources: `docs/spiking/neuron_render.md` (Tomassy 2014, Stedehouder 2017, Megías 2001,
  Hellwig 1994, Chomiak & Hu 2009, Hursh 1939, Benavides-Piccione 2002/2013, Wilson 1983, Rushton 1951). Reference
  look: Lee et al. 2006 PLoS Biol (CC BY 2.5), only in `docs/screens/neuron_render/side_by_side.png`.
- Checks: `pytest tests/test_neuron_render.py` (node check `tests/js/neuron_render_check.js`); screenshots and timings
  `python tests/neuron_render_shots.py`.

## Logged-in TikTok and YouTube, view-only (#60)
- `sessions.py`: `SUB01_SESSION_TIKTOK` / `SUB01_SESSION_YOUTUBE` (Railway; Cookie-Editor JSON export or Playwright cookies
  / storage state) → only cookies of the site's own domain, expired ones dropped. Logged in while a login cookie is
  unexpired; a sign-in button, a login wall or a redirect to a login page logs that site out until the next restart
  (one log line). Values are never logged or returned; YouTube keeps Restricted Mode (`PREF f2=8000000` replaces the
  session's PREF). Without the variables nothing changes.
- `browse.py`: per screen, one in-memory context per logged-in site (`Screen.sites`) alongside the logged-out one
  (`Screen.public`); `_open` picks the context by URL (`_use`). Logged-in contexts only navigate on their own domains
  and never to a private URL (`_site_route`). The env vars reach the browse service process (`browse_service.ENV_KEEP`)
  but never Chromium (`browse.CHROMIUM_ENV`).
- `view_only.py`: private pages (URL in `_open` and in the route, DOM + URL before every screenshot in `_private_ok`),
  action links never offered (`pick_links`, `result_page`) or opened (`_open`), dismiss buttons never an action, and
  the avatar / name / action buttons hidden before every screenshot (`HIDE_ACCOUNT_CSS`, `HIDE_ACCOUNT_JS`). Titles on
  a logged-in site (captions, hashtags, creators) pass `video_text_ok`.
- `/api/browsing` → `accounts`: `{"tiktok": {"state": "logged in" | "logged out", "reason"}}`. Risk note and cookie
  refresh steps in `docs/OPERATIONS.md`.

## Daily clips for the social accounts (#59, PR `feature/daily-clips`)
- `clips.py`: up to three vertical clips a day (1080x1920, 15-40 s, H.264, no audio) in `/data/clips/`, kept 14 Tokyo
  days: `day` ("A day in 30 s": desk screenshots / eye frames sampled every 20 min, captions from the life and reading
  logs), `dream` (the closed diary night: its frames, title and sentences), `choice` (a chess position with the 5
  candidates and the vote bars, or a browsing options card). Every frame has the corner label "AI · fictional character
  · simulated brain"; every clip ends on a card with the site name. Captions go through `clips.safe` (no finance words,
  no "thinks/feels"/mind claims, no links); life-log motives are cut ("hungry: orders food" -> "orders food"); the chart
  activity is never sampled; a browsing card with one unsafe option is left out whole.
- The server only samples (cheap reads every 60 s). Renders run in a child at `nice 19` with no secrets in its env,
  RLIMIT_CPU 120 s over Pillow + ffmpeg (`-threads 1 -preset veryfast`), one at a time, only at Tokyo 01:00-07:00 or
  with at most `SUB01_CLIPS_LOW_VIEWERS` (20) websockets. A day clip costs ~17 CPU-s, dream ~13, choice ~8.
  `analysis/bench_clips.py` measures the tick with renders running (see the PR for numbers).
- Room capture (`CLIPS_ROOM=1`, off by default): 6 frames of `/` in a headless Chromium child, once a day. Software
  WebGL makes it ~380 CPU-s per capture, so it stays off on Railway's shared CPU.
- `/admin/clips` (the site password's cookie, the `SUB01_ADMIN_TOKEN` header, or the token typed into its form, which
  sets an HttpOnly cookie on `/admin`): today's and recent clips, download, the ready caption (<= 150 characters with
  the label, + `#AI #AIgenerated #digitaltwin #Tokyo #simulation`) and a copy button.
- Auto-post, off unless set: `TIKTOK_POST_TOKEN` (Content Posting API; `TIKTOK_POST_MODE` draft (default, inbox) or
  direct with `is_aigc` and `TIKTOK_PRIVACY` SELF_ONLY), `YOUTUBE_CLIENT_ID` + `YOUTUBE_CLIENT_SECRET` +
  `YOUTUBE_REFRESH_TOKEN` (resumable upload, `YOUTUBE_PRIVACY` private, `containsSyntheticMedia`). One post per
  platform per Tokyo day, also when it fails; each is a $0 `clips` row in `costs.jsonl` (`/api/costs` → `posts_today`).
  `CLIPS=0` turns the whole thing off.

## Trades and sleep (fix 2026-10-02, PR `fix/sleep-and-trades`)
- **No trade feed until our coin launches.** `--mint` defaults to the env var `MINT`, which is unset, so there is no
  Solana stream at all and the pool label reads "no coin yet".
  - Until 2026-10-02 the default was a third-party token, `6GmAFS…`, a Raydium LaunchLab coin.
  - Its LaunchLab `TradeEvent` has the same Anchor discriminator as pump.fun's, so the decoder read it as
    793,100 SOL buys ("$97M trades"). Each one added arousal and woke him: arousal reached 215 and the debt 105 h,
    with no REM and no dreams.
- **At launch:** set `MINT` on Railway to our pump.fun mint, and optionally `SOLANA_WS` to a private RPC.
  - The feed then turns on, and the trade → brain wiring (`Live.apply`, `SleepEngine.stimulus`) is unchanged.
  - The pool name and our PumpSwap pool address(es) come from DexScreener, re-read every 10 min, so a graduation is
    picked up.
- **Decoding** (`decode_trades`, tested on real mainnet transactions in `tests/fixtures/solana_trades.json`):
  - an event counts only if it was emitted by pump.fun (`6EF8…F6P`) or PumpSwap (`pAMM…EA`), tracked through the
    invoke stack in the logs;
  - a bonding-curve `TradeEvent` must carry our mint;
  - a PumpSwap event must be about one of our pools; no pool known means no PumpSwap trades;
  - amounts are lamports / 1e9.
- **Guards:**
  - any single trade above `MAX_TRADE_USD` ($250k) is ignored, and logged at most once a minute;
  - total arousal is capped at `AROUSAL_MAX` (2 × the wake threshold);
  - past 18 h of sleep debt (more than one whole lost night), sleep pressure gradually overrides outside arousal
    (`SleepEngine.arousal_drive`). Chat can still keep him up for one night, as before. Under a nonstop stream of the
    largest allowed trades he still sleeps about 7.8 h a day, and the debt levels off at about 24 h.
- **Restarts:** every load clamps arousal to the wake threshold, trims the cause log, and caps the debt at 12 h.
  - The one-time repair `2026-10-02-trades` also drops the fake debt (to ≤ 2 h) and tonight's broken night record;
    `last_night` is kept as history.
  - In simulation he then falls asleep around midnight Tokyo with about 75 min of REM and replays.
- This fix adds no word or content filters (owner's instruction: chat words, vulgar ones included, are kept as they are).

## Science status (be honest on the site)
- The old public "r = 0.40" came from replaying his recorded fMRI as drive; with no coupling at all it is 0.45.
  Never present it as "his wiring produces his activity" (`analysis/null_test.py`).
- PR #5 (`feature/real-wiring`): connectome v2 (MRtrix3 + SIFT2) and a wiring-only Hopf slow layer reach FC r ≈ 0.21
  on held-out sessions, beat strength-preserving nulls, borderline vs geometry-preserving nulls. **Merge this.**
- PR #4 (`feature/digital-twin`): weaker fit (0.10), overlaps PR #5; do not merge as is (salvage receptor maps
  under CC BY 4.0, the sleep circuit, the body model later).
- `feature/spiking-brain`: 1M LIF neurons stable on an RTX 4000 Ada / A5000; memory recall works and REM replay
  strengthens cortex; **Pong does not learn** (17.5 % vs 25 % no-plasticity control): off by default (`SUB01_PONG=1`),
  labelled "not learning yet" when shown.
  Daily session (Railway `spiking/pod_manager.py`, default 21:00-22:00 Tokyo, 1 h/day from pod creation, 8 GPU-h per
  rolling 7 days, needs `SUB01_POD_SECRET` + `RUNPOD_API_KEY`): next-day test of yesterday's items → encode today's top
  5 chat + top 5 readings → test → compressed sleep with replay → test. Weights on `/data/spiking/` (pods have no
  volume). Per-item rows `memory_tests.jsonl` → `GET /api/memory` → room card "Does it remember what it read
  yesterday?". GPU check 2026-10-01 (A5000, 1M): 6/6 items recalled from half cues a simulated day later.
- PR #3 (brain-city "construct") is superseded by the room.
- `netneurolab/hansen_receptors` is CC BY-NC-SA → not usable.

## When merging PR #5 into main, keep from main
- `web/index.html` brain v2 (add the slow-layer label to its status line; it reads `m.baseline` — when the
  recording replay is off, show the slow layer and its held-out r next to what randomised wiring reaches).
- `/` → `room.html`, `/diary`, `/api/diary`, `/api/reading`, the `run_research` task, `NOCACHE`, the diary hooks in
  `run_eye`, `SOLANA_WS` + RPC backoff.
- Dockerfile copies `diary.py research.py` plus whatever the slow layer needs (`twin/`, `out/connectome_v2.npz`).

- Sleep engine = the Phillips-Robinson circuit (PR #11, `docs/twin/sleep.md`). Rollback: revert its merge commit; a
  `state.json` saved by the circuit loads and runs in the old rule engine (checked 2026-10-01), so no state reset.

## Hard rules
- No secrets in git or logs; keep the password gate; skull-stripped T1 only (no face).
- RunPod: max 1 pod per task, delete on finish/error/60 min, log costs, never touch the pod named "BRAIN".
- No heavy compute on the user's Mac (it overheats): use cloud sessions or RunPod.
- Higgsfield credits are the user's: preflight with `get_cost` and confirm big spends.
