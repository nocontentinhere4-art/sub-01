# natural socked feet for v5 (preview/bed-music): the sock below YG is replaced by one smooth implicit surface per foot
# (foot + leg blended), with adult-male proportions (26 cm, ball wider than the heel, instep, medial arch, squared oblique
# toe end, soft toe ridges), kept inside the slide (strap underside, walls, footbed) and meshed by marching cubes, then
# decimated (Blender) to ~7k triangles per foot. Knit UVs near the ankle as in footfill3; skinned from the nearest original
# foot vertices, smoothed, the heel given to the Foot bone. Writes slide_tris.bin, gone_tris.bin and footfill_*.bin for
# splitslides.mjs. Run with DARKK=195.
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
gone|=~sl&~gone&(np.abs(cen[:,2])>0.03)&(P[I][:,:,1].max(1)<0.045)            # stray slivers of the old sock under the foot
gone.astype(np.uint8).tofile('gone_tris.bin')
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
# ---- the foot: one smooth implicit surface (foot + leg, smooth union), proportions of an adult male foot for a 1.75 m
# man (length 26 cm = 0.15 H; ball 10 cm wide at ~70% from the heel; heel 6.5 cm; instep 6.5-7 cm high at mid-foot,
# 8 cm at the ankle crease; ball 3.8 cm; toes 2.3 cm; medial arch ~1.4 cm under the mid-foot), meshed by marching cubes
from skimage.measure import marching_cubes
CM=1/178.6                                                                    # Tripo units per cm

def decimate(verts,faces,ntri):
    import bpy,bmesh
    me=bpy.data.meshes.new('f'); me.from_pydata(verts.tolist(),[],faces.tolist()); me.update()
    ob=bpy.data.objects.new('f',me); bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active=ob; ob.select_set(True)
    md=ob.modifiers.new('d','DECIMATE'); md.ratio=min(1.0,ntri/len(faces)); md.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier='d')
    m2=ob.data; v=np.array([x.co[:] for x in m2.vertices]); f=np.array([p.vertices[:] for p in m2.polygons])
    bpy.data.objects.remove(ob); return v,f
