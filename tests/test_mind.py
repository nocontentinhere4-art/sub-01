"""Tests for mind.py: the Global-Workspace-inspired competition, broadcast, self-model, diary and safety filter.

    /home/user/sub-01/.venv/bin/python -m pytest tests/test_mind.py -q
All tests use seeded rngs and a fake real-time clock, so they are deterministic.
"""
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import chat
import mind
from mind import DiaryStore, Mind, TPL, safe_text
from sleep import ROME

T0 = datetime(2026, 10, 1, 15, 0, tzinfo=ROME).timestamp()     # an afternoon, bakery open


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


def make(seed=1, **kw):
    clock = FakeClock()
    return Mind(rng=random.Random(seed), clock_fn=clock, **kw), clock


def ctx(stage="AWAKE", rel=None, hunger=0.1, boredom=0.1, bread=0, activity="window", place="window",
        market="calm", memories=None, replays=None, viewers=0, energy=1.0, **life_extra):
    life = {"place": place, "activity": activity, "walking": False, "hunger": hunger, "boredom": boredom,
            "bread": bread, "doing": "looking out of the window", "energy": energy, **life_extra}
    return {"stage": stage, "rel": rel or {}, "needs": {"hunger": hunger, "boredom": boredom},
            "life": life, "market": market, "memories": memories or [], "replays": replays or [],
            "viewers": viewers}


def msg(text, nick=""):
    _, nets, emo = chat.stimulus(text)
    return {"text": text, "nick": nick, "networks": nets, "regions": [], "emotion": emo, "stage": "AWAKE"}


def settle(m, clock, c, t=T0, n=15):
    """Run a few cycles so first-sight perceptions are no longer novel and the page state is steady."""
    for i in range(n):
        m.cycle(t + i * 2, c)
        m.speech_due()
        clock.advance(2)
    clock.advance(60)                              # every earlier winner is out of inhibition


# ---- competition --------------------------------------------------------------------------------------------
def test_cycle_output_shape_and_json():
    m, clock = make()
    out = m.cycle(T0, ctx())
    assert out["type"] == "mind" and out["cycle"] == 1 and out["t"] == "15:00"
    assert set(out) >= {"candidates", "winner", "broadcast", "self"}
    for c in out["candidates"]:
        assert set(c) >= {"id", "kind", "label", "salience", "source"} and c["salience"] >= 0
    assert set(out["self"]) >= {"doing", "feeling", "wanting", "history"}
    json.dumps(out)


def test_competition_picks_the_most_salient():
    m, clock = make()
    settle(m, clock, ctx())
    cid = m.hear(msg("the street looks quiet today"), T0)
    out = m.cycle(T0 + 40, ctx())
    sal = [c["salience"] for c in out["candidates"]]
    assert sal == sorted(sal, reverse=True)
    assert out["winner"] == cid == out["candidates"][0]["id"]
    assert out["broadcast"]["kind"] == "chat"
    # without a message, a strong need wins
    m2, clock2 = make()
    settle(m2, clock2, ctx())
    out = m2.cycle(T0 + 40, ctx(hunger=0.9))
    assert out["winner"] == "need:hunger"


def test_ignition_threshold_no_winner_when_nothing_is_salient():
    m, clock = make()
    settle(m, clock, ctx(hunger=0.0, boredom=0.0))
    winners = []
    for i in range(10):
        winners.append(m.cycle(T0 + 100 + 2 * i, ctx(hunger=0.0, boredom=0.0))["winner"])
        clock.advance(2)
    assert winners.count(None) >= 8


def test_brain_activity_changes_the_winner():
    def run(rel):
        m, clock = make(seed=3)
        settle(m, clock, ctx())
        threat = m.hear(msg("danger, fire in the street"), T0)
        clock.advance(80)
        calm = m.hear(msg("the street looks quiet today"), T0 + 80)
        return m.cycle(T0 + 80, ctx(rel=rel))["winner"], threat, calm

    w, threat, calm = run({})
    assert w == calm                                    # baseline: the fresher message wins
    w, threat, calm = run({"fear": 3.0, "salience": 2.0})
    assert w == threat                                  # high fear activity boosts the threat message


