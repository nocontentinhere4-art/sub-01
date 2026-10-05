"""Bridge to r/bake.html: render the bind-pose mesh from an OpenCV-style camera, get colour + world positions."""
import base64, functools, http.server, threading, numpy as np, io
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent   # serves bake.html; needs node_modules here (npm i in room_build, symlink it)


def lookat(pos, tgt, up=(0, 1, 0)):
    """OpenCV R, t for a camera at pos looking at tgt (x right, y down, z forward)."""
    pos, tgt, up = map(lambda v: np.asarray(v, float), (pos, tgt, up))
    z = tgt - pos; z /= np.linalg.norm(z)
    x = np.cross(z, up); x /= np.linalg.norm(x)    # right
    y = np.cross(z, x)                              # down
    R = np.stack([x, y, z])
    return R, -R @ pos


def cw_of(R, t):
    C = -R.T @ t
    M = np.eye(4); M[:3, :3] = R.T @ np.diag([1, -1, -1]); M[:3, 3] = C
    return M.flatten().tolist()


class Renderer:
    def __init__(self, glb, extra=None):
        files = {'/model.glb': glb, **(extra or {})}

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(s, *a, **k): super().__init__(*a, directory=str(ROOT), **k)
            def log_message(s, *a): pass
            def translate_path(s, path):
                p = path.split('?')[0]
                return str(files[p]) if p in files else super().translate_path(path)
        self.files = files
        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.pw = sync_playwright().start()
        self.b = self.pw.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                                         args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])
        self.p = self.b.new_page(viewport={'width': 2048, 'height': 2048})
        self.p.on('pageerror', lambda e: print('PAGEERR', e))
        self.p.goto(f'http://127.0.0.1:{self.srv.server_address[1]}/bake.html?glb=/model.glb')
        self.p.wait_for_function('window.ready', timeout=600000)
        self.info = self.p.evaluate('window.info')

    def set_texture(self, path, slot='map'):
        key = f'/tex_{slot}.png'; self.files[key] = path
        self.p.evaluate("([u, s]) => setTexture(u, s)", [key + '?' + str(np.random.randint(1e9)), slot])

    def view(self, cam, w, h, pos=True, crop=None):
        """cam: {'K': 3x3, 'R', 't'} or {'ortho': [l, r, t, b], 'R', 't'}. Returns (rgb uint8 HxWx3, pos float HxWx4 or None)."""
        c = {'cw': cw_of(cam['R'], cam['t']), 'full': [w, h]}
        if crop: c['crop'] = list(map(int, crop)); w, h = c['crop'][2], c['crop'][3]
        if 'ortho' in cam: c['ortho'] = list(map(float, cam['ortho']))
        else: K = cam['K']; c.update(fy=float(K[1, 1]), cx=float(K[0, 2]), cy=float(K[1, 2]))
        out = self.p.evaluate('([c,w,h,p]) => view(c,w,h,p)', [c, w, h, pos])
        png = self.p.locator('canvas').screenshot()
        rgb = np.asarray(Image.open(io.BytesIO(png)).convert('RGB'))
        P = None
        if pos:
            P = np.frombuffer(base64.b64decode(out['pos']), np.float32).reshape(h, w, 4)[::-1].copy()
        return rgb, P

    def close(self):
        self.b.close(); self.pw.stop(); self.srv.shutdown()
