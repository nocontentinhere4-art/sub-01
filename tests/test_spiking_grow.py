"""Neurogenesis (spiking/growth.py): the day network grows by a daily step, keeps the atlas proportions, wires the new
neurons from their regions' statistics, forms and prunes synapses within a budget, persists and falls back, and
refuses to grow past what fits. numpy only (no torch), small networks (~5k neurons).

    python -m pytest tests/test_spiking_grow.py -q
"""
import asyncio
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import brain_vote as V  # noqa: E402
from spiking import frames  # noqa: E402
from spiking import growth as G  # noqa: E402
from spiking import live as L  # noqa: E402
from spiking.config import Config  # noqa: E402
from spiking.regions import Regions  # noqa: E402

SMALL = 5000


@pytest.fixture(scope="module")
def reg():
    return Regions()


def in_degree(net):
    deg = np.zeros(net.n, dtype=np.int64)
    for x in net.innate:
        np.add.at(deg, x["dst"], 1)
    return deg


# --- the daily step: proportions and the cap ---------------------------------------------------------------------------
def test_daily_step_keeps_the_atlas_proportions_and_stops_at_the_cap(reg):
    add = G.split_by_region(5000, reg)
    assert add.sum() == 5000 and (add >= 0).all() and len(add) == reg.n
    assert np.corrcoef(add, reg.volumes)[0, 1] > 0.99                     # proportional to the regions' volumes
    assert add[np.argmax(reg.volumes)] > add[np.argmin(reg.volumes)]
    assert G.split_by_region(0, reg).sum() == 0
    said = []
    g = G.Growth(Config(n_neurons=SMALL), reg, SMALL, per_day=500, cap=5800, log=said.append)
    add, why = g.plan("2026-10-11")
    assert why is None and add.sum() == 500
    g.record("2026-10-11", add)
    assert g.plan("2026-10-11") == (None, "already grown today") and g.grown == 500 and g.n == 5500
    add, why = g.plan("2026-10-12")
    assert add.sum() == 300 and why is None                              # the cap cuts the step, never passes it
    g.record("2026-10-12", add)
    add, why = g.plan("2026-10-13")
    assert add is None and "at the cap" in why and said[-1].endswith(why)
    g.plan("2026-10-13")
    assert len(said) == 1                                                # a refusal is logged once a day
    add, why = g.plan("2026-10-14", fits=lambda n: None)
    assert add is None and "at the cap" in why and len(said) == 2
    off = G.Growth(Config(n_neurons=SMALL), reg, SMALL, per_day=0, log=said.append)
    assert off.plan("2026-10-11") == (None, "growth off (SUB01_GROW_PER_DAY=0)")
    guard = G.Growth(Config(n_neurons=SMALL), reg, SMALL, per_day=500, cap=10 ** 6, log=said.append)
    assert guard.plan("2026-10-11", fits=lambda n: f"memory: {n} too big")[1] == "memory: 5500 too big"
    assert guard.status("2026-10-11")["growth"]["refused"] == "memory: 5500 too big" and guard.status("2026-10-12")["growth"]["refused"] is None
    assert guard.plan("2026-10-11", fits=lambda n: None)[0].sum() == 500     # the guard says yes later the same day: it grows


