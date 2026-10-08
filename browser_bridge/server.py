"""Local authenticated receiver for the owner-selected, guarded Fomo tab.

No cookies, wallet keys, or browser credentials enter this service.
"""
import argparse
import hashlib
import hmac
import io
import json
import re
import time
from pathlib import Path
from aiohttp import web
from PIL import Image

TOKEN_PAGE=re.compile(r'https://fomo\.family/tokens/solana/([1-9A-HJ-NP-Za-km-z]{32,44})/?\Z')
KEY=web.AppKey('bridge.config',dict)

def validated_frame(raw,url):
    if not TOKEN_PAGE.fullmatch(url) or len(raw)>1500000:raise ValueError('invalid source')
    with Image.open(io.BytesIO(raw)) as image:
        if image.format!='JPEG' or not 320<=image.width<=1920 or not 180<=image.height<=1080:raise ValueError('invalid frame')
        image.verify()
    return hashlib.sha256(raw).hexdigest()

def write_atomic(path,raw):
    tmp=path.with_suffix('.tmp');tmp.write_bytes(raw);tmp.replace(path)

def application(token,data_dir):
    app=web.Application(client_max_size=1500000)
    app[KEY]={'token':token,'data':Path(data_dir)}
    target=Path(data_dir)/'embed';target.mkdir(parents=True,exist_ok=True)
    def check(request):
        if request.remote not in ('127.0.0.1','::1') or not hmac.compare_digest(request.headers.get('Authorization',''),'Bearer '+token):raise web.HTTPUnauthorized()
        origin=request.headers.get('Origin','')
        if origin and not re.fullmatch(r'chrome-extension://[a-p]{32}',origin):raise web.HTTPForbidden()
    async def frame(request):
        check(request);raw=await request.read();url=request.headers.get('X-Fomo-Page','')
        try:digest=validated_frame(raw,url)
        except (ValueError,OSError):raise web.HTTPBadRequest()
        write_atomic(target/'fomo-live-frame.jpg',raw)
        meta={'version':1,'mode':'live_browser','source':'fomo-tab-extension','page':url,'revision':digest,'updated_at':time.time()}
        write_atomic(target/'fomo-live-frame.json',json.dumps(meta).encode())
        return web.json_response({'ok':True})
    async def intent(request):
        check(request)
        try:
            data=json.loads((Path(data_dir)/'copytrading/display-intent.json').read_text())
            if not 0<=time.time()-data['updated_at']<=300 or not re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}',data['mint']):raise ValueError()
            result={'mint':data['mint'],'revision':data['revision']}
        except (ValueError,KeyError,OSError,TypeError):result={}
        return web.json_response(result,headers={'Cache-Control':'no-store'})
    app.router.add_post('/frame',frame);app.router.add_get('/intent',intent)
    return app

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--data-dir',required=True);a=p.parse_args()
    config=json.loads(Path(a.config).read_text())
    web.run_app(application(config['token'],a.data_dir),host='127.0.0.1',port=8878)

if __name__=='__main__':main()
