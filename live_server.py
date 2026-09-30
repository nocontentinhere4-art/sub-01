"""SUB-01 live: runs the whole-brain model in real time and feeds it Solana trades and chat messages.

    python live_server.py --mint <token mint>   # real pump.fun / PumpSwap trades
    python live_server.py --demo                                         # synthetic trades
    python live_server.py --demo --time-scale 60 --start 23:55           # one sim hour per real minute

Buys drive the reward + visual regions, sells drive salience + amygdala, large
trades hit the thalamus + attention network. Chat messages are stimuli (see chat.py).
A sleep/wake cycle on the Europe/Rome clock (sleep.py) changes the rhythm and how much
any stimulus gets through; during REM, stored messages are replayed. Page on http://localhost:8765.
"""
import argparse
import asyncio
import base64
import struct
from collections import deque
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
from chat import (REGION_RULES, RULES, Dedupe, RateLimiter, check as chat_check, check_nick, dedupe_key,
                  stimulus as chat_stimulus, topical_networks)
from sleep import (REPLAY_MEAN_S, ROME, TRANSITION_REAL_S, TRANSITION_S, Clock, Memory, SleepEngine, Store, hhmm,
                   lerp, stamp)
from eye import Eye, ReplicateLLM, load_env, market_mood
from real_baseline import RealBaseline
from life import ACTIVITIES, WORLD, Life
from mind import DiaryStore, Mind, safe_text

