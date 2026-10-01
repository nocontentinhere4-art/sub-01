"""Integration of the v2 twin components in the live server (headless, no network, no sockets).

    python -m pytest tests/test_integration.py -q

Drives `live_server.Live.tick()` (the same code the server runs every 50 ms) with a fake clock that advances
30 sim seconds per tick, i.e. `--time-scale 600`, over one accelerated night, with synthetic trades and a few chat
messages. Checks: no exceptions, the `twin` object in every tick message, neuromodulators follow the sleep circuit,
one memory is consolidated in the first REM episode with a correct sha256, weights stay inside the plasticity
bounds, the body stays in range, Life takes its hunger from the body, state is persisted. A digital twin model of one
real person's brain structure and recorded activity; not a mind, not conscious, not the person.
"""
import hashlib
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import live_server as ls
from sleep import TZ
from twin.plasticity import weights_sha256

STEP_S = 30.0            # sim seconds per tick (= --time-scale 600 at 20 ticks per second)
ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    """Sim clock that only moves when the test says so."""

    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t


def loc(day, hm):
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=TZ).timestamp()


class Night:
    """One accelerated night from 22:30 to 08:30 with trades and chat messages. Results kept for the tests."""

    def __init__(self, tmp, model="twin", ticks=None):
        self.live = live = ls.Live("demo", True, 600.0, tmp, start=loc(1, "22:30"), model=model)
        live.clock = FakeClock(loc(1, "22:30"))
        live.time_scale = 600.0
        self.msgs, self.log = [], []
        rng = random.Random(1)
        chat = {60: "good evening, how was the day", 150: "the market feels calm tonight",
                700: "a message heard while asleep"}
        n = ticks or int((10 * 3600) / STEP_S)
        for i in range(n):
            if i in chat:
                ok, why, _, _ = live.accept_chat(chat[i], f"10.0.0.{i}")
                assert ok, why
            if i % 15 == 0:                                   # a trade every 7.5 sim minutes, 55 % buys
                kind = "buy" if rng.random() < 0.55 else "sell"
                live.pending.append({"kind": kind, "usd": float(np.exp(rng.gauss(4.0, 1.5))), "tx": "", "who": "", "at": 0.0})
            msg, events = live.tick(now=i * ls.TICK)
            live.clock.t += STEP_S
            self.msgs.append(msg)
            self.log.append((live.engine.stage, msg["twin"]["levels"], live.body.vitals(), events,
                             live.brain.W.copy() if i == n - 1 else None))
            if any(e["type"] == "memory" for e in events):
                self.sha_at_memory = weights_sha256(live.plast.W)     # the plasticity weights right after consolidation
        self.events = [e for _, _, _, ev, _ in self.log for e in ev]


_night = {}


def night(tmp_path_factory):
    if "twin" not in _night:
        _night["twin"] = Night(tmp_path_factory.mktemp("night"))
    return _night["twin"]


def test_tick_messages_have_the_twin_object(tmp_path_factory):
    n = night(tmp_path_factory)
    for m in n.msgs:
        json.dumps(m)                                          # serialisable
        tw = m["twin"]
        assert set(tw) == {"score", "levels", "vitals", "sleep", "memories", "drift"}
        assert set(tw["levels"]) == {"DA", "5HT", "NE", "ACh"}
        assert set(tw["vitals"]) == {"hr_bpm", "resp_per_min", "glucose_mg_dl", "hunger"}
        assert set(tw["sleep"]) == {"stage", "H", "C", "pressure"}
        assert set(tw["memories"]) == {"count", "last"} and len(tw["memories"]["last"]) <= 5
        assert set(tw["drift"]) == {"rel_frobenius", "edges_changed"}
        assert np.isfinite(m["act"]).all()
    tw = n.msgs[-1]["twin"]
    sc = json.loads((ROOT / "web" / "twin_score.json").read_text())
    assert tw["score"]["fc_r"] == sc["heldout"]["fc_r"] and tw["score"]["label"] == sc["label"]
    assert "weak static match" in tw["score"]["label"]
    assert len(json.dumps(tw)) < 1500                         # small


