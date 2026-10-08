"""Sims 4 .package (DBPF 2.1) + S3 clip (_pilC3S_) reader, written from the public format
(s3pi/s4pi docs). Usage: python3 -I s4clip.py <package> [set_N]"""
import struct, sys, zlib, re

def fnv32(s):
    h = 0x811C9DC5
    for c in s.encode():
        h = ((h * 0x01000193) & 0xFFFFFFFF) ^ c
    return h
def fnv64(s):
    h = 0xCBF29CE484222325
    for c in s.encode():
        h = ((h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF) ^ c
    return h

def read_package(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'DBPF'
    cnt, = struct.unpack_from('<I', d, 36); p, = struct.unpack_from('<I', d, 64)
    flags, = struct.unpack_from('<I', d, p); p += 4
    const = {}; names = ['type', 'group', 'insthi']
    for i, n in enumerate(names):
        if flags & (1 << i): const[n], = struct.unpack_from('<I', d, p); p += 4
    out = []
    for _ in range(cnt):
        e = {}
        for n in names:
            if n in const: e[n] = const[n]
            else: e[n], = struct.unpack_from('<I', d, p); p += 4
        e['instlo'], off, fs, e['memsize'] = struct.unpack_from('<IIII', d, p); p += 16
        size = fs & 0x7fffffff; comp = 0
        if fs & 0x80000000: comp, _ = struct.unpack_from('<HH', d, p); p += 4
        b = d[off:off + size]
        e['data'] = zlib.decompress(b) if comp == 0x5A42 else b
        e['inst'] = (e['insthi'] << 32) | e['instlo']
        out.append(e)
    return out

def stbl(b):
    # STBL v5: 'STBL' ver(2) compressed(1) count(8) reserved(2) strlen(4) then entries
    assert b[:4] == b'STBL'
    n, = struct.unpack_from('<Q', b, 7); p = 21; m = {}
    for _ in range(n):
        k, fl, ln = struct.unpack_from('<IBH', b, p); p += 7
        m[k] = b[p:p + ln].decode('utf-8', 'replace'); p += ln
    return m

def s3clip(b):
    """returns dict(frame_dur, nframes, name, src, curves=[(hash, type, [(frame, values)])])"""
    o = b.find(b'_pilC3S_'); b = b[o:]
    ver, unk, fdur, nfr, unk2, ncur, nfl, cdo, fdo, ano, sno = struct.unpack_from('<IIfHHIIIIII', b, 8)
    floats = struct.unpack_from('<%df' % nfl, b, fdo)
    name = b[ano:b.index(b'\0', ano)].decode(); src = b[sno:b.index(b'\0', sno)].decode()
    curves = []
    for i in range(ncur):
        fo, key, off, scale, cnt, fl, typ = struct.unpack_from('<IIffHBB', b, cdo + 20 * i)
        dtype = fl & 7; static = (fl >> 3) & 1; fmt = fl >> 4
        nf = {1: 1, 2: 3, 4: 4}[dtype]
        p = fo; frames = []
        for _ in range(cnt):
            fi, flags = struct.unpack_from('<HH', b, p); p += 4
            vals = []
            if fmt == 0:  # indexed
                for k in range(nf):
                    ix, = struct.unpack_from('<H', b, p); p += 2
                    v = floats[ix]
                    if flags & (1 << k): v = -v
                    vals.append(v * scale + off)
            else:  # packed
                if dtype == 2:
                    pk, = struct.unpack_from('<I', b, p); p += 4
                    for k in range(3):
                        v = ((pk >> (10 * k)) & 1023) / 1023.0
                        if flags & (1 << k): v = -v
                        vals.append(v * scale + off)
                elif dtype == 4:
                    for k in range(4):
                        pk, = struct.unpack_from('<H', b, p); p += 2
                        v = (pk & 4095) / 4095.0
                        if flags & (1 << k): v = -v
                        vals.append(v * scale + off)
                else:
                    pk, = struct.unpack_from('<H', b, p); p += 2
                    v = pk / 65535.0
                    if flags & 1: v = -v
                    vals.append(v * scale + off)
            frames.append((fi, vals))
        curves.append(dict(key=key, type=typ, dtype=dtype, static=static, fmt=fmt, off=off, scale=scale, frames=frames, end=p))
    return dict(ver=ver, fdur=fdur, nframes=nfr, name=name, src=src, curves=curves, size=len(b))

def clips_by_set(path):
    ents = read_package(path)
    clips = {}
    for e in ents:
        if e['type'] != 0x6B20C4F3: continue
        m = re.search(rb'PosePack_\d+_(set_\d+)', e['data'])
        clips[m.group(1).decode() if m else hex(e['inst'])] = e['data']
    return ents, clips

def set_names(ents):
    """set_N -> English pose name (snippet pose_display_name keys into the STBL holding them)"""
    snip = [e for e in ents if e['type'] == 0x7DF2169C][0]['data'].decode()
    pairs = re.findall(r'_(set_\d+)</T><T n="pose_display_name">0x([0-9A-F]+)', snip)
    for e in ents:
        if e['type'] != 0x220557DA: continue
        m = stbl(e['data'])
        if (e['inst'] >> 56) == 0 and all(int(h, 16) in m for _, h in pairs):   # locale 0x00 = English
            return {s: m[int(h, 16)] for s, h in pairs}
    return {}

if __name__ == '__main__':
    ents, clips = clips_by_set(sys.argv[1])
    for k in sorted(clips, key=lambda s: int(s.split('_')[1]) if s.startswith('set_') else 0):
        c = s3clip(clips[k])
        print(k, c['name'], c['src'], c['nframes'], round(c['fdur'], 4), len(c['curves']), 'end', c['curves'][-1]['end'], c['size'])
