"""Static checks for web/world/character.js (the stream's runtime checks are headless-browser screenshots)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "web" / "world" / "character.js").read_text()
MAN = json.loads((ROOT / "web" / "assets" / "manifest.json").read_text())


def test_exports_contract():
    assert re.search(r"export function createCharacter\(scene, assets\)", SRC)
    assert re.search(r"export function createBaker\(scene, assets, anchors\)", SRC)
    for member in ("setAnchors", "setPhoneTexture", "phoneMount", "phoneScreen"):
        assert member in SRC


def test_no_external_hosts_or_cdn():
    # only three.js (importmap) and same-origin assets; nothing is fetched from the network by URL
    code = "\n".join(l for l in SRC.splitlines() if not l.lstrip().startswith("//"))
    assert "http://" not in code and "https://" not in code
    assert "cdn." not in code and "unpkg" not in code and "jsdelivr" not in code


def test_no_forbidden_claims():
    # the figure is a rendering of a simulation: never described as alive / conscious / sentient / a person
    code = "\n".join(l for l in SRC.splitlines() if not l.lstrip().startswith("//"))
    for word in ("conscious", "sentient", "alive"):
        assert word not in code.lower()
    assert not re.search(r"\bface(s)?\b.*texture", code, re.I)           # no face features / face textures


def test_clip_slots_match_manifest():
    slots = set(MAN["character"]["clips"])
    rules = re.search(r"const NAME_RULES = \{(.*?)\n\};", SRC, re.S).group(1)
    names = set(re.findall(r"^\s{2}([a-z_]+):", rules, re.M))
    assert slots <= names, slots - names
    for clip in ("idle", "walk", "sit", "sit_desk", "lie", "lie_phone", "eat", "stand", "look_window"):
        assert f"{clip}:" in SRC and clip in SRC
    assert "serve" in SRC


def test_assets_credits_untouched_by_character_stream():
    # this stream adds no assets: everything is procedural or loaded from web/assets/character/ when it exists
    assert "web/assets/character/" in SRC
