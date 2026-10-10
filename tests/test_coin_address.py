"""The coin's contract address on the pages (owner, 2026-10-11): SUB01_CA or MINT, only a valid Solana address, and
/city reaches his map."""
import live_server as ls

SOL = "So11111111111111111111111111111111111111112"          # a 32-byte base58 address


def test_ca_from_env_or_mint(monkeypatch):
    monkeypatch.delenv("SUB01_CA", raising=False)
    assert ls.coin_address("") == ""                            # nothing set: nothing shown
    assert ls.coin_address(SOL) == SOL                          # MINT
    monkeypatch.setenv("SUB01_CA", " " + SOL + " ")
    assert ls.coin_address("") == SOL                           # SUB01_CA, trimmed
    assert ls.coin_address("other") == SOL                      # SUB01_CA wins over MINT


def test_ca_only_a_solana_address(monkeypatch):
    monkeypatch.delenv("SUB01_CA", raising=False)
    for bad in ("abc", "0x52908400098527886E0F7030069857D2E4169EE7", SOL + "x", "O0Il" * 10):
        assert ls.coin_address(bad) == ""


def test_city_paths():
    for old in ("/city", "/life", "/map"):
        assert ls.OLD_PATHS[old] == "/life.html"
