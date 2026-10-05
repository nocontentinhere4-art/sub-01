# a dark inner T-shirt panel just behind the hoodie front and his neck, filling the hood's V below his neck.
import numpy as np, os
from PIL import Image
P=np.fromfile('headlo_pos.bin',np.float32).reshape(-1,3); N=np.fromfile('headlo_nrm.bin',np.float32).reshape(-1,3)
UV=np.fromfile('headlo_uv.bin',np.float32).reshape(-1,2); I=np.fromfile('headlo_idx.bin',np.uint32).reshape(-1,3)
PX=float(os.environ.get('PX','0.037')); ZW=float(os.environ.get('PZ','0.035')); Y0,Y1=0.775,float(os.environ.get('PY','0.835')); NA,NY=12,6
im=np.asarray(Image.open('headlo_base.jpeg').convert('RGB')).astype(np.float32); h,w=im.shape[:2]
hair=np.nonzero(P[:,1]>P[:,1].max()-0.01)[0]
cols=im[(UV[hair,1]%1*h).astype(int).clip(0,h-1),(UV[hair,0]%1*w).astype(int).clip(0,w-1)].mean(1)
SK=UV[hair[np.argsort(np.abs(cols-np.percentile(cols,30)))[0]]]
V=[];NN=[]
for j in range(NY+1):
    y=Y0+(Y1-Y0)*j/NY
    for i in range(NA+1):
        z=-ZW+2*ZW*i/NA; V.append([PX-0.25*(z/ZW)**2*ZW,y,z+float(os.environ.get('PC','-0.006'))]); NN.append([1,0,0])     # flat panel facing +X, edges curving back
V=np.array(V,np.float32); NN=np.array(NN,np.float32); n0=len(P); T=[]
for j in range(NY):
    for i in range(NA):
        p=n0+j*(NA+1)+i; T+=[[p,p+1,p+NA+1],[p+1,p+NA+2,p+NA+1]]
np.concatenate([P,V]).astype(np.float32).tofile('headx_pos.bin'); np.concatenate([N,NN]).astype(np.float32).tofile('headx_nrm.bin')
np.concatenate([UV,np.repeat(SK[None],len(V),0)]).astype(np.float32).tofile('headx_uv.bin'); np.concatenate([I,np.array(T,np.uint32)]).astype(np.uint32).tofile('headx_idx.bin')
print('inner T-shirt panel verts',len(V))
