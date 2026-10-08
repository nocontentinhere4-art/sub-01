"""Pose-pack icons (DST5 = Sims' shuffled DXT5) -> PNG: python3 -I dst_icons.py <package> <out dir>"""
import sys, io, re, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s4clip import read_package
from PIL import Image
def undst5(b):
    hdr = bytearray(b[:128]); hdr[84:88] = b'DXT5'; d = b[128:]; n = len(d)
    o0, o2 = 0, n >> 3; o1 = o2 + (n >> 2); o3 = o1 + (6 * n >> 4); out = bytearray()
    for i in range((o2 - o0) // 2):
        out += d[o0+2*i:o0+2*i+2] + d[o1+6*i:o1+6*i+6] + d[o2+4*i:o2+4*i+4] + d[o3+4*i:o3+4*i+4]
    return bytes(hdr) + bytes(out)
ents = read_package(sys.argv[1]); os.makedirs(sys.argv[2], exist_ok=True)
snip = [e for e in ents if e['type'] == 0x7DF2169C][0]['data'].decode()
icons = {int(h, 16): s for s, h in re.findall(r'_(set_\d+)</T><T n="pose_display_name">0x[0-9A-F]+</T><T n="pose_description">0x[0-9A-F]+</T><T n="sort_order">\d+</T><T n="icon">2f7d0004:00000000:([0-9a-f]+)', snip)}
for e in ents:
    if e['type'] == 0xB2D882:
        Image.open(io.BytesIO(undst5(e['data']))).convert('RGB').save(os.path.join(sys.argv[2], icons.get(e['inst'], hex(e['inst'])) + '.png'))
