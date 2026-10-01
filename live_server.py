"""SUB-01 live: runs the whole-brain model in real time and feeds it Solana trades and chat messages.

    python live_server.py --mint <token mint>   # real pump.fun / PumpSwap trades
    python live_server.py --demo                                         # synthetic trades
    python live_server.py --demo --time-scale 60 --start 23:55           # one sim hour per real minute

Buys drive the reward + visual regions, sells drive salience + amygdala, large
trades hit the thalamus + attention network. Chat messages are stimuli (see chat.py).
A sleep circuit on the local Asia/Tokyo clock (sleep.py, SUB01_TZ) changes the rhythm and how much
any stimulus gets through; during REM, stored messages are replayed. Page on http://localhost:8765.

The brain model is chosen with --model twin|sl (env SUB01_MODEL, default twin: twin/model.py; sl: the old
Stuart-Landau model in brain_sim.py). Around it run the v2 twin components (docs/twin_report.md): neuromodulators
(twin/neurochem.py) that set a per-region gain, a small body (twin/body.py) that feeds hunger and heart rate back,
and toy plasticity with one memory a night (twin/plasticity.py). This is a digital twin model of one real person's
brain structure and recorded activity; not a mind, not conscious, not the person.
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
from collections import deque
from datetime import datetime
from pathlib import Path

import aiohttp
import numpy as np
from aiohttp import web

from brain_sim import make_brain
from chat import RULES, Dedupe, RateLimiter, check as chat_check, dedupe_key, stimulus as chat_stimulus
from sleep import ROME, Clock, Memory, SleepEngine, Store, hhmm
from eye import Eye, load_env, market_mood
from real_baseline import RealBaseline
from life import WORLD, Life
from twin.body import Body
from twin.neurochem import Neuromodulators
from twin.plasticity import Plasticity

HERE = Path(__file__).parent
TICK = 0.05                     # seconds of simulated time per broadcast (real time)
BASELINE_DRIVE = 1.6            # excitability per z-unit of the recorded resting-state signal
SAVE_S = 60                     # persist sleep state + memory every minute (real time)
REPLAY_AMP = 0.35               # replayed stimulus pattern, relative to the original message
STIM_TAU = 2.0                  # s, decay of brain.stimulate() drive (brain_sim.Brain and twin.model.TwinBrain)
PROBE_S = 2.0                   # model seconds before / after a chat message used to measure the brain response
PROBE_TICKS = int(PROBE_S / TICK)   # ticks of model time in a probe window
PROBE_REGIONS = 8               # regions recorded as "the response" of one message (largest activity increase)
BODY_EVERY_S = 1.0              # the body is stepped when this much sim time has accumulated (one call can be ~180 s)
HEBB_EVERY_S = 5.0              # plasticity.hebbian() is called with the activity averaged over this much sim time
WEIGHTS_EVERY_S = 60.0          # brain.set_weights(plasticity.W) at most once per sim minute ...
WEIGHTS_MIN_TICKS = 40          # ... and at most once per 2 s of real time
MEMORY_TEXT_MAX = 80            # characters of a memory's message shown in the tick message
TWIN_SCORE = HERE / "web" / "twin_score.json"
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


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


class Live:
    def __init__(self, mint, demo, time_scale=1.0, data_dir=HERE / "data", start=None, trust_proxy=False, model=None):
        self.model = (model or os.environ.get("SUB01_MODEL", "twin")).strip().lower()
        self.brain = make_brain(self.model)
        self.mint, self.demo = mint, demo
        self.trust_proxy = trust_proxy
        self.data_dir = Path(data_dir)
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
        life_state = json.loads(life_path.read_text()) if life_path.exists() else None
        # --- v2 twin components (docs/twin_contracts.md); their state lives in the data dir, never in out/ -----------
        self.twin_path = self.data_dir / "twin_state.json"
        tstate = load_json(self.twin_path, {})
        self.neuro = Neuromodulators(state=tstate.get("neuro"))
        self.body = Body(tstate.get("body") or (life_state or {}).get("body"))
        W0 = getattr(self.brain, "W0", self.brain.W)
        pdir = self.data_dir if self.model == "twin" else self.data_dir / self.model     # weights belong to one model
        self.plast = Plasticity(W0, pdir, names=self.brain.names)
        # plasticity only where the brain uses the weights (TwinBrain.set_weights); the old model has no such hook, so
        # with --model sl no Hebbian drift and no "memory" (a weight change the model would never see) is reported
        self.plastic = hasattr(self.brain, "set_weights")
        self.consolidated_day = tstate.get("consolidated_day")      # night (date) that already had its REM consolidation
        self.score = self.load_score(self.model)
        self.memories = self.load_memories()
        if hasattr(self.brain, "set_weights") and self.plast.drift()["rel_frobenius"] > 0:
            self.brain.set_weights(self.plast.W)                    # resume with the weights learned so far
        self.life = Life(life_state, body=self.body)
        self.time_scale = time_scale
        self.life.time_scale = time_scale
        self.baseline = None             # set by main() unless --no-real-baseline (optional: "replaying a real session")
        self.eye_every = 90.0            # seconds between eye frames while awake (--eye-every)
        self.recent_trades = []          # (t, kind, usd) for the eye's market mood
        self.recent_replays = []         # REM replays for the eye's dreams
        self.last_groups = {}
        self.last_frame = None
        # tick state
        self.steps = int(TICK / self.brain.dt)                  # integration steps per tick
        self.gidx = {k: v for k, v in self.brain.group_idx.items() if v}
        self.n_ticks = 0
        self.last_sim_t = None
        self.last_amyg = 0.0             # amygdala activity excess over its resting level (previous tick)
        self.act_hist = deque(maxlen=PROBE_TICKS)      # last 2 model seconds of per-region activity
        self.probes = []                 # accepted chat messages whose brain response is being measured
        self.body_acc = 0.0              # sim seconds not yet given to the body
        self.heb_acc, self.heb_dt, self.heb_n = None, 0.0, 0
        self.w_dirty, self.w_last_t, self.w_last_tick = False, None, 0
        self.drift = self.plast.drift()
        self.perf = {"ticks": 0, "tick_s": 0.0, "model_s": 0.0}     # thread CPU seconds, see /api/perf

    # --- twin state ---------------------------------------------------------------
    @staticmethod
    def load_score(model="twin"):
        """web/twin_score.json -> the few numbers and the honest label shown on the pages.

        The held-out score belongs to the model that runs: the twin's numbers for --model twin, the old
        Stuart-Landau model's own held-out numbers (baselines.old_model) for --model sl, never the twin's."""
        d = load_json(TWIN_SCORE, {})
        h, base = d.get("heldout", {}), d.get("baselines", {})
        out = {"label": d.get("label", ""), "fc_r": h.get("fc_r"), "fcd_ks": h.get("fcd_ks"),
               "n_runs": h.get("n_runs"), "ceiling_r": base.get("test_retest_ceiling_r")}
        if model == "sl":
            old = base.get("old_model", {})
            out |= {"label": "old Stuart-Landau model vs recorded resting-state fMRI (held-out sessions): "
                             "no static match, no FC-dynamics match",
                    "fc_r": old.get("fc_r"), "fcd_ks": old.get("fcd_ks")}
        return out

    def load_memories(self):
        mem = load_json(self.plast.memories_path, [])
        return mem if isinstance(mem, list) else []

    def save_twin(self):
        """Persist neuromodulators, body and plasticity (weights.npz) in the data dir."""
        Store._write(self.twin_path, {"neuro": self.neuro.to_dict(), "body": self.body.to_dict(),
                                      "consolidated_day": self.consolidated_day})
        self.plast.save()

    def twin_snapshot(self, levels, st):
        """Small "twin" object for the tick message: score, neuromodulators, vitals, sleep, memories, drift."""
        v = self.body.vitals()
        return {"score": self.score,
                "levels": {k: round(x, 2) for k, x in levels.items()},
                "vitals": v | {"hunger": round(self.body.hunger, 2)},
                "sleep": {"stage": st["stage"], "H": st["H"], "C": st["C"], "pressure": st["pressure"]},
                "memories": {"count": len(self.memories),
                             "last": [{"n": m["n"], "day": m["day"], "message": m["message"][:MEMORY_TEXT_MAX],
                                       "sha256": m["sha256"][:12]} for m in self.memories[-5:]]},
                "drift": {"rel_frobenius": float(f"{self.drift['rel_frobenius']:.3g}"),
                          "edges_changed": self.drift["edges_changed"]}}

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
        self.neuro.on_trade(tr["kind"], tr["usd"], self.clock.now())       # phasic DA (pumps) / NE (dumps, volatility)
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
            await asyncio.sleep(random.expovariate(1.5))
            kind = "buy" if random.random() < 0.55 else "sell"
            usd = math.exp(random.gauss(3.5, 1.6))
            self.pending.append({"kind": kind, "usd": usd, "tx": "", "who": "demo", "at": time.time()})

    # --- chat -> stimuli + memory -----------------------------------------------
    @staticmethod
    def public(m):
        return {"text": m["text"], "t": hhmm(m["t"]), "networks": m["networks"], "emotion": m["emotion"],
                "asleep": m["asleep"], "stage": m["stage"]}

    def accept_chat(self, text, key):
        """Filter, store and play one chat message into the brain. Returns (ok, reason_or_None, memory_item, stimulus_gain)."""
        ok, reason = chat_check(text, key, self.limiter, self.dedupe)      # filter first; blocked = never stored
        if not ok:
            return False, reason, None, 0.0
        text = text.strip()
        t = self.clock.now()
        stim, hits, emotion = chat_stimulus(text)
        gain = self.engine.stimulus(t, "message")
        before = (np.mean(self.act_hist, axis=0) if self.act_hist else np.zeros(self.brain.n))
        for g, a in stim.items():
            self.brain.stimulate(g, a * gain)
        m = self.memory.add(t, text, self.engine.stage, stim, emotion, hits)
        # measure the model's response over the next PROBE_S model seconds (tick() finishes it and records it)
        if self.plastic:
            self.probes.append({"t": t, "text": text, "before": before, "acc": np.zeros(self.brain.n), "k": 0})
        if self.eye:
            self.eye.hear(text, t)
        self.life.hear(text, t)
        return True, None, m, gain

    async def handle_chat(self, ws, key, text):
        ok, reason, m, gain = self.accept_chat(text, key)
        if not ok:
            await ws.send_json({"type": "chat_ack", "ok": False, "reason": reason})
            return
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
    def finish_probes(self, act):
        """Add this tick's activity to every open chat probe; a finished one becomes a recorded response."""
        for pr in self.probes:
            pr["acc"] += act
            pr["k"] += 1
        done = [pr for pr in self.probes if pr["k"] >= PROBE_TICKS]
        for pr in done:
            self.probes.remove(pr)
            inc = pr["acc"] / pr["k"] - pr["before"]              # activity increase over the 2 s after vs the 2 s before
            top = np.argsort(inc)[::-1][:PROBE_REGIONS]
            self.plast.record_response(pr["t"], pr["text"], [int(i) for i in top], float(inc[top].sum()))

    def consolidate_if_due(self, t, events):
        """First REM episode of each night: one memory (plasticity.consolidate), then push the weights to the brain."""
        e = self.engine
        day = (e.night or {}).get("date")
        if e.stage != "REM" or day is None or self.consolidated_day == day:
            return
        self.consolidated_day = day
        rec = self.plast.consolidate(day)
        if rec:
            self.memories = self.load_memories()
            self.w_dirty = True
            self.push_weights(t, force=True)
            events.append({"type": "memory", "t": hhmm(t), "n": rec["n"],
                           "text": f"memory #{rec['n']} consolidated in REM: \u201c{rec['message'][:MEMORY_TEXT_MAX]}\u201d"})
        self.save_twin()

    def push_weights(self, t, force=False):
        """brain.set_weights(plasticity.W): once per sim minute (and not more often than every 2 s of real time)."""
        if not (self.w_dirty and hasattr(self.brain, "set_weights")):
            return
        if not force and (self.n_ticks - self.w_last_tick < WEIGHTS_MIN_TICKS
                          or (self.w_last_t is not None and t - self.w_last_t < WEIGHTS_EVERY_S)):
            return
        self.brain.set_weights(self.plast.W)
        self.w_dirty, self.w_last_t, self.w_last_tick = False, t, self.n_ticks
        self.drift = self.plast.drift()

    def tick(self, now=None):
        """One broadcast step (TICK of model time). Returns the tick message (a dict) and the events of this step."""
        now = time.time() if now is None else now
        cpu0 = time.thread_time()
        b, e = self.brain, self.engine
        self.n_ticks += 1
        t = self.clock.now()
        dt_sim = (t - self.last_sim_t) if self.last_sim_t is not None else TICK * self.time_scale
        self.last_sim_t = t
        dt_sim = max(0.0, dt_sim)
        events = self.sleep_tick()
        levels = self.neuro.update(dt_sim, sleep_levels=e.modulators)       # tonic follows the sleep circuit
        if self.baseline:                                         # optional: replaying a recorded real session as drive
            gain = {"AWAKE": 1.0, "REM": 0.7}.get(e.stage, 0.3)
            b.drive = BASELINE_DRIVE * gain * np.clip(self.baseline.advance(TICK), -2.0, 3.0)
        due = [x for x in self.pending if x["at"] <= now]
        self.pending = [x for x in self.pending if x["at"] > now]
        for tr in due:
            self.apply(tr)
        levels = self.neuro.levels                                # includes the phasic kicks of these trades
        if hasattr(b, "set_gain"):
            b.set_gain(self.neuro.region_gain(levels, n=b.n))
        # body: stepped in sim time (a tick can be ~180 s at --time-scale 3600), feeds back into the insula proxy
        self.body_acc += dt_sim
        if self.body_acc >= BODY_EVERY_S:
            self.body.update(self.body_acc, levels, self.last_amyg, e.stage, exertion=self.life.exertion())
            self.body_acc = 0.0
        for g, v in self.body.intero_drive().items():            # continuous input: v is the steady-state stimulus level
            if self.gidx.get(g):
                b.stimulate(g, v * e.gain * TICK / STIM_TAU)
        cpu_m = time.thread_time()
        acc = np.zeros(b.n)
        for _ in range(self.steps // 5):
            z = b.step(5)
            acc += np.abs(z)
        act = acc / (self.steps // 5)
        self.perf["model_s"] += time.thread_time() - cpu_m
        self.act_hist.append(act)
        self.finish_probes(act)
        # plasticity: Hebbian while awake on the activity averaged over HEBB_EVERY_S of sim time
        if e.stage == "AWAKE" and self.plastic:
            self.heb_acc = act.copy() if self.heb_acc is None else self.heb_acc + act
            self.heb_dt += dt_sim
            self.heb_n += 1
            if self.heb_dt >= HEBB_EVERY_S:
                self.plast.hebbian(self.heb_acc / self.heb_n, self.heb_dt, stage="AWAKE")
                self.heb_acc, self.heb_dt, self.heb_n = None, 0.0, 0
                self.w_dirty = True
        else:
            self.heb_acc, self.heb_dt, self.heb_n = None, 0.0, 0
        if self.plastic:
            self.consolidate_if_due(t, events)
        self.push_weights(t)
        if self.n_ticks % 20 == 1:
            self.drift = self.plast.drift()
        wave = {k: float(z.real[i].mean()) for k, i in self.gidx.items()}
        st = b.state()
        groups = {k: round(float(act[i].mean()), 3) for k, i in self.gidx.items()}
        sleep = self.engine.status()
        msg = {"type": "tick", "act": np.round(act, 3).tolist(), "wave": wave, "groups": groups,
               "sync": round(st["sync"], 3), "stats": self.stats,
               "trades": [{k: x[k] for k in ("kind", "usd", "tx", "who")} for x in due],
               "pool": self.pool_name, "events": events,
               "sleep": sleep | {"burst": round(self.burst, 2)},
               "baseline": self.baseline.status() if self.baseline else None,
               "twin": self.twin_snapshot(levels, sleep)}
        self.last_groups = groups
        base = sum(groups.values()) / max(1, len(groups))
        rel = {k: v / max(base, 1e-6) for k, v in groups.items()}
        self.last_amyg = max(0.0, rel.get("fear", 1.0) - 1.0)
        hot = min(1.0, sum(1 for x in self.recent_trades if now - x[0] < 60) / 10)
        tsim = self.clock.now()
        self.life.update(tsim, TICK, TICK * self.time_scale, self.engine.stage, rel, hot,
                         self.engine.pressure(tsim))
        msg["life"] = self.life.snapshot()
        self.perf["ticks"] += 1
        self.perf["tick_s"] += time.thread_time() - cpu0
        return msg, events

    async def run_brain(self):
        next_t = last_save = time.time()
        while True:
            now = time.time()
            msg, events = self.tick(now)
            await self.broadcast(msg)
            if events:
                await self.broadcast(self.nights())
            if now - last_save >= SAVE_S:
                self.store.save(self.engine, self.memory)
                self.life_path.write_text(json.dumps(self.life.to_dict()))
                self.save_twin()
                last_save = now
            next_t += TICK
            await asyncio.sleep(max(0.0, next_t - time.time()))

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
                                                 self.life.snapshot()["doing"])
                self.last_frame = rec
                await self.broadcast({"type": "eye", **rec})
            except Exception as e:                                    # never let the eye stop the brain
                print("eye error:", repr(e), flush=True)
                await asyncio.sleep(10)
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
    """'HH:MM' -> sim epoch of that local (SUB01_TZ) time today."""
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
    live = Live(args.mint, args.demo, args.time_scale, data_dir,
                parse_start(args.start) if args.start else None, args.trust_proxy, args.model)
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
        load_env(HERE / ".env")                   # REPLICATE_API_TOKEN -> images in the cloud, not on this Mac
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
    if args.host in ("127.0.0.1", "localhost"):                   # local-only: CPU seconds of the loop (twin/measure_cpu_live.py)
        app.router.add_get("/api/perf", lambda r: web.json_response(live.perf | {"model": live.model}))

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
    app.router.add_get("/", lambda r: web.FileResponse(HERE / "web" / "life.html"))       # the life is the front page
    app.router.add_get("/brain", lambda r: web.FileResponse(HERE / "web" / "index.html"))
    app.router.add_static("/", HERE / "web")
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, args.host, args.port).start()
    print(f"SUB-01 live on http://localhost:{args.port}  ({'demo' if args.demo else args.mint}, "
          f"time x{args.time_scale:g}, model {live.model}, state in {data_dir})", flush=True)
    tasks = [live.run_brain(), live.demo_trades() if args.demo else live.rpc_trades()]
    if live.eye:
        tasks.append(live.run_eye())
    try:
        await asyncio.gather(*tasks)
    finally:
        live.store.save(live.engine, live.memory)
        live.save_twin()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mint", default=os.environ.get("MINT", "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx"))
    p.add_argument("--demo", action="store_true")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--frames-dir", help="where eye frames are written (default out/eye/frames)")
    p.add_argument("--time-scale", type=float, default=1.0, help="sim seconds per real second (60: 1 h per minute)")
    p.add_argument("--start", help="local (SUB01_TZ) time HH:MM to start the (accelerated) clock at, e.g. 23:55")
    p.add_argument("--data-dir", help="state + nights directory (default data/, or data/demo when accelerated)")
    p.add_argument("--eye-every", type=float, default=90.0, help="seconds between eye frames while awake")
    p.add_argument("--model", choices=("twin", "sl"), default=None,
                   help="brain model: twin (twin/model.py, default) or sl (old Stuart-Landau); env SUB01_MODEL")
    p.add_argument("--no-real-baseline", action="store_true", help="simulated background only")
    p.add_argument("--eye", action="store_true", help="generate what SUB-01 'sees' (local image + language models)")
    p.add_argument("--trust-proxy", action="store_true", help="rate-limit by X-Forwarded-For (behind a reverse proxy)")
    asyncio.run(main(p.parse_args()))
