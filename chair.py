"""The chair: visitors send simulated shocks to his network; the measured activity moves his body (web/chair.html).

The chain, and what each link is:
  1. a visitor picks an intensity (1-5) and presses the button -> {"type": "shock", "level": k} on /ws/chair;
  2. the Hub validates it, throttles it per client, keeps a bounded queue and a global cooldown, and answers the
     sender with the request's state: queued, throttled, full, unavailable or stopped (nothing is enforced by the page);
  3. the one source (today: the simulation child process, spiking/alif.py; the Source interface below is what a
     future provider would implement) delivers the stimulus as a pulse train into the running network: the request
     becomes "delivered", with the simulation time and what was injected;
  4. the network's measured activity (population rates in 20 ms bins, against its own quiet baseline) streams to
     every viewer as the trace; when the activity is back in its band, or 6 s have passed, the response card closes:
     "measured" (peak against baseline, onset, burst, recruitment, undershoot, recovery);
  5. the body (web/chair_scene.js) animates from the three numbers of Drive, read off the bins: tension (rate above
     baseline), slack (the undershoot) and heavy (the adaptation current above its baseline); the lamp dip at
     delivery is the only thing that follows the button itself;
  6. speech.py turns the same measured state into his short reactions and the odd comment.

Every viewer sees the same experiment: one process advances the network, the Hub broadcasts one trace. Timestamps:
`t_wall` (server epoch ms) and `t_ms` (simulation ms) on every event; ids `c-<n>` from the server.

Limits (server side): levels 1-5; QUEUE_MAX waiting; one delivery every COOLDOWN_S and at most PER_MINUTE a minute;
per client one request every CLIENT_EVERY_S with a burst of CLIENT_BURST; the operator can stop and reset
(/api/chair/stop, /api/chair/resume, /api/chair/reset, admin token). With no viewer for IDLE_PAUSE_S the network
pauses (its state is kept, nothing is simulated or sent); it resumes on the next viewer.

Honesty: when the source is down the page shows "unavailable" and gets no trace, no drive and no speech; nothing is
made up to fill the gap. The label on the page is "Simulated neural activity". No living neurons and no hardware are
connected; a source that is not the simulation must say what it is in its status and must never be relabelled.
"""
import asyncio
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

from aiohttp import web

HERE = Path(__file__).resolve().parent
LEVEL_MIN, LEVEL_MAX = 1, 5
QUEUE_MAX = 6
COOLDOWN_S = 2.0
PER_MINUTE = 20
CLIENT_EVERY_S, CLIENT_BURST = 3.0, 2
IDLE_PAUSE_S = 45.0
TRACE_KEEP = 500                  # bins kept for a late joiner (10 s at 20 ms)
EVENTS_KEEP = 60
MAX_WS = 200
SAY_WAIT_S, SAY_WAIT_COMMENT_S = 2.5, 12.0   # how long a line waits for its audio (cached reactions answer at once)
LABEL = "Simulated neural activity"
STATES = ("queued", "delivered", "measured", "refused", "dropped", "throttled", "full", "unavailable", "stopped")


class Bucket:
    """Token bucket: `burst` tokens, one back every `every` seconds."""

    def __init__(self, every, burst, clock):
        self.every, self.burst, self.clock = every, burst, clock
        self.tokens, self.at = float(burst), clock()

    def take(self):
        now = self.clock()
        self.tokens = min(self.burst, self.tokens + (now - self.at) / self.every)
        self.at = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return 0.0
        return round((1.0 - self.tokens) * self.every, 1)      # seconds until the next token


# --- the source interface ----------------------------------------------------------------------------------------------
class Source:
    """What the Hub needs from whatever produces the activity. Only SimSource exists. A biological provider would
    implement the same calls and report kind="biological" in status(); the page shows the kind it is told."""
    kind = "simulation"

    def __init__(self):
        self.on_trace = None          # async callable(trace dict)
        self.on_event = None          # async callable(event dict): delivered / measured / refused
        self.on_state = None          # async callable(status dict)

    def status(self):
        return {"kind": self.kind, "available": False, "running": False}

    async def start(self): ...
    async def stimulate(self, rid, level): return False
    async def resume(self): ...
    async def pause(self): ...
    async def reset(self): ...


