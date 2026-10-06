# Mixamo source clips (working files, not a deliverable)

Real motion capture from Mixamo (Adobe), downloaded by the owner from his own free Adobe
account and handed to us as build input. They live here only so the retarget pipeline can
read them; they are **not** part of what the site serves.

## Licence

Mixamo characters and animations are free and royalty-free for use in commercial and
non-commercial projects. The one restriction that matters to us: **the raw files may not be
redistributed as standalone assets** — no asset packs, no templates, no publishing these
`.fbx` files as a product. Incorporating the motion into our own project, retargeted onto our
own character, is exactly the permitted use.

So: these files stay inside this private repository as build input. Nothing under this
directory is ever served by the web app, copied into `web/`, or published anywhere.

Reference: <https://community.adobe.com/t5/mixamo-discussions/mixamo-faq-licensing-royalties-ownership-eula-and-tos/m-p/13234775>

## What is here

All five are FBX Binary, Without Skin, 30 fps, no keyframe reduction, on the standard Mixamo
skeleton: 66 joints named `mixamorig:*`, including the full finger chains
(`...HandIndex1..4`, `Middle`, `Ring`, `Pinky`, `Thumb`). Those finger chains are the reason
these are worth more to us than the Kimodo takes, which carried no fingers at all.

| file | what it is | where it goes in the room |
|---|---|---|
| `Sitting.fbx` | seated, settled | desk, base seated pose |
| `Sitting_1.fbx` | seated, a second reading | desk, variation so the seat does not loop visibly |
| `Seated_Idle.fbx` | seated idle | desk, the idle under everything else |
| `Scared.fbx` | startle | rare moment at the computer — something outside, a jolt, as if the building moved |
| `Angry_Gesture.fbx` | frustration | rare moment at the computer — something he is working on goes wrong |
| `Stand_To_Sit.fbx` | lowering into the chair | arriving at the desk |
| `Sit_To_Stand.fbx` | rising out of the chair | leaving the desk |
| `Sit_To_Type.fbx` | hands coming up to the keyboard | entering the typing pose |
| `Typing.fbx` | typing | the working pose itself |
| `Type_To_Sit.fbx` | hands coming back down | leaving the typing pose |
| `Standing_Clap.fbx` | celebrating | rare moment — something at the computer goes brilliantly |
| `Sitting_Rubbing_Arm.fbx` | rubbing an arm | small seated idle, breaks the loop |
| `Sitting_Talking.fbx` | talking with the hands | small seated idle, breaks the loop |
| `Sleeping_Idle.fbx` | asleep, breathing | the bed, replacing the flat pose |
| `Laying_Sleeping.fbx` | asleep, a second reading | the bed, variation |
| `Laying_Nodding.fbx` | head moving while lying down | the bed, awake with music |

The transition takes replace the two the owner called out as broken — standing up and sitting
down — and give us the way in and out of typing, which we never had: until now the hands
arrived at the keyboard by teleporting there.

`Standing_Clap` is performed standing, and he is seated at the computer. It is played as a
chain — `Sit_To_Stand` → `Standing_Clap` → `Stand_To_Sit` — so he comes up out of the chair to
celebrate and settles back down. Grafting a standing upper body onto a seated base is what
produced the stitched-together poses we have already thrown away once; all three parts here
are real captures, so the chain costs us nothing and reads as one motion.

The last two are deliberately rare: they are punctuation, not behaviour. They play once in a
long while and never twice near each other.

## Known defect to fix in the retarget

In some of these clips **the hands pass into the thighs.** Mixamo poses them against its own
body proportions, which are not ours; on our character the arms end up inside the legs. A
retargeted clip is not finished until the hands clear the legs through the whole clip, not at
one sampled frame. Treat it the same way as furniture contact: measure it over time, per
region, and report the number.