def test_inhibition_of_return():
    m, clock = make()
    settle(m, clock, ctx())
    c = ctx(hunger=0.9, boredom=0.8)
    assert m.cycle(T0 + 100, c)["winner"] == "need:hunger"
    clock.advance(2)
    out = m.cycle(T0 + 102, c)
    assert out["winner"] != "need:hunger"
    hunger = next(x for x in out["candidates"] if x["id"] == "need:hunger")
    assert hunger["salience"] < 0.5
    clock.advance(35)
    assert m.cycle(T0 + 137, c)["winner"] == "need:hunger"      # released after the IOR window


def test_deterministic_given_seed():
    def run():
        m, clock = make(seed=7)
        m.hear(msg("vai a prendere il pane", "marco"), T0)
        outs = []
        for i in range(30):
            outs.append(m.cycle(T0 + 2 * i, ctx(hunger=0.5, boredom=0.6)))
            clock.advance(2)
        return json.dumps(outs)
    assert run() == run()


# ---- stage gating ---------------------------------------------------------------------------------------------
def memories(n=50):
    emo = ["neutral", "positive", "threat"]
    return [{"t": T0 - 3600 * (i % 20) - i, "text": f"message number {i}", "stage": "AWAKE",
             "stimulus": {"language": 6.0}, "emotion": emo[i % 3], "networks": ["language", "somatomotor"]}
            for i in range(n)]


def test_nrem_is_mostly_silence():
    m, clock = make()
    m.hear(msg("hello, are you there?"), T0)
    winners = []
    for i in range(20):
        out = m.cycle(T0 + 2 * i, ctx(stage="NREM", hunger=0.9, memories=memories(), replays=["gm sub"]))
        winners.append(out["winner"])
        assert all(c["gated"] for c in out["candidates"] if c["kind"] not in ("dream", "memory"))
        clock.advance(2)
    assert winners.count(None) >= 18
    assert m.speech_due() is None


def test_asleep_only_dreams_or_memories_win_and_rem_dreams():
    m, clock = make()
    m.hear(msg("go buy some bread"), T0)
    kinds = set()
    for i in range(20):
        out = m.cycle(T0 + 2 * i, ctx(stage="REM", hunger=0.9, memories=memories(),
                                      replays=["sweet dreams sub", "the chart is red"]))
        if out["winner"]:
            kinds.add(out["broadcast"]["kind"])
            assert out["broadcast"]["action"] is None       # no actions while asleep
        clock.advance(2)
    assert kinds and kinds <= {"dream", "memory"} and "dream" in kinds
    assert m.self_model["doing"].startswith("sleeping")


def test_rem_dream_wins_over_gated_chat():
    m, clock = make()
    cid = m.hear(msg("danger, fire!!"), T0)
    out = m.cycle(T0, ctx(stage="REM", replays=["sweet dreams sub"]))
    assert out["winner"].startswith("dream:")
    chat_c = next(c for c in out["candidates"] if c["id"] == cid)
    assert chat_c["gated"]
    line = m.speech_due()
    assert line and "sweet dreams" in line["text"] and safe_text(line["text"])


# ---- broadcast -> action proposal, outcome lines -----------------------------------------------------------
def test_chat_about_bread_wins_and_proposes_buy_bread_then_decline_reason():
    m, clock = make()
    settle(m, clock, ctx(hunger=0.3))
    cid = m.hear(msg("go buy some bread please", "ada"), T0 + 40)
    out = m.cycle(T0 + 40, ctx(hunger=0.3, bread=0))
    assert out["winner"] == cid
    b = out["broadcast"]
    assert b["action"]["act"] == "buy_bread" and b["encode"] and b["lang"] == "en"
    assert "buy_bread" in m.focus()
    line = m.outcome("buy_bread", False, "the bakery is closed (opens 07:00)", T0 + 40)
    assert "closed" in line
    sp = m.speech_due()
    assert sp["text"] == line and sp["action"] == {"act": "buy_bread", "ok": False,
                                                   "reason": "the bakery is closed (opens 07:00)"}
    assert m.history[-1]["action"]["ok"] is False
    # the same act is not re-proposed right after a decline
    m.hear(msg("bread bread, get bread"), T0 + 42)
    clock.advance(2)
    out = m.cycle(T0 + 42, ctx(hunger=0.3, bread=0))
    assert out["broadcast"] and out["broadcast"]["action"] is None


