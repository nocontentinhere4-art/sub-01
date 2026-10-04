"""Records the live brain model's per-region activity and sleep stage from a running server's /ws (demo or live).
usage: python record_act.py <url> <seconds> <out.json>"""
import asyncio, json, sys, time
import aiohttp

async def main(url, secs, out):
    rows, t0 = [], time.time()
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect(url) as ws:
            async for m in ws:
                d = json.loads(m.data)
                if d.get("type") != "tick" or not d.get("act"):
                    continue
                sl = d.get("sleep") or {}
                rows.append({"t": round(time.time() - t0, 3), "act": [round(a, 4) for a in d["act"]],
                             "stage": sl.get("stage"), "clock": sl.get("clock"), "sync": d.get("sync")})
                if time.time() - t0 > secs:
                    break
    json.dump(rows, open(out, "w"))
    st = {}
    for r in rows:
        st[r["stage"]] = st.get(r["stage"], 0) + 1
    print(out, len(rows), "ticks", st, rows[0]["clock"], "->", rows[-1]["clock"])

asyncio.run(main(sys.argv[1], float(sys.argv[2]), sys.argv[3]))
