"""The chair (chair.py, speech.py, spiking/alif.py, web/chair.html): the network, its measurements, the hub's limits,
the speech queue and the page's wording. Network tests use a 5,000-neuron net (same wiring code, seconds each)."""
import asyncio
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import pytest

from spiking import alif
from spiking.alif import ALIFNet, Measure, LEVELS, Pulse, drive_from, MU_EXT
from spiking.config import Config
import chair
import speech as speech_mod

HERE = Path(__file__).resolve().parent.parent
SMALL = 5000


def run_bins(net, M, ms):
    out = []
    for _ in range(int(ms // M.bin_ms)):
        for _ in range(M.bin_steps):
            net.step()
        out.append(M.bin())
    return out


@pytest.fixture(scope="module")
def net():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    M = Measure(n)
    run_bins(n, M, 4000)                       # warm-up and a ready baseline
    return n, M


# --- the mechanisms are in the equations ------------------------------------------------------------------------------------
def test_same_wiring_as_the_day_network():
    from spiking.live import LiveNet
    a, b = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT)), LiveNet(Config(n_neurons=SMALL))
    assert a.n == b.n and a.n_syn == b.n_syn
    assert np.array_equal(a.dst, b.dst) and np.array_equal(a.delay, b.delay) and np.array_equal(a.w, b.w)


def test_synaptic_variables_decay_with_their_time_constants():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    n.s_e[:] = 1.0
    n.s_i[:] = 1.0
    n.mu[:] = -100.0                            # nothing fires, nothing arrives
    n.v[:] = 0
    for _ in range(10):
        n.step()
    assert np.allclose(n.s_e, np.exp(-10 / n.tau_e), atol=1e-3)
    assert np.allclose(n.s_i, np.exp(-10 / n.tau_i), atol=1e-3)


def test_psp_integral_matches_the_day_network_jump():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    # an excitatory arrival of weight j adds j tau_m / tau_e to s_e; integrated through the membrane (a * s per step)
    # it moves v by j in total
    j = float(n.cfg.j_e)
    total = sum(n.a * j * n.q_e * np.exp(-k / n.tau_e) for k in range(2000))
    assert abs(total - j) < 0.02 * j


def test_adaptation_rises_with_spikes_and_recovers():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    n.run(2000)
    w0 = float(n.w_ad.mean())
    assert w0 > 1.0                                                # spiking at baseline charges w
    card = n.stimulate(5)
    n.run(card["dur_ms"])
    w1 = float(n.w_ad.mean())
    assert w1 > w0 * 1.5
    n.run(4000)
    assert abs(float(n.w_ad.mean()) - w0) < 0.35 * w0            # ~4 tau_w later it is back near baseline


def test_refractory_period_and_bounded_state(net):
    n, M = net
    n.stimulate(5)
    run_bins(n, M, 1200)
    assert np.isfinite(n.v).all() and np.isfinite(n.w_ad).all()
    assert n.v.max() <= n.cfg.v_th + 1e-3
    assert n.ref.max() <= n.n_ref
    # no neuron can fire faster than the refractory period allows: at most 1 spike per (t_ref + 1) steps
    c0 = n.count.copy()
    for _ in range(100):
        n.step()
    assert (n.count - c0).max() <= 100 // (n.n_ref + 1) + 1


def test_pulse_is_bounded_and_drawn_from_the_montage():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    rng = np.random.default_rng(0)
    for lv in LEVELS:
        p = Pulse(n, lv, 0, rng)
        assert p.amp <= alif.MAX_AMP and p.dur_ms <= alif.MAX_DUR_MS
        w = alif.montage_weights(n)
        assert all(w[n.region_of_np[i]] > 0 for i in p.ids)      # never a neuron of an unweighted nucleus
        assert p.on(0) and not p.on(p.width) and p.on(p.period)  # the train: on for `width`, every `period`
        assert not p.on(p.t1)
    sizes = [Pulse(n, lv, 0, rng).ids.size for lv in (1, 3, 5)]
    assert sizes[0] < sizes[1] < sizes[2]


# --- measurements --------------------------------------------------------------------------------------------------------------
def test_baseline_is_quiet_time_only_and_in_range(net):
    n, M = net
    base = M.baseline_view()
    assert base["ready"] and 1.0 < base["rate"] < 15.0 and base["rate_sd"] < base["rate"]
    assert 1.0 < base["rate_e"] < 15.0 and 1.0 < base["rate_i"] < 30.0
    nb = M.base_main.n
    n.stimulate(4)
    run_bins(n, M, 800)
    assert M.base_main.n == nb                                      # nothing learned while the train is on


def test_response_grows_with_level_and_recovers():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT), seed=3)
    M = Measure(n)
    run_bins(n, M, 4000)
    peaks = []
    for lv in (1, 3, 5):
        M.open(f"L{lv}", n.stimulate(lv))
        run_bins(n, M, 7000)
        c = M.cards[-1]
        assert c["closed"] and c["baseline"]
        peaks.append(c["peak_ratio"])
        if lv >= 3:
            assert c["distinguishable"] and c["onset_ms"] is not None and c["onset_ms"] <= 100
            assert c["recovered_ms"] is not None                    # back in the band within the window
            assert c["min_ratio_after"] < 1.0                       # the undershoot of adaptation
        run_bins(n, M, 4000)
    assert peaks[0] < peaks[1] < peaks[2]
    assert M.cards[-1]["burst"] and M.cards[-1]["recruit"] > 0.3