def smin(a,b,k): h=np.clip(0.5+0.5*(b-a)/k,0,1); return b*(1-h)+a*h-k*h*(1-h)
def sstep(e0,e1,x): t_=np.clip((x-e0)/(e1-e0),0,1); return t_*t_*(3-2*t_)
parts=[]; tubes={}
nrmS=np.zeros_like(P)                                                         # slide normals (for the strap check)
SLT=I[sl]; fnS=np.cross(P[SLT[:,1]]-P[SLT[:,0]],P[SLT[:,2]]-P[SLT[:,0]])
for j in range(3): np.add.at(nrmS,SLT[:,j],fnS)
nrmS/=np.linalg.norm(nrmS,axis=1,keepdims=True)+1e-12
slv=np.unique(SLT.ravel())
for side,sg in (('L',-1),('R',1)):
    V=fv[np.sign(P[fv,2])==sg]; Q=P[V]
    dv=np.unique(I[dark&foot[I].all(1)&(np.sign(cen[:,2])==sg)].ravel()); D=P[dv][:,[0,2]]
    c=D.mean(0); u_,s_,vt=np.linalg.svd(D-c); ax=vt[0] if vt[0][0]>0 else -vt[0]; lat=np.array([-ax[1],ax[0]])
    med=1.0 if (lat@np.array([0,-sg]))>0 else -1.0                           # +v is the medial (big-toe) side
    t=(Q[:,[0,2]]-c)@ax; sv=(Q[:,[0,2]]-c)@lat; y=Q[:,1]
    sw=np.unique(I[wz&~sl&(np.sign(cen[:,2])==sg)&(np.abs(cen[:,1]-(YG+0.002))<0.003)].ravel()); S2=P[sw][:,[0,2]]
    tc=S2.mean(0); uu,ss,tv=np.linalg.svd(S2-tc); e1=tv[0]; e2=tv[1]
    r1=(np.percentile((S2-tc)@e1,98)-np.percentile((S2-tc)@e1,2))/2-0.0012; r2=(np.percentile((S2-tc)@e2,98)-np.percentile((S2-tc)@e2,2))/2-0.0012
    tubes[sg]=(tc,e1,e2,r1,r2)
    toes=np.isin(V,srcw)&(y>FB+0.003)&(y<0.035)
    t_toe=t[toes].max(); Lf=26*CM; t_heel=t_toe-Lf; yb=FB+0.0008
    Wb=np.percentile(sv[toes&((t-t_heel)/Lf>0.62)],97)-np.percentile(sv[toes&((t-t_heel)/Lf>0.62)],3)
    vball=(np.percentile(sv[toes&((t-t_heel)/Lf>0.62)],97)+np.percentile(sv[toes&((t-t_heel)/Lf>0.62)],3))/2
    vleg=(tc-c)@lat; uleg=((tc-c)@ax-t_heel)/CM                               # the leg's centre, cm from the heel
    # profiles along the foot, u in cm from the heel (0) to the toe tip (26); v, h in cm
    U=  [0,  1.5, 4,   7,   10,  13,  16,  19,  21,  23,  25,  26]
    HW= [2.4,3.1, 3.3, 3.3, 3.5, 3.9, 4.5, 5.0, 4.9, 4.4, 3.4, 2.4]               # half width (ball 10 cm, heel 6.6)
    HT= [3.2,5.5, 9.0, 9.5, 9.0, 7.4, 6.0, 4.2, 3.3, 2.6, 2.2, 1.8]               # top above the sole (instep, ball, toes)
    hwk=Wb/CM/2/5.0                                                            # scale the width to this foot's toes
    def prof(u,arr): return np.interp(u,U,arr)
    def vc(u): return np.interp(u,[0,8,14,26],[vleg/CM,vleg/CM,vball/CM,vball/CM])
    lo=np.array([c[0],c[1]])
    # grid in world coordinates (Tripo units)
    pts=np.array([c+ax*t_heel+lat*vc(0)*CM, c+ax*t_toe+lat*vc(26)*CM]); mn=pts.min(0)-0.05; mx=pts.max(0)+0.05
    step=0.15*CM
    xs=np.arange(mn[0],mx[0],step); zs=np.arange(mn[1],mx[1],step); ys=np.arange(yb-0.3*CM,YG+2.2*CM,step)
    X,Yg,Z=np.meshgrid(xs,ys,zs,indexing='ij')
    rel=np.stack([X-c[0],Z-c[1]],-1); uu_=((rel@ax)-t_heel)/CM; vv=(rel@lat)/CM; hh=(Yg-yb)/CM
    vcen=vc(uu_); hw=prof(uu_,HW)*hwk; ht=prof(uu_,HT)
    vn=(vv-vcen)/np.maximum(hw,1e-3); mside=np.clip(vn*med,-1,1)             # -1 lateral .. +1 medial
    # oblique, squared toe end (the big-toe side longest) and a round heel
    uend=25.3+0.7*mside; ufront=np.clip((uu_-(uend-2.6))/2.6,0,None); taper_f=np.clip(1-ufront**4,0,1)**0.25
    uback=np.clip((2.4-uu_)/2.4,0,None); taper_b=np.clip(1-uback**2.2,0,1)**(1/2.2)
    tp=np.where(uu_>13,taper_f,taper_b)
    # soft toe ridge: five gentle rises across the toe box near the tips
    ridge=0.22*np.cos(np.pi*4.5*(vn+1)/2)**2*sstep(21.5,23.5,uu_)*(1-sstep(25.0,26.0,uu_))
    top=(ht+ridge)*tp
    # the sole: flat on the lateral side, the medial arch raised under the mid-foot; toes curl up a touch at the tip
    arch=1.4*np.exp(-((uu_-11)/4.2)**2)*sstep(-0.3,0.9,mside)
    bot=arch+0.35*sstep(24.5,26,uu_)
    bot=np.minimum(bot,top*0.6)
    hm=(top+bot)/2; hh2=np.maximum((top-bot)/2,1e-3)
    pv=2.6; ph=np.where(hh>hm,2.2,4.0)
    g=(np.abs(vv-vcen)/np.maximum(hw*tp**0.5,1e-3))**pv+(np.abs(hh-hm)/hh2)**ph
    d_foot=(g**(1/2.4)-1)*np.minimum(hw,hh2)                                  # ~ distance (cm), negative inside
    d_foot=np.where((uu_<0)|(uu_>26.2),np.maximum(d_foot,np.abs(np.clip(uu_-13,-13,13))-13+0.0),d_foot)
    # the leg: Tripo's sock ring, a touch inside it, narrowing a little toward the heel (Achilles, malleoli)
    q=np.stack([X-tc[0],Z-tc[1]],-1); a1=(q@e1); a2=(q@e2)
    HL=[2.0,4.0,6.0,8.0,(YG-yb)/CM,(YG-yb)/CM+2.0]
    fback=np.interp(hh,HL,[0.55,0.62,0.76,0.90,0.97,0.94])                   # the Achilles: the heel bulges out below it
    ffront=np.interp(hh,HL,[0.75,0.86,0.94,0.97,0.97,0.94])
    bk=(a1*np.sign(e1[0]))<0                                                   # behind the leg's centre (heel side)
    fr1=np.where(bk,fback,ffront); fr2=np.interp(hh,HL,[0.70,0.84,0.93,0.97,0.97,0.94])
    d_leg=(np.sqrt((a1/(r1*fr1))**2+(a2/(r2*fr2))**2)-1)*min(r1,r2)/CM
    d_leg=np.maximum(d_leg,np.maximum(1.5-hh,hh-((YG-yb)/CM+2.0)))
    d=smin(d_foot,d_leg,float(os.environ.get('KBL','1.6')))
    d=-smin(-d,hh,0.4)                                                         # flat sole on the footbed (soft edge)
    # the slide: the foot stays CL cm inside its inner surfaces (strap underside and walls, footbed top), so with the
    # slides on nothing shows through the strap
    ins=np.einsum('ij,ij->i',nrmS[slv],np.c_[c[0]+0*slv,yb+0.02+0*slv,c[1]+0*slv][:,[0,1,2]]*0+np.c_[(c+np.outer((P[slv][:,[0,2]]-c)@ax,ax))[:,0],np.full(len(slv),yb+0.02),(c+np.outer((P[slv][:,[0,2]]-c)@ax,ax))[:,1]]-P[slv])>0
    axq=np.c_[(c+np.outer((P[slv][:,[0,2]]-c)@ax,ax))[:,0],np.full(len(slv),yb+0.02),(c+np.outer((P[slv][:,[0,2]]-c)@ax,ax))[:,1]]-P[slv]
    ins=np.einsum('ij,ij->i',nrmS[slv],axq/np.linalg.norm(axq,axis=1,keepdims=True))>0.35   # clearly facing the foot (not the strap's edges)
    ins&=np.sign(P[slv,2])==sg
    ins&=~((nrmS[slv,1]>0.5)&(P[slv,1]>FB+0.004))                         # up-facing bits above the footbed: toe shading, not slide
    iv=slv[ins]; pts_=np.stack([X,Yg,Z],-1).reshape(-1,3)
    dq,kq=cKDTree(P[iv]).query(pts_,distance_upper_bound=0.8*CM); okq=np.isfinite(dq)
    lim=np.full(len(pts_),-1e3); s_=iv[kq[okq]]
    lim[okq]=0.25-np.einsum('ij,ij->i',pts_[okq]-P[s_],nrmS[s_])/CM
    d0=d.copy()
    from scipy.ndimage import gaussian_filter
    lm_=gaussian_filter(np.maximum(lim,-3.0).reshape(d.shape),float(os.environ.get('LSIG','3')))   # a soft press, not a cut
    if not os.environ.get('NOLIM'): d=-smin(-d,-lm_,0.3)
    cut=(d<-0.0)&False
    lm=lim.reshape(d.shape); dbg=(lm>0)&(d0<-0.2)
    if os.environ.get('DBG'):
        print(side,'cut voxels',dbg.sum()); hu=np.histogram(uu_[dbg],bins=np.arange(-1,28,1))[0]; print(' u hist',hu.tolist())
        sel=dbg&(uu_>19); print(' u>19: h',np.percentile(hh[sel],[5,50,95]).round(1) if sel.any() else '-', 'v-vcen',np.percentile((vv-vcen)[sel],[5,50,95]).round(1) if sel.any() else '-')
        si=np.unique(s_[(lim[okq]>0)&(d0.reshape(-1)[okq]<-0.2)&(uu_.reshape(-1)[okq]>19)])
        print(' slide verts responsible',len(si), P[si].min(0).round(3) if len(si) else '', P[si].max(0).round(3) if len(si) else '', 'normals',nrmS[si].mean(0).round(2) if len(si) else '')
        np.save('resp_%s.npy'%side,si)
    verts,faces,_,_=marching_cubes(d,0.0,spacing=(step,step,step))
    verts=verts+np.array([xs[0],ys[0],zs[0]])
    # Taubin smoothing (the marching-cubes steps out, the shape kept)
    nv=len(verts); E=np.r_[faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]; E=np.r_[E,E[:,::-1]]
    from scipy.sparse import coo_matrix as _coo
    A_=_coo((np.ones(len(E)),(E[:,0],E[:,1])),shape=(nv,nv)).tocsr(); A_.data[:]=1; deg=np.asarray(A_.sum(1)).ravel()
    for it in range(12):
        for lam in (0.5,-0.53):
            verts=verts+lam*((A_@verts)/deg[:,None]-verts)
    # decimate (quadric collapse, Blender) to a few thousand triangles per foot
    verts,faces=decimate(verts,faces,int(os.environ.get('NTRI','7000')))
    # keep the main piece, then knock down any decimation spikes and relax a little
    from scipy.sparse.csgraph import connected_components as _cc
    nv=len(verts); E=np.r_[faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]; E=np.r_[E,E[:,::-1]]
    A_=_coo((np.ones(len(E)),(E[:,0],E[:,1])),shape=(nv,nv)).tocsr(); A_.data[:]=1
    _,lab=_cc(A_,directed=False); big=np.argmax(np.bincount(lab)); faces=faces[lab[faces[:,0]]==big]
    deg=np.maximum(np.asarray(A_.sum(1)).ravel(),1)
    for it in range(3):
        mu=(A_@verts)/deg[:,None]; sp=np.linalg.norm(verts-mu,axis=1)>0.35*CM; verts[sp]=mu[sp]
    for it in range(3):
        for lam in (0.5,-0.53): verts=verts+lam*((A_@verts)/deg[:,None]-verts)
    print(side,'spikes fixed',int(sp.sum()))
    print(side,'x min after decimate %.4f'%verts[:,0].min())
    parts.append((verts,faces))
    print(side,'foot %.1f cm, ball %.1f cm, %d verts'%(Lf/CM,2*5.0*hwk,len(verts)))
