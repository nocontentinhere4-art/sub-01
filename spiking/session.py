"""One GPU session on the pod: `python -m spiking.session` (config in the SUB01_SESSION env var, JSON).

Loads the learned weights (from the server, or none), runs the phases, streams compact state to the server over
a websocket authenticated with SUB01_POD_SECRET, writes /out/status.json + /out/results.json (read by
validate / pod_manager through the pod's port 8000) and uploads the learned weights at the end.
Phases: bench, rates, delays, recall_yesterday, encode, pong_train, pong_exam, memory_test, sleep, free.
Items (cfg "items") are the day's chat messages and readings, each {text, source: chat|reading, item}; a reading's
text is its title + keywords. recall_yesterday tests the previous session's items before anything new is stored.
In validate mode extra controls run (no-plasticity Pong, random paddle, sleep without replay).
"""
import json
import math
import os
import queue
import sys
import threading
import time
import traceback
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import torch

from .config import Config
from .memory import MemorySystem, sleep_block, words
from .net import SpikingNet
from .pong import Pong, random_paddle, tracking_paddle

ROOT = Path(__file__).resolve().parent.parent
GROUP_KEYS = ("visual", "somatomotor", "attention", "salience", "limbic", "control", "default", "reward", "fear",
              "memory", "relay", "language")


class StopSession(Exception):
    pass


# --- link to the Railway server (optional) ----------------------------------------------------------------------
class Link:
    """Websocket to the server in a background thread; frames out via a queue, commands in via a queue."""

    def __init__(self, server, secret, session_id):
        self.server, self.secret, self.sid = server.rstrip("/"), secret, session_id
        self.out, self.inbox = queue.Queue(maxsize=200), queue.Queue()
        self.connected = False
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        import asyncio
        asyncio.run(self._main())

    async def _main(self):
        import asyncio
        import aiohttp
        url = self.server.replace("https://", "wss://").replace("http://", "ws://") + f"/api/spiking/pod?session={self.sid}"
        headers = {"Authorization": "Bearer " + self.secret}
        while not self.stop.is_set():
            try:
                async with aiohttp.ClientSession() as http, http.ws_connect(url, headers=headers, heartbeat=20,
                                                                           max_msg_size=1 << 20) as ws:
                    self.connected = True

                    async def reader():
                        async for m in ws:
                            if m.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    self.inbox.put(json.loads(m.data))
                                except ValueError:
                                    pass
                    rd = asyncio.ensure_future(reader())
                    while not self.stop.is_set() and not rd.done():
                        try:
                            msg = self.out.get_nowait()
                            await ws.send_str(json.dumps(msg))
                        except queue.Empty:
                            await asyncio.sleep(0.05)
                    while not self.out.empty():                          # flush (done frame) before closing
                        await ws.send_str(json.dumps(self.out.get_nowait()))
                    rd.cancel()
            except Exception as e:
                print("link error:", type(e).__name__, flush=True)
            self.connected = False
            if not self.stop.is_set():
                await asyncio.sleep(3)

    def send(self, msg):
        try:
            self.out.put_nowait(msg)
        except queue.Full:                                               # drop state frames rather than block the sim
            pass

    def close(self, timeout=10):
        t0 = time.time()
        while not self.out.empty() and time.time() - t0 < timeout:
            time.sleep(0.1)
        self.stop.set()

    def _req(self, path, method="GET", data=None, ctype="application/octet-stream", timeout=300):
        req = urllib.request.Request(self.server + path, method=method, data=data,
                                     headers={"Authorization": "Bearer " + self.secret, "Content-Type": ctype,
                                              "User-Agent": "sub01-pod/1.0"})
        return urllib.request.urlopen(req, timeout=timeout)

    def get_weights(self, path):
        try:
            with self._req("/api/spiking/weights") as r:
                Path(path).write_bytes(r.read())
            return True
        except Exception as e:
            print("no learned weights from server:", type(e).__name__, getattr(e, "code", ""), flush=True)
            return False

    def put_weights(self, path):
        with self._req("/api/spiking/weights", "POST", Path(path).read_bytes()) as r:
            return r.status


