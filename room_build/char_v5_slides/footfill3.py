# bare (socked) feet for v5 once the slides are their own mesh. Tripo never modelled the foot under the strap, so the
# whole sock below the trouser cuff is replaced by a generated one: an ankle tube (ellipse fitted to the original sock,
# from inside the foot up into the trouser leg) and a foot (lofted, 26 cm, rounded heel and toe, flat-ish sole on the
# footbed, inside the strap). Its texture comes from the nearest point of the original sock/toes (ribs, toe shading), so
# the slides-on look stays; seams between UV islands fall back to a plain sock texel. Skinned from the nearest original
# foot vertices. Writes slide_tris.bin, gone_tris.bin and footfill_*.bin for splitslides.mjs.
import numpy as np, json, os
from scipy.spatial import cKDTree
exec(open('slides.py').read().split("print('foot tris'")[0])
FB=float(os.environ.get('FB','0.0155')); INS=float(os.environ.get('INS','0.0025')); YG=float(os.environ.get('YG','0.06'))
cen=P[I].mean(1); white=cand&(L>150)
rim=cand&~dark&((P[I][:,:,1].max(1)<FB+0.003)|(L<140))
feetzone=(np.abs(cen[:,2])>0.045)&(np.abs(cen[:,2])<0.15)&(P[I][:,:,1].max(1)<0.058)&(cen[:,0]>-0.08)&(cen[:,0]<0.12)
rest_=feetzone&(L<150)&~dark
sl=dark|rim|rest_; np.nonzero(sl)[0].astype(np.uint32).tofile('slide_tris.bin')
wz=(np.abs(cen[:,2])>0.045)&(np.abs(cen[:,2])<0.15)&(cen[:,0]>-0.08)&(cen[:,0]<0.12)&(L>150)
gone=wz&~sl&(P[I][:,:,1].max(1)<YG); gone.astype(np.uint8).tofile('gone_tris.bin')
print('slide tris',int(sl.sum()),'original sock tris replaced',int(gone.sum()))
srcw=np.unique(I[(white|gone)&~sl].ravel())                          # original sock/toe surface: texture source
sockuv=UV[I[gone&(cen[:,1]>0.045)].ravel()]; sc=tex(sockuv); SK=sockuv[np.argmin(np.abs(sc-np.median(sc,0)).sum(1))]
fv=np.unique(I[cand].ravel())
def loft(rings):        # rings: list of (NC,3) arrays -> closed tube with end caps
    NS_,NC_=len(rings),len(rings[0]); V_=np.vstack(rings+[rings[0].mean(0)[None],rings[-1].mean(0)[None]]); T_=[]
    for i in range(NS_-1):
        for k in range(NC_):
            a=i*NC_+k; b=i*NC_+(k+1)%NC_; T_+=[[a,b,a+NC_],[b,b+NC_,a+NC_]]
    p0,p1=NS_*NC_,NS_*NC_+1
    for k in range(NC_): T_+=[[p0,(k+1)%NC_,k],[p1,(NS_-1)*NC_+k,(NS_-1)*NC_+(k+1)%NC_]]
    T_=np.array(T_); c_=V_.mean(0); fn=np.cross(V_[T_[:,1]]-V_[T_[:,0]],V_[T_[:,2]]-V_[T_[:,0]])
    if ((V_[T_].mean(1)-c_)*fn).sum(1).mean()<0: T_=T_[:,[0,2,1]]
    return V_,T_
