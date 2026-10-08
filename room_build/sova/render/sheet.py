"""Headless contact sheet: python3 -I sheet.py <out.jpg> <spec.json>
spec: {"glbs": [{"glb": path, "clip": name, "title": str, "plane": [y,cx,cz,sx,sz] | null, "views": {"front": [dx,dy,dz], "side": [...]}, "frames": 8}]}"""
import json, sys, os, base64, io, threading, functools, http.server, socketserver
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
THREE = os.path.join(HERE, '..', '..', 'node_modules', 'three')
spec = json.load(open(sys.argv[2])); out = sys.argv[1]
class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, p):
        p = p.split('?')[0]
        if p.startswith('/three/'): return os.path.join(THREE, p[7:])
        if p.startswith('/f/'): return '/' + p[3:]
        return os.path.join(HERE, p.lstrip('/'))
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
TILE = int(os.environ.get("TILE", 240)); rows = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    for g in spec['glbs']:
        pg = b.new_page(); pg.goto(f'http://127.0.0.1:{port}/view.html'); pg.wait_for_function('window.ready')
        anims = dict(pg.evaluate(f'load("/f{os.path.abspath(g["glb"])}")'))
        dur = anims[g['clip']]; nf = g.get('frames', 8)
        plane_y = g['plane'][0] if g.get('plane') else None
        F, Lf = pg.evaluate(f'basis("{g["clip"]}", 6)')
        def auto(v):
            if not isinstance(v, str): return v
            up = [0, 1, 0]; e = 0.35
            hd, hp = pg.evaluate('bones(["mixamorigHead","mixamorigHips"])')
            ax = [hp[0] - hd[0], 0, hp[2] - hd[2]]; nn = (ax[0] ** 2 + ax[2] ** 2) ** .5 or 1; ax = [ax[0] / nn, 0, ax[2] / nn]
            base = {'front': F, 'left': Lf, 'right': [-x for x in Lf], 'feet': ax}[v.split('+')[0]]
            if v.startswith('feet'): e = 0.6
            if '+top' in v: e = 1.2
            return [base[k] + e * up[k] for k in range(3)]
        for view, d in g['views'].items():
            d = auto(d)
            imgs = []
            for i in range(nf):
                t = dur * (i + 0.5) / nf
                pg.evaluate(f'pose("{g["clip"]}", {t})')
                bs = pg.evaluate('bones(["mixamorigHips","mixamorigHead","mixamorigLeftHand","mixamorigRightHand","mixamorigLeftFoot","mixamorigRightFoot"])')
                c = [sum(x[k] for x in bs) / len(bs) for k in range(3)]
                if g.get('target') == 'head':
                    hh = pg.evaluate('bones(["mixamorigHead","mixamorigLeftHand","mixamorigRightHand"])'); c = [(2 * hh[0][k] + hh[1][k] + hh[2][k]) / 4 for k in range(3)]
                elif isinstance(g.get('target'), str):
                    c = pg.evaluate(f'bones(["{g["target"]}"])')[0]
                elif g.get('target'): c = g['target']
                if plane_y is not None:
                    # mattress top under his torso only (hips -> head, +-0.45 m wide; it ends near his knees)
                    hp, hd = bs[0], bs[1]; cx, cz = (hp[0] + hd[0]) / 2, (hp[2] + hd[2]) / 2
                    sx, sz = abs(hd[0] - hp[0]) + 0.9, abs(hd[2] - hp[2]) + 0.9
                    pg.evaluate(f'setPlane({plane_y}, {cx}, {cz}, {sx}, {sz})')
                url = pg.evaluate(f'shot({json.dumps(c)}, {json.dumps(d)}, {g.get("dist", 3.6)})')
                im = Image.open(io.BytesIO(base64.b64decode(url.split(',')[1]))).convert('RGB').resize((TILE, TILE))
                ImageDraw.Draw(im).text((4, 4), f'{view} t={t:.1f}s', fill=(20, 20, 20)); imgs.append(im)
            rows.append((f'{g["title"]} - {view}', imgs))
        pg.close()
    b.close()
srv.shutdown()
ncol = max(len(r[1]) for r in rows); LH = 18
sheet = Image.new('RGB', (ncol * TILE, len(rows) * (TILE + LH)), (255, 255, 255)); d = ImageDraw.Draw(sheet)
for r, (title, imgs) in enumerate(rows):
    y = r * (TILE + LH); d.text((4, y + 3), title, fill=(0, 0, 0))
    for i, im in enumerate(imgs): sheet.paste(im, (i * TILE, y + LH))
sheet.save(out, quality=82); print(out, sheet.size)