HERE = Path(__file__).parent
TICK = 0.05                     # seconds of simulated time per broadcast (real time)
BASELINE_DRIVE = 1.6            # excitability per z-unit of the recorded resting-state signal
SAVE_S = 60                     # persist sleep state + memory every minute (real time)
REPLAY_AMP = 0.35               # replayed stimulus pattern, relative to the original message
MIND_EVERY = 2.0                # seconds (real) between workspace cycles
NICKS_CAP = 5000                # remembered nicknames (oldest last-seen dropped)
FORCED_REPLAY_S = (4.0, 8.0)    # --force-stage REM: real seconds between replays (for screenshots)
RPC_WS = "wss://api.mainnet-beta.solana.com"
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
    def __init__(self, mint, demo, time_scale=1.0, data_dir=HERE / "data", start=None, trust_proxy=False,
                 life_activity=None, force_market=None, force_stage=None, use_llm=True):
        self.brain = Brain()
        self.force_market, self.force_stage = force_market, force_stage      # demo-only (checked in the CLI)
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
        life_path = Path(data_dir) / "life.json"
        self.life_path = life_path
        self.life = Life(json.loads(life_path.read_text()) if life_path.exists() else None)
        self.forced_activity = life_activity
        if life_activity:                                            # demo-only: force the first activity
            self.life.start(life_activity, self.clock.now(), "demo: " + life_activity)
        self.time_scale = time_scale
        self.data_dir = Path(data_dir)
        # the workspace (mind.py): state + diary persist with the rest; the language model is optional
        self.mind_path = self.data_dir / "mind.json"
        try:
            mind_state = json.loads(self.mind_path.read_text()) if self.mind_path.exists() else None
        except (ValueError, OSError):
            mind_state = None
        token = os.environ.get("REPLICATE_API_TOKEN") if use_llm else None
        self.mind = Mind(mind_state, llm=ReplicateLLM(token).ask if token else None, store=DiaryStore(data_dir),
                         auto_flush=False)
        self.last_mind = None            # last 'mind' message (sent in hello)
        self.last_market = "calm"
        self.rel = {}
        self._pend_obj = self._pend_cid = None
        self.nicks_path = self.data_dir / "nicks.json"
        try:
            self.nicks = json.loads(self.nicks_path.read_text()) if self.nicks_path.exists() else {}
        except (ValueError, OSError):
            self.nicks = {}
        self.nick_index = {k.casefold(): k for k in self.nicks}
        self.tick_ms = deque(maxlen=2400)         # compute time per tick (ms), for /api/perf
        self.mind_ms = deque(maxlen=600)
        self.llm_calls = 0
        self.baseline = None             # set by main() unless --no-real-baseline
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
            while True:
                try:
                    async with http.ws_connect(RPC_WS, heartbeat=30) as ws:
                        await ws.send_json({"jsonrpc": "2.0", "id": 1, "method": "logsSubscribe",
                                            "params": [{"mentions": [self.mint]}, {"commitment": "confirmed"}]})
                        async for m in ws:
                            v = json.loads(m.data).get("params", {}).get("result", {}).get("value")
                            if not v or v.get("err"):
                                continue
                            for tr in decode_trades(v["logs"]):
                                tr["usd"] = tr.pop("sol") * self.sol_usd
                                tr["tx"], tr["who"], tr["at"] = v["signature"], "", time.time()
                                self.pending.append(tr)
                except Exception as e:
                    print("rpc stream error, reconnecting:", e, flush=True)
                    await asyncio.sleep(2)

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
            await asyncio.sleep(random.expovariate(3.0 if self.force_market else 1.5))
            kind = "buy" if random.random() < 0.55 else "sell"
            usd = math.exp(random.gauss(3.5, 1.6))
            if self.force_market:                     # --force-market: strongly biased, so market_mood reads it
                kind = "buy" if self.force_market == "pump" else "sell"
                if random.random() < 0.08:
                    kind = "sell" if kind == "buy" else "buy"
                usd = math.exp(random.gauss(4.6, 0.8))
            self.pending.append({"kind": kind, "usd": usd, "tx": "", "who": "demo", "at": time.time()})

    # --- chat -> stimuli + memory -----------------------------------------------
    @staticmethod
    def public(m):
        out = {"text": m["text"], "t": hhmm(m["t"]), "networks": m["networks"], "emotion": m["emotion"],
               "asleep": m["asleep"], "stage": m["stage"]}
        if m.get("nick"):
            out["nick"] = m["nick"]
        return out

    def regions_of(self, networks):
        """Brain region indices (= index into tick.act = web/brain.json nodes) of the given networks, sorted."""
        idx = set()
        for g in networks:
            idx.update(self.brain.group_idx.get(g, ()))
        return sorted(idx)

    def remember_nick(self, nick):
        """-> returning? Keeps {nick: {first, last, count}} (real epoch seconds, no IPs)."""
        if not nick:
            return False
        now = int(time.time())
        key = self.nick_index.get(nick.casefold())
        if key is None:
            if len(self.nicks) >= NICKS_CAP:
                old = min(self.nicks, key=lambda k: self.nicks[k]["last"])
                self.nicks.pop(old)
                self.nick_index.pop(old.casefold(), None)
            self.nicks[nick] = {"first": now, "last": now, "count": 1}
            self.nick_index[nick.casefold()] = nick
            return False
        e = self.nicks[key]
        e["last"], e["count"] = now, e["count"] + 1
        return True

    def save_nicks(self):
        tmp = self.nicks_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.nicks, ensure_ascii=False))
        tmp.replace(self.nicks_path)

    async def handle_chat(self, ws, key, text, nick=""):
        nick = " ".join(nick.split()) if isinstance(nick, str) else nick
        ok, reason = check_nick(nick)                                      # nickname: same filter as the text
        if ok and nick and not safe_text(nick):
            ok, reason = False, "nickname: not allowed"
        if not ok:
            await ws.send_json({"type": "chat_ack", "ok": False, "reason": reason})
            return
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
        regions = self.regions_of(topical_networks(text))
        m = self.memory.add(t, text, self.engine.stage, stim, emotion, hits)
        if nick:
            m["nick"] = nick
        if self.eye:
            self.eye.hear(text, t)
        self.life.hear(text, t)
        returning = self.remember_nick(nick)
        cid = self.mind.hear({"text": text, "nick": nick, "networks": hits, "regions": regions, "emotion": emotion,
                              "stage": self.engine.stage}, t)
        await ws.send_json({"type": "chat_ack", "ok": True, "cid": cid})
        await self.broadcast({"type": "chat", "gain": round(gain, 2), "cid": cid, "nick": nick or None,
                              "returning": returning, "regions": regions, **self.public(m)})

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

    def forced_sleep(self, t):
        """--force-stage (demo only): hold the engine in NREM or REM for screenshots instead of the real night."""
        e = self.engine
        dt = max(0.0, t - e.t)
        e.t = t
        e.asleep, e.stage, e.arousal = True, self.force_stage, 0.0
        e.depth = 0.7 if self.force_stage == "NREM" else 0.0
        if e.night is None:
            e.open_night(t)
        if e.night["sleep_onset"] is None:
            e.night["sleep_onset"] = stamp(t)
        if e.onset is None:
            e.onset = t
        e.params = lerp(e.params, e.stage_params(), 1 - math.exp(-min(dt / TRANSITION_S, TICK / TRANSITION_REAL_S)))
        ev = []
        if self.force_stage == "REM":
            if e.next_replay is None:
                e.next_replay = time.time() + random.uniform(*FORCED_REPLAY_S)
            elif time.time() >= e.next_replay:
                e.next_replay = time.time() + random.uniform(*FORCED_REPLAY_S)
                ev.append({"type": "replay", "text": "replay"})
        return ev

    def sleep_tick(self):
        """Advance the sleep engine, apply its parameters to the model, run REM replays and bursts."""
        b, e = self.brain, self.engine
        t = self.clock.now()
        out = []
        for ev in (self.forced_sleep(t) if self.force_stage else e.update(t, dt_real=TICK)):
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
            t_start = time.perf_counter()
            events = self.sleep_tick()
            if self.baseline:                                         # his recorded activity drives excitability
                gain = {"AWAKE": 1.0, "REM": 0.7}.get(self.engine.stage, 0.3)
                b.drive = BASELINE_DRIVE * gain * np.clip(self.baseline.advance(TICK), -2.0, 3.0)
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
                   "baseline": self.baseline.status() if self.baseline else None}
            self.last_groups = groups
            base = sum(groups.values()) / max(1, len(groups))
            rel = self.rel = {k: v / max(base, 1e-6) for k, v in groups.items()}
            self.last_market = msg["market"] = market_mood(self.recent_trades)
            hot = min(1.0, sum(1 for x in self.recent_trades if now - x[0] < 60) / 10)
            tsim = self.clock.now()
            self.life.update(tsim, TICK, TICK * self.time_scale, self.engine.stage, rel, hot,
                             self.engine.pressure(tsim))
            msg["life"] = self.life.snapshot()
            await self.broadcast(msg)
            if events:
                await self.broadcast(self.nights())
            if now - last_save >= SAVE_S:
                self.save_all()
                last_save = now
            self.tick_ms.append((time.perf_counter() - t_start) * 1000)
            next_t += TICK
            await asyncio.sleep(max(0.0, next_t - time.time()))

    def save_all(self):
        """Persist sleep state + memory, the life, the workspace state + diary and the nickname table."""
        self.store.save(self.engine, self.memory)
        self.life_path.write_text(json.dumps(self.life.to_dict()))
        tmp = self.mind_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.mind.to_dict(), ensure_ascii=False))
        tmp.replace(self.mind_path)
        self.mind.flush()                                       # data/diary/YYYY-MM-DD.json (small, once a minute)
        self.save_nicks()

    # --- the workspace (mind.py) ----------------------------------------------------
    def mind_ctx(self, t):
        snap = self.life.snapshot()
        return {"stage": self.engine.stage, "rel": self.rel,
                "needs": {"hunger": self.life.hunger, "boredom": self.life.boredom, "energy": self.life.energy},
                "life": snap, "market": self.last_market, "replays": list(self.recent_replays),
                "memories": self.memory.items[-200:], "viewers": len(self.clients)}

    async def mind_step(self):
        """One workspace cycle (~2 s): broadcast 'mind', run the winner's proposed action through life.request and
        pass the answer back, then emit the inner-speech line (language model only with viewers, off the loop)."""
        t = self.clock.now()
        t0 = time.perf_counter()
        msg = self.mind.cycle(t, self.mind_ctx(t))
        self.last_mind = msg
        b = msg["broadcast"]
        if b and b["action"]:
            if self.forced_activity and (self.life.activity != self.forced_activity
                                         or (not self.life.path and t >= self.life.until)):
                self.forced_activity = None                          # the forced demo activity is over
            if self.forced_activity:                                 # demo: let the forced activity run its course
                ok, why = False, "busy: already doing that"
            else:
                ok, why = self.life.request(b["action"]["act"], t, b["action"]["reason"])
            self.mind.outcome(b["action"]["act"], ok, why, t)
        if self.mind.pending is not self._pend_obj:                # a new line was queued: it belongs to this winner
            self._pend_obj, self._pend_cid = self.mind.pending, msg["winner"]
        req = self.mind.llm_request()
        self.mind_ms.append((time.perf_counter() - t0) * 1000)
        await self.broadcast(msg)
        if req:
            asyncio.get_running_loop().create_task(self.run_llm(req))
        await self.send_speech(t)

    async def send_speech(self, t):
        sp = self.mind.speech_due()
        if sp:
            cid = self._pend_cid if self._pend_cid and self._pend_cid.startswith("chat:") else None
            await self.broadcast({"type": "speech", **sp, "cid": cid, "t": hhmm(t)})
            self._pend_obj = self._pend_cid = None

    async def run_llm(self, req):
        self.llm_calls += 1
        text = await asyncio.get_running_loop().run_in_executor(None, self.mind.run_llm, req)
        self.mind.llm_result(req["id"], text)                    # used only if it passes safe_llm_text

    async def run_mind(self):
        next_t = time.time() + MIND_EVERY
        while True:
            await asyncio.sleep(max(0.0, next_t - time.time()))
            next_t = time.time() + MIND_EVERY
            try:
                await self.mind_step()
            except Exception as e:                                   # never let the workspace stop the brain
                print("mind error:", repr(e), flush=True)
            for _ in range(int(MIND_EVERY / 0.5) - 1):               # a line held for the language model goes out
                await asyncio.sleep(0.5)                             # as soon as it is ready or its wait is over
                try:
                    await self.send_speech(self.clock.now())
                except Exception as e:
                    print("speech error:", repr(e), flush=True)

    # --- the eye: what SUB-01 "sees" ----------------------------------------------
    async def run_eye(self):
        loop = asyncio.get_running_loop()
        while True:
            if not self.clients:                                      # nobody watching: don't spend GPU (and heat)
                await asyncio.sleep(5)
                continue
            stage = self.engine.stage
            t = self.clock.now()
            if stage == "AWAKE" and self.recent_replays:
                self.recent_replays = []                              # dreams end when it wakes up
            try:
                rec = await loop.run_in_executor(None, self.eye.step, t, stage, self.last_groups,
                                                 market_mood(self.recent_trades), list(self.recent_replays), hhmm(t),
                                                 self._eye_doing())
                self.last_frame = rec
                await self.broadcast({"type": "eye", **rec})
            except Exception as e:                                    # never let the eye stop the brain
                print("eye error:", repr(e), flush=True)
                await asyncio.sleep(10)
            await asyncio.sleep(self.eye_every * {"AWAKE": 1.0, "REM": 0.75}.get(stage, 3.0))

    def _eye_doing(self):
        focus = self.mind.focus()                                 # what currently holds the workspace (extra context)
        doing = self.life.snapshot()["doing"]
        return f"{doing}; {focus}" if focus else doing

    # --- http ----------------------------------------------------------------
    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
        await ws.prepare(request)
        # rate-limit key; kept only in memory for this connection and the 10 s limiter window
        key = request.remote
        if self.trust_proxy and request.headers.get("X-Forwarded-For"):
            key = request.headers["X-Forwarded-For"].split(",")[0].strip()
        await ws.send_json({"type": "hello", "chat": [self.public(m) for m in self.memory.items[-30:]],
                            "rules": [[cond, list(groups)] for cond, groups in RULES], "world": WORLD,
                            "regions": {g: list(i) for g, i in self.brain.group_idx.items() if i},
                            "region_rules": [{"topic": r["topic"], "networks": list(r["networks"]),
                                              "words": list(r.get("kw") or r.get("first"))} for r in REGION_RULES],
                            "mind": self.last_mind, "market": self.last_market})
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
                nick = d.get("nick")
                await self.handle_chat(ws, key, d["text"], "" if nick is None else nick)
        self.clients.discard(ws)
        return ws


