"""SUB-01 live: runs the whole-brain model in real time and feeds it Solana trades and chat messages.

    python live_server.py --mint <token mint>   # real pump.fun / PumpSwap trades
    python live_server.py --demo                                         # synthetic trades
    python live_server.py --demo --time-scale 60 --start 23:55           # one sim hour per real minute

Buys drive the reward + visual regions, sells drive salience + amygdala, large
trades hit the thalamus + attention network. Chat messages are stimuli (see chat.py).
A sleep circuit on the local Asia/Tokyo clock (sleep.py: Phillips-Robinson MA/VLPO flip-flop + REM-on/REM-off
oscillator) changes the rhythm, how much any stimulus gets through and the tonic neuromodulator levels;
during REM, stored messages are replayed. Page on http://localhost:8765.
"""
import argparse
import asyncio
import base64
import struct
import json
import math
import os
import random
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import numpy as np
from aiohttp import web

from brain_sim import Brain
from chat import RULES, Dedupe, RateLimiter, check as chat_check, dedupe_key, stimulus as chat_stimulus
from sleep import TZ, Clock, Memory, SleepEngine, Store, hhmm
from eye import Eye, ReplicateLLM, load_env, market_mood
from diary import Diary
from real_baseline import RealBaseline
from life import WORLD, Life
from twin.body import Body
from twin.neurochem import Neuromodulators
from research import Reader
from browse import Browser

