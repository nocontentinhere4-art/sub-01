#!/bin/bash
# reference sheets: real photos (refs/) next to frames of the final renders (both cameras), per clip
# usage: make_refsheets.sh <renders_dir> <refs_dir> <out_dir>
R=$1; F=$2; O=$3; T=$(mktemp -d); mkdir -p $O
grab(){ # clip time -> $T/<clip>_<time>_c0.jpg, _c1.jpg
  ffmpeg -y -loglevel error -ss $2 -i $R/$1.mp4 -vframes 1 $T/f.png
  python3 -c "
from PIL import Image; im=Image.open('$T/f.png'); w=im.width//2
im.crop((0,0,w,im.height)).save('$T/$1_$2_c0.jpg'); im.crop((w,0,2*w,im.height)).save('$T/$1_$2_c1.jpg')"; }
sheet(){ python3 $(dirname $0)/refsheet.py "$@"; }
grab b_type 4; grab b_type 12
sheet $O/b_type_refs.jpg "(b) typing: real references (Pexels) vs our frames" "$F/typing_1.jpg|Reference, side|$T/b_type_4_c1.jpg|Ours t=4 s, camera 2|$T/b_type_12_c1.jpg|Ours t=12 s (mouse), camera 2" "$F/typing_2.jpg|Reference, 3/4 rear|$T/b_type_4_c0.jpg|Ours t=4 s, camera 1|$T/b_type_12_c0.jpg|Ours t=12 s, camera 1"
grab c_read 3; grab c_read 6.2
sheet $O/c_read_refs.jpg "(c) reading at the desk: real references (Pexels) vs our frames" "$F/reading_1.jpg|Reference, side|$T/c_read_3_c1.jpg|Ours t=3 s, camera 2|$T/c_read_6.2_c1.jpg|Ours t=6.2 s (page turn), camera 2" "$F/reading_2.jpg|Reference, 3/4 front|$T/c_read_3_c0.jpg|Ours t=3 s, camera 1|$T/c_read_6.2_c0.jpg|Ours t=6.2 s, camera 1"
grab d_phone 3; grab d_phone 9
sheet $O/d_phone_refs.jpg "(d) phone in the chair: real references (Pexels) vs our frames" "$F/phone_1.jpg|Reference, 3/4|$T/d_phone_3_c1.jpg|Ours t=3 s, camera 2|$T/d_phone_9_c1.jpg|Ours t=9 s, camera 2" "$F/phone_2.jpg|Reference, 3/4 front|$T/d_phone_3_c0.jpg|Ours t=3 s, camera 1|$T/d_phone_9_c0.jpg|Ours t=9 s, camera 1"
grab e_getup 2; grab e_getup 7.5
sheet $O/e_getup_refs.jpg "(e) stretch in the chair, get up: real references (Pexels) vs our frames" "$F/stretching_1.jpg|Reference, 3/4 side|$T/e_getup_2_c0.jpg|Ours t=2 s (stretch), camera 1|$T/e_getup_2_c1.jpg|Ours t=2 s, camera 2" "$F/stretching_2.jpg|Reference, front|$T/e_getup_7.5_c0.jpg|Ours t=7.5 s (up), camera 1|$T/e_getup_7.5_c1.jpg|Ours t=7.5 s, camera 2"
grab f_bed 6.2; grab f_bed 10.8
sheet $O/f_bed_refs.jpg "(f) to bed, lie down: real references (Pexels) vs our frames" "$F/lying_1.jpg|Reference, side|$T/f_bed_10.8_c1.jpg|Ours t=10.8 s, camera 2|$T/f_bed_10.8_c0.jpg|Ours t=10.8 s, camera 1" "$F/getting_up_2.jpg|Reference, on the edge|$T/f_bed_6.2_c1.jpg|Ours t=6.2 s (on the edge), camera 2|$T/f_bed_6.2_c0.jpg|Ours t=6.2 s, camera 1"
grab g_wake 1; grab g_wake 6.3
sheet $O/g_wake_refs.jpg "(g) wake up, get up: real references (Pexels) vs our frames" "$F/lying_2.jpg|Reference, lying|$T/g_wake_1_c1.jpg|Ours t=1 s, camera 2|$T/g_wake_1_c0.jpg|Ours t=1 s, camera 1" "$F/getting_up_1.jpg|Reference, edge of the bed|$T/g_wake_6.3_c1.jpg|Ours t=6.3 s, camera 2|$T/g_wake_6.3_c0.jpg|Ours t=6.3 s, camera 1"
grab a_walkin 11.9
sheet $O/a_walkin_refs.jpg "(a) walk in, sit at the desk: the final seated pose vs a real reference (Pexels)" "$F/typing_2.jpg|Reference, 3/4 rear|$T/a_walkin_11.9_c1.jpg|Ours t=11.9 s, camera 2|$T/a_walkin_11.9_c0.jpg|Ours t=11.9 s, camera 1"
rm -rf $T
