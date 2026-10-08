"""Hand close-up video, before | after side by side: the camera follows the hands (both, or one), 640x360 by default.
python3 -I handcam.py <spec.json> <out.mp4>
spec: {"segments": [{"glb", "before": [clip.glb], "after": [clip.glb], "clip", "title", "secs", "t0"?, "bones"?: [...],
                     "dir"?: [x,y,z] (target -> camera, his frame: +Z forward, +X his left), "dist"?: m, "seat"?: y}]}"""
import json, sys, os, io, base64, math, threading, http.server, socketserver, subprocess
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); THREE = os.path.join(HERE, '..', '..', 'node_modules', 'three')
W, H, FPS = int(os.environ.get('MW', 640)), int(os.environ.get('MH', 360)), int(os.environ.get('MFPS', 24)); HW = W // 2
spec = json.load(open(sys.argv[1])); out = sys.argv[2]
class Hd(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, p):
        p = p.split('?')[0]
        if p.startswith('/three/'): return os.path.join(THREE, p[7:])
        if p.startswith('/f/'): return '/' + p[3:]
        return os.path.join(HERE, p.lstrip('/'))
    def log_message(self, *a): pass
srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Hd); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
F1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', max(12, H // 22))
F2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', max(12, H // 18))
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-maxrate', os.environ.get('MRATE', '900k'), '-bufsize', '2600k',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
def norm(v): n = math.sqrt(sum(x * x for x in v)) or 1; return [x / n for x in v]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    total = 0
    for g in spec['segments']:
        pages = []
        for key in ('before', 'after'):
            pg = b.new_page(viewport={'width': HW, 'height': H})
            pg.goto(f'http://127.0.0.1:{port}/view.html?w={HW}&h={H}&mattress=solid'); pg.wait_for_function('window.ready')
            clips = json.dumps(['/f' + os.path.abspath(c) for c in g[key]])
            anims = dict(pg.evaluate(f'load("/f{os.path.abspath(g["glb"])}", {clips})'))
            pg.evaluate('setBg("#dfe3e8"); setKey(1.4); setFloor(true)')
            if g.get('seat') is not None: pg.evaluate(f'setSeat({g["seat"]})')
            pages.append((pg, anims[g['clip']]))
        bones = json.dumps(g.get('bones', ['mixamorigLeftHand', 'mixamorigRightHand']))
        d = norm(g.get('dir', [0.35, 0.55, 1.0])); dist = g.get('dist', 0.9); t0 = g.get('t0', 0.0); n = int(round(g['secs'] * FPS))
        tgt = None
        for i in range(n):
            ims = []
            for k, (pg, dur) in enumerate(pages):
                t = min(dur - 1e-3, t0 + i / FPS); pg.evaluate(f'pose("{g["clip"]}", {t})')
                if k == 0:                        # one camera for both: follows the before-hands, smoothed
                    pts = pg.evaluate(f'bones({bones})'); c = [sum(q[j] for q in pts) / len(pts) for j in range(3)]
                    tgt = c if tgt is None else [0.85 * a + 0.15 * x for a, x in zip(tgt, c)]
                url = pg.evaluate(f'shot({json.dumps(tgt)}, {json.dumps(d)}, {dist})')
                ims.append(Image.open(io.BytesIO(base64.b64decode(url.split(',')[1]))).convert('RGB'))
            im = Image.new('RGB', (W, H)); im.paste(ims[0], (0, 0)); im.paste(ims[1], (HW, 0))
            dr = ImageDraw.Draw(im); dr.rectangle([HW - 1, 0, HW, H], fill=(30, 30, 30))
            ov = Image.new('RGBA', (W, H // 9), (20, 22, 28, 170)); im.paste(ov, (0, 0), ov)
            dr.text((8, 4), g['title'], font=F1, fill=(255, 255, 255))
            dr.text((8, H - H // 12 - 4), 'PRIMA', font=F2, fill=(200, 40, 40)); dr.text((HW + 8, H - H // 12 - 4), 'DOPO', font=F2, fill=(20, 130, 50))
            ff.stdin.write(im.tobytes())
        total += n; print(f'{g["clip"]:30s} {n} frames, total {total / FPS:.1f}s', flush=True)
        for pg, _ in pages: pg.close()
    b.close()
ff.stdin.close(); ff.wait(); srv.shutdown(); print(out, os.path.getsize(out) // 1024, 'KB')
