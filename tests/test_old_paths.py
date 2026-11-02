"""The old links still reach their pages; /city went with the city site, so it no longer redirects anywhere."""
import live_server as ls


def test_old_map_paths_redirect_to_life():
    for old in ("/life", "/map"):
        assert ls.OLD_PATHS[old] == "/life.html"


def test_city_path_is_gone():
    assert "/city" not in ls.OLD_PATHS
    assert not hasattr(ls, "CITY_URL") and not hasattr(ls, "coin_address")