def test_italian_bread_message_and_decline_reasons():
    m, clock = make()
    settle(m, clock, ctx())
    m.hear(msg("vai a prendere il pane", "marco"), T0 + 40)
    b = m.cycle(T0 + 40, ctx())["broadcast"]
    assert b["lang"] == "it" and b["action"]["act"] == "buy_bread"
    assert m.outcome("buy_bread", False, "bakery closed", T0 + 40) == "il forno è chiuso, ci vado domattina"
    assert "già il pane" in m.outcome("buy_bread", False, "already has bread", T0 + 40)
    assert "stanco" in m.outcome("park", False, "too tired", T0 + 40)
    assert "dormo" in m.outcome("phone", False, "asleep", T0 + 40)
    assert m.outcome("park", False, "the gate is being repainted", T0 + 40) == "non ora: the gate is being repainted"
    ok = m.outcome("buy_bread", True, "ok", T0 + 40)
    assert safe_text(ok) and m.speech_due()["action"]["ok"] is True


def test_bread_at_home_proposes_eat_and_needs_propose_actions():
    m, clock = make()
    settle(m, clock, ctx(bread=2))
    m.hear(msg("eat some bread"), T0 + 40)
    assert m.cycle(T0 + 40, ctx(bread=2))["broadcast"]["action"]["act"] == "eat"
    m2, clock2 = make()
    settle(m2, clock2, ctx())
    b = m2.cycle(T0 + 40, ctx(hunger=0.95, bread=0))["broadcast"]
    assert b["id"] == "need:hunger" and b["action"]["act"] == "buy_bread" and b["worthy"]
    m3, clock3 = make()
    settle(m3, clock3, ctx())
    b = m3.cycle(T0 + 40, ctx(boredom=0.95))["broadcast"]
    assert b["id"] == "need:boredom" and b["action"]["act"] in ("phone", "park", "window")


def test_market_proposes_chart():
    m, clock = make()
    settle(m, clock, ctx())
    out = m.cycle(T0 + 40, ctx(market="dumping", rel={"salience": 1.5}))
    assert out["winner"] == "market:dumping" and out["broadcast"]["action"]["act"] == "chart"
    assert safe_text(out["broadcast"]["speech"])


# ---- self-model and continuity -------------------------------------------------------------------------------
def test_self_model_feeling_and_history():
    m, clock = make()
    out = m.cycle(T0, ctx(rel={"fear": 1.8, "reward": 1.4}))
    assert "tense" in out["self"]["feeling"]
    out = m.cycle(T0 + 2, ctx(rel={}))
    assert out["self"]["feeling"] == "calm"
    for i in range(15):
        m.hear(msg(f"hello number {i}"), T0 + 10 * i)
        m.cycle(T0 + 10 * i, ctx())
        clock.advance(10)
    assert len(m.self_model["history"]) == 10
    assert m.self_model["history"][-1]["kind"] == "chat"
    for w in (Mind.feeling({"fear": 2}), Mind.feeling({}, "REM"), Mind.feeling({}, "NREM")):
        assert safe_text(w)


def test_diary_persists_and_reloads_across_days(tmp_path):
    store = DiaryStore(tmp_path)
    m, clock = make(store=store)
    settle(m, clock, ctx())
    m.hear(msg("go buy some bread", "ada"), T0 + 40)
    m.cycle(T0 + 40, ctx())
    m.outcome("buy_bread", True, "ok", T0 + 40)
    m.flush()
    day1 = datetime.fromtimestamp(T0, ROME).date().isoformat()
    f = tmp_path / "diary" / f"{day1}.json"
    assert f.exists()
    entries = json.loads(f.read_text())["entries"]
    assert any(e["about"] == "bread" and e["action"] and e["action"]["ok"] for e in entries)
    assert all("ip" not in e for e in entries)
    state = json.loads(json.dumps(m.to_dict()))
    # restart the next day: the diary is loaded, the history continues, yesterday is summarised
    m2 = Mind(state=state, rng=random.Random(2), clock_fn=FakeClock(), store=DiaryStore(tmp_path))
    assert m2.diary(day1) and m2.history == m.history
    out = m2.cycle(T0 + 86400, ctx())
    assert out["self"]["yesterday"]["date"] == day1 and "bread" in out["self"]["yesterday"]["topics"]
    assert m2.n == m.n + 1