# --- the grown network: wiring and rates ---------------------------------------------------------------------------
def test_grown_neurons_get_their_regions_in_degree_and_the_rates_stay_in_range():
    net = L.LiveNet(Config(n_neurons=SMALL))
    base = L.LiveNet(Config(n_neurons=SMALL))
    c = net.cfg
    for b, day_add in enumerate((G.split_by_region(500, net.reg), G.split_by_region(300, net.reg))):
        n_syn = net.grow(day_add, b)
        assert n_syn > 0
    assert net.n == SMALL + 800 and net.n_base == SMALL and len(net.blocks) == 2
    assert net.region_size().sum() == net.n and (net.region_size() >= net.size).all()
    assert net.region_n_exc().sum() == net.is_exc_np.sum()
    frac = (net.is_exc_np[SMALL:]).mean()
    assert 0.75 < frac < 0.85                                            # 80 % excitatory among the grown
    # the base network is untouched: same synapses, same CSR
    for k in ("src", "dst", "w", "delay"):
        assert np.array_equal(getattr(net, k), getattr(base, k))
    assert np.array_equal(net.rowptr[:SMALL + 1], base.rowptr) and (net.rowptr[SMALL:] == base.rowptr[-1]).all()
    assert np.array_equal(net.slot_off, base.delay.astype(np.int64) * net.n + base.dst)   # re-addressed to the new n
    # fixed in-degree from the region's statistics: k_e + k_i + k_long (+ the hippocampal collaterals), no autapses
    deg = in_degree(net)
    grown = np.arange(SMALL, net.n)
    k = c.k_e_local + c.k_i_local + c.k_long
    hc = np.isin(net.region_of_np[grown], list(net.hc_regions))
    assert (deg[grown][~hc] == k).all()
    assert set(deg[grown][hc]) <= {k + c.k_hc_rec, k + c.k_hc_rec_i}
    assert (deg[:SMALL] == 0).all()                                      # new neurons listen first: no innate outputs onto the base
    for x in net.innate:
        src = np.repeat(np.arange(net.n), np.diff(x["rowptr"]))
        assert not (src == x["dst"]).any()
        assert ((x["w"] > 0) == net.is_exc_np[src]).all()                 # E sources excite, I sources inhibit
        assert x["delay"].max() < net.D and x["delay"].min() >= 1
        same = net.region_of_np[src] == net.region_of_np[x["dst"]]
        assert set(np.unique(x["delay"][same])) <= set(range(c.delay_local[0], c.delay_local[1] + 1))
    # long-range sources follow the connectome: the biggest region's top source regions
    x = net.innate[0]
    src = np.repeat(np.arange(net.n), np.diff(x["rowptr"]))
    r = int(np.argmax(net.blocks[0]["size"]))
    sel = (net.region_of_np[x["dst"]] == r) & (net.region_of_np[src] != r) & (x["w"] > 0)
    counts = np.bincount(net.region_of_np[src[sel]], minlength=net.reg.n).astype(float)
    p = net.reg.W[:, r] / net.reg.W[:, r].sum()
    top = np.argsort(-p)[:3]
    assert np.allclose(counts[top] / counts.sum(), p[top], atol=0.05)
    # neurons grown later draw the earlier grown ones as sources (they gain outputs as the region grows)
    src1 = np.repeat(np.arange(net.n), np.diff(net.innate[1]["rowptr"]))
    assert ((src1 >= SMALL) & (src1 < SMALL + 500)).any()
    # a few seconds of simulated time: every population in the asynchronous regime, grown ones included
    net.run(500)
    c0 = net.count.copy()
    net.run(2000)
    d = net.count - c0
    e_base = d[:SMALL][net.is_exc_np[:SMALL]].mean() / 2.0
    e_grown, i_grown = d[grown][net.is_exc_np[grown]].mean() / 2.0, d[grown][~net.is_exc_np[grown]].mean() / 2.0
    print(f"\ngrown 5000+800: base E {e_base:.2f} Hz, grown E {e_grown:.2f} Hz, grown I {i_grown:.2f} Hz")
    assert 1.0 <= e_base <= 15.0 and 1.0 <= e_grown <= 15.0 and 1.0 <= i_grown <= 20.0
    rr = np.bincount(net.region_of_np, weights=d, minlength=net.reg.n) / net.region_size() / 2.0
    assert rr.max() < 30 and rr.min() > 0.3
    # the page's sample places grown neurons in their region, and equals from_ids on the base layout
    ids = np.concatenate([np.arange(0, SMALL, 97), grown[::13]])
    s = frames.Sample.from_layout(ids, net)
    assert np.array_equal(s.region, net.region_of_np[ids]) and (s.slot < 256).all()
    b = frames.Sample.from_ids(ids[ids < SMALL], base.off, base.size)
    s0 = frames.Sample.from_layout(ids[ids < SMALL], base)                 # on the base layout: the same as from_ids
    assert np.array_equal(s.region[ids < SMALL], b.region) and np.array_equal(s0.slot, b.slot)
    assert (s.slot[ids < SMALL] <= b.slot).all()                           # grown: the region is bigger, base ranks keep their order
    rank = net.region_rank(grown)
    assert (rank >= net.size[net.region_of_np[grown]]).all() and (rank < net.region_size()[net.region_of_np[grown]]).all()
    # the twin shares the innate wiring and has no formed synapses
    tw = net.twin()
    assert tw.n == net.n and tw.innate[0] is net.innate[0] and tw.formed is None and tw.n_syn == net.n_syn


