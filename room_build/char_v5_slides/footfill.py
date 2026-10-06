# bare (socked) feet under the slides: per foot, a closed lofted volume that fills the original envelope (the inside of
# the strap, the toes, the sock and the ankle), inset so the original sock and toe surfaces stay on top where they
# exist; white sock colour (one sock texel); skinned from the 4 nearest original foot vertices. Also moves the thin
# white footbed rim into the slides.
import numpy as np, json, os
from scipy.spatial import cKDTree
exec(open('slides.py').read().split("print('foot tris'")[0])
FB=float(os.environ.get('FB','0.0155')); INS=float(os.environ.get('INS','0.0028')); NS,NC=48,36
cen=P[I].mean(1); white=cand&(L>150)
rim=cand&~dark&((P[I][:,:,1].max(1)<FB+0.003)|(L<float(os.environ.get('GL','140'))))
sl=np.nonzero(dark|rim)[0]; sl.astype(np.uint32).tofile('slide_tris.bin'); print('slide tris',len(sl),'rim',int(rim.sum()))
sockuv=UV[I[white&(cen[:,1]>0.035)].ravel()]; sc=tex(sockuv); SK=sockuv[np.argmin(np.abs(sc-np.median(sc,0)).sum(1))]
fv=np.unique(I[cand].ravel())
allV=[];allN=[];allT=[];n0=0
for side,sg in (('L',-1),('R',1)):
    V=fv[np.sign(P[fv,2])==sg]; Q=P[V]
    dv=np.unique(I[dark&foot[I].all(1)&(np.sign(cen[:,2])==sg)].ravel()); D=P[dv][:,[0,2]]
    c=D.mean(0); u,s,vt=np.linalg.svd(D-c); ax=vt[0] if vt[0][0]>0 else -vt[0]; lat=np.array([-ax[1],ax[0]])
    t=(Q[:,[0,2]]-c)@ax; sv=(Q[:,[0,2]]-c)@lat; y=Q[:,1]
    t0,t1=t.min()+0.006,t.max()-0.002; ts=np.linspace(t0,t1,NS)
    wv=np.isin(V,np.unique(I[white&~rim].ravel())); dvm=np.isin(V,dv)
    up=y>FB+0.004; prof=[]; caps=[]
    for tk in ts:
        k=up&wv&(np.abs(t-tk)<0.005); kd=dvm&(np.abs(t-tk)<0.005)&(y>FB+0.004)
        strapped=kd.sum()>5 and (y[kd].max()>(y[k].max() if k.any() else 0)-0.002)
        if k.sum()<20 or strapped: prof.append([np.nan,np.nan,FB+0.0008,np.nan]); caps.append(y[kd].max()-float(os.environ.get('STRAP','0.0035')) if kd.sum()>5 else 9); continue
        caps.append(9); prof.append([sv[k].min()+INS, sv[k].max()-INS, FB+0.0008, y[k].max()-INS])
    prof=np.array(prof)
    for j in range(4):
        b=np.isnan(prof[:,j]); prof[b,j]=np.interp(np.nonzero(b)[0],np.nonzero(~b)[0],prof[~b,j])
    for _ in range(3):
        prof[1:-1]=(prof[:-2]+2*prof[1:-1]+prof[2:])/4
    prof[:,3]=np.minimum(prof[:,3],np.array(caps))
    # taper both ends into rounded caps
    tp=np.ones(NS); m_=6
    for i in range(m_): f=np.sin((i+1)/(m_+1)*np.pi/2); tp[i]=min(tp[i],f); tp[-1-i]=min(tp[-1-i],f)
    verts=[]; nrm=[]
    for i,tk in enumerate(ts):
        smin,smax,yb,yt=prof[i]; sm=(smin+smax)/2; hw=(smax-smin)/2*tp[i]; ym=(yb+yt)/2; hh=(yt-yb)/2*max(tp[i],0.35)
        ymid=yb+hh                                    # keep the sole flat on the footbed
        for k_ in range(NC):
            a=2*np.pi*k_/NC; ca,sa=np.cos(a),np.sin(a); e=float(os.environ.get('EXP','0.85'))
            ss=sm+hw*np.sign(ca)*abs(ca)**e; yy=ymid+hh*np.sign(sa)*abs(sa)**(1.0 if sa>0 else 0.4)
            xz=c+ax*tk+lat*ss; verts.append([xz[0],yy,xz[1]])
    verts=np.array(verts)
    tri=[]
    for i in range(NS-1):
        for k_ in range(NC):
            a_=i*NC+k_; b_=i*NC+(k_+1)%NC; tri+=[[a_,b_,a_+NC],[b_,b_+NC,a_+NC]]
    # caps: a pole at each end
    pc=[verts[:NC].mean(0),verts[-NC:].mean(0)]; i0=len(verts); verts=np.vstack([verts,pc])
    for k_ in range(NC):
        tri.append([i0,(k_+1)%NC,k_]); tri.append([i0+1,(NS-1)*NC+k_,(NS-1)*NC+(k_+1)%NC])
    tri=np.array(tri)
    # orientation: make normals point outward (centroid test)
    cc=verts.mean(0); fn=np.cross(verts[tri[:,1]]-verts[tri[:,0]],verts[tri[:,2]]-verts[tri[:,0]])
    if ((verts[tri].mean(1)-cc)*fn).sum(1).mean()<0: tri=tri[:,[0,2,1]]; fn=-fn
    vn=np.zeros_like(verts); 
    for j in range(3): np.add.at(vn,tri[:,j],fn)
    vn/=np.linalg.norm(vn,axis=1,keepdims=True)+1e-12
    allV.append(verts); allN.append(vn); allT.append(tri+n0); n0+=len(verts)
    print(side,'axis',ax.round(3),'length',round(t1-t0,4),'max height',prof[:,3].max().round(4),'max width',(prof[:,1]-prof[:,0]).max().round(4))
V=np.vstack(allV).astype(np.float32); N_=np.vstack(allN).astype(np.float32); T=np.vstack(allT).astype(np.uint32)
d,k=cKDTree(P[fv]).query(V,k=4); src=fv[k]; ws=1/np.maximum(d,1e-5)**2; ws/=ws.sum(1,keepdims=True)
acc={}
Jn=np.zeros((len(V),4),np.uint16); Wn=np.zeros((len(V),4),np.float32)
for i in range(len(V)):
    a={}
    for q in range(4):
        for jj,ww in zip(J[src[i,q]],W[src[i,q]]): a[int(jj)]=a.get(int(jj),0)+ww*ws[i,q]
    top=sorted(a.items(),key=lambda x:-x[1])[:4]; tot=sum(x[1] for x in top)
    for q,(jj,ww) in enumerate(top): Jn[i,q]=jj; Wn[i,q]=ww/tot
V.tofile('footfill_pos.bin'); N_.tofile('footfill_nrm.bin'); np.repeat(SK[None],len(V),0).astype(np.float32).tofile('footfill_uv.bin')
Jn.tofile('footfill_j.bin'); Wn.tofile('footfill_w.bin'); T.tofile('footfill_idx.bin')
print('foot volume verts',len(V),'tris',len(T),'sock texel',tex(SK[None])[0])