parts=[]; NS,NC=56,40
for side,sg in (('L',-1),('R',1)):
    V=fv[np.sign(P[fv,2])==sg]; Q=P[V]
    dv=np.unique(I[dark&foot[I].all(1)&(np.sign(cen[:,2])==sg)].ravel()); D=P[dv][:,[0,2]]
    c=D.mean(0); u_,s_,vt=np.linalg.svd(D-c); ax=vt[0] if vt[0][0]>0 else -vt[0]; lat=np.array([-ax[1],ax[0]])
    t=(Q[:,[0,2]]-c)@ax; sv=(Q[:,[0,2]]-c)@lat; y=Q[:,1]
    # ankle tube: ellipse from the original sock at 5-6 cm (white verts, this side)
    sw=np.unique(I[wz&~sl&(np.sign(cen[:,2])==sg)&(np.abs(cen[:,1]-(YG+0.002))<0.003)].ravel()); S2=P[sw][:,[0,2]]
    tc=S2.mean(0); uu,ss,tv=np.linalg.svd(S2-tc); e1=tv[0]; e2=tv[1]
    r1=(np.percentile((S2-tc)@e1,98)-np.percentile((S2-tc)@e1,2))/2-0.0012; r2=(np.percentile((S2-tc)@e2,98)-np.percentile((S2-tc)@e2,2))/2-0.0012
    rings=[]
    for yy in np.linspace(0.022,YG+0.005,14):
        f=float(np.interp(yy,[0.022,0.035,0.045,0.055,YG,YG+0.005],[0.55,0.72,0.84,0.90,0.92,0.84]))
        rings.append(np.array([[*(tc+e1*r1*f*np.cos(a)+e2*r2*f*np.sin(a))] for a in np.linspace(0,2*np.pi,NC,endpoint=False)])[:,[0,1]])
    rings=[np.c_[r[:,0],np.full(len(r),yy),r[:,1]] for r,yy in zip(rings,np.linspace(0,1,14)*(YG+0.005-0.022)+0.022)]
    parts.append(loft(rings))
    # foot
    toes=np.isin(V,srcw)&(y>FB+0.003)&(y<0.035)
    t_toe=t[toes].max(); tb=float(((tc-c)@ax)-max(abs(e1@ax)*r1,abs(e2@ax)*r2)*0.84-0.003)
    t_heel=min(t_toe-float(os.environ.get('FOOTL','0.1456')),tb); Lf=t_toe-t_heel
    ts=np.linspace(t_heel,t_toe,NS); u=(ts-t_heel)/Lf
    fz=toes&((t-t_heel)/Lf>0.62); Wb=np.percentile(sv[fz],97)-np.percentile(sv[fz],3)
    toetop=np.percentile(y[toes&((t-t_heel)/Lf>0.8)],95)
    ctr=[]; caps=[]; capw=[]; solew=[]
    solev=np.isin(V,dv)&(y<FB)
    for tk in ts:
        k=np.isin(V,srcw)&(np.abs(t-tk)<0.006)&(y<0.04); kd=np.isin(V,dv)&(np.abs(t-tk)<0.004)&(y>FB+0.004)
        ctr.append((np.percentile(sv[k],3)+np.percentile(sv[k],97))/2 if k.sum()>20 else np.nan)
        caps.append(y[kd].max()-0.0035 if kd.sum()>5 and y[kd].max()>FB+0.018 else 9)
        capw.append((np.percentile(sv[kd],99)-np.percentile(sv[kd],1))/2-0.003 if kd.sum()>5 else 9)
        ks=solev&(np.abs(t-tk)<0.004); solew.append((np.percentile(sv[ks],1),np.percentile(sv[ks],99)) if ks.sum()>5 else (np.nan,np.nan))
    ctr=np.array(ctr); bb=np.isnan(ctr); ctr[bb]=np.interp(np.nonzero(bb)[0],np.nonzero(~bb)[0],ctr[~bb])
    tcs=(tc-c)@lat
    for _ in range(8): ctr[1:-1]=(ctr[:-2]+2*ctr[1:-1]+ctr[2:])/4
    ctr=np.where(u<0.35,tcs+(ctr-tcs)*np.clip(u/0.35,0,1),ctr)            # the heel lines up under the ankle tube
    wprof=np.interp(u,[0,0.03,0.10,0.28,0.50,0.70,0.82,0.92,0.97,1.0],[0.45,0.64,0.70,0.72,0.84,0.98,0.95,0.80,0.60,0.34])
    yb=FB+0.0008; ank=float(os.environ.get('ANKH','0.052'))
    hcurve=np.interp(u,[0,0.05,0.15,0.30,0.45,0.60,0.72,0.84,0.94,1.0],[0.60,0.88,1.0,1.0,0.90,0.70,0.55,0.45,0.38,0.30])
    base=yb+(ank-yb)*hcurve; capa=np.array(caps)
    ks_=[(capa[i]-yb)/(base[i]-yb) for i in range(NS) if capa[i]<9 and base[i]>yb]
    kfac=max(0.55,min(1.0,np.percentile(ks_,10))) if ks_ else 1.0
    blend=np.clip((u-0.2)/0.15,0,1); hscale=1-(1-kfac)*blend
    print(side,'instep scaled by %.2f to stay under the strap'%kfac)
    rings=[]
    for i,tk in enumerate(ts):
        hw=min(Wb/2*wprof[i],capw[i]); yt=yb+(ank-yb)*hcurve[i]*hscale[i]
        if not np.isnan(solew[i][0]):                                        # never wider than the slide's sole
            lo_,hi_=solew[i][0]+0.004,solew[i][1]-0.004
            hw=max(min(hw,ctr[i]-lo_,hi_-ctr[i]),0.008)
        wsm=float(np.clip((u[i]-0.45)/0.35,0,1)); wsm=wsm*wsm*(3-2*wsm)                      # ease into the toes' height
        yt=(1-wsm)*yt+wsm*min(yt,toetop-INS+0.001)
        yt=max(min(yt,caps[i]),yb+0.004); hh=(yt-yb)/2; ym=yb+hh
        r=[]
        for a in np.linspace(0,2*np.pi,NC,endpoint=False):
            ca,sa=np.cos(a),np.sin(a); ssv=ctr[i]+hw*np.sign(ca)*abs(ca)**0.85; yy=ym+hh*np.sign(sa)*abs(sa)**(1.0 if sa>0 else 0.5)
            xz=c+ax*tk+lat*ssv; r.append([xz[0],yy,xz[1]])
        rings.append(np.array(r))
    parts.append(loft(rings))
    print(side,'foot %.1f cm, ball %.1f cm, toe height %.1f cm, ankle radii %.1f x %.1f cm'%(Lf*178.6,Wb*178.6,(toetop-FB)*178.6,r1*178.6,r2*178.6))
