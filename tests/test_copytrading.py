"""Paper execution, causal ordering, reversal, delayed credit and restart checks."""
import asyncio
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from copytrading import PaperConfig, PaperEngine, validate_feed
from copytrading.__main__ import main
from copytrading.api import attach
from copytrading.engine import trader_cue
from analysis.copytrade_benchmark import fixture


def quote(eid, t, **prices):
    return dict(id=eid, t=t, type="quote", source="observed", prices=prices)


def offer(eid, t, trader="alpha", asset="A"):
    return dict(id=eid, t=t, type="offer", source="observed", signals=[dict(trader=trader, asset=asset, side="buy")])


@pytest.mark.parametrize("mutate", [
    lambda es: es.append(dict(es[0])),
    lambda es: es[1].update(t=-1),
    lambda es: es[0]["prices"].update(A=float("nan")),
    lambda es: es[0]["prices"].update(A=0),
    lambda es: es[1]["signals"][0].update(side="sell"),
    lambda es: es[1]["signals"].append(dict(es[1]["signals"][0])),
    lambda es: es[1].update(source="unknown"),
])
def test_invalid_input_has_no_effect(mutate):
    events = [quote("q", 0, A=100), offer("o", 1)]
    mutate(events)
    engine = PaperEngine()
    with pytest.raises(ValueError):
        engine.replay(events)
    assert engine.cash == 1000 and not engine.decisions


def test_roundtrip_fees_slippage_cash_and_exact_once_settlement():
    events = [quote("q", 0, A=100), offer("o", 1), quote("exit", 61, A=110), quote("again", 62, A=999)]
    result = PaperEngine().replay(events)
    ret = 110*.997*.998 / (100*1.003*1.002) - 1
    assert result["realized_pnl"] == pytest.approx(100*ret)
    assert result["cash"] == pytest.approx(1000 + 100*ret)
    assert len(result["closed"]) == 1 and not result["unresolved"]
    assert result["reputation"]["alpha"]["observations"] == 1


def test_future_quote_does_not_change_earlier_decision():
    before = [quote("q", 0, A=100), offer("o", 1)]
    a = PaperEngine().replay(before + [quote("later", 61, A=200)])
    b = PaperEngine().replay(before + [quote("later", 61, A=1)])
    assert a["decisions"] == b["decisions"]
    assert a["realized_pnl"] > 0 > b["realized_pnl"]


def test_wallet_identifiers_remain_distinct_after_native_tokenization():
    from spiking.words import words
    assert words(trader_cue("wallet123")) != words(trader_cue("wallet456"))
    assert trader_cue("wallet123") == trader_cue("wallet123")


def test_missing_or_stale_quote_never_fills_and_never_fabricates_exit():
    result = PaperEngine().replay([offer("missing", 0), quote("q", 1, A=100), offer("stale", 30),
                                  quote("q2", 31, A=100), offer("valid", 32), quote("other", 999, B=100)])
    assert [d["pick"] for d in result["decisions"]] == ["cash", "cash", "alpha"]
    assert result["realized_pnl"] == 0 and result["open_cost"] == 100
    assert result["unresolved"][0]["overdue"] and result["balance_at_cost"] == 1000


def test_no_overallocation_and_no_early_close():
    events = [quote("q", 0, A=100)] + [offer(f"o{i}", i) for i in range(1, 8)] + [quote("early", 30, A=110)]
    result = PaperEngine().replay(events)
    assert len(result["unresolved"]) == 4 and len(result["closed"]) == 0
    assert result["cash"] == 600
    assert all(d["reason"] == "capacity limit" for d in result["decisions"][4:])


def test_reputation_relearns_after_reversal_and_beats_controls_on_constructed_fixture():
    events = fixture(92)
    a = PaperEngine().replay(events)
    b = PaperEngine(policy="fixed").replay(events)
    c = PaperEngine(policy="random").replay(events)
    assert a["realized_pnl"] > b["realized_pnl"] and a["realized_pnl"] > c["realized_pnl"]
    assert sum(d["pick"] == "alpha" for d in a["decisions"][30:50]) >= 16
    assert sum(d["pick"] == "charlie" for d in a["decisions"][80:]) >= 16
    assert a["reputation"]["alpha"]["score"] < a["reputation"]["charlie"]["score"]
    assert a["reputation"]["alpha"]["recent_n"] == 20
    assert a["reputation"]["alpha"]["observations"] == 100


class FakeBrain:
    def __init__(self):
        self.pending, self.rewards, self.discarded = {}, [], []

    def decide(self, labels, did):
        self.pending[did] = list(labels)
        return dict(pick=0, pool_rates=[3.0]*len(labels))

    def learn(self, did, followed, delta):
        assert did in self.pending and 0 <= followed < len(self.pending[did])
        self.pending.pop(did)
        self.rewards.append((did, followed, delta))
        return dict(ok=True)

    def discard(self, did):
        self.pending.pop(did)
        self.discarded.append(did)

    def status(self):
        return dict(n_learn=len(self.rewards))


def test_delayed_credit_goes_to_original_decision_not_latest_and_cash_discards_tag():
    brain = FakeBrain()
    events = [quote("q", 0, A=100, B=100), offer("first", 1), offer("second", 2, "bravo", "B"),
              quote("b", 62, B=50), quote("a", 63, A=110)]
    result = PaperEngine(brain=brain).replay(events)
    assert [r[0] for r in brain.rewards] == ["second", "first"]
    assert brain.rewards[0][2] < 0 < brain.rewards[1][2]
    assert not brain.pending and all(r["ok"] for r in result["learning"])
    brain = FakeBrain()
    PaperEngine(brain=brain, policy="cash").replay([quote("q", 0, A=100), offer("o", 1)])
    assert brain.discarded == ["o"] and not brain.pending


