import numpy as np, json, os
from scipy.spatial import cKDTree
exec(open('load.py').read())
bP,bUV,bI,_=load('body'); bs=skin(colors('body',bUV))
J=np.fromfile('body_j.bin',np.uint16).reshape(-1,4); W=np.fromfile('body_w.bin',np.float32).reshape(-1,4)
names=json.load(open('body_joints.json')); H,N1,N2=[names.index(n) for n in ['Head','NeckTwist01','NeckTwist02']]
wj=lambda j:(W*(J==j)).sum(1)
dom=J[np.arange(len(J)),W.argmax(1)]
# source for weight transfer: verts driven mostly by head/neck bones
ok=[names.index(n) for n in ['Head','NeckTwist01','NeckTwist02','Spine02','L_Clavicle','R_Clavicle']]
src=np.isin(dom,ok)&(bP[:,1]>0.70)
HX='headx' if __import__('os').path.exists('headx_pos.bin') else 'headlo'
hP=np.fromfile(HX+'_pos.bin',np.float32).reshape(-1,3)
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
S_=0.166; T_=np.array([0.078-S_*0.418, 0.873-S_*0.365-float(os.environ.get('DROPHEAD','0')), -0.006]); MARGIN=float(__import__('os').environ.get('MARGIN','0.05'))
xo=(bP[:,0]-T_[0])/S_; yo=(bP[:,1]-T_[1])/S_
dh,_=cKDTree(hP).query(bP); hair=(~bs)&(wj(H)>0.3)&((bP[:,1]>float(os.environ.get('HAIRY','0.87')))|((bP[:,1]>0.83)&(colors('body',bUV).mean(1)<36)))&(dh<float(__import__('os').environ.get('HAIRD','0.012')))&(bP[:,1]>0.83)
bc0=colors('body',bUV)
rr=np.hypot(bP[:,0]-0.02,bP[:,2]+0.006); NR=float(__import__('os').environ.get('NR','0.055'))
plane=0.13+(0.25-xo)*0.42
CH_=float(os.environ.get('CHESTY','0.80'))
rm=((wj(H)>0.3)&bs&(bP[:,1]>CH_))|(bs&(bP[:,1]>float(__import__('os').environ.get('NECKY','0.76')))&(rr<0.07))|hair   # old head, old neck skin, old hair
HD=float(os.environ.get('HOODD','0.01')); dh2,_=cKDTree(hP).query(bP)
rm|=(~bs)&(dh2<HD)&(bP[:,1]>0.78)                                     # body hood surface right at his collar: his collar is the hood top
bright=bc0.mean(1)>85
rm|=bright&(bP[:,1]>0.72)&(bP[:,1]<0.82)&(np.abs(bP[:,2]+0.006)<0.04)&(bP[:,0]>0.03)   # the light lining chip at the V
bcv=colors('body',bUV).mean(1)
#rm|=(bcv>70)&(bP[:,0]>0.03)&(bP[:,1]>0.74)&(bP[:,1]<0.83)&(rr<0.13)            # light lining chips at the V
rm|=(~bs)&(wj(H)>0.3)&(dh<0.03)&(bP[:,1]>0.84)&(bcv<40)   # last old-hair specks
# per angle around the neck: body skin may not rise above his neck's own bottom edge in that direction
cax=np.array([0.024,0.0015]); NB=48
ah=np.arctan2(hP[:,2]-cax[1],hP[:,0]-cax[0]); rh_=np.hypot(hP[:,0]-cax[0],hP[:,2]-cax[1])
ab=np.arctan2(bP[:,2]-cax[1],bP[:,0]-cax[0]); wb=((ab+np.pi)/(2*np.pi)*NB).astype(int)%NB; wh_=((ah+np.pi)/(2*np.pi)*NB).astype(int)%NB
lim=np.full(NB,9.0)
for k in range(NB):
    q=(wh_==k)&(rh_<0.07)
    if q.any(): lim[k]=hP[q,1].min()
