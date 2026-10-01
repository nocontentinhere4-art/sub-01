"""CPU use of the live server at real time (target: <= 30 % of one core, docs/twin_contracts.md).

    OMP_NUM_THREADS=1 python twin/measure_cpu_live.py [--seconds 60] [--out twin/data/cpu_live.json]

Starts `live_server.py --demo` (default flags of the Dockerfile CMD except --eye: the real-baseline replay is on, no
image generation) on a free local port with a temporary data dir, lets it warm up, and samples
  * the server process's CPU time (user + system, from /proc/<pid>/stat) over `--seconds` of wall time, and
  * the model step alone (thread CPU time spent inside brain.step, from the server's local /api/perf),
in two phases: nobody watching, and one browser-like websocket client receiving every tick message.
Writes the numbers to twin/data/cpu_live.json. Percent of one core = CPU seconds / wall seconds * 100.
A digital twin model of one real person's brain structure and recorded activity; not a mind, not conscious, not the person.
"""
import argparse
import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
CLK = os.sysconf("SC_CLK_TCK")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def proc_cpu_s(pid):
    """utime + stime of a process in seconds."""
    f = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / CLK


async def get_json(http, url):
    async with http.get(url) as r:
        return await r.json()


async def sample(pid, base, seconds, with_client):
    async with aiohttp.ClientSession() as http:
        ws = task = None
        n_msg = [0, 0]

        async def reader():
            async for m in ws:
                n_msg[0] += 1
                n_msg[1] += len(m.data) if isinstance(m.data, (str, bytes)) else 0
        if with_client:
            ws = await http.ws_connect(base + "/ws".replace("http", "ws"), max_msg_size=0) if False else \
                await http.ws_connect(base.replace("http", "ws") + "/ws", max_msg_size=0)
            task = asyncio.create_task(reader())
        await asyncio.sleep(5)                                    # settle after (dis)connecting
        p0, t0, c0 = await get_json(http, base + "/api/perf"), time.monotonic(), proc_cpu_s(pid)
        m0 = list(n_msg)
        await asyncio.sleep(seconds)
        p1, t1, c1 = await get_json(http, base + "/api/perf"), time.monotonic(), proc_cpu_s(pid)
        if task:
            task.cancel()
            await ws.close()
        wall = t1 - t0
        out = {"client_connected": with_client, "wall_s": round(wall, 1),
               "server_cpu_pct_of_one_core": round(100 * (c1 - c0) / wall, 1),
               "model_step_cpu_pct_of_one_core": round(100 * (p1["model_s"] - p0["model_s"]) / wall, 1),
               "tick_logic_cpu_pct_of_one_core": round(100 * (p1["tick_s"] - p0["tick_s"]) / wall, 1),
               "ticks": p1["ticks"] - p0["ticks"], "ticks_per_s": round((p1["ticks"] - p0["ticks"]) / wall, 2)}
        if with_client:
            out["ws_messages"], out["ws_kb_per_s"] = n_msg[0] - m0[0], round((n_msg[1] - m0[1]) / 1024 / wall, 1)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--model", default="twin")
    ap.add_argument("--out", default=str(ROOT / "twin" / "data" / "cpu_live.json"))
    a = ap.parse_args()
    port = free_port()
    env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUNBUFFERED="1")
    env.pop("SITE_PASSWORD", None)
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen([sys.executable, "live_server.py", "--demo", "--port", str(port), "--data-dir", tmp,
                                 "--model", a.model], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(120):
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                    break
                except OSError:
                    time.sleep(0.5)
            time.sleep(10)                                         # warm-up
            phases = [asyncio.run(sample(proc.pid, base, a.seconds, wc)) for wc in (False, True)]
        finally:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()
    res = {"what": "CPU use of live_server.py --demo at real time (time-scale 1, no eye), twin model, one viewer or none",
           "model": a.model, "target_pct_of_one_core": 30.0, "phases": phases,
           "worst_server_cpu_pct": max(p["server_cpu_pct_of_one_core"] for p in phases),
           "meets_target": max(p["server_cpu_pct_of_one_core"] for p in phases) <= 30.0,
           "how": "server CPU = utime+stime of the process from /proc/<pid>/stat over the sampled wall time; model step = "
                  "time.thread_time() spent in brain.step inside Live.tick (/api/perf); OMP_NUM_THREADS=1",
           "machine": {"python": platform.python_version(), "cpus_visible": os.cpu_count(),
                       "platform": platform.platform(), "note": "shared sandbox (other jobs run on the same CPUs); "
                       "a dedicated Railway vCPU may differ"},
           "measured_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