def write_feed(path, events):
    path.write_text("".join(json.dumps(e)+"\n" for e in events))


def test_restart_replays_open_positions_and_memory_exactly_and_rejects_duplicate(tmp_path):
    events = fixture(3, 20)
    first, second, full = [tmp_path / name for name in ("first.jsonl", "second.jsonl", "full.jsonl")]
    split = 17  # deliberately ends while a position is open
    write_feed(first, events[:split])
    write_feed(second, events[split:])
    write_feed(full, events)
    args = ["--controller-only", "--data-dir", str(tmp_path / "resumed")]
    main(args + ["--feed", str(first)])
    resumed = main(args + ["--feed", str(second), "--resume"])
    fresh = main(["--controller-only", "--data-dir", str(tmp_path / "fresh"), "--feed", str(full)])
    assert resumed == fresh
    snapshot = tmp_path / "resumed" / "copytrading" / "paper.json"
    old = snapshot.read_bytes()
    with pytest.raises(ValueError):
        main(args + ["--feed", str(second), "--resume"])
    assert snapshot.read_bytes() == old


def test_read_only_api_no_post_route_and_off_then_snapshot(tmp_path):
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from state_io import save_json
    async def go():
        app = web.Application()
        attach(app, tmp_path)
        async with TestClient(TestServer(app)) as client:
            assert (await (await client.get("/api/copytrading")).json())["state"] == "off"
            path = tmp_path / "copytrading" / "paper.json"
            path.parent.mkdir()
            save_json(path, dict(report=dict(mode="paper", source="synthetic"), feed_hash="abc"))
            assert (await (await client.get("/api/copytrading")).json())["source"] == "synthetic"
            assert (await client.post("/api/copytrading", json={})).status == 405
    asyncio.run(go())


def test_native_brain_learns_from_paper_outcomes_and_keeps_valid_late_reward_after_bad_input():
    from copytrading.native import NativeBrain
    brain = NativeBrain(5000, seed=77)
    result = PaperEngine(brain=brain).replay(fixture(4, 8))
    assert result["brain"]["n_learn"] == len(result["closed"]) > 0
    assert all(r["ok"] for r in result["learning"])
    assert (abs(brain.brain.dw) > 0).any()
    brain.decide(["trader alpha", "hold cash"], did="late")
    assert not brain.learn("late", 0, float("nan"))["ok"]
    assert brain.learn("late", 0, .2)["ok"]
    assert not brain.learn("late", 0, .2)["ok"]


def test_native_replay_restart_is_identical_including_learned_weights(tmp_path):
    events = fixture(5, 8)
    feed = tmp_path / "feed.jsonl"
    tail = tmp_path / "tail.jsonl"
    full = tmp_path / "full.jsonl"
    write_feed(feed, events[:8])
    write_feed(tail, events[8:])
    write_feed(full, events)
    args = ["--neurons", "5000", "--diagnostic-small-network", "--data-dir", str(tmp_path / "resume")]
    main(args + ["--feed", str(feed)])
    a = main(args + ["--feed", str(tail), "--resume"])
    b = main(["--neurons", "5000", "--diagnostic-small-network", "--data-dir", str(tmp_path / "fresh"), "--feed", str(full)])
    assert a == b


def test_native_size_upgrade_preserves_old_weights(tmp_path):
    from spiking.live import LiveBrain
    path = tmp_path / "weights.npz"
    first = LiveBrain(5000, path, twin=False)
    first.decide(["alpha", "bravo"], did="a")
    first.learn("a", 0, .3)
    old = path.read_bytes()
    upgraded = LiveBrain(6000, path, twin=False)
    assert upgraded.n_learn == 0
    backups = list(tmp_path.glob("weights.npz.incompatible-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == old


def test_profiles_and_large_cpu_allocations_are_blocked_before_build():
    from spiking.profiles import neurons_for
    from copytrading.native import NativeBrain, TorchBrain
    assert neurons_for("simple") == 100000
    assert neurons_for("trading") == 500000
    assert neurons_for("night") == 1000000
    with pytest.raises(ValueError):
        NativeBrain(500000)
    pytest.importorskip("torch")
    with pytest.raises(ValueError):
        TorchBrain(500000, device="cpu")


def test_torch_adapter_credits_actual_followed_pool_and_preserves_invalid_tag():
    pytest.importorskip("torch")
    from copytrading.native import TorchBrain
    brain = TorchBrain(5000, device="cpu", seed=5)
    decision = brain.decide(["trader alpha", "trader bravo", "hold cash"], did="credit")
    followed = (decision["pick"] + 1) % 3
    q, pre, owners, _ = brain.pending["credit"]
    before = brain.net.plast.dw.clone()
    assert not brain.learn("credit", followed, float("nan"))["ok"]
    assert brain.learn("credit", followed, .5)["ok"]
    update = (brain.net.plast.dw-before)[q].cpu().numpy()
    assert (update[owners == followed] > 0).any()
    assert (update[owners != followed] < 0).any()
    assert not brain.learn("credit", followed, .5)["ok"]


def test_concurrent_importer_is_rejected_without_snapshot_write(tmp_path):
    from copytrading.__main__ import writer_lock
    feed = tmp_path / "feed.jsonl"
    write_feed(feed, fixture(7, 2))
    data = tmp_path / "data"
    with writer_lock(data / "copytrading" / ".writer.lock"):
        with pytest.raises(RuntimeError, match="another paper importer"):
            main(["--controller-only", "--feed", str(feed), "--data-dir", str(data)])
    assert not (data / "copytrading" / "paper.json").exists()
