"""Opt-in, read-only desk player. No private room APIs or account cookies are shared."""
import asyncio
import hashlib
import io
import html
import json
import math
import os
import time
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web

ENABLED = web.AppKey('x_embed_enabled', bool)
ROOT = Path(__file__).parent / 'web'
ASSETS = {
    'player.js': ROOT / 'embed/player.js',
    'card.png': ROOT / 'embed/card.png',
    'room.glb': ROOT / 'room/room_clean.glb',
    'character.glb': ROOT / 'room/char_v5.glb',
    'character.js': ROOT / 'room/char_v5.js',
    'idle.glb': ROOT / 'room/mh_v5/room_seated_idle.glb',
}
PUBLIC_PATHS = frozenset(['/share/sub01', '/embed/sub01', '/embed/state', '/embed/fomo-frame.jpg'] +
                         ['/embed/assets/' + name for name in ASSETS])


def public_request(request):
    return bool(request.app.get(ENABLED)) and request.method in ('GET', 'HEAD') and request.path in PUBLIC_PATHS


def public_origin(value):
    u = urlsplit(value)
    if (u.scheme != 'https' or not u.hostname or u.username or u.password or
            u.path not in ('', '/') or u.query or u.fragment or any(c.isspace() for c in value)):
        raise ValueError('SUB01_PUBLIC_URL must be an HTTPS origin, e.g. https://sub01.example')
    return value.rstrip('/')


def account_snapshot(path):
    """Trusted connector contract only. No connector or trade executor is started here."""
    out = {'mode': 'account', 'state': 'disconnected', 'updated_at': None, 'operations': []}
    try:
        with path.open('rb') as f:
            raw = f.read(262145)
        if len(raw) > 262144:
            return out
        d = json.loads(raw)
        updated = d.get('updated_at')
        if (d.get('version') != 1 or d.get('mode') != 'real' or d.get('provider') != 'fomo' or
                not isinstance(updated, (float, int)) or isinstance(updated, bool) or
                not math.isfinite(updated) or not 0 < updated <= time.time() + 30):
            return out
        rows = d.get('executions', [])
        if not isinstance(rows, list):
            return out
        alphabet = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
        seen = set()
        for r in rows[-8:]:
            if not isinstance(r, dict):
                continue
            tx, symbol, amount = r.get('tx'), r.get('asset'), r.get('amount')
            if (r.get('status') != 'confirmed' or r.get('side') not in ('buy', 'sell') or
                    not isinstance(tx, str) or not 80 <= len(tx) <= 90 or not set(tx) <= alphabet or tx in seen or
                    not isinstance(symbol, str) or not 1 <= len(symbol) <= 32 or not symbol.isascii() or
                    not all(c.isalnum() or c in '_-.' for c in symbol) or
                    not isinstance(amount, (float, int)) or isinstance(amount, bool) or
                    not math.isfinite(amount) or amount <= 0):
                continue
            seen.add(tx)
            out['operations'].append({'asset': symbol, 'action': r['side'], 'amount': amount, 'tx': tx})
        out.update(updated_at=updated, state='connected' if d.get('connected') is True and time.time()-updated <= 60 else 'disconnected')
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return out


def approved_frame(path, digest):
    """An exact reviewed frame only. Arbitrary/new browser screenshots never become public."""
    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        return None
    from PIL import Image
    try:
        with path.open('rb') as f:
            raw=f.read(4*1024*1024+1)
        if len(raw)>4*1024*1024 or hashlib.sha256(raw).hexdigest()!=digest:
            return None
        with Image.open(io.BytesIO(raw)) as image:
            if image.format!='JPEG' or image.width*image.height>2073600:
                return None
            image.verify()
        return raw
    except (OSError,ValueError):
        return None


def attach(app, live, data_dir):
    enabled = os.environ.get('SUB01_X_EMBED') == '1'
    app[ENABLED] = enabled
    if not enabled:
        return
    origin = public_origin(os.environ.get('SUB01_PUBLIC_URL', ''))
    cached, cached_at = None, -math.inf
    lock = asyncio.Lock()
    frame_path = Path(data_dir) / 'embed/fomo-reviewed-frame.jpg'
    frame_hash = os.environ.get('SUB01_FOMO_FRAME_SHA256', '')

    async def state(request):
        nonlocal cached, cached_at
        async with lock:
            now = time.monotonic()
            if cached is None or now - cached_at >= 2:
                account = await asyncio.to_thread(account_snapshot, Path(data_dir) / 'embed/fomo.json')
                frame = await asyncio.to_thread(approved_frame, frame_path, frame_hash)
                tick = getattr(live, 'last_tick', None)
                cached = {'version': 1, 'server_time': time.time(),
                          'simulation': 'demo' if getattr(live, 'demo', False) else 'running',
                          'connected': tick is not None and now - tick < 15,
                          'fomo': {'connected': account['state'] == 'connected'}, 'trading': account,
                          'monitor': {'available': frame is not None, 'revision': frame_hash if frame else None, 'mode': 'reviewed_still'}}
                cached_at = now
        return web.json_response(cached, headers={'Cache-Control': 'no-store',
                                                  'X-Content-Type-Options': 'nosniff'})

    async def player(request):
        return web.FileResponse(ROOT / 'embed/player.html', headers={
            'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline' 'wasm-unsafe-eval'; connect-src 'self' blob: https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; frame-src 'none'; object-src 'none'; base-uri 'none'",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'})

    async def share(request):
        o = html.escape(origin, quote=True)
        return web.Response(text=f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SUB-01 — The desk</title><meta name="twitter:card" content="player">
<meta name="twitter:title" content="SUB-01 — The desk">
<meta name="twitter:description" content="SUB-01 at the desk. Watch the account status.">
<meta name="twitter:image" content="{o}/embed/assets/card.png">
<meta name="twitter:player" content="{o}/embed/sub01">
<meta name="twitter:player:width" content="480"><meta name="twitter:player:height" content="480">
<meta property="og:url" content="{o}/share/sub01"><meta property="og:image" content="{o}/embed/assets/card.png">
</head><body style="margin:0;background:#111;color:white;font-family:system-ui">
<iframe title="SUB-01 desk player" src="/embed/sub01" style="border:0;width:100%;height:100dvh"></iframe>
</body></html>''', content_type='text/html', headers={'Cache-Control': 'no-cache'})

    async def asset(request):
        path = ASSETS.get(request.match_info['name'])
        if path is None:
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={'Cache-Control': 'no-cache',
                                               'X-Content-Type-Options': 'nosniff'})

    async def frame(request):
        raw = await asyncio.to_thread(approved_frame, frame_path, frame_hash)
        if raw is None:
            raise web.HTTPNotFound()
        return web.Response(body=raw, content_type='image/jpeg', headers={'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff'})

    app.router.add_get('/embed/fomo-frame.jpg', frame)
    app.router.add_get('/share/sub01', share)
    app.router.add_get('/embed/sub01', player)
    app.router.add_get('/embed/state', state)
    app.router.add_get('/embed/assets/{name}', asset)
