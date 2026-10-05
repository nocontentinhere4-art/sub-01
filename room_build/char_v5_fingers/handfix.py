# hands only: grey-blue texels in the hand UV islands take the hand's own skin colour (their shading kept)
import numpy as np, json, io
from PIL import Image, ImageDraw, ImageFilter
Image.MAX_IMAGE_PIXELS=None
P=np.fromfile('b_pos.bin',np.float32).reshape(-1,3); I=np.fromfile('b_idx.bin',np.uint32).reshape(-1,3)
UV=np.frombuffer(open('body_base.img.uv','rb').read(),np.float32).reshape(-1,2)
J=np.fromfile('nf_j.bin',np.uint16).reshape(-1,4); W=np.fromfile('nf_w.bin',np.float32).reshape(-1,4)
names=json.load(open('b_skin.json'))['joints']+[q['name'] for q in json.load(open('fingers.json'))['joints']]
hj=[i for i,n in enumerate(names) if n.endswith('_Hand') or n.startswith('finger') or n.startswith('metacarpal')]
hv=(W*np.isin(J,hj)).sum(1)>0.5
im=Image.open('body_base.img').convert('RGB'); w,h=im.size; A=np.asarray(im).astype(np.float32)
m=Image.new('L',(w,h),0); dr=ImageDraw.Draw(m)
for t in I[hv[I].all(1)]: dr.polygon([(float(UV[v,0]%1*w),float(UV[v,1]%1*h)) for v in t],fill=255)
M=np.asarray(m.filter(ImageFilter.MaxFilter(5)))>0
r,g,b=A[...,0],A[...,1],A[...,2]; L=A.mean(-1)
skin=M&(r>b+25)&(r>g+8)&(L>90); grey=M&~skin&(L>60)&(r<b+18)            # bluish/neutral grey, not dark (nails/creases stay)
med=np.median(A[skin],0); lm=med.mean()
new=np.clip(med*(L/lm)[...,None],0,255)
k=np.asarray(Image.fromarray((grey*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[...,None]/255*M[...,None]
A=A*(1-k)+new*k
print('hand texels',int(M.sum()),'grey',int(grey.sum()),'skin median',med.round(1))
Image.fromarray(A.astype(np.uint8)).save('body_base_fix.jpg',quality=92)
