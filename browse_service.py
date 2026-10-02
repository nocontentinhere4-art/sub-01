"""The screens' browser in its own process: Chromium can crash or bloat without taking the brain down.

    python browse_service.py --host 127.0.0.1 --port 8790        # started by live_server (BROWSE=1), or
    python browse_service.py --host :: --port $PORT              # as its own Railway service (same repo and image)

HTTP API (every call needs the header X-Browse-Token = BROWSE_SERVICE_TOKEN when that is set):
  POST /init  {state}                   restore the browsing log (the brain's process keeps it on /data)
  POST /step  {device, heard, interest, mode} scroll / open the next page; or {"decide": page} when the brain should
                                        choose. mode "video": he is watching videos (YouTube, muted, #17)
  POST /act   {device, action, why, interest}  carry out the brain's choice
  POST /close {device|null}             put a screen away (or everything)
  GET  /shot/{device}.jpg               latest screenshot        GET /health
  GET  /state   log + screen status, every text typed (site search boxes only), every banner pressed away, and
                the searches per source today / requests per host this hour (`search_counts`, #56)
The service never sees the server's secrets: it runs with a minimal environment (see LocalBrowser.spawn). The one
exception is the logged-in sessions of SUB-01's own TikTok / YouTube accounts (#60, sessions.py), which only the
browser's logged-in contexts use; Chromium's own environment never carries them.

In the brain's process, BrowserClient talks to it with short timeouts; if it does not answer it raises BrowserDown,
the screen shows "browser restarting" and LocalBrowser (when the service is a child process) starts a new one. A
watchdog restarts the child when its process tree uses more than BROWSE_MEM_MB (default 1200) of memory.
"""
import argparse
import asyncio
import json
import os
import secrets
import signal
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import web

HERE = Path(__file__).parent
TOKEN_HEADER = "X-Browse-Token"
MEM_MB = float(os.environ.get("BROWSE_MEM_MB") or 1200)
STEP_LIMIT_S, ACT_LIMIT_S = 70.0, 110.0                         # a hung page (endless script) is abandoned
HUNG_AFTER = 3                                                  # consecutive failed calls: restart the child
ENV_KEEP = ("PATH", "HOME", "LANG", "TZ", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH", "FONTCONFIG_PATH", "PYTHONPATH",
            "BROWSE_PROXY", "BROWSE_IGNORE_TLS", "BROWSE_CHROMIUM", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
            # #60: the logged-in sessions reach this process only; browse.py adds them to their site's own browser
            # context and Chromium's environment never carries them (browse.CHROMIUM_ENV)
            "SUB01_SESSION_TIKTOK", "SUB01_SESSION_YOUTUBE")


class BrowserDown(Exception):
    pass


# --- the service (runs in its own process) -------------------------------------------------------------------------
def make_app(browser, token=None):
    token = token if token is not None else os.environ.get("BROWSE_SERVICE_TOKEN", "")

    @web.middleware
    async def auth(request, handler):
        if token and request.headers.get(TOKEN_HEADER, "") != token:
            raise web.HTTPUnauthorized()
        return await handler(request)

    app = web.Application(middlewares=[auth], client_max_size=1024 ** 2)

    async def body(request):
        try:
            d = await request.json()
        except ValueError:
            raise web.HTTPBadRequest()
        if not isinstance(d, dict):
            raise web.HTTPBadRequest()
        return d

    def device(d):
        dev = d.get("device")
        if dev not in browser.screens:
            raise web.HTTPBadRequest(text="device")
        return dev

    async def init(request):
        """Restore the saved log, only into a fresh service (never over a running one's newer log)."""
        d = await body(request)
        st = d.get("state") or {}
        fresh = not browser.log and not browser.used
        if fresh:
            browser.log = list(st.get("log", []))[-60:]
            browser.used = set(st.get("used", []))
            if st.get("searches") and hasattr(browser, "limits"):   # rate limits and counts survive a restart
                from search_sources import Limits
                browser.limits = Limits(state=st["searches"])
        return web.json_response({"ok": True, "applied": fresh})

    async def limited(coro, limit, dev):
        try:
            return await asyncio.wait_for(coro, limit)
        except asyncio.TimeoutError:                            # e.g. a page whose script never returns
            print(f"browse service: {dev} took over {limit:.0f}s, closing it", flush=True)
            await browser.close(dev)
            return None

    async def step(request):
        d = await body(request)
        dev = device(d)
        mode = "video" if d.get("mode") == "video" else None
        out = await limited(browser.step(dev, list(d.get("heard") or [])[-5:], d.get("interest"), mode), STEP_LIMIT_S,
                            dev)
        if out and "decide" in out:
            return web.json_response({"decide": out["decide"]})
        return web.json_response({"status": out})

    async def act(request):
        d = await body(request)
        dev = device(d)
        st = await limited(browser.act(dev, d.get("action") or {}, str(d.get("why") or "")[:200], d.get("interest")),
                           ACT_LIMIT_S, dev)
        return web.json_response({"status": st})

    async def close(request):
        d = await body(request)
        await browser.close(d.get("device") if d.get("device") in browser.screens else None)
        return web.json_response({"ok": True})

    async def shot(request):
        sc = browser.screens.get(request.match_info["device"])
        if not sc or not sc.shot:
            raise web.HTTPNotFound()
        return web.Response(body=sc.shot, content_type="image/jpeg", headers={"X-Shot-Id": str(sc.shot_id)})

    async def state(request):
        return web.json_response({**browser.to_dict(), "screens": {k: s.status() for k, s in browser.screens.items()},
                                  "open": browser.browser is not None,
                                  "sandbox": getattr(browser, "sandbox", None), "uid": os.getuid(),
                                  "typed": getattr(browser, "typed", [])[-30:],
                                  "dismissed": getattr(browser, "dismissed", [])[-30:],
                                  "search_counts": browser.limits.public() if hasattr(browser, "limits") else None,
                                  "accounts": browser.accounts() if hasattr(browser, "accounts") else None})

    async def health(request):
        return web.json_response({"ok": True, "pid": os.getpid(), "rss_mb": round(tree_rss_mb(os.getpid()), 1)})

    for path, fn in (("/init", init), ("/step", step), ("/act", act), ("/close", close)):
        app.router.add_post(path, fn)
    app.router.add_get("/shot/{device}.jpg", shot)
    app.router.add_get("/state", state)
    app.router.add_get("/health", health)

    async def shutdown(app):
        await browser.close()
    app.on_cleanup.append(shutdown)
    return app


