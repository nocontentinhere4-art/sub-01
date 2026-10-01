"""His brain decides what he clicks: the eyes' proposals are validated, the brain model votes, tastes are learned,
the browser runs apart from the brain.

    python -m pytest tests/test_brain_decides.py -q
No network and no AI calls: providers are fakes. One test starts the real browser service process (no page loads).
"""
import asyncio
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import brain_vote as V
import eyes as E
import live_server
from browse_service import BrowserClient, BrowserDown, LocalBrowser, make_app
from live_server import Live, supervised
from tastes import PageWatch, Tastes


def run(coro):
    return asyncio.run(coro)


PAGE = {"url": "https://en.wikipedia.org/wiki/Bread", "title": "Bread", "host": "en.wikipedia.org", "kind": "page",
        "text": "Bread is a staple food prepared from a dough of flour and water.", "can_back": False,
        "links": [{"id": "L1", "href": "https://en.wikipedia.org/wiki/Sourdough", "text": "Sourdough bread", "area": 900},
                  {"id": "L2", "href": "https://www.youtube.com/watch?v=abc", "text": "How bakers knead dough",
                   "video": True, "area": 4000},
                  {"id": "L3", "href": "https://en.wikipedia.org/wiki/Wheat", "text": "Wheat", "area": 300},
                  {"id": "L4", "href": "https://www.bet365.com/offers", "text": "Bonus offers today", "area": 300},
                  {"id": "L5", "href": "https://example.org/login", "text": "Sign in to your account", "area": 300}]}


# --- 1. the eyes: proposals are validated, nothing invented ------------------------------------------------------
def test_only_links_on_the_page_and_the_guard():
    items = [{"action": "click", "target": "L1", "label": "read about sourdough", "networks": {"reward": 0.7}},
             {"action": "click", "target": "L99", "label": "invented link"},
             {"action": "click", "target": "https://evil.example/x", "label": "invented url"},
             {"action": "click", "target": "https://en.wikipedia.org/wiki/Wheat", "label": "wheat"},  # real href: ok
             {"action": "click", "target": "L4", "label": "offers"},                                # blocked host
             {"action": "click", "target": "L5", "label": "log in"},                                # login link
             {"action": "open_video", "target": "L1", "label": "not a video"},
             {"action": "open_video", "target": "L2", "label": "watch kneading", "networks": {"visual": 0.9}},
             {"action": "teleport", "target": "L1", "label": "x"}]
    out = E.validate(items, PAGE)
    assert [(o["action"], o["target"]) for o in out] == [("click", "L1"), ("click", "L3"), ("open_video", "L2")]
    assert out[0]["href"] == "https://en.wikipedia.org/wiki/Sourdough"
    assert all(o["href"] in {l["href"] for l in PAGE["links"]} for o in out)


@pytest.mark.parametrize("q,ok", [("Tokyo bakeries", True), ("how sourdough rises", True), ("cheap crypto tokens", False),
                                  ("$SOL price today", False), ("https://x.com", False), ("buy bitcoin now", False),
                                  ("one two three four five six seven", False), ("casino night", False),
                                  ("x", False), ("porn", False)])
def test_search_queries_are_filtered(q, ok):
    out = E.validate([{"action": "search", "target": q, "label": "search"}], PAGE)
    assert bool(out) == ok


def test_labels_networks_back_and_limits():
    items = [{"action": "scroll", "label": "keep reading this long page about bread and wheat today please",
              "networks": {"reward": 3, "fear": -1, "soul": 0.5, "visual": "nan", "attention": 0.4}},
             {"action": "back", "label": "go back"},                                  # can_back is False: dropped
             {"action": "leave", "label": "porn site"},                               # blocked label
             {"action": "search", "target": "rye bread", "label": "", "networks": None}]
    out = E.validate(items, PAGE)
    assert [o["action"] for o in out] == ["scroll", "search"]
    assert len(out[0]["label"].split()) == 8
    assert out[0]["networks"] == {"reward": 1.0, "attention": 0.4}                  # clipped; unknown/NaN/<=0 dropped
    assert set(out[1]["networks"]) <= set(E.NETWORKS) and out[1]["networks"]        # lexicon fallback
    many = [{"action": "click", "target": l, "label": l} for l in ("L1", "L1", "L3")] + \
           [{"action": "search", "target": f"bread {w}", "label": w} for w in ("rye", "spelt", "corn", "oat")]
    out = E.validate(many, PAGE)
    assert len(out) == E.MAX_OPTIONS and len({(o["action"], o["target"]) for o in out}) == len(out)


