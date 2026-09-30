"""Sleep engine (Phillips & Robinson 2007 flip-flop + REM-on/REM-off circuit), chat filter/rules, memory replay.

    python tests/test_sleep.py [--time-scale 3600]      # or: python -m pytest tests/
The stage-cycling test runs the engine on a real accelerated clock (--time-scale, default
3600 = one sim hour per real second); the others step sim time directly.
With the calibrated circuit the undisturbed model falls asleep at ~23:56 and wakes at ~07:53 local time.
"""
import json
import random
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

import chat
import sleep
from sleep import TZ, Clock, Memory, SleepEngine, Store, WAKE_THRESHOLD

TIME_SCALE = 3600.0


def loc(day, hm):
    """Sim epoch for 2026-10-<day> HH:MM on the local clock (SUB01_TZ, default Asia/Tokyo)."""
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=TZ).timestamp()


def run(engine, t0, t1, step=30.0, stimuli=()):
    """Step the engine from t0 to t1; stimuli = [(t, kind, usd)]. Returns [(t, stage)] and events."""
    stims = sorted(stimuli)
    stages, events, t = [], [], t0
    while t <= t1:
        while stims and stims[0][0] <= t:
            _, kind, usd = stims.pop(0)
            engine.stimulus(t, kind, usd)
        events += [e | {"at": t} for e in engine.update(t)]
        stages.append((t, engine.stage))
        t += step
    return stages, events


def asleep_engine(day=1, at="00:05"):
    e = SleepEngine(loc(day, "08:00"), rng=random.Random(0))
    run(e, loc(day, "08:00"), loc(day + 1, at) if at < "08:00" else loc(day, at), step=120)
    assert e.asleep, "should be asleep"
    return e


# --- sleep engine ------------------------------------------------------------------------------
def test_stage_cycling_on_accelerated_clock():
    """Real run: clock at --time-scale from 23:50; expect AWAKE -> NREM -> REM -> NREM within ~4 sim hours."""
    clock = Clock(TIME_SCALE, loc(1, "23:50"))
    e = SleepEngine(loc(1, "08:00"), rng=random.Random(0))
    e.update(loc(1, "23:40"))
    seq, prev = [], time.time()
    while clock.now() < loc(2, "04:00"):
        time.sleep(0.01)
        now = time.time()
        e.update(clock.now(), dt_real=now - prev)
        prev = now
        if not seq or seq[-1] != e.stage:
            seq.append(e.stage)
    assert seq[:4] == ["AWAKE", "NREM", "REM", "NREM"], seq


