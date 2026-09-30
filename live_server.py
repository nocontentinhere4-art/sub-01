"""SUB-01 live: runs the whole-brain model in real time and feeds it Solana trades.

    python live_server.py --mint <token mint>   # real pump.fun / PumpSwap trades
    python live_server.py --demo                                         # synthetic trades

Buys drive the reward + visual regions, sells drive salience + amygdala, large
trades hit the thalamus + attention network. Page on http://localhost:8765.
"""
import argparse
import asyncio
import base64
import struct
import json
import math
import random
import time
from pathlib import Path

import aiohttp
import numpy as np
from aiohttp import web

from brain_sim import Brain

HERE = Path(__file__).parent
TICK = 0.05                     # seconds of simulated time per broadcast (real time)
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
    def __init__(self, mint, demo):
        self.brain = Brain()
        self.mint, self.demo = mint, demo
        self.sol_usd = 150.0
        self.clients = set()
        self.pending = []           # trades waiting to be played into the brain
        self.seen = set()
        self.pool_name = "demo" if demo else mint[:6]
        self.stats = {"buys": 0, "sells": 0, "usd": 0.0}

    # --- trades -> stimuli ---------------------------------------------------
    def apply(self, tr):
        s = min(15.0, 2.0 + 3.0 * math.log10(1.0 + tr["usd"]))
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
            b.stimulate("relay", 10)
            b.stimulate("attention", 8)
        self.stats["usd"] += tr["usd"]

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

    # --- simulation loop -------------------------------------------------------
    async def run_brain(self):
        b = self.brain
        steps = int(TICK / b.dt)
        gidx = {k: v for k, v in b.group_idx.items() if v}
        next_t = time.time()
        while True:
            now = time.time()
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
                   "groups": {k: round(float(act[i].mean()), 3) for k, i in gidx.items()},
                   "sync": round(st["sync"], 3), "stats": self.stats,
                   "trades": [{k: t[k] for k in ("kind", "usd", "tx", "who")} for t in due],
                   "pool": self.pool_name}
            data = json.dumps(msg)
            for ws in list(self.clients):
                try:
                    await ws.send_str(data)
                except Exception:
                    self.clients.discard(ws)
            next_t += TICK
            await asyncio.sleep(max(0.0, next_t - time.time()))

    # --- http ----------------------------------------------------------------
    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20)
        await ws.prepare(request)
        self.clients.add(ws)
        async for _ in ws:
            pass
        self.clients.discard(ws)
        return ws


async def main(args):
    live = Live(args.mint, args.demo)
    app = web.Application(client_max_size=64 * 1024 ** 2)
    app.router.add_get("/ws", live.ws_handler)

    async def snap(request):                      # save a canvas capture posted by the page (local only)
        name = Path(request.query.get("name", "snap")).name
        ext = request.query.get("ext", "png") if request.query.get("ext") in ("png", "webm", "mp4") else "png"
        (HERE / "out" / f"{name}.{ext}").write_bytes(await request.read())
        return web.Response(text="ok")
    app.router.add_post("/snap", snap)
    app.router.add_get("/", lambda r: web.FileResponse(HERE / "web" / "index.html"))
    app.router.add_static("/", HERE / "web")
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", args.port).start()
    print(f"SUB-01 live on http://localhost:{args.port}  ({'demo' if args.demo else args.mint})")
    tasks = [live.run_brain(), live.demo_trades() if args.demo else live.rpc_trades()]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mint", default="6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--port", type=int, default=8765)
    asyncio.run(main(p.parse_args()))
