"""Single persistent Linux/x86 computer for SUB-01, isolated inside v86/WebAssembly."""

import asyncio
import json
import os
import random
import shutil
import time
from pathlib import Path

COMMANDS = [
    ("uname -a", "attention"),
    ("ls /", "default"),
    ("date", "salience"),
    ("cat /proc/uptime", "somatomotor"),
    ("free", "attention"),
    ("ls /root", "reward"),
]


class Computer:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.process = None
        self.output = ""
        self.ready = False
        self.paused = False
        self.status = "starting"
        self.last_command = ""
        self.commands = 0
        self.last_agent = 0
        self.error = ""
        self._running = False
        self.input_until = 0.0

    def view(self):
        return {
            "status": self.status,
            "ready": self.ready,
            "output": self.output[-10000:],
            "paused": self.paused,
            "last_command": self.last_command,
            "commands": self.commands,
            "os": "Buildroot Linux / x86",
            "error": self.error,
        }

    async def send(self, message):
        if not self.process or self.process.returncode is not None:
            return False
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        try:
            await asyncio.wait_for(self.process.stdin.drain(), 0.05)
            return True
        except (asyncio.TimeoutError, BrokenPipeError, ConnectionResetError):
            self.status = "offline"
            self.ready = False
            return False

    async def input(self, text):
        if not self.ready:
            return False
        self.input_until = time.monotonic() + 5
        self.paused = False
        return await self.send({"type": "input", "text": text})

    async def agent_step(self, home, rel):
        using = home.activity == "use_computer" and not home.path
        if (
            not using
            and self.ready
            and not self.paused
            and time.monotonic() > self.input_until
        ):
            if await self.send({"type": "pause"}):
                self.paused = True
        if using and self.ready:
            if self.paused:
                await self.send({"type": "resume"})
                self.paused = False
            if time.monotonic() - self.last_agent > 18:
                weights = [max(0.05, float(rel.get(group, 1))) for _, group in COMMANDS]
                command = random.choices(COMMANDS, weights=weights)[0][0]
                if await self.input(command + "\n"):
                    self.last_command = command
                    self.commands += 1
                    self.last_agent = time.monotonic()
                    home.memories.append(
                        {
                            "at": round(home.time, 1),
                            "activity": "use_computer",
                            "command": command,
                        }
                    )
                    home.memories = home.memories[-100:]

    async def run(self):
        node = shutil.which("node")
        if not node:
            self.status = "unavailable"
            self.error = "Node.js is not installed"
            return
        from computer.bootstrap import ensure

        self.status = "preparing"
        try:
            assets = await asyncio.to_thread(ensure, self.data_dir / "computer-assets")
        except Exception:
            self.status = "unavailable"
            self.error = "Pinned Linux guest could not be prepared"
            raise
        env = {k: os.environ[k] for k in ("PATH", "LANG", "TZ") if k in os.environ}
        env["SUB01_VM_ASSETS"] = str(assets)
        env["SUB01_VM_STATE"] = str(self.data_dir / "computer.bin")
        self.process = await asyncio.create_subprocess_exec(
            node,
            "--max-old-space-size=192",
            str(Path(__file__).parent / "computer/worker.cjs"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        self._running = True
        try:
            async for line in self.process.stdout:
                try:
                    m = json.loads(line)
                except ValueError:
                    continue
                if m.get("type") == "terminal":
                    self.output = str(m.get("output", ""))[-12000:]
                    self.ready = bool(m.get("ready"))
                    self.paused = bool(m.get("paused"))
                    self.status = "ready" if self.ready else "booting"
                elif m.get("type") == "error":
                    self.error = str(m.get("message", ""))[:160]
            self.status = "offline"
            self.ready = False
        finally:
            self._running = False
            if self.process.returncode is None:
                await self.send({"type": "shutdown"})
                try:
                    await asyncio.wait_for(self.process.wait(), 5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()