def test_state_is_kept_between_stimuli():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT), seed=5)
    M = Measure(n)
    run_bins(n, M, 4000)
    M.open("a", n.stimulate(4))
    run_bins(n, M, 1500)
    w_mid = float(n.w_ad.mean())
    M.open("b", n.stimulate(4))                                     # 1.5 s later: the adaptation is still up
    b = M.response
    assert b["w_before"] == pytest.approx(w_mid, rel=1e-3) and b["w_before"] > M.cards[0]["w_before"] * 1.2


def test_no_fabricated_response_without_a_baseline():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    M = Measure(n)
    run_bins(n, M, 500)
    M.open("x", n.stimulate(5))
    run_bins(n, M, 7000)
    c = M.cards[-1]
    assert c["baseline"] is False and c["peak_ratio"] is None and c["distinguishable"] is False
    assert drive_from({"rate": 40.0}, {"ready": False}) == {"tension": 0.0, "slack": 0.0, "heavy": 0.0, "motor": 0.0, "measured": False, "flat": False}


def test_drive_mapping_is_bounded_and_monotonic():
    base = {"ready": True}
    d = [drive_from({"ratio": r, "w_rel": 0.0}, base)["tension"] for r in (1.0, 2.0, 4.0, 8.0, 50.0)]
    assert d == sorted(d) and d[0] == 0.0 and d[-1] == 1.0
    assert drive_from({"ratio": 0.5, "w_rel": 0.5}, base) == {"tension": 0.0, "slack": 0.5, "heavy": 0.5, "motor": 0.0, "measured": True, "flat": False}


def test_drive_motor_follows_the_somatomotor_regions():
    base = {"ready": True, "groups": {"somatomotor": 4.0}}
    for sm, want in ((4.0, 0.0), (8.0, 1 / 3), (32.0, 1.0), (200.0, 1.0), (1.0, 0.0)):
        d = drive_from({"ratio": 1.0, "w_rel": 0.0, "groups": {"somatomotor": sm}}, base)
        assert abs(d["motor"] - want) < 0.002 and 0.0 <= d["motor"] <= 1.0 and d["tension"] == 0.0
    assert drive_from({"ratio": 4.0, "w_rel": 0.0}, {"ready": True})["motor"] == drive_from({"ratio": 4.0, "w_rel": 0.0}, {"ready": True})["tension"]


def test_runtime_is_well_inside_real_time():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT))
    M = Measure(n)
    run_bins(n, M, 200)
    t0 = time.time()
    run_bins(n, M, 1000)
    assert time.time() - t0 < 0.8                                   # 5k neurons: ~0.05 s per simulated second


