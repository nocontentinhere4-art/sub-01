"""State files under --data-dir that survive a kill mid-write.

save_json writes `<path>.tmp`, flushes and fsyncs it, then renames it onto `<path>` (os.replace is atomic on POSIX),
so a reader sees either the old file or the new one, never half of one. load_json never raises on a missing or
broken file: it logs one line, keeps the broken file aside as `<path>.corrupt-<UTC time>` for a look later, and
returns the default, so one torn file cannot crash-loop the server at startup.

Append-only logs (`*.jsonl`) are not replaced: append_jsonl starts a new line if a crash left the last one torn, and
read_jsonl skips lines that do not parse.
"""
import json
import os
import time
from pathlib import Path


def save_json(path, obj, **dumps_kw):
    """Atomically replace `path` with json.dumps(obj, **dumps_kw)."""
    path = Path(path)
    data = json.dumps(obj, **dumps_kw)                    # serialise first: a bad object leaves the old file alone
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def load_json(path, default=None, expect=dict):
    """The parsed file, or `default` when it is missing, unreadable, not JSON, or not an `expect` (None: any type)."""
    path = Path(path)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return default
    except OSError as e:
        print(f"state: cannot read {path} ({type(e).__name__}), starting from defaults", flush=True)
        return default
    try:
        obj = json.loads(raw.decode("utf-8"))
        if expect is not None and not isinstance(obj, expect):
            raise ValueError(f"not a {expect.__name__}")
        return obj
    except ValueError as e:                               # JSONDecodeError and UnicodeDecodeError are ValueErrors
        aside = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}")
        try:
            os.replace(path, aside)
            kept = f"kept as {aside.name}"
        except OSError:
            kept = "could not move it aside"
        print(f"state: {path} is corrupt ({type(e).__name__}, {len(raw)} bytes), {kept}; starting from defaults",
              flush=True)
        return default


def append_jsonl(path, *rows):
    """Append one JSON object per line; a torn last line (no trailing newline) is closed first, not glued to."""
    path = Path(path)
    with open(path, "ab+") as f:
        if f.tell() > 0:
            f.seek(-1, os.SEEK_END)
            torn = f.read(1) != b"\n"
        else:
            torn = False
        f.write((("\n" if torn else "") + "".join(json.dumps(r) + "\n" for r in rows)).encode("utf-8"))


def read_jsonl(path, last=None):
    """Rows of a JSONL file (the last `last` lines only when given), skipping lines that do not parse."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if last is not None:
        lines = lines[-last:]
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out
