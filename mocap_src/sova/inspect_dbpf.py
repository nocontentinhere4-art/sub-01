import struct, sys, zlib, collections, re
d=open(sys.argv[1],'rb').read()
assert d[:4]==b'DBPF', d[:4]
maj,minr=struct.unpack_from('<II',d,4)
cnt,=struct.unpack_from('<I',d,36); ipos,=struct.unpack_from('<I',d,64); 
print('ver',maj,minr,'entries',cnt)
p=ipos; flags,=struct.unpack_from('<I',d,p); p+=4
const={}
names=['type','group','insthi']
for i,n in enumerate(names):
    if flags&(1<<i): const[n],=struct.unpack_from('<I',d,p); p+=4
ents=[]
for _ in range(cnt):
    e={}
    for n in names:
        if n in const: e[n]=const[n]
        else: e[n],=struct.unpack_from('<I',d,p); p+=4
    e['instlo'],e['off'],fs,e['memsize']=struct.unpack_from('<IIII',d,p); p+=16
    e['size']=fs&0x7fffffff
    if fs&0x80000000: e['comp'],e['comm']=struct.unpack_from('<HH',d,p); p+=4
    ents.append(e)
c=collections.Counter(hex(e['type']) for e in ents); print(c)
def data(e):
    b=d[e['off']:e['off']+e['size']]
    if e.get('comp')==0x5A42: return zlib.decompress(b)
    return b if e.get('comp',0)==0 else None
for e in ents:
    b=data(e)
    if b is None: print(hex(e['type']),'comp',hex(e.get('comp',0))); continue
    strs=set(s.decode() for s in re.findall(rb'[\x20-\x7e]{6,}',b[:4000]))
    if e['type']==0x6B20C4F3: print('CLIP', len(b), sorted(strs)[:6])
    elif e['type'] in (0x220557DA,):  # STBL
        print('STBL',len(b))
    else: print(hex(e['type']), len(b), sorted(strs)[:8])
print('----')
for e in ents:
    if e['type']!=0x6B20C4F3: continue
    b=data(e)
    if b is None: print('clip comp',hex(e.get('comp',0)), e['size'], e['memsize']); continue
    i=b.find(b'_pilC3S_')
    strs=[s.decode() for s in re.findall(rb'[\x20-\x7e]{5,}',b) ][:5]
    # S3 clip: magic(8) ver(4) unk(4) frameDuration f32, frameCount u16
    if i>=0:
        ver,unk,fd=struct.unpack_from('<IIf',b,i+8); fc,=struct.unpack_from('<H',b,i+20)
        print(len(b), 'frames',fc,'fdur',round(fd,4), strs[:3])
    else: print(len(b), strs)
