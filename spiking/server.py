"""aiohttp routes on the Railway server for the GPU pod: websocket ingress, learned-weights store, results, status.

The three pod routes bypass the site password gate and authenticate with `Authorization: Bearer <SUB01_POD_SECRET>`
(hmac.compare_digest); without that variable on the server they answer 403. Never imports torch or spiking.net.
"""
import asyncio
import hmac
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
from aiohttp import web

from spiking.costs import CostLog

SPIKING_KEY = web.AppKey("spiking", object)
POD_PATHS = ("/api/spiking/pod", "/api/spiking/weights", "/api/spiking/result")
KINDS = {"pong_curve": "pong_curves", "exam": "exams", "memory_test": "memory_tests", "bench": "bench"}
EXTRA_KINDS = {"encode": "encodes", "rates": "rates", "delays": "delays", "sleep": "sleeps"}   # stored, not on the page
MAX_WS_MSG = 1 << 20
MAX_WEIGHTS = 512 * 1024 ** 2
RELAY_MIN_S = 0.25                  # at most 4 state frames per second go to the page
GOOD_MIN_S = 30.0


class SpikingHub:
    def __init__(self, live, data_dir, secret=None, clock=time.monotonic):
        self.live = live
        self.dir = Path(data_dir) / "spiking"
        self.dir.mkdir(parents=True, exist_ok=True)
        self._secret = secret
        self.clock = clock
        self.ws = None
        self.session = None                 # {"session_id", "n_neurons", "device", "phases"} from the pod's hello
        self.last_state = None
        self.manager = None                 # PodManager (on_hello/on_state/on_done/on_disconnect) when enabled
        self.stage = None
        self._relayed = -1e9
        self._good = -1e9
        self._tasks = set()
        try:
            self.last = json.loads((self.dir / "last.json").read_text())
        except (OSError, ValueError):
            self.last = {}

    # --- auth ---------------------------------------------------------------------
    @property
    def secret(self):
        return self._secret if self._secret is not None else os.environ.get("SUB01_POD_SECRET", "")

    def check(self, request):
        """403 when the server has no secret, 401 on a missing or wrong bearer token."""
        if not self.secret:
            raise web.HTTPForbidden()
        sent = request.headers.get("Authorization", "")
        if not hmac.compare_digest(sent.encode(), ("Bearer " + self.secret).encode()):
            raise web.HTTPUnauthorized()

    # --- results ------------------------------------------------------------------
    def store_result(self, msg):
        kind = msg.get("kind")
        files = KINDS | EXTRA_KINDS
        if kind not in files:
            return False
        rec = {k: v for k, v in msg.items() if k != "type"} | {"received": datetime.now(timezone.utc).isoformat()}
        with open(self.dir / f"{files[kind]}.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        self.last[kind] = rec
        tmp = self.dir / "last.json.tmp"
        tmp.write_text(json.dumps(self.last))
        os.replace(tmp, self.dir / "last.json")
        return True

    # --- forwards to the pod (sync entry points: they schedule the send) --------------
    @property
    def connected(self):
        return self.ws is not None and not self.ws.closed

    def _spawn(self, coro):
        t = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)
        return t

    async def _send(self, msg):
        ws = self.ws
        if ws is not None and not ws.closed:
            try:
                await ws.send_json(msg)
                return True
            except Exception:
                pass
        return False

    def forward(self, msg):
        if not self.connected:
            return False
        self._spawn(self._send(msg))
        return True

    def forward_chat(self, text, emotion="neutral"):
        return self.forward({"type": "chat", "text": text, "emotion": emotion})

    def forward_good(self):
        if not self.connected or self.clock() - self._good < GOOD_MIN_S:
            return False
        self._good = self.clock()
        return self.forward({"type": "good"})

    def forward_sleep(self, stage):
        """Forward the sleep engine stage when it changes (called every tick, cheap when unchanged)."""
        if stage == self.stage:
            return False
        self.stage = stage
        return self.forward({"type": "sleep", "stage": stage})

    async def forward_stop(self):
        return await self._send({"type": "stop"})

    # --- websocket from the pod ----------------------------------------------------
    async def pod_ws(self, request):
        self.check(request)
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_WS_MSG)
        await ws.prepare(request)
        old, self.ws = self.ws, ws
        if old is not None and not old.closed:
            await old.close()
        self.session = None
        if self.stage:
            await ws.send_json({"type": "sleep", "stage": self.stage})
        try:
            async for m in ws:
                if m.type == aiohttp.WSMsgType.TEXT:
                    await self.on_frame(m.data)
        finally:
            if self.ws is ws:
                self.ws, self.session, self.last_state = None, None, None
                if self.manager:
                    self.manager.on_disconnect()
                await self.live.broadcast({"type": "spiking", "live": False})
        return ws

    async def on_frame(self, data):
        try:
            d = json.loads(data)
        except ValueError:
            return
        if not isinstance(d, dict):
            return
        kind = d.get("type")
        if kind == "hello":
            self.session = {k: d.get(k) for k in ("session", "n_neurons", "device", "phases")}
            if self.manager:
                self.manager.on_hello(d)
        elif kind == "state":
            self.last_state = d
            if self.manager:
                self.manager.on_state(d)
            now = self.clock()
            if now - self._relayed >= RELAY_MIN_S:
                self._relayed = now
                await self.live.broadcast({k: v for k, v in d.items() if k != "type"} | {"type": "spiking"})
        elif kind == "result":
            self.store_result(d)
        elif kind == "done":
            if self.manager:
                self.manager.on_done(d)
            await self.live.broadcast({"type": "spiking", "live": False, "done": True, "ok": bool(d.get("ok"))})

    # --- weights ------------------------------------------------------------------
    async def weights_get(self, request):
        self.check(request)
        path = self.dir / "weights.npz"
        if not path.exists():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def weights_post(self, request):
        """Stream the body to a temp file (request.content is not subject to client_max_size), then swap atomically."""
        self.check(request)
        tmp = self.dir / "weights.upload.tmp"
        size, head = 0, b""
        try:
            with open(tmp, "wb") as f:
                async for chunk in request.content.iter_chunked(1 << 20):
                    size += len(chunk)
                    if size > MAX_WEIGHTS:
                        raise web.HTTPRequestEntityTooLarge(max_size=MAX_WEIGHTS, actual_size=size)
                    head = head or chunk[:2]
                    f.write(chunk)
            if size == 0 or head != b"PK":                      # an npz is a zip archive
                raise web.HTTPBadRequest(text="expected an npz body")
            cur = self.dir / "weights.npz"
            if cur.exists():
                os.replace(cur, self.dir / "weights.prev.npz")
            os.replace(tmp, cur)
        finally:
            tmp.unlink(missing_ok=True)
        return web.json_response({"ok": True, "bytes": size})

    async def result_post(self, request):
        self.check(request)
        try:
            d = await request.json()
        except ValueError:
            raise web.HTTPBadRequest(text="bad json")
        if not isinstance(d, dict) or not self.store_result(d):
            raise web.HTTPBadRequest(text="unknown result kind")
        return web.json_response({"ok": True})

    # --- page ---------------------------------------------------------------------
    def status(self):
        mgr = self.manager.status() if self.manager else {}
        live = bool(mgr.get("live")) if mgr else self.connected and self.session is not None
        session = mgr.get("session") if mgr else None
        if session is None and self.session:
            session = {"session_id": self.session.get("session"), "device": self.session.get("device"),
                       "n_neurons": self.session.get("n_neurons")}
        return {"live": live, "session": session, "next_session": mgr.get("next_session") if mgr else None,
                "last": {k: self.last.get(k) for k in KINDS},
                "spend": mgr.get("spend") or CostLog(self.dir / "costs.jsonl").summary()}

    async def status_get(self, request):
        return web.json_response(self.status())


def attach(app, live, data_dir, secret=None):
    """Register the routes; the hub is also stored under `SPIKING_KEY` and `live.spiking`."""
    hub = SpikingHub(live, data_dir, secret)
    app[SPIKING_KEY] = hub
    live.spiking = hub
    app.router.add_get("/api/spiking/pod", hub.pod_ws)
    app.router.add_get("/api/spiking/weights", hub.weights_get)
    app.router.add_post("/api/spiking/weights", hub.weights_post)
    app.router.add_post("/api/spiking/result", hub.result_post)
    app.router.add_get("/api/spiking/status", hub.status_get)
    return hub
