"""Montage video of the baked clips on our character: one 3/4-front camera per clip, a title on top, 1280x720 30 fps H.264.
python3 -I montage.py <spec.json> <out.mp4>
spec: {"segments": [{"glb", "clips"?, "clip", "title", "sub"?, "t0"?, "secs", "speed"?, "kind": "desk"|"bed", "plane"?: y}]}"""
import json, sys, os, io, base64, math, threading, http.server, socketserver, subprocess
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); THREE = os.path.join(HERE, '..', '..', 'node_modules', 'three')
W, H, FPS = 1280, 720, 30
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
F1 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 46)
F2 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22)
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '24', '-maxrate', '1300k', '-bufsize', '2600k',
                       '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
def norm(v): n = math.sqrt(sum(x * x for x in v)) or 1; return [x / n for x in v]
def roty(v, a): c, s = math.cos(a), math.sin(a); return [c * v[0] + s * v[2], v[1], -s * v[0] + c * v[2]]
BONES = '["mixamorigHips","mixamorigHead","mixamorigLeftHand","mixamorigRightHand","mixamorigLeftFoot","mixamorigRightFoot"]'
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    total = 0
    for g in spec['segments']:
        pg = b.new_page(viewport={'width': W, 'height': H})
        pg.goto(f'http://127.0.0.1:{port}/view.html?w={W}&h={H}&mattress=solid'); pg.wait_for_function('window.ready')
        clips = json.dumps(['/f' + os.path.abspath(c) for c in g.get('clips', [])])
        anims = dict(pg.evaluate(f'load("/f{os.path.abspath(g["glb"])}", {clips})')); dur = anims[g['clip']]
        pg.evaluate('setBg("#dfe3e8"); setKey(1.4); setFloor(true)')
        t0, sp, n = g.get('t0', 0.0), g.get('speed', 1.0), int(round(g['secs'] * FPS))
        # one camera for the segment: framed on the body over the samples, 3/4 front
        samples = [min(dur - 1e-3, t0 + sp * g['secs'] * k / 4) for k in range(5)]
        pts = []
        for t in samples:
            pg.evaluate(f'pose("{g["clip"]}", {t})'); pts += pg.evaluate(f'bones({BONES})')
        c = [sum(q[k] for q in pts) / len(pts) for k in range(3)]
        span = max(max(q[k] for q in pts) - min(q[k] for q in pts) for k in range(3))
        F, Lf = pg.evaluate(f'basis("{g["clip"]}", 6)')
        if g['kind'] == 'desk':
            d = norm(roty([0, 0, 1], math.radians(35))); d = norm([d[0], 0.20, d[2]]); dist = 3.8
            c = [0.0, 0.80, 0.12]; pg.evaluate('setSeat(0.58)')
        else:                                    # lying: from beside his feet, 3/4, from above
            hd, hp = pg.evaluate('bones(["mixamorigHead","mixamorigHips"])')
            ax = norm([hp[0] - hd[0], 0, hp[2] - hd[2]]); d = norm(roty(ax, math.radians(g.get('yaw', 40)))); d = norm([d[0], 0.75, d[2]])
            dist = max(2.2, 1.9 + span)
        if g.get('plane') is not None:
            pg.evaluate(f'setPlane({g["plane"]}, {c[0]}, {c[2]}, 1.0, 2.0)')
        for i in range(n):
            t = min(dur - 1e-3, t0 + sp * i / FPS)
            pg.evaluate(f'pose("{g["clip"]}", {t})')
            url = pg.evaluate(f'shot({json.dumps(c)}, {json.dumps(d)}, {dist})')
            im = Image.open(io.BytesIO(base64.b64decode(url.split(',')[1]))).convert('RGB')
            ov = Image.new('RGBA', (W, 96), (20, 22, 28, 170)); im.paste(ov, (0, 0), ov)
            dr = ImageDraw.Draw(im); dr.text((40, 14), g['title'], font=F1, fill=(255, 255, 255))
            if g.get('sub'): dr.text((42, 66), g['sub'], font=F2, fill=(210, 214, 222))
            ff.stdin.write(im.tobytes())
        total += n; print(f'{g["clip"]:30s} {n} frames, total {total / FPS:.1f}s', flush=True); pg.close()
    b.close()
ff.stdin.close(); ff.wait(); srv.shutdown(); print(out, os.path.getsize(out) // 1024, 'KB')