class SimSource(Source):
    """The simulation child (python -m spiking.alif), restarted with a backoff when it dies."""

    def __init__(self, n_neurons=None, python=sys.executable):
        super().__init__()
        self.n_neurons = int(n_neurons or os.environ.get("SUB01_CHAIR_NEURONS") or 20_000)
        self.python = python
        self.proc, self.ready, self.info = None, False, {}
        self.running = False
        self.restarts = 0
        self._stopping = False
        self._reader = None
        self.want_running = False

    def status(self):
        return {"kind": self.kind, "available": bool(self.ready and self.alive()), "running": bool(self.running and self.ready),
                "n_neurons": self.info.get("n_neurons"), "restarts": self.restarts, "label": LABEL,
                "mechanisms": ["membrane potential and spikes", "refractory period", "excitatory and inhibitory synapses",
                               "synaptic time constants", "conduction delays", "spike-frequency adaptation",
                               "background noise"]}

    def alive(self):
        return self.proc is not None and self.proc.returncode is None

    async def start(self):
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "TZ", "PYTHONPATH")}
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", PYTHONUNBUFFERED="1")
        self.ready, self.running = False, False
        self.proc = await asyncio.create_subprocess_exec(self.python, "-m", "spiking.alif", "--neurons", str(self.n_neurons),
                                                         stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                                                         env=env, cwd=str(HERE), limit=1 << 20)
        self._reader = asyncio.get_running_loop().create_task(self._read(self.proc))

    async def _read(self, proc):
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                kind = msg.get("type")
                if kind == "ready":
                    self.info, self.ready = msg, True
                    print(f"chair: network ready, {msg.get('n_neurons')} neurons", flush=True)
                    if self.want_running:
                        await self.resume()
                    await self._state()
                elif kind == "trace":
                    self.running = bool(msg.get("running"))
                    if self.on_trace:
                        await self.on_trace(msg)
                elif kind == "state":
                    self.running = bool(msg.get("running"))
                    await self._state()
                elif kind in ("delivered", "measured", "refused", "reset_done", "flatline", "revived"):
                    if self.on_event:
                        await self.on_event(msg)
        finally:
            self.ready, self.running = False, False
            await self._state()

    async def _state(self):
        if self.on_state:
            try:
                await self.on_state(self.status())
            except Exception as e:
                print("chair: state not sent:", repr(e)[:100], flush=True)

    def send(self, msg):
        if not self.alive() or not self.ready:
            return False
        try:
            self.proc.stdin.write((json.dumps(msg) + "\n").encode())
            return True
        except (BrokenPipeError, ConnectionResetError, RuntimeError):
            return False

    async def stimulate(self, rid, level):
        return self.send({"type": "stim", "id": rid, "level": int(level)})

    async def resume(self):
        self.want_running = True
        return self.send({"type": "resume"})

    async def pause(self):
        self.want_running = False
        return self.send({"type": "pause"})

    async def reset(self):
        return self.send({"type": "reset", "id": "reset"})

    async def run(self):
        """Keep the child alive (supervised by live_server)."""
        backoff = 5.0
        while not self._stopping:
            if not self.alive():
                if self.proc is not None:
                    self.restarts += 1
                    print(f"chair: network process exited ({self.proc.returncode}); restarting in {backoff:.0f} s", flush=True)
                    await asyncio.sleep(backoff)
                    backoff = min(300.0, backoff * 2)
                try:
                    await self.start()
                except Exception as e:
                    print("chair: cannot start the network:", repr(e)[:120], flush=True)
                    await asyncio.sleep(backoff)
                    continue
            else:
                backoff = 5.0
            await asyncio.sleep(2.0)

    async def stop(self):
        self._stopping = True
        if self.alive():
            self.send({"type": "stop"})
            try:
                await asyncio.wait_for(self.proc.wait(), 3.0)
            except asyncio.TimeoutError:
                self.proc.kill()


