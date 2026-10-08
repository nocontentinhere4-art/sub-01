"""A/B/C video: per clip, three variants side by side (top: this morning's montage camera; bottom: a hand close-up),
1280x720, 30 fps. python3 -I abcam.py <spec.json> <out.mp4>
spec: {"title", "secs", "t0"?, "kind": desk|bed, "plane"?, "hand": {"bones", "dir", "dist", "drop"?},
       "variants": [{"label", "glb", "clips", "clip"}] x3}"""
import json, sys, os, io, base64, math, threading, http.server, socketserver, subprocess
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); THREE = os.path.join(HERE, '..', '..', 'node_modules', 'three')
W, H, FPS = 1280, 720, 30; TB = 44; PW = W // 3; PH = (H - TB) // 2
g = json.load(open(sys.argv[1])); out = sys.argv[2]
class Hd(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, p):
        p = p.split('?')[0]
        if p.startswith('/three/'): return os.path.join(THREE, p[7:])
        if p.startswith('/f/'): return '/' + p[3:]
        return os.path.join(HERE, p.lstrip('/'))
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Hd); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
F1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
F2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
def norm(v): n = math.sqrt(sum(x * x for x in v)) or 1; return [x / n for x in v]
def roty(v, a): c, s = math.cos(a), math.sin(a); return [c * v[0] + s * v[2], v[1], -s * v[0] + c * v[2]]
COL = {'MATTINA': (90, 90, 200), 'ORA': (200, 60, 60), 'NUOVO': (20, 140, 60)}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    pages = []
    for v in g['variants']:
        pg = b.new_page(viewport={'width': PW, 'height': PH})
        pg.goto(f'http://127.0.0.1:{port}/view.html?w={PW}&h={PH}&mattress=solid'); pg.wait_for_function('window.ready')
        anims = dict(pg.evaluate(f'load("/f{v["glb"]}", {json.dumps(["/f" + c for c in v["clips"]])})'))
        pg.evaluate('setBg("#dfe3e8"); setKey(1.4); setFloor(true)')
        dur = anims[v['clip']]; t0 = g.get('t0', 0.0)
        if g['kind'] == 'desk':                  # this morning's montage camera
            d = norm(roty([0, 0, 1], math.radians(35))); d = norm([d[0], 0.20, d[2]]); dist = 3.8; c = [0.0, 0.80, 0.12]; pg.evaluate('setSeat(0.58)')
        else:
            pts = []
            for k in range(5):
                pg.evaluate(f'pose("{v["clip"]}", {min(dur - 1e-3, t0 + g["secs"] * k / 4)})')
                pts += pg.evaluate('bones(["mixamorigHips","mixamorigHead","mixamorigLeftHand","mixamorigRightHand","mixamorigLeftFoot","mixamorigRightFoot"])')
            c = [sum(q[k] for q in pts) / len(pts) for k in range(3)]; span = max(max(q[k] for q in pts) - min(q[k] for q in pts) for k in range(3))
            hd, hp = pg.evaluate('bones(["mixamorigHead","mixamorigHips"])')
            ax = norm([hp[0] - hd[0], 0, hp[2] - hd[2]]); d = norm(roty(ax, math.radians(40))); d = norm([d[0], 0.75, d[2]]); dist = max(2.2, 1.9 + span)
        if g.get('plane') is not None: pg.evaluate(f'setPlane({g["plane"]}, {c[0]}, {c[2]}, 1.0, 2.0)')
        pages.append(dict(pg=pg, dur=dur, clip=v['clip'], c=c, d=d, dist=dist, label=v['label'], tgt=None))
    hc = g['hand']; hd_ = norm(hc.get('dir', [0.3, 0.5, 1])); bones = json.dumps(hc['bones'])
    n = int(round(g['secs'] * FPS))
    for i in range(n):
        im = Image.new('RGB', (W, H), (24, 26, 32)); dr = ImageDraw.Draw(im)
        for k, P in enumerate(pages):
            pg = P['pg']; t = min(P['dur'] - 1e-3, g.get('t0', 0.0) + i / FPS); pg.evaluate(f'pose("{P["clip"]}", {t})')
            a = Image.open(io.BytesIO(base64.b64decode(pg.evaluate(f'shot({json.dumps(P["c"])}, {json.dumps(P["d"])}, {P["dist"]})').split(',')[1]))).convert('RGB')
            pts = pg.evaluate(f'bones({bones})'); c = [sum(q[j] for q in pts) / len(pts) for j in range(3)]; c[1] -= hc.get('drop', 0.05)
            P['tgt'] = c if P['tgt'] is None else [0.8 * x + 0.2 * y for x, y in zip(P['tgt'], c)]
            h = Image.open(io.BytesIO(base64.b64decode(pg.evaluate(f'shot({json.dumps(P["tgt"])}, {json.dumps(hd_)}, {hc["dist"]})').split(',')[1]))).convert('RGB')
            im.paste(a, (k * PW, TB)); im.paste(h, (k * PW, TB + PH))
            dr.text((k * PW + 10, TB + 8), P['label'], font=F2, fill=COL.get(P['label'], (0, 0, 0)))
        for k in (1, 2): dr.rectangle([k * PW - 1, TB, k * PW, H], fill=(24, 26, 32))
        dr.text((14, 8), g['title'], font=F1, fill=(255, 255, 255))
        ff.stdin.write(im.tobytes())
    for P in pages: P['pg'].close()
    b.close()
ff.stdin.close(); ff.wait(); srv.shutdown(); print(out, os.path.getsize(out) // 1024, 'KB', flush=True)
