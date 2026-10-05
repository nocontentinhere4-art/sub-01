# v5 bust texture polish (bust texture only): skin a little less orange/warm, and the dark nostril texels lightened.
import numpy as np, os, colorsys
from PIL import Image, ImageDraw, ImageFilter
exec(open('load.py').read())
P=np.fromfile('headlo_pos.bin',np.float32).reshape(-1,3); UV=np.fromfile('headlo_uv.bin',np.float32).reshape(-1,2)
I=np.fromfile('headlo_idx.bin',np.uint32).reshape(-1,3)
im=np.asarray(Image.open('headlo_base.jpeg').convert('RGB')).astype(np.float32); h,w=im.shape[:2]
r,g,b=im[...,0],im[...,1],im[...,2]
sk=(r>95)&(r>b+10)&(r>g)                                             # skin-like texels (lips included, hair and eyes not)
lum=im.mean(-1,keepdims=True); SAT=float(os.environ.get('SAT','0.82')); WARM=np.array([0.985,1.0,1.03])
new=np.clip((lum+(im-lum)*SAT)*WARM*float(os.environ.get('BR','1.03')),0,255)
soft=np.asarray(Image.fromarray((sk*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[...,None]/255
im=im*(1-soft)+new*soft
# nostrils: triangles near and under the nose tip; dark texels there move 35% toward the local skin colour
face=(P[:,1]>0.85); tip=P[face][np.argmax(P[face][:,0])]
near=np.linalg.norm(P-tip,axis=1)<0.014; tri=I[near[I].all(1)&(P[I][:,:,1].max(1)<tip[1]+0.002)]
m=Image.new('L',(w,h),0); d=ImageDraw.Draw(m)
for t in tri: d.polygon([(float(UV[v,0]%1*w),float(UV[v,1]%1*h)) for v in t],fill=255)
m=np.asarray(m.filter(ImageFilter.MaxFilter(5)))>0
L=im.mean(-1); skinmed=np.median(im[m&(L>110)],0) if (m&(L>110)).any() else np.array([190,150,130])
dark=m&(L<float(os.environ.get('DARK','70')))
im[dark]=im[dark]*(1-float(os.environ.get('NOSTRIL','0.35')))+skinmed*float(os.environ.get('NOSTRIL','0.35'))
print('nose tip',tip.round(3),'nostril texels lightened',int(dark.sum()),'skin texels',int(sk.sum()))
Image.fromarray(im.astype(np.uint8)).save('head_base_fix.jpeg',quality=93)
