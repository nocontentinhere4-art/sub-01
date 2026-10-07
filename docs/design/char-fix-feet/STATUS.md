# char-fix-feet (G19): STATUS

**State: in progress** (branch `preview/char-fix-feet`, off main 92395c7).

Task: v5's feet -> white socks in black slides, transplanted from the owner's Tripo reference
(preview/char-owner-tripo), as a deterministic script `room_build/charfix/feet.mjs` (in GLB -> out GLB, feet/ankles only)
that G10d can run after its collar script.

## Done so far
- `room_build/charfix/ref_feet.mjs`: the reference cut to its feet (49,493 tris under 16 cm, 15 texture charts packed
  in a 2048² atlas) -> `room_build/charfix/ref_feet.glb` (1.4 MB, committed; deterministic).
- `room_build/charfix/feet.mjs`: working end to end on web/room/char_v5.glb (deterministic: two runs, same md5).
  Slides closed (0 open edges), socks open only at the top (inside the trouser cuff).
- `room_build/charfix/probe.py` + `feet_probe.js`: in-page measurements (soles over the floor per frame, sock-in-slide,
  seam/tube gap, the bed mechanism) and close-ups.

## Next
- page probe before/after, render sheet, numbers, full pytest.
