"""HTTP contract checks for shared devices and protected edits."""

import asyncio
from types import SimpleNamespace
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from home_api import add_home_routes
from home_world import HomeWorld


class Computer:
    def __init__(self):
        self.inputs = []

    def view(self):
        return {"status": "ready", "output": "guest only"}

    async def input(self, text):
        self.inputs.append(text)
        return True


async def client():
    home = HomeWorld()
    computer = Computer()

    async def save():
        pass

    live = SimpleNamespace(
        home=home,
        computer=computer,
        life=SimpleNamespace(
            snapshot=lambda: {"activity": "research"}, apply_vote=lambda a, t: True
        ),
        engine=SimpleNamespace(stage="AWAKE"),
        clock=SimpleNamespace(now=lambda: 1234),
        client_ip=lambda r: r.remote,
        save_state=save,
    )
    app = web.Application()
    add_home_routes(app, live, lambda r: r.headers.get("X-Admin-Token") == "test")
    c = TestClient(TestServer(app))
    await c.start_server()
    return c, live


def test_shared_read_state_and_authenticated_edits():
    async def run():
        c, live = await client()
        try:
            r = await c.get("/api/home")
            d = await r.json()
            assert d["computer"]["output"] == "guest only"
            for path, data in [
                ("notes", {"text": "hello"}),
                ("computer", {"input": "uname -a"}),
                ("settings", {"lamp": False}),
                ("intent", {"activity": "play_console"}),
            ]:
                r = await c.post("/api/home/" + path, json=data)
                assert r.status == 403
                r = await c.post(
                    "/api/home/" + path, json=data, headers={"X-Admin-Token": "test"}
                )
                assert r.status == 200
            assert (
                live.computer.inputs == ["uname -a\n"]
                and live.home.notes[-1]["text"] == "hello"
                and live.home.settings["lamp"] is False
            )
            r = await c.get("/api/home")
            assert (await r.json())["home"]["notes"][-1]["text"] == "hello"
        finally:
            await c.close()

    asyncio.run(run())


def test_public_input_limits_and_disabled_house():
    async def run():
        c, live = await client()
        try:
            for i, d in enumerate([float("nan"), float("inf"), True, 2, "1"]):
                # Separate IP identities for independent malformed requests; same real remote is checked below.
                live.client_ip = lambda r, k=i: str(k)
                r = await c.post("/api/home/pong", json={"direction": d})
                assert r.status == 400
            live.client_ip = lambda r: "one-viewer"
            r = await c.post("/api/home/pong", json={"direction": -1})
            assert r.status == 200
            r = await c.post("/api/home/pong", json={"direction": 1})
            assert r.status == 429
            r = await c.post(
                "/api/home/notes",
                json={"text": "x" * 5000},
                headers={"X-Admin-Token": "test"},
            )
            assert r.status == 413
            live.home = None
            assert (await c.get("/api/home")).status == 404
            assert (await c.get("/house")).status == 404
        finally:
            await c.close()

    asyncio.run(run())