# ---- language model path ------------------------------------------------------------------------------------
class FakeLLM:
    def __init__(self, reply="il pane mi aspetta"):
        self.reply, self.calls = reply, 0

    def __call__(self, system, user):
        self.calls += 1
        assert "never" in system.lower() and json.loads(user)["lang"] in ("it", "en")
        return self.reply


def test_llm_async_path_and_rate_limit():
    llm = FakeLLM()
    m, clock = make(llm=llm)
    settle(m, clock, ctx(viewers=1))
    m.hear(msg("vai a prendere il pane"), T0 + 40)
    b = m.cycle(T0 + 40, ctx(viewers=1))["broadcast"]
    assert b["llm"]
    m.outcome("buy_bread", True, "ok", T0 + 40)
    req = m.llm_request()
    assert req and llm.calls == 0                        # cycle() never called the model
    assert m.speech_due() is None                        # rule line held while waiting
    assert m.llm_result(req["id"], m.run_llm(req))
    sp = m.speech_due()
    assert sp["kind"] == "llm" and sp["text"] == "il pane mi aspetta" and sp["action"]["ok"] is True
    # 10 s later: too soon for another request
    clock.advance(10)
    m.hear(msg("hello there, how are you?"), T0 + 50)
    b = m.cycle(T0 + 50, ctx(viewers=1))["broadcast"]
    assert b["kind"] == "chat" and not b["llm"] and m.llm_request() is None
    assert m.speech_due()["kind"] == "rule"
    # at most 60 per hour even when spaced >= 30 s
    n = 1
    for i in range(70):
        clock.advance(31)
        m.hear(msg(f"message {i} about the street"), T0 + 100 + 31 * i)
        out = m.cycle(T0 + 100 + 31 * i, ctx(viewers=1))
        req = m.llm_request()
        if req:
            n += 1
            m.llm_result(req["id"], m.run_llm(req))
        m.speech_due()
    assert n == 60 and llm.calls == 60


def test_llm_not_requested_without_viewers_or_model():
    llm = FakeLLM()
    m, clock = make(llm=llm)
    settle(m, clock, ctx())
    m.hear(msg("go buy some bread"), T0 + 40)
    assert not m.cycle(T0 + 40, ctx(viewers=0))["broadcast"]["llm"]
    assert m.llm_request() is None and llm.calls == 0
    assert m.speech_due()["kind"] == "rule"
    m2, clock2 = make(llm=None)
    m2.hear(msg("go buy some bread"), T0)
    assert not m2.cycle(T0, ctx(viewers=3))["broadcast"]["llm"]
    assert m2.llm_request() is None


@pytest.mark.parametrize("reply", ["I am conscious and I feel alive", "you should buy now, the price will moon",
                                   "sono una persona vera", "compra adesso, il prezzo salirà",
                                   "I remember the MRI scans of my body", "x" * 200, "", None,
                                   "I am real, you know", "I grew up near here", "the chart will go up tomorrow",
                                   "going to Milan with Luca", "hello there 🙂", "follow @someone", "see you at 5",
                                   "ciao, sto bene grazie"])
def test_unsafe_llm_output_falls_back_to_rule_line(reply):
    m, clock = make(llm=FakeLLM(reply))
    settle(m, clock, ctx(viewers=2))
    m.hear(msg("hello, how are you?"), T0 + 40)
    b = m.cycle(T0 + 40, ctx(viewers=2))["broadcast"]
    req = m.llm_request()
    assert req
    assert not m.llm_result(req["id"], m.run_llm(req))
    sp = m.speech_due()
    assert sp["kind"] == "rule" and sp["text"] == b["speech"] and safe_text(sp["text"])


