"""Smoke test of the live server in --demo mode (CI job `smoke`; run locally with `python tests/smoke_demo.py`).

Starts `live_server.py --demo` with BROWSE=0 in a temporary data dir, waits for /api/config, checks HTTP 200 on the
pages and read APIs, checks that /ws sends a `tick` within 10 s, then prints the server's CPU cost per tick, read
from /proc/<pid>/stat over 20 s of /ws (Linux only; skipped with a note elsewhere).
With --torn-state the data dir first gets state files cut off mid-write (a kill during a save, issue #21): the server
must still start, log one "is corrupt" line per file and keep each one aside as <name>.corrupt-<UTC time>.
No `test_` prefix, so pytest does not collect it.
"""
import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
PATHS = ["/", "/brain", "/diary", "/api/diary", "/api/reading", "/api/frames", "/api/browsing"]
TICK_S = 0.05            # live_server.TICK: one broadcast per 50 ms
TORN = {                 # state files read back at startup, each cut off mid-write
    "life.json": '{"activity": "research", "path": [], "hunger',
    "body.json": '{"body": {"ghrelin": 0.4, "glucose',
    "reading.json": '{"log": [{"title": "Bread", "url": "https://en.wikipedia.org/wiki/Br',
    "state.json": '{"engine": {"t": 1790000000.0, "stage": "AWAKE", "pressure": 0.3',
}


def seed_torn(data_dir):
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    for name, text in TORN.items():
        (d / name).write_text(text)


def check_torn(data_dir, log_text):
    failures = []
    for name in TORN:
        kept = list(Path(data_dir).glob(name + ".corrupt-*"))
        lines = [ln for ln in log_text.splitlines() if f"{name} is corrupt" in ln]
        ok = len(kept) == 1 and len(lines) == 1
        print(f"{'ok  ' if ok else 'FAIL'} torn {name:<13} {len(lines)} log line, kept aside: {kept[0].name if kept else '-'}")
        if not ok:
            failures.append(f"torn {name}: {len(lines)} log lines, {len(kept)} files kept aside")
    return failures


def cpu_seconds(pid):
    """utime + stime of a process, in seconds (fields 14 and 15 of /proc/<pid>/stat)."""
    stat = Path(f"/proc/{pid}/stat").read_text()
    fields = stat[stat.rindex(")") + 2:].split()      # skip "pid (comm) ", comm may contain spaces
    return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")


async def wait_ready(session, base, proc, timeout):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited with code {proc.returncode} before /api/config answered")
        try:                                        # a slow answer while starting up is retried like a refusal
            async with session.get(base + "/api/config", timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    return time.monotonic() - t0
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError(f"/api/config did not answer within {timeout:g} s")


async def run(args, proc):
    base = f"http://127.0.0.1:{args.port}"
    failures = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
        ready = await wait_ready(s, base, proc, args.startup_timeout)
        print(f"ready: /api/config answered after {ready:.1f} s")
        for path in PATHS:
            async with s.get(base + path) as r:
                body = await r.read()
                ok = r.status == 200
                print(f"{'ok  ' if ok else 'FAIL'} GET {path:<14} {r.status}  {len(body)} bytes")
                if not ok:
                    failures.append(f"GET {path} -> {r.status}")

        async with s.ws_connect(base + "/ws") as ws:
            t0 = time.monotonic()
            first = None
            while time.monotonic() - t0 < 10:
                try:
                    msg = await ws.receive_json(timeout=max(0.1, 10 - (time.monotonic() - t0)))
                except asyncio.TimeoutError:
                    break
                if msg.get("type") == "tick":
                    first = time.monotonic() - t0
                    break
            if first is None:
                print("FAIL /ws sent no tick within 10 s")
                failures.append("/ws: no tick within 10 s")
                return failures
            print(f"ok   /ws first tick after {first:.2f} s")

            # tick cost: server CPU seconds over a window of /ws, divided by the ticks received in it
            linux = Path(f"/proc/{proc.pid}/stat").exists()
            cpu0 = cpu_seconds(proc.pid) if linux else None
            t0, ticks = time.monotonic(), 0
            while time.monotonic() - t0 < args.measure:
                try:
                    msg = await ws.receive_json(timeout=max(0.1, args.measure - (time.monotonic() - t0)))
                except asyncio.TimeoutError:
                    break
                ticks += msg.get("type") == "tick"
            wall = time.monotonic() - t0
            if not ticks:
                failures.append("/ws: no ticks during the measurement window")
                return failures
            print(f"ticks: {ticks} in {wall:.1f} s ({ticks / wall:.1f}/s, nominal {1 / TICK_S:.0f}/s)")
            if linux:
                cpu = cpu_seconds(proc.pid) - cpu0
                print(f"TICK COST: {1000 * cpu / ticks:.1f} ms CPU per {1000 * TICK_S:.0f} ms tick "
                      f"({100 * cpu / wall:.0f}% of one core, {cpu:.2f} CPU-s over {wall:.1f} s)")
            else:
                print("TICK COST: not measured (/proc not available on this OS)")
    return failures


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--data-dir", help="server state dir (default: a fresh temporary dir)")
    p.add_argument("--measure", type=float, default=20.0, help="seconds of /ws used for the tick cost")
    p.add_argument("--startup-timeout", type=float, default=90.0)
    p.add_argument("--torn-state", action="store_true", help="start with truncated state files (issue #21)")
    args = p.parse_args()

    tmp = None
    if not args.data_dir:
        tmp = tempfile.TemporaryDirectory(prefix="sub01-smoke-")
        args.data_dir = tmp.name
    if args.torn_state:
        seed_torn(args.data_dir)
    env = dict(os.environ, BROWSE="0", PYTHONUNBUFFERED="1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    env.setdefault("OMP_NUM_THREADS", "1")
    env.pop("SITE_PASSWORD", None)                  # the gate would answer 401; it has its own tests
    log = tempfile.TemporaryFile(mode="w+")
    cmd = [sys.executable, str(ROOT / "live_server.py"), "--demo", "--port", str(args.port),
           "--data-dir", args.data_dir]
    print("$ BROWSE=0 python live_server.py", " ".join(cmd[2:]))
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        failures = asyncio.run(run(args, proc))
        if args.torn_state:
            log.seek(0)
            failures += check_torn(args.data_dir, log.read())
    except Exception as e:                          # startup failure, connection refused, ...
        failures = [f"{type(e).__name__}: {e}"]
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    if failures:
        log.seek(0)
        print("\n--- server log (last 60 lines) ---")
        print("".join(log.readlines()[-60:]))
        print("SMOKE FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print("SMOKE OK")
    if tmp:
        tmp.cleanup()


if __name__ == "__main__":
    main()
