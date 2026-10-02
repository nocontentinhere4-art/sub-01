"""SUB-01 live: runs the whole-brain model in real time and feeds it Solana trades and chat messages.

    python live_server.py --mint <token mint>   # real pump.fun / PumpSwap trades
    python live_server.py --demo                                         # synthetic trades
    python live_server.py --demo --time-scale 60 --start 23:55           # one sim hour per real minute

Buys drive the reward + visual regions, sells drive salience + amygdala, large
trades hit the thalamus + attention network. Chat messages are stimuli (see chat.py).
A sleep circuit on the local Asia/Tokyo clock (sleep.py: Phillips-Robinson MA/VLPO flip-flop + REM-on/REM-off
oscillator) changes the rhythm, how much any stimulus gets through and the tonic neuromodulator levels;
during REM, stored messages and articles it read are replayed. Page on http://localhost:8765.
"""
import argparse
import asyncio
import base64
import struct
import json
import math
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import numpy as np
from aiohttp import web

from brain_sim import Brain
from chat import RULES, Dedupe, RateLimiter, check as chat_check, dedupe_key, stimulus as chat_stimulus
from sleep import ROME, TZ, Clock, Memory, SleepEngine, Store, day_of, hhmm, next_bedtime, night_date
from eye import Eye, ReplicateLLM, load_env, market_mood
from diary import Diary
from real_baseline import RealBaseline
from life import WORLD, Life
from twin.body import Body
from twin.neurochem import Neuromodulators
from research import Reader, reading_stimulus
from browse import Browser, display_ok
import brain_vote
from browse_service import BrowserClient, BrowserDown, LocalBrowser
from eyes import Eyes
from tastes import PageWatch, Tastes
from state_io import load_json, read_jsonl, save_json

try:                                             # the GPU spiking brain is optional: the server runs without it
    from spiking import pod_manager as spiking_manager, server as spiking_server
except Exception as _e:
    spiking_manager = spiking_server = None
    print("spiking routes unavailable:", type(_e).__name__, flush=True)

HERE = Path(__file__).parent
TICK = 0.05                     # seconds of simulated time per broadcast (real time)
BASELINE_DRIVE = 1.6            # excitability per z-unit of the recorded resting-state signal
GOOD = re.compile(r"\bgood\b!?", re.I)    # chat 'good!' -> dopamine pulse on the spiking pod
NOCACHE = {"Cache-Control": "no-cache"}   # pages change with deploys: always revalidate
NEURO_K = 3.0                   # excitability per unit of receptor-weighted gain change (gain stays in 0.5..1.5)
SAVE_S = 60                     # persist sleep state + memory every minute (real time)
REPLAY_AMP = 0.35               # replayed stimulus pattern, relative to the original message
RPC_WS = os.environ.get("SOLANA_WS", "wss://api.mainnet-beta.solana.com")   # e.g. a Helius wss URL (env, never logged)
DEXS = "https://api.dexscreener.com/latest/dex/tokens/{}"
PUMP_TRADE = bytes.fromhex("bddb7fd34ee661ee")   # pump.fun bonding curve TradeEvent
AMM_BUY = bytes.fromhex("67f4521f2cf57777")      # PumpSwap BuyEvent
AMM_SELL = bytes.fromhex("3e2f370aa503dc2a")     # PumpSwap SellEvent


def decode_trades(logs):
    """Anchor events in 'Program data:' lines -> [{kind, sol}]."""
    out = []
    for line in logs:
        if not line.startswith("Program data: "):
            continue
        b = base64.b64decode(line[14:])
        if b[:8] == PUMP_TRADE and len(b) >= 57:
            sol, _, is_buy = struct.unpack_from("<QQ?", b, 40)          # after mint pubkey
            out.append({"kind": "buy" if is_buy else "sell", "sol": sol / 1e9})
        elif b[:8] in (AMM_BUY, AMM_SELL) and len(b) >= 72:
            # fields: ts, base_amount, quote_limit, user_base, user_quote, pool_base, pool_quote, quote_amount
            f = struct.unpack_from("<8Q", b, 8)
            buy_base = b[:8] == AMM_BUY
            if f[5] < f[6]:          # smaller raw reserve = SOL side, so SOL is the pool's base
                sol, is_buy = f[1], not buy_base
            else:
                sol, is_buy = f[7], buy_base
            out.append({"kind": "buy" if is_buy else "sell", "sol": sol / 1e9 if sol < 1e13 else 0.0})
    return out


LITE_DROP = ("act", "wave", "groups", "slow")     # per-region brain activity: only the brain page draws it


class Feed:
    """What one websocket client gets. Default (plain /ws): every tick, 20 a second, as before.
    /ws?rate=5 sends ~5 ticks a second, carrying the trades and events of the skipped ticks;
    &lite=1 leaves out the per-region activity (for pages that do not draw the brain, e.g. the room)."""

    RATES = (1.0, 20.0)                                 # ticks a second a client may ask for

    def __init__(self, rate=None, lite=False):
        if rate is not None:                            # clamped: a tiny rate would buffer trades/events without bound
            rate = min(max(rate, self.RATES[0]), self.RATES[1])
        self.every = max(1, round(1.0 / (TICK * rate))) if rate else 1
        self.lite, self.n, self.trades, self.events = lite, 0, [], []

    @classmethod
    def from_query(cls, query):
        try:
            rate = float(query.get("rate", ""))
        except ValueError:
            rate = None
        if rate is not None and not (math.isfinite(rate) and rate > 0):
            rate = None                                 # unusable: every tick, as plain /ws
        return cls(rate, query.get("lite") in ("1", "true"))

    def take(self, msg, data):
        """The text to send for `msg` (already serialised as `data`), or None to skip this tick."""
        if msg.get("type") != "tick" or (self.every == 1 and not self.lite):
            return data
        out = msg
        if self.every > 1:
            self.trades += msg.get("trades") or []
            self.events += msg.get("events") or []
            self.n += 1
            if (self.n - 1) % self.every:              # the first tick goes out at once, then every n-th
                return None
            out = msg | {"trades": self.trades, "events": self.events}
            self.trades, self.events = [], []
        if self.lite:
            out = {k: v for k, v in out.items() if k not in LITE_DROP}
        return json.dumps(out)