HERE = Path(__file__).parent
TICK = 0.05                     # seconds of simulated time per broadcast (real time)
BASELINE_DRIVE = 1.6            # excitability per z-unit of the recorded resting-state signal
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
        for m in self.memory.items[-200:]:
            self.dedupe.recent.append(dedupe_key(m["text"]))
        self.burst = 0.0
        self.sol_usd = 150.0
        self.clients = set()
        self.pending = []           # trades waiting to be played into the brain
        self.seen = set()
        self.pool_name = "demo" if demo else mint[:6]
        self.stats = {"buys": 0, "sells": 0, "usd": 0.0}
        self.eye = None                  # set by main() with --eye
        self.diary = None                # dream diary, set by main() with --eye
        life_path = Path(data_dir) / "life.json"
        self.life_path = life_path
        self.body_path = Path(data_dir) / "body.json"
        bs = json.loads(self.body_path.read_text()) if self.body_path.exists() else {}
        life_state = json.loads(life_path.read_text()) if life_path.exists() else None
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
        self.reader = Reader(json.loads(self.reading_path.read_text()) if self.reading_path.exists() else None)
        self.browsing_path = Path(data_dir) / "browsing.json"
        self.browser = None              # set by main() with --browse: a real headless browser on the open web
        self.baseline = None             # set by main() with --replay-real-session (else the fitted slow layer runs)
        self.eye_every = 90.0            # seconds between eye frames while awake (--eye-every)
        self.recent_trades = []          # (t, kind, usd) for the eye's market mood
        self.recent_replays = []         # REM replays for the eye's dreams
        self.last_groups = {}
        self.last_frame = None

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
        await ws.send_json({"type": "chat_ack", "ok": True})
        await self.broadcast({"type": "chat", "gain": round(gain, 2), **self.public(m)})

    def nights(self):
        def summary(n):
            if not n:
                return None
            return {"date": n["date"], "sleep_onset": n["sleep_onset"], "woke_up": n["woke_up"],
                    "wakeups": n["wakeups"], "replays": n["replays"][-20:], "sleep_debt": n["sleep_debt"]}
        return {"type": "nights", "last": summary(self.engine.last_night), "tonight": summary(self.engine.night)}

    async def broadcast(self, msg):
        data = json.dumps(msg)
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                self.clients.discard(ws)

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
                self.recent_replays = (self.recent_replays + [m["text"]])[-8:]
                out.append({"type": "replay", "t": hhmm(t), "text": m["text"], "networks": m["networks"],
                            "received": hhmm(m["t"])})
            else:
                out.append(ev | {"t": hhmm(t)})
                if ev.get("natural"):
                    self.store.save(e, self.memory)                          # night closed: write it now
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
            rel = {k: v / max(base, 1e-6) for k, v in groups.items()}
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
                msg["life"]["reading"] = self.reader.current()
            if self.browser and (dev := self.screen_device()):
                msg["life"]["screen"] = self.browser.screens[dev].status()
            await self.broadcast(msg)
            if events:
                await self.broadcast(self.nights())
            if now - last_save >= SAVE_S:
                self.store.save(self.engine, self.memory)
                self.life_path.write_text(json.dumps(self.life.to_dict()))
                self.body_path.write_text(json.dumps({"body": self.body.to_dict(), "neuro": self.neuro.to_dict()}))
                self.reading_path.write_text(json.dumps(self.reader.to_dict(), ensure_ascii=False))
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
            heard = [m["text"] for m in self.memory.items[-5:] if t - m["t"] < 3 * 3600]
            art = await loop.run_in_executor(None, self.reader.read, t, heard)
            if art:
                await self.broadcast({"type": "reading", **art})

    # --- the screens: a real browser on the open web (desk + phone) -------------------
    def screen_device(self):
        if self.life.path or self.engine.stage != "AWAKE":
            return None
        return {"research": "desk", "phone": "phone"}.get(self.life.activity)

    async def run_browse(self):
        idle_since, last_save = time.time(), time.time()
        while True:
            await asyncio.sleep(1)
            dev = self.screen_device()
            now = time.time()
            if dev is None:
                if self.browser.browser is not None and now - idle_since > 120:   # put away: free the memory
                    await self.browser.close()
                continue
            idle_since = now
            other = "phone" if dev == "desk" else "desk"
            if self.browser.screens[other].ctx is not None:
                await self.browser.close(other)
            t = self.clock.now()
            heard = [m["text"] for m in self.memory.items[-5:] if t - m["t"] < 3 * 3600]
            art = self.reader.current()
            st = await self.browser.step(dev, heard, art["title"] if art else None)
            if st:
                await self.broadcast({"type": "screen", **st})
            if now - last_save > 300:
                self.browsing_path.write_text(json.dumps(self.browser.to_dict(), ensure_ascii=False))
                last_save = now

    # --- the eye: what SUB-01 "sees" ----------------------------------------------
    async def run_eye(self):
        loop = asyncio.get_running_loop()
        while True:
            t = self.clock.now()
            if self.diary and (date := self.diary.pending_close(self.engine)):      # morning: write last night's entry
                try:
                    tok = os.environ.get("REPLICATE_API_TOKEN")
                    llm = self.eye.llm or (ReplicateLLM(tok) if tok else None)
                    await loop.run_in_executor(None, self.diary.close, self.engine.last_night, llm)
                    print(f"diary: night of {date} written", flush=True)
                except Exception as e:
                    print("diary error:", repr(e), flush=True)
            attended = bool(self.clients)
            dream = bool(self.diary) and not attended and self.diary.due(self.engine, t)
            if not attended and not dream:                            # nobody watching and no dream due: spend nothing
                await asyncio.sleep(5)
                continue
            stage = self.engine.stage
            if stage == "AWAKE" and self.recent_replays:
                self.recent_replays = []                              # dreams end when it wakes up
            try:
                rec = await loop.run_in_executor(None, self.eye.step, t, stage, self.last_groups,
                                                 market_mood(self.recent_trades), list(self.recent_replays), hhmm(t),
                                                 self.life.snapshot()["doing"])
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
        await ws.send_json({"type": "hello", "chat": [self.public(m) for m in self.memory.items[-30:]],
                            "rules": [[cond, list(groups)] for cond, groups in RULES], "world": WORLD})
        await ws.send_json(self.nights())
        if self.last_frame:
            await ws.send_json({"type": "eye", **self.last_frame})
        self.clients.add(ws)
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            try:
                d = json.loads(msg.data)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("type") == "chat" and isinstance(d.get("text"), str):
                await self.handle_chat(ws, key, d["text"])
        self.clients.discard(ws)
        return ws


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
        if Browser.available():
            bpath = data_dir / "browsing.json"
            live.browser = Browser(json.loads(bpath.read_text()) if bpath.exists() else None)
        else:
            print("--browse: playwright is not installed, screens stay on Wikipedia reading", flush=True)

    async def screen_shot(request):               # latest screenshot of the desk or phone screen
        dev = request.match_info["device"]
        sc = live.browser.screens.get(dev) if live.browser else None
        if not sc or not sc.shot:
            raise web.HTTPNotFound()
        return web.Response(body=sc.shot, content_type="image/jpeg", headers={"Cache-Control": "no-store"})
    app.router.add_get("/api/screen/{device}.jpg", screen_shot)

    async def browsing(request):                  # pages shown on his screens, newest last
        return web.json_response({"on": bool(live.browser), "log": live.browser.log[-30:] if live.browser else []})
    app.router.add_get("/api/browsing", browsing)
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
        rows = log.read_text().splitlines()[-int(request.query.get("n", "40")):] if log.exists() else []
        world = live.eye.world.top(live.clock.now(), 20) if live.eye else []
        return web.json_response({"frames": [json.loads(r) for r in rows], "world": world})
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
        tasks.append(live.run_browse())
    try:
        await asyncio.gather(*tasks)
    finally:
        live.store.save(live.engine, live.memory)
        if live.browser:
            live.browsing_path.write_text(json.dumps(live.browser.to_dict(), ensure_ascii=False))
            await live.browser.close()


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
