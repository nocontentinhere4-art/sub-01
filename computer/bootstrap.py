"""Fetch pinned guest ROM/kernel assets from official upstream; never mount host files in the VM."""

import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GUEST = [
    a
    for a in json.loads((ROOT / "manifest.json").read_text())
    if a["file"].endswith(".bin")
]


def valid(file, asset):
    return (
        file.is_file()
        and file.stat().st_size == asset["bytes"]
        and hashlib.sha256(file.read_bytes()).hexdigest() == asset["sha256"]
    )


def ensure(destination, prefer_bundled=True):
    destination = Path(destination)
    if prefer_bundled and all(valid(ROOT / a["file"], a) for a in GUEST):
        return ROOT
    destination.mkdir(parents=True, exist_ok=True)
    for a in GUEST:
        file = destination / a["file"]
        if valid(file, a):
            continue
        request = urllib.request.Request(
            a["source"], headers={"User-Agent": "SUB01-Home/1.0"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(a["bytes"] + 1)
        if len(data) != a["bytes"] or hashlib.sha256(data).hexdigest() != a["sha256"]:
            raise RuntimeError(
                "Upstream guest asset differs from pinned version: " + a["file"]
            )
        temporary = file.with_suffix(".download")
        temporary.write_bytes(data)
        temporary.replace(file)
    return destination


if __name__ == "__main__":
    ensure(sys.argv[1] if len(sys.argv) > 1 else ROOT)
    print("Pinned Linux guest and BIOS assets verified")