def test_modulators_follow_sleep(tmp_path_factory):
    n = night(tmp_path_factory)
    stages = {s: [] for s in ("AWAKE", "NREM", "REM")}
    for st, lv, *_ in n.log[10:]:
        stages[st].append(lv)
    assert all(len(v) > 20 for v in stages.values()), {k: len(v) for k, v in stages.items()}
    mean = {s: {k: float(np.mean([x[k] for x in v])) for k in ("DA", "5HT", "NE", "ACh")} for s, v in stages.items()}
    for k in ("DA", "5HT", "NE", "ACh"):
        assert mean["NREM"][k] < mean["AWAKE"][k], (k, mean)        # NREM: all lower than wake
    assert mean["REM"]["ACh"] > mean["NREM"]["ACh"] + 0.2           # REM: acetylcholine high again ...
    assert mean["REM"]["NE"] < mean["AWAKE"]["NE"] - 0.2            # ... noradrenaline and serotonin low
    assert mean["REM"]["5HT"] < mean["AWAKE"]["5HT"] - 0.2
    gains = n.live.brain.gain
    assert gains.shape == (n.live.brain.n,) and np.isfinite(gains).all() and 0.4 < gains.min() and gains.max() < 1.6


def test_one_memory_in_the_first_rem_with_correct_sha256(tmp_path_factory):
    n = night(tmp_path_factory)
    live = n.live
    mem = [e for e in n.events if e["type"] == "memory"]
    assert len(mem) == 1 and mem[0]["text"].startswith("memory #1")
    i = next(i for i, (_, _, _, ev, _) in enumerate(n.log) if any(e["type"] == "memory" for e in ev))
    assert n.log[i][0] == "REM"                                    # consolidated while in REM
    assert all(s != "REM" for s, *_ in n.log[:i])                   # ... in the first REM episode of the night
    records = json.loads((live.data_dir / "memories.json").read_text())
    assert len(records) == 1                                       # one per night, not one per REM episode
    rec = records[0]
    assert rec["n"] == 1 and rec["message"] in ("good evening, how was the day", "the market feels calm tonight")
    assert rec["day"] == "2026-10-01" and len(rec["regions"]) >= 2
    # sha256 of the float32 C-order bytes of the weights right after consolidation (they move again once awake)
    assert rec["sha256"] == n.sha_at_memory and len(rec["sha256"]) == 64
    assert hashlib.sha256(np.ascontiguousarray(live.plast.W.astype("<f4")).tobytes()).hexdigest() != rec["sha256"]
    last = n.msgs[-1]["twin"]["memories"]
    assert last["count"] == 1 and last["last"][0]["sha256"] == rec["sha256"][:12] and last["last"][0]["n"] == 1
    assert live.consolidated_day == "2026-10-01"
    pending = [r["message"] for r in live.plast.pending]
    assert pending == ["a message heard while asleep"]               # a later message waits for the next night
    assert not any(r["message"] == rec["message"] for r in live.plast.pending)


def test_weights_stay_bounded_and_reach_the_brain(tmp_path_factory):
    n = night(tmp_path_factory)
    live, p = n.live, n.live.plast
    D = np.where(p.mask, p.W - p.W0, 0.0)
    assert np.all(np.abs(D) <= p.edge_cap * p.W0 * (1 + 1e-9) + 1e-15)
    assert p.drift()["rel_frobenius"] <= p.total_cap + 1e-12
    assert np.isfinite(p.W).all() and np.array_equal(p.W[~p.mask], p.W0[~p.mask])    # no edge is ever created
    assert live.brain.W0.shape == p.W0.shape and np.array_equal(live.brain.W0, p.W0)
    W_end = n.log[-1][4]
    assert np.abs(W_end - p.W0).max() > 0                           # the consolidated memory changed the brain's weights
    assert np.linalg.norm(W_end - p.W) / np.linalg.norm(p.W0) <= p.total_cap
    assert n.msgs[-1]["twin"]["drift"]["edges_changed"] > 0
    z = np.load(ROOT / "out" / "connectome.npz", allow_pickle=True)           # the original is only read
    assert z["weights"].shape[0] >= live.brain.n


