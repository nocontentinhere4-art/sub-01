"""The bed fit's bone names on either rig (G17): the fit (bed_clip.py, bed_turn.py) speaks v5's names; a Mixamo-rigged
character (the owner's v5 through Mixamo's auto-rigger: mixamorig* bones, kept as they are, three.js drops the colon) is
read through this map. Bones v5 has and Mixamo has not (Pelvis, NeckTwist02, the twist bones) are simply absent there.
canon(name) -> the v5 name the fit uses (or the name itself); rename(d) renames an exp.mjs json's nodes in place and
returns the original names (to write the clip back under them)."""
import re

MIX2V5 = {'Hips': 'Hip', 'Spine': 'Waist', 'Spine1': 'Spine01', 'Spine2': 'Spine02', 'Neck': 'NeckTwist01', 'Head': 'Head', 'HeadTop_End': 'head_end'}
for S, s in (('Left', 'L'), ('Right', 'R')):
    MIX2V5.update({f'{S}Shoulder': f'{s}_Clavicle', f'{S}Arm': f'{s}_Upperarm', f'{S}ForeArm': f'{s}_Forearm', f'{S}Hand': f'{s}_Hand',
                   f'{S}UpLeg': f'{s}_Thigh', f'{S}Leg': f'{s}_Calf', f'{S}Foot': f'{s}_Foot', f'{S}ToeBase': f'{s}_ToeBase', f'{S}Toe_End': f'{s}_ToeEnd'})
    for i, f in enumerate(('Thumb', 'Index', 'Middle', 'Ring', 'Pinky')):
        for j in range(1, 5): MIX2V5[f'{S}Hand{f}{j}'] = f'finger{i + 1}-{j}.{s}'


def strip(n):
    return re.sub(r'^mixamorig\d*:?', '', n)


def is_mixamo(names):
    return any(re.match(r'^mixamorig\d*:?Hips$', n) for n in names)


def canon(n):
    return MIX2V5.get(strip(n), n) if n.startswith('mixamorig') else n


def rename(d):
    orig = [n['name'] for n in d['nodes']]
    for n in d['nodes']: n['name'] = canon(n['name'])
    return orig