# --- the session ---------------------------------------------------------------------------------------------
class Session:
    def __init__(self, cfg, out_dir, link=None):
        self.cfg = cfg
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.link = link
        self.t_wall0 = time.time()
        self.deadline = self.t_wall0 + 60 * float(cfg.get("max_minutes", 55)) - 120   # 2 min to save + upload
        self.results = {"session_id": cfg.get("session_id"), "day": cfg.get("day"), "validate": bool(cfg.get("validate")),
                        "phases": {}, "files": []}
        self.phase, self.progress = "start", 0.0
        self.last_frame_wall, self.last_frame_t, self.last_frame_n, self.frame_snap = 0.0, 0, 0, None
        self.pong = None
        self.stage = "AWAKE"
        self.chat_until = -1
        self.stopping = False
        self.status()

    # --- status / streaming -------------------------------------------------------------------------------------
    def status(self, done=False, error=None):
        st = {"phase": self.phase, "progress": round(self.progress, 3), "done": done, "error": error,
              "t_sim": round(getattr(self, "net", None).t / 1000.0, 1) if getattr(self, "net", None) else 0.0,
              "wall_s": round(time.time() - self.t_wall0, 1)}
        tmp = self.out / "status.json.tmp"
        tmp.write_text(json.dumps(st))
        tmp.replace(self.out / "status.json")

    def log(self, *a):
        print(f"[{time.time() - self.t_wall0:7.1f}s] {self.phase}:", *a, flush=True)

    def hook(self, net):
        now = time.time()
        if now > self.deadline and not self.stopping:
            self.stopping = True
            raise StopSession("deadline")
        if self.chat_until >= 0 and net.t >= self.chat_until:
            net.set_neuron_drive("chat", None)
            self.chat_until = -1
        if now - self.last_frame_wall >= 0.25:
            self.frame(net, now)
        if self.link is not None:
            while True:
                try:
                    msg = self.link.inbox.get_nowait()
                except queue.Empty:
                    break
                self.command(msg)

    def frame(self, net, now):
        if self.frame_snap is None:
            self.frame_snap, self.last_frame_wall, self.last_frame_t = net.snapshot(), now, net.t
            return
        dt_steps = max(1, net.t - self.last_frame_t)
        rr = net.region_rates_since(self.frame_snap)
        groups = net.group_rates(rr)
        n_sp = float((net.region_count - self.frame_snap[2]).sum())
        wall = max(1e-6, now - self.last_frame_wall)
        sim_s = dt_steps * net.cfg.dt / 1000.0
        if int(now) % 5 == 0:
            self.status()
        if self.link is not None:
            p = net.plast
            msg = {"type": "state", "t_sim": round(net.t / 1000.0, 2), "phase": self.phase, "n_neurons": net.n,
                   "spikes_per_s": round(n_sp / sim_s, 1), "mean_rate_hz": round(n_sp / sim_s / net.n, 3),
                   "steps_per_s": round(dt_steps / wall, 1), "realtime_x": round(sim_s / wall, 3),
                   "groups": {k: round(v, 2) for k, v in groups.items() if k in GROUP_KEYS},
                   "raster": {"n": len(net.raster_ids), "t0": int(self.last_frame_t), "t1": int(net.t),
                              "spikes": net.pop_raster(self.last_frame_t)[:4000]},
                   "pong": self.pong.shown.frame() if (self.pong is not None and "pong" in self.phase) else None,
                   "dopamine": round(p.mod["da"], 3) if p is not None else 0.0}
            self.link.send(msg)
        else:
            net.raster_log.clear() if net.raster_rows is not None else None
        self.frame_snap, self.last_frame_wall, self.last_frame_t = net.snapshot(), now, net.t

    def command(self, msg):
        kind = msg.get("type")
        if kind == "stop":
            self.stopping = True
            raise StopSession("stop requested")
        if kind == "good" and self.pong is not None and self.phase in ("pong_train", "free"):
            self.pong.good()
        elif kind == "sleep" and msg.get("stage") in ("AWAKE", "NREM", "REM"):
            self.stage = msg["stage"]
        elif kind == "chat" and isinstance(msg.get("text"), str):
            ws = words(msg["text"])                              # only in the free run: never during exams / tests
            if ws and getattr(self, "mem", None) is not None and self.phase == "free":
                self.net.set_neuron_drive("chat", self.mem.pattern(ws), 4.0)
                self.chat_until = self.net.t + 300
                self.pending_chat.append(msg["text"])

    def result(self, kind, payload):
        rec = {"type": "result", "kind": kind, "day": self.cfg.get("day"), "session": self.cfg.get("session_id"),
               **payload}
        self.results["phases"].setdefault(kind, []).append(payload)
        if self.link is not None:
            self.link.send(rec)
        self.save_results()

    def save_results(self):
        tmp = self.out / "results.json.tmp"
        tmp.write_text(json.dumps(self.results, indent=1, default=float))
        tmp.replace(self.out / "results.json")

    # --- build --------------------------------------------------------------------------------------------------
    def build(self):
        c = self.cfg
        self.phase = "build"
        self.status()
        dev = c.get("device") or ("cuda" if torch.cuda.is_available() else "cpu")
        conf = Config(n_neurons=int(c.get("n_neurons", 20_000)), seed=int(c.get("seed", 1)),
                      **{k: v for k, v in (c.get("config") or {}).items()})
        t0 = time.time()
        self.net = net = SpikingNet(conf, device=dev, verbose=True)
        self.results["build"] = {"device": dev, "gpu": torch.cuda.get_device_name(0) if str(dev).startswith("cuda") else None,
                                 "n_neurons": net.n, "synapses": net.n_syn, "max_delay_ms": net.D - 1,
                                 "plastic_synapses": net.plast.P if net.plast else 0, "build_s": round(time.time() - t0, 1),
                                 "config_hash": conf.config_hash(), "config": conf.to_dict(),
                                 "torch": torch.__version__}
        try:
            from real_baseline import RealBaseline
            net.attach_baseline(RealBaseline(net.reg.names, ROOT / "out" / "rest"))
            self.results["build"]["baseline_runs"] = len(net.baseline.files)
        except Exception as e:
            self.log("no recorded baseline:", type(e).__name__)
        net.enable_raster(200)
        self.mem = MemorySystem(net)
        self.pending_chat = []
        wpath = self.out / "weights_in.npz"
        meta = None
        if self.link is not None and self.link.get_weights(wpath):
            pass
        if wpath.exists() and net.plast is not None:
            try:
                meta = net.plast.load(wpath, elapsed_days=float(c.get("elapsed_days", 0.0)))
                self.mem.from_meta(meta)
                self.log("loaded learned weights:", net.plast.stats())
            except Exception as e:
                self.log("could not load learned weights:", e)
        self.results["build"]["weights_loaded"] = meta is not None
        net.hook = self.hook
        if self.link is not None:
            self.link.send({"type": "hello", "session": c.get("session_id") or self.link.sid, "n_neurons": net.n,
                            "device": self.results["build"]["gpu"] or dev, "phases": c.get("phases")})
        net.run(500)                                                     # settle

    # --- phases -------------------------------------------------------------------------------------------------
    def ph_bench(self):
        net = self.net
        out = {}
        p = net.plast
        for label, frozen in (("plasticity_off", True), ("plasticity_on", False)):
            if p is not None:
                p.frozen = frozen
            net.run(200)
            net.sync()
            t0, s0, n0 = time.time(), net.t, net.n_spikes
            ms = int(self.cfg.get("bench_ms", 5000))
            for k in range(0, ms, 1000):                     # with learning on, a reward every second (as in Pong)
                if p is not None and not frozen:
                    p.dopamine(0.8)
                net.run(min(1000, ms - k))
            net.sync()
            wall = time.time() - t0
            steps = net.t - s0
            out[label] = {"steps_per_s": round(steps / wall, 1), "realtime_x": round(steps / wall / 1000.0, 3),
                          "mean_rate_hz": round((net.n_spikes - n0) / net.n / (steps / 1000.0), 3)}
        if p is not None:
            p.frozen = False
        out.update(n_neurons=net.n, synapses=net.n_syn, gpu=self.results["build"]["gpu"],
                   gpu_mem_gb=round(net.memory_gb(), 2) if net.memory_gb() else None,
                   steps_per_s=out["plasticity_on"]["steps_per_s"], realtime_x=out["plasticity_on"]["realtime_x"])
        self.result("bench", out)

    def ph_rates(self):
        """Mean rates per population over a minute with the recorded drive; runaway check."""
        net = self.net
        secs = int(self.cfg.get("rates_s", 60))
        per_s, e_rates, i_rates = [], [], []
        exc = torch.as_tensor(net.is_exc_np, device=net.device)
        for k in range(secs):
            snap = net.snapshot()
            net.run(1000)
            r = net.rates_since(snap)
            per_s.append(net.region_rates_since(snap))
            e_rates.append(float(r[exc].mean()))
            i_rates.append(float(r[~exc].mean()))
            self.progress = (k + 1) / secs
        rr = np.array(per_s)
        neuron_rates = None
        snap = net.snapshot()
        net.run(2000)
        nr = net.rates_since(snap).cpu().numpy()
        out = {"seconds": secs, "mean_e_hz": round(float(np.mean(e_rates)), 3), "mean_i_hz": round(float(np.mean(i_rates)), 3),
               "region_rate_pct": {str(q): round(float(np.percentile(rr, q)), 3) for q in (1, 5, 50, 95, 99)},
               "region_rate_max": round(float(rr.max()), 3),
               "groups": {k: round(v, 3) for k, v in net.group_rates(rr.mean(0)).items()},
               "per_second_e": [round(x, 3) for x in e_rates],
               "neuron_rate_pct": {str(q): round(float(np.percentile(nr, q)), 3) for q in (5, 50, 95, 99)},
               "frac_silent_2s": round(float(np.mean(nr == 0)), 4),
               "runaway": bool(rr.max() > 50 or np.mean(e_rates) > 15)}
        self.result("rates", out)

    def ph_delays(self):
        net = self.net
        reg = net.reg
        long = (net.kind == 2)
        src_r = net.region_of[net.src[long].long()].cpu().numpy()
        dst_r = net.region_of[net.dst[long].long()].cpu().numpy()
        d = net.delay[long].cpu().numpy().astype(float)
        expect = np.maximum(1, np.round(reg.lengths[src_r, dst_r] / net.cfg.velocity_mm_ms))
        sample = np.random.default_rng(0).choice(len(d), size=min(len(d), 200_000), replace=False)
        out = {"n_long_synapses": int(long.sum()), "max_abs_error_ms": float(np.abs(d - expect).max()),
               "delay_ms_pct": {str(q): float(np.percentile(d[sample], q)) for q in (5, 50, 95)},
               "fibre_mm_pct": {str(q): round(float(np.percentile(reg.lengths[src_r[sample], dst_r[sample]], q)), 1)
                                for q in (5, 50, 95)},
               "velocity_m_s": net.cfg.velocity_mm_ms}
        self.result("delays", out)

    def day_items(self):
        """The day's items: cfg "items" ({text, source, item}), else cfg "messages" as chat; max 5 of each source."""
        raw = self.cfg.get("items")
        if raw is None:
            raw = [{"text": m["text"] if isinstance(m, dict) else str(m), "source": "chat"}
                   for m in (self.cfg.get("messages") or [])]
        out, n = [], {}
        for it in raw:
            src = "reading" if it.get("source") == "reading" else "chat"
            if it.get("text") and n.get(src, 0) < MAX_PER_SOURCE:
                n[src] = n.get(src, 0) + 1
                out.append({"text": str(it["text"]), "source": src, "item": str(it.get("item") or it["text"])})
        return out

    def ph_encode(self, items=None, day=None):
        items = self.day_items() if items is None else items
        day = day or self.cfg.get("day")
        stored = []
        for i, it in enumerate(items):
            r = self.mem.encode(it["text"], day, it["source"], it["item"])
            if r:
                stored.append({"text": it["text"], "item": it["item"], "source": it["source"], "words": r["words"],
                               "drive_rate": round(r["drive_rate"], 2)})
            self.progress = (i + 1) / max(1, len(items))
        self.result("encode", {"stored": stored, "n_registry": len(self.mem.registry)})

    def ph_memory_test(self, label=None, items=None, day=None):
        res = self.mem.test(day or self.cfg.get("day"), lures=int(self.cfg.get("lures", 6)), items=items)
        res.pop("kind", None)
        if label:
            res["label"] = label
        self.result("memory_test", res)
        return res

    def ph_recall_yesterday(self, today=None):
        """Half-cue recall of the previous session's items, a day later (after forgetting), before new encoding."""
        today = today or self.cfg.get("day")
        days = sorted({m.get("day") for m in self.mem.registry if m.get("day") and m.get("day") != today})
        if not days:
            self.result("memory_test", {"label": "next day", "skipped": "nothing stored on an earlier day",
                                        "scores": [], "recalled": []})
            return None
        items = [m for m in self.mem.registry if m.get("day") == days[-1]]
        return self.ph_memory_test("next day", items=items, day=today)

    def _pong(self):
        if self.pong is None:
            self.pong = Pong(self.net, seed=int(self.cfg.get("seed", 1)))
        return self.pong

    def _exam_no_learning(self, rallies, game_seed=None):
        """Control: the same network with every learned change removed (frozen), same exam."""
        p = self.net.plast
        if p is None:
            return self._pong().exam(rallies, game_seed=game_seed)
        dw, theta = p.dw.clone(), self.net.theta.clone()
        p.dw.zero_()
        p._apply()
        self.net.theta.zero_()                                       # also the homeostatic excitability
        self.net._dirty = True
        try:
            return self._pong().exam(rallies, game_seed=game_seed)
        finally:
            p.dw.copy_(dw)
            p._apply()
            self.net.theta.copy_(theta)
            self.net._dirty = True

    def ph_pong_train(self):
        pong = self._pong()
        minutes = float(self.cfg.get("pong_train_minutes", 10))
        blocks = int(self.cfg.get("pong_blocks", 0)) or None
        t_end = self.net.t + minutes * 60_000
        n = 0
        while (blocks is None and self.net.t < t_end) or (blocks is not None and n < blocks):
            pong.train(1, int(self.cfg.get("block_rallies", 20)))
            n += 1
            self.progress = min(1.0, (n / blocks) if blocks else 1 - (t_end - self.net.t) / (minutes * 60_000))
            self.log("block", pong.curve[-1])
        self.result("pong_curve", {"points": pong.curve, "block_rallies": int(self.cfg.get("block_rallies", 20))})

    def ph_pong_exam(self, label="exam"):
        pong = self._pong()
        rallies = int(self.cfg.get("exam_rallies", 20))
        seed = 1000 + len(self.results["phases"].get("exam", []))
        exam = pong.exam(rallies, game_seed=seed)
        ctrl = self._exam_no_learning(rallies, game_seed=seed) if self.net.plast is not None else None
        rnd = random_paddle(2000, seed=int(self.cfg.get("seed", 1)))
        out = {"label": label, **exam, "controls": {"no_plasticity": ctrl["hit_rate"] if ctrl else None,
                                                     "no_plasticity_hits": ctrl["hits"] if ctrl else None,
                                                     "random": rnd["hit_rate"]}}
        self.result("exam", out)
        return out

    def ph_sleep(self, replay=True, label=None):
        minutes = float(self.cfg.get("sleep_minutes", 4))
        reps = sleep_block(self.net, self.mem, minutes, cycles=int(self.cfg.get("sleep_cycles", 2)), replay=replay)
        out = {"minutes_sim": minutes, "replay": replay, "label": label,
               "replays": [r["text"] for r in reps] if reps else []}
        self.result("sleep", out)

    def ph_free(self):
        """Free run with live inputs until the session ends (chat drives patterns; REM from the server replays)."""
        rng = np.random.default_rng(0)
        end = self.deadline
        next_replay = 0.0
        while time.time() < end:
            if self.pending_chat:
                self.mem.encode(self.pending_chat.pop(0), self.cfg.get("day"))
            if self.stage == "REM" and self.net.t >= next_replay:
                self.mem.replay_once(rng)
                next_replay = self.net.t + rng.exponential(5000)
            self.net.mu_offset = (-1.0 + 2.5 * math.sin(2 * math.pi * 0.8 * self.net.t / 1000.0)) if self.stage == "NREM" else 0.0
            self.net._dirty = True
            self.net.run(200)

    # --- run ------------------------------------------------------------------------------------------------------
    def run(self):
        err = None
        try:
            self.build()
            phases = self.cfg.get("phases") or ["bench", "rates", "delays"]
            for i, ph in enumerate(phases):
                self.phase, self.progress = ph, 0.0
                if self.net.plast is not None:                   # eligibility only where dopamine can arrive
                    self.net.plast.set_stdp(ph in ("bench", "pong_train", "validate_pong", "free"))
                self.status()
                self.log("start")
                t0 = time.time()
                if ph == "validate_memory":
                    self.validate_memory()
                elif ph == "validate_reading":
                    self.validate_reading()
                elif ph == "validate_pong":
                    self.validate_pong()
                elif ph == "memory_test":
                    n_before = len(self.results["phases"].get("memory_test", []))
                    slept = any(k.endswith(":sleep") for k in self.results.get("timing", {}))
                    self.ph_memory_test("after sleep" if slept else ("after encoding" if n_before == 0 else None))
                elif ph == "pong_exam":
                    self.ph_pong_exam()
                else:
                    getattr(self, "ph_" + ph)()
                self.results.setdefault("timing", {})[f"{i}:{ph}"] = {"wall_s": round(time.time() - t0, 1)}
                self.log("done in", round(time.time() - t0, 1), "s")
        except StopSession as e:
            self.log("stopping:", e)
            self.results["stopped"] = str(e)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            traceback.print_exc()
        finally:
            self.finish(err)
        return self.results

    def validate_memory(self):
        """Encode -> test -> sleep with replay -> test, and the same sleep without replay (restored weights)."""
        if not self.cfg.get("messages"):
            self.cfg["messages"] = DEMO_MESSAGES
        self.ph_encode()
        self.ph_memory_test("after encoding")
        p = self.net.plast
        dw0 = p.dw.clone()
        theta0, rate0 = self.net.theta.clone(), p.rate.clone()
        reg0 = json.loads(json.dumps(self.mem.registry))
        self.ph_sleep(replay=False, label="control: same time, no replay")
        self.ph_memory_test("after sleep without replay (control)")
        p.dw.copy_(dw0)
        p._apply()
        self.net.theta.copy_(theta0)
        p.rate.copy_(rate0)
        p.last_homeo = None
        self.net._dirty = True
        self.mem.registry = reg0
        self.ph_sleep(replay=True, label="sleep with REM replay")
        self.ph_memory_test("after sleep with replay")

    def validate_reading(self):
        """Two days in one pod: day 1 encodes chat + readings, sleeps with replay, is tested; a day of forgetting
        passes (the decay applied between real sessions); day 2 first tests day 1's items from half cues (the
        "next morning" test), then encodes its own items and sleeps."""
        d2 = self.cfg.get("day") or date.today().isoformat()
        d1 = (date.fromisoformat(d2) - timedelta(days=1)).isoformat()
        day1 = self.cfg.get("items_day1") or DEMO_ITEMS[:6]
        day2 = self.cfg.get("items_day2") or DEMO_ITEMS[6:]
        self.ph_encode(self._norm(day1), d1)
        self.ph_memory_test("after encoding", day=d1)
        self.ph_sleep(replay=True, label="day 1 sleep with REM replay")
        self.ph_memory_test("after sleep", day=d1)
        if self.net.plast is not None:
            self.net.plast.forget(float(self.cfg.get("elapsed_days", 1.0)))
        self.ph_recall_yesterday(today=d2)
        self.ph_encode(self._norm(day2), d2)
        self.ph_sleep(replay=True, label="day 2 sleep with REM replay")
        self.ph_memory_test("after sleep", items=[m for m in self.mem.registry if m.get("day") == d2], day=d2)

    @staticmethod
    def _norm(items):
        return [{"text": it["text"], "source": it.get("source", "chat"), "item": it.get("item") or it["text"]}
                for it in items]

    def validate_pong(self):
        """Exams before training (= no plasticity), training curve, exams after (frozen) + controls."""
        pong = self._pong()
        reps = int(self.cfg.get("exam_repeats", 2))
        er = int(self.cfg.get("exam_rallies", 20))
        pre = [pong.exam(er, game_seed=500 + k) for k in range(reps)]      # same ball sequences before / after
        self.result("exam", {"label": "before training (no learning yet)", "exams": pre,
                             "hits": sum(e["hits"] for e in pre), "rallies": sum(e["rallies"] for e in pre),
                             "hit_rate": round(sum(e["hits"] for e in pre) / sum(e["rallies"] for e in pre), 4)})
        self.ph_pong_train()
        post = [pong.exam(er, game_seed=500 + k) for k in range(reps)]
        ctrl = [self._exam_no_learning(er, game_seed=500 + k) for k in range(reps)]
        rnd = random_paddle(5000, seed=int(self.cfg.get("seed", 1)))
        trk = tracking_paddle(500)
        self.result("exam", {"label": "after training (frozen)", "exams": post,
                             "hits": sum(e["hits"] for e in post), "rallies": sum(e["rallies"] for e in post),
                             "hit_rate": round(sum(e["hits"] for e in post) / sum(e["rallies"] for e in post), 4),
                             "controls": {"no_plasticity": round(sum(e["hits"] for e in ctrl) / sum(e["rallies"] for e in ctrl), 4),
                                          "no_plasticity_exams": ctrl, "random": rnd["hit_rate"],
                                          "ideal_tracker": trk["hit_rate"]}})

    def finish(self, err):
        net = getattr(self, "net", None)
        self.phase = "save"
        self.status()
        try:
            if net is not None and net.plast is not None:
                net.hook = None
                wpath = self.out / "weights.npz"
                info = net.plast.save(wpath, {**self.mem.to_meta(), "last_day": self.cfg.get("day"),
                                              "sessions": int(net.plast.meta.get("sessions", 0)) + 1})
                self.results["weights"] = {**info, "stats": net.plast.stats(), "bytes": wpath.stat().st_size}
                if self.link is not None and not self.cfg.get("validate") and err is None:
                    self.results["weights"]["upload_status"] = self.link.put_weights(wpath)
        except Exception as e:
            err = err or f"save: {type(e).__name__}: {e}"
            traceback.print_exc()
        self.results["wall_s"] = round(time.time() - self.t_wall0, 1)
        self.results["sim_s"] = round(net.t / 1000.0, 1) if net is not None else 0
        self.results["error"] = err
        self.results["files"] = sorted({"results.json", "session.log"} | set(self.results.get("files", [])))
        self.save_results()
        if self.link is not None:
            self.link.send({"type": "done", "ok": err is None, "error": err})
            self.link.close()
        self.phase = "done"
        self.status(done=True, error=err)


