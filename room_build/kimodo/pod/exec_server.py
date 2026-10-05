"""Tiny command server for the one GPU pod (the pod has no SSH route from the sandbox): POST /exec runs a shell command in
the background, GET /job polls it, POST /upload and GET /file move files. Every request needs the X-Tok header, a random
value made per run and passed to the pod as EXEC_TOKEN (never committed). Port 8000, reached through the RunPod HTTPS proxy."""
import http.server, json, os, subprocess, threading, uuid, urllib.parse, shutil
TOK = os.environ["EXEC_TOKEN"]; JOBS = {}
def run(jid, cmd):
    log = f"/workspace/jobs/{jid}.log"
    with open(log, "w") as f:
        p = subprocess.Popen(["bash", "-lc", cmd], stdout=f, stderr=subprocess.STDOUT, cwd="/workspace")
        JOBS[jid]["pid"] = p.pid; JOBS[jid]["rc"] = p.wait()
class H(http.server.BaseHTTPRequestHandler):
    def auth(self):
        if self.headers.get("X-Tok") != TOK:
            self.send_response(403); self.end_headers(); return False
        return True
    def out(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if not self.auth(): return
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path == "/job":
            jid = q["id"][0]; j = JOBS.get(jid, {})
            try: txt = open(f"/workspace/jobs/{jid}.log", errors="replace").read()[-int(q.get("n", ["6000"])[0]):]
            except Exception: txt = ""
            return self.out({"rc": j.get("rc"), "log": txt})
        if u.path == "/file":
            p = q["path"][0]; sz = os.path.getsize(p); self.send_response(200)
            self.send_header("Content-Length", str(sz)); self.end_headers()
            with open(p, "rb") as f: shutil.copyfileobj(f, self.wfile)
            return
        self.out({"ok": True})
    def do_POST(self):
        if not self.auth(): return
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        n = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(n)
        if u.path == "/exec":
            jid = uuid.uuid4().hex[:8]; JOBS[jid] = {}
            threading.Thread(target=run, args=(jid, body.decode()), daemon=True).start()
            return self.out({"id": jid})
        if u.path == "/upload":
            p = q["path"][0]; os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            open(p, "wb").write(body); return self.out({"ok": True, "n": len(body)})
    def log_message(self, *a): pass
os.makedirs("/workspace/jobs", exist_ok=True)
http.server.ThreadingHTTPServer(("0.0.0.0", 8000), H).serve_forever()