# --- the activity rule --------------------------------------------------------------------------------------------
def test_activity_rule_forms_reinforces_decays_and_prunes_within_the_budget():
    net = L.LiveNet(Config(n_neurons=SMALL))
    net.grow(G.split_by_region(400, net.reg), 0)
    g = G.Growth(net.cfg, net.reg, SMALL, per_day=400, cap=10 ** 6, log=lambda *a: None)
    rng = np.random.default_rng(0)
    exc = np.flatnonzero(net.is_exc_np)
    active = np.concatenate([rng.choice(exc[exc < SMALL], 30, replace=False), rng.choice(exc[exc >= SMALL], 10, replace=False)])
    counts = np.zeros(net.n, dtype=np.int64)
    counts[active] = int(G.ACT_HZ * 2) + 10                              # 40 co-active excitatory neurons in a 2 s window
    formed_runs = []
    for _ in range(6):
        st = g.activity(net, counts, 2000, rng)
        formed_runs.append(st["formed"])
        f = g.formed
        assert st["formed"] <= G.FORM_PER_RUN and len(f["src"]) <= len(active) * G.EXTRA_BUDGET
        assert np.isin(f["src"], active).all() and np.isin(f["dst"], active).all() and (f["src"] != f["dst"]).all()
        assert (f["w"] >= G.W_MIN).all() and (f["w"] <= G.W_MAX + 1e-6).all()
        assert np.bincount(f["dst"], minlength=net.n).max() <= G.EXTRA_BUDGET     # the budget per neuron
        assert (f["delay"] >= 1).all() and f["delay"].max() < net.D
        assert np.array_equal(f["src"], np.sort(f["src"]))                 # CSR order
    assert formed_runs[0] > 0 and sum(formed_runs) == g.meta["formed_total"]
    f = g.formed
    assert (f["w"] > G.FORM_W).any()                                     # co-active again: reinforced
    young = np.isin(f["src"], active[active >= SMALL]) | np.isin(f["dst"], active[active >= SMALL])
    assert young.mean() > 0.25                                           # young neurons are favoured (10 of 40, bias x4)
    net.set_formed(f["src"], f["dst"], f["w"], f["delay"])
    n_syn = net.n_syn
    assert net.formed["n"] == len(f["src"]) and n_syn == sum(x["n"] for x in net.innate) + len(net.src) + len(f["src"])
    net.run(50)                                                           # the formed set is delivered too
    # a long silent window: decay below W_MIN and silent sources prune everything
    zero = np.zeros(net.n, dtype=np.int64)
    st = g.activity(net, zero, int(G.PRUNE_SILENT_S * 1000) + 1000, rng)
    assert len(g.formed["src"]) == 0 and st["pruned"] == len(f["src"]) and g.meta["pruned_total"] >= st["pruned"]  # (budget replacements counted too)
    net.set_formed(**g.formed)
    assert net.formed is None and net.n_syn == n_syn - len(f["src"])
    # a weakly co-active pair decays away without reinforcement
    g.activity(net, counts, 2000, rng)
    w0 = g.formed["w"].copy()
    for _ in range(3):
        g.activity(net, zero, 2000, rng)
    assert len(g.formed["w"]) == len(w0) and (g.formed["w"] < w0).all()


