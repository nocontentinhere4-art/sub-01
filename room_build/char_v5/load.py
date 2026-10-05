import numpy as np, json
from PIL import Image
Image.MAX_IMAGE_PIXELS=None
def load(n, rot=False):
    P=np.fromfile(n+'_pos.bin',np.float32).reshape(-1,3).copy(); UV=np.fromfile(n+'_uv.bin',np.float32).reshape(-1,2)
    I=np.fromfile(n+'_idx.bin',np.uint32).reshape(-1,3); N=np.fromfile(n+'_nrm.bin',np.float32).reshape(-1,3).copy()
    if rot: P=np.stack([P[:,2],P[:,1],-P[:,0]],1); N=np.stack([N[:,2],N[:,1],-N[:,0]],1)
    return P,UV,I,N
def colors(n,UV):
    im=np.asarray(Image.open(n+'_base.jpeg').convert('RGB')); h,w=im.shape[:2]
    x=np.clip((UV[:,0]%1)*w,0,w-1).astype(int); y=np.clip((UV[:,1]%1)*h,0,h-1).astype(int)
    return im[y,x].astype(np.float32)
def skin(C): return (C[:,0]>110)&(C[:,0]>C[:,2]+12)
