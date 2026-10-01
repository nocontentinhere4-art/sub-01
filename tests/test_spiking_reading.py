"""Daily reading memory on the spiking brain: readings and chat are stored, replayed in sleep, recalled the next day.

    python -m pytest tests/test_spiking_reading.py -q     # the session test runs ~2 min on 2 CPU cores (N = 20k)
No RunPod, no network: the pod manager runs against the fake API of test_spiking_ops.
"""
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from spiking import pod_manager                                        # noqa: E402
from spiking import server as spiking_server                          # noqa: E402
from sleep import Memory                                              # noqa: E402
from test_spiking_ops import AUTH, beats, make_mgr, reasons, run, tk, with_client   # noqa: E402

ITEMS_D1 = [
    {"text": "good morning little brain, the sun is warm today", "source": "chat"},
    {"text": "Inokashira Park park pond cherry blossoms kichijoji zoo boats", "source": "reading", "item": "Inokashira Park"},
    {"text": "Bread flour dough yeast baking oven crust wheat", "source": "reading", "item": "Bread"},
    {"text": "Moon orbit tides craters lunar apollo satellite phases", "source": "reading", "item": "Moon"},
]
ITEMS_D2 = [{"text": "Tea leaves brewing ceremony matcha kettle cups", "source": "reading", "item": "Tea"}]


# --- the GPU session code path, on CPU at small N ---------------------------------------------------------------
@pytest.fixture(scope="module")
def two_days(tmp_path_factory):
    torch = pytest.importorskip("torch")
    from spiking.session import run_session
    prev = torch.get_num_threads()
    torch.set_num_threads(2)
    try:
        cfg = {"n_neurons": 20000, "device": "cpu", "seed": 1, "day": "2026-10-02", "max_minutes": 20,
               "config": {"hc_scale": 6}, "phases": ["validate_reading"], "sleep_minutes": 0.1, "sleep_cycles": 1,
               "lures": 6, "validate": True, "elapsed_days": 1.0, "session_id": "cpu-test",
               "items_day1": ITEMS_D1, "items_day2": ITEMS_D2}
        out = tmp_path_factory.mktemp("session")
        res = run_session(cfg, out)
    finally:
        torch.set_num_threads(prev)
    assert res["error"] is None, res["error"]
    return res, out


def by_label(res):
    return {(t["label"], t["scores"][0]["item_day"] if t.get("scores") else None): t
            for t in res["phases"]["memory_test"]}


def test_encode_replay_recall_beats_lures(two_days):
    res, _ = two_days
    t = by_label(res)[("after sleep", "2026-10-01")]
    hc = [s["hc"] for s in t["scores"]]
    lure = [c["hc"] for c in t["control_scores"]]
    assert len(t["recalled"]) >= 3 and sum(hc) / len(hc) > max(lure) + 0.5        # well above every lure, in Hz
    sleeps = res["phases"]["sleep"]
    assert sleeps[0]["replay"] is True and len(sleeps[0]["replays"]) >= 1          # REM replayed stored items


def test_readings_and_chat_both_stored_with_source(two_days):
    res, _ = two_days
    enc = res["phases"]["encode"][0]["stored"]
    assert {s["source"] for s in enc} == {"chat", "reading"}
    assert {s["item"] for s in enc if s["source"] == "reading"} == {"Inokashira Park", "Bread", "Moon"}
    t = by_label(res)[("after encoding", "2026-10-01")]
    assert all({"item", "source", "item_day", "hc", "hc_recalled"} <= set(s) for s in t["scores"])
    assert {s["source"] for s in t["scores"]} == {"chat", "reading"}


def test_next_day_test_uses_yesterdays_items_after_forgetting(two_days):
    res, out = two_days
    nd = by_label(res)[("next day", "2026-10-01")]
    assert {s["item_day"] for s in nd["scores"]} == {"2026-10-01"}                  # only yesterday's items
    assert len(nd["scores"]) == len(ITEMS_D1) and nd["day"] == "2026-10-02"
    assert len(nd["recalled"]) >= 1                                                 # something survives a day
    d2 = by_label(res)[("after sleep", "2026-10-02")]
    assert [s["item"] for s in d2["scores"]] == ["Tea"]
    assert (out / "weights.npz").exists()                                            # learned weights saved


def test_day_items_are_capped_per_source(tmp_path):
    pytest.importorskip("torch")
    from spiking.session import Session
    items = [{"text": f"chat {i} words here", "source": "chat"} for i in range(8)]
    items += [{"text": f"Title{i} key words", "source": "reading", "item": f"Title{i}"} for i in range(7)]
    s = Session({"items": items}, tmp_path)
    got = s.day_items()
    assert [x["source"] for x in got].count("chat") == 5 and [x["source"] for x in got].count("reading") == 5
    assert got[5]["item"] == "Title0"
    old = Session({"messages": [{"text": "warm bread"}]}, tmp_path / "o").day_items()     # old config: chat only
    assert old == [{"text": "warm bread", "source": "chat", "item": "warm bread"}]


# --- Railway side: what goes to the pod -------------------------------------------------------------------------
def memory_with_readings(t):
    mem = Memory()
    mem.add(t - 3600, "do you like trains?", "AWAKE", {}, "neutral", [])
    mem.add(t - 1800, "good night", "AWAKE", {}, "positive", [])
    for k in range(7):
        mem.add(t - 7200 + 300 * k, f"Title {k}", "AWAKE", {}, "neutral", [], source="reading",
                title=f"Title {k}", keywords=["moon", "tides"])
    mem.add(t - 2 * 86400, "Old article", "AWAKE", {}, "neutral", [], source="reading", title="Old article")
    return mem