# --- persistence and fallbacks ------------------------------------------------------------------------------------------
def test_growth_persists_across_restarts_and_falls_back_on_mismatch_or_corruption(tmp_path):
    said = []
    path = tmp_path / "spiking" / "live_weights.npz"
    a = L.LiveBrain(SMALL, path, twin=True, log=said.append, per_day=300, cap=10 ** 6)
    assert a.growth_path == tmp_path / "spiking" / "growth.npz"
    r1 = a.grow_today("2026-10-11")
    assert r1["added"] == 300 and r1["grow_today"] == 300 and r1["n_neurons"] == SMALL + 300 and a.tw.net.n == SMALL + 300
    assert a.grow_today("2026-10-11")["why"] == "already grown today"
    r2 = a.grow_today("2026-10-12")
    assert r2["added"] == 300 and r2["grown"] == 600 and a.growth_path.exists()
    assert len(a.ch.action) > len(L.Chooser(L.LiveNet(Config(n_neurons=SMALL))).action)   # the pools include grown striatum
    assert np.array_equal(a.tw.net.w[a.ch.pidx], a.ch.w0)                 # the twin never learned
    for i in range(3):
        a.decide(["read about bread", "tokyo parks"], did=i)
        a.learn(i, 0, 0.4)
    # some formed synapses, written with the file
    rng = np.random.default_rng(1)
    counts = np.zeros(a.net.n, dtype=np.int64)
    counts[rng.choice(np.flatnonzero(a.net.is_exc_np), 40, replace=False)] = 60
    a.growth.activity(a.net, counts, 2000, rng)
    assert len(a.growth.formed["src"]) > 0
    a.save_growth()
    st = a.status()
    assert st["n_neurons"] == SMALL + 600 and st["grown"] == 600 and st["synapses"] == a.net.n_syn and st["cap"] == 10 ** 6
    assert st["growth"]["blocks"] == 2 and st["growth"]["formed"] == len(a.growth.formed["src"])
    assert st["grow_today"] == 0                                          # (today is not 2026-10-12)
    b = L.LiveBrain(SMALL, path, twin=True, log=said.append, per_day=300, cap=10 ** 6)
    assert b.net.n == SMALL + 600 and b.growth.days == ["2026-10-11", "2026-10-12"] and b.n_learn == 3
    for x, y in zip(a.net.innate, b.net.innate):
        assert np.array_equal(x["dst"], y["dst"]) and np.array_equal(x["w"], y["w"]) and np.array_equal(x["delay"], y["delay"])
    assert np.array_equal(a.net.region_of_np, b.net.region_of_np) and np.array_equal(a.net.is_exc_np, b.net.is_exc_np)
    fa, fb = a.growth.formed, b.growth.formed
    assert np.array_equal(fa["src"], fb["src"]) and np.array_equal(fa["dst"], fb["dst"]) and np.allclose(fa["w"], fb["w"], atol=1e-3)
    assert b.net.formed["n"] == len(fb["src"]) and b.tw.net.formed is None
    assert np.array_equal(a.net.w, b.net.w)                              # the learned base weights load as before
    assert b.grow_today("2026-10-12")["why"] == "already grown today"     # the day survives the restart
    assert not list(path.parent.glob("*.tmp"))
    # the growth file for another base network: kept aside, the base network runs, said once
    n0 = len(said)
    c = L.LiveBrain(SMALL + 100, path, twin=False, log=said.append, per_day=300, cap=10 ** 6)
    assert c.net.n == SMALL + 100 and c.growth.grown == 0 and list(path.parent.glob("growth.npz.other-*"))
    assert len(said) == n0 + 2 and "another base network" in said[n0]      # (the weights file is for another network too)
    assert not c.growth_path.exists()
    # a torn file: kept aside, the base network runs
    a.growth.save(a.growth_path)
    a.growth_path.write_bytes(a.growth_path.read_bytes()[:120])
    n0 = len(said)
    d = L.LiveBrain(SMALL, path, twin=False, log=said.append, per_day=300, cap=10 ** 6)
    assert d.net.n == SMALL and list(path.parent.glob("growth.npz.corrupt-*")) and "unreadable" in said[n0]
    # growth off: the message says so and nothing changes
    e = L.LiveBrain(SMALL, None, twin=False, log=said.append, per_day=0)
    assert e.grow_today("2026-10-11")["why"].startswith("growth off") and e.net.n == SMALL
    # the file stays compact: a ledger, not synapses (the innate wiring is regenerated)
    a.growth.save(a.growth_path)
    assert a.growth_path.stat().st_size < 50_000 + 11 * len(a.growth.formed["src"])