# --- the hub -----------------------------------------------------------------------------------------------------------
class Hub:
    def __init__(self, source, key_of=None, clock=time.time, on_delivered=None, speech=None, admin_ok=None, chat=None, on_chat=None):
        self.source = source
        self.key_of = key_of or (lambda request: request.remote or "?")
        self.clock = clock
        self.on_delivered = on_delivered          # callable(event): the live brain gets the shock too (live_server)
        self.speech = speech                      # speech.Speech or None
        self.chat = chat                          # speech.ChairChat or None (the page's chat)
        self.on_chat = on_chat                    # callable(text): the message reaches the live brain too
        self.admin_ok = admin_ok or (lambda request: False)
        self.clients = set()
        self.buckets = {}                         # client key -> Bucket (memory only; stale ones pruned)
        self.queue = deque()
        self.deliveries = deque()                 # wall times of deliveries (the per-minute cap)
        self.last_delivery = -1e9
        self.inflight = None                      # the request sent to the source, until "delivered" / "refused"
        self.open_card = None                     # the delivered stimulus until "measured"
        self.n = 0
        self.events = deque(maxlen=EVENTS_KEEP)
        self.cards = deque(maxlen=10)
        self.bins = deque(maxlen=TRACE_KEEP)
        self.last_trace = None
        self.stopped = False
        self.flat = False                         # the network flatlined (a rule of the piece: spiking/alif.py)
        self.last_viewer = clock()
        self.stats = {"submitted": 0, "delivered": 0, "throttled": 0, "full": 0, "refused": 0}
        source.on_trace, source.on_event, source.on_state = self._trace, self._event, self._state

    # --- state for the page ----------------------------------------------------------------------------------------
    def status(self):
        s = self.source.status()
        s.update(stopped=self.stopped, queue=len(self.queue), viewers=len(self.clients),
                 cooldown_s=COOLDOWN_S, per_minute=PER_MINUTE, inflight=self.inflight["id"] if self.inflight else None,
                 open=self.open_card["id"] if self.open_card else None, label=LABEL, flat=self.flat)
        if self.stopped:
            s["available"] = False
            s["why"] = "stopped by the operator"
        elif not s.get("available"):
            s["why"] = "the network is not running"
        return s

    def hello(self):
        return {"type": "hello", "status": self.status(), "levels": {str(k): v for k, v in LEVELS_PUBLIC.items()},
                "limits": {"queue": QUEUE_MAX, "cooldown_s": COOLDOWN_S, "per_minute": PER_MINUTE,
                           "client_every_s": CLIENT_EVERY_S, "client_burst": CLIENT_BURST},
                "bins": list(self.bins), "trace": self.last_trace, "events": list(self.events)[-20:],
                "card": self.open_card, "cards": list(self.cards), "label": LABEL,
                "voice": self.speech.status() if self.speech else {"available": False},
                "chat": list(self.chat.log) if self.chat else None}

    # --- requests ----------------------------------------------------------------------------------------------------
    def submit(self, key, level):
        """-> the ack for the sender (state and why); a queued request also becomes a public event."""
        self.stats["submitted"] += 1
        now = self.clock()
        if not isinstance(level, int) or isinstance(level, bool) or not (LEVEL_MIN <= level <= LEVEL_MAX):
            return {"type": "ack", "state": "refused", "why": "level must be a whole number from 1 to 5"}
        if self.stopped:
            return {"type": "ack", "state": "stopped", "why": "the experiment is stopped"}
        if not self.source.status().get("available"):
            return {"type": "ack", "state": "unavailable", "why": "the network is not running"}
        b = self.buckets.get(key)
        if b is None:
            b = self.buckets[key] = Bucket(CLIENT_EVERY_S, CLIENT_BURST, self.clock)
            if len(self.buckets) > 5000:                                   # memory: forget the oldest keys
                for k in list(self.buckets)[:1000]:
                    self.buckets.pop(k, None)
        wait = b.take()
        if wait > 0:
            self.stats["throttled"] += 1
            return {"type": "ack", "state": "throttled", "retry_s": wait, "why": f"one every {CLIENT_EVERY_S:.0f} s per visitor"}
        if len(self.queue) >= QUEUE_MAX:
            self.stats["full"] += 1
            return {"type": "ack", "state": "full", "why": f"{QUEUE_MAX} shocks are already waiting"}
        self.n += 1
        rid = f"c-{self.n}"
        req = {"id": rid, "level": level, "t_wall": int(now * 1000), "key": key}
        self.queue.append(req)
        ev = {"type": "event", "id": rid, "state": "queued", "level": level, "t_wall": req["t_wall"], "pos": len(self.queue)}
        self._note(ev)
        return {"type": "ack", "id": rid, "state": "queued", "pos": len(self.queue), "eta_s": self.eta(len(self.queue))}

    def eta(self, pos):
        gap = max(0.0, COOLDOWN_S - (self.clock() - self.last_delivery))
        return round(gap + (pos - 1) * COOLDOWN_S, 1)

    def _minute_ok(self):
        now = self.clock()
        while self.deliveries and now - self.deliveries[0] > 60.0:
            self.deliveries.popleft()
        return len(self.deliveries) < PER_MINUTE

    async def pump_once(self):
        """One scheduling step: send the next queued request when the source and the cooldown allow it."""
        now = self.clock()
        st = self.source.status()
        if self.clients:
            self.last_viewer = now
            if st.get("available") and not st.get("running") and not self.stopped:
                await self.source.resume()
        elif st.get("running") and now - self.last_viewer > IDLE_PAUSE_S and not self.queue:
            await self.source.pause()
        if self.stopped or not st.get("available") or not st.get("running"):
            if self.queue and (self.stopped or not st.get("available")):
                self._drop_all("stopped" if self.stopped else "unavailable")
            return
        if self.inflight is not None or self.open_card is not None and now - self.last_delivery < COOLDOWN_S:
            return
        if not self.queue or now - self.last_delivery < COOLDOWN_S or not self._minute_ok():
            return
        req = self.queue.popleft()
        req["t_sent"] = now
        if not await self.source.stimulate(req["id"], req["level"]):
            self._note({"type": "event", "id": req["id"], "state": "dropped", "why": "the network did not take it",
                        "t_wall": int(now * 1000)})
            return
        self.inflight = req

    def _drop_all(self, why):
        while self.queue:
            req = self.queue.popleft()
            self._note({"type": "event", "id": req["id"], "state": "dropped", "why": why, "t_wall": int(self.clock() * 1000)})

    async def pump(self):
        while True:
            try:
                await self.pump_once()
                if self.speech:
                    for msg in self.speech.tick(self.clock()):
                        await self._say(msg)
            except Exception as e:
                print("chair: pump error:", repr(e)[:120], flush=True)
            await asyncio.sleep(0.1)

    async def _say(self, msg):
        """A line to say: rendered by the voice provider off the loop when one answers (a reaction waits at most
        SAY_WAIT_S for it, a comment longer), then broadcast with its audio; without a voice, the caption alone."""
        if msg.get("type") == "say" and self.speech and self.speech.voice.available():
            loop = asyncio.get_running_loop()
            wait = SAY_WAIT_S if msg.get("kind") == "reaction" else SAY_WAIT_COMMENT_S
            try:
                audio = await asyncio.wait_for(loop.run_in_executor(None, self.speech.voice.synthesize, msg["text"], msg.get("cls")), wait)
            except (asyncio.TimeoutError, Exception) as e:
                audio = None
                print("chair: voice not ready in time:", repr(e)[:80], flush=True)
            self.speech.voiced(msg, audio, self.clock())
        await self.broadcast(msg)

    async def warm_voice(self):
        """Render the reaction vocabulary ahead when the voice is up (and again after it comes back)."""
        loop = asyncio.get_running_loop()
        while True:
            v = self.speech.voice if self.speech else None
            if v is not None and hasattr(v, "warm") and v.available() and len(getattr(v, "cache", {})) < 12:
                await loop.run_in_executor(None, v.warm)
            await asyncio.sleep(60.0)

    def chat_state(self):
        """The measured state the chat's model call gets: the last cards and the phase, never a feeling."""
        cards = [{k: c.get(k) for k in ("level", "peak_ratio", "burst", "recruit", "recovered_ms", "distinguishable")} for c in list(self.cards)[-3:]]
        return {"phase": (self.last_trace or {}).get("phase"), "last_shocks": cards, "open": bool(self.open_card),
                "source": self.source.status().get("kind"), "flat": self.flat,
                "flatlines": (self.last_trace or {}).get("flatlines"), "revivals": (self.last_trace or {}).get("revivals")}

    async def run_comments(self):
        """The comment or the chat answer the speech module asked for, written off the loop (the mind's metered model
        call); the answer is then said (rendered when a voice answers) and shown to everyone."""
        loop = asyncio.get_running_loop()
        while True:
            job = self.speech.take_comment_job() if self.speech else None
            if job:
                rid, system, user, cls = job
                text = None
                if self.speech.ask:
                    try:
                        text = await loop.run_in_executor(None, self.speech.ask, system, user)
                    except Exception as e:
                        print("chair: comment not written:", repr(e)[:100], flush=True)
                self.speech.finish_comment(rid, text, cls, self.clock())
            cj = self.chat.take_job(self.clock()) if self.chat else None
            if cj:
                mid, system, user = cj
                text = None
                if self.chat.ask:
                    try:
                        text = await loop.run_in_executor(None, self.chat.ask, system, user)
                    except Exception as e:
                        print("chair: answer not written:", repr(e)[:100], flush=True)
                line = self.chat.finish(mid, text, self.clock())
                if line:
                    await self.broadcast(line)
            await asyncio.sleep(0.5)

    # --- from the source ------------------------------------------------------------------------------------------
    async def _event(self, msg):
        kind = msg.get("type")
        now = self.clock()
        if kind == "delivered":
            req = self.inflight if self.inflight and self.inflight["id"] == msg.get("id") else {"id": msg.get("id"), "level": msg.get("level")}
            self.inflight = None
            self.last_delivery = now
            self.deliveries.append(now)
            self.stats["delivered"] += 1
            ev = {"type": "event", "state": "delivered", "t_wall": int(now * 1000),
                  **{k: v for k, v in msg.items() if k != "type"}}
            self.open_card = {"id": ev["id"], "level": ev["level"], "t_ms": ev["t_ms"], "t_wall": ev["t_wall"]}
            self._note(ev)
            if self.on_delivered:
                try:
                    self.on_delivered(ev)
                except Exception as e:
                    print("chair: delivered hook:", repr(e)[:100], flush=True)
            if self.speech:
                self.speech.on_delivered(ev, now)
        elif kind == "measured":
            card = {k: v for k, v in msg.items() if k != "type"}
            self.cards.append(card)
            if self.open_card and self.open_card["id"] == card.get("id"):
                self.open_card = None
            self._note({"type": "event", "state": "measured", "t_wall": int(now * 1000), **card})
            if self.speech:
                self.speech.on_measured(card, now)
        elif kind == "refused":
            self.stats["refused"] += 1
            req, self.inflight = self.inflight, None
            why = msg.get("why")
            if req is not None and why in ("busy", "paused"):                  # not lost: back to the front of the queue
                self.queue.appendleft(req)
            else:
                self._note({"type": "event", "id": msg.get("id"), "state": "refused", "why": why, "t_wall": int(now * 1000)})
        elif kind == "flatline":
            self.flat = True
            self._note({"type": "event", "state": "flatline", "t_wall": int(now * 1000), **{k: v for k, v in msg.items() if k != "type"}})
            if self.speech:
                self.speech.on_flatline(msg, now)
        elif kind == "revived":
            self.flat = False
            self._note({"type": "event", "state": "revived", "t_wall": int(now * 1000), **{k: v for k, v in msg.items() if k != "type"}})
            if self.speech:
                self.speech.on_revived(msg, now)
        elif kind == "reset_done":
            self.flat = False
            self.bins.clear()
            self.cards.clear()
            self.open_card, self.inflight = None, None
            self._note({"type": "event", "state": "reset", "t_wall": int(now * 1000)})

    def _note(self, ev):
        self.events.append(ev)
        asyncio.get_event_loop().create_task(self.broadcast(ev))

    async def _trace(self, msg):
        for b in msg.get("bins", []):
            self.bins.append(b)
        self.last_trace = {k: v for k, v in msg.items() if k != "bins"}
        if self.speech:
            self.speech.on_trace(msg, self.clock())
        await self.broadcast(msg)

    async def _state(self, status):
        await self.broadcast({"type": "status", **self.status()})

    # --- clients ------------------------------------------------------------------------------------------------
    async def broadcast(self, msg):
        if not self.clients:
            return
        data = json.dumps(msg)
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except Exception:
                self.clients.discard(ws)

    async def ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1024, compress=True)
        await ws.prepare(request)
        if len(self.clients) >= MAX_WS:
            try:
                await ws.send_json({"type": "full", "retry": 30})
                await ws.close(code=1013, message=b"full")
            except Exception:
                pass
            return ws
        key = self.key_of(request)
        self.clients.add(ws)
        self.last_viewer = self.clock()
        try:
            await ws.send_json(self.hello())
            await self._viewers()
            async for msg in ws:
                if msg.type != web.WSMsgType.TEXT:
                    continue
                try:
                    d = json.loads(msg.data)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("type") == "shock":
                    await ws.send_json(self.submit(key, d.get("level")))
                elif isinstance(d, dict) and d.get("type") == "chat" and self.chat and isinstance(d.get("text"), str):
                    ack, msg = self.chat.submit(key, d["text"], d.get("via"), self.clock(), self.chat_state())
                    await ws.send_json(ack)
                    if msg:
                        await self.broadcast(msg)
                        if self.on_chat:
                            try:
                                self.on_chat(msg["text"])
                            except Exception as e:
                                print("chair: chat hook:", repr(e)[:80], flush=True)
                elif isinstance(d, dict) and d.get("type") == "status":
                    await ws.send_json({"type": "status", **self.status()})
        finally:
            self.clients.discard(ws)
            await self._viewers()
        return ws

    async def _viewers(self):
        """The viewer count changed: every page shows it (a status message)."""
        await self.broadcast({"type": "status", **self.status()})

    # --- operator ---------------------------------------------------------------------------------------------------
    async def stop(self):
        self.stopped = True
        self._drop_all("stopped")
        await self.source.pause()
        await self.broadcast({"type": "status", **self.status()})

    async def resume(self):
        self.stopped = False
        await self.source.resume()
        await self.broadcast({"type": "status", **self.status()})

    async def reset(self):
        self._drop_all("reset")
        self.inflight, self.open_card = None, None
        await self.source.reset()
        if self.speech:
            self.speech.reset()


