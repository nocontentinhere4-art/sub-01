"""Chronological paper broker + bounded, recent-outcome reputation controller.

The reputation model is external to the spiking brain. It learns from prospective
shadow observations, while the native brain receives credit only for copied trades.
No wallet, order submission, credentials or network client exists in this module.
"""
from dataclasses import asdict, dataclass
import hashlib
import math
import random
import statistics


@dataclass(frozen=True)
class PaperConfig:
    balance: float = 1000.0
    allocation: float = 0.1
    fee_bps: float = 20.0
    slippage_bps: float = 30.0
    horizon_s: float = 60.0
    max_quote_age_s: float = 15.0
    max_open: int = 4
    memory_window: int = 20
    min_observations: int = 2
    uncertainty: float = 0.5
    native_weight: float = 0.001
    exploration: float = 0.05
    reward_scale: float = 0.1
    seed: int = 1

    def __post_init__(self):
        for name in ("balance", "horizon_s", "max_quote_age_s", "reward_scale"):
            if not math.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("fee_bps", "slippage_bps"):
            if not math.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) < 10000:
                raise ValueError(f"invalid {name}")
        for name in ("allocation", "exploration", "native_weight", "uncertainty"):
            if not math.isfinite(getattr(self, name)) or not 0 <= getattr(self, name) <= 1:
                raise ValueError(f"invalid {name}")
        if not 0 < self.allocation <= 0.25:
            raise ValueError("allocation must be in (0, .25]")
        for name in ("max_open", "memory_window", "min_observations", "seed"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if not 1 <= self.max_open <= 4 or self.memory_window < 2 or not 1 <= self.min_observations <= self.memory_window:
            raise ValueError("invalid capacity or observation limits")


def number(x, positive=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or (positive and x <= 0):
        raise ValueError("expected finite numeric value" + (" > 0" if positive else ""))
    return float(x)


def identifier(x):
    if not isinstance(x, str) or not 1 <= len(x) <= 64 or not x.isascii() or not all(c.isalnum() or c in "_-.:" for c in x):
        raise ValueError("expected a short ASCII identifier")
    return x


def trader_cue(trader):
    # The shared language tokenizer removes digits/punctuation. Raw wallet-like
    # identifiers (e.g. trader123/trader456) would otherwise collapse to one cue.
    digest = hashlib.sha256(trader.encode()).hexdigest()[:32]
    return "trader " + "".join(chr(ord("a") + int(c, 16)) for c in digest)


def validate_feed(events):
    """Fail the entire import on malformed, duplicated or out-of-order data."""
    if not isinstance(events, list) or len(events) > 10000:
        raise ValueError("feed must be a list of at most 10000 events")
    seen, previous = set(), -math.inf
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("event must be an object")
        eid, timestamp = identifier(event.get("id")), number(event.get("t"))
        if eid in seen or timestamp < previous:
            raise ValueError("duplicate event id or out-of-order timestamp")
        seen.add(eid)
        previous = timestamp
        if event.get("source") not in ("synthetic", "observed"):
            raise ValueError("source must be synthetic or observed")
        if event.get("type") == "quote":
            if not isinstance(event.get("prices"), dict) or not event["prices"] or len(event["prices"]) > 100:
                raise ValueError("quote needs 1-100 prices")
            for asset, price in event["prices"].items():
                identifier(asset)
                number(price, positive=True)
        elif event.get("type") == "offer":
            signals = event.get("signals")
            if not isinstance(signals, list) or not 1 <= len(signals) <= 5:
                raise ValueError("offer needs 1-5 signals (plus cash)")
            traders = set()
            for signal in signals:
                if not isinstance(signal, dict):
                    raise ValueError("signal must be an object")
                trader = identifier(signal.get("trader"))
                identifier(signal.get("asset"))
                if trader == "cash" or trader in traders or signal.get("side") != "buy":
                    raise ValueError("unique traders, buy observations only; cash is reserved")
                traders.add(trader)
        else:
            raise ValueError("unknown event type")
    return events


class PaperEngine:
    def __init__(self, config=None, brain=None, policy="adaptive"):
        self.cfg = config or PaperConfig()
        if policy not in ("adaptive", "random", "fixed", "cash"):
            raise ValueError("unknown policy")
        self.brain, self.policy = brain, policy
        self.rng = random.Random(self.cfg.seed)
        self.cash = self.cfg.balance
        self.prices, self.memory, self.total_observations = {}, {}, {}
        self.open, self.shadows, self.decisions, self.closed = [], [], [], []
        self.learning = []
        self.now = None

    def reputation(self, trader):
        values = self.memory.get(trader, [])
        n = len(values)
        mean = statistics.mean(values) if n else 0.0
        sd = max(0.05, statistics.stdev(values)) if n > 1 else 0.05
        penalty = self.cfg.uncertainty * sd / math.sqrt(max(1, n))
        return {"observations": self.total_observations.get(trader, 0), "recent_n": n,
                "mean_net_return": mean, "uncertainty_penalty": penalty, "score": mean - penalty}

    def _return(self, entry, exit_price):
        fee, slip = self.cfg.fee_bps / 10000, self.cfg.slippage_bps / 10000
        return exit_price * (1 - slip) * (1 - fee) / (entry * (1 + slip) * (1 + fee)) - 1

    def _observe(self, trader, value):
        self.memory[trader] = (self.memory.get(trader, []) + [value])[-self.cfg.memory_window:]
        self.total_observations[trader] = self.total_observations.get(trader, 0) + 1

    def _settle(self, updates):
        # A new, observed quote is required. Never exit using an old cached price.
        for shadow in list(self.shadows):
            if self.now < shadow["due"] or shadow["asset"] not in updates:
                continue
            value = self._return(shadow["entry"], updates[shadow["asset"]])
            self._observe(shadow["trader"], value)
            self.shadows.remove(shadow)
        for pos in list(self.open):
            if self.now < pos["due"] or pos["asset"] not in updates:
                continue
            ret = self._return(pos["entry"], updates[pos["asset"]])
            proceeds = pos["stake"] * (1 + ret)
            self.cash += proceeds
            result = dict(pos, exit_t=self.now, exit_price=updates[pos["asset"]],
                          net_return=ret, pnl=proceeds - pos["stake"], proceeds=proceeds,
                          exit_delay_s=self.now - pos["due"])
            self.closed.append(result)
            self.open.remove(pos)
            if self.brain is not None:
                reward = max(-1.0, min(1.0, ret / self.cfg.reward_scale))
                expected = max(-1.0, min(1.0, pos["expected"] / self.cfg.reward_scale))
                learned = self.brain.learn(pos["id"], pos["pick"], (reward - expected) / 2.0)
                self.learning.append(dict(id=pos["id"], reward=reward, expected=expected, **learned))

    def _offer(self, event):
        eligible = [s for s in event["signals"] if s["asset"] in self.prices and
                    0 <= self.now - self.prices[s["asset"]][1] <= self.cfg.max_quote_age_s]
        eligible.sort(key=lambda s: s["trader"])
        row = {"id": event["id"], "t": self.now, "source": event["source"], "mode": "paper",
               "offered": event["signals"], "eligible": eligible, "pick": "cash", "reason": None}
        self.decisions.append(row)
        if not eligible or len(self.open) >= self.cfg.max_open or len(self.shadows) + len(eligible) > 200:
            row["reason"] = "no fresh quotes" if not eligible else "capacity limit"
            return
        labels = [trader_cue(s["trader"]) for s in eligible] + ["hold cash"]
        native = self.brain.decide(labels, did=event["id"]) if self.brain else None
        rates = native["pool_rates"] if native else [0.0] * len(labels)
        avg = sum(rates) / len(rates)
        lean = [math.tanh((r - avg) / 2) for r in rates]
        reps = [self.reputation(s["trader"]) for s in eligible]
        scores = [r["score"] + self.cfg.native_weight * lean[i] for i, r in enumerate(reps)]
        scores.append(self.cfg.native_weight * lean[-1])
        row.update(reputation=reps, scores=scores, native=native, neural_labels=labels,
                   controller="external recent-return model + bounded native spiking preference")
        if self.policy == "cash":
            pick, reason = len(eligible), "cash control"
        elif self.policy == "random":
            pick, reason = self.rng.randrange(len(labels)), "random control"
        elif self.policy == "fixed":
            pick, reason = 0, "fixed trader control"
        else:
            untested = [i for i, r in enumerate(reps) if r["observations"] < self.cfg.min_observations]
            if untested:
                pick, reason = min(untested, key=lambda i: (reps[i]["observations"], i)), "bounded cold-start exploration"
            elif self.rng.random() < self.cfg.exploration:
                pick, reason = self.rng.randrange(len(labels)), "bounded exploration"
            else:
                pick, reason = max(range(len(scores)), key=lambda i: scores[i]), "recent net return minus uncertainty + native preference"
        row.update(reason=reason, followed_index=pick)
        # Counterfactual tracking is prospective: the prices below are all known NOW.
        for signal in eligible:
            self.shadows.append(dict(trader=signal["trader"], asset=signal["asset"],
                                     entry=self.prices[signal["asset"]][0], due=self.now + self.cfg.horizon_s))
        if pick == len(eligible):
            if self.brain:
                self.brain.discard(event["id"])
            return
        signal = eligible[pick]
        stake = min(self.cash, self.cfg.balance * self.cfg.allocation)
        if stake <= 0:
            row["reason"] = "no available paper cash"
            if self.brain:
                self.brain.discard(event["id"])
            return
        self.cash -= stake
        row["pick"] = signal["trader"]
        row["asset"] = signal["asset"]
        self.open.append(dict(id=event["id"], trader=signal["trader"], asset=signal["asset"],
                              entry=self.prices[signal["asset"]][0], entry_t=self.now,
                              due=self.now + self.cfg.horizon_s, stake=stake, pick=pick,
                              expected=reps[pick]["mean_net_return"]))

    def replay(self, events):
        validate_feed(events)
        if self.now is not None:
            raise ValueError("replay requires a fresh engine")
        for event in events:
            self.now = event["t"]
            if event["type"] == "quote":
                self.prices.update({a: (p, self.now) for a, p in event["prices"].items()})
                self._settle(event["prices"])
            else:
                self._offer(event)
        return self.report()

    def report(self):
        # Unresolved positions are reported at cost, NOT silently called profitable.
        cost = sum(p["stake"] for p in self.open)
        return {"mode": "paper", "policy": self.policy, "config": asdict(self.cfg),
                "input_time": self.now, "cash": self.cash, "open_cost": cost,
                "balance_at_cost": self.cash + cost, "realized_pnl": sum(p["pnl"] for p in self.closed),
                "unresolved": [dict(p, overdue=self.now >= p["due"]) for p in self.open],
                "shadow_pending": len(self.shadows), "closed": self.closed, "decisions": self.decisions,
                "reputation": {t: self.reputation(t) for t in sorted(self.memory)},
                "learning": self.learning, "brain": self.brain.status() if self.brain else None,
                "limits": "Long-only fixed-horizon paper copies; quoted-price fills with assumed fees/slippage. No liquidity, MEV or transaction-failure model. No Fomo connector."}


def feed_hash(events):
    import json
    return hashlib.sha256(json.dumps(events, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()