def parse_start(hm):
    """'HH:MM' -> sim epoch of that Rome time today."""
    h, m = map(int, hm.split(":"))
    return datetime.now(ROME).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


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
    if args.eye:
        load_env(HERE / ".env")                   # REPLICATE_API_TOKEN: read before the workspace picks its language model
    live = Live(args.mint, args.demo, args.time_scale, data_dir,
                parse_start(args.start) if args.start else None, args.trust_proxy,
                args.life_activity, {"pump": "pump", "dump": "dump"}.get(args.force_market), args.force_stage,
                not args.no_llm)
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
    if not args.no_real_baseline and list((HERE / "out" / "rest").glob("*.npz")):
        live.baseline = RealBaseline(live.brain.names, HERE / "out" / "rest")
    if args.eye:
        frames_dir = Path(args.frames_dir) if args.frames_dir else HERE / "out" / "eye" / "frames"
        live.eye = Eye(frames_dir, data_dir / "world.json", width=640, height=360, steps=6)
        live.eye_every = args.eye_every
        app.router.add_static("/eye", frames_dir)

    async def frames(request):                    # recent eye frames for the world page
        log = live.eye.log if live.eye else HERE / "missing"
        rows = log.read_text().splitlines()[-int(request.query.get("n", "40")):] if log.exists() else []
        world = live.eye.world.top(live.clock.now(), 20) if live.eye else []
        return web.json_response({"frames": [json.loads(r) for r in rows], "world": world})
    app.router.add_get("/api/frames", frames)

    async def perf(request):                      # compute time per tick / per workspace cycle (budget: 50 ms / 5 ms)
        def stats(d):
            v = sorted(d)
            if not v:
                return None
            return {"n": len(v), "mean_ms": round(sum(v) / len(v), 2), "p95_ms": round(v[int(0.95 * (len(v) - 1))], 2),
                    "max_ms": round(v[-1], 2)}
        return web.json_response({"tick": stats(live.tick_ms), "mind": stats(live.mind_ms),
                                  "clients": len(live.clients), "llm_calls": live.llm_calls})
    app.router.add_get("/api/perf", perf)
    app.router.add_get("/", lambda r: web.FileResponse(HERE / "web" / "life.html"))       # the life is the front page
    app.router.add_get("/brain", lambda r: web.FileResponse(HERE / "web" / "index.html"))
    app.router.add_static("/", HERE / "web")
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, args.host, args.port).start()
    print(f"SUB-01 live on http://localhost:{args.port}  ({'demo' if args.demo else args.mint}, "
          f"time x{args.time_scale:g}, state in {data_dir})", flush=True)
    tasks = [live.run_brain(), live.run_mind(), live.demo_trades() if args.demo else live.rpc_trades()]
    if live.eye:
        tasks.append(live.run_eye())
    try:
        await asyncio.gather(*tasks)
    finally:
        live.save_all()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mint", default=os.environ.get("MINT", "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx"))
    p.add_argument("--demo", action="store_true")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--frames-dir", help="where eye frames are written (default out/eye/frames)")
    p.add_argument("--time-scale", type=float, default=1.0, help="sim seconds per real second (60: 1 h per minute)")
    p.add_argument("--start", help="Rome time HH:MM to start the (accelerated) clock at, e.g. 23:55")
    p.add_argument("--data-dir", help="state + nights directory (default data/, or data/demo when accelerated)")
    p.add_argument("--eye-every", type=float, default=90.0, help="seconds between eye frames while awake")
    p.add_argument("--no-real-baseline", action="store_true", help="simulated background only")
    p.add_argument("--eye", action="store_true", help="generate what SUB-01 'sees' (local image + language models)")
    p.add_argument("--life-activity", choices=sorted(ACTIVITIES), help="demo only: force the first activity "
                   "(e.g. buy_bread: it walks to the bakery)")
    p.add_argument("--force-market", choices=["pump", "dump"], help="demo only: biased demo trades so the market "
                   "mood reads pumping / dumping")
    p.add_argument("--force-stage", choices=["NREM", "REM"], help="demo only: hold the sleep engine in that stage")
    p.add_argument("--no-llm", action="store_true", help="never call a language model for inner speech")
    p.add_argument("--trust-proxy", action="store_true", help="rate-limit by X-Forwarded-For (behind a reverse proxy)")
    a = p.parse_args()
    for flag in ("life_activity", "force_market", "force_stage"):
        if getattr(a, flag) and not a.demo:
            p.error(f"--{flag.replace('_', '-')} is demo-only: it needs --demo")
    asyncio.run(main(a))
