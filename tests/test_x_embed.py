"""Public desk must never open the gated application or expose account data."""
import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import x_embed
from live_server import password_gate


def test_public_surface_keeps_private_gate(monkeypatch, tmp_path):
    monkeypatch.setenv('SUB01_X_EMBED', '1')
    monkeypatch.setenv('SUB01_PUBLIC_URL', 'https://sub01.example')
    async def check():
        app = web.Application(middlewares=[password_gate('private')])
        x_embed.attach(app, SimpleNamespace(last_tick=time.monotonic(), demo=False), tmp_path)
        async def private(request):
            return web.Response(text='secret')
        for path in ('/', '/api/copytrading', '/api/screens', '/ws', '/room/char_v5.glb'):
            app.router.add_get(path, private)
        async with TestClient(TestServer(app)) as client:
            for path in ('/share/sub01', '/embed/sub01', '/embed/state', '/embed/assets/player.js', '/embed/assets/room.glb', '/embed/assets/card.png'):
                res = await client.get(path, allow_redirects=False)
                assert res.status == 200, path
                await res.read()
            body = await (await client.get('/share/sub01')).text()
            assert 'https://sub01.example/embed/sub01' in body
            assert 'twitter:card' in body
            state = await (await client.get('/embed/state')).json()
            assert state['trading']['state'] == 'disconnected'
            assert state['fomo'] == {'connected': False}
            for path in ('/api/copytrading', '/api/screens', '/ws'):
                assert (await client.get(path, allow_redirects=False)).status == 401
            for path in ('/', '/room/char_v5.glb', '/embed/assets/life.json', '/embed/assets/../private'):
                assert (await client.get(path, allow_redirects=False)).status != 200
            assert (await client.post('/embed/state', json={'trade': 'buy'}, allow_redirects=False)).status != 200
            assert (await client.head('/embed/sub01')).status == 200
    asyncio.run(check())


def test_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv('SUB01_X_EMBED', raising=False)
    app = web.Application()
    x_embed.attach(app, SimpleNamespace(), tmp_path)
    assert not app[x_embed.ENABLED]
    assert not list(app.router.routes())


@pytest.mark.parametrize('url', ['http://example.com', 'https://u:p@example.com', 'https://example.com/a', 'https://example.com?q=x', 'https://example.com/#x', 'https://example.com/\n', ''])
def test_bad_origin(url):
    with pytest.raises(ValueError):
        x_embed.public_origin(url)


def test_real_snapshot_requires_correct_source_and_redacts_secrets(tmp_path):
    p = tmp_path/'fomo.json'
    assert x_embed.account_snapshot(p)['state'] == 'disconnected'
    data = {'version':1,'provider':'fomo','mode':'real','connected':True,'updated_at':time.time(),
            'cookie':'DO_NOT_SHARE','wallet':'PRIVATE', 'executions':[
                {'side':'buy','asset':'SOL','amount':1,'status':'confirmed','tx':'2'*88,'cookie':'SECRET'},
                {'side':'sell','asset':'BAD','amount':1,'status':'pending','tx':'3'*88}]}
    p.write_text(json.dumps(data))
    result=x_embed.account_snapshot(p)
    assert result['state']=='connected' and len(result['operations'])==1
    assert 'SECRET' not in json.dumps(result) and 'PRIVATE' not in json.dumps(result) and 'DO_NOT_SHARE' not in json.dumps(result)
    data['mode']='paper';p.write_text(json.dumps(data))
    assert x_embed.account_snapshot(p)['operations']==[]
    data['mode']='real';data['updated_at']-=120;p.write_text(json.dumps(data))
    assert x_embed.account_snapshot(p)['state']=='disconnected'
    p.write_text('{bad')
    assert x_embed.account_snapshot(p)['operations']==[]


def test_only_exact_reviewed_frame_is_publishable(tmp_path):
    import hashlib,io
    from PIL import Image
    path=tmp_path/'frame.jpg'
    out=io.BytesIO();Image.new('RGB',(640,360)).save(out,format='JPEG');raw=out.getvalue();path.write_bytes(raw)
    approved=hashlib.sha256(raw).hexdigest()
    assert x_embed.approved_frame(path,approved)==raw
    assert x_embed.approved_frame(path,'') is None
    path.write_bytes(raw+b'changed')
    assert x_embed.approved_frame(path,approved) is None
    path.write_bytes(b'cookies')
    assert x_embed.approved_frame(path,hashlib.sha256(b'cookies').hexdigest()) is None