def attach(app, hub, page=HERE / "web" / "chair.html", nocache=None):
    """Routes: /chair (the page), /ws/chair, /api/chair/status (public), the operator POSTs (admin token)."""
    nocache = nocache or {"Cache-Control": "no-store"}
    app.router.add_get("/chair", lambda r: web.FileResponse(page, headers=nocache))
    app.router.add_get("/ws/chair", hub.ws_handler)
    async def voice_file(request):             # a rendered line, from the provider's cache (web/chair.html plays it)
        key = request.match_info["key"]
        v = hub.speech.voice if hub.speech else None
        wav = v.audio(key) if (v is not None and hasattr(v, "audio") and key.isalnum()) else None
        if wav is None:
            raise web.HTTPNotFound(text="no such line")
        return web.Response(body=wav, content_type="audio/wav", headers={"Cache-Control": "private, max-age=600"})
    app.router.add_get("/api/chair/voice/{key}.wav", voice_file)
    app.router.add_get("/api/chair/status", lambda r: web.json_response(
        {**hub.status(), "stats": hub.stats, "cards": list(hub.cards)[-5:],
         "chat": hub.chat.stats if hub.chat else None}, headers=nocache))

    def op(fn):
        async def handler(request):
            if not hub.admin_ok(request):
                raise web.HTTPUnauthorized(text="admin token required")
            await fn()
            return web.json_response(hub.status(), headers=nocache)
        return handler
    app.router.add_post("/api/chair/stop", op(hub.stop))
    app.router.add_post("/api/chair/resume", op(hub.resume))
    app.router.add_post("/api/chair/reset", op(hub.reset))
    return hub


# the public view of the levels (the page shows what a level injects; spiking/alif.py owns the numbers)
try:
    from spiking.alif import LEVELS as _LV, PULSE_HZ as _HZ, PULSE_WIDTH_MS as _PW
    LEVELS_PUBLIC = {k: {"amp_mv": v["amp"], "frac": v["frac"], "dur_ms": v["dur_ms"], "pulse_hz": _HZ, "pulse_ms": _PW}
                     for k, v in _LV.items()}
except Exception:                                   # numpy missing (tests of the hub alone)
    LEVELS_PUBLIC = {k: {"dur_ms": 300 + 175 * (k - 1)} for k in range(1, 6)}