class Live:
    def __init__(self, mint, demo, time_scale=1.0, data_dir=HERE / "data", start=None, trust_proxy=False):
        self.brain = Brain()
        self.mint, self.demo = mint, demo
        self.trust_proxy = trust_proxy
        self.store = Store(data_dir)
        saved, mem = self.store.load()
        self.memory = Memory(mem)
        if start is None and saved and time_scale != 1:
            start = saved["t"]                                   # accelerated clock resumes where it stopped
        self.clock = Clock(time_scale, start)
        now = self.clock.now()
        self.engine = SleepEngine.from_dict(saved) if saved else SleepEngine(now)
        self.engine.t = min(self.engine.t, now)
        self.engine.update(now)
        self.limiter, self.dedupe = RateLimiter(), Dedupe()
        for m in self.memory.chat()[-200:]:
            self.dedupe.recent.append(dedupe_key(m["text"]))
        self.burst = 0.0
        self.sol_usd = 150.0
        self.clients = set()
        self.feeds = {}             # websocket -> Feed (its tick rate and fields)
        self.pending = []           # trades waiting to be played into the brain
        self.seen = set()
        self.pool_name = "demo" if demo else mint[:6]
        self.stats = {"buys": 0, "sells": 0, "usd": 0.0}
        self.eye = None                  # set by main() with --eye
        self.diary = None                # dream diary, set by main() with --eye
        life_path = Path(data_dir) / "life.json"
        self.life_path = life_path
        self.body_path = Path(data_dir) / "body.json"
        bs = load_json(self.body_path, {})              # state_io: a torn file is kept aside, never a crash loop
        life_state = load_json(life_path)
        if not bs.get("body") and life_state and "hunger" in life_state:      # first start: carry the old hunger over
            bs["body"] = {"ghrelin": min(1.0, max(0.0, life_state["hunger"]))}
        self.body = Body(bs.get("body"))
        self.neuro = Neuromodulators(state=bs.get("neuro"))
        atlas = json.load(open(HERE / "out" / "atlas_names.json"))
        self.nm_idx = np.array([atlas.index(n) for n in self.brain.names])
        self.life = Life(life_state, body=self.body)
        self.time_scale = time_scale
        self.life.time_scale = time_scale
        self.reading_path = Path(data_dir) / "reading.json"
        self.reader = Reader(load_json(self.reading_path))
        self.browsing_path = Path(data_dir) / "browsing.json"
        self.browser = None              # BrowserClient (main() with --browse): Chromium runs in its own process
        self.local_browser = None        # LocalBrowser when that process is our child (no BROWSE_SERVICE_URL)
        self.browsing_state = load_json(self.browsing_path, {})
        self.eyes = None                 # eyes.py: an AI lists options; the brain model picks (brain_vote.py)
        self.tastes = Tastes(Path(data_dir) / "tastes.json")
        self.pagewatch = PageWatch()
        self.decisions = {}              # device -> last decision record (shown in the screen card)
        self.decision_log = []
        self.targets = {}                # link / search -> wall time last chosen (novelty)
        seed = os.environ.get("BRAIN_DECIDES_SEED")
        self.vote_rng = np.random.default_rng(int(seed) if seed else None)
        self.baseline = None             # set by main() with --replay-real-session (else the fitted slow layer runs)
        self.eye_every = 90.0            # seconds between eye frames while awake (--eye-every)
        self.recent_trades = []          # (t, kind, usd) for the eye's market mood
        self.recent_replays = []         # REM replays for the eye's dreams
        self.recent_read_replays = []    # ...and titles of replayed readings
        self.last_groups = {}
        self.last_rel = {}               # group activity / mean, guides what it reads next
        self.last_frame = None
        self.spiking = None              # SpikingHub, set by spiking.server.attach in main()

    # --- trades -> stimuli ---------------------------------------------------
    def apply(self, tr):
        gain = self.engine.stimulus(self.clock.now(), "trade", tr["usd"])     # asleep: less gets through
        s = gain * min(15.0, 2.0 + 3.0 * math.log10(1.0 + tr["usd"]))
        b = self.brain
        if tr["kind"] == "buy":
            b.stimulate("reward", s)
            b.stimulate("visual", 0.5 * s)
            self.stats["buys"] += 1
        else:
            b.stimulate("salience", s)
            b.stimulate("fear", s)
            self.stats["sells"] += 1
        if tr["usd"] >= 1000:
            b.stimulate("relay", 10 * gain)
            b.stimulate("attention", 8 * gain)
        self.stats["usd"] += tr["usd"]
        self.neuro.on_trade(tr["kind"], tr["usd"], t=time.time())          # buys: dopamine RPE; sells: noradrenaline
        self.recent_trades = [x for x in self.recent_trades if time.time() - x[0] < 300] + [(time.time(), tr["kind"], tr["usd"])]

    async def rpc_trades(self):
        """Stream every pump.fun / PumpSwap trade of the mint straight from Solana logs."""
        async with aiohttp.ClientSession() as http:
            try:
                async with http.get(DEXS.format(self.mint)) as r:
                    pairs = (await r.json()).get("pairs") or []
                    if pairs:
                        self.pool_name = f"${pairs[0]['baseToken']['symbol']}"
            except Exception as e:
                print("name lookup failed:", e)
            asyncio.create_task(self.sol_price(http))
            backoff = 2.0
            while True:
                try:
                    async with http.ws_connect(RPC_WS, heartbeat=30) as ws:
                        await ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                            "params": [{"mentions": [self.mint]}, {"commitment": "confirmed"}]})
                        backoff = 2.0
                        async for m in ws:
                            v = json.loads(m.data).get("params", {}).get("result", {}).get("value")
                            if not v or v.get("err"):
                                continue
                            for tr in decode_trades(v["logs"]):
                                tr["usd"] = tr.pop("sol") * self.sol_usd
                                tr["tx"], tr["who"], tr["at"] = v["signature"], "", time.time()
                                self.pending.append(tr)
                except Exception as e:                    # public RPCs refuse some cloud IPs: back off, don't hammer
                    if backoff == 2.0 or backoff >= 60:
                        print(f"rpc stream error, retrying every {backoff:.0f}s:", str(e).split(", url=")[0], flush=True)
                    await asyncio.sleep(backoff)
                    backoff = min(60.0, backoff * 2)

    async def sol_price(self, http):
        while True:
            try:
                async with http.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as r:
                    self.sol_usd = float((await r.json())["solana"]["usd"])
            except Exception:
                pass
            await asyncio.sleep(600)

    async def demo_trades(self):
        while True:
            await asyncio.sleep(random.expovariate(1.5))
            kind = "buy" if random.random() < 0.55 else "sell"
            usd = math.exp(random.gauss(3.5, 1.6))
            self.pending.append({"kind": kind, "usd": usd, "tx": "", "who": "demo", "at": time.time()})

    # --- chat -> stimuli + memory -----------------------------------------------
    @staticmethod
    def public(m):
        return {"text": m["text"], "t": hhmm(m["t"]), "networks": m["networks"], "emotion": m["emotion"],
                "asleep": m["asleep"], "stage": m["stage"]}

    def heard(self, t):
        """Recent chat texts (not readings), newest last."""
        return [m["text"] for m in self.memory.chat()[-5:] if t - m["t"] < 3 * 3600]

    def absorb_reading(self, art):
        """An article it opened becomes a stimulus (chat rules at half gain + language/attention) and a memory."""
        t = self.clock.now()
        stim, hits, emotion = reading_stimulus(art["title"], art.get("keywords", []))
        gain = self.engine.gain                               # asleep = attenuated, as for chat
        for g, a in stim.items():
            self.brain.stimulate(g, a * gain)
        m = self.memory.add(t, art["title"], self.engine.stage, stim, emotion, hits, source="reading",
                            title=art["title"], keywords=art.get("keywords", []), url=art.get("url", ""))
        art.update(networks=hits, emotion=emotion, gain=round(gain, 2))
        return m

    def tonight_chance(self, m):
        """Estimated chance this memory is replayed tonight (blocking: run in a worker thread)."""
        return round(self.memory.replay_chance(m, next_bedtime(self.clock.now())), 2)

    def reading_now(self, t):
        """The article on the desk for the tick; its tonight estimate only while it is about the coming night."""
        art = self.reader.current()
        if art and "tonight" in art and art.get("tonight_night") != night_date(next_bedtime(t)):
            art = {k: v for k, v in art.items() if k != "tonight"}
        return art

    async def handle_chat(self, ws, key, text):
        ok, reason = chat_check(text, key, self.limiter, self.dedupe)      # filter first; blocked = never stored
        if not ok:
            await ws.send_json({"type": "chat_ack", "ok": False, "reason": reason})
            return
        text = text.strip()
        t = self.clock.now()
        stim, hits, emotion = chat_stimulus(text)
        gain = self.engine.stimulus(t, "message")
        for g, a in stim.items():
            self.brain.stimulate(g, a * gain)
        m = self.memory.add(t, text, self.engine.stage, stim, emotion, hits)
        if self.eye:
            self.eye.hear(text, t)
        self.life.hear(text, t)
        if self.spiking:                                   # no-op when no GPU pod is connected
            self.spiking.forward_chat(text, emotion)
            if GOOD.search(text):
                self.spiking.forward_good()
        await ws.send_json({"type": "chat_ack", "ok": True})
        await self.broadcast({"type": "chat", "gain": round(gain, 2), **self.public(m)})

    def nights(self):
        def summary(n):
            if not n:
                return None
            reading = sum(1 for r in n["replays"] if r.get("source") == "reading")
            return {"date": n["date"], "sleep_onset": n["sleep_onset"], "woke_up": n["woke_up"],
                    "wakeups": n["wakeups"], "replays": n["replays"][-20:], "sleep_debt": n["sleep_debt"],
                    "n_replays": {"chat": len(n["replays"]) - reading, "reading": reading}}
        return {"type": "nights", "last": summary(self.engine.last_night), "tonight": summary(self.engine.night)}

    async def broadcast(self, msg):
        data = json.dumps(msg)
        for ws in list(self.clients):
            feed = self.feeds.get(ws)
            out = feed.take(msg, data) if feed else data
            if out is None:
                continue
            try:
                await ws.send_str(out)
            except Exception:
                self.clients.discard(ws)
                self.feeds.pop(ws, None)

    def sleep_tick(self):
        """Advance the sleep engine, apply its parameters to the model, run REM replays and bursts."""
        b, e = self.brain, self.engine
        t = self.clock.now()
        out = []
        for ev in e.update(t, dt_real=TICK):
            if ev["type"] == "replay":
                m = self.memory.pick(t, e.night_start(), replayed=e.replay_counts())
                if m is None:
                    continue
                b.stimulate("memory", 6.0)                                   # hippocampus drives the replay
                for g, a in m["stimulus"].items():
                    b.stimulate(g, REPLAY_AMP * a)
                e.record_replay(t, m)
                src = m.get("source", "chat")
                if src == "reading":
                    self.recent_read_replays = (self.recent_read_replays + [m["text"]])[-8:]
                else:
                    self.recent_replays = (self.recent_replays + [m["text"]])[-8:]
                out.append({"type": "replay", "t": hhmm(t), "text": m["text"], "networks": m["networks"],
                            "received": hhmm(m["t"]), "source": src})
            else:
                out.append(ev | {"t": hhmm(t)})
                if ev.get("natural"):
                    self.store.save(e, self.memory)                          # night closed: write it now
        if self.spiking:
            self.spiking.forward_sleep(e.stage)
        p = e.params
        b.set_rhythm(p["f_hz"], p["coupling"], p["noise"])
        b.a = p["a"]
        if e.stage == "REM" and random.random() < TICK / 4.0:              # brief REM bursts (~every 4 s)
            self.burst = 1.0
            b.stimulate("relay", 4.0)
            b.stimulate("visual", 3.0)
        self.burst *= math.exp(-TICK / 0.4)
        return out

    # --- simulation loop -------------------------------------------------------
    async def run_brain(self):
        b = self.brain
        steps = int(TICK / b.dt)
        gidx = {k: v for k, v in b.group_idx.items() if v}
        next_t = last_save = time.time()
        while True:
            now = time.time()
            events = self.sleep_tick()
            gain = {"AWAKE": 1.0, "REM": 0.7}.get(self.engine.stage, 0.3)
            if self.baseline:                                         # replaying a real recorded session (optional)
                b.drive = BASELINE_DRIVE * gain * np.clip(self.baseline.advance(TICK), -2.0, 3.0)
            else:                                                     # spontaneous slow layer fitted to his data
                b.slow_gain = gain
            due = [t for t in self.pending if t["at"] <= now]
            self.pending = [t for t in self.pending if t["at"] > now]
            for tr in due:
                self.apply(tr)
            acc = np.zeros(b.n)
            for _ in range(steps // 5):
                z = b.step(5)
                acc += np.abs(z)
            act = acc / (steps // 5)
            wave = {k: float(z.real[i].mean()) for k, i in gidx.items()}
            st = b.state()
            msg = {"type": "tick", "act": np.round(act, 3).tolist(), "wave": wave,
                   "groups": (groups := {k: round(float(act[i].mean()), 3) for k, i in gidx.items()}),
                   "sync": round(st["sync"], 3), "stats": self.stats,
                   "trades": [{k: t[k] for k in ("kind", "usd", "tx", "who")} for t in due],
                   "pool": self.pool_name, "events": events,
                   "sleep": self.engine.status() | {"burst": round(self.burst, 2)},
                   "baseline": self.baseline.status() if self.baseline else None,
                   "slow": b.slow.status() if b.slow_on else None}
            self.last_groups = groups
            base = sum(groups.values()) / max(1, len(groups))
            rel = self.last_rel = {k: v / max(base, 1e-6) for k, v in groups.items()}
            # neuromodulators x receptor maps -> regional excitability; the body -> interoceptive drive to the insula
            levels = self.neuro.update(TICK, self.engine.modulators)      # tonic levels read from the sleep circuit
            b.neuromod = NEURO_K * (self.neuro.region_gain(levels)[self.nm_idx] - 1.0)
            amyg = max(0.0, rel.get("fear", 1.0) - 1.0)
            body_levels = dict(levels, NE=min(levels["NE"], 1.5))       # the market can quicken his pulse, not race it
            self.body.update(TICK * self.time_scale, body_levels, min(amyg, 0.4), self.engine.stage,
                             exertion=self.life.exertion())
            for grp, amt in self.body.intero_drive().items():
                b.stimulate(grp, amt * TICK / 2.0)                    # settles at `amt` (stimuli decay with tau 2 s)
            hot = min(1.0, sum(1 for x in self.recent_trades if now - x[0] < 60) / 10)
            tsim = self.clock.now()
            self.life.update(tsim, TICK, TICK * self.time_scale, self.engine.stage, rel, hot,
                             self.engine.pressure(tsim))
            msg["life"] = self.life.snapshot()
            msg["neuro"] = {k: round(v, 2) for k, v in levels.items()}
            if self.life.activity == "research" and not self.life.path:
                msg["life"]["reading"] = self.reading_now(tsim)
            if self.browser and (dev := self.screen_device()):
                msg["life"]["screen"] = self.screen_status(dev)
                self.pagewatch.feed(rel, now, TICK)
            await self.broadcast(msg)
            if events:
                await self.broadcast(self.nights())
            if now - last_save >= SAVE_S:
                self.store.save(self.engine, self.memory)
                save_json(self.life_path, self.life.to_dict())
                save_json(self.body_path, {"body": self.body.to_dict(), "neuro": self.neuro.to_dict()})
                save_json(self.reading_path, self.reader.to_dict(), ensure_ascii=False)
                last_save = now
            next_t += TICK
            await asyncio.sleep(max(0.0, next_t - time.time()))

    # --- the computer: what it reads (Wikipedia only) ---------------------------------
    async def run_research(self):
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(5)
            t = self.clock.now()
            if self.life.activity != "research" or self.life.path or not self.reader.due(t):
                continue
            art = await loop.run_in_executor(None, self.reader.read, t, self.heard(t), dict(self.last_rel))
            if art:
                m = self.absorb_reading(art)
                try:
                    art["tonight"] = await loop.run_in_executor(None, self.tonight_chance, m)
                    art["tonight_night"] = night_date(next_bedtime(self.clock.now()))
                except Exception as e:                     # an estimate must never stop the reading
                    print("research: replay estimate failed:", repr(e)[:120], flush=True)
                await self.broadcast({"type": "reading", **art})

    # --- the screens: a real browser on the open web (desk + phone) -------------------
    def screen_device(self):
        if self.life.path or self.engine.stage != "AWAKE":
            return None
        return {"research": "desk", "phone": "phone"}.get(self.life.activity)

    def screen_status(self, dev):
        if self.browser.restarting:
            return {"device": dev, "restarting": True}
        st = self.browser.screens.get(dev)
        dec = self.decisions.get(dev)
        if st and not display_ok(st.get("title", "")):           # the public card never shows such a title
            st = dict(st, title=st.get("host", ""))
        # the options belong to the page they were considered on and to the page the choice led to, no later one
        if st and dec and (st.get("url") == dec.get("page_url") or st.get("id") == dec.get("status_id")):
            st = dict(st, decision={k: dec.get(k) for k in ("options", "reason", "eyes", "ms", "temperature", "page",
                                                            "outcome")})
        return st

    async def run_browse(self):
        """Drive the screens through the browser service; if it is down the brain and the page carry on."""
        idle_since, last_save, last_sync, ready, open_dev = time.time(), time.time(), time.time(), False, None
        while True:
            await asyncio.sleep(1)
            dev = self.screen_device()
            now = time.time()
            try:
                if dev is None:
                    if open_dev and now - idle_since > 120:     # put away: the service frees the memory
                        self.end_page()
                        await self.browser.close()
                        open_dev = None
                    continue
                idle_since = now
                if self.local_browser:
                    proc = await self.local_browser.ensure()
                    if proc == "down":
                        raise BrowserDown("browser process did not start")
                    if proc != "ok":                            # a new process: give it the saved log again
                        ready, open_dev = False, None
                        self.end_page()
                if not ready:
                    await self.browser.init(self.browsing_state)
                    ready = True
                if open_dev and open_dev != dev:
                    self.end_page()
                    await self.browser.close(open_dev)
                open_dev = dev
                t = self.clock.now()
                art = self.reader.current()
                interest = art["title"] if art else None
                d = await self.browser.step(dev, self.heard(t), interest)
                st = await self.decide(dev, d["decide"], interest) if d.get("decide") else d.get("status")
                if st:
                    await self.broadcast({"type": "screen", **self.screen_status(dev)})
                if now - last_sync > 30:                        # the log shown on /api/browsing stays fresh
                    await self.sync_browsing()
                    last_sync = now
                if now - last_save > 300:
                    save_json(self.browsing_path, self.browsing_state, ensure_ascii=False)
                    last_save = now
            except BrowserDown as e:
                if not self.browser.restarting:
                    print("browser down:", e, flush=True)
                    self.browser.restarting = True
                    if dev:
                        await self.broadcast({"type": "screen", "device": dev, "restarting": True})
                self.end_page()
                ready, open_dev = False, None
                await asyncio.sleep(5)

    async def sync_browsing(self):
        s = await self.browser.state()
        if s.get("log") or not self.browsing_state.get("log"):
            self.browsing_state = {"log": s.get("log", []), "used": s.get("used", [])}

    def end_page(self):
        """He leaves the page: its measured brain response updates his tastes."""
        res = self.pagewatch.finish()
        if res:
            self.tastes.learn(*res)

    def novel(self, option):
        key = option.get("href") or option.get("target") or option["action"]
        return option["action"] in ("click", "open_video", "search") and time.time() - self.targets.get(key, 0) > 7 * 86400

    async def decide(self, dev, page, interest=None):
        """The eyes list options for the page; the brain model votes; the browser carries the choice out."""
        loop = asyncio.get_running_loop()
        try:
            opts, meta = await asyncio.wait_for(loop.run_in_executor(None, self.eyes.propose, page, interest), 60)
        except asyncio.TimeoutError:                           # the AI is too slow: the page's own links
            from eyes import local_options
            opts, meta = local_options(page, interest), {"source": "local", "why_local": "AI too slow"}
        if not opts:
            return await self.browser.act(dev, {"action": "leave"}, "nothing safe to do on this page", interest)
        try:
            return await self._vote_and_act(dev, page, opts, meta, interest)
        except BrowserDown:
            raise
        except Exception as e:                                 # a failing vote must not stall the screens
            print("decide failed:", repr(e)[:160], flush=True)
            return await self.browser.act(dev, {"action": "leave"}, "the brain vote failed; wandered on", interest)

    async def _vote_and_act(self, dev, page, opts, meta, interest):
        loop = asyncio.get_running_loop()
        t = self.clock.now()
        mood = {"boredom": self.life.boredom, "pressure": self.engine.pressure(t), "tired": self.engine.tired}
        gain = self.engine.gain
        topics = [Tastes.topics(o, page.get("title", "")) for o in opts]
        tastes = [self.tastes.predict(tp) for tp in topics]
        clone = self.brain.clone()                            # snapshot on the event loop, simulated in a thread
        dec = await loop.run_in_executor(None, lambda: brain_vote.vote(
            clone, opts, gain, mood, tastes, [self.novel(o) for o in opts], self.vote_rng))
        chosen = opts[dec["chosen"]]
        brain_vote.apply(self.brain, chosen, gain)             # the live brain receives the chosen stimulus
        self.end_page()
        self.pagewatch.start(topics[dec["chosen"]], time.time())
        now = time.time()
        self.targets = {k: v for k, v in self.targets.items() if now - v < 7 * 86400}
        self.targets[chosen.get("href") or chosen.get("target") or chosen["action"]] = now
        title = page.get("title", "")[:120]
        dec.update(device=dev, t=hhmm(t), page=title if display_ok(title) else page.get("host", ""), eyes=meta,
                   page_url=page.get("url"))
        self.decisions[dev] = dec
        self.decision_log = (self.decision_log + [dec])[-30:]
        await self.broadcast({"type": "decision", **dec})
        st = await self.browser.act(dev, {k: chosen.get(k) for k in ("action", "target", "label", "href")},
                                    dec["reason"], interest)
        dec["status_id"] = (st or {}).get("id")
        dec["outcome"] = self.outcome(chosen, st)
        return st

    @staticmethod
    def outcome(chosen, st):
        """What the chosen action led to, said plainly on the card: the voted page, a redirect, or not shown."""
        import urllib.parse
        if not st:
            return "could not be carried out"
        if st.get("missed"):
            return st["missed"]
        href = chosen.get("href")
        if href and st.get("url") and st["url"].split("#")[0] != href.split("#")[0]:
            host = urllib.parse.urlsplit(st["url"]).hostname or ""
            return f"redirected to {host.removeprefix('www.')}"
        return "opened" if href else "done"

    # --- the eye: what SUB-01 "sees" ----------------------------------------------
    async def run_eye(self):
        loop = asyncio.get_running_loop()
        while True:
            t = self.clock.now()
            if self.diary and (date := self.diary.pending_close(self.engine)):      # morning: write last night's entry
                try:
                    tok = os.environ.get("REPLICATE_API_TOKEN")
                    llm = self.eye.llm or (ReplicateLLM(tok) if tok else None)
                    read = [{"title": m["text"], "url": m.get("url", "")} for m in self.memory.items
                            if m.get("source") == "reading" and day_of(m["t"]) == date]
                    await loop.run_in_executor(None, self.diary.close, self.engine.last_night, llm, read)
                    print(f"diary: night of {date} written", flush=True)
                except Exception as e:
                    print("diary error:", repr(e), flush=True)
            attended = bool(self.clients)
            dream = bool(self.diary) and not attended and self.diary.due(self.engine, t)
            if not attended and not dream:                            # nobody watching and no dream due: spend nothing
                await asyncio.sleep(5)
                continue
            stage = self.engine.stage
            if stage == "AWAKE" and (self.recent_replays or self.recent_read_replays):
                self.recent_replays, self.recent_read_replays = [], []   # dreams end when it wakes up
            try:
                rec = await loop.run_in_executor(None, self.eye.step, t, stage, self.last_groups,
                                                 market_mood(self.recent_trades), list(self.recent_replays), hhmm(t),
                                                 self.life.snapshot()["doing"], list(self.recent_read_replays))
                self.last_frame = rec
                await self.broadcast({"type": "eye", **rec})
                if self.diary and stage == "REM" and self.engine.night is not None:
                    self.diary.add(self.engine.night["date"], rec, t, attended)
            except Exception as e:                                    # never let the eye stop the brain
                print("eye error:", repr(e), flush=True)
                await asyncio.sleep(10)
            if dream:
                await asyncio.sleep(5)                                # unattended: the diary paces itself
                continue
            await asyncio.sleep(self.eye_every * {"AWAKE": 1.0, "REM": 0.75}.get(stage, 3.0))

    # --- http ----------------------------------------------------------------
    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
        await ws.prepare(request)
        # rate-limit key; kept only in memory for this connection and the 10 s limiter window
        key = request.remote
        if self.trust_proxy and request.headers.get("X-Forwarded-For"):
            key = request.headers["X-Forwarded-For"].split(",")[0].strip()
        await ws.send_json({"type": "hello", "chat": [self.public(m) for m in self.memory.chat()[-30:]],
                            "rules": [[cond, list(groups)] for cond, groups in RULES], "world": WORLD})
        await ws.send_json(self.nights())
        if self.last_frame:
            await ws.send_json({"type": "eye", **self.last_frame})
        self.feeds[ws] = Feed.from_query(request.query)
        self.clients.add(ws)
        try:
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    d = json.loads(msg.data)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("type") == "chat" and isinstance(d.get("text"), str):
                    await self.handle_chat(ws, key, d["text"])
        finally:                                       # also on errors / cancellation: never leak a client or its buffer
            self.clients.discard(ws)
            self.feeds.pop(ws, None)
        return ws


async def supervised(name, fn, backoff=5.0):
    """Run a background task forever: an unexpected error is logged and the task restarts, so a part such as the
    screens' browser can fail without stopping the brain loop (asyncio.gather would otherwise end the server)."""
    while True:
        try:
            await fn()
            return
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"{name} task failed, restarting in {backoff:.0f}s:", repr(e)[:160], flush=True)
            await asyncio.sleep(backoff)


def parse_start(hm):
    """'HH:MM' -> sim epoch of that local (Tokyo) time today."""
    h, m = map(int, hm.split(":"))
    return datetime.now(TZ).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


LOGIN_PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>SUB-01</title><body style="margin:0;height:100vh;display:grid;place-items:center;background:#040406;
color:#ececf2;font-family:ui-monospace,Menlo,monospace"><form method=post action=/login style="display:grid;gap:12px">
<div style="background:#ff6a00;color:#0a0a0a;font-size:28px;letter-spacing:.12em;padding:2px 12px">SUB-01</div>
<input name=password type=password placeholder="password" autofocus style="background:#0c0c12;color:#ececf2;
border:1px solid #2a2a36;padding:10px;font:inherit"><button style="background:#ececf2;border:0;padding:10px;
font:inherit">enter</button>{msg}</form></body>"""


def password_gate(password):
    """Private preview: one shared password (SITE_PASSWORD), remembered in an HttpOnly cookie."""
    import hashlib
    import hmac
    token = hashlib.sha256(("sub01:" + password).encode()).hexdigest()

    @web.middleware
    async def gate(request, handler):
        if request.path == "/login":
            if request.method == "POST":
                form = await request.post()
                if hmac.compare_digest(str(form.get("password", "")), password):
                    resp = web.HTTPFound("/")
                    resp.set_cookie("sub01", token, max_age=30 * 86400, httponly=True, samesite="Lax",
                                    secure=request.headers.get("X-Forwarded-Proto") == "https")
                    raise resp
                return web.Response(text=LOGIN_PAGE.format(msg="<small>wrong password</small>"),
                                    content_type="text/html", status=401)
            return web.Response(text=LOGIN_PAGE.format(msg=""), content_type="text/html")
        if spiking_server and request.path in spiking_server.POD_PATHS:
            return await handler(request)                  # the pod authenticates with its own secret in the handler
        if hmac.compare_digest(request.cookies.get("sub01", ""), token):
            return await handler(request)
        if request.path == "/ws" or request.path.startswith("/api/"):
            raise web.HTTPUnauthorized()
        raise web.HTTPFound("/login")
    return gate


async def main(args):
    data_dir = Path(args.data_dir) if args.data_dir else HERE / "data" / ("demo" if args.time_scale != 1 else "")
    live = Live(args.mint, args.demo, args.time_scale, data_dir,
                parse_start(args.start) if args.start else None, args.trust_proxy)
    middlewares = [password_gate(os.environ["SITE_PASSWORD"])] if os.environ.get("SITE_PASSWORD") else []
    app = web.Application(client_max_size=64 * 1024 ** 2, middlewares=middlewares)
    app.router.add_get("/ws", live.ws_handler)
    manager = None
    if spiking_server:
        hub = spiking_server.attach(app, live, data_dir)
        manager = spiking_manager.from_env(data_dir, get_items=lambda: spiking_manager.top_items(live.memory, live.clock.now()))
        if manager.enabled():
            hub.manager, manager.send_stop = manager, hub.forward_stop
        else:
            manager = None

    async def snap(request):                      # save a canvas capture posted by the page (local only)
        name = Path(request.query.get("name", "snap")).name
        ext = request.query.get("ext", "png") if request.query.get("ext") in ("png", "webm", "mp4") else "png"
        (HERE / "out" / f"{name}.{ext}").write_bytes(await request.read())
        return web.Response(text="ok")
    if args.host in ("127.0.0.1", "localhost"):
        app.router.add_post("/snap", snap)        # local-only helper: never exposed on a public host
    if args.replay_real_session and list((HERE / "out" / "rest").glob("*.npz")):
        live.baseline = RealBaseline(live.brain.names, HERE / "out" / "rest")
        live.brain.use_slow_layer(False)          # the recording replaces the model's own slow activity
    if args.browse:
        load_env(HERE / ".env")                   # REPLICATE_API_TOKEN / ANTHROPIC_API_KEY for the eyes (never logged)
        if os.environ.get("BROWSE_SERVICE_URL"):  # Chromium as its own Railway service
            live.browser = BrowserClient(os.environ["BROWSE_SERVICE_URL"], os.environ.get("BROWSE_SERVICE_TOKEN", ""))
        elif Browser.available():                 # Chromium in a child process with its own memory watchdog
            live.local_browser = LocalBrowser()
            live.browser = live.local_browser.client
        else:
            print("--browse: playwright is not installed, screens stay on Wikipedia reading", flush=True)
        live.eyes = Eyes(data_dir=data_dir)

    async def screen_shot(request):               # latest screenshot of the desk or phone screen
        dev = request.match_info["device"]
        try:
            shot = await live.browser.shot(dev) if live.browser and dev in ("desk", "phone") else None
        except BrowserDown:
            shot = None
        if not shot:
            raise web.HTTPNotFound()
        return web.Response(body=shot, content_type="image/jpeg", headers={"Cache-Control": "no-store"})
    app.router.add_get("/api/screen/{device}.jpg", screen_shot)

    async def browsing(request):                  # pages shown on his screens, newest last
        log = (live.browser.log or live.browsing_state.get("log", [])) if live.browser else []
        return web.json_response({"on": bool(live.browser), "log": log[-30:]})
    app.router.add_get("/api/browsing", browsing)

    async def tastes(request):                    # what kinds of pages have paid off in the brain's response
        return web.json_response(live.tastes.top())
    app.router.add_get("/api/tastes", tastes)

    async def decisions(request):                 # the brain's last choices on the screens, with the options it saw
        return web.json_response({"decisions": live.decision_log[-20:],
                                  "eyes": live.eyes.budget.summary() if live.eyes else None,
                                  "note": "An AI reads the page and lists options; his brain model picks. "
                                          "It does not understand what it reads."})
    app.router.add_get("/api/decisions", decisions)
    if args.eye:
        load_env(HERE / ".env")                   # REPLICATE_API_TOKEN -> images in the cloud, not on this Mac
        frames_dir = Path(args.frames_dir) if args.frames_dir else HERE / "out" / "eye" / "frames"
        live.eye = Eye(frames_dir, data_dir / "world.json", width=640, height=360, steps=6)
        live.eye_every = args.eye_every
        app.router.add_static("/eye", frames_dir)
        live.diary = Diary(data_dir, frames_dir)
        app.router.add_static("/diary-img", live.diary.img)

    async def diary_index(request):                # nights written so far, newest first
        return web.json_response({"nights": live.diary.index() if live.diary else []})

    async def diary_night(request):
        try:
            d = live.diary.load(request.match_info["date"]) if live.diary else None
        except ValueError:
            d = None
        if d is None:
            raise web.HTTPNotFound()
        return web.json_response(d)
    app.router.add_get("/api/diary", diary_index)
    app.router.add_get("/api/diary/{date}", diary_night)

    async def reading(request):                   # what it read at the computer, newest last
        return web.json_response({"log": live.reader.log[-20:]})
    app.router.add_get("/api/reading", reading)

    async def frames(request):                    # recent eye frames for the world page
        log = live.eye.log if live.eye else HERE / "missing"
        rows = read_jsonl(log, last=int(request.query.get("n", "40")))         # a torn last line is skipped
        world = live.eye.world.top(live.clock.now(), 20) if live.eye else []
        return web.json_response({"frames": rows, "world": world})
    app.router.add_get("/api/frames", frames)

    gmaps_ok = {}

    async def gmaps_works(key, referer):
        """Only hand the Maps key to browsers once Google really serves Street View with it (billing on)."""
        if key not in gmaps_ok or time.time() - gmaps_ok[key][1] > 3600:
            url = ("https://maps.googleapis.com/maps/api/streetview/metadata?location=35.70545,139.57455&radius=50&key="
                   + key)
            try:
                async with aiohttp.ClientSession() as http, http.get(url, headers={"Referer": referer}) as r:
                    ok = (await r.json()).get("status") == "OK"
            except Exception:
                ok = False
            gmaps_ok[key] = (ok, time.time())
        return gmaps_ok[key][0]

    async def config(request):                    # browser config (Maps JS keys are referrer-restricted by design)
        key = os.environ.get("GOOGLE_MAPS_KEY", "")
        referer = f"{request.headers.get('X-Forwarded-Proto', request.scheme)}://{request.host}/"
        return web.json_response({"gmaps": key if key and await gmaps_works(key, referer) else ""})
    app.router.add_get("/api/config", config)
    app.router.add_get("/", lambda r: web.FileResponse(HERE / "web" / "room.html", headers=NOCACHE))   # his room is the front page       # the life is the front page
    app.router.add_get("/brain", lambda r: web.FileResponse(HERE / "web" / "index.html", headers=NOCACHE))
    app.router.add_get("/diary", lambda r: web.FileResponse(HERE / "web" / "diary.html", headers=NOCACHE))
    app.router.add_static("/", HERE / "web")
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, args.host, args.port).start()
    print(f"SUB-01 live on http://localhost:{args.port}  ({'demo' if args.demo else args.mint}, "
          f"time x{args.time_scale:g}, state in {data_dir})", flush=True)
    tasks = [live.run_brain(), live.run_research(), live.demo_trades() if args.demo else live.rpc_trades()]
    if live.eye:
        tasks.append(live.run_eye())
    if live.browser:
        tasks.append(supervised("browse", live.run_browse))
    if manager:
        tasks.append(manager.run())
    try:
        await asyncio.gather(*tasks)
    finally:
        live.store.save(live.engine, live.memory)
        if manager:
            manager.shutdown()
        if live.browser:
            try:
                await asyncio.wait_for(live.sync_browsing(), 5)  # the newest log, if the browser still answers
            except (BrowserDown, asyncio.TimeoutError):
                pass
            save_json(live.browsing_path, live.browsing_state, ensure_ascii=False)
            if live.local_browser:
                await live.local_browser.aclose()
            else:
                await live.browser.aclose()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mint", default=os.environ.get("MINT", "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx"))
    p.add_argument("--demo", action="store_true")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--frames-dir", help="where eye frames are written (default out/eye/frames)")
    p.add_argument("--time-scale", type=float, default=1.0, help="sim seconds per real second (60: 1 h per minute)")
    p.add_argument("--start", help="local (Tokyo) time HH:MM to start the (accelerated) clock at, e.g. 23:55")
    p.add_argument("--data-dir", help="state + nights directory (default data/, or data/demo when accelerated)")
    p.add_argument("--eye-every", type=float, default=90.0, help="seconds between eye frames while awake")
    p.add_argument("--replay-real-session", action="store_true", default=os.environ.get("REPLAY_REAL_SESSION") == "1",
                   help="replay his recorded resting-state fMRI as the background instead of the fitted slow layer")
    p.add_argument("--no-real-baseline", action="store_true", help=argparse.SUPPRESS)   # old flag (now the default)
    p.add_argument("--eye", action="store_true", help="generate what SUB-01 'sees' (local image + language models)")
    p.add_argument("--browse", action="store_true", default=os.environ.get("BROWSE") == "1",
                   help="real headless browser on the open web for his computer and phone screens (needs playwright)")
    p.add_argument("--trust-proxy", action="store_true", help="rate-limit by X-Forwarded-For (behind a reverse proxy)")
    asyncio.run(main(p.parse_args()))
