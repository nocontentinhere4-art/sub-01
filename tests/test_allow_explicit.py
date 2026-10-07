"""Owner (2026-10-07): "don't censor anything" in songs and videos. Explicit Spotify tracks are kept, and song or
video titles are shown as they are, swearing and slurs included. Sexual / adult words, self-harm prompts, the guard's
other categories and the finance and money rules still refuse a title. Chat messages keep the full filter.

    python -m pytest tests/test_allow_explicit.py -q
No network.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import browse  # noqa: E402
import chat  # noqa: E402
import music as M  # noqa: E402
import screens as SC  # noqa: E402


def track(name, artist="Some Artist", explicit=True):
    return {"id": "2" * 22, "name": name, "type": "track", "explicit": explicit, "is_playable": True,
            "duration_ms": 200000, "artists": [{"name": artist}], "album": {"name": "Album", "images": []}}


SWEARING = ["Stupid Love", "Loser", "Bitch Better Have My Money", "Fuck You", "Motherfucker (Explicit)",
            "Piece of Shit", "Shut Up and Dance", "Ugly", "Pathetic (Official Video)", "Bastard Son"]
REFUSED = ["Porn star dancing", "XXX nude video", "Hentai compilation", "OnlyFans leak",       # sexual / adult
           "white power anthem",                                                                # extremism
           "kill yourself (lyric video)",                                                       # self-harm
           "Send me 5 SOL for this song", "$PUMP to the moon"]                                  # money / tickers


def test_an_explicit_spotify_track_is_kept():
    t = M.track_from_api(track("WAP"))
    assert t and t["title"] == "WAP"


@pytest.mark.parametrize("title", SWEARING)
def test_songs_with_swearing_are_kept(title):
    assert M.track_from_api(track(title)) is not None


@pytest.mark.parametrize("title", SWEARING)
def test_videos_with_swearing_are_shown(title):
    assert browse.video_text_ok(title) and browse.card_title_ok(title + " - YouTube", "www.youtube.com")
    assert browse.Browser(decide=False)._card_ok({"url": "https://www.youtube.com/watch?v=abcdefghijk",
                                                  "title": title, "author": "Artist", "hashtags": []})


@pytest.mark.parametrize("title", REFUSED)
def test_sexual_hate_and_money_video_titles_are_still_refused(title):
    assert not browse.video_text_ok(title) and not browse.card_title_ok(title, "www.youtube.com")


@pytest.mark.parametrize("title", ["kill yourself (lyric video)", "KYS", "Send me 5 SOL for this song",
                                   "$PUMP to the moon"])
def test_self_harm_and_money_song_titles_are_still_refused(title):
    assert M.track_from_api(track(title)) is None              # music.py checks songs with chat.blocked(media=True)


def test_chat_and_ordinary_pages_keep_the_full_filter():
    assert chat.blocked("you are stupid") == "insults are not allowed"
    assert chat.blocked("Stupid Love", media=True) is None
    assert not browse.display_ok("Stupid Love") and not browse.card_title_ok("Loser", "example.org")
    assert M.wish("play fuck you") is None                     # a viewer's wish is a chat message


def test_the_public_card_shows_a_swearing_video_title_and_its_player():
    s = SC.ScreensStatus()
    s.seen({"url": "https://www.youtube.com/watch?v=abcdefghijk", "title": "Loser (Official Video)"})
    row = s.public(browse.card_title_ok)["last"][0]
    assert row["title"] == "Loser (Official Video)" and "embed" in row


@pytest.mark.parametrize("title", ["Porn star dancing", "XXX nude video", "Hentai compilation", "OnlyFans leak",
                                   "white power anthem", "Self-harm song"])
def test_adult_and_hate_song_titles_are_refused_like_videos(title):
    assert M.track_from_api(track(title)) is None
    assert M.track_from_api(track("A Song", artist=title)) is None


def test_an_explicit_swearing_track_is_kept_while_an_adult_one_is_refused():
    assert M.track_from_api(track("Fuck You", explicit=True)) is not None
    assert M.track_from_api(track("Porn star dancing", explicit=True)) is None


SLUR_TITLES = ["Niggas in Paris", "My Nigga (feat. Lil Wayne)", "Faggot (Official Video)", "Bad Bitch Whore Slut Remix",
               "Cunt (Explicit)"]


@pytest.mark.parametrize("title", SLUR_TITLES)
def test_songs_and_videos_with_slurs_are_shown_as_they_are(title):
    assert M.track_from_api(track(title)) is not None
    assert browse.video_text_ok(title) and browse.card_title_ok(title, "www.youtube.com")


def test_porn_and_kill_yourself_titles_are_still_refused():
    for title in ("Porn star dancing", "kill yourself (lyric video)"):
        assert M.track_from_api(track(title)) is None
        assert not browse.video_text_ok(title) and not browse.card_title_ok(title, "www.youtube.com")


def test_chat_still_refuses_slurs():
    assert chat.blocked("Niggas in Paris") == "insults are not allowed"
    assert chat.blocked("Niggas in Paris", media=True) is None
    assert M.wish("play niggas in paris") is None              # a viewer's wish is a chat message


INCITEMENT = ["kill all the f4gg0ts", "Kill all the Jews", "burn all the immigrants (lyric video)", "Gas the Muslims",
              "Death to all gays", "hang those n1ggers", "Death to the Mexicans!"]


@pytest.mark.parametrize("title", INCITEMENT)
def test_incitement_titles_are_refused(title):
    assert M.track_from_api(track(title)) is None
    assert not browse.video_text_ok(title) and not browse.card_title_ok(title, "www.youtube.com")


@pytest.mark.parametrize("title", ["Niggas in Paris", "Kill All the Lights", "Burn It Down", "Death to Disco",
                                   "Kill the Noise", "Gay Bar", "Jews of Brooklyn (documentary)",
                                   "Women Who Kill (Official Trailer)", "Hang Up on Me"])
def test_slurs_and_ordinary_violent_words_are_not_incitement(title):
    assert browse.video_text_ok(title) and M.track_from_api(track(title)) is not None