def test_top_items_sends_chat_and_todays_readings():
    t = tk(1, 21).timestamp()
    mem = memory_with_readings(t)
    msgs = pod_manager.top_messages(mem, t)
    assert [m["text"] for m in msgs] == ["good night", "do you like trains?"]       # readings never as chat
    items = pod_manager.top_items(mem, t)
    reads = [i for i in items if i["source"] == "reading"]
    assert len(reads) == 5 and all(i["text"].endswith("moon tides") for i in reads)
    assert reads[0]["item"] == "Title 6" and "Old article" not in [i["item"] for i in items]   # today, newest first


def test_session_config_carries_items_and_pong_is_opt_in(tmp_path):
    t = tk(1, 21)
    mem = memory_with_readings(t.timestamp())
    mgr, fc, api, log, stops = make_mgr(tmp_path, t)
    mgr.get_items = lambda: pod_manager.top_items(mem, fc.now().timestamp())
    cfg = mgr.session_config(t, 60, t)
    assert [i["source"] for i in cfg["items"]].count("reading") == 5 and len(cfg["messages"]) == 2
    assert cfg["phases"] == ["recall_yesterday", "encode", "memory_test", "sleep", "memory_test", "free"]
    mgr2, *_ = make_mgr(tmp_path / "p", t, env={"SUB01_PONG": "1"})
    assert mgr2.session_config(t, 60, t)["phases"][1:4] == ["encode", "pong_train", "pong_exam"]


def test_default_schedule_and_one_hour_a_day(tmp_path):
    from spiking.pod_manager import PodManager
    mgr = PodManager(tmp_path, "https://srv", "s", env={"RUNPOD_API_KEY": "k"})
    assert mgr.schedule.windows == [(21 * 60, 22 * 60, "Asia/Tokyo")]
    assert mgr.max_hours_day == 1.0 and mgr.max_session_min == 60
    assert mgr.schedule.next_session(tk(1, 20)) == (tk(1, 21), tk(1, 22))
    # 0.9 h already used today: only 6 min left -> no pod
    mgr, fc, api, log, stops = make_mgr(tmp_path / "c", tk(1, 21), schedule="21:00-22:00")
    log.start("old", "sub01-spiking-old", "g", 0.3, "session")
    fc.t += timedelta(hours=0.9)
    log.stop("old", "done")
    assert str(run(mgr.run_session(tk(1, 21), tk(1, 23)))).startswith("skipped")
    assert not [c for c in api.calls if c[0] == "POST"]
    # 0.5 h used: the session is cut to the 30 min left, then deleted
    mgr, fc, api, log, stops = make_mgr(tmp_path / "d", tk(2, 20), schedule="21:00-22:00")
    log.start("old", "sub01-spiking-old", "g", 0.3, "session")
    fc.t += timedelta(hours=0.5)
    log.stop("old", "done")
    fc.t = tk(2, 21)
    fc.script.append((tk(2, 21, 1), mgr.on_hello))
    beats(mgr, fc, tk(2, 21, 1))
    assert run(mgr.run_session(tk(2, 21), tk(2, 22))) == "session end"
    assert fc.t - tk(2, 21) == timedelta(minutes=30) and reasons(log)[-1] == "session end"
    assert [p["name"] for p in api.pods] == ["BRAIN"]                                     # ours deleted, BRAIN untouched


# --- server: per-item results and /api/memory -------------------------------------------------------------------
def mt(label, day, test_day, session, items):
    return {"type": "result", "kind": "memory_test", "day": test_day, "label": label, "session": session,
            "thresholds": {"hc": 0.3, "ctx": 0.1},
            "scores": [{"text": f"{i} words", "item": i, "source": src, "item_day": day, "hc": hc,
                        "hc_recalled": hc > 0.3} for i, src, hc in items]}


def test_results_rows_and_api_memory(tmp_path):
    async def go(client, hub, live):
        assert (await (await client.get("/api/memory")).json())["items"] == []
        posts = [mt("after sleep", "2026-10-01", "2026-10-01", "s1", [("Moon", "reading", 2.0), ("hi", "chat", 1.0)]),
                 mt("next day", "2026-10-01", "2026-10-02", "s2", [("Moon", "reading", 0.2), ("Bread", "reading", 1.5),
                                                                   ("hi", "chat", 0.1)]),
                 mt("after sleep", "2026-10-02", "2026-10-02", "s2", [("hello", "chat", 2.0)])]   # day 2: no readings
        for p in posts:
            assert (await client.post("/api/spiking/result", json=p, headers=AUTH)).status == 200
        rows = [json.loads(x) for x in (tmp_path / "spiking" / "memory_tests.jsonl").read_text().splitlines()]
        assert len(rows) == 6
        assert {"day", "item", "source", "recalled", "score"} <= set(rows[0])
        assert rows[0] == {**rows[0], "day": "2026-10-01", "item": "Moon", "source": "reading", "recalled": True,
                           "score": 2.0, "label": "after sleep", "session": "s1"}
        m = await (await client.get("/api/memory")).json()
        assert m["day"] == "2026-10-01" and m["label"] == "next day"           # the next-day test wins
        assert [(i["item"], i["recalled"]) for i in m["items"]] == [("Bread", True), ("Moon", False), ("hi", False)]
        assert "a model, not a mind" in m["note"] and "partial cue" in m["note"]
        assert (await client.post("/api/spiking/result", json=posts[0])).status == 401   # pod secret needed to write
    run(with_client(tmp_path, go))