def test_body_vitals_in_range_and_life_uses_the_body(tmp_path_factory):
    n = night(tmp_path_factory)
    for st, _, v, *_ in n.log:
        assert 38 <= v["hr_bpm"] <= 140 and 6 <= v["resp_per_min"] <= 35 and 50 <= v["glucose_mg_dl"] <= 250, (st, v)
    asleep = [v["hr_bpm"] for st, _, v, *_ in n.log[200:] if st == "NREM"]
    awake = [v["hr_bpm"] for st, _, v, *_ in n.log[:100] if st == "AWAKE"]
    assert np.mean(asleep) < np.mean(awake)                          # heart rate lower in NREM than in the evening
    live = n.live
    assert live.life.body is live.body and not live.life.own_body
    assert live.life.hunger == live.body.hunger and 0.0 <= live.body.hunger <= 1.0
    assert live.life.snapshot()["hunger"] == round(live.body.hunger, 2)


def test_chat_responses_are_measured_and_the_state_is_persisted(tmp_path_factory):
    n = night(tmp_path_factory)
    live = n.live
    assert not live.probes                                           # every probe finished and was recorded
    live.save_twin()
    for f in ("twin_state.json", "weights.npz", "memories.json", "pending_responses.json"):
        assert (live.data_dir / f).exists(), f
    again = ls.Live("demo", True, 600.0, live.data_dir, start=loc(2, "08:30"), model="twin")
    assert again.consolidated_day == live.consolidated_day
    assert again.body.to_dict()["glucose"] == live.body.to_dict()["glucose"]
    assert np.array_equal(again.plast.W, live.plast.W) and np.array_equal(again.brain.W, live.plast.W)
    assert [m["sha256"] for m in again.memories] == [m["sha256"] for m in live.memories]
    assert not (live.data_dir / "connectome.npz").exists()


def test_old_model_still_works(tmp_path):
    live = ls.Live("demo", True, 600.0, tmp_path, start=loc(1, "22:30"), model="sl")
    live.clock = FakeClock(loc(1, "22:30"))
    assert live.model == "sl" and not hasattr(live.brain, "set_gain")
    for i in range(120):
        if i == 5:
            assert live.accept_chat("hello from the old model", "k")[0]
        live.pending.append({"kind": "buy", "usd": 50.0, "tx": "", "who": "", "at": 0.0}) if i % 20 == 0 else None
        msg, _ = live.tick(now=i * ls.TICK)
        live.clock.t += STEP_S
        json.dumps(msg)
        assert "twin" in msg and np.isfinite(msg["act"]).all()
    assert (tmp_path / "sl").exists() or live.plast.data_dir == tmp_path / "sl"       # weights kept per model
    # the old model does not use plastic weights: no drift and no memory are reported for it, and its page score
    # is its own held-out score, never the twin's
    assert not live.plastic and msg["twin"]["drift"]["edges_changed"] == 0 and msg["twin"]["memories"]["count"] == 0
    sc = json.loads((ROOT / "web" / "twin_score.json").read_text())
    assert msg["twin"]["score"]["fc_r"] == sc["baselines"]["old_model"]["fc_r"] != sc["heldout"]["fc_r"]
    assert "Stuart-Landau" in msg["twin"]["score"]["label"]


def test_pages_docker_and_gitignore_are_wired():
    web = ROOT / "web"
    wording = "a digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the person"
    assert wording in (web / "twin_panel.js").read_text()
    for page in ("index.html", "life.html"):
        s = (web / page).read_text()
        assert 'id="twin-host"' in s and 'src="twin_panel.js"' in s and "twinPanel.update(m.twin)" in s, page
    panel = (web / "twin_panel.js").read_text()
    assert "http://" not in panel and "https://" not in panel and "fetch(" not in panel     # no external requests
    assert "innerHTML" not in panel                                                          # chat text only via textContent
    docker = (ROOT / "Dockerfile").read_text()
    for need in ("COPY twin ./twin", "COPY twin/data ./twin/data", "COPY web/twin_score.json"):
        assert need in docker
    ignore = (ROOT / ".gitignore").read_text().splitlines()
    assert "/data/" in ignore and "data/" not in ignore                                      # twin/data/ is tracked
    for f in ("RECEPTORS_SOURCES.md", "receptors_214.csv", "cpu_live.json"):
        assert (ROOT / "twin" / "data" / f).exists(), f
