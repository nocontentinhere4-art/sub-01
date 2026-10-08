"""Visual QA of web/room.html's UI at one commit: screenshots at 4 viewports, one per panel tab, and the checks a
visitor would hit. python3 ui_qa.py <base url> <out dir> <commit label>
  - viewports: 1280x800 desktop; 390x844, 360x780, 430x932 mobile (is_mobile, has_touch)
  - states: the page as loaded, then each tab of the panel (Vote, Chat, Teach, More) clicked
  - per state: page errors, console errors, horizontal overflow (scrollingElement.scrollWidth > innerWidth),
    tap targets under 44 px (visible links, buttons, inputs, tabs), overlapping fixed elements (not nested)
  - writes <out>/qa_sheet.jpg (rows: viewports, columns: states), <out>/qa.json and <out>/QA.md (worst first)"""
import json, sys, os, time
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
BASE, OUT, LABEL = sys.argv[1].rstrip('/'), sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
VIEWS = [('1280x800', 1280, 800, False), ('390x844', 390, 844, True), ('360x780', 360, 780, True), ('430x932', 430, 932, True)]
TABS = ['Vote', 'Chat', 'Teach', 'More']
SETTLE = float(os.environ.get('SETTLE', 25))
PROBE = '''() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0.05 &&
           r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const name = e => (e.id ? '#' + e.id : e.tagName.toLowerCase() + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\\s+/)[0] : ''))
                    + ((e.innerText || e.value || e.getAttribute('aria-label') || '').trim() ? ' "' + (e.innerText || e.value || e.getAttribute('aria-label')).trim().slice(0, 24) + '"' : '');
  const se = document.scrollingElement;
  const taps = [...document.querySelectorAll('a[href], button, input:not([type=hidden]), select, textarea, [role=button], [role=tab], [onclick], summary, label[for]')]
    .filter(vis).map(e => { const r = e.getBoundingClientRect(); return {el: name(e), w: Math.round(r.width), h: Math.round(r.height)}; })
    .filter(t => t.w < 44 || t.h < 44);
  const fixed = [...document.querySelectorAll('body *')].filter(e => getComputedStyle(e).position === 'fixed' && vis(e));
  const over = [];
  for (let i = 0; i < fixed.length; i++) for (let j = i + 1; j < fixed.length; j++) {
    const a = fixed[i], b = fixed[j]; if (a.contains(b) || b.contains(a)) continue;
    const r = a.getBoundingClientRect(), q = b.getBoundingClientRect();
    const w = Math.min(r.right, q.right) - Math.max(r.left, q.left), h = Math.min(r.bottom, q.bottom) - Math.max(r.top, q.top);
    if (w > 4 && h > 4 && getComputedStyle(a).pointerEvents !== 'none' && getComputedStyle(b).pointerEvents !== 'none' &&
        !(a.tagName === 'CANVAS' || b.tagName === 'CANVAS')) over.push({a: name(a), b: name(b), w: Math.round(w), h: Math.round(h)});
  }
  return {scrollW: se.scrollWidth, innerW: innerWidth, overflow: se.scrollWidth > innerWidth, taps, over: over.slice(0, 20)};
}'''
res = []; shots = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
                          args=['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    for vn, w, h, mob in VIEWS:
        ctx = b.new_context(viewport={'width': w, 'height': h}, is_mobile=mob, has_touch=mob, device_scale_factor=2 if mob else 1)
        pg = ctx.new_page(); errs, cons = [], []
        pg.on('pageerror', lambda e: errs.append(str(e)[:300]))
        pg.on('console', lambda m: cons.append(m.text[:240]) if m.type == 'error' else None)
        try: pg.goto(BASE + '/', wait_until='load', timeout=120000)
        except Exception as e: errs.append(f'goto: {e}'[:200])
        pg.wait_for_timeout(int(SETTLE * 1000))
        for st in ['loaded'] + TABS:
            note = ''
            if st != 'loaded':
                loc = None
                for get in (lambda: pg.get_by_role('tab', name=st, exact=True), lambda: pg.get_by_role('button', name=st, exact=True),
                            lambda: pg.get_by_text(st, exact=True)):
                    try:
                        l = get()
                        if l.count() and l.first.is_visible(): loc = l.first; break
                    except Exception: pass
                if loc is None: note = 'TAB NOT FOUND'
                else:
                    try: loc.click(timeout=15000); pg.wait_for_timeout(1500)
                    except Exception as e: note = f'click failed: {e}'[:160]
            f = f'{OUT}/{vn}_{st}.png'
            try: pg.screenshot(path=f, timeout=180000, animations='disabled'); shots[(vn, st)] = f
            except Exception as e: note += f' shot: {e}'[:120]
            try: pr = pg.evaluate(PROBE)
            except Exception as e: pr = dict(overflow=None, taps=[], over=[], scrollW=0, innerW=0); note += f' probe: {e}'[:120]
            res.append(dict(view=vn, state=st, note=note.strip(), page_errors=list(errs), console_errors=list(cons), **pr))
            print(json.dumps(dict(view=vn, state=st, note=note, errs=len(errs), overflow=pr['overflow'], taps=len(pr['taps']), over=len(pr['over']))), flush=True)
        ctx.close()
    b.close()
json.dump(res, open(f'{OUT}/qa.json', 'w'), indent=1)
# contact sheet: rows = viewports, cols = states; each cell scaled to 300 px tall
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15); CH = 340; states = ['loaded'] + TABS
cells = {}
for (vn, st), f in shots.items():
    im = Image.open(f).convert('RGB'); s = CH / im.height; cells[(vn, st)] = im.resize((max(1, int(im.width * s)), CH))
