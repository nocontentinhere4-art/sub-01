"""Home APIs: shared devices, bounded public Pong input, authenticated editing."""

import json
import math
import time
from collections import OrderedDict
from pathlib import Path
from aiohttp import web
from life import ACTIVITIES

HERE = Path(__file__).parent


def add_home_routes(app, live, admin_ok):
    inputs = OrderedDict()

    def enabled():
        if not live.home:
            raise web.HTTPNotFound(text="Home is not enabled")

    def operator(request):
        if not admin_ok(request):
            raise web.HTTPForbidden(text="Operator authentication required")

    async def body(request):
        if request.content_length is not None and request.content_length > 4096:
            raise web.HTTPRequestEntityTooLarge(
                max_size=4096, actual_size=request.content_length
            )
        chunks = []
        size = 0
        async for chunk in request.content.iter_chunked(4096):
            size += len(chunk)
            if size > 4096:
                raise web.HTTPRequestEntityTooLarge(max_size=4096, actual_size=size)
            chunks.append(chunk)
        try:
            b = json.loads(b"".join(chunks))
        except (ValueError, UnicodeDecodeError):
            raise web.HTTPBadRequest(text="Invalid JSON")
        if not isinstance(b, dict):
            raise web.HTTPBadRequest(text="Expected object")
        return b

    async def state(request):
        enabled()
        return web.json_response(
            {
                "home": live.home.view(),
                "computer": live.computer.view(),
                "life": live.life.snapshot(),
                "stage": live.engine.stage,
                "time": live.clock.now(),
            },
            headers={"Cache-Control": "no-store"},
        )

    async def computer(request):
        enabled()
        return web.json_response(
            live.computer.view(), headers={"Cache-Control": "no-store"}
        )

    async def command(request):
        enabled()
        operator(request)
        b = await body(request)
        text = b.get("input")
        if not isinstance(text, str) or len(text) > 2000:
            raise web.HTTPBadRequest(text="Input too long")
        return web.json_response({"ok": await live.computer.input(text + "\n")})

    async def note(request):
        enabled()
        operator(request)
        b = await body(request)
        if not isinstance(b.get("text"), str):
            raise web.HTTPBadRequest(text="Text required")
        ok = live.home.add_note(b["text"])
        await live.save_state()
        return web.json_response({"ok": ok})

    async def pong(request):
        enabled()
        key = live.client_ip(request)
        now = time.monotonic()
        if now - inputs.get(key, 0) < 0.08:
            raise web.HTTPTooManyRequests()
        inputs[key] = now
        inputs.move_to_end(key)
        if len(inputs) > 1024:
            inputs.popitem(last=False)
        b = await body(request)
        direction = b.get("direction")
        if (
            isinstance(direction, bool)
            or not isinstance(direction, (float, int))
            or not math.isfinite(direction)
            or abs(direction) > 1
        ):
            raise web.HTTPBadRequest(text="Direction must be -1 to 1")
        live.home.pong.input(direction)
        return web.json_response({"ok": True})

    async def intent(request):
        enabled()
        operator(request)
        b = await body(request)
        act = b.get("activity")
        if act not in ACTIVITIES or act == "sleep":
            raise web.HTTPBadRequest(text="Unknown activity")
        live.life.apply_vote(act, live.clock.now())
        return web.json_response(
            {
                "ok": True,
                "activity": act,
                "meaning": "A nudge, not a forced action; needs and sleep still decide",
            }
        )

    async def settings(request):
        enabled()
        operator(request)
        b = await body(request)
        for k in ("lamp", "curtain"):
            if k in b:
                if not isinstance(b[k], bool):
                    raise web.HTTPBadRequest(text="Expected boolean")
        for k in ("lamp", "curtain"):
            if k in b:
                live.home.settings[k] = b[k]
        await live.save_state()
        return web.json_response(live.home.settings)

    async def house(request):
        enabled()
        return web.FileResponse(
            HERE / "web/house/index.html", headers={"Cache-Control": "no-cache"}
        )

    app.router.add_get("/house", house)
    app.router.add_get("/api/home", state)
    app.router.add_get("/api/home/computer", computer)
    app.router.add_post("/api/home/computer", command)
    app.router.add_post("/api/home/notes", note)
    app.router.add_post("/api/home/pong", pong)
    app.router.add_post("/api/home/settings", settings)
    app.router.add_post("/api/home/intent", intent)
