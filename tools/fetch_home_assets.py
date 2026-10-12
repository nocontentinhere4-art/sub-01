"""Fetch pinned CC0 Poly Haven assets, with verified hashes and source manifest."""

import concurrent.futures, hashlib, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "web/house/assets"


def get(url):
    return subprocess.check_output(
        ["curl", "-LfsS", "--retry", "2", "--max-time", "90", url]
    )


def asset(name, model=False):
    meta = json.loads(get("https://api.polyhaven.com/files/" + name))
    base = ROOT / name
    base.mkdir(parents=True, exist_ok=True)
    files = {}
    if model:
        d = meta["gltf"]["1k"]["gltf"]
        files = {name + ".gltf": d, **d["include"]}
    else:
        for kind, key in [
            ("diff", "Diffuse"),
            ("normal", "nor_gl"),
            ("rough", "Rough"),
        ]:
            files[kind + ".jpg"] = meta[key]["1k"]["jpg"]
    result = []
    for filename, d in files.items():
        blob = get(d["url"])
        assert hashlib.md5(blob).hexdigest() == d["md5"]
        dest = base / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        result.append(
            {
                "file": str(dest.relative_to(ROOT)),
                "url": d["url"],
                "sha256": hashlib.sha256(blob).hexdigest(),
                "bytes": len(blob),
            }
        )
    return {
        "asset": name,
        "source": "https://polyhaven.com/a/" + name,
        "license": "CC0-1.0",
        "files": result,
    }


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as p:
        jobs = [
            p.submit(asset, x, True)
            for x in [
                "sofa_03",
                "modern_arm_chair_01",
                "potted_plant_01",
                "modern_coffee_table_01",
            ]
        ] + [
            p.submit(asset, x)
            for x in [
                "wooden_floor_02",
                "white_plaster_02",
                "quatrefoil_jacquard_fabric",
                "interior_tiles",
                "fine_grained_wood",
            ]
        ]
        records = [j.result() for j in jobs]
    (ROOT / "manifest.json").write_text(json.dumps(records, indent=2))
    print("Downloaded", sum(f["bytes"] for a in records for f in a["files"]), "bytes")
