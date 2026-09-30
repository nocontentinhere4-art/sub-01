"""Tiny RunPod REST client (key from the git-ignored .env / environment; never printed)."""
import json
import os
import urllib.request
from pathlib import Path


def _key():
    if os.environ.get("RUNPOD_API_KEY"):
        return os.environ["RUNPOD_API_KEY"].strip()
    env = Path(__file__).parent / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        if line.startswith("RUNPOD_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("RUNPOD_API_KEY missing")


def api(path, method="GET", body=None):
    req = urllib.request.Request("https://rest.runpod.io/v1" + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json",
                                          "User-Agent": "sub01/1.0 (+https://github.com/nocontentinhere4-art/sub-01)"})
    raw = urllib.request.urlopen(req, timeout=60).read()
    return json.loads(raw) if raw else None
