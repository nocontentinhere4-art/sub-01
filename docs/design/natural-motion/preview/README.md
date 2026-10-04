# Preview: living idles (#134), main and this branch

`idles_preview.mp4` — 83 s, 1280 × 720, 30 fps, H.264 (6 MB), for the owner's visual OK.

| | left: main (before) | right: this branch (after) |
|---|---|---|
| top | the default camera | the default camera |
| bottom | a close camera | the same close camera |

Each idle is made to play once, in turn, and named while it plays:
- **At the desk:** sip from the bottle, lean back with his hands behind his head, a glance out of the window, a phone
  check, a neck and shoulder roll, an eye rub, a head scratch, a shift in the chair.
- **At the window (15 s):** chin on his hand, a stretch.
- **In bed with the phone (15 s):** the phone down on his chest, a look away.

On main the same idle plays where it exists. Where main has none (the window glance, the neck roll, the eye rub, the
phone down), the left side shows what main does instead. Live, the actions come every 25–75 s, chosen by how tired
and bored he is, with small fidgets between them; here they are back to back so the video stays short.

How it was made (`tools/`): headless Chromium with software WebGL. The page runs in `?debug&nolive`, its own loop frozen,
and is stepped one 1/30 s frame at a time by its own clock (`sim(1/30)`, #114's motion layer included). That is why it
is smooth at 30 fps although software GL draws about one frame a second. Frames are drawn at half resolution (640 × 360
per view) and put together by `make_video.py`:

    node tools/preview.mjs <port> default|close <frames dir>   (one per view: main on one port, this branch on another)
    python tools/make_video.py <dir holding pv_main_default, pv_new_default, pv_main_close, pv_new_close> out.mp4

The scenes and cameras are in `tools/timeline.json`. Each place (desk, window, bed) starts with a cut.