# --- the cost guard ------------------------------------------------------------------------------------------------------
def test_cost_guard_refuses_what_does_not_fit():
    assert G.fit_reason(500_000, 505_000) is None                         # nothing measured: not held against the step
    assert G.fit_reason(500_000, 500_000, rss=1e9, room=0) is None        # no growth asked
    assert G.fit_reason(500_000, 505_000, rss=1.0e9, room=1.0e9) is None  # +1 % of 1 GB x 1.3 = 13 MB: fits
    why = G.fit_reason(500_000, 505_000, rss=1.0e9, room=5e6)
    assert why.startswith("memory:") and "505,000" in why
    assert G.fit_reason(500_000, 505_000, ms_per_ms=0.5, deadline_s=2.0, twin=True) is None   # 2 x 350 x 0.5 x 1.01 = 0.35 s
    why = G.fit_reason(500_000, 505_000, ms_per_ms=2.5, deadline_s=2.0, twin=True)             # 1.77 s > 80 % of 2 s
    assert why.startswith("time:") and "deadline" in why
    assert G.fit_reason(500_000, 505_000, ms_per_ms=2.5, deadline_s=2.0, twin=False) is None   # the learner alone fits
    assert G.gpu_fit_reason(1_000_000, "NVIDIA RTX A4000") is None
    assert G.gpu_fit_reason(2_500_000, "NVIDIA RTX A4000").startswith("memory:")     # 14.3 GB > 80 % of 16 GB
    assert G.gpu_fit_reason(2_000_000, "NVIDIA RTX A4000") is None                   # 11.4 GB of 12.8 allowed, 0.62x real time
    assert G.gpu_fit_reason(2_000_000, "NVIDIA A40") is None
    assert G.gpu_fit_reason(3_500_000, "NVIDIA A40").startswith("time:")             # 1.52x / 3.5 < 0.5x real time
    assert G.gpu_fit_reason(1_000_000, "NVIDIA L4").startswith("time:")
    assert G.gpu_fit_reason(1_000_000, "unknown GPU") is None
    assert G.mem_room_bytes() is None or G.mem_room_bytes() > -1e12
    assert G.own_rss_bytes() is None or G.own_rss_bytes() > 1e6


# --- the child process: the server's grow message at his wake-up, the card's fields -----------------------------------
def test_child_grows_once_a_day_on_the_servers_wake_message(tmp_path, monkeypatch):
    monkeypatch.setenv("SUB01_GROW_PER_DAY", "200")
    monkeypatch.setenv("SUB01_NEURONS_MAX", "5300")

    async def go():
        cl = L.LiveClient(tmp_path, n_neurons=SMALL)
        assert cl.on_stage("AWAKE") is None and cl.grow_day is None       # not ready: nothing sent
        cl.stage = None
        await cl.start()
        try:
            for _ in range(600):
                if cl.ready:
                    break
                await asyncio.sleep(0.1)
            assert cl.ready and cl.info["n_neurons"] == SMALL and cl.info["grown"] == 0 and cl.info["cap"] == 5300
            cl.on_stage("NREM")
            assert cl.grow_day is None                                    # asleep: never grows
            cl.on_stage("AWAKE")
            assert cl.grow_day == L._today()
            for _ in range(300):
                if cl.info.get("grown"):
                    break
                await asyncio.sleep(0.1)
            assert cl.info["grown"] == 200 and cl.info["grow_today"] == 200 and cl.info["n_neurons"] == SMALL + 200
            assert cl.info["synapses"] > 0 and cl.info["growth"]["blocks"] == 1
            assert cl.on_stage("AWAKE") is None and cl.grow(force=False) is False   # once a day from the server
            st = await cl.call("status")
            assert st["n_neurons"] == SMALL + 200 and st["grown"] == 200 and st["grow_per_day"] == 200
            ans = await cl.decide(["read about bread", "tokyo parks"], did="b-1")
            assert ans["n_neurons"] == SMALL + 200                        # the size reported follows the grown network
            assert V.network_label("cpu", ans["n_neurons"]) == "5k-neuron network on CPU"
            cl.send({"type": "grow", "id": "again", "day": L._today()})     # the child refuses a second step today
            await asyncio.sleep(0.5)
            assert cl.info["grown"] == 200
            b = V.Backend(cpu=cl, log=L.DecisionLog(tmp_path))
            v = L.view(b)
            assert v["n_neurons"] == SMALL + 200 and v["grown"] == 200 and v["grow_today"] == 200 and v["cap"] == 5300
            assert v["synapses"] == cl.info["synapses"] and v["grow_per_day"] == 200 and v["growth"]["blocks"] == 1
            assert "5,200 neurons" in v["card"]
        finally:
            await cl.stop()
        assert (tmp_path / "spiking" / "growth.npz").exists()
    asyncio.run(go())
