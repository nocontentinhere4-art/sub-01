"""Server-level tests: chat handling (nick checks, returning nicknames, message fields), the workspace speech id,
the demo-only flags and the save / restore round trip.

    /home/user/sub-01/.venv/bin/python -m pytest tests/test_server.py -q
"""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

import live_server
from live_server import Live


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, m):
        self.sent.append(m)

    async def send_str(self, s):
        self.sent.append(json.loads(s))

    def of(self, typ):
        return [m for m in self.sent if m.get("type") == typ]


def make(tmp_path, **kw):
    return Live("mint", True, 60.0, tmp_path, use_llm=False, **kw)


def run(coro):
    return asyncio.run(coro)


def chat(live, ws, text, nick="", key="k"):
    live.limiter.last.clear()
    return live.handle_chat(ws, key, text, nick)


def test_bad_nick_is_rejected_and_nothing_is_broadcast(tmp_path):
    live = make(tmp_path)
    me, other = FakeWS(), FakeWS()
    live.clients.add(other)
    for bad in ("SUB-01", "ЅUB-01", "Sub-O1", "x" * 21, "a@b", "admin"):
        run(chat(live, me, "hello there", bad))
    acks = me.of("chat_ack")
    assert len(acks) == 6 and not any(a["ok"] for a in acks) and all(a["reason"] for a in acks)
    assert other.sent == [] and live.nicks == {} and live.memory.items == []


def test_accepted_chat_carries_the_contract_fields(tmp_path):
    live = make(tmp_path)
    me, other = FakeWS(), FakeWS()
    live.clients.add(other)
    run(chat(live, me, "vai a comprare il pane al forno", "Anna"))
    ack = me.of("chat_ack")[0]
    m = other.of("chat")[0]
    assert ack["ok"] and ack["cid"] == m["cid"] and m["cid"].startswith("chat:")
    assert m["nick"] == "Anna" and m["returning"] is False and m["text"]
    assert isinstance(m["regions"], list) and m["regions"] and all(isinstance(i, int) for i in m["regions"])
    assert "ip" not in json.dumps(m).lower()


def test_returning_nick_is_matched_case_insensitively_and_counted(tmp_path):
    live = make(tmp_path)
    assert live.remember_nick("Anna") is False
    assert live.remember_nick("anna") is True and live.remember_nick("ANNA") is True
    assert live.nicks["Anna"]["count"] == 3 and set(live.nicks["Anna"]) == {"first", "last", "count"}
    assert live.remember_nick("") is False


def test_nick_store_is_capped_and_drops_the_oldest(tmp_path):
    live = make(tmp_path)
    cap = live_server.NICKS_CAP
    for i in range(cap):
        live.nicks[f"n{i}"] = {"first": i, "last": i, "count": 1}
        live.nick_index[f"n{i}"] = f"n{i}"
    live.remember_nick("fresh")
    assert len(live.nicks) == cap and "n0" not in live.nicks and "fresh" in live.nicks


def test_winning_chat_speech_carries_the_chats_cid(tmp_path):
    live = make(tmp_path, start=live_server.parse_start("14:00"))   # awake: the result must not depend on the wall clock
    watcher = FakeWS()
    live.clients.add(watcher)
    run(chat(live, FakeWS(), "ho fame, vai a comprare il pane", "Anna"))
    cid = watcher.of("chat")[0]["cid"]

    async def go():
        for _ in range(60):
            live.clock.sim0 += 10                          # the workspace has its own pacing: move the clock on
            await live.mind_step()
            if watcher.of("speech"):
                break
            await asyncio.sleep(0)
    run(go())
    speeches = watcher.of("speech")
    assert speeches, "the message never won the workspace in 60 cycles"
    assert {"text", "kind", "lang", "about", "cid", "action", "t"} <= set(speeches[0])
    assert speeches[0]["cid"] == cid
    assert all(s["cid"] is None or s["cid"].startswith("chat:") for s in speeches)


