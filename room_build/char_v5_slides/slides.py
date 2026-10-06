# split the slides (black straps and soles) out of the v5 body: triangles on the foot/toe bones whose texture is dark
import numpy as np, json, os
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
P=np.fromfile('b_pos.bin',np.float32).reshape(-1,3); I=np.fromfile('b_idx.bin',np.uint32).reshape(-1,3)
UV=np.frombuffer(open('body_base.img.uv','rb').read(),np.float32).reshape(-1,2)
J=np.fromfile('nf_j.bin',np.uint16).reshape(-1,4); W=np.fromfile('nf_w.bin',np.float32).reshape(-1,4)
names=json.load(open('b_skin.json'))['joints']
fj=[names.index(n) for n in names if any(k in n for k in ('Foot','ToeBase'))]
dom=J[np.arange(len(J)),W.argmax(1)]; foot=np.isin(dom,fj)
im=np.asarray(Image.open('body_base_fix.jpg').convert('RGB')).astype(np.float32); h,w=im.shape[:2]
def tex(uv): return im[(uv[:,1]%1*h).astype(int).clip(0,h-1),(uv[:,0]%1*w).astype(int).clip(0,w-1)]
# per-triangle colour: mean of 3 corners + centroid
c=(tex(UV[I].reshape(-1,2)).reshape(-1,3,3).mean(1)+tex(UV[I].mean(1)))/2
L=c.mean(1); YMAX=float(os.environ.get('YMAX','0.075'))
low=P[:,1]<0.03
cand=(foot|low)[I].all(1)&(P[I][:,:,1].max(1)<YMAX)
dark=cand&(L<float(os.environ.get('DL','70')))
print('foot tris',int(foot[I].all(1).sum()),'cand',int(cand.sum()),'dark',int(dark.sum()),'y range foot',P[foot,1].min().round(4),P[foot,1].max().round(4))
print('L hist cand',np.histogram(L[cand],bins=[0,30,50,70,90,120,160,200,256])[0])
np.save('slide_tris.npy',np.nonzero(dark)[0])
