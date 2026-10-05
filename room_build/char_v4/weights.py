import numpy as np, json
from scipy.spatial import cKDTree
exec(open('load.py').read())
bP,bUV,bI,_=load('body'); bs=skin(colors('body',bUV))
J=np.fromfile('body_j.bin',np.uint16).reshape(-1,4); W=np.fromfile('body_w.bin',np.float32).reshape(-1,4)
names=json.load(open('body_joints.json')); H,N1,N2=[names.index(n) for n in ['Head','NeckTwist01','NeckTwist02']]
wj=lambda j:(W*(J==j)).sum(1)
dom=J[np.arange(len(J)),W.argmax(1)]
# source for weight transfer: verts driven mostly by head/neck bones
src=np.isin(dom,[H,N1,N2])&(bP[:,1]>0.74)
hP=np.fromfile('headlo_pos.bin',np.float32).reshape(-1,3)
tr=cKDTree(bP[src]); d,k=tr.query(hP,k=4)
ws=1/np.maximum(d,1e-5)**2; ws/=ws.sum(1,keepdims=True)
# accumulate weights per joint over the 4 nearest
sj=J[src][k]; sw=W[src][k]*ws[:,:,None]
acc=np.zeros((len(hP),len(names)),np.float32)
for a in range(4):
    for b in range(4): np.add.at(acc,(np.arange(len(hP)),sj[:,a,b]),sw[:,a,b])
top=np.argsort(-acc,1)[:,:4]; tw=np.take_along_axis(acc,top,1); tw/=tw.sum(1,keepdims=True)
top.astype(np.uint16).tofile('headlo_j.bin'); tw.astype(np.float32).tofile('headlo_w.bin')
print('head verts',len(hP),'mean dist to source',d[:,0].mean(),'dominant joints',{names[j]:int(c) for j,c in zip(*np.unique(top[:,0],return_counts=True))})
# remove the old head: triangles whose vertices are all head-driven or neck skin above the collar
S_=0.166; T_=np.array([0.078-S_*0.418, 0.873-S_*0.365, -0.006]); MARGIN=float(__import__('os').environ.get('MARGIN','0.05'))
xo=(bP[:,0]-T_[0])/S_; yo=(bP[:,1]-T_[1])/S_
dh,_=cKDTree(hP).query(bP); hair=(~bs)&(wj(H)>0.3)&(dh<float(__import__('os').environ.get('HAIRD','0.012')))&(bP[:,1]>0.83)
bc0=colors('body',bUV)
rr=np.hypot(bP[:,0]-0.02,bP[:,2]+0.006); NR=float(__import__('os').environ.get('NR','0.055'))
plane=0.13+(0.25-xo)*0.42
rm=(((wj(H)>0.3)|bs)&(yo>plane+MARGIN))|(bs&(xo>-0.1)&(yo>0.10+float(__import__("os").environ.get("FM","0.05"))))|hair|(bs&(bP[:,1]>float(__import__('os').environ.get('JY','0.825')))&(dh>0.004)&(rr>0.035))   # old jaw outside the new neck; same slanted cut as the head, body kept a little above it (overlap)
tri=bI[~rm[bI].any(1)]
tri.astype(np.uint32).tofile('body_keep_idx.bin'); print('body tris',len(bI),'->',len(tri))
# match the body's neck skin tone (below the cut) to the owner's neck just above it
from PIL import Image, ImageDraw, ImageFilter
hUV=np.fromfile('headlo_uv.bin',np.float32).reshape(-1,2)
him=np.asarray(Image.open('headlo_base.jpeg').convert('RGB')).astype(np.float32); hh,hw=him.shape[:2]
hc=him[np.clip((hUV[:,1]%1)*hh,0,hh-1).astype(int),np.clip((hUV[:,0]%1)*hw,0,hw-1).astype(int)]
hneck=skin(hc)&(hP[:,1]>hP[:,1].min()+0.008)&(hP[:,1]<hP[:,1].min()+0.03)&(hP[:,0]<0.06)
bneckv=bs&(bP[:,1]>0.70)&(np.abs(bP[:,2])<0.06)
bc=colors('body',bUV)
ratio=hc[hneck].mean(0)/bc[bneckv].mean(0); print('neck tone ratio',ratio,hneck.sum(),bneckv.sum())
ntri=tri[bneckv[tri].all(1)]
im=Image.open('body_base.jpeg').convert('RGB'); W_,H_=im.size
mask=Image.new('L',im.size,0); dr=ImageDraw.Draw(mask)
for t in ntri:
    dr.polygon([(float(bUV[v,0]%1*W_),float(bUV[v,1]%1*H_)) for v in t],fill=255)
mask=mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(4))
a=np.asarray(im).astype(np.float32); m=np.asarray(mask).astype(np.float32)[...,None]/255
out=a*(1-m)+np.clip(a*ratio,0,255)*m
Image.fromarray(out.astype(np.uint8)).save('body_base_neck.jpeg',quality=92); print('neck tris toned',len(ntri))