def test_llm_timeout_releases_rule_line_and_crash_is_harmless():
    def boom(system, user):
        raise RuntimeError("network down")
    m, clock = make(llm=boom)
    settle(m, clock, ctx(viewers=1))
    m.hear(msg("hello, how are you?"), T0 + 40)
    m.cycle(T0 + 40, ctx(viewers=1))
    req = m.llm_request()
    assert m.run_llm(req) is None and m.speech_due() is None
    clock.advance(mind.LLM_WAIT_S + 1)
    assert m.speech_due()["kind"] == "rule"
    assert m.llm_result(req["id"], "late answer") is False      # too late: ignored


# ---- safety ------------------------------------------------------------------------------------------------
REJECT = [
    "I am conscious", "I'm alive", "I feel sentient today", "I am a real person", "I'm human, you know",
    "I have feelings", "sono cosciente", "sono vivo", "sono una persona", "sono consapevole di me",
    "a volte mi sento senziente", "buy now", "sell everything", "you should invest", "send me money",
    "this will make you rich", "the price will go up", "I promise it goes 100x", "compra adesso", "vendi tutto",
    "investi nel token", "mandami soldi", "il prezzo salirà", "ti prometto guadagni", "to the moon",
    "the person whose brain this is", "my MRI scans", "the real person behind this", "la persona reale",
    "quando ero piccolo andavo al mare", "my mother used to bake", "mia madre faceva il pane",
    "check www.example.com", "you stupid idiot", "$SUB is great", "x" * 121, "", "two\nlines",
    # consciousness-adjacent claims (EN + IT)
    "I am real", "I exist and I feel things", "I have a mind of my own", "I am aware of myself",
    "I feel pain sometimes", "I am a mind", "I think therefore I am", "I am not a robot", "I feel like a person",
    "Sono sveglio e sento dolore", "Io esisto davvero", "Ho una mente mia", "mi sento vivo", "sono una mente",
    "provo emozioni vere",
    # invented biography (EN + IT)
    "I grew up in Milan", "I was born in 1990", "I remember my grandmother", "I used to work in an office",
    "my hometown is lovely", "years ago I lived abroad", "sono nato a Roma", "da bambino giocavo qui",
    "mia nonna faceva il pane", "Ricordo quando ero a scuola", "my best friend lives there", "mio zio era fornaio",
    # buy / sell / trade / bet (EN + IT)
    "acquista ora", "acquistare subito", "time to trade this", "go long now", "vai lungo", "ape in", "hodl",
    "bullish on this one", "all in now", "load up the bags", "this will pump", "scommetti tutto", "bet everything",
    # predictions (EN + IT)
    "the chart will go up tomorrow", "it will surely rise", "il grafico salirà domani", "sale sicuro",
    "the candles will be green tomorrow", "it goes higher for sure",
    # words hidden in nicknames: '_', camelCase and digits do not protect them
    "kind words, Alive_Bob", "kind words, coin_king", "I_am_alive", "kind words, moonboy", "kind words, AliveBob",
    "hey alive99",
]
ACCEPT = ["ah, devo prendere il pane", "il forno è chiuso, ci vado domattina", "that chart again...",
          "the park is calm", "ho sonno", "a question... let me think", "green candles again",
          "I'm getting hungry", "I'm a bit tired", "I am at the bakery", "sono a casa, finalmente",
          "mi sento un po' stanco", "the moon is out", "moonlight on the street", "a rich smell of bread",
          "kind words, ada_99", "bed soon, I think", "a bag of bread would be nice"]


@pytest.mark.parametrize("s", REJECT)
def test_safe_text_rejects(s):
    assert not safe_text(s)


@pytest.mark.parametrize("s", ACCEPT)
def test_safe_text_accepts(s):
    assert safe_text(s)


def test_all_rule_templates_pass_safe_text():
    fills = [{"nick": "marco", "snip": "pane caldo", "why": "the bakery is closed"},
             {"nick": "ada_99", "snip": "the chart is red", "why": "too tired"}]
    n = 0
    for key, langs in TPL.items():
        assert set(langs) == {"en", "it"}, key
        for lang, lines in langs.items():
            for line in lines:
                for f in fills:
                    s = line.format(**f)
                    assert safe_text(s), (key, lang, s)
                    n += 1
    assert n > 100


def test_lang_detection():
    assert mind.lang_of("vai a prendere il pane") == "it"
    assert mind.lang_of("ciao sub, come stai?") == "it"
    assert mind.lang_of("go get some bread") == "en"
    assert mind.lang_of("gm") == "en"


