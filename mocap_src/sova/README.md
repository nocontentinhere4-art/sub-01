# SovaSims animations (Sims 4 `.package`): source for the animation work, private, never on main

The owner downloaded these from SovaSims' Patreon (https://www.patreon.com/cw/SOVASIMS) on 2026-10-08 and gave them
to us to bring onto our character. `manifest.json` lists each original file's post, size and SHA-256.

**Licence:** SovaSims' public terms forbid converting the animations to other games and redistributing them without
permission. The owner has said he deals with the author himself. Until he confirms the author's OK, they stay on this
private branch: nothing goes into `web/`, onto main or online, and the files are never shared outside this repository.

## Format
DBPF 2.1; animations are CLIP resources (0x6B20C4F3) with an S3 clip (`_pilC3S_`, 30 fps) on the Sims 4 skeleton
(`b__ROOT__`, `b__Spine0__`, ...). `python3 -I inspect_dbpf.py <package>` prints the index and frame counts;
`CLIP_NAMES.txt` lists the English names per package (string-table order, not clip order: map names to clips via
the pose_display_name keys in the snippet 0x7DF2169C).

## What is here (only clips with one actor are usable: a "SIM A / SIM B" pair is a two-person scene)
| file | useful single-actor clips |
|---|---|
| Sova_Sitting_Animations.package (V6) | DESK - START 01, DESK - LOOK BEHIND, Neutral/Bored/Sad/Upset [1-6], Listen/Talking Front/Left/Right, LOOK LEFT/RIGHT, Sit Down, Standing Up |
| Sova_Sitting_Animations_2.0.package | UPSET idle/talk V1-V3 (skip the wine clips) |
| Sova_Action_Reactions_Animations.package | MOCAP looking around/left/right/away, neck stretching, searching pockets, thinking (chin), laugh sit, frustrated V1/V2, anxious, distracted then smile, mood change, confused |
| Sova_Idle_p_Talking_Animations.package | neutral/annoyed/confused/worried/nervous/frustrated idle + talk, shake head, look down/front (skip FLIRTY) |
| Sova_MOCAP_Talking_Animations.package | neutral, smiling, bored, serious, happy, upset, angry, bashful (real motion capture) |
| Sova_Phone_Animations.package (V12) | IN BED 01-04, WATCHING A VIDEO A/B, ON THE COUCH reading/typing/thinking, TEXTING, TYPING, RECEIVE TEXT, READING MESSAGE |
| Sova_Bed_Animations.package (V3) | sitting on bed, looking down/left/right (the Movie / Lap clips are two-person) |
| Sova_Animation_Pack_7.package | sleeping idle; waking up and sleeping again; waking up and leaving the bed |
| Sova_Turn_Animations.package | right turn neutral/confused/sad/upset/surprised |
| Sova_SAD_Animations.package | HEARTBROKEN - SITTING idle/talk only (the rest is two-person) |
| SovaSims_Machinima_single_clothed.package | subset of the WickedWhims Machinima set written by `filter_ww.py`: door knocking/opening/coming in, sitting and lying on bed, sleeping loops. The original package is not in the repository: it also has two-person romance and undressed scenes. |

Not brought in: Looking, Walking and Personal (two-person scenes only), Office (clipboard gestures, nothing for the desk).
