"""Review shots: open every route on a running demo server, collect JS errors, screenshot desktop + phone.
Usage: BROWSE=0 python3 live_server.py --demo --port 8799 &  then  python3 tools/review_shots.py http://localhost:8799 [out_dir]"""
import sys, os, time, json
from playwright.sync_api import sync_playwright
base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8799"
out = sys.argv[2] if len(sys.argv) > 2 else "tests/visual/out/review"; os.makedirs(out, exist_ok=True)
routes = ["/", "/brain", "/room", "/diary", "/world.html", "/tastes.html", "/about.html", "/life.html"]
report = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])
    for w, h, tag in ((1440, 900, "desk"), (390, 844, "phone")):
        ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
        for r in routes:
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.on("console", lambda m: errs.append("console: " + m.text[:200]) if m.type == "error" and "api/screen" not in m.text and "favicon" not in m.text else None)
            try:
                pg.goto(base + r, wait_until="domcontentloaded", timeout=30000); time.sleep(7 if r in ("/", "/brain", "/room") else 3)
                name = (r.strip("/").replace("/", "_").replace(".html", "") or "live") + "-" + tag + ".png"
                pg.screenshot(path=os.path.join(out, name), full_page=(tag == "phone"))
                sw = pg.evaluate("document.documentElement.scrollWidth"); cw = pg.evaluate("document.documentElement.clientWidth")
                report[r + " " + tag] = {"errors": errs[:5], "hscroll": sw > cw + 1, "shot": name}
            except Exception as e:
                report[r + " " + tag] = {"errors": errs[:5] + ["LOAD: " + str(e)[:160]]}
            pg.close()
        ctx.close()
    b.close()
print(json.dumps(report, indent=1))