def test_parse_is_tolerant_but_strict_about_shape():
    assert E.parse('Sure! {"options": [{"action": "scroll"}]} hope that helps') == [{"action": "scroll"}]
    assert E.parse('[{"action": "back"}, 3, "x"]') == [{"action": "back"}]
    assert E.parse("no json here") == [] and E.parse('{"options": "nope"}') == []


class FakeProvider:
    name, model = "fake", "claude-opus-5-5"

    def __init__(self, reply, fail=False):
        self.reply, self.fail, self.calls = reply, fail, []

    def ask(self, system, user):
        self.calls.append(json.loads(user))
        assert "Never write a URL" in system
        if self.fail:
            raise TimeoutError("provider down")
        return self.reply, 1500, 200


def test_one_call_per_page_and_topped_up_with_local_options(tmp_path):
    reply = json.dumps({"options": [{"action": "click", "target": "L1", "label": "sourdough", "networks": {"reward": 0.6}}]})
    prov = FakeProvider(reply)
    eyes = E.Eyes(prov, E.Budget(tmp_path / "c.jsonl"))
    opts, meta = eyes.propose(PAGE, "bread")
    assert meta["source"] == "ai" and len(prov.calls) == 1 and len(opts) >= E.MIN_OPTIONS
    assert opts[0]["target"] == "L1" and {o["action"] for o in opts[1:]} <= set(E.ACTIONS)
    assert "href" not in json.dumps(prov.calls[0]) and len(prov.calls[0]["page"]["links"]) == 5   # ids, not URLs
    opts2, meta2 = eyes.propose(PAGE, "bread")
    assert len(prov.calls) == 1 and "no new call" in meta2["source"] and opts2[0] == opts[0]


