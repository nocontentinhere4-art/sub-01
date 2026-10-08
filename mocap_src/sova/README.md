# SovaSims - Phone Animations (Sims 4 pose pack, Ver. 8): evaluation source only

Given to us by the owner on 2026-10-08. A Sims 4 `.package` (DBPF 2.1) with 46 animation clips (CLIP 0x6B20C4F3,
S3 clips `_pilC3S_`, 30 fps, 200-1401 frames) on the Sims 4 skeleton (`b__ROOT__`, `b__Spine0__`, ...), 47 DDS icons,
18 string tables (English names below) and one Pose Player snippet.

**Licence: unknown.** We have not found SovaSims' terms. Many Sims animators forbid converting their animations to other
projects. Until the owner confirms that the author allows it, this is an evaluation: nothing derived from it goes into
`web/`, onto main or online. This branch is never merged.

Clips of interest (set index -> English name):
- in bed: set_11 IN BED 01 - IDLE, set_12 IN BED 01 - TALK VER. A, set_13 IN BED 01 - TALK VER. B,
  set_14 IN BED 02 - IDLE, set_15 IN BED 02 - TALK, set_4 IN BED 03 - VER. A, set_5 IN BED 03 - VER. B
- watching videos: WATCHING A VIDEO VER. A/B - LANDSCAPE/PORTRAIT
- couch / sitting: ON THE COUCH - READING / TYPING / THINKING; TEXTING; TYPING

Names are in the English string table (`python3 -I inspect_dbpf.py <package>` prints the index and frame counts;
the name<->set map is given by the pose_display_name keys in the snippet 0x7DF2169C and the STBL keys).