for _ in range(2): lim=np.minimum(lim,np.minimum(np.roll(lim,1),np.roll(lim,-1)))
rm|=bs&(bP[:,1]>lim[wb]-float(os.environ.get('UNDER','0.004')))&(rr<0.13)
rm|=bs&(bP[:,1]>CH_)&(rr<0.13)   # all body skin around the neck and chest: no skin left at the hood
tri=bI[~rm[bI].any(1)]
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
_,bw=np.unique(np.round(bP*2e5).astype(np.int64),axis=0,return_inverse=True); bw=bw.ravel(); tw=bw[tri]; nn=bw.max()+1
g=coo_matrix((np.ones(len(tw)*2),(np.r_[tw[:,0],tw[:,1]],np.r_[tw[:,1],tw[:,2]])),shape=(nn,nn))
_,lab=connected_components(g,directed=False); tl=lab[tw[:,0]]; cnt=np.bincount(tl)
stray=(cnt[tl]<int(os.environ.get('STRAY','300')))&(bP[tri[:,0],1]>0.70)
print('stray body fragments removed',int(stray.sum()),'tris'); tri=tri[~stray]
tri.astype(np.uint32).tofile('body_keep_idx.bin'); print('body tris',len(bI),'->',len(tri))
# match the body's neck skin tone (below the cut) to the owner's neck just above it
from PIL import Image, ImageDraw, ImageFilter
hUV=np.fromfile('headlo_uv.bin',np.float32).reshape(-1,2)
him=np.asarray(Image.open('headlo_base.jpeg').convert('RGB')).astype(np.float32); hh,hw=him.shape[:2]
hc=him[np.clip((hUV[:,1]%1)*hh,0,hh-1).astype(int),np.clip((hUV[:,0]%1)*hw,0,hw-1).astype(int)]
hPl=np.fromfile('headlo_pos.bin',np.float32).reshape(-1,3); hneck=skin(hc)&(hPl[:,1]>hPl[:,1].min()+0.002)&(hPl[:,1]<hPl[:,1].min()+0.02)
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

# no skin colour on the hoodie: in the UV area of the cloth triangles around the hood, skin-toned texels take the
# median hoodie colour (body texture only)
cl=tri[(bP[tri,1].min(1)>0.62)&(rr[tri].max(1)<0.2)]
base=np.asarray(Image.open('body_base_neck.jpeg').convert('RGB')).copy(); H_,W_=base.shape[:2]
m=Image.new('L',(W_,H_),0); dr=ImageDraw.Draw(m)
for t in cl: dr.polygon([(float(bUV[v,0]%1*W_),float(bUV[v,1]%1*H_)) for v in t],fill=255)
m=np.asarray(m.filter(ImageFilter.MaxFilter(5)))>0
px=base.astype(np.int32); sk=((px[...,0]>90)&(px[...,0]>px[...,2]+15)&(px[...,0]>px[...,1]+5))|(px.mean(-1)>75)
cloth=base[m&~sk]; fill=np.median(cloth,0).astype(np.uint8) if len(cloth) else np.array([40,40,42],np.uint8)
sel=m&sk; base[sel]=fill
br=base.astype(np.float32).mean(-1); hi_=m&(br>float(fill.mean())+float(os.environ.get('LIN','12')))            # light lining blotches -> hoodie tone
base[hi_]=(base[hi_].astype(np.float32)*((float(fill.mean())+12)/br[hi_])[:,None]).astype(np.uint8)
inner=tri[(bP[tri,1].min(1)>0.79)&(rr[tri].max(1)<float(os.environ.get('INR','0.12')))]       # inner hood around the neck: one flat dark fabric
m3=Image.new('L',(W_,H_),0); d3=ImageDraw.Draw(m3)
for t in inner: d3.polygon([(float(bUV[v,0]%1*W_),float(bUV[v,1]%1*H_)) for v in t],fill=255)
m3=np.asarray(m3.filter(ImageFilter.MaxFilter(5)))>0
lin=base[m3].astype(np.float32); lum=lin.mean(-1,keepdims=True); base[m3]=np.clip(fill.astype(np.float32)*(0.85+0.3*np.clip(lum/255,0,1)),0,255).astype(np.uint8)
print('inner hood tris',len(inner),'texels',int(m3.sum()))
ch=tri[bs[tri].any(1)&(bP[tri,1].min(1)>0.64)&(rr[tri].max(1)<0.13)]               # chest skin in the V: dark T-shirt
m2=Image.new('L',(W_,H_),0); d2=ImageDraw.Draw(m2)
for t in ch: d2.polygon([(float(bUV[v,0]%1*W_),float(bUV[v,1]%1*H_)) for v in t],fill=255)
m2=np.asarray(m2.filter(ImageFilter.MaxFilter(5)))>0; base[m2]=(fill.astype(np.float32)*0.8).astype(np.uint8); print('T-shirt texels',int(m2.sum()))
print('hoodie skin texels recoloured',int(sel.sum()),'to',fill)
Image.fromarray(base).save('body_base_neck.jpeg',quality=92)
