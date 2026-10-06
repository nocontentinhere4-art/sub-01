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

The last two are deliberately rare: they are punctuation, not behaviour. They play once in a
long while and never twice near each other.

## Known defect to fix in the retarget

In some of these clips **the hands pass into the thighs.** Mixamo poses them against its own
body proportions, which are not ours; on our character the arms end up inside the legs. A
retargeted clip is not finished until the hands clear the legs through the whole clip, not at
one sampled frame. Treat it the same way as furniture contact: measure it over time, per
region, and report the number.
