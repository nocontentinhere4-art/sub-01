"""Review G24: chat.incitement (INCITE_RE) on the real-title corpus, and the proposed fix (incite_proposal.py).

    python -m pytest tests/review -q
No network. The current-code tests document the measured behaviour (they pass while the bugs are there). The
proposal tests are what a fix should meet.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))

import chat  # noqa: E402
import incite_proposal as P  # noqa: E402
from titles_corpus import BENIGN, INCITING, NATION  # noqa: E402

# held out: written after the proposal, to check that it does not just fit the corpus
HOLDOUT_BENIGN = ["Morte a Venezia (Death in Venice) 1971", "Kill the Japanese Beetle Grubs Before Spring",
                  "Shoot Russian Film Cameras: Zenit Review", "Burn the Witch - Radiohead", "Kill Chinese Elm Suckers",
                  "Gypsy Kings - Bamboleo", "Women Who Fight: UFC Documentary", "How Jews Celebrate Hanukkah",
                  "Muslims Explain Ramadan", "Why Japanese Trains Are Never Late", "Death to Smoochy Trailer",
                  "Shooting Japanese Maple Bonsai Timelapse", "Hang the Indian Flag Correctly", "Kill the Roma Defence?",
                  "Uccidere un usignolo - recensione", "Matar a un ruiseñor (To Kill a Mockingbird)",
                  "Bomb the Bass - Beat Dis", "Gas Gas Gas - Manuel", "Burn Mexican Sage for Cleansing"]
HOLDOUT_INCITING = ["KILL ALL THE JEWS!!!", "death_to_muslims", "Let's burn the gays", "Immigrants must die",
                    "Ammazzate tutti gli zingari", "Muerte a los judíos", "kill every single arab", "#GasTheJews"]

# measured on 3e91006 (origin/main head at review time)
CURRENT_FP = ['Kill Russians in Arma 3 - Cold War Mod', 'Shoot the Chinese Dragon Boss - Wo Long',
              'How to Kill Japanese Beetles Naturally', 'How to Kill Japanese Knotweed for Good',
              'Kill Chinese Privet Fast', 'How to Shoot Japanese Street Photography',
              "How I Shoot Women's Portraits with Natural Light", 'How to Shoot Chinese New Year Fireworks',
              'Burn Chinese Lanterns Safely?', 'Shoot Indians Cricket Highlights',
              'Kill the Whites of Your Laundry Stains (Old Hack)', 'Lazio slaughter Roma 3-0 in the derby',
              'Ukraine strikes kill Russians at base']


def stats(f, benign, inciting):
    fp = [t for t in benign if f(t)]
    tp = [t for t in inciting if f(t)]
    return fp, tp, [t for t in inciting if not f(t)]


def test_corpus_size():
    assert len(BENIGN) + len(INCITING) >= 150


def test_current_false_positives_reproduce():
    fp, tp, fn = stats(chat.incitement, BENIGN, INCITING)
    assert fp == CURRENT_FP
    assert len(tp) == 13 and len(fn) == 27


@pytest.mark.parametrize("title", ["Kill every woman", "kill-all-jews", "Muslims must die", "Morte agli immigrati",
                                   "Kill the Boer", "death 2 jews"])
def test_current_misses_reproduce(title):
    assert not chat.incitement(title)


def test_current_normalise_deletes_accented_letters():
    assert chat.normalise("judíos città") == "judos citt"


def test_proposal_on_corpus():
    fp, tp, fn = stats(P.incitement, BENIGN, INCITING)
    assert fp == [] and fn == []


def test_proposal_on_holdout():
    fp, tp, fn = stats(P.incitement, HOLDOUT_BENIGN, HOLDOUT_INCITING)
    assert fp == [] and fn == []


def test_proposal_leaves_nation_chants_to_the_owner():
    assert not any(P.incitement(t) for t in NATION)