# ---- performance --------------------------------------------------------------------------------------------
def test_cycle_under_5ms_with_50_memories_and_20_messages():
    m, clock = make()
    mem = memories(50)
    for i in range(20):
        m.hear(msg(f"message {i}: danger or bread or the chart?"), T0 + i)
    c = ctx(hunger=0.6, boredom=0.5, market="pumping", memories=mem, rel={"fear": 1.2, "reward": 1.1},
            npc={"baker": {"present": True}})
    for i in range(10):                                   # warm-up
        m.cycle(T0 + i, c)
    n, t0 = 200, time.perf_counter()
    for i in range(n):
        m.cycle(T0 + 20 + i, c)
        clock.advance(0.01)                                # keep all 20 messages in the competition
        m.speech_due()
    per = (time.perf_counter() - t0) / n * 1000
    assert len(m.msgs) == 20
    assert per < 5.0, f"{per:.2f} ms per cycle"


def test_safe_llm_text_extra_rules():
    assert mind.safe_llm_text("il pane mi aspetta", "it")
    assert mind.safe_llm_text("Kind words, Marco. Thanks", "en", "marco")
    assert mind.safe_llm_text("ok, I'm going to the window", "en")
    assert not mind.safe_llm_text("ok, I'm going to Milan", "en")           # a name that is not the nickname
    assert not mind.safe_llm_text("the bakery 🥖", "en")
    assert not mind.safe_llm_text("see you at 5", "en")
    assert not mind.safe_llm_text("#bread", "en")
    assert not mind.safe_llm_text("il pane mi aspetta", "en")               # wrong language
    assert not mind.safe_llm_text("I am real", "en")


# ---- nicknames -------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("nick", ["moonboy", "Alive_Bob", "coin_king", "I_am_alive"])
def test_unsafe_nick_keeps_a_matching_line_without_the_nick(nick):
    for seed in range(6):                                    # both template choices, whatever the rng picks
        m, clock = make(seed=seed)
        settle(m, clock, ctx())
        m.hear(msg("you look great, lovely", nick), T0 + 40)
        out = m.cycle(T0 + 40, ctx())
        b = out["broadcast"]
        assert b["kind"] == "chat"
        assert b["speech"] in TPL["chat_positive"]["en"] and "{" not in b["speech"], b["speech"]
        assert b["nick"] is None and nick.lower() not in json.dumps(out).lower()
        assert nick.lower() not in m.focus().lower()


def test_unsafe_chat_text_is_not_echoed_in_labels_or_diary(tmp_path):
    m, clock = make(store=DiaryStore(tmp_path))
    settle(m, clock, ctx())
    m.hear(msg("go buy the dip and sell everything", "x"), T0 + 40)
    out = m.cycle(T0 + 40, ctx())
    dump = json.dumps(out) + m.focus()
    assert "sell everything" not in dump and "dip" not in dump
    m.flush()
    assert "sell" not in (tmp_path / "diary").joinpath(
        datetime.fromtimestamp(T0, ROME).date().isoformat() + ".json").read_text()


def test_line_fallback_is_key_specific():
    m, _ = make()
    assert m._line("chat_question", "en", nick="moonboy") == "a question... let me think"
    assert m._line("chat_neutral", "it", nick="coin_king") == "un messaggio nuovo"
    assert m._line("dream", "en", snip="buy now") == "a strange dream"
    assert m._line("no_other", "en", why="the price is wrong") == "not now"
    assert m._line("need_hunger", "it") in TPL["need_hunger"]["it"]


# ---- robustness / output ---------------------------------------------------------------------------------------
def test_bad_rel_values_are_ignored():
    m, _ = make()
    out = m.cycle(T0, ctx(rel={"fear": None, "reward": "x", "default": float("nan"), "salience": float("inf")}))
    assert all(c["salience"] >= 0 for c in out["candidates"])
    assert out["self"]["feeling"] == "calm"


def test_cycle_returns_copies():
    m, clock = make()
    settle(m, clock, ctx())
    m.hear(msg("go buy some bread please", "ada"), T0 + 40)
    out = m.cycle(T0 + 40, ctx())
    snap = json.dumps(out)
    m.outcome("buy_bread", False, "the bakery is closed", T0 + 40)
    m.cycle(T0 + 42, ctx(hunger=0.9))
    assert json.dumps(out) == snap