def test_hello_contract(tmp_path):
    live = make(tmp_path)

    class Req:
        remote = "127.0.0.1"
        headers = {}
    # build the hello the way ws_handler does, through its pieces
    regions = {g: list(i) for g, i in live.brain.group_idx.items() if i}
    assert regions and all(isinstance(i, int) for v in regions.values() for i in v)
    assert live.regions_of(["reward"]) == sorted(live.brain.group_idx["reward"])


def test_save_and_restore_round_trip(tmp_path):
    live = make(tmp_path)
    run(chat(live, FakeWS(), "ciao, sono Anna e ho fame", "Anna"))
    live.save_all()
    assert json.loads((tmp_path / "nicks.json").read_text())["Anna"]["count"] == 1
    assert (tmp_path / "mind.json").exists() and (tmp_path / "life.json").exists()
    again = make(tmp_path)
    assert "Anna" in again.nicks and again.remember_nick("anna") is True
    assert again.mind.to_dict().keys() == live.mind.to_dict().keys()


@pytest.mark.parametrize("flag", [["--life-activity", "buy_bread"], ["--force-market", "dump"],
                                  ["--force-stage", "REM"]])
def test_demo_flags_are_refused_without_demo(flag):
    r = subprocess.run([sys.executable, str(ROOT / "live_server.py"), "--port", "0", *flag],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "demo" in r.stderr


class SlowLLM:
    """A language model that answers after the wait for it has almost run out."""
    def __call__(self, system, user):
        time.sleep(1.0)
        return "sto pensando al pane"


def test_held_chat_line_is_not_lost_when_an_action_winner_follows(tmp_path):
    live = make(tmp_path, start=live_server.parse_start("14:00"))
    live.mind.llm = SlowLLM()
    watcher = FakeWS()
    live.clients.add(watcher)
    run(chat(live, FakeWS(), "ho fame, vai a comprare il pane", "Anna"))
    cid = watcher.of("chat")[0]["cid"]

    async def go():
        live.life.hunger = 0.97
        live.life.bread = False
        for _ in range(40):
            live.clock.sim0 += 10
            live.life.hunger = 0.97
            live.mind.next_proposal, live.mind.cooldown = 0.0, {}     # let an action winner come at once
            await live.mind_step()
            if any(s["cid"] == cid for s in watcher.of("speech")):
                break
            await asyncio.sleep(0.1)
    run(go())
    assert any(s["cid"] == cid for s in watcher.of("speech")), "the winning chat never got its inner line"


def test_release_held_sends_the_rule_line_at_once(tmp_path):
    live = make(tmp_path)
    live.mind.pending = {"text": "x", "kind": "rule", "lang": "en", "about": "a", "action": None,
                         "_llm": True, "_req": 7, "_deadline": live.mind.clock() + 99, "_ctx": {}}
    assert live.mind.speech_due() is None
    assert live.mind.release_held() and live.mind.speech_due()["text"] == "x"
    assert live.mind.llm_result(7, "late answer") is False


def test_hello_is_served_by_the_real_handler_and_is_json(tmp_path):
    from aiohttp import web, ClientSession
    from aiohttp.test_utils import TestServer
    live = make(tmp_path)

    async def go():
        app = web.Application()
        app.router.add_get("/ws", live.ws_handler)
        async with TestServer(app) as srv, ClientSession() as cs:
            async with cs.ws_connect(srv.make_url("/ws")) as ws:
                hello = json.loads((await ws.receive()).data)
                await ws.close()
        return hello
    hello = run(go())
    assert hello["type"] == "hello" and hello["regions"] and hello["region_rules"] and "mind" in hello
    json.dumps(hello)


def test_bad_nicks_are_rate_limited_too(tmp_path):
    live = make(tmp_path)
    me = FakeWS()
    run(live.handle_chat(me, "k", "hi", "admin"))
    run(live.handle_chat(me, "k", "hi", "admin"))
    assert me.of("chat_ack")[1]["reason"] == "too fast"
