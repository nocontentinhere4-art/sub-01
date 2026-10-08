import asyncio
import hashlib
import io
import json
import time
from pathlib import Path
import pytest
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image
from browser_bridge.server import application, validated_frame
from x_embed import live_frame

URL='https://fomo.family/tokens/solana/'+'2'*44

def jpeg():
    out=io.BytesIO();Image.new('RGB',(640,360)).save(out,format='JPEG');return out.getvalue()

@pytest.mark.parametrize('url',['https://evil.example/tokens/solana/'+'2'*44,'https://fomo.family/settings','https://fomo.family/login',URL+'?secret=test'])
def test_only_token_page_allowed(url):
    with pytest.raises(ValueError):validated_frame(jpeg(),url)

def test_live_ingest_authentication_expiry_and_tampering(tmp_path):
    async def run():
        async with TestClient(TestServer(application('test-key',tmp_path))) as client:
            raw=jpeg()
            assert (await client.post('/frame',data=raw,headers={'X-Fomo-Page':URL})).status==401
            headers={'Authorization':'Bearer test-key','X-Fomo-Page':URL,'Origin':'https://evil.example'}
            assert (await client.post('/frame',data=raw,headers=headers)).status==403
            headers['Origin']='chrome-extension://'+'a'*32
            assert (await client.post('/frame',data=raw,headers=headers)).status==200
            frame,meta=live_frame(tmp_path)
            assert frame==raw and meta['mode']=='live_browser'
            path=tmp_path/'embed/fomo-live-frame.json'
            meta['updated_at']=time.time()-5;path.write_text(json.dumps(meta))
            assert live_frame(tmp_path)==(None,None)
            meta['updated_at']=time.time();path.write_text(json.dumps(meta))
            (tmp_path/'embed/fomo-live-frame.jpg').write_bytes(raw+b'changed')
            assert live_frame(tmp_path)==(None,None)
            assert (await client.get('/intent',headers={'Authorization':'Bearer test-key'})).status==200
    asyncio.run(run())
