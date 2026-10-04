# SUB-01 launch film for X

`sub01_x_launch.mp4`: 31 s, 1080×1080 (square fills the most of the X mobile feed), H.264 + AAC, 30 fps, ~10 MB.
Kinetic typography in the style of a product launch film; all images are the repo's own renders (`docs/readme/`,
`out/x_logo.png`). It reads without sound (X autoplays muted); the soundtrack is a synthesised heartbeat and drone
on a 0.6 s grid, every cut on a beat, near silence under "It's a model. Not a mind."

Rebuild: `node render.js` (Playwright + Chromium seek each frame of `storyboard.html`, `soundtrack.py` makes the
audio, ffmpeg encodes). Edit copy or timing in `storyboard.html` (`S` holds the scene times).

Wording follows the project rules: no mind, feeling or consciousness claims, no price talk, the scanned person and
the dataset are not named, "AI · fictional character · simulated brain" in the corner for the whole clip.
Numbers: 214 regions, 923,135 fibres (shown as 923,000), 1M spiking neurons (README), sleep 23:56 → 07:54 Tokyo.

## Post copy (draft)

> We turned one public MRI scan into a brain model that never switches off.
>
> It drives a fictional guy in a tiny room in Tokyo: it sleeps when its sleep–wake circuit says so, reads the web,
> and replays the day in REM.
>
> It's a model, not a mind. Watch it live soon.
>
> #AI #AIgenerated #neuroscience #Tokyo

Alternative hook for the first line: "This guy's every click is voted on by a simulated brain."