MAX_PER_SOURCE = 5
# synthetic validation items: invented chat lines + public Wikipedia titles with keywords (no real chat content)
DEMO_ITEMS = [
    {"text": "good morning little brain, the sun is warm today", "source": "chat"},
    {"text": "a red bicycle crossed the bridge near the river", "source": "chat"},
    {"text": "Inokashira Park park pond cherry blossoms kichijoji zoo boats", "source": "reading",
     "item": "Inokashira Park"},
    {"text": "Bread flour dough yeast baking oven crust wheat", "source": "reading", "item": "Bread"},
    {"text": "Moon orbit tides craters lunar apollo satellite phases", "source": "reading", "item": "Moon"},
    {"text": "Origami paper folding crane sheet japanese craft", "source": "reading", "item": "Origami"},
    {"text": "do you dream about the ocean and its waves", "source": "chat"},
    {"text": "Tea leaves brewing ceremony matcha kettle cups", "source": "reading", "item": "Tea"},
    {"text": "Lighthouse tower lamp coast ships beacon keeper", "source": "reading", "item": "Lighthouse"},
    {"text": "Snow crystals winter flakes cold mountains white", "source": "reading", "item": "Snow"},
]
DEMO_MESSAGES = [  # synthetic messages for validation (no real chat content)
    {"text": "good morning little brain, the sun is warm today", "emotion": "positive"},
    {"text": "a red bicycle crossed the bridge near the river", "emotion": "neutral"},
    {"text": "do you dream about the ocean and its waves", "emotion": "neutral"},
    {"text": "the bakery smells of fresh bread and coffee", "emotion": "positive"},
    {"text": "we watched the stars over the quiet mountain", "emotion": "neutral"},
]


def run_session(cfg, out_dir, stream=None):
    """In-process entry (CPU validation, tests). `stream`: optional Link-like object."""
    return Session(dict(cfg), out_dir, stream).run()


def main():
    cfg = json.loads(os.environ.get("SUB01_SESSION") or "{}")
    out = Path(os.environ.get("SUB01_OUT", "/out"))
    link = None
    if os.environ.get("SUB01_SERVER_URL") and os.environ.get("SUB01_POD_SECRET"):
        link = Link(os.environ["SUB01_SERVER_URL"], os.environ["SUB01_POD_SECRET"],
                    os.environ.get("SUB01_SESSION_ID") or cfg.get("session_id") or "session")
        for _ in range(100):                                             # up to 10 s for the websocket
            if link.connected:
                break
            time.sleep(0.1)
    res = Session(cfg, out, link).run()
    sys.exit(0 if not res.get("error") else 1)


if __name__ == "__main__":
    main()
