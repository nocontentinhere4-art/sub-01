"""Per-client websocket feed: /ws stays 20 ticks/s with everything; ?rate= and &lite=1 thin it without losing trades."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from live_server import TICK, Feed  # noqa: E402


LIFE = {"place": "bed", "activity": "phone", "hunger": 0.4,
        "vitals": {"hr_bpm": 64.0, "resp_per_min": 14.0, "glucose_mg_dl": 92.0}}
NEURO = {"DA": 1.0, "5HT": 0.9, "NE": 1.1, "ACh": 1.2}


def tick(i, trades=(), events=()):
    return {"type": "tick", "i": i, "act": [0.1] * 214, "wave": {"a": 1.0}, "groups": {"a": 0.1}, "slow": None,
            "trades": list(trades), "events": list(events), "life": LIFE, "neuro": NEURO, "sleep": {"stage": "AWAKE"}}


def run(feed, msgs):
    return [json.loads(o) if o is not None else None for o in (feed.take(m, json.dumps(m)) for m in msgs)]


def test_default_is_unchanged():
    f = Feed.from_query({})
    for m in [tick(0), {"type": "chat", "text": "hi"}, tick(1)]:
        data = json.dumps(m)
        assert f.take(m, data) is data


def test_rate_downsamples_and_carries_trades_and_events():
    f = Feed.from_query({"rate": "5"})
    assert f.every == round(1 / (TICK * 5))
    msgs = [tick(i, trades=[{"kind": "buy", "usd": i}] if i % 3 == 0 else [],
                 events=[{"type": "wake", "i": i}] if i == 6 else []) for i in range(12)]
    out = run(f, msgs)
    sent = [o for o in out if o is not None]
    assert [o["i"] for o in sent] == [0, 4, 8]                      # first at once, then every 4th
    got = [t["usd"] for o in sent for t in o["trades"]]
    assert got == [0, 3, 6]                                          # nothing lost up to the last sent tick
    assert [e["i"] for o in sent for e in o["events"]] == [6]
    assert sent[1]["act"] == msgs[4]["act"]                          # not lite: the brain arrays stay


def test_non_ticks_always_pass_through():
    f = Feed.from_query({"rate": "2", "lite": "1"})
    m = {"type": "screen", "device": "desk", "id": 3}
    data = json.dumps(m)
    assert f.take(m, data) is data


def test_lite_drops_brain_arrays_only():
    f = Feed.from_query({"lite": "1"})
    o = run(f, [tick(0, trades=[{"kind": "sell", "usd": 9}])])[0]
    assert "act" not in o and "wave" not in o and "groups" not in o and "slow" not in o
    assert o["life"] == LIFE and o["sleep"]["stage"] == "AWAKE" and o["trades"][0]["usd"] == 9


def test_bad_rates_fall_back_to_every_tick():
    for q in ({"rate": "abc"}, {"rate": "0"}, {"rate": "-5"}, {"rate": "nan"}, {"rate": "inf"}):
        assert Feed.from_query(q).every == 1
    assert Feed.from_query({"rate": "1000"}).every == 1               # faster than the tick: every tick


def test_lite_keeps_what_the_room_shows():
    """The room's cards need life (with the body's vitals), the neuromodulators, sleep, trades and events."""
    f = Feed.from_query({"rate": "5", "lite": "1"})
    msgs = [tick(i, trades=[{"kind": "buy", "usd": i}], events=[{"type": "replay", "i": i}]) for i in range(5)]
    sent = [o for o in run(f, msgs) if o is not None]
    last = sent[-1]
    assert last["life"]["vitals"] == LIFE["vitals"] and last["neuro"] == NEURO and last["sleep"]["stage"] == "AWAKE"
    assert [t["usd"] for o in sent for t in o["trades"]] == [0, 1, 2, 3, 4]
    assert [e["i"] for o in sent for e in o["events"]] == [0, 1, 2, 3, 4]


def test_rate_is_clamped_to_1_20_per_second():
    slowest, fastest = round(1 / (TICK * 1)), 1
    for q in ("1e-310", "1e-9", "0.5", "1"):                         # tiny rates: at least one tick a second
        assert Feed.from_query({"rate": q}).every == slowest, q    # (1e-310 used to raise OverflowError)
    for q in ("20", "1000", "1e308"):
        assert Feed.from_query({"rate": q}).every == fastest, q


def test_tiny_rate_does_not_buffer_without_bound():
    f = Feed.from_query({"rate": "1e-9", "lite": "1"})
    sent = 0
    for i in range(10 * f.every):
        sent += run(f, [tick(i, trades=[{"kind": "buy", "usd": 1}])])[0] is not None
        assert len(f.trades) < f.every                                # flushed at least once a second
    assert sent == 10

