"""Tests for chat.py additions: the topic table (REGION_RULES) and nicknames."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

import chat


@pytest.mark.parametrize("text,topic,nets", [
    ("vado a comprare il pane", "food / bread", {"reward", "limbic"}),
    ("I love bread", "food / bread", {"reward"}),
    ("let's go to the park", "outside / park", {"limbic", "memory"}),
    ("andiamo fuori a passeggiare", "outside / park", {"limbic", "memory"}),
    ("the chart looks wild", "market / chart", {"salience", "attention"}),
    ("scrolling tiktok again", "phone / social", {"visual", "default"}),
    ("ciao a tutti", "greetings / people", {"default"}),
    ("I feel sad today", "feelings", {"limbic"}),
    ("perché piove?", "questions", {"attention", "control"}),
])
def test_topics_hit_their_networks(text, topic, nets):
    assert topic in [t for t, _ in chat.topics(text)]
    stim, hits, _ = chat.stimulus(text)
    assert nets <= set(hits) and nets <= set(stim)


def test_existing_rules_unchanged_for_plain_text():
    stim, hits, emo = chat.stimulus("the sky is grey")
    assert hits == ["language", "somatomotor"] and emo == "neutral"
    assert chat.topical_networks("the sky is grey") == ["language"]


def test_topical_networks_drop_the_universal_row():
    assert chat.topical_networks("comprare il pane") == ["reward", "limbic"]


def test_topic_drive_is_not_summed_with_the_content_rules():
    stim, _, _ = chat.stimulus("what is the chart doing?")      # question rule + topic row both give attention 6
    assert stim["attention"] == 6.0


@pytest.mark.parametrize("nick,ok", [
    ("", True), ("Bob", True), ("anna_b-2", True), ("zoë", True), ("a b c", True), ("x" * 20, True),
    ("x" * 21, False), ("bob.com", False), ("a@b", False), ("$WIF", False), ("idiot", False),
    ("SUB-01", False), ("\u0405UB-01", False), ("Sub-O1", False), ("SUB-Ol", False), ("\u0430nna", False),
    ("Subito", True), ("Sublime", True), ("admin", False), ("\u00c9milie", True), ("sub01 fan", False), ("12345678901", False), ("<b>", False),
])
def test_check_nick(nick, ok):
    assert chat.check_nick(nick)[0] is ok


def test_check_nick_reason_and_non_text():
    assert chat.check_nick("x" * 21)[1].startswith("nickname")
    assert chat.check_nick(5)[0] is False


def test_italian_threat_and_positive_words_reach_fear_and_reward():
    from chat import stimulus, topical_networks
    stim, nets, emo = stimulus("ho paura, c'è un pericolo")
    assert emo == "threat" and stim["fear"] > 0 and stim["salience"] > 0
    assert "fear" in topical_networks("ho paura del buio")
    stim, nets, emo = stimulus("grazie, sei gentile")
    assert emo == "positive" and stim["reward"] > 0
    assert stimulus("vai a comprare il pane")[2] == "neutral"       # a plain request stays neutral
