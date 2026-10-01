"""Phase A tests: sleep engine, chat filter/rules, memory replay.

    python tests/test_sleep.py [--time-scale 3600]      # or: python -m pytest tests/
The stage-cycling test runs the engine on a real accelerated clock (--time-scale, default
3600 = one sim hour per real second); the others step sim time directly.
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
from sleep import ROME, Clock, Memory, SleepEngine, Store, WAKE_THRESHOLD

TIME_SCALE = 3600.0


def rome(day, hm):
    """Sim epoch for 2026-10-<day> HH:MM Rome time."""
    h, m = map(int, hm.split(":"))
    return datetime(2026, 10, day, h, m, tzinfo=ROME).timestamp()


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
    e = SleepEngine(rome(day, "08:00"), rng=random.Random(0))
    run(e, rome(day, "08:00"), rome(day + 1, at) if at < "08:00" else rome(day, at), step=120)
    assert e.asleep, "should be asleep"
    return e


# --- sleep engine ------------------------------------------------------------------------------
def test_stage_cycling_on_accelerated_clock():
    """Real run: clock at --time-scale from 23:50; expect AWAKE -> NREM -> REM -> NREM within ~4 sim hours."""
    clock = Clock(TIME_SCALE, rome(1, "23:50"))
    e = SleepEngine(rome(1, "08:00"), rng=random.Random(0))
    e.update(rome(1, "23:40"))
    seq, prev = [], time.time()
    while clock.now() < rome(2, "04:00"):
        time.sleep(0.01)
        now = time.time()
        e.update(clock.now(), dt_real=now - prev)
        prev = now
        if not seq or seq[-1] != e.stage:
            seq.append(e.stage)
    assert seq[:4] == ["AWAKE", "NREM", "REM", "NREM"], seq


def test_rem_grows_and_nrem_deepest_early():
    e = asleep_engine()
    stages, _ = run(e, rome(2, "00:05"), rome(2, "07:55"), step=60)
    rem_min = [0] * 6
    deep = [0.0] * 6
    for t, s in stages:
        k = int((t - rome(2, "00:00")) // (90 * 60))
        if k < 6 and s == "REM":
            rem_min[k] += 1
    e2 = asleep_engine()
    for t in np.arange(rome(2, "00:05"), rome(2, "07:55"), 60):
        e2.update(t)
        k = int((t - rome(2, "00:00")) // (90 * 60))
        if k < 6:
            deep[k] = max(deep[k], e2.depth)
    assert rem_min[0] < rem_min[3], rem_min
    assert deep[0] > deep[3], deep


def test_wakes_at_eight_and_writes_timeline():
    e = asleep_engine()
    _, ev = run(e, rome(2, "00:05"), rome(2, "08:10"), step=60)
    assert not e.asleep and e.last_night is not None
    assert any(x["type"] == "wake" and x.get("natural") for x in ev)
    stages = [x["stage"] for x in e.last_night["timeline"]]
    assert "NREM" in stages and "REM" in stages and stages[-1] == "AWAKE"


def test_transitions_are_smooth():
    e = SleepEngine(rome(1, "23:58"), rng=random.Random(0))
    freqs = []
    for i in range(0, 20 * 60, 5):                     # 5 s sim steps across the fall-asleep transition
        e.update(rome(1, "23:58") + i)
        freqs.append(e.params["f_hz"])
    jumps = np.abs(np.diff(freqs))
    assert freqs[0] > 9 and freqs[-1] < 4, (freqs[0], freqs[-1])
    assert jumps.max() < 1.5, jumps.max()             # 10 Hz -> ~1-3 Hz glides over > a minute
    # high time-scale: dt_real limits the step even if a tick covers minutes of sim time
    e2 = SleepEngine(rome(1, "23:58"), rng=random.Random(0))
    e2.update(rome(1, "23:59"))
    e2.update(rome(2, "00:20"), dt_real=0.05)
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
    t0 = rome(2, "02:00")
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
    t0 = rome(2, "03:00")
    _, ev = run(e, t0, t0 + 60, step=10, stimuli=[(t0 + 5, "trade", 20000)])
    assert any(x["type"] == "wake" and "large trade" in x["text"] for x in ev), ev


def test_small_trades_do_not_wake_it():
    e = asleep_engine(at="03:00")
    t0 = rome(2, "03:00")
    run(e, t0, t0 + 600, step=5, stimuli=[(t0 + i, "trade", 300) for i in range(0, 600, 2)])
    assert e.asleep and e.arousal < WAKE_THRESHOLD


def test_debt_rises_after_wakeups_and_lowers_next_day_gain():
    quiet, noisy = asleep_engine(), asleep_engine()
    t0 = rome(2, "00:05")
    run(quiet, t0, rome(2, "10:00"), step=30)
    wake_bursts = [(rome(2, h) + 15 * i, "message", 0) for h in ("01:30", "03:00", "04:30", "06:00") for i in range(6)]
    _, ev = run(noisy, t0, rome(2, "10:00"), step=15, stimuli=wake_bursts)
    assert sum(x["type"] == "wake" and not x.get("natural") for x in ev) == 4
    assert noisy.debt > quiet.debt + 0.5, (noisy.debt, quiet.debt)
    assert noisy.gain < quiet.gain, (noisy.gain, quiet.gain)
    assert noisy.params["noise"] > quiet.params["noise"]
    assert noisy.last_night["sleep_debt"]["end"] > noisy.last_night["sleep_debt"]["start"]


def test_high_debt_falls_asleep_early_and_recovers():
    e = SleepEngine(rome(1, "08:00"), rng=random.Random(0))
    e.debt = 3.0
    run(e, rome(1, "08:00"), rome(1, "21:30"), step=120)
    assert e.asleep, "tired brain should go to bed before midnight"
    d = e.debt
    run(e, rome(1, "21:30"), rome(2, "07:00"), step=120)
    assert e.debt < d


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
    mem.add(rome(1, "12:00"), "old day message", "AWAKE", {"language": 6}, "neutral", ["language"])
    mem.add(rome(1, "20:00"), "evening message", "AWAKE", {"language": 6}, "neutral", ["language"])
    mem.add(rome(2, "01:00"), "tonight message", "NREM", {"language": 6}, "neutral", ["language"])
    rng = random.Random(1)
    picks = [mem.pick(rome(2, "02:00"), e.night_start(), rng)["text"] for _ in range(500)]
    assert picks.count("tonight message") > 0.6 * len(picks), {p: picks.count(p) for p in set(picks)}
    # emotion raises the odds between otherwise equal messages
    mem2 = Memory()
    mem2.add(rome(2, "01:00"), "calm", "NREM", {}, "neutral", [])
    mem2.add(rome(2, "01:00"), "scary", "NREM", {}, "threat", [])
    picks = [mem2.pick(rome(2, "02:00"), e.night_start(), rng)["text"] for _ in range(500)]
    assert picks.count("scary") > picks.count("calm")
    # habituation: a memory already replayed many times tonight loses its lead
    mem3 = Memory()
    mem3.add(rome(2, "01:00"), "scary", "NREM", {}, "threat", [])
    mem3.add(rome(2, "01:01"), "calm", "NREM", {}, "neutral", [])
    worn = {Memory.key(mem3.items[0]): 9}                 # "scary", received 01:00
    picks = [mem3.pick(rome(2, "02:00"), e.night_start(), rng, worn)["text"] for _ in range(500)]
    assert picks.count("calm") > picks.count("scary")


def test_rem_replays_recorded_in_night_file():
    e = asleep_engine()
    mem = Memory()
    mem.add(rome(2, "00:10"), "hello from tonight", "NREM", {"language": 6, "default": 6}, "neutral",
            ["language", "default"])
    replays, t = 0, rome(2, "00:05")
    while t < rome(2, "08:30"):
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
    mem.add(rome(2, "02:00"), "remember me", "REM", {"reward": 8}, "positive", ["reward"])
    with tempfile.TemporaryDirectory() as d:
        Store(d).save(e, mem)
        saved, items = Store(d).load()
        e2, mem2 = SleepEngine.from_dict(saved), Memory(items)
        assert e2.asleep and e2.stage == e.stage and e2.debt == 1.7 and e2.night["date"] == e.night["date"]
        assert mem2.items[0]["text"] == "remember me"
        e2.update(rome(2, "08:05"))
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