colw = [max([cells[(v[0], st)].width for v in VIEWS if (v[0], st) in cells] or [200]) for st in states]
sheet = Image.new('RGB', (sum(colw) + 10 * len(states) + 100, (CH + 26) * len(VIEWS) + 30), (245, 245, 245)); dr = ImageDraw.Draw(sheet)
dr.text((8, 6), f'ui-simple QA · {LABEL}', font=F, fill=(0, 0, 0))
for r, v in enumerate(VIEWS):
    y = 30 + r * (CH + 26); dr.text((8, y + CH // 2), v[0], font=F, fill=(0, 0, 0)); x = 100
    for c, st in enumerate(states):
        dr.text((x, y), st, font=F, fill=(60, 60, 60))
        if (v[0], st) in cells: sheet.paste(cells[(v[0], st)], (x, y + 20))
        else: dr.text((x, y + 40), 'no shot', font=F, fill=(200, 0, 0))
        x += colw[c] + 10
sheet.save(f'{OUT}/qa_sheet.jpg', quality=80)
# QA.md, worst first
L = [f'# ui-simple visual QA: {LABEL}', '',
     f'Demo server (`--demo --time-scale 60 --start 10:00`), headless Chromium; viewports {", ".join(v[0] for v in VIEWS)}; states: as loaded, then each tab clicked. Sheet: `qa_sheet.jpg`. Raw: `qa.json`.', '']
errs = sorted({e for r in res for e in r['page_errors']}); cerr = sorted({e for r in res for e in r['console_errors']})
miss = [f"{r['view']} {r['state']}: {r['note']}" for r in res if r['note']]
ovf = [f"{r['view']} {r['state']}: scrollWidth {r['scrollW']} > {r['innerW']}" for r in res if r['overflow']]
ovl = {}
for r in res:
    for o in r['over']: ovl.setdefault(f"{o['a']} × {o['b']}", []).append(f"{r['view']}/{r['state']} ({o['w']}×{o['h']} px)")
taps = {}
for r in res:
    if r['view'] == '1280x800': continue                       # tap size matters on touch
    for t in r['taps']: taps.setdefault(t['el'], set()).add(f"{t['w']}×{t['h']}")
n = 1
def sec(title, items):
    global n
    if not items: return
    L.append(f'## {n}. {title}'); L.extend(f'- {x}' for x in items); L.append(''); n += 1
sec('Page errors (uncaught JS)', errs)
sec('A tab could not be found or clicked', miss)
sec('Horizontal overflow (page scrolls sideways)', ovf)
sec('Overlapping fixed elements', [f'{k}: ' + ', '.join(v[:4]) + (f' (+{len(v) - 4})' if len(v) > 4 else '') for k, v in ovl.items()])
sec('Tap targets under 44 px on touch viewports', [f'{k}: ' + ', '.join(sorted(v)) for k, v in sorted(taps.items())][:40])
sec('Console errors', cerr[:20])
if n == 1: L.append('No problems found by the automatic checks.')
open(f'{OUT}/QA.md', 'w').write('\n'.join(L) + '\n'); print('wrote', OUT)