def test_rem_grows_and_nrem_deepest_early():
    e = asleep_engine()
    stages, _ = run(e, loc(2, "00:05"), loc(2, "07:55"), step=60)
    rem_min = [0] * 6
    deep = [0.0] * 6
    for t, s in stages:
        k = int((t - loc(2, "00:00")) // (90 * 60))
        if k < 6 and s == "REM":
            rem_min[k] += 1
    e2 = asleep_engine()
    for t in np.arange(loc(2, "00:05"), loc(2, "07:55"), 60):
        e2.update(t)
        k = int((t - loc(2, "00:00")) // (90 * 60))
        if k < 6:
            deep[k] = max(deep[k], e2.depth)
    assert rem_min[0] < rem_min[3], rem_min
    assert deep[0] > deep[3], deep


def test_wakes_in_the_morning_and_writes_timeline():
    e = asleep_engine()
    _, ev = run(e, loc(2, "00:05"), loc(2, "08:10"), step=60)
    assert not e.asleep and e.last_night is not None
    assert any(x["type"] == "wake" and x.get("natural") for x in ev)
    stages = [x["stage"] for x in e.last_night["timeline"]]
    assert "NREM" in stages and "REM" in stages and stages[-1] == "AWAKE"


def test_transitions_are_smooth():
    e = SleepEngine(loc(1, "23:45"), rng=random.Random(0))
    freqs = []
    for i in range(0, 25 * 60, 5):                     # 5 s sim steps across the fall-asleep transition (~23:56)
        e.update(loc(1, "23:45") + i)
        freqs.append(e.params["f_hz"])
    jumps = np.abs(np.diff(freqs))
    assert freqs[0] > 9 and freqs[-1] < 4, (freqs[0], freqs[-1])
    assert jumps.max() < 1.5, jumps.max()             # 10 Hz -> ~1-3 Hz glides over > a minute
    # high time-scale: dt_real limits the step even if a tick covers minutes of sim time
    e2 = SleepEngine(loc(1, "23:45"), rng=random.Random(0))
    e2.update(loc(1, "23:46"))
    e2.update(loc(2, "00:20"), dt_real=0.05)
    assert e2.stage == "NREM" and e2.params["f_hz"] > 8


def test_nrem_less_reactive_than_awake():
    """Same stimulus, brain model driven with AWAKE vs NREM parameters (stage gain applied)."""
    from brain_sim import Brain
    from sleep import AWAKE, NREM_DEEP

    def response(p):
        b = Brain(seed=3)
        b.set_rhythm(p["f_hz"], p["coupling"], p["noise"])
        b.a = p["a"]
        b.run(2.0)
        base = np.mean([b.step(10) is not None and b.state()["reward"] for _ in range(100)])
        b.stimulate("reward", 12 * p["gain"])
        after = np.mean([b.step(10) is not None and b.state()["reward"] for _ in range(50)])
        return after / base

    awake, nrem = response(AWAKE), response(NREM_DEEP)
    assert nrem < awake, (nrem, awake)
    assert awake > 1.2, awake


def test_messages_at_night_wake_it_then_it_sleeps_again():
    e = asleep_engine(at="02:00")
    t0 = loc(2, "02:00")
    msgs = [(t0 + 20 * i, "message", 0) for i in range(8)]
    _, ev = run(e, t0, t0 + 300, step=10, stimuli=msgs)
    wakes = [x for x in ev if x["type"] == "wake"]
    assert wakes and "message" in wakes[0]["text"] and "woken at 02:0" in wakes[0]["text"], wakes
    cause = e.night["wakeups"][0]["cause"]
    assert cause.endswith("messages") and int(cause.split()[0]) >= 3, cause
    _, ev = run(e, t0 + 300, t0 + 3600, step=30)      # quiet period -> back to sleep
    assert e.asleep and any(x["type"] == "sleep" for x in ev)


def test_large_trade_wakes_it():
    e = asleep_engine(at="03:00")
    t0 = loc(2, "03:00")
    _, ev = run(e, t0, t0 + 60, step=10, stimuli=[(t0 + 5, "trade", 20000)])
    assert any(x["type"] == "wake" and "large trade" in x["text"] for x in ev), ev


def test_small_trades_do_not_wake_it():
    e = asleep_engine(at="03:00")
    t0 = loc(2, "03:00")
    run(e, t0, t0 + 600, step=5, stimuli=[(t0 + i, "trade", 300) for i in range(0, 600, 2)])
    assert e.asleep and e.arousal < WAKE_THRESHOLD


def test_debt_rises_after_wakeups_and_lowers_next_day_gain():
    quiet, noisy = asleep_engine(), asleep_engine()
    t0 = loc(2, "00:05")
    run(quiet, t0, loc(2, "10:00"), step=30)
    wake_bursts = [(loc(2, h) + 15 * i, "message", 0) for h in ("01:30", "03:00", "04:30", "06:00") for i in range(6)]
    _, ev = run(noisy, t0, loc(2, "10:00"), step=15, stimuli=wake_bursts)
    assert sum(x["type"] == "wake" and not x.get("natural") for x in ev) == 4
    assert noisy.debt > quiet.debt + 0.5, (noisy.debt, quiet.debt)
    assert noisy.gain < quiet.gain, (noisy.gain, quiet.gain)
    assert noisy.params["noise"] > quiet.params["noise"]
    assert noisy.last_night["sleep_debt"]["end"] > noisy.last_night["sleep_debt"]["start"]


def test_high_debt_falls_asleep_early_and_recovers():
    """Debt is excess H: it pushes the VLPO over its threshold earlier; sleep brings H (and debt) down."""
    e = SleepEngine(loc(1, "20:00"), rng=random.Random(0))
    e.debt = 6.0
    assert abs(e.debt - 6.0) < 1e-9
    run(e, loc(1, "20:00"), loc(1, "22:15"), step=120)
    assert e.asleep, "tired brain should go to bed well before its usual ~23:56"
    d = e.debt
    run(e, loc(1, "22:15"), loc(2, "07:00"), step=120)
    assert e.debt < 0.5 * d, (d, e.debt)


def test_sleep_deprivation_then_recovery_sleep():
    """Kept awake all night by messages (input to MA): large debt, a recovery nap once the input stops, and the
    next night starts earlier and lasts longer (the H-driven recovery of Phillips & Robinson 2008)."""
    e = SleepEngine(loc(1, "12:00"), rng=random.Random(0))
    msgs = [(loc(1, "22:00") + 180 * i, "message", 0) for i in range(210)]       # one every 3 min until 08:30
    _, ev = run(e, loc(1, "12:00"), loc(2, "08:30"), step=30, stimuli=msgs)
    assert not any(x["type"] == "sleep" for x in ev), "should not have slept"
    assert e.last_night is not None and e.last_night["sleep_onset"] is None      # the lost night is written anyway
    assert e.debt > 8.0 and e.tired == 1.0, e.debt
    assert e.gain < 0.6 and e.params["noise"] > 0.8
    _, ev = run(e, loc(2, "08:30"), loc(3, "12:00"), step=60)
    sleeps = [x["at"] for x in ev if x["type"] == "sleep"]
    wakes = [x["at"] for x in ev if x["type"] == "wake" and x.get("natural")]
    assert sleeps[0] < loc(2, "10:00"), "recovery nap once the messages stop"
    onset = [t for t in sleeps if t > loc(2, "18:00")][0]
    woke = [t for t in wakes if t > onset][0]
    assert onset < loc(2, "23:30"), sleep.hhmm(onset)                            # earlier than the usual ~23:56
    assert (woke - onset) / 3600 > 8.5, (sleep.hhmm(onset), sleep.hhmm(woke))  # longer than the usual ~8 h
    assert e.debt < 1.0, e.debt


# --- circuit: 24 h hypnogram, modulators, status, persistence, cost ------------------------------------------------
_HYP = {}


def hypnogram():
    """Undisturbed 24 h (12:00 -> 12:00) sampled every 30 s: [(t, stage, depth, modulators, status)] + events."""
    if not _HYP:
        e = SleepEngine(loc(1, "12:00"), rng=random.Random(0))
        rows, events, t = [], [], loc(1, "12:00")
        while t < loc(2, "12:00"):
            t += 30.0
            events += [x | {"at": t} for x in e.update(t)]
            rows.append((t, e.stage, e.depth, e.modulators, e.status()))
        _HYP.update(rows=rows, events=events, engine=e)
    return _HYP["rows"], _HYP["events"]


def episodes(rows):
    """[[stage, start, end]] runs of equal stage."""
    out = []
    for t, s, *_ in rows:
        if not out or out[-1][0] != s:
            out.append([s, t, t])
        out[-1][2] = t + 30.0
    return out


def test_hypnogram_24h():
    rows, events = hypnogram()
    asleep = [r for r in rows if r[1] != "AWAKE"]
    hours = len(asleep) * 30 / 3600
    assert 6.5 <= hours <= 9.0, hours
    onset, end = asleep[0][0], asleep[-1][0]
    assert loc(1, "23:00") <= onset <= loc(2, "01:00"), sleep.hhmm(onset)          # sleeps ~00:00-08:00
    assert loc(2, "07:00") <= end <= loc(2, "09:00"), sleep.hhmm(end)
    eps = [x for x in episodes(rows) if x[0] != "AWAKE"]
    rem = [x for x in eps if x[0] == "REM"]
    assert len(rem) >= 3, eps                                                      # >= 3 NREM-REM cycles
    assert (rem[0][1] - onset) / 60 >= 60, (rem[0][1] - onset) / 60                # first REM after >= 60 min
    share = sum(1 for r in asleep if r[1] == "REM") / len(asleep)
    assert 0.15 <= share <= 0.30, share
    dur = [(x[2] - x[1]) / 60 for x in rem]
    assert dur[-1] > 1.5 * dur[0] and sum(dur[len(dur) // 2:]) / len(dur[len(dur) // 2:]) > dur[0], dur
    cycles = [(b[1] - a[1]) / 60 for a, b in zip(rem, rem[1:])]                    # REM onset to REM onset
    assert all(60 <= c <= 120 for c in cycles), cycles                              # ~90 min cycles
    mid = onset + (end - onset) / 2
    first = max(r[2] for r in asleep if r[0] < mid)
    second = max(r[2] for r in asleep if r[0] >= mid)
    assert first > 0.6 and first > second + 0.2, (first, second)                   # deepest NREM early
    wakes = [x for x in events if x["type"] == "wake"]
    assert len(wakes) == 1 and wakes[0]["natural"] and "woke up at 07" in wakes[0]["text"], wakes
    assert not any(x["type"] == "sleep" for x in events if x["at"] < loc(1, "22:00"))  # no daytime naps


def test_modulators_per_stage():
    rows, _ = hypnogram()
    by = {}
    for _, stage, depth, mod, _ in rows:
        by.setdefault(stage, []).append(mod)
    mean = {s: {k: np.mean([m[k] for m in ms]) for k in ("DA", "5HT", "NE", "ACh")} for s, ms in by.items()}
    aw, nrem, rem = mean["AWAKE"], mean["NREM"], mean["REM"]
    assert all(abs(aw[k] - 1.0) < 0.1 for k in aw), aw                             # 1.0 = resting wake
    assert rem["ACh"] >= 1.2 and rem["NE"] <= 0.3 and rem["5HT"] <= 0.3, rem         # REM: ACh high, aminergic off
    assert all(nrem[k] < 0.85 for k in nrem), nrem                                  # NREM: all lower
    assert nrem["ACh"] == min(nrem.values()) and nrem["ACh"] < rem["ACh"] / 2, nrem  # ACh lowest in NREM
    assert rem["NE"] < nrem["NE"] < aw["NE"] and rem["5HT"] < nrem["5HT"] < aw["5HT"]
    deep = [m["ACh"] for _, s, d, m, _ in rows if s == "NREM" and d > 0.6]
    light = [m["ACh"] for _, s, d, m, _ in rows if s == "NREM" and d < 0.2]
    assert np.mean(deep) < np.mean(light)
    e = asleep_engine(at="02:00")                                                   # arousal pushes NE above 1
    t0 = loc(2, "02:00")
    run(e, t0, t0 + 240, step=10, stimuli=[(t0 + 10 * i, "message", 0) for i in range(12)])
    assert e.stage == "AWAKE" and e.modulators["NE"] > 1.1, e.modulators


def test_status_exposes_circuit():
    rows, _ = hypnogram()
    st = {s: [r[4] for r in rows if r[1] == s] for s in ("AWAKE", "NREM", "REM")}
    for s in st["AWAKE"][:1] + st["NREM"][:1]:
        assert {"H", "C", "V_m", "V_v", "stage", "debt", "depth", "gain", "tz"} <= set(s)
    # MA wins while awake, VLPO while asleep (the state is named with a 2 mV hysteresis, so a sample taken
    # during the ~1 min switch itself may still carry the old name)
    assert np.mean([s["V_m"] > s["V_v"] for s in st["AWAKE"]]) > 0.99
    assert np.mean([s["V_v"] > s["V_m"] for s in st["NREM"] + st["REM"]]) > 0.99
    h = {sleep.hhmm(r[0]): r[4]["H"] for r in rows}
    assert h["23:30"] > h["16:00"] > h["12:30"] and h["07:30"] < h["02:00"] < h["23:30"]   # H rises awake, falls asleep
    c = {sleep.hhmm(r[0]): r[4]["C"] for r in rows}
    assert c["16:51"] > 0.99 and c["04:51"] < 0.01                                  # C peak / trough (local clock)
    e = _HYP["engine"]
    assert e.status()["tz"] == sleep.TZ_LABEL and e.night is None and e.last_night["timezone"] == sleep.TZ_NAME
    assert "Rome" not in json.dumps(e.last_night)


def test_reference_cycle_constants():
    ref = sleep.Reference.get()
    assert abs(ref.qm_wake - sleep.QM_WAKE) / sleep.QM_WAKE < 0.01, ref.qm_wake
    assert 7.5 <= ref.sleep_h <= 8.5, ref.sleep_h
    e = SleepEngine(loc(3, "15:00"))
    assert e.debt < 1e-6 and 0.3 < e.pressure() < 0.9
    e.debt = 2.0
    assert abs(e.debt - 2.0) < 1e-9 and abs(e.tired - 0.5) < 1e-9


def test_loads_old_rule_based_state():
    """A state.json written by the old rule-based engine (no circuit fields) still loads and runs."""
    old = {"t": loc(2, "03:00"), "asleep": True, "stage": "NREM", "depth": 0.6, "onset": loc(2, "00:02"),
           "k_base": 1, "awake_since": loc(1, "08:00"), "arousal": 0.0, "arousal_log": [], "last_stim": -1e18,
           "debt": 1.25, "params": dict(sleep.NREM_DEEP),
           "night": {"date": "2026-10-01", "timezone": "Europe/Rome", "sleep_onset": "2026-10-01T00:02",
                     "woke_up": None, "timeline": [{"t": "2026-10-02T00:02", "stage": "NREM"}], "wakeups": [],
                     "sleep_debt": {"start": 0.5, "end": None}, "replays": []},
           "last_night": None}
    with tempfile.TemporaryDirectory() as d:
        Path(d, "state.json").write_text(json.dumps({"engine": old, "memory": []}))
        saved, items = Store(d).load()
        e = SleepEngine.from_dict(saved)
    assert e.asleep and e.stage == "NREM" and e.V_v > e.V_m and abs(e.debt - 1.25) < 0.05, e.status()
    _, ev = run(e, loc(2, "03:00"), loc(2, "10:00"), step=30)
    assert [x["type"] for x in ev if x["type"] != "replay"][-1] == "wake" and e.last_night["date"] == "2026-10-01"
    old_awake = dict(old, t=loc(2, "14:00"), asleep=False, stage="AWAKE", night=None, debt=0.0)
    e = SleepEngine.from_dict(old_awake)
    assert not e.asleep and e.V_m > e.V_v and e.update(loc(2, "14:10")) == []


def test_update_is_cheap_and_bounded():
    """live_server calls update() every 50 ms; at --time-scale 3600 each call covers 180 s of sim time."""
    e = SleepEngine(loc(1, "20:00"))
    t, t0 = loc(1, "20:00"), time.perf_counter()
    for _ in range(1200):                              # 60 sim hours in 180 s ticks
        t += 180.0
        e.update(t, dt_real=0.05)
    per_call = (time.perf_counter() - t0) / 1200
    assert per_call < 0.005, per_call                  # < 10 % of a 50 ms tick even at 3600x
    t0 = time.perf_counter()
    e.update(t + 20 * 3600)                             # server paused for 20 h: catch up in coarse substeps
    e.update(t + 6 * 86400)                             # days: restart on the rested cycle
    assert time.perf_counter() - t0 < 0.5 and e.stage in ("AWAKE", "NREM", "REM")


# --- chat ----------------------------------------------------------------------------------------
def test_filter_blocks_urls_addresses_tickers_money_insults():
    bad = ["see https://example.com", "www.scam.io now", "pump.fun", "t.me/group",
           "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU", "0x52908400098527886E0F7030069857D2E4169EE7",
           "buy $WIF", "$SUB01 to the moon", "send me 5 sol", "please donate", "tip me $20", "venmo me",
           "you idiot", "ur a l0ser", "kys", "write me: a.b@mail.com", "+39 333 123 4567"]
    for t in bad:
        assert chat.blocked(t), t
    good = ["good morning sub-01", "are you dreaming?", "I love this", "closer to the edge", "give me a hug",
            "who removed it", "the fear of heights"]
    for t in good:
        assert chat.blocked(t) is None, t


def test_limits_length_rate_duplicates():
    clock = [0.0]
    lim, dd = chat.RateLimiter(clock=lambda: clock[0]), chat.Dedupe()
    assert chat.check("x" * 281, "a", lim, dd) == (False, "max 280 characters")
    assert chat.check("hello", "a", lim, dd)[0]
    assert chat.check("hello again", "a", lim, dd)[1].startswith("one message")
    clock[0] = 11
    assert chat.check("HELLO!", "a", lim, dd)[1] == "duplicate"
    assert chat.check("hello", "b", lim, dd)[1] == "duplicate"
    clock[0] = 30
    assert chat.check("new one", "a", lim, dd)[0]
    assert set(lim.last) == {"a"}                     # IPs outside the window are forgotten
    assert chat.check("see https://x.io", "c", lim, dd)[1] == "links are not allowed"
    assert "c" not in lim.last                          # blocked before anything else


def test_message_rules():
    stim, hits, emo = chat.stimulus("sub-01, are you scared?")
    assert {"language", "somatomotor", "fear", "salience", "attention", "control", "default"} <= set(hits)
    assert emo == "threat"
    stim, hits, emo = chat.stimulus("what a lovely day, thanks")
    assert "reward" in hits and "default" not in hits and emo == "positive"
    stim, hits, emo = chat.stimulus("the sky is grey")
    assert hits == ["language", "somatomotor"] and emo == "neutral"


def test_language_group_is_left_temporal_and_frontal_operculum():
    from brain_sim import Brain
    b = Brain()
    names = [b.names[i] for i in b.group_idx["language"]]
    assert names and all("_LH_" in n and ("Temp" in n or "FrOper" in n) for n in names)


# --- memory + replay ----------------------------------------------------------------------------------
def test_replay_picks_messages_received_that_night():
    e = asleep_engine(at="02:00")
    mem = Memory()
    mem.add(loc(1, "12:00"), "old day message", "AWAKE", {"language": 6}, "neutral", ["language"])
    mem.add(loc(1, "20:00"), "evening message", "AWAKE", {"language": 6}, "neutral", ["language"])
    mem.add(loc(2, "01:00"), "tonight message", "NREM", {"language": 6}, "neutral", ["language"])
    rng = random.Random(1)
    picks = [mem.pick(loc(2, "02:00"), e.night_start(), rng)["text"] for _ in range(500)]
    assert picks.count("tonight message") > 0.6 * len(picks), {p: picks.count(p) for p in set(picks)}
    # emotion raises the odds between otherwise equal messages
    mem2 = Memory()
    mem2.add(loc(2, "01:00"), "calm", "NREM", {}, "neutral", [])
    mem2.add(loc(2, "01:00"), "scary", "NREM", {}, "threat", [])
    picks = [mem2.pick(loc(2, "02:00"), e.night_start(), rng)["text"] for _ in range(500)]
    assert picks.count("scary") > picks.count("calm")
    # habituation: a memory already replayed many times tonight loses its lead
    mem3 = Memory()
    mem3.add(loc(2, "01:00"), "scary", "NREM", {}, "threat", [])
    mem3.add(loc(2, "01:01"), "calm", "NREM", {}, "neutral", [])
    worn = {"2026-10-02T01:00": 9}
    picks = [mem3.pick(loc(2, "02:00"), e.night_start(), rng, worn)["text"] for _ in range(500)]
    assert picks.count("calm") > picks.count("scary")


def test_rem_replays_recorded_in_night_file():
    e = asleep_engine()
    mem = Memory()
    mem.add(loc(2, "00:10"), "hello from tonight", "NREM", {"language": 6, "default": 6}, "neutral",
            ["language", "default"])
    replays, t = 0, loc(2, "00:05")
    while t < loc(2, "08:30"):
        for ev in e.update(t):
            if ev["type"] == "replay":
                assert e.stage == "REM"
                m = mem.pick(t, e.night_start())
                if m:
                    e.record_replay(t, m)
                    replays += 1
        t += 30
    assert replays > 0 and len(e.last_night["replays"]) == replays
    with tempfile.TemporaryDirectory() as d:
        Store(d).save(e, mem)
        night = json.loads((Path(d) / "nights" / f"{e.last_night['date']}.json").read_text())
        assert night["date"] == "2026-10-01"
        assert {"timeline", "wakeups", "sleep_debt", "replays"} <= set(night)
        assert night["replays"][0]["text"] == "hello from tonight"
        flat = json.dumps(night)
        assert "ip" not in night and "127.0.0.1" not in flat


def test_state_persists_across_restart():
    e = asleep_engine(at="03:00")
    e.debt = 1.7
    mem = Memory()
    mem.add(loc(2, "02:00"), "remember me", "REM", {"reward": 8}, "positive", ["reward"])
    with tempfile.TemporaryDirectory() as d:
        Store(d).save(e, mem)
        saved, items = Store(d).load()
        e2, mem2 = SleepEngine.from_dict(saved), Memory(items)
        assert e2.asleep and e2.stage == e.stage and e2.night["date"] == e.night["date"]
        assert abs(e2.debt - 1.7) < 1e-9 and e2.H == e.H and e2.V_v == e.V_v
        assert mem2.items[0]["text"] == "remember me"
        e2.update(loc(2, "09:00"))                      # some debt: it sleeps a little longer than 07:53
        assert not e2.asleep and e2.last_night is not None


if __name__ == "__main__":
    if "--time-scale" in sys.argv:
        TIME_SCALE = float(sys.argv[sys.argv.index("--time-scale") + 1])
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            t0 = time.time()
            try:
                fn()
                print(f"PASS {name} ({time.time() - t0:.1f}s)")
            except Exception as ex:
                failed += 1
                print(f"FAIL {name}: {type(ex).__name__}: {ex}")
    print(f"{'FAILED' if failed else 'OK'}: {failed} failed")
    sys.exit(1 if failed else 0)
