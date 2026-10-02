"""His spiking neurons in the day (#55): spiking/live.py, its child-process protocol, the brain_vote term, the night.

numpy only (no torch), so it runs in CI and in the server image. The learning check builds a 10k-neuron network and
its frozen twin (~25 s on one core). The torch checks at the end (same synapses as net.py, the night's replay of real
choices) are skipped where torch is absent.

    python -m pytest tests/test_spiking_live.py -q
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import brain_vote as V  # noqa: E402
from spiking import live as L  # noqa: E402
from spiking.config import Config  # noqa: E402

SMALL = 5000


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def small():
    return L.LiveBrain(SMALL, None)


# --- cues and pools from real labels ---------------------------------------------------------------------------------
def test_variable_offer_sets_any_labels(small):
    offers = [["read about bread", "wander somewhere else"],
              ["パン", "", "next page", "a", "keep reading this page"],
              ["apple", "river", "cloud", "stone", "lamp", "bird"],
              ["Search Tokyo parks", "search tokyo PARKS!", "museum hours"]]
    for labels in offers:
        d = small.decide(labels)
        assert d["pick"] in range(len(labels)) and len(d["pool_rates"]) == len(labels)
        assert 0 < d["decision_ms"] <= L.TIMEOUT_MS and np.isfinite(d["pool_rates"]).all()
        assert d["twin_pick"] in range(len(labels)) and len(d["twin_rates"]) == len(labels)
    assert len(small.decide([str(i) + " option" for i in range(9)])["pool_rates"]) == L.MAX_OPTIONS
    with pytest.raises(ValueError):
        small.decide(["only one"])


def test_pools_are_disjoint_and_words_keep_their_neurons(small):
    ch = small.ch
    labels = ["read about bread", "bread recipes", "tokyo parks", "wander somewhere else"]
    for lb in labels:
        ch.cue(lb)
    pools = L.label_pools(ch.action, [ch._aff[lb] for lb in labels])
    allp = np.concatenate(pools)
    assert len(allp) == len(np.unique(allp)) == len(ch.action) and all(len(p) > 0 for p in pools)
    # the same word lands on the same neurons in every label (what is learned about "bread" carries over)
    bread = L.label_cue(small.net, "bread", ch.cue_space)
    assert np.isin(bread, ch.cue("read about bread")).all() and np.isin(bread, ch.cue("bread recipes")).all()
    assert set(ch.cue("bread")) <= set(ch.cue_space)
    # rank-normalised affinity: a long label does not get a smaller pool on average
    a = L.label_affinity("one two three four", 1000)
    assert abs(a.mean() - 0.5) < 1e-9 and abs(a.std() - L.label_affinity("one", 1000).std()) < 1e-9


def test_lean_is_bounded_and_centred():
    ln = L.lean([5.0, 9.0, 4.0])
    assert ln[1] > 0 > ln[2] and np.all(np.abs(ln) <= 1) and abs(L.lean([3, 3])[0]) < 1e-12


# --- learning -------------------------------------------------------------------------------------------------------
def test_learning_beats_the_frozen_twin_on_a_synthetic_stream():
    t0 = time.process_time()
    b = L.LiveBrain(10_000, None)
    r = L.synthetic(b, trials=100, seed=1)
    cpu = time.process_time() - t0
    print(f"\nlive 10k, 100 decisions with variable offers: learned {r['learned']}, frozen twin {r['twin']}, "
          f"chance {r['chance']}; curve {r['curve']} vs {r['twin_curve']}; {cpu:.1f} s CPU")
    assert r["learned"] >= r["twin"] + 0.15 and r["learned"] >= r["chance"] + 0.15
    assert abs(r["twin"] - r["chance"]) < 0.15                     # the twin never learns: near chance
    assert np.abs(b.tw.net.w[b.ch.pidx] - b.ch.w0).max() == 0      # the twin's weights never moved
    assert np.abs(b.dw).max() > 0 and (b.ch.w0 + b.dw <= b.ch.w_max + 1e-6).all() and (b.ch.w0 + b.dw >= -1e-6).all()


def test_learning_rate_decays_to_a_floor(small):
    n0 = small.n_learn
    try:
        small.n_learn = 0
        assert small.eta() == L.ETA
        small.n_learn = int(L.ETA_HALF)
        assert abs(small.eta() - L.ETA / 2) < 1e-12
        small.n_learn = 10 ** 6
        assert small.eta() == L.ETA * L.ETA_FLOOR
    finally:
        small.n_learn = n0


def test_learn_tags_the_followed_pool_only_for_that_decision(small):
    d = small.decide(["read about bread", "tokyo parks", "jazz records"], did="x")
    dw0 = small.dw.copy()
    assert small.learn("unknown", 0, 0.5)["ok"] is False
    assert small.learn("x", 7, 0.5)["ok"] is False                 # not an offered option: nothing learned
    small.decide(["read about bread", "tokyo parks", "jazz records"], did="x")
    r = small.learn("x", 0, 0.5)
    assert r["ok"] and r["da"] == 1.0                              # DA_GAIN x 0.5, clipped to 1
    up = small.dw - dw0
    q = small.ch.post
    assert not np.any(up[(q < 0) | ~np.isin(q, small.ch.action)])  # only synapses onto offered pools moved
    assert small.learn("x", 0, 0.5)["ok"] is False                 # one dopamine per decision
    assert d["pick"] in (0, 1, 2)


def test_weights_persist_across_a_restart_and_a_torn_file_is_kept_aside(tmp_path):
    path = tmp_path / "spiking" / "live_weights.npz"
    a = L.LiveBrain(SMALL, path, twin=False)
    thr = a.ch.thr_hz
    for i in range(3):
        a.decide(["read about bread", "tokyo parks"], did=i)
        a.learn(i, 0, 0.4)
    b = L.LiveBrain(SMALL, path, twin=False)
    assert b.n_learn == 3 and b.n_decisions == 3 and b.calib is None and b.ch.thr_hz == thr   # no recalibration
    assert np.array_equal(a.dw, b.dw) and np.array_equal(a.net.w, b.net.w)
    assert not list(path.parent.glob("*.tmp"))
    path.write_bytes(path.read_bytes()[:100])                      # torn by a kill mid-write
    c = L.LiveBrain(SMALL, path, twin=False)
    assert c.n_learn == 0 and not np.any(c.dw) and list(path.parent.glob("live_weights.npz.corrupt-*"))
    d = L.LiveBrain(SMALL + 1000, path, twin=False)                # another network: starts fresh, never mixes
    assert d.n_learn == 0


# --- the vote ------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def brain():
    from brain_sim import Brain
    b = Brain()
    b.run(1)
    return b


SAME = [{"action": "click", "label": f"page {c}", "networks": {"reward": 0.5}} for c in "abc"]


def test_vote_without_and_with_the_spiking_term(brain):
    base = V.vote(brain.clone(), SAME, 1.0, rng=np.random.default_rng(0))
    assert base["spiking"]["used"] is False and all(o["spiking"] is None for o in base["options"])
    sp = {"pick": 2, "pool_rates": [4.0, 4.0, 12.0], "decision_ms": 60, "n_neurons": 20000, "id": 5}
    d = V.vote(brain.clone(), SAME, 1.0, rng=np.random.default_rng(0), spiking=sp)
    assert d["spiking"]["used"] and d["spiking"]["leaned_to"] == "page c" and d["spiking"]["weight"] == V.SPIKING_W
    assert d["options"][2]["spiking"] > 0.9 and d["options"][0]["spiking"] < 0
    assert d["options"][2]["p"] > base["options"][2]["p"]           # the term moves the vote toward its lean...
    assert max(o["p"] for o in d["options"]) < 0.999                 # ...as one term among others
    for bad in ({"why": "spiking network offline"}, {"pool_rates": [1.0, 2.0]}, {"pool_rates": [1, "x", 2]},
                {"pool_rates": [1.0, float("nan"), 2.0]}):
        s = V.vote(brain.clone(), SAME, 1.0, rng=np.random.default_rng(0), spiking=bad)
        assert s["spiking"]["used"] is False and [o["p"] for o in s["options"]] == [o["p"] for o in base["options"]]
    assert V.vote(brain.clone(), SAME, 1.0, rng=np.random.default_rng(0),
                  spiking={"why": "spiking network offline"})["spiking"]["why"] == "spiking network offline"


# --- the child process -------------------------------------------------------------------------------------------
async def _ready(cl, s=60):
    for _ in range(int(s * 10)):
        if cl.ready:
            return True
        await asyncio.sleep(0.1)
    return False


def test_child_process_protocol_learning_log_and_restart(tmp_path):
    async def go():
        cl = L.LiveClient(tmp_path, n_neurons=SMALL)
        assert (await cl.decide(["a b", "c d"]))["why"] == "spiking network offline"
        await cl.start()
        try:
            assert await _ready(cl)
            ans = await cl.decide(["read about bread", "tokyo parks", "wander somewhere else"])
            assert len(ans["pool_rates"]) == 3 and ans["pick"] in range(3) and ans["wall_ms"] < 2000
            cl.followed(ans, 1)
            assert cl.view()["last"]["followed_label"] == "tokyo parks"
            cl.outcome(0.3, 0.2)                                    # he left the page: dopamine for that decision
            st = await cl.call("status")
            assert st["n_learn"] == 1 and st["n_decisions"] == 1
            rows = [json.loads(x) for x in (tmp_path / "spiking" / "live_choices.jsonl").read_text().splitlines()]
            assert rows[-1]["followed"] == 1 and rows[-1]["labels"] == ["read about bread", "tokyo parks", "wander somewhere else"]
            assert rows[-1]["delta"] == 0.2 and rows[-1]["k"] == 3
            cl.outcome(0.1, 0.1)                                    # nothing pending: nothing logged
            assert len((tmp_path / "spiking" / "live_choices.jsonl").read_text().splitlines()) == 1
            ans = await cl.decide(["x y", "z w"])
            cl.followed(ans, 0)
            cl.outcome(None, None)                                  # a stay too short to measure: logged, not learned
            assert (await cl.call("status"))["n_learn"] == 1
            v = cl.view()
            assert v["state"] == "live" and v["decisions_today"] == 2 and v["learned_today"] == 1
            assert "takes part in his choices and learns from simulated reward" in v["card"]
            cl.proc.kill()                                          # the child dies: the vote goes on without it
            await cl.proc.wait()
            await asyncio.sleep(0.2)
            assert "offline" in (await cl.decide(["a", "b"]))["why"] or not cl.ready
        finally:
            await cl.stop()
        assert (tmp_path / "spiking" / "live_weights.npz").exists()
    run(go())


def test_a_slow_child_is_skipped_after_the_timeout_and_never_blocks_the_loop(tmp_path):
    """A child that never answers: decide() gives up after `timeout`; the event loop keeps ticking meanwhile (the
    50 ms brain tick is never delayed by the spiking network)."""
    async def go():
        cl = L.LiveClient(tmp_path, timeout=0.5, python=sys.executable)
        cl.proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "import sys,time\nfor l in sys.stdin: time.sleep(60)",
                                                       stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE)
        cl._reader_task = asyncio.get_running_loop().create_task(cl._read(cl.proc))
        cl.ready = True
        ticks, stop = [], False

        async def ticker():
            while not stop:
                ticks.append(time.perf_counter())
                await asyncio.sleep(0.05)
        tk = asyncio.get_running_loop().create_task(ticker())
        t0 = time.perf_counter()
        ans = await cl.decide(["a", "b", "c"])
        dt = time.perf_counter() - t0
        stop = True
        await tk
        cl.proc.kill()
        await cl.proc.wait()
        assert "slower than 0.5 s" in ans["why"] and 0.45 < dt < 1.0 and cl.slow == 1
        gaps = np.diff(ticks)
        assert len(ticks) >= 8 and gaps.max() < 0.15
        assert V.spiking_term(ans, 3) is None                      # what the vote receives: the term is skipped
    run(go())


# --- the night uses the day ------------------------------------------------------------------------------------------
def _log(tmp_path, rows):
    p = tmp_path / "spiking" / "live_choices.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_day_choices_go_to_the_night_session_with_SUB01_CHOICE(tmp_path):
    from datetime import datetime, timezone
    from spiking import pod_manager as M
    now = datetime(2026, 10, 2, 11, 0, tzinfo=timezone.utc)          # 20:00 Tokyo
    day = "2026-10-02"
    rows = [{"t": 1, "day": day, "labels": ["read bread", "tokyo parks"], "k": 2, "pick": 0, "twin_pick": 1,
             "followed": i % 2, "response": 0.2, "delta": 0.1} for i in range(5)]
    rows += [{"t": 1, "day": "2026-10-01", "labels": ["old", "day"], "k": 2, "pick": 0, "twin_pick": 0, "followed": 0,
              "response": 0.2, "delta": 0.1},
             {"t": 1, "day": day, "labels": ["no", "outcome"], "k": 2, "pick": 0, "twin_pick": 0, "followed": 0,
              "response": None, "delta": None}]
    _log(tmp_path, rows)
    env = {"SUB01_CHOICE": "1", "SUB01_SESSIONS": "daily 21:00-22:00"}
    m = M.PodManager(tmp_path, "http://x", "s" * 32, env=env, clock=lambda: now, api=object())
    cfg = m.session_config(now, 60, now)
    assert len(cfg["choices"]) == 5 and cfg["choices"][0] == {"labels": ["read bread", "tokyo parks"], "followed": 0,
                                                               "delta": 0.1, "response": 0.2}
    assert "choice_train" in cfg["phases"]
    off = M.PodManager(tmp_path, "http://x", "s" * 32, env={"SUB01_SESSIONS": "daily 21:00-22:00"},
                           clock=lambda: now, api=object())
    assert "choices" not in off.session_config(now, 60, now)
    _log(tmp_path, [dict(rows[0], labels=["w" * 80] * 6, k=6) for _ in range(400)])   # the create request stays small
    cfg = m.session_config(now, 60, now)
    assert 0 < len(cfg["choices"]) <= M.MAX_CHOICES and len(json.dumps(cfg["choices"])) <= M.CHOICES_MAX_CHARS


def test_score_compares_with_the_twin_and_chance():
    rows = [{"response": 0.5, "k": 2, "pick": 0, "twin_pick": 1, "followed": 0}] * 10 + \
           [{"response": -0.5, "k": 4, "pick": 0, "twin_pick": 0, "followed": 1}] * 5 + [{"response": None, "k": 3}]
    s = L.score(rows)
    assert s["paid_off"] == 10 and s["decisions_with_outcome"] == 15
    assert s["matched_paid_off"] == {"learned": 1.0, "twin": 0.0, "chance": 0.5}
    assert s["matched_not_paid_off"]["learned"] == 0.0 and s["curve"][0]["n"] == 10


# --- with torch: the same synapses as net.py, and the night's replay ------------------------------------------------
def test_live_net_has_the_synapses_of_net_py():
    torch = pytest.importorskip("torch")
    from spiking.net import SpikingNet
    cfg = Config(n_neurons=SMALL)
    a, b = SpikingNet(cfg, "cpu"), L.LiveNet(cfg)
    assert a.n == b.n and a.D == b.D and a.n_syn == b.n_syn
    assert np.array_equal(a.dst.numpy(), b.dst) and np.array_equal(a.w.numpy(), b.w)
    assert np.array_equal(a.rowptr.numpy(), b.rowptr) and np.array_equal(a.src.numpy(), b.src)
    assert np.array_equal(a.delay.numpy().astype(np.int64) * a.n + a.dst.numpy(), b.slot_off)
    from spiking.memory import MemorySystem
    ch = L.Chooser(b)
    assert np.array_equal(ch.cue("bread"), np.intersect1d(MemorySystem(a, frac=L.WORD_FRAC).word_neurons("bread"),
                                                          ch.cue_space))
    del torch


def test_night_replays_real_choices_on_the_torch_network():
    pytest.importorskip("torch")
    from spiking.choice import RealChoiceTask
    from spiking.net import SpikingNet
    net = SpikingNet(Config(n_neurons=10_000), "cpu")
    rng = np.random.default_rng(0)
    vocab = ["read bread", "tokyo parks", "train timetable", "jazz records"]
    choices = []
    for _ in range(30):
        k = int(rng.integers(2, 5))
        off = list(rng.choice(4, size=k, replace=False))
        fol = int(rng.integers(k))
        r = 0.5 if off[fol] == 0 else -0.5
        choices.append({"labels": [vocab[i] for i in off], "followed": fol, "delta": r, "response": r})
    choices.append({"labels": ["only one"], "followed": 0, "delta": 1.0})          # dropped: not a choice
    task = RealChoiceTask(net, choices)
    task.calibrate()
    frozen = task.replay(learn=False)
    assert not task.net.plast.dw.abs().max() > 0
    learned = task.replay(learn=True)
    assert frozen["choices"] == learned["choices"] == 30 and task.n_learn == 30
    assert float(task.net.plast.dw.abs().max()) > 0
    print(f"\nnight replay (10k, torch CPU, 30 choices): frozen {frozen['matched_paid_off']}, "
          f"learning pass {learned['matched_paid_off']}, chance {frozen['chance']}")
