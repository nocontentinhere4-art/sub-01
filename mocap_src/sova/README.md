# SovaSims - Phone Animations (Sims 4 pose pack, Ver. 8): evaluation source only

Given to us by the owner on 2026-10-08. A Sims 4 `.package` (DBPF 2.1) with 46 animation clips (CLIP 0x6B20C4F3,
S3 clips `_pilC3S_`, 30 fps, 200-1401 frames) on the Sims 4 skeleton (`b__ROOT__`, `b__Spine0__`, ...), 47 DDS icons,
18 string tables (English names below) and one Pose Player snippet.

**Licence:** the owner downloaded these from the author's Patreon and told us to go ahead (2026-10-08). The terms are not in the
package; this branch is still never merged, and what derives from it goes into `web/` only through the usual review.

Clips of interest (set index -> English name):
- in bed: set_11 IN BED 01 - IDLE, set_12 IN BED 01 - TALK VER. A, set_13 IN BED 01 - TALK VER. B,
  set_14 IN BED 02 - IDLE, set_15 IN BED 02 - TALK, set_4 IN BED 03 - VER. A, set_5 IN BED 03 - VER. B
- watching videos: WATCHING A VIDEO VER. A/B - LANDSCAPE/PORTRAIT
- couch / sitting: ON THE COUCH - READING / TYPING / THINKING; TEXTING; TYPING

Names are in the English string table (`python3 -I inspect_dbpf.py <package>` prints the index and frame counts;
the name<->set map is given by the pose_display_name keys in the snippet 0x7DF2169C and the STBL keys).

## SovaSims_Machinima_single_clothed.package

A subset of the owner's `WW_SOVASIMS_Machinima_Animations.package` (a WickedWhims set), written by `filter_ww.py`:
only the single-actor, fully clothed, non-romantic clips are kept. The original package is **not** in the repository,
because it also contains two-actor romance and partly undressed scenes, which have no place in this project.

Kept (each with its small companion clip, the door or bed object): Knocking On Door, Knock and Open,
Getting In V1 / V3 / V4 (coming in through the door), SITTING and LYING ON BED, SLEEPING LOOP V1,
SLEEPING LOOP V1 TO V2, SLEEPING LOOP V2. ("Getting In Sad" is listed in the set, but its clips are not in the package.)
