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
| `Texting.fbx` | on the phone | his phone sessions — most of his shorts are watched on it |
| `Texting_While_Standing.fbx` | on the phone, standing | on his feet by the window or the door |
| `Standing_Using_Touchscreen_Tablet.fbx` | holding a flat screen, standing | a larger screen held in both hands |
| `Gaming.fbx` | holding a controller | the gamepad that is already on his desk |

The posture of the three phone takes (seated, standing, how the arms are held) is whatever
Mixamo captured, not what their names imply. Confirm each on retarget before deciding which of
his phone moments it belongs to.

## Deliberately not here

`Laying Hand Gesture` — the owner looked at it and rejected it. He had asked for the hands to
move while he lies in bed, and this is the clip for it, but he did not like the performance. So
the bed carries head motion and breathing and no hand gesture, by his decision. Do not add it,
and do not hand-animate a replacement: invented hand motion is the thing this whole set exists
to get rid of. If the hands read as dead once the bed clips are retargeted, that is a question
for him, not something to paper over.

The transition takes replace the two the owner called out as broken — standing up and sitting
down — and give us the way in and out of typing, which we never had: until now the hands
arrived at the keyboard by teleporting there.

The three punctuation clips are played **whole**, and the chair moves instead of the performance.
Measured rather than read from their names (G12): `Standing_Clap` starts and ends seated and
contains its own rise and sit-down; `Scared` is a seated startle that jumps up and sits back;
`Angry_Gesture` stays seated with the feet 0.6 m in front of the hips. An earlier note here said
`Standing_Clap` would play as `Sit_To_Stand` → `Standing_Clap` → `Stand_To_Sit` — that was decided
from the name and would have stood him up twice. Before each of the three, the page rolls the
chair back by a distance derived from that clip's own reach, and rolls it in once he is seated.

The three phone takes are all **standing** (`Texting` included, despite its name), and `Gaming` is
seated with the controller over his lap. None of them is lying down, so the phone in bed — where
he watches most of his shorts — has no capture yet.

The last two are deliberately rare: they are punctuation, not behaviour. They play once in a
long while and never twice near each other.

## Known defect to fix in the retarget

In some of these clips **the hands pass into the thighs.** Mixamo poses them against its own
body proportions, which are not ours; on our character the arms end up inside the legs. A
retargeted clip is not finished until the hands clear the legs through the whole clip, not at
one sampled frame. Treat it the same way as furniture contact: measure it over time, per
region, and report the number.
