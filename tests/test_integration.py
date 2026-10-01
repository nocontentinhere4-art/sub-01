"""Integration: the whole construct chain on the server side, as the page sees it over the websocket.

bread chat -> the chat candidate wins the workspace -> a speech line with the chat's cid and the buy_bread action accepted
-> life walks from home to the bakery counter (tick.life.route / progress, which the page turns into the fibre road)
-> later carries the bread home (a second walk that ends at the table).
Also: an explicit --start is honoured at time scale 1 (real-time demo at a chosen hour).

    /home/user/sub-01/.venv/bin/python -m pytest tests/test_integration.py -q
"""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import live_server
from live_server import Live
from mind import safe_text
from sleep import Clock


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)

    async def send_str(self, s):
        self.sent.append(json.loads(s))

    def of(self, typ):
        return [m for m in self.sent if m.get("type") == typ]


def test_start_is_honoured_at_real_time_scale():
    c = Clock(1.0, 1_000_000.0)
    assert abs(c.now() - 1_000_000.0) < 5
    assert abs(Clock(1.0).now() - time.time()) < 5              # no start: the real clock (production)


def test_bread_chat_drives_speech_and_the_walk_to_the_bakery_and_home(tmp_path):
    live = Live("mint", True, 1.0, tmp_path, start=live_server.parse_start("10:00"), use_llm=False)
    watcher = FakeWS()
    live.clients.add(watcher)
    live.limiter.last.clear()
    asyncio.run(live.handle_chat(FakeWS(), "k", "ho fame, vai a comprare il pane", "Anna"))
    chats = watcher.of("chat")
    assert chats and chats[0]["cid"].startswith("chat:") and chats[0]["regions"]
    cid = chats[0]["cid"]

    walks = []                                                   # [(route tuple, [progress...])]
    DT = 0.5

    async def go():
        for step in range(1200):                                 # 10 sim minutes at most
            live.clock.sim0 += DT
            t = live.clock.now()
            live.life.update(t, DT, DT, live.engine.stage, live.rel or {}, 0.0, live.engine.pressure(t))
            if step % 4 == 0:                                    # the workspace cycles every ~2 s
                await live.mind_step()
            s = live.life.snapshot()
            if s.get("walking") and s.get("route"):
                r = tuple(s["route"])
                if not walks or walks[-1][0] != r:
                    walks.append((r, []))
                walks[-1][1].append(s["progress"])
            if len(walks) >= 2 and not s.get("walking"):
                return
    asyncio.run(go())

    speech = [m for m in watcher.of("speech") if m["cid"] == cid]
    assert speech, "the bread message never won the workspace"
    assert speech[0]["action"] and speech[0]["action"]["act"] == "buy_bread" and speech[0]["action"]["ok"] is True
    assert speech[0]["about"] == "bread" and speech[0]["lang"] == "it"
    assert safe_text(speech[0]["text"])

    assert len(walks) >= 2, f"expected a walk to the bakery and one back home, got {[w[0] for w in walks]}"
    out_route, out_prog = walks[0]
    assert out_route[-1] == "counter" and "bakery_door" in out_route and "door_out" in out_route
    assert out_prog[-1] > 0.6 and all(b >= a - 1e-9 for a, b in zip(out_prog, out_prog[1:]))   # progress only moves forward
    back_route, back_prog = walks[1]
    assert back_route[0] == "counter" and back_route[-1] == "table"
    assert back_prog[-1] > 0.6
    assert live.life.snapshot()["place"] == "table"
