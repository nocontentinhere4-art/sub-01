# finger bones for the v5 body (MakeHuman names, parents and world-aligned rest frames), placed in the hand mesh,
# with smooth weights along each finger. Writes fingers.json (joints) and new JOINTS_0/WEIGHTS_0 (nf_j.bin, nf_w.bin).
import numpy as np, json
exec(open('seg.py').read().split("if __name__")[0])
RY=np.array([[0,0,1],[0,1,0],[-1,0,0]],float)        # rest frame: MakeHuman's (faces +Z) turned to face +X
PROP=(0.46,0.29)                                     # proximal and middle phalanx, as fractions of knuckle-to-tip
CUTS={'L':(0.0283,0.0445),'R':(0.0338,0.0507)}       # (thumb splits off, fingers split off), along the hand axis
def axis_of(Q):
    c=Q.mean(0); u,s,vt=np.linalg.svd(Q-c); a=vt[0]; return c,a
def smooth(x,b,h): return np.clip((x-(b-h))/(2*h),0,1)**2*(3-2*np.clip((x-(b-h))/(2*h),0,1))
joints=[]; NJ=len(names)
newJ=J.astype(np.int64).copy(); newW=W.astype(np.float64).copy()
for side in 'LR':
    h,w0,d,m=frame(side); t=(P-w0)@d; cth,cf=CUTS[side]
    # fingers: components below the web, ordered front (+X, next to the thumb) to back
    mk=m&(t>cf); lab=comps(mk); u,c=np.unique(lab[mk],return_counts=True)
    big=[b for b in u[c>60]]; cen={b:P[mk&(lab==b)].mean(0) for b in big}
    big=sorted(big,key=lambda b:-cen[b][0]); thumb_tipcomp,fingers=big[0],big[1:5]
    # thumb: the component that splits off first, the one holding the thumb tip
    mt=m&(t>cth); labt=comps(mt); tl=labt[np.nonzero(mk&(lab==thumb_tipcomp))[0][0]]; thumbset=mt&(labt==tl)
    palmn=np.cross(d,np.array([1.0,0,0])); palmn/=np.linalg.norm(palmn)
    if side=='L' and palmn[2]<0: palmn=-palmn
    if side=='R' and palmn[2]>0: palmn=-palmn
    chains=[]
    Q=P[thumbset]; c0,a=axis_of(Q); a=a if (Q[np.argmax(t[thumbset])]-c0)@a>0 else -a
    us=(Q-c0)@a; tip=c0+a*us.max()*0.92; mcp=c0+a*us.min(); cmc=mcp-a*0.014; ip=mcp+(tip-mcp)*0.55
    chains.append(('finger1',None,[cmc,mcp,ip],tip,thumbset,(0.012,0.005,0.003)))
    for k,b in enumerate(fingers):
        sel=mk&(lab==b); Q=P[sel]; c0,a=axis_of(Q); a=a if a@d>0 else -a
        us=(Q-c0)@a; tip=c0+a*us.max()*0.95; web=c0+a*us.min(); mcp=web-a*0.008
        L_=np.linalg.norm(tip-mcp); pip=mcp+a*L_*PROP[0]; dip=pip+a*L_*PROP[1]
        meta=w0+(mcp-w0)*0.35
        chains.append((f'finger{k+2}',(f'metacarpal{k+1}',meta),[mcp,pip,dip],tip,sel,(0.006,0.003,0.0025)))
    sfx='.'+side
    for base,meta,pts,tip,sel,hw in chains:
        par=f'{side}_Hand'
        if meta: joints.append(dict(name=meta[0]+sfx,parent=par,pos=meta[1].tolist())); par=meta[0]+sfx
        for i,p in enumerate(pts):
            joints.append(dict(name=f'{base}-{i+1}{sfx}',parent=par,pos=p.tolist())); par=f'{base}-{i+1}{sfx}'
    # weights: each hand vertex goes to its finger (component, or the nearest finger axis near the knuckles)
    idx=np.nonzero(m)[0]; best=np.full(len(idx),-1); bestd=np.full(len(idx),9.0); upar=np.zeros(len(idx))
    for ci,(base,meta,pts,tip,sel,hw) in enumerate(chains):
        a=(tip-pts[0])/np.linalg.norm(tip-pts[0]); rel=P[idx]-pts[0]; uu=rel@a
        perp=np.linalg.norm(rel-np.outer(uu,a),axis=1)
        insel=sel[idx]; dist=np.where(insel,-1.0,perp+np.where(uu<-hw[0],9,0))
        better=dist<bestd; best[better]=ci; bestd[better]=dist[better]
    for k,v in enumerate(idx):
        ci=best[k]
        if ci<0 or bestd[k]>(0.016 if ci==0 else 0.011): continue
        base,meta,pts,tip,sel,hw=chains[ci]
        segs=[pts[0],pts[1],pts[2],tip]; 
        # continuous position along the chain
        a0=(segs[1]-segs[0]); u0=(P[v]-segs[0])@a0/(a0@a0)*np.linalg.norm(a0)
        a1=(segs[2]-segs[1]); u1=(P[v]-segs[1])@a1/(a1@a1)*np.linalg.norm(a1)
        a2=(segs[3]-segs[2]); u2=(P[v]-segs[2])@a2/(a2@a2)*np.linalg.norm(a2)
        r0=smooth(u0,0,hw[0]); r1=smooth(u1,0,hw[1]); r2=smooth(u2,0,hw[2])
        wb=[r0-r1, r1-r2, r2]; wb=[max(0,x) for x in wb]; s_=sum(wb)
        if s_<1e-4: continue
        wb=[x*r0/s_ for x in wb]                         # finger total = r0
        names_=[f'{base}-{i+1}.{side}' for i in range(3)]
        cand={}
        for j_,w_ in zip(J[v],W[v]): cand[int(j_)]=cand.get(int(j_),0)+w_*(1-r0)
        for nm,w_ in zip(names_,wb):
            ji=NJ+[q['name'] for q in joints].index(nm); cand[ji]=cand.get(ji,0)+w_
        top=sorted(cand.items(),key=lambda x:-x[1])[:4]; tot=sum(x[1] for x in top)
        newJ[v]=[x[0] for x in top]+[0]*(4-len(top)); newW[v]=[x[1]/tot for x in top]+[0]*(4-len(top))
    print(side,'thumb verts',int(thumbset.sum()),'finger verts',[int((mk&(lab==b)).sum()) for b in fingers],'hand verts',int(m.sum()),'reassigned',int((best>=0).sum()))
for q in joints:
    M=np.eye(4); M[:3,:3]=RY; M[:3,3]=q['pos']; q['bind']=M.tolist()
json.dump(dict(joints=joints,palm_axes={}),open('fingers.json','w'),indent=0)
newJ.astype(np.uint16).tofile('nf_j.bin'); newW.astype(np.float32).tofile('nf_w.bin')
print('joints added',len(joints))
for q in joints[:8]: print(q['name'],q['parent'],np.round(q['pos'],4))
