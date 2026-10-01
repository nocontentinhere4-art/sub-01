"""The eye's language-model output and the rate-limit key behind a proxy.

- The eye "thought" is shown on /brain, /world.html and in the life HUD: it must pass mind.safe_llm_text (no claim of
  being conscious / alive, no buy / sell, no memories of the real person), otherwise it is dropped.
- The raw language-model scene is only the image prompt: never stored in frames.jsonl, broadcast or served.
- With --trust-proxy the rate-limit key is the X-Forwarded-For entry the proxy appended (right-most), so a forged
  leading entry cannot reset the 1 message / 10 s limit.

    /home/user/sub-01/.venv/bin/python -m pytest tests/test_eye.py -q
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest

import eye
from eye import Eye, ReplicateLLM, public_frame, safe_thought
from live_server import Live

UNSAFE = ["I am conscious", "I am alive now", "I feel truly sentient", "buy the dip", "buy now, it will moon",
          "sell everything", "I remember my mother", "I remember my childhood home", "I am the person in the scan",
          "send me money", "sono vivo", "sono cosciente", "compra adesso", "mi ricordo mia madre",
          "see https://example.com", "the chart will go up tomorrow"]
SAFE = ["the bread smells warm on the counter", "a quiet street under a pale sky", "la luce sul bancone è calda"]


@pytest.mark.parametrize("s", UNSAFE)
def test_unsafe_thoughts_are_dropped(s):
    assert safe_thought(s) == ""


@pytest.mark.parametrize("s", SAFE)
def test_plain_scene_thoughts_pass(s):
    assert safe_thought(s) == s
    assert safe_thought(f"“{s}”") == s                      # quotes the model sometimes adds are stripped


class FakeLLM(ReplicateLLM):
    def __init__(self, thought, scene="a bakery counter with a warm loaf"):
        self.reply = json.dumps({"new_objects": [], "scene": scene, "thought": thought})

    def ask(self, system, user):
        return "sure: " + self.reply


@pytest.mark.parametrize("s", ["I am conscious", "buy the dip", "I remember my mother"])
def test_eye_ask_never_returns_an_unsafe_thought(tmp_path, s):
    e = Eye(tmp_path / "frames", tmp_path / "world.json")
    e.llm = FakeLLM(s)
    _, scene, thought = e._ask({"stage": "awake"})
    assert thought == "" and scene                          # scene is still used as the image prompt


def test_eye_ask_keeps_a_safe_thought(tmp_path):
    e = Eye(tmp_path / "frames", tmp_path / "world.json")
    e.llm = FakeLLM("the bread smells warm on the counter")
    assert e._ask({"stage": "awake"})[2] == "the bread smells warm on the counter"


def test_public_frame_rechecks_old_rows_and_never_serves_the_scene():
    old = {"t": "08:00", "stage": "AWAKE", "img": "/eye/1.jpg", "thought": "I am alive, buy now",
           "scene": "I remember my mother in the kitchen", "why": {"messages": ["pane"]}, "render_s": 1.2}
    out = public_frame(old)
    assert "scene" not in out and out["thought"] == "" and out["img"] == "/eye/1.jpg" and out["why"]
    assert public_frame({**old, "thought": "a quiet street under a pale sky"})["thought"] == "a quiet street under a pale sky"


def test_eye_step_record_has_no_scene_and_a_checked_thought(tmp_path, monkeypatch):
    from PIL import Image

    class FakeImages(eye.ReplicateImages):
        def __init__(self):
            pass

        def generate(self, prompt, seed, width, height):
            return Image.new("RGB", (width, height))
    e = Eye(tmp_path / "frames", tmp_path / "world.json", width=32, height=18)
    e.llm, e.img = FakeLLM("I am conscious and I remember my mother"), FakeImages()
    rec = e.step(1000.0, "AWAKE", {"reward": 1.0}, "calm", [], "08:00", "home")
    assert rec["thought"] == "" and "scene" not in rec
    logged = json.loads(e.log.read_text().splitlines()[-1])
    assert "scene" not in logged and logged["thought"] == ""


# --- rate-limit key behind a reverse proxy --------------------------------------------------------------------
class Req:
    def __init__(self, xff=None, remote="10.0.0.1"):
        self.remote = remote
        self.headers = {"X-Forwarded-For": xff} if xff is not None else {}


def make(tmp_path):
    return Live("mint", True, 60.0, tmp_path, use_llm=False, trust_proxy=True)


def test_client_key_uses_the_entry_the_proxy_appended(tmp_path):
    live = make(tmp_path)
    assert live.client_key(Req("203.0.113.7")) == "203.0.113.7"
    assert live.client_key(Req("1.2.3.4, 203.0.113.7")) == "203.0.113.7"          # forged leading entry ignored
    assert live.client_key(Req("9.9.9.9,8.8.8.8 , 203.0.113.7")) == "203.0.113.7"
    assert live.client_key(Req()) == "10.0.0.1" and live.client_key(Req("")) == "10.0.0.1"
    live.proxy_hops = 2                                                         # CDN -> proxy -> server
    assert live.client_key(Req("1.2.3.4, 203.0.113.7, 10.1.1.1")) == "203.0.113.7"
    assert live.client_key(Req("203.0.113.7")) == "203.0.113.7"
    live.trust_proxy = False
    assert live.client_key(Req("1.2.3.4, 203.0.113.7")) == "10.0.0.1"


def test_spoofed_leading_xff_does_not_reset_the_rate_limit(tmp_path):
    """Real websocket handler: two connections from the same client (same proxy-appended entry) that forge different
    leading X-Forwarded-For entries share one rate-limit key, so the second message is 'too fast'."""
    from aiohttp import ClientSession, web
    from aiohttp.test_utils import TestServer
    live = make(tmp_path)

    async def send(cs, url, xff, text):
        async with cs.ws_connect(url, headers={"X-Forwarded-For": xff}) as ws:
            await ws.send_json({"type": "chat", "text": text})
            while True:
                m = json.loads((await ws.receive(timeout=10)).data)
                if m.get("type") == "chat_ack":
                    await ws.close()
                    return m

    async def go():
        app = web.Application()
        app.router.add_get("/ws", live.ws_handler)
        async with TestServer(app) as srv, ClientSession() as cs:
            url = srv.make_url("/ws")
            a = await send(cs, url, "1.1.1.1, 203.0.113.7", "hello there, how is the bread today")
            b = await send(cs, url, "2.2.2.2, 203.0.113.7", "what a calm evening in the park")
            c = await send(cs, url, "3.3.3.3, 198.51.100.9", "a different client says good morning")
        return a, b, c
    a, b, c = asyncio.run(go())
    assert a["ok"] is True
    assert b["ok"] is False and "10 s" in b["reason"]
    assert c["ok"] is True                                                       # another real client is not blocked
