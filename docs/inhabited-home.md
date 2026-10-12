# Inhabited first-person home

This adds a live home to the existing SUB-01 brain server. `HOME_ENABLED=1` activates it at `/` and `/house`; `/room-classic` remains available. The default stays disabled until the visual and production checks are complete. `HOME_ENTRYPOINT=0` keeps the legacy front page while the live home can be checked at `/house` on the same brain server.

The same server owns his activity, position, PC, Pong game, phone notes and journal. Watching the home does not create another brain, browser, operating system or game. Follow mode receives a compact 5 Hz state feed, interpolated by the renderer. Explore mode moves a visitor camera without moving SUB-01. Bathroom occupancy replaces the entire render with a privacy scene, including while a spectator explores elsewhere.

## Rooms and movement

A two-level home contains office, kitchen, living area, wooden staircase, bedroom, bathroom, balcony and an opening front door with an entrance terrace. Continuous waypoints map his existing needs and brain-guided activity selection into the house. New gated activities are Linux computer use, wall-TV Pong and a bathroom break. An optional operator intent is a nudge under the same needs/sleep rules, never a forced brain verdict.

## Devices

- PC: an actual shared v86 x86 Linux guest (see `computer/NOTICE.md`), and the existing guarded real-browser screen. Files persist in a VM snapshot. The initial computer agent chooses from bounded guest commands; it cannot yet use arbitrary desktop applications.
- TV: shared server physics for Pong, plus a view of the existing brain-voted live chess game. His motor and attention groups affect the left controller; scoring feeds simulated reward/salience back into the brain. This controller is not evidence of comprehension or consciousness. A viewer can challenge the right paddle with bounded inputs.
- Phone: clock, activity journal, notes, messages/brain impulses, existing guarded browser, and a view of the existing music selection. These are functional web apps, not an emulated mobile OS.

`SUB01_ADMIN_TOKEN` protects terminal input, notes, lamp/curtain settings and operator intents. Public Pong input is rate limited and finite/bounded. No production secrets enter the emulator, public state or browser assets. `home.json` and `computer.bin` live in the existing persistent data directory. Node.js is added to the container for the VM.

## Materials and performance

Asset source/license/hash metadata is in `web/house/assets/manifest.json`. Scanned Poly Haven CC0 furniture and 1K PBR materials replace procedural lounge furniture and flat surfaces. Two diffuse maps have neutral colour variants; geometry remains original or CC0. Three.js includes its MIT license. The room is a single WebGL scene, with one cached shadow map, an actual indoor HDR lighting capture, 512px prebuilt mobile variants, a small prefiltered environment, instanced skyline and a capped pixel budget. Fixed architecture is batched by compatible materials/attributes. This is an improvement toward the X reference; matching its Unreal architectural rendering remains an open visual target.

## Verification

`python -m pytest tests/test_home_world.py -q` checks every waypoint edge against rendered furniture/wall colliders, all node-to-node routes, continuous movement/replanning, bathroom privacy, new activity selection and persistence. `python tools/check_home_vm.py` boots the real guest, writes a file, saves/restores and verifies it after restart. Browser checks must cover desktop and phones, PC, Pong, notes, impulses, stairs, bathroom entry/exit and performance after all assets load.

Baseline main at the start of this branch has unrelated failing tests. A full local run returned 1842 passed, 64 skipped, 9 failed. Six of those failures were reproduced with the original `live_server.py`, `life.py` and Dockerfile restored (legacy desk-rule, audience/decider, sleep replay, dated neurogenesis expectation and GPU label). Two clip failures are macOS subprocess resource-limit errors; the remaining spiking websocket test reset its connection. They must not be represented as a green full suite.

## Offline contact lighting

The `/house` rollout on the existing Railway service was checked on October 12: live brain feed, wall-TV Pong, real Linux boot, authenticated guest commands and the real browser screen are working. The production root remains the legacy room. Operator editing requires the privately configured admin credential. Photographic Tokyo window layers reuse the existing room's public-domain/CC0 assets and credits, sharing textures and disabling reflection-probe renders. Windows, scanned cushions and a desk lamp include 512px phone variants. A live spiking growth crash was traced to missing source IDs in formed-synapse CSR data; preserving those IDs lets growth re-address the connections and finish resizing state. The new regression checks two growth steps with formed connections and a runnable network afterward. The other spiking tests returned 13 passed, 1 skipped and the pre-existing GPU-label assertion failure.

A CPU ray-traced contact-occlusion atlas adds depth to fixed architecture without a post-processing pass. The geometry atlas is about 4 MB; its approximately 1 megapixel grayscale JPEG uses about 4 MB of GPU memory (a 512px mobile variant is prebuilt). Dynamic doors and devices keep their original geometry. Matching world bounds reject outdated baked parts. The fallback remains usable if the optional atlas fails.

To rebuild, export the house with the local-only `?bake=1` button, rename `out/home-bake-source.png` to `.glb`, and install `xatlas`, `pygltflib`, `numpy` plus the npm packages `three@0.180.0` and `three-mesh-bvh@0.9.2` in a tooling directory. Run `prepare_home_lightmap.py SOURCE.glb web/house/assets/lighting/architecture.glb`, then `HOME_BAKE_MODULES=/path/to/tooling node tools/bake_home_contact.mjs web/house/assets/lighting/architecture.glb`. Convert its PGM to the full/lite JPEGs with Pillow. The export filename is only an accommodation for the existing local snapshot helper; it contains GLB bytes. This is ambient contact lighting, not a claim of full global illumination or Unreal quality.