# merge, unweld (per-triangle UVs), texture from the nearest original sock/toe point
Vs=[];Ts=[];n0=0
for V_,T_ in parts: Vs.append(V_); Ts.append(T_+n0); n0+=len(V_)
V=np.vstack(Vs); T=np.vstack(Ts)
fn=np.cross(V[T[:,1]]-V[T[:,0]],V[T[:,2]]-V[T[:,0]]); vn=np.zeros_like(V)
for j in range(3): np.add.at(vn,T[:,j],fn)
vn/=np.linalg.norm(vn,axis=1,keepdims=True)+1e-12
_,nk=cKDTree(P[srcw]).query(V); vuv=UV[srcw[nk]]
TU=vuv[T]; span=np.max(np.abs(TU-TU.mean(1,keepdims=True)).max(2),1); bad=span>float(os.environ.get('SPAN','0.01'))
TU[:]=SK
# the knit: per new triangle near the ankle, Tripo's own sock UVs from the band just above the join (same angle around
# the leg, one UV island, local affine fit), mirrored downward so the ribs carry on at their scale and the join at YG
# is continuous
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
BAND=float(os.environ.get('BAND','0.014'))
srcT=I[gone&(L>float(os.environ.get('KL','185')))&(P[I][:,:,1].min(1)>0.03)&(P[I][:,:,1].max(1)<YG+0.004)]   # Tripo's visible sock (the replaced surface)
sv_=np.unique(srcT.ravel()); n_=len(P)
g_=coo_matrix((np.ones(len(srcT)*3),(np.r_[srcT[:,0],srcT[:,1],srcT[:,2]],np.r_[srcT[:,1],srcT[:,2],srcT[:,0]])),shape=(n_,n_))
_,isl=connected_components(g_,directed=False)
knit=0
for ti in range(len(T)):
    g=V[T[ti]].mean(0); sg=1 if g[2]>0 else -1
    if sg not in tubes or V[T[ti]][:,1].min()<FB+float(os.environ.get('KFLOOR','0.012')): continue
    tc_,e1_,e2_,r1_,r2_=tubes[sg]
    def th(p): d=p[[0,2]]-tc_; return np.arctan2((d@e2_)/r2_,(d@e1_)/r1_)
    d=g[[0,2]]-tc_
    if np.hypot((d@e1_)/r1_,(d@e2_)/r2_)>1.45: continue                 # the toes keep the plain sock colour
    cand_=sv_[np.sign(P[sv_,2])==sg]
    thc=th(g); ths=np.array([th(p) for p in P[cand_]]); dth=np.angle(np.exp(1j*(ths-thc)))
    w_=np.abs(dth)<np.radians(14)
    if w_.sum()<6: continue
    ids,cnt=np.unique(isl[cand_[w_]],return_counts=True); best=ids[np.argmax(cnt)]
    m_=w_&(isl[cand_]==best)
    if m_.sum()<6: continue
    A=np.c_[dth[m_],P[cand_[m_],1],np.ones(m_.sum())]; coef,*_=np.linalg.lstsq(A,UV[cand_[m_]],rcond=None)
    ylo,yhi=P[cand_[m_],1].min(),P[cand_[m_],1].max()
    out=[]
    for p in V[T[ti]]:
        yr=min(max(p[1],ylo),yhi)                                        # where the strap hid the sock, the ribs run on
        out.append(np.array([np.angle(np.exp(1j*(th(p)-thc))),yr,1.0])@coef)
    out=np.array(out); smp=np.vstack([out,out.mean(0)[None],(out[[0,1,2]]+out[[1,2,0]])/2])
    if tex(smp).mean(1).min()<float(os.environ.get('DARKK','170')): continue   # an island edge: keep the plain sock colour
    TU[ti]=out; knit+=1
