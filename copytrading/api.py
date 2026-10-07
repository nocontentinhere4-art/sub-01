"""Read-only status; inherits the site's gate. No execution/import HTTP endpoint."""
from pathlib import Path
import asyncio
from state_io import load_json


def attach(app, data_dir):
    from aiohttp import web
    path = Path(data_dir) / "copytrading" / "paper.json"

    async def get(request):
        snapshot = await asyncio.to_thread(load_json, path)
        if snapshot is None:
            return web.json_response({"mode": "paper", "state": "off"})
        report = dict(snapshot["report"])
        # Full history stays on disk; keep the web response bounded.
        for key in ("decisions", "closed", "learning"):
            if key in report:
                report[key + "_total"] = len(report[key])
                report[key] = report[key][-100:]
        return web.json_response(dict(report, state="snapshot", feed_hash=snapshot["feed_hash"],
                                      note="Read-only replay snapshot, not a running exchange account."))

    app.router.add_get("/api/copytrading", get)
