# keeps only single-actor, fully clothed, non-romantic clips of a WickedWhims package; writes a new DBPF with those CLIPs
import struct, sys, zlib, re
KEEP={'Knocking On Door','Getting In V1','Getting In V3','Getting In V4','Getting In Sad','Knock and Open',
      'SITTING and LYING ON BED','SLEEPING LOOP V1','SLEEPING LOOP V1 TO V2','SLEEPING LOOP V2'}
src,dst=sys.argv[1],sys.argv[2]
d=open(src,'rb').read()
cnt,=struct.unpack_from('<I',d,36); p,=struct.unpack_from('<I',d,64)
flags,=struct.unpack_from('<I',d,p); p+=4
const={}
for i,n in enumerate(['type','group','insthi']):
    if flags&(1<<i): const[n],=struct.unpack_from('<I',d,p); p+=4
ents=[]
for _ in range(cnt):
    e={}
    for n in ['type','group','insthi']:
        e[n]=const[n] if n in const else struct.unpack_from('<I',d,p)[0]
        if n not in const: p+=4
    e['lo'],e['off'],e['fs'],e['ms']=struct.unpack_from('<IIII',d,p); p+=16; e['comp']=(0,0)
    if e['fs']&0x80000000: e['comp']=struct.unpack_from('<HH',d,p); p+=4
    ents.append(e)
def body(e):
    b=d[e['off']:e['off']+(e['fs']&0x7fffffff)]
    return zlib.decompress(b) if e['comp'][0]==0x5A42 else b
snip=[body(e).decode('utf-8','replace') for e in ents if e['type']==0x7DF2169C][0]
want={}
for blk in snip.split('animation_raw_display_name')[1:]:
    name=re.search(r'>([^<]*)<',blk).group(1)
    if name in KEEP:
        assert blk.count('actor_id')==1 and 'naked_type">NONE' in blk, name
        for c in re.findall(r'animation_clip_name">([^<]*)<',blk): want[c]=name
out=[]
for e in ents:
    if e['type']!=0x6B20C4F3: continue
    b=body(e); m=re.search(rb'[\x20-\x7e]{6,}',b).group().decode()
    if m in want: out.append((e,b,m))
print("missing", set(want)-{m for _,_,m in out})
# write uncompressed DBPF 2.1
hdr=bytearray(96); hdr[:4]=b'DBPF'; struct.pack_into('<II',hdr,4,2,1)
blob=bytearray(hdr); idx=bytearray(struct.pack('<I',0))
for e,b,m in out:
    off=len(blob); blob+=b
    idx+=struct.pack('<IIIIIII',e['type'],e['group'],e['insthi'],e['lo'],off,len(b)|0x80000000,len(b))+struct.pack('<HH',0,1)
ipos=len(blob); blob+=idx
struct.pack_into('<I',blob,36,len(out)); struct.pack_into('<I',blob,44,len(idx)); struct.pack_into('<I',blob,64,ipos)
open(dst,'wb').write(blob)
for e,b,m in out: print(m, '->', want[m], len(b))