print('knit-textured triangles',knit,'of',len(T))
bad[:]=False
VV=V[T].reshape(-1,3).astype(np.float32); NN=vn[T].reshape(-1,3).astype(np.float32); UU=TU.reshape(-1,2).astype(np.float32); TT=np.arange(len(VV),dtype=np.uint32)
# skin: per welded vertex, the 4 nearest originals' weights blended per joint, then smoothed over the new surface (no
# single vertex may follow a different bone from its neighbours), the top 4 kept
d,k=cKDTree(P[fv]).query(V,k=4); src=fv[k]; ws=1/np.maximum(d,1e-5)**2; ws/=ws.sum(1,keepdims=True)
NJ=int(J.max())+1; acc=np.zeros((len(V),NJ))
for q in range(4):
    for r in range(J.shape[1]): np.add.at(acc,(np.arange(len(V)),J[src[:,q],r].astype(int)),W[src[:,q],r]*ws[:,q])
# below the ankle the sock belongs to the foot: Tripo's skin gives the heel to the calf (twist) bones, which tears the
# heel off the foot when it points (lying down); the calf's share fades to the Foot bone under the ankle joint
hcm=(V[:,1]-FB)/CM; fz=1-np.clip((hcm-5.0)/4.0,0,1); fz=fz*fz*(3-2*fz)
for foot_,calves in ((5,(4,7,8)),(15,(14,17,18))):
    for cj in calves: mv=acc[:,cj]*fz; acc[:,cj]-=mv; acc[:,foot_]+=mv
from scipy.sparse import coo_matrix as _c2
E=np.r_[T[:,[0,1]],T[:,[1,2]],T[:,[2,0]]]; E=np.r_[E,E[:,::-1]]
A2=_c2((np.ones(len(E)),(E[:,0],E[:,1])),shape=(len(V),len(V))).tocsr(); A2.data[:]=1; dg=np.asarray(A2.sum(1)).ravel()[:,None]
for it in range(int(os.environ.get('WSM','6'))): acc=0.5*acc+0.5*(A2@acc)/np.maximum(dg,1)
Jv=np.argsort(-acc,1)[:,:4]; Wv=np.take_along_axis(acc,Jv,1); Wv/=Wv.sum(1,keepdims=True)
Jn=Jv[T].reshape(-1,4).astype(np.uint16); Wn=Wv[T].reshape(-1,4).astype(np.float32)
VV.tofile('footfill_pos.bin'); NN.tofile('footfill_nrm.bin'); UU.tofile('footfill_uv.bin'); Jn.tofile('footfill_j.bin'); Wn.tofile('footfill_w.bin'); TT.tofile('footfill_idx.bin')
print('new sock tris',len(T),'plain-texel tris (UV seams)',int(bad.sum()))