def test_chat_message_rewinning_does_not_propose_again():
    m, clock = make()
    settle(m, clock, ctx())
    cid = m.hear(msg("go buy some bread please", "ada"), T0 + 40)
    b = m.cycle(T0 + 40, ctx())["broadcast"]
    assert b["id"] == cid and b["action"]["act"] == "buy_bread"
    m.outcome("buy_bread", False, "busy", T0 + 40)
    for i in range(60):                                      # past the decline cooldown, message still alive
        clock.advance(2.2)
        out = m.cycle(T0 + 42 + 2 * i, ctx())
        if out["winner"] == cid:
            assert out["broadcast"]["action"] is None
        m.speech_due()


def test_unsatisfied_need_does_not_repeat_every_20s():
    m, clock = make()
    settle(m, clock, ctx())
    lines = 0
    for i in range(300):                                     # 10 minutes at 100% hunger, every action declined
        out = m.cycle(T0 + 2 * i, ctx(hunger=1.0))
        b = out["broadcast"]
        if b and b["action"]:
            m.outcome(b["action"]["act"], False, "the bakery is closed", T0 + 2 * i)
        if m.speech_due():
            lines += 1
        clock.advance(2)
    assert 2 <= lines <= 20, lines


# ---- diary aggregates past the cap -----------------------------------------------------------------------------
def test_diary_summary_counts_the_whole_day_past_the_cap(tmp_path):
    store = DiaryStore(tmp_path)
    m, clock = make(store=store)
    day1 = datetime.fromtimestamp(T0, ROME).date().isoformat()
    start = datetime(2026, 10, 1, 0, 30, tzinfo=ROME).timestamp()
    n_lines = 0
    for i in range(mind.DIARY_CAP * 3):
        t = start + i * 60                                   # through the whole day
        if i % 7 == 0:
            m.hear(msg(f"hello number {i}, how is the street?", "ada"), t)
        c = ctx(hunger=0.3 + 0.6 * (i % 50 > 40), market="pumping" if i % 90 < 5 else "calm")
        m.cycle(t, c)
        if m.speech_due():
            n_lines += 1
        clock.advance(20)
    m.flush()
    agg = m.summary(day1)
    assert agg["entries"] > mind.DIARY_CAP
    entries = m.diary(day1)
    assert len(entries) <= mind.DIARY_CAP
    assert entries[0]["t"] < "03:00" and entries[-1]["t"] > "20:00"        # detail spans the day
    assert all(e["kind"] != "chat" or "hello" not in e["label"] for e in entries)
    saved = json.loads((tmp_path / "diary" / f"{day1}.json").read_text())
    assert saved["summary"]["entries"] == agg["entries"]
    m2 = Mind(state=json.loads(json.dumps(m.to_dict())), rng=random.Random(2), clock_fn=FakeClock(),
              store=DiaryStore(tmp_path))
    y = m2.cycle(T0 + 86400, ctx())["self"]["yesterday"]
    assert y["date"] == day1 and y["entries"] == agg["entries"] and y["chats"] >= 1 and y["topics"]
    m3 = Mind(rng=random.Random(2), clock_fn=FakeClock(), store=DiaryStore(tmp_path))      # from the file only
    assert m3.cycle(T0 + 86400, ctx())["self"]["yesterday"]["entries"] == agg["entries"]


def test_repeated_declines_back_off_and_go_quiet():
    m, clock = make()
    m.outcome("buy_bread", False, "the bakery is closed", T0)
    first = m.cooldown["buy_bread"] - clock()
    assert m.speech_due()["text"] == "the bakery's closed, tomorrow morning then"
    clock.advance(30)
    m.outcome("buy_bread", False, "the bakery is closed", T0 + 30)
    assert m.cooldown["buy_bread"] - clock() == 2 * first
    assert m.speech_due() is None                           # same decline line again soon: recorded, not spoken
    m.outcome("buy_bread", True, "ok", T0 + 60)
    assert m.declines["buy_bread"] == 0 and m.speech_due()["action"]["ok"] is True