# --- cost cap and spend log ----------------------------------------------------------------------------------------
def test_cost_cap_and_spend_log(tmp_path):
    now = [1000.0]
    budget = E.Budget(tmp_path / "costs.jsonl", per_hour=2, clock=lambda: now[0])
    prov = FakeProvider(json.dumps({"options": [{"action": "scroll", "label": "keep reading"}]}))
    eyes = E.Eyes(prov, budget)
    for i in range(3):
        eyes.propose(dict(PAGE, url=f"https://en.wikipedia.org/wiki/P{i}"))
        now[0] += 60
    assert len(prov.calls) == 2                                                  # the third page: over the cap
    _, meta = eyes.propose(dict(PAGE, url="https://en.wikipedia.org/wiki/P9"))
    assert meta["source"] == "local" and "cap" in meta["why_local"]
    rows = [json.loads(x) for x in (tmp_path / "costs.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and rows[0]["usd"] == round((1500 * 4.0 + 200 * 20.0) / 1e6, 6) and rows[0]["in"] == 1500
    now[0] += 3600
    eyes.propose(dict(PAGE, url="https://en.wikipedia.org/wiki/P10"))
    assert len(prov.calls) == 3                                                  # a rolling hour later: allowed
    s = budget.summary()
    assert s["calls_last_hour"] == 1 and s["usd_total"] > 0 and s["max_per_hour"] == 2
    assert E.Budget(tmp_path / "costs.jsonl", per_hour=2, clock=lambda: now[0]).calls == budget.calls   # survives restart


def test_provider_error_falls_back_to_local_and_is_logged(tmp_path):
    eyes = E.Eyes(FakeProvider("", fail=True), E.Budget(tmp_path / "c.jsonl"))
    opts, meta = eyes.propose(PAGE, "bread")
    assert meta["source"] == "local" and "TimeoutError" in meta["why_local"] and len(opts) >= E.MIN_OPTIONS
    assert json.loads((tmp_path / "c.jsonl").read_text())["ok"] is False
    assert E.Eyes(None, E.Budget()).propose(PAGE)[1]["why_local"] == "no AI key"


# --- 2. the brain vote -------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def brain():
    from brain_sim import Brain
    b = Brain()
    b.run(1)
    return b


REWARD = {"action": "click", "label": "bakery", "networks": {"reward": 1.0, "visual": 0.3}}
FEAR = {"action": "click", "label": "storm warning", "networks": {"fear": 1.0, "salience": 0.6}}
MIXED = [REWARD, FEAR, {"action": "search", "label": "maps", "networks": {"attention": 0.8}},
         {"action": "scroll", "label": "keep reading", "networks": {"language": 0.3}},
         {"action": "open_video", "label": "kneading video", "networks": {"visual": 1.0, "reward": 0.3}}]


def test_lookahead_matches_the_live_model_exactly(brain):
    ref = brain.clone()
    zs = [np.abs(ref.step(1)) for _ in range(50)]
    amp = V.simulate(brain.clone(), [np.zeros(brain.n)], seconds=0.05)
    assert np.allclose(amp[0], np.mean(zs, 0), atol=1e-12)


def test_vote_is_deterministic_and_leaves_the_live_brain_alone(brain):
    buf, stim, t = brain.buf.copy(), brain.stim.copy(), brain.t
    a = V.vote(brain.clone(), MIXED, 1.0, rng=np.random.default_rng(3))
    b = V.vote(brain.clone(), MIXED, 1.0, rng=np.random.default_rng(3))
    assert a["chosen"] == b["chosen"] and [o["p"] for o in a["options"]] == [o["p"] for o in b["options"]]
    assert np.array_equal(buf, brain.buf) and np.array_equal(stim, brain.stim) and brain.t == t
    assert a["clones"] == 6 and a["seconds"] == 0.3


def test_vote_prefers_reward_over_fear(brain):
    d = V.vote(brain.clone(), [FEAR, REWARD], 1.0, rng=np.random.default_rng(0))
    fear, reward = d["options"]
    assert reward["response"] > 0 > fear["response"] and reward["p"] > 0.95
    picks = [V.vote(brain.clone(), [FEAR, REWARD], 1.0, rng=np.random.default_rng(s))["chosen"] for s in range(20)]
    assert picks.count(1) >= 19
    assert "reward" in d["reason"] or "visual" in d["reason"]


def test_sleepy_and_bored_mean_a_higher_temperature(brain):
    assert V.temperature(0, 0, 0) < V.temperature(0.8, 0, 0) < V.temperature(0.8, 1.0, 0.5)
    rested = V.vote(brain.clone(), MIXED, 1.0, {"boredom": 0.0, "pressure": 0.1}, rng=np.random.default_rng(1))
    sleepy = V.vote(brain.clone(), MIXED, 1.0, {"boredom": 0.5, "pressure": 1.0, "tired": 0.6}, rng=np.random.default_rng(1))
    H = lambda d: -sum(o["p"] * math.log(o["p"]) for o in d["options"] if o["p"] > 0)
    assert sleepy["temperature"] > rested["temperature"] and H(sleepy) > H(rested)


def test_tastes_and_novelty_enter_the_vote(brain):
    same = [dict(REWARD, label="a"), dict(REWARD, label="b")]
    d = V.vote(brain.clone(), same, 1.0, tastes=[0.0, 0.9], novel=[False, True], rng=np.random.default_rng(0))
    assert d["options"][1]["p"] > 0.9 and d["options"][1]["taste"] == 0.9 and d["options"][1]["novel"]


def test_vote_is_cheap(brain):
    t0 = time.perf_counter()
    d = V.vote(brain.clone(), MIXED, 1.0, rng=np.random.default_rng(0))
    ms = (time.perf_counter() - t0) * 1000
    print(f"\nbrain vote: {len(MIXED)} options + 1 baseline x 300 ms simulated in {ms:.0f} ms on one core")
    assert d["ms"] < 2500                     # ~230-300 ms measured on the sandbox core; generous for slow CI


def test_chosen_stimulus_reaches_the_live_brain_scaled_by_gain(brain):
    c = brain.clone()
    before = c.stim.copy()
    V.apply(c, REWARD, 0.25)
    i = c.group_idx["reward"]
    assert np.allclose(c.stim[i] - before[i], 1.0 * V.STIM_AMP * 0.25)


# --- 3. tastes -----------------------------------------------------------------------------------------------------
def test_preference_update_is_a_prediction_error_rule(tmp_path):
    now = [0.0]
    t = Tastes(tmp_path / "tastes.json", clock=lambda: now[0])
    topics = Tastes.topics({"label": "sourdough bread", "networks": {"reward": 0.8, "visual": 0.1}}, "Bread")
    assert topics[0] == "net:reward" and "kw:sourdough" in topics and "net:visual" not in topics
    d1 = t.learn(topics, 1.0)
    assert d1 == 1.0 and abs(t.predict(topics) - 0.3) < 1e-9
    d2 = t.learn(topics, 1.0)
    assert abs(d2 - 0.7) < 1e-9 and t.predict(topics) > 0.5                  # smaller error, same direction
    t.learn(["kw:storm"], -1.0)
    assert t.predict(["kw:storm"]) < 0 and t.top()["dislikes"][0]["topic"] == "storm"
    saved = Tastes(tmp_path / "tastes.json", clock=lambda: now[0])
    assert saved.pref == t.pref
    p = t.predict(topics)
    now[0] += 7 * 86400                                                        # one time constant later
    t.decay()
    assert abs(t.predict(topics) - p * math.exp(-1)) < 1e-9


def test_page_watch_measures_the_stay():
    w = PageWatch()
    w.start(["kw:bread"], 0.0)
    for k in range(100):                                                       # reward above its running baseline
        w.feed({"reward": 1.0 if k < 30 else 2.0, "attention": 1.0, "fear": 1.0}, k * 0.1, 0.1)
    topics, r = w.finish()
    assert topics == ["kw:bread"] and 0 < r <= 1
    w.start(["kw:x"], 0.0)
    w.feed({"reward": 1.0}, 0.0, 0.1)
    assert w.finish() is None                                                  # too short to measure


# --- 5. the browser apart from the brain ---------------------------------------------------------------------------
def test_supervised_task_restarts_after_a_crash():
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("boom")
    run(supervised("t", flaky, backoff=0.01))
    assert len(calls) == 3


class DeadClient:
    def __init__(self):
        self.restarting, self.screens, self.calls = False, {}, 0

    async def init(self, state):
        self.calls += 1
        raise BrowserDown("connection refused")


def test_browser_crash_does_not_stop_the_brain_loop():
    sent = []

    async def broadcast(msg):
        sent.append(msg)

    live = SimpleNamespace(screen_device=lambda: "desk", browser=DeadClient(), local_browser=None, browsing_state={},
                           broadcast=broadcast, end_page=lambda: None)
    live.screen_status = lambda dev: Live.screen_status(live, dev)

    async def main():
        ticks = 0
        task = asyncio.create_task(Live.run_browse(live))

        async def brain():                                                    # stands in for run_brain's 20 Hz loop
            nonlocal ticks
            for _ in range(60):
                await asyncio.sleep(0.05)
                ticks += 1
        await brain()
        task.cancel()
        return ticks
    ticks = run(main())
    assert ticks == 60 and live.browser.calls >= 1
    assert live.browser.restarting and {"type": "screen", "device": "desk", "restarting": True} in sent
    assert live.screen_status("desk") == {"device": "desk", "restarting": True}


class FakeBrowser:
    def __init__(self):
        self.screens = {"desk": SimpleNamespace(shot=b"\xff\xd8jpg", shot_id=4, status=lambda: {"id": 4, "device": "desk"}),
                        "phone": SimpleNamespace(shot=None, shot_id=0, status=lambda: None)}
        self.log, self.used, self.browser, self.acts = [], set(), None, []

    async def step(self, device, heard, interest):
        return {"decide": dict(PAGE, device=device)}

    async def act(self, device, action, why, interest):
        self.acts.append((device, action, why))
        return {"id": 5, "device": device, "why": why}

    async def close(self, device=None):
        pass

    def to_dict(self):
        return {"log": self.log, "used": list(self.used)}


def test_service_api_and_client():
    from aiohttp.test_utils import TestServer

    async def main():
        fb = FakeBrowser()
        server = TestServer(make_app(fb, token="tok"))
        await server.start_server()
        url = f"http://127.0.0.1:{server.port}"
        try:
            c = BrowserClient(url, "tok")
            d = await c.step("desk", ["hi"], "bread")
            assert d["decide"]["links"][0]["id"] == "L1"
            st = await c.act("desk", {"action": "click", "target": "L1"}, "his brain picked it")
            assert st["id"] == 5 and fb.acts[0][1]["target"] == "L1" and c.screens["desk"]["id"] == 5
            assert await c.shot("desk") == b"\xff\xd8jpg"                        # proxied screenshot
            bad = BrowserClient(url, "wrong")
            with pytest.raises(BrowserDown):
                await bad.step("desk")                                         # token required
            await bad.aclose()
            await c.aclose()
        finally:
            await server.close()
        down = BrowserClient("http://127.0.0.1:9", "tok", timeout=2)
        with pytest.raises(BrowserDown):
            await down.step("desk")
        await down.aclose()
    run(main())


def test_local_browser_process_restarts_after_a_kill(tmp_path):
    async def main():
        lb = LocalBrowser()
        try:
            assert await lb.ensure() and lb.alive()
            pid = lb.proc.pid
            await lb.kill()                                                   # as if Chromium took it down
            lb.proc = SimpleNamespace(returncode=-9, pid=pid)                 # dead child still referenced
            assert await lb.ensure() and lb.alive() and lb.proc.pid != pid
            assert lb.restarts == 1 and lb.client.restarting                  # the screen says "restarting"
            assert await lb.client.health()
        finally:
            await lb.aclose()
        assert not lb.alive()
    run(main())


def test_decide_wires_eyes_vote_tastes_and_act(brain, tmp_path):
    """Live.decide with a fake browser and fake eyes: the chosen action is carried out and recorded."""
    sent = []

    async def broadcast(msg):
        sent.append(msg)

    fb = FakeBrowser()
    client = SimpleNamespace(act=fb.act)
    eyes = E.Eyes(FakeProvider(json.dumps({"options": [
        {"action": "click", "target": "L1", "label": "sourdough", "networks": {"reward": 1.0}},
        {"action": "click", "target": "L3", "label": "wheat", "networks": {"fear": 1.0}},
        {"action": "scroll", "label": "keep reading", "networks": {"language": 0.2}}]})), E.Budget(tmp_path / "c.jsonl"))
    engine = SimpleNamespace(gain=1.0, tired=0.0, pressure=lambda t: 0.2)
    live = SimpleNamespace(eyes=eyes, brain=brain.clone(), browser=client, engine=engine, broadcast=broadcast,
                           life=SimpleNamespace(boredom=0.1), clock=SimpleNamespace(now=time.time),
                           tastes=Tastes(tmp_path / "t.json"), pagewatch=PageWatch(), decisions={}, decision_log=[],
                           targets={}, vote_rng=np.random.default_rng(0))
    live.novel = lambda o: Live.novel(live, o)
    live.end_page = lambda: Live.end_page(live)
    reward = live.brain.group_idx["reward"]
    before = live.brain.stim[reward].copy()
    st = run(Live.decide(live, "desk", dict(PAGE, device="desk"), "bread"))
    dec = live.decisions["desk"]
    assert st["id"] == 5 and fb.acts[0][1]["target"] == dec["options"][dec["chosen"]]["target"]
    assert dec["options"][dec["chosen"]]["label"] == "sourdough" and dec["eyes"]["source"] == "ai"
    assert sent[0]["type"] == "decision" and live.pagewatch.cur["topics"][0] == "net:reward"
    assert np.allclose(live.brain.stim[reward] - before, V.STIM_AMP * 1.0)       # the live brain got the stimulus


def test_claude_provider_request_and_reply(monkeypatch):
    """ClaudeEyes against a local fake Messages endpoint: the request it sends and how it reads the reply."""
    pytest.importorskip("anthropic")
    import http.server
    import threading
    seen = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"], seen["beta"] = self.path, self.headers.get("anthropic-beta", "")
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
                              "content": [{"type": "text", "text": '{"options": [{"action": "scroll", "label": "more"}]}'}],
                              "stop_reason": "end_turn", "stop_sequence": None,
                              "usage": {"input_tokens": 1234, "output_tokens": 56}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_port}")
    try:
        prov = E.default_provider()
        assert isinstance(prov, E.ClaudeEyes) and prov.model == "claude-opus-5-5"
        text, tin, tout = prov.ask(E.SYSTEM, E.prompt(PAGE))
    finally:
        srv.shutdown()
    assert E.parse(text) == [{"action": "scroll", "label": "more"}] and (tin, tout) == (1234, 56)
    b = seen["body"]
    assert seen["path"].startswith("/v1/messages") and b["model"] == "claude-opus-5-5"
    assert b["output_config"] == {"effort": "low"} and b["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"] and b["system"] == E.SYSTEM
