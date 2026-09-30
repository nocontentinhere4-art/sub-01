"""web/assets/manifest.json must describe exactly the files on disk, and every asset file must be
credited (CC0 / permissive) in web/assets/CREDITS.md."""
import json
import re
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "web" / "assets"
MAN = json.loads((ASSETS / "manifest.json").read_text())
CREDITS = (ASSETS / "CREDITS.md").read_text()
ROLES = {"bed", "table", "chair", "desk", "laptop", "lamp", "shelf", "sofa", "stove", "street_lamp", "bench", "tree",
         "bush", "planter", "bread", "basket", "display", "cart", "hydrant", "trash", "rock", "clock", "ceiling_lamp",
         "cabinet", "pillows"}
AREAS = {"apartment", "street", "bakery", "park"}
CLIPS = {"idle", "walk", "sit", "sit_desk", "lie", "lie_phone", "eat", "look_window", "serve"}


def _disk(url):
    assert url.startswith("/assets/"), url
    return ASSETS / url[len("/assets/"):]


def test_manifest_shape():
    assert set(MAN["hdri"]) == {"day", "dusk", "night", "interior", "city"}
    for k in ("hdri", "textures", "models", "character", "totalBytes"):
        assert k in MAN
    assert set(MAN["character"]["clips"]) == CLIPS
    for s, t in MAN["textures"].items():
        assert {"map", "normalMap", "roughnessMap", "repeatPerMetre"} <= set(t), s
        assert t["repeatPerMetre"] > 0
    for k, m in MAN["models"].items():
        assert {"url", "scale", "rotationY", "yOffset", "size", "tris", "area", "role"} <= set(m), k
        assert m["area"] in AREAS and m["role"] in ROLES, k
        assert len(m["size"]) == 3 and all(v > 0 for v in m["size"]), k


def test_every_referenced_file_exists():
    urls = list(MAN["hdri"].values())
    for t in MAN["textures"].values():
        urls += [t["map"], t["normalMap"], t["roughnessMap"]]
    urls += [m["url"] for m in MAN["models"].values()]
    if MAN["character"]["url"]:
        urls.append(MAN["character"]["url"])
    for u in urls:
        assert _disk(u).is_file(), u


def test_every_asset_file_is_in_manifest_and_credited():
    referenced = set(MAN["hdri"].values()) | {m["url"] for m in MAN["models"].values()}
    for t in MAN["textures"].values():
        referenced |= {t["map"], t["normalMap"], t["roughnessMap"]}
    credited = {m.lower() for m in re.findall(r"polyhaven\.com/a/([A-Za-z0-9_]+)", CREDITS.replace("~~", ""))}
    assert "CC0" in CREDITS
    for f in sorted(ASSETS.rglob("*")):
        if not f.is_file() or f.name in ("CREDITS.md", "manifest.json") or "character" in f.relative_to(ASSETS).parts:
            continue
        rel = "/assets/" + f.relative_to(ASSETS).as_posix()
        assert rel in referenced, f"not in manifest: {rel}"
        slug = f.parent.name if f.parent.parent.name == "textures" else re.sub(r"_1k$", "", f.stem)
        assert slug.lower() in credited, f"not in CREDITS.md: {rel}"


def test_total_bytes_matches_disk():
    # totalBytes covers hdri + textures + models; the character library is reported separately
    total = sum(f.stat().st_size for f in ASSETS.rglob("*")
                if f.is_file() and f.name not in ("CREDITS.md", "manifest.json")
                and "character" not in f.relative_to(ASSETS).parts)
    assert MAN["totalBytes"] == total
