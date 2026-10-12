# SUB-01’s emulated computer

A single server-owned v86/WebAssembly x86 machine runs Buildroot Linux. It has 64 MB guest RAM and 2 MB VGA RAM. There is no host filesystem mount, guest network adapter, or bridge to a host shell. Viewers read its terminal; only the authenticated operator can type. SUB-01 selects bounded guest commands using live cortical group signals. This is an initial computer agent, not a general autonomous operating-system user.

The guest filesystem survives through an atomic machine-state snapshot in the persistent data volume. Idle CPU execution pauses; snapshots are written once per minute and on a graceful stop. Corrupt/incompatible snapshots report an error and fall back to a fresh boot.

## Upstream software and source

- v86: https://github.com/copy/v86 — BSD 2-Clause, see `V86-LICENSE`. Distribution: https://copy.sh/v86/build/libv86.js and https://copy.sh/v86/build/v86.wasm.
- SeaBIOS / VGA BIOS: binaries distributed by v86 at https://copy.sh/v86/bios/seabios.bin and https://copy.sh/v86/bios/vgabios.bin. Corresponding source/build: https://github.com/copy/v86/tree/master/bios and https://www.seabios.org/ . SeaBIOS is LGPLv3; see `BIOS-LICENSE` and the upstream BIOS build script.
- Linux/Buildroot demo image: https://i.copy.sh/buildroot-bzimage.bin . The kernel is Linux 5.6.15 (GPLv2); userspace includes BusyBox. The v86 Buildroot integration/build instructions are at https://github.com/copy/v86/tree/master/tools . Upstream Linux source: https://www.kernel.org/pub/linux/kernel/v5.x/linux-5.6.15.tar.xz . Buildroot: https://buildroot.org/ . These components retain their upstream licenses.

The demo image is a minimal serial-console guest, not a browser or a desktop Linux distribution. The house’s browser comes from SUB-01’s separate, existing browsing service.

Guest BIOS/kernel binaries are not stored in the source repository. `bootstrap.py` downloads the pinned official artifacts and verifies their sizes and SHA-256 hashes, during the private container build or into the server's persistent cache for local development. The shared web UI transmits the terminal display, not the guest system image.
