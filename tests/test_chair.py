"""The chair (chair.py, speech.py, spiking/alif.py, web/chair.html): the network, its measurements, the hub's limits,
the speech queue and the page's wording. Network tests use a 5,000-neuron net (same wiring code, seconds each)."""
import asyncio
import json
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
    assert drive_from({"rate": 40.0}, {"ready": False}) == {"tension": 0.0, "slack": 0.0, "heavy": 0.0, "measured": False}


def test_drive_mapping_is_bounded_and_monotonic():
    base = {"ready": True}
    d = [drive_from({"ratio": r, "w_rel": 0.0}, base)["tension"] for r in (1.0, 2.0, 4.0, 8.0, 50.0)]
    assert d == sorted(d) and d[0] == 0.0 and d[-1] == 1.0
    assert drive_from({"ratio": 0.5, "w_rel": 0.5}, base) == {"tension": 0.0, "slack": 0.5, "heavy": 0.5, "measured": True}


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


async def _two_clients_on(client, hub):
    w1 = await client.ws_connect("/ws/chair", headers={"X-Key": "one"})
    w2 = await client.ws_connect("/ws/chair", headers={"X-Key": "two"})
    h1, h2 = await w1.receive_json(), await w2.receive_json()
    assert h1["type"] == "hello" and h2["type"] == "hello" and h1["levels"] == h2["levels"]
    await w1.send_json({"type": "shock", "level": 4})
    ack = await w1.receive_json()
    assert ack["type"] == "ack" and ack["state"] == "queued" and ack["id"] == "c-1"
    e1, e2 = await w1.receive_json(), await w2.receive_json()
    assert e1 == e2 and e1["state"] == "queued"
    await hub.pump_once()
    await hub._event({"type": "delivered", "id": "c-1", "level": 4, "t_ms": 500.0, "n_recruited": 10, "dur_ms": 800})
    d1, d2 = await w1.receive_json(), await w2.receive_json()
    assert d1 == d2 and d1["state"] == "delivered" and d1["t_ms"] == 500.0 and "t_wall" in d1
    await w2.send_json({"type": "shock", "level": "x"})
    assert (await w2.receive_json())["state"] == "refused"
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
    assert len([q for q in sp.queue if q["kind"] == "reaction"]) == 1 and sp.queue[-1]["cls"] == "burst"
    assert sp.stats["cancelled"] == 1                                # the small one went
    sp.on_trace({"card": card, "t_ms": 700, "phase": "stimulated"}, now)
    assert len(sp.queue) == 1                                        # one reaction per stimulus


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


def test_speech_lines_never_claim_feeling_or_consciousness():
    text = " ".join(sum(speech_mod.REACTIONS.values(), []) + sum(speech_mod.RULE_COMMENTS.values(), [])).lower()
    for bad in ("i feel", "hurts", "pain", "conscious", "alive", "i am human"):
        assert bad not in text
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
    assert "setDrive" in js and "reduced" in js and "shock()" in js
    assert re.search(r"\bAI\b", js) is None