# merge, unweld (per-triangle UVs), texture from the nearest original sock/toe point
Vs=[];Ts=[];n0=0
for V_,T_ in parts: Vs.append(V_); Ts.append(T_+n0); n0+=len(V_)
V=np.vstack(Vs); T=np.vstack(Ts)
fn=np.cross(V[T[:,1]]-V[T[:,0]],V[T[:,2]]-V[T[:,0]]); vn=np.zeros_like(V)
for j in range(3): np.add.at(vn,T[:,j],fn)
vn/=np.linalg.norm(vn,axis=1,keepdims=True)+1e-12
_,nk=cKDTree(P[srcw]).query(V); vuv=UV[srcw[nk]]
TU=vuv[T]; span=np.max(np.abs(TU-TU.mean(1,keepdims=True)).max(2),1); bad=span>float(os.environ.get('SPAN','0.01'))
TU[:]=SK if os.environ.get('PLAIN','1')=='1' else TU; TU[bad]=SK
VV=V[T].reshape(-1,3).astype(np.float32); NN=vn[T].reshape(-1,3).astype(np.float32); UU=TU.reshape(-1,2).astype(np.float32); TT=np.arange(len(VV),dtype=np.uint32)
d,k=cKDTree(P[fv]).query(VV,k=4); src=fv[k]; ws=1/np.maximum(d,1e-5)**2; ws/=ws.sum(1,keepdims=True)
Jn=np.zeros((len(VV),4),np.uint16); Wn=np.zeros((len(VV),4),np.float32)
for i in range(len(VV)):
    acc={}
    for q in range(4):
        for jj,ww in zip(J[src[i,q]],W[src[i,q]]): acc[int(jj)]=acc.get(int(jj),0)+ww*ws[i,q]
    top=sorted(acc.items(),key=lambda x:-x[1])[:4]; tot=sum(x[1] for x in top)
    for q,(jj,ww) in enumerate(top): Jn[i,q]=jj; Wn[i,q]=ww/tot
VV.tofile('footfill_pos.bin'); NN.tofile('footfill_nrm.bin'); UU.tofile('footfill_uv.bin'); Jn.tofile('footfill_j.bin'); Wn.tofile('footfill_w.bin'); TT.tofile('footfill_idx.bin')
print('new sock tris',len(T),'plain-texel tris (UV seams)',int(bad.sum()))