def descendants(pid):
    """pid and all its descendants (Linux /proc)."""
    children = {}
    for p in Path("/proc").glob("[0-9]*"):
        try:
            ppid = int((p / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        children.setdefault(ppid, []).append(int(p.name))
    out, todo = [], [pid]
    while todo:
        q = todo.pop()
        out.append(q)
        todo += children.get(q, [])
    return out


def mem_mb(pid):
    """Proportional memory (PSS: shared pages split between processes) of one process, else its RSS; 0 if gone."""
    try:
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                return int(line.split()[1]) / 1024
    except (OSError, ValueError, IndexError):
        pass
    try:
        return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2 ** 20
    except (OSError, ValueError, IndexError, AttributeError):
        return 0.0


def tree_rss_mb(pid):
    """Memory of a process and all its descendants (Chromium's renderers included), counted as PSS."""
    return sum(mem_mb(p) for p in descendants(pid))


# --- the client (in the brain's process) ---------------------------------------------------------------------------
class BrowserClient:
    """Async HTTP client for the service. Any failure -> BrowserDown; the caller shows 'browser restarting'."""

    def __init__(self, url, token="", timeout=40.0):
        self.url, self.token, self.timeout = url.rstrip("/"), token, timeout
        self.http = None
        self.screens = {}                                       # last status per device (for the tick message)
        self.log = []
        self.searches = None                                    # searches per source today (/api/browsing, #56)
        self.accounts = None                                    # logged in / out per site (/api/browsing, #60)
        self.shots = {}                                         # device -> (shot id, jpeg bytes)
        self.restarting = False
        self.failures = 0                                       # consecutive failed calls (hung service)

    def reset(self):
        """A new service process: nothing cached from the old one is valid (shot ids start again at 1)."""
        self.restarting, self.failures = True, 0
        self.screens.clear()
        self.shots.clear()

    async def _session(self):
        if self.http is None or self.http.closed:
            self.http = aiohttp.ClientSession(headers={TOKEN_HEADER: self.token} if self.token else {})
        return self.http

    async def _post(self, path, payload, timeout=None):
        try:
            http = await self._session()
            async with http.post(self.url + path, json=payload,
                                 timeout=aiohttp.ClientTimeout(total=timeout or self.timeout)) as r:
                if r.status != 200:
                    raise BrowserDown(f"{path}: HTTP {r.status}")
                out = await r.json()
            self.failures = 0
            return out
        except BrowserDown:
            self.failures += 1
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError) as e:
            self.failures += 1
            raise BrowserDown(f"{path}: {type(e).__name__}") from None

    async def _get(self, path, timeout=10.0):
        try:
            http = await self._session()
            async with http.get(self.url + path, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return r.status, await r.read(), r.headers
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            raise BrowserDown(f"{path}: {type(e).__name__}") from None

    async def init(self, state):
        await self._post("/init", {"state": state}, timeout=10)

    async def step(self, device, heard=(), interest=None, mode=None):
        d = await self._post("/step", {"device": device, "heard": list(heard), "interest": interest, "mode": mode},
                             timeout=STEP_LIMIT_S + 20)
        self.restarting = False
        if d.get("status"):
            self.screens[device] = d["status"]
        return d

    async def act(self, device, action, why="", interest=None):
        d = await self._post("/act", {"device": device, "action": action, "why": why, "interest": interest},
                             timeout=ACT_LIMIT_S + 20)
        if d.get("status"):
            self.screens[device] = d["status"]
        return d.get("status")

    async def close(self, device=None):
        self.screens.pop(device, None) if device else self.screens.clear()
        await self._post("/close", {"device": device}, timeout=15)

    async def state(self):
        status, raw, _ = await self._get("/state")
        if status != 200:
            raise BrowserDown(f"/state: HTTP {status}")
        d = json.loads(raw)
        self.log = d.get("log", [])
        self.searches = d.get("search_counts")
        self.accounts = d.get("accounts")
        for dev, st in (d.get("screens") or {}).items():
            if st:
                self.screens[dev] = st
        return d

    async def shot(self, device):
        """Latest JPEG of a screen (cached by shot id; refetched when the screen shows a new one)."""
        want = (self.screens.get(device) or {}).get("id")
        have = self.shots.get(device)
        if have and have[0] == want:
            return have[1]
        status, raw, headers = await self._get(f"/shot/{device}.jpg")
        if status != 200:
            return have[1] if have else None
        self.shots[device] = (int(headers.get("X-Shot-Id", want or 0)), raw)
        return raw

    async def health(self):
        status, raw, _ = await self._get("/health", timeout=5.0)
        return status == 200

    async def aclose(self):
        if self.http is not None:
            await self.http.close()


class LocalBrowser:
    """Runs the service as a child process on 127.0.0.1 with a minimal environment and restarts it when it dies, stops
    answering or uses more than BROWSE_MEM_MB."""

    def __init__(self, port=None, mem_mb=MEM_MB, python=sys.executable):
        self.fixed_port = port or int(os.environ.get("BROWSE_SERVICE_PORT") or 0)    # 0: a free port per start
        self.port = self.fixed_port
        self.mem_mb, self.python = mem_mb, python
        self.token = secrets.token_hex(16)
        self.proc = None
        self.restarts = 0
        self.client = BrowserClient(f"http://127.0.0.1:{self.port}", self.token)

    async def spawn(self):
        if not self.fixed_port:
            import socket
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                self.port = s.getsockname()[1]
            self.client.url = f"http://127.0.0.1:{self.port}"
        env = {k: v for k, v in os.environ.items() if k in ENV_KEEP}
        env["BROWSE_SERVICE_TOKEN"] = self.token
        env["BROWSE_PARENT_PID"] = str(os.getpid())             # it exits by itself if the brain's process dies
        self.proc = await asyncio.create_subprocess_exec(
            self.python, str(HERE / "browse_service.py"), "--host", "127.0.0.1", "--port", str(self.port),
            env=env, cwd=str(HERE), start_new_session=True)
        for _ in range(60):                                     # up to ~15 s to come up
            await asyncio.sleep(0.25)
            if self.proc.returncode is not None:
                break
            try:
                if await self.client.health():
                    return True
            except BrowserDown:
                pass
        return False

    def alive(self):
        return self.proc is not None and self.proc.returncode is None

    async def kill(self):
        if self.proc is not None and self.proc.returncode is None:
            tree = descendants(self.proc.pid)                   # Chromium may run in its own process group
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            for pid in tree:
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            await self.proc.wait()

    async def ensure(self):
        """-> "ok" (running), "started" / "restarted" (a new process: re-send the saved state) or "down"."""
        why = None
        if self.alive() and tree_rss_mb(self.proc.pid) > self.mem_mb:
            why = f"over {self.mem_mb:.0f} MB"
        elif self.alive() and self.client.failures >= HUNG_AFTER:
            why = f"{self.client.failures} calls failed (hung?)"
        elif self.alive():
            return "ok"
        restarting = self.proc is not None
        if why:
            print(f"browse service {why}: restarting", flush=True)
        await self.kill()
        if restarting:
            self.restarts += 1
            self.client.reset()                                 # the screen says "browser restarting" meanwhile
        ok = await self.spawn()
        print("browse service " + ("restarted" if restarting and ok else "started" if ok else "did not start"),
              flush=True)
        return ("restarted" if restarting else "started") if ok else "down"

    async def aclose(self):
        await self.client.aclose()
        await self.kill()


async def serve(host, port):
    from browse import Browser
    if host not in ("127.0.0.1", "localhost", "::1") and not os.environ.get("BROWSE_SERVICE_TOKEN"):
        raise SystemExit("browse service: set BROWSE_SERVICE_TOKEN before listening beyond localhost")
    browser = Browser(decide=True)
    runner = web.AppRunner(make_app(browser))
    await runner.setup()
    await web.TCPSite(runner, host, port).start()
    print(f"browse service on {host}:{port} (pid {os.getpid()})", flush=True)
    stop = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass
    parent = int(os.environ.get("BROWSE_PARENT_PID") or 0)

    async def orphan_watch():                                   # started by live_server: never outlive it
        while parent and not stop.is_set():
            await asyncio.sleep(2)
            if os.getppid() != parent:
                print("browse service: parent process gone, exiting", flush=True)
                stop.set()
    watch = asyncio.create_task(orphan_watch())
    await stop.wait()
    watch.cancel()
    await runner.cleanup()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8790)))
    a = p.parse_args()
    asyncio.run(serve(a.host, a.port))
