"""Boot the actual emulator, create a file, restart, and verify it survived.
Run manually; no production credentials, host mount, or guest network.
"""

import asyncio, json, os, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


async def run(snapshot, command, needle):
    env = {k: os.environ[k] for k in ("PATH", "LANG") if k in os.environ}
    from computer.bootstrap import ensure

    env["SUB01_VM_ASSETS"] = str(
        await asyncio.to_thread(ensure, snapshot.parent / "guest")
    )
    env["SUB01_VM_STATE"] = str(snapshot)
    p = await asyncio.create_subprocess_exec(
        "node",
        str(ROOT / "computer/worker.cjs"),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    async def send(text):
        p.stdin.write((json.dumps(text) + "\n").encode())
        await p.stdin.drain()

    try:
        ready = False
        for _ in range(45):
            m = json.loads(await asyncio.wait_for(p.stdout.readline(), 10))
            if m.get("ready") and not ready:
                await send({"type": "input", "text": command + "\n"})
                ready = True
            if needle in m.get("output", ""):
                await send({"type": "shutdown"})
                await asyncio.wait_for(p.wait(), 15)
                assert p.returncode == 0
                return
        raise AssertionError("Guest did not return expected output")
    finally:
        if p.returncode is None:
            p.terminate()
            await p.wait()


async def main():
    with tempfile.TemporaryDirectory(prefix="sub01-vm-check-") as temp:
        snapshot = Path(temp) / "computer.bin"
        await run(
            snapshot,
            "echo home-persisted > /root/test; cat /root/test",
            "home-persisted\r\n",
        )
        assert snapshot.stat().st_size > 1000000
        await run(snapshot, "cat /root/test", "home-persisted\r\n")
        print(
            "PASS: actual Linux boot, file write, VM save/restore, persisted file read"
        )


if __name__ == "__main__":
    asyncio.run(main())