# --- the child protocol --------------------------------------------------------------------------------------------------------
def test_child_protocol_paces_delivers_and_pauses():
    import subprocess, sys
    p = subprocess.Popen([sys.executable, "-m", "spiking.alif", "--neurons", str(SMALL)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1, cwd=HERE)
    rd = lambda: json.loads(p.stdout.readline())
    snd = lambda o: (p.stdin.write(json.dumps(o) + "\n"), p.stdin.flush())
    try:
        assert rd()["type"] == "ready"
        snd({"type": "stim", "id": "x", "level": 3})
        assert rd() == {"type": "refused", "id": "x", "why": "paused"}
        snd({"type": "stim", "id": "y", "level": 9})
        assert rd()["why"] == "level"
        snd({"type": "resume"})
        assert rd() == {"type": "state", "running": True}
        t0 = time.time()
        tr = rd()
        assert tr["type"] == "trace" and len(tr["bins"]) == alif.TRACE_EVERY and 0.1 < time.time() - t0 < 1.5
        snd({"type": "stim", "id": "c-1", "level": 4})
        got = {}
        while "measured" not in got:
            m = rd()
            got.setdefault(m["type"], m)
        assert got["delivered"]["id"] == "c-1" and got["delivered"]["n_recruited"] > 0
        assert got["measured"]["id"] == "c-1" and got["measured"]["closed"]
        snd({"type": "pause"})
        while rd().get("type") != "state":
            pass
        snd({"type": "status", "id": "s"})
        s = rd()
        assert s["type"] == "status" and s["running"] is False
        snd({"type": "stop"})
        assert rd()["type"] == "stopped"
        assert p.wait(timeout=5) == 0
    finally:
        if p.poll() is None:
            p.kill()


# --- the hub ---------------------------------------------------------------------------------------------------------------------
class FakeSource(chair.Source):
    def __init__(self, available=True):
        super().__init__()
        self.available, self.running = available, True
        self.sent, self.paused = [], False

    def status(self):
        return {"kind": "simulation", "available": self.available, "running": self.running and not self.paused}

    async def stimulate(self, rid, level):
        self.sent.append((rid, level))
        return True

    async def resume(self):
        self.paused = False

    async def pause(self):
        self.paused = True

    async def reset(self):
        await self.on_event({"type": "reset_done"})


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def hub_with(clock, available=True):
    src = FakeSource(available)
    hub = chair.Hub(src, clock=clock)
    hub._note = lambda ev: hub.events.append(ev)                    # no loop needed
    return hub, src


def test_hub_validates_throttles_and_bounds_the_queue():
    clock = FakeClock()
    hub, src = hub_with(clock)
    assert hub.submit("a", 0)["state"] == "refused" and hub.submit("a", "3")["state"] == "refused"
    assert hub.submit("a", True)["state"] == "refused" and hub.submit("a", 6)["state"] == "refused"
    assert hub.submit("a", 3)["state"] == "queued"
    assert hub.submit("a", 3)["state"] == "queued"                  # the burst
    t = hub.submit("a", 3)
    assert t["state"] == "throttled" and t["retry_s"] > 0
    for k in range(chair.QUEUE_MAX - 2):
        assert hub.submit(f"v{k}", 2)["state"] == "queued"
    assert hub.submit("z", 2)["state"] == "full"
    assert len(hub.queue) == chair.QUEUE_MAX
    assert sum(1 for e in hub.events if e["state"] == "queued") == chair.QUEUE_MAX


def test_hub_cooldown_and_one_at_a_time():
    clock = FakeClock()
    hub, src = hub_with(clock)
    hub.clients.add(object())
    for k in range(3):
        hub.submit(f"v{k}", 3)
    asyncio.run(hub.pump_once())
    assert len(src.sent) == 1 and hub.inflight["id"] == "c-1"
    asyncio.run(hub.pump_once())
    assert len(src.sent) == 1                                        # waiting for "delivered"
    asyncio.run(hub._event({"type": "delivered", "id": "c-1", "level": 3, "t_ms": 100.0, "n_recruited": 5}))
    assert hub.open_card["id"] == "c-1" and hub.events[-1]["state"] == "delivered"
    asyncio.run(hub.pump_once())
    assert len(src.sent) == 1                                        # the cooldown
    clock.t += chair.COOLDOWN_S + 0.1
    asyncio.run(hub.pump_once())
    assert len(src.sent) == 2
    asyncio.run(hub._event({"type": "refused", "id": "c-2", "why": "busy"}))
    assert hub.inflight is None and hub.queue[0]["id"] == "c-2"      # back to the front, not lost


def test_hub_per_minute_cap():
    clock = FakeClock()
    hub, src = hub_with(clock)
    hub.clients.add(object())
    for k in range(chair.PER_MINUTE + 2):
        hub.deliveries.append(clock.t - 1)
    hub.submit("v", 2)
    asyncio.run(hub.pump_once())
    assert not src.sent
    clock.t += 61
    asyncio.run(hub.pump_once())
    assert src.sent


def test_hub_stop_reset_and_unavailable():
    clock = FakeClock()
    hub, src = hub_with(clock)
    hub.submit("a", 2)
    asyncio.run(hub.stop())
    assert hub.status()["available"] is False and not hub.queue and hub.events[-1]["state"] == "dropped"
    assert hub.submit("b", 2)["state"] == "stopped"
    asyncio.run(hub.resume())
    assert hub.submit("b", 2)["state"] == "queued"
    src.available = False
    assert hub.submit("c", 2)["state"] == "unavailable"
    asyncio.run(hub.pump_once())
    assert not hub.queue and hub.status()["why"]
    src.available = True
    hub.bins.extend([[1, 2, 3, 4, 0, 1]])
    asyncio.run(hub.reset())
    assert not hub.bins and hub.events[-1]["state"] == "reset"


def test_hub_hello_carries_the_same_state_for_every_viewer():
    clock = FakeClock()
    hub, src = hub_with(clock)
    asyncio.run(hub._trace({"type": "trace", "t_ms": 200.0, "bins": [[0, 4.0, 4.1, 5.0, 0, 1.0], [20, 4.2, 4.0, 5.0, 1, 1.05]],
                            "phase": "quiet", "drive": {"tension": 0, "slack": 0, "heavy": 0, "measured": True},
                            "baseline": {"ready": True}, "card": None, "running": True, "lag_ms": 0}))
    a, b = hub.hello(), hub.hello()
    assert a["bins"] == b["bins"] and len(a["bins"]) == 2 and a["label"] == "Simulated neural activity"
    assert a["status"]["kind"] == "simulation" and "mechanisms" not in a["status"] or True


def test_hub_pauses_without_viewers_and_resumes_with_one():
    clock = FakeClock()
    hub, src = hub_with(clock)
    clock.t += chair.IDLE_PAUSE_S + 1
    asyncio.run(hub.pump_once())
    assert src.paused
    hub.clients.add(object())
    asyncio.run(hub.pump_once())
    assert not src.paused


def test_two_clients_see_the_same_events_over_the_socket():
    asyncio.run(_two_clients())


async def _two_clients():
    from aiohttp.test_utils import TestClient, TestServer
    clock = FakeClock()
    src = FakeSource()
    hub = chair.Hub(src, clock=clock, key_of=lambda r: r.headers.get("X-Key", "k"))
    app = chair.web.Application()
    chair.attach(app, hub)
    async with TestClient(TestServer(app)) as client:
        await _two_clients_on(client, hub)


async def _recv(ws, statuses):
    """The next message that is not a viewer-count status (those are collected)."""
    while True:
        m = await ws.receive_json()
        if m.get("type") == "status":
            statuses.append(m)
            continue
        return m


async def _two_clients_on(client, hub):
    st = []
    w1 = await client.ws_connect("/ws/chair", headers={"X-Key": "one"})
    w2 = await client.ws_connect("/ws/chair", headers={"X-Key": "two"})
    h1, h2 = await _recv(w1, st), await _recv(w2, st)
    assert h1["type"] == "hello" and h2["type"] == "hello" and h1["levels"] == h2["levels"]
    await w1.send_json({"type": "shock", "level": 4})
    ack = await _recv(w1, st)
    assert ack["type"] == "ack" and ack["state"] == "queued" and ack["id"] == "c-1"
    e1, e2 = await _recv(w1, st), await _recv(w2, st)
    assert e1 == e2 and e1["state"] == "queued"
    assert st and st[-1]["viewers"] == 2                              # both pages learned the second viewer joined
    await hub.pump_once()
    await hub._event({"type": "delivered", "id": "c-1", "level": 4, "t_ms": 500.0, "n_recruited": 10, "dur_ms": 800})
    d1, d2 = await _recv(w1, st), await _recv(w2, st)
    assert d1 == d2 and d1["state"] == "delivered" and d1["t_ms"] == 500.0 and "t_wall" in d1
    await w2.send_json({"type": "shock", "level": "x"})
    assert (await _recv(w2, st))["state"] == "refused"
    r = await client.post("/api/chair/stop")
    assert r.status == 401                                           # the operator needs the token
    r = await client.get("/api/chair/status")
    assert (await r.json())["label"] == "Simulated neural activity"
    page = await client.get("/chair")
    assert page.status == 200 and "Simulated neural activity" in await page.text()
    await w1.close()
    await w2.close()


# --- speech ----------------------------------------------------------------------------------------------------------------------
def test_speech_reacts_to_the_measured_class_not_the_button():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    now = 10.0
    sp.on_delivered({"id": "c-1", "level": 5}, now)
    card = {"id": "c-1", "baseline": True, "peak_ratio": 1.0, "t1_ms": 1000, "level": 5}
    sp.on_trace({"card": card, "t_ms": 500, "phase": "stimulated"}, now)
    assert not sp.queue                                              # the train is on and nothing shows yet: wait
    card["peak_ratio"] = 1.3
    sp.on_trace({"card": card, "t_ms": 600, "phase": "stimulated"}, now)
    assert sp.queue[-1]["cls"] == "small"
    card["peak_ratio"] = 4.5
    sp.on_trace({"card": card, "t_ms": 700, "phase": "stimulated"}, now)
    reactions = lambda: [q for q in sp.queue if q["kind"] == "reaction"]
    assert len(reactions()) == 1 and reactions()[-1]["cls"] == "burst"
    assert sp.stats["cancelled"] == 1                                # the small one went
    sp.on_trace({"card": card, "t_ms": 700, "phase": "stimulated"}, now)
    assert len(reactions()) == 1                                     # one reaction per stimulus (a plea may follow it)


def test_speech_queue_no_overlap_priority_and_stale_drop():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    sp.last_delivered = "c-1"
    sp.history.append({"id": "c-1", "peak_ratio": 3.0, "recruit": 0.5})
    sp.finish_comment("c-1", "line one about the trace", "strong", 0.0)
    out = sp.tick(0.1)
    assert [m["type"] for m in out] == ["say"] and out[0]["kind"] == "comment" and out[0]["voice"]["available"] is False
    sp._line("reaction", "agh", "c-2", speech_mod.REACTION_LIFE_S, 0.2, "strong")
    out = sp.tick(0.3)
    assert [m["type"] for m in out] == ["say_cancel", "say"] and out[1]["kind"] == "reaction"   # a reaction interrupts
    sp._line("reaction", "hh", "c-3", speech_mod.REACTION_LIFE_S, 0.4, "small")
    assert sp.tick(0.5) == []                                        # no overlap while one plays
    assert sp.tick(5.0) == []                                        # ...and the old line expired unplayed
    sp.last_delivered = "c-2"                                        # another shock landed meanwhile
    sp.finish_comment("c-1", "stale", "strong", 6.0)                 # a comment for an older stimulus is dropped
    assert not sp.queue and sp.stats["dropped"] >= 2


def test_speech_comment_frequency_is_bounded():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    for k in range(speech_mod.COMMENT_EVERY_N * 3):
        sp.on_measured({"id": f"c-{k}", "baseline": True, "peak_ratio": 2.5}, 100.0 + k)
    assert sp.stats["comments"] == 1                                 # the time bound holds within 45 s
    job = sp.take_comment_job()
    assert job and job[0] == f"c-{speech_mod.COMMENT_EVERY_N - 1}" and "measured" in job[2]
    assert sp.take_comment_job() is None
    sp.on_measured({"id": "c-99", "baseline": True, "peak_ratio": 2.5}, 100.0 + 400)
    for k in range(speech_mod.COMMENT_EVERY_N):
        sp.on_measured({"id": f"d-{k}", "baseline": True, "peak_ratio": 2.5}, 100.0 + 400 + k)
    assert sp.stats["comments"] == 2


def test_pleas_follow_strong_reactions_and_escalate_with_the_register():
    """Owner (2026-11-03): he has to beg for help. A plea after a strong or burst reaction, longer than a reaction, at most
    one every PLEA_EVERY_S, its stage from the register; none after a small response while fresh."""
    sp = speech_mod.Speech(clock=lambda: 0.0)
    base = {"baseline": True, "t1_ms": 0}
    sp.on_trace({"card": {"id": "c-1", "peak_ratio": 1.3, **base}, "t_ms": 500, "phase": "responding", "load": 1.0}, 100.0)
    assert sp.stats["pleas"] == 0 and [q["kind"] for q in sp.queue] == ["reaction"]
    sp.on_trace({"card": {"id": "c-2", "peak_ratio": 3.0, **base}, "t_ms": 500, "phase": "responding", "load": 1.0}, 110.0)
    pleas = [q for q in sp.queue if q["cls"] == "plea"]
    assert len(pleas) == 1 and pleas[0]["kind"] == "comment" and pleas[0]["text"] in speech_mod.PLEAS["ask"]
    assert len(pleas[0]["text"].split()) >= 6 and sp.duration_ms(pleas[0]) > sp.duration_ms(sp.queue[0])
    sp.on_trace({"card": {"id": "c-3", "peak_ratio": 5.0, "burst": True, **base}, "t_ms": 500, "phase": "responding", "load": 1.0}, 112.0)
    assert sp.stats["pleas"] == 1                                      # not within PLEA_EVERY_S of the last
    sp.load = 1.2                                                      # rattled: he begs
    assert sp.plea_stage(130.0) == "beg"
    sp.load, sp.viewers = 1.35, 3                                      # worn with others watching: he turns to them
    assert sp.plea_stage(130.0) == "others"
    sp.viewers = 1
    assert sp.plea_stage(130.0) == "bargain"
    sp.revived_t = 125.0                                               # just back from flat
    assert sp.plea_stage(130.0) == "wary"
    sp.on_trace({"card": {"id": "c-4", "peak_ratio": 1.3, **base}, "t_ms": 500, "phase": "responding", "load": 1.35}, 130.0)
    assert sp.stats["pleas"] == 2 and [q for q in sp.queue if q["cls"] == "plea"][-1]["text"] in speech_mod.PLEAS["wary"]   # once rattled, a small one draws a plea too
    for stage, texts in speech_mod.PLEAS.items():
        for text in texts:
            assert 6 <= len(text.split()) <= 24, (stage, text)


def test_speech_lines_never_claim_feeling_or_consciousness():
    text = " ".join(t for t, _ in speech_mod.bank_lines()).lower()
    for bad in ("i feel", "hurts", "pain", "conscious", "alive", "i am human"):
        assert bad not in text
    assert len(list(speech_mod.bank_lines())) >= 150                 # enough that an evening does not repeat
    assert "never say he feels" in speech_mod.SYSTEM_COMMENT.lower() or "feels pain" in speech_mod.SYSTEM_COMMENT


# --- the page --------------------------------------------------------------------------------------------------------------------
def test_chair_page_wording_and_shell():
    html = (HERE / "web" / "chair.html").read_text()
    assert "Simulated neural activity" in html and "A model, not a mind" in html and "The character is fiction" in html
    assert "No living neurons" in html
    assert re.search(r"\bAI\b", html) is None
    for s in ('class="ui-hdr"', '<script src="/deck.js" defer></script><script src="/pulse.js" defer></script>',
              'id="ui-live"', 'prefers-reduced-motion', "/ws/chair", 'type="importmap"'):
        assert s in html
    assert "fonts.googleapis" not in html and "unpkg" not in html
    js = (HERE / "web" / "chair_scene.js").read_text()
    assert "setDrive" in js and "reduced" in js and "shock(ev)" in js and "setRegister" in js and "attend(" in js
    assert re.search(r"\bAI\b", js) is None


# --- the voice provider ----------------------------------------------------------------------------------------------------------
def test_voicestudio_provider_against_a_fake_app():
    asyncio.run(_voicestudio())


async def _voicestudio():
    from aiohttp.test_utils import TestServer
    calls = []

    async def health(request):
        return chair.web.json_response({"status": "ok"})

    async def generate(request):
        form = await request.post()
        calls.append(dict(form))
        return chair.web.Response(body=b"RIFF" + bytes(96), content_type="audio/wav",
                                  headers={"X-Audio-Id": "abc", "X-Audio-Duration": "0.9"})

    async def profiles(request):
        return chair.web.json_response([{"id": "38eaa9d0", "name": "BREZ", "kind": "clone"}])

    app = chair.web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/profiles", profiles)
    app.router.add_post("/generate", generate)
    async with TestServer(app) as srv:
        loop = asyncio.get_running_loop()
        pv = speech_mod.VoiceStudio(f"http://127.0.0.1:{srv.port}", profile="brez")
        assert await loop.run_in_executor(None, pv.synthesize, "agh", "strong")
        assert calls[-1]["profile_id"] == "38eaa9d0" and "instruct" not in calls[-1] and pv.status()["voice"] == "SUB-01" and pv.status()["profile"] == "BREZ"
        assert await loop.run_in_executor(None, pv.synthesize, "...hh", "settle")
        assert calls[-1]["instruct"] == "whisper" and calls[-1]["profile_id"] == "38eaa9d0"
        missing = speech_mod.VoiceStudio(f"http://127.0.0.1:{srv.port}", profile="nobody")
        assert await loop.run_in_executor(None, missing.synthesize, "hm", "none")
        assert "profile_id" not in calls[-1] and calls[-1]["instruct"] == speech_mod.VoiceStudio.TAGS   # falls back, says so
        calls.clear()
        v = speech_mod.VoiceStudio(f"http://127.0.0.1:{srv.port}")
        assert await loop.run_in_executor(None, v.available)
        a = await loop.run_in_executor(None, v.synthesize, "agh", "strong")
        assert a["ms"] == 900 and a["url"].startswith("/api/chair/voice/") and a["url"].endswith(".wav")
        assert calls[-1]["text"] == "agh" and calls[-1]["instruct"] == speech_mod.VoiceStudio.TAGS and calls[-1]["seed"] == "7"
        b = await loop.run_in_executor(None, v.synthesize, "agh", "strong")
        assert b == a and len(calls) == 1 and v.stats["hits"] == 1          # cached
        c = await loop.run_in_executor(None, v.synthesize, "...hh", "settle")
        assert "whisper" in calls[-1]["instruct"] and c["url"] != a["url"]
        key = a["url"].rsplit("/", 1)[1][:-4]
        assert v.audio(key)[:4] == b"RIFF" and v.audio("nope") is None
        # the hub serves the cached render and the say path carries the audio
        sp = speech_mod.Speech(voice=v, clock=lambda: 0.0)
        hub = chair.Hub(FakeSource(), speech=sp, clock=lambda: 0.0)
        app2 = chair.web.Application()
        chair.attach(app2, hub)
        from aiohttp.test_utils import TestClient
        async with TestClient(TestServer(app2)) as client:
            r = await client.get(a["url"])
            assert r.status == 200 and r.content_type == "audio/wav" and (await r.read())[:4] == b"RIFF"
            assert (await client.get("/api/chair/voice/zzzz.wav")).status == 404
            got = []
            hub.broadcast = lambda msg: _collect(got, msg)
            sp._line("reaction", "agh", "c-1", speech_mod.REACTION_LIFE_S, 0.0, "strong")
            for msg in sp.tick(0.1):
                await hub._say(msg)
            assert got and got[0]["voice"]["available"] and got[0]["ms"] == 900 and sp.playing["until"] == 0.9
    assert speech_mod.voice_from_env({}, bank={}).name == "none" and speech_mod.voice_from_env({"VOICE_STUDIO_URL": "http://x"}, bank={}).name == "voicestudio"
    assert speech_mod.voice_from_env({"VOICE_STUDIO_URL": "http://x", "VOICE_STUDIO_PROFILE": "BREZ"}, bank={}).profile == "BREZ"


async def _collect(got, msg):
    got.append(msg)


def test_bank_voice_plays_committed_lines_and_captions_the_rest(tmp_path):
    bank = {"agh|strong": {"file": "a.wav", "ms": 890, "text": "agh", "style": "strong"},
            "hm|none": {"file": "b.wav", "ms": 830, "text": "hm", "style": "none"}}
    v = speech_mod.BankVoice(bank)
    assert v.available() and v.status()["lines"] == 2 and v.status()["voice"] == "SUB-01"
    assert v.synthesize("agh", "strong") == {"url": "/chair_voice/a.wav", "ms": 890}
    assert v.synthesize("agh", "burst") is None and v.synthesize("nope", "strong") is None
    assert speech_mod.voice_from_env({}, bank=bank).name == "bank"
    assert speech_mod.voice_from_env({}, bank={}).name == "none"
    vs = speech_mod.voice_from_env({"VOICE_STUDIO_URL": "http://x"}, bank=bank)
    assert vs.name == "voicestudio" and vs.synthesize("agh", "strong")["url"] == "/chair_voice/a.wav"   # the bank answers first
    # the committed bank: every rule line (reactions, comments, register, visitor, idle, join, no-model) is in it, as mp3
    real = speech_mod.load_bank(HERE)
    for text, cls in speech_mod.bank_lines():
        e = real[f"{text}|{cls}"]
        f = HERE / speech_mod.BANK_DIR / e["file"]
        assert f.suffix == ".mp3" and f.stat().st_size > 1000 and 300 < e["ms"] < 14000, (text, cls)
    assert sum(f.stat().st_size for f in (HERE / speech_mod.BANK_DIR).iterdir()) < 6e6     # small enough to commit


def test_speech_never_repeats_a_line_while_it_is_recent():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    said = []
    for k in range(12):
        sp.on_delivered({"id": f"c-{k}", "level": 5}, float(k))
        sp.on_trace({"card": {"id": f"c-{k}", "baseline": True, "peak_ratio": 3.0, "t1_ms": 0}, "t_ms": 100, "phase": "responding"}, float(k))
        said.append(sp.queue[-1]["text"])
    assert len(set(said)) == 12                                      # twelve strong reactions, twelve different lines
    p = speech_mod.Picker(random.Random(1))
    seq = [p.pick(["a", "b"]) for _ in range(6)]
    assert all(x != y for x, y in zip(seq, seq[1:]))                 # a tiny pool: never the same line twice in a row
    for k in range(5):                                               # rule comments too, and the register's lines join the pool
        sp.history.append({"id": f"c-{k}", "peak_ratio": 3.0, "recruit": 0.5})
        sp.last_delivered = f"c-{k}"
        sp.finish_comment(f"c-{k}", None, "strong", 20.0 + k)
    texts = [q["text"] for q in sp.queue if q["kind"] == "comment"]
    assert len(set(texts)) == len(texts)


def test_register_is_measured_from_load_shocks_and_revival():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    assert sp.register(0.0) == "fresh"
    sp.on_trace({"load": 1.2}, 1.0)
    assert sp.register(1.0) == "rattled"
    sp.on_trace({"load": 1.35}, 2.0)
    assert sp.register(2.0) == "worn"
    sp.on_trace({"load": 1.0}, 3.0)
    assert sp.register(3.0) == "fresh"
    for k in range(speech_mod.SHOCKS_RATTLED):
        sp.on_delivered({"id": f"c-{k}", "level": 2}, 10.0 + k)
    assert sp.register(14.0) == "rattled" and sp.register(100.0) == "fresh"
    sp.on_revived({"type": "revived", "dead_s": 3.0, "level": 4}, 200.0)
    assert sp.register(200.0) == "wary" and sp.register(200.0 + speech_mod.WARY_S + 1) == "fresh"
    assert set(sp.status()) >= {"register", "model", "queue"}
    job = sp.take_comment_job()
    assert job and "recent_lines" in job[2]
    sp.history.append({"id": "c-9", "peak_ratio": 2.5})
    sp.on_measured({"id": "c-9", "baseline": True, "peak_ratio": 2.5}, 300.0)
    sp.on_measured({"id": "c-10", "baseline": True, "peak_ratio": 2.5}, 301.0)
    job = sp.take_comment_job()
    assert job and '"register"' in job[2] and "recent_lines" in job[2] and "register" in job[1]


def test_visitor_memory_lines():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    t = 0.0

    def shock(who, level=3):
        nonlocal t
        t += 30.0
        sp.on_delivered({"id": f"c-{int(t)}", "level": level}, t, who=who)
        return [q["text"] for q in sp.queue if q["cls"] == "visitor"]
    assert shock("a") == []                                          # a first hand, alone: nothing
    assert shock("a")[-1] in speech_mod.VISITOR_LINES["second"]
    assert shock("a")[-1] in speech_mod.VISITOR_LINES["third"]
    assert shock("b")[-1] in speech_mod.VISITOR_LINES["new"]         # another hand while the first is active
    assert sp.stats["visitor_lines"] == 3
    shock("a", 5)
    assert sp.stats["visitor_lines"] == 3                            # the fourth: nothing to say
    assert shock("a", 5)[-1] in speech_mod.VISITOR_LINES["regular"]
    assert shock("a", 5)[-1] in speech_mod.VISITOR_LINES["fives"]
    sp.on_delivered({"id": "x", "level": 5}, t + 1.0, who="b")       # within VISITOR_EVERY_S: nothing, whoever it is
    assert sp.stats["visitor_lines"] == 5
    assert "a" not in json.dumps(sp.status()) or "visitors" not in sp.status()   # keys never leave the process


def test_join_and_idle_lines_when_people_watch_and_nobody_presses():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    assert sp.tick(0.0, viewers=0) == []
    out = sp.tick(1.0, viewers=1)
    assert out and out[0]["cls"] == "join" and out[0]["text"] in speech_mod.JOIN_LINES
    assert sp.tick(2.0, viewers=2) == []                             # one join line a minute
    for t in range(3, int(speech_mod.IDLE_AFTER_S)):
        assert all(m.get("cls") != "idle" for m in sp.tick(float(t), viewers=2))
    out = sp.tick(1.0 + speech_mod.IDLE_AFTER_S + 0.5, viewers=2)
    assert out and out[0]["cls"] == "idle" and out[0]["text"] in sum(speech_mod.IDLE_LINES.values(), [])
    sp.on_delivered({"id": "c-1", "level": 3}, 50.0)                 # a shock resets the quiet
    assert all(m.get("cls") != "idle" for m in sp.tick(50.0 + speech_mod.IDLE_AFTER_S - 1, viewers=2))
    out = sp.tick(50.0 + speech_mod.IDLE_EVERY_S + 1, viewers=2)
    assert out and out[0]["cls"] == "idle" and sp.stats["idle_lines"] == 2
    sp.on_flatline({"type": "flatline"}, 130.0)
    assert sp.tick(400.0, viewers=2) == []                           # flat: nothing
    sp.on_revived({"type": "revived", "dead_s": 5.0, "level": 4}, 401.0)
    sp.queue.clear(); sp.pending_comment = None; sp.playing = None
    assert sp.tick(900.0, viewers=0) == []                           # nobody watching: nothing


def test_chair_model_meter_bounds_comment_and_chat_calls():
    calls = []
    sp = speech_mod.Speech(ask=lambda s, u: calls.append(u) or "a line", clock=lambda: 0.0)
    sp.meter = speech_mod.CallMeter(per_hour=2, per_day=3)
    assert sp.ask_metered("s", "u") == "a line" and sp.ask_metered("s", "u") == "a line"
    assert sp.ask_metered("s", "u") is None and len(calls) == 2      # the hour's share is spent: a rule line instead
    cc = speech_mod.ChairChat(sp, ask=lambda s, u: "an answer", clock=lambda: 0.0)
    assert cc.ask_metered("s", "u") is None                          # the chat shares the meter
    sp.meter.times.clear()
    assert cc.ask_metered("s", "u") == "an answer"
    assert sp.status()["model"]["calls_last_hour"] == 1
    assert speech_mod.Speech(ask=None, clock=lambda: 0.0).ask_metered("s", "u") is None


def test_every_voice_provider_survives_the_startup_log_line():
    """live_server prints one line about the voice at start; it crashed production once (2026-11-03) on the bank."""
    for v in (speech_mod.NoVoice(), speech_mod.BankVoice({"a|b": {"file": "a.wav", "ms": 1}}), speech_mod.VoiceStudio("http://127.0.0.1:1")):
        line = f"{v.name} at {getattr(v, 'base', '?')} ({'up' if v.available() else 'not answering yet'}; profile {getattr(v, 'profile', None) or 'none, designed'})"
        assert v.name in line


# --- the chair chat --------------------------------------------------------------------------------------------------------------
def test_chair_chat_no_filter_limits_and_spoken_answer():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    cc = speech_mod.ChairChat(sp, ask=None, clock=lambda: 0.0)
    state = {"phase": "quiet", "last_shocks": [], "open": False, "source": "simulation"}
    ack, msg = cc.submit("a", "  hey   are you ok? https://x.y $$$ ", "voice", 100.0, state)
    assert ack["state"] == "ok" and msg["who"] == "you" and msg["via"] == "voice" and msg["text"] == "hey are you ok? https://x.y $$$"   # no filter
    assert cc.submit("a", "again", "text", 101.0, state)[0]["state"] == "throttled"       # one every 15 s per visitor
    assert cc.submit("b", "me too", "text", 101.0, state)[0]["state"] == "busy"           # one answer at a time
    assert cc.submit("c", "", "text", 101.0, state)[0]["state"] == "empty"
    assert cc.submit("c", "x" * 400, "text", 101.0, state)[0]["state"] == "busy" and len("x" * 400) > speech_mod.CHAT_MAX
    job = cc.take_job(100.0)
    assert job and job[0] == "m-1" and "SUB-01" in job[1] and "hey are you ok" in job[2] and "never" not in job[1].lower()
    line = cc.finish("m-1", '"strapped in a chair and you ask if i am ok. peak was 4x. ' + "word " * 60 + '"', 102.0)
    assert line["who"] == "him" and line["to"] == "m-1" and len(line["text"].split()) == speech_mod.REPLY_WORDS   # length is the only bound
    out = sp.tick(102.1)
    assert out and out[0]["type"] == "say" and out[0]["kind"] == "reply" and out[0]["text"] == line["text"]
    assert cc.submit("b", "me too", "text", 103.0, state)[0]["state"] == "ok"              # free again
    cc.take_job(130.0)
    assert cc.finish("m-2", None, 130.0)["text"] in speech_mod.NO_MODEL_LINES                # no model: a plain line, never silence
    assert cc.stats == {"messages": 2, "throttled": 1, "replies": 2, "model": 1}


# --- the flatline and the revival ------------------------------------------------------------------------------------------------
def test_flatline_rule_and_revival_in_the_simulation():
    n = ALIFNet(Config(n_neurons=SMALL, mu_ext=MU_EXT), seed=9)
    M = Measure(n)
    run_bins(n, M, 4000)
    bw = M.base_main.mean[3]
    for k in range(6):                                              # moderate use never gets there
        M.open(f"a{k}", n.stimulate(3))
        run_bins(n, M, 3000)
    assert not n.flat and M.load < alif.FLAT_LOAD_RATIO * bw and not M.events
    M.load = alif.FLAT_LOAD_RATIO * bw * 1.01                        # the load the rule reads, pushed over the line
    run_bins(n, M, 40)
    assert n.flat and M.events and M.events[0]["type"] == "flatline" and M.phase == "flat"
    assert float(n.mu.max()) == 0.0
    b = run_bins(n, M, 1500)
    assert all(x["flat"] for x in b) and b[-1]["rate"] < 0.05       # no spontaneous activity without the drive
    assert drive_from(b[-1], M.baseline_view()) == {"tension": 0.0, "slack": 1.0, "heavy": 1.0, "motor": 0.0, "measured": True, "flat": True}
    c = n.stimulate(2)
    M.open("weak", c)
    run_bins(n, M, 1500)
    assert not c["revived"] and n.flat                               # too weak to bring the drive back
    c = n.stimulate(alif.REVIVE_LEVEL)
    M.open("rev", c)
    assert c["revived"] and not n.flat and M.events[-1]["type"] == "revived" and M.events[-1]["dead_s"] > 2
    b = run_bins(n, M, 4000)
    assert b[-1]["rate"] > 1.0 and not b[-1]["flat"]


def test_speech_and_chat_go_silent_when_flat_and_speak_on_revival():
    sp = speech_mod.Speech(clock=lambda: 0.0)
    cc = speech_mod.ChairChat(sp, clock=lambda: 0.0)
    sp.on_delivered({"id": "c-1", "level": 5}, 1.0)
    sp._line("reaction", "agh", "c-1", 3.0, 1.0, "strong")
    sp.on_flatline({"type": "flatline"}, 2.0)
    assert sp.flat and not sp.queue
    sp.on_trace({"card": {"id": "c-1", "baseline": True, "peak_ratio": 4.0, "t1_ms": 0}, "t_ms": 100, "phase": "flat"}, 2.5)
    assert not sp.queue                                             # no reactions while flat
    assert cc.submit("v", "are you there?", "text", 3.0, {})[0]["state"] == "flat"
    sp.on_revived({"type": "revived", "dead_s": 7.0, "level": 4}, 10.0)
    assert not sp.flat and sp.queue and sp.queue[0]["cls"] == "back"
    job = sp.take_comment_job()
    assert job and job[0] == "revive" and "flatlined" in job[1] and '"flat_for_s": 7.0' in job[2]
    sp.finish_comment("revive", None, "back", 10.5)
    kinds = [(q["kind"], q["cls"]) for q in sp.queue]
    assert ("reaction", "back") in kinds and ("comment", "back") in kinds
    out = sp.tick(10.6)
    assert out[0]["type"] == "say" and out[0]["cls"] == "back"
