# test poses (fist, pinch, phone grip) as extra local rotations of the finger joints, for QA renders only
import numpy as np, json
exec(open('seg.py').read().split("if __name__")[0])
RY=np.array([[0,0,1],[0,1,0],[-1,0,0]],float)
F={q['name']:np.array(q['pos']) for q in json.load(open('fingers.json'))['joints']}
def qax(axis,deg):
    a=axis/np.linalg.norm(axis); h=np.radians(deg)/2; return np.r_[a*np.sin(h),np.cos(h)]
def rotm(axis,deg):
    a=axis/np.linalg.norm(axis); t=np.radians(deg); K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]]); return np.eye(3)+np.sin(t)*K+(1-np.cos(t))*K@K
def m2q(M):
    w=np.sqrt(max(0,1+M[0,0]+M[1,1]+M[2,2]))/2; x=(M[2,1]-M[1,2])/(4*w); y=(M[0,2]-M[2,0])/(4*w); z=(M[1,0]-M[0,1])/(4*w); return np.array([x,y,z,w])
def aim(v,t):
    v=v/np.linalg.norm(v); t=t/np.linalg.norm(t); ax=np.cross(v,t); s=np.linalg.norm(ax); c=v@t
    if s<1e-6: return np.eye(3)
    return rotm(ax,np.degrees(np.arctan2(s,c)))
TIPS={}
def tip_of(side,base):
    # fingertip used by fingers.py: rebuild from the last joint direction (2nd->3rd) scaled like the distal phalanx
    p2=F[f'{base}-2.{side}']; p3=F[f'{base}-3.{side}']; return p3+(p3-p2)*(0.86 if base!='finger1' else 0.9)
def pose(kind):
    out={}
    for side in 'LR':
        h,w0,d,m=frame(side); n=np.array([0,0,1.0]) if side=='L' else np.array([0,0,-1.0]); n=n-d*(n@d); n/=np.linalg.norm(n)
        bend=np.cross(d,n)
        ang={'fist':(80,95,60),'pinch':(35,45,20),'phone':(55,50,30)}[kind]
        idx_ang={'pinch':(40,50,25)}.get(kind,ang)
        chains={}
        for k in range(2,6):
            a3=idx_ang if (k==2) else (ang if kind!='pinch' else (25,30,15))
            pts=[F[f'finger{k}-{i}.{side}'] for i in (1,2,3)]+[tip_of(side,f'finger{k}')]
            P_=[p.copy() for p in pts]
            for i,th in enumerate(a3):
                R=rotm(bend,th)
                for j in range(i+1,4): P_[j]=P_[i]+R@(P_[j]-P_[i])
                out[f'finger{k}-{i+1}.{side}']=qax(RY.T@bend,th).tolist()
            chains[k]=P_
        cmc,mcp,ip=[F[f'finger1-{i}.{side}'] for i in (1,2,3)]; tt=tip_of(side,'finger1')
        if kind=='fist': tgt=chains[3][1]+n*0.004-d*0.002
        elif kind=='pinch': tgt=chains[2][3]
        else: tgt=chains[2][0]+n*0.012+d*0.016
        Ra0=aim(tt-cmc,tgt-cmc); fac={'fist':0.7,'pinch':1.0,'phone':0.8}[kind]
        ax_=np.array([Ra0[2,1]-Ra0[1,2],Ra0[0,2]-Ra0[2,0],Ra0[1,0]-Ra0[0,1]]); ang_=np.degrees(np.arccos(np.clip((np.trace(Ra0)-1)/2,-1,1)))
        Ra=rotm(ax_,ang_*fac) if np.linalg.norm(ax_)>1e-9 else np.eye(3)
        out[f'finger1-1.{side}']=m2q(RY.T@Ra@RY).tolist()
        td=Ra@(tt-cmc); tb=np.cross(td,n); 
        c2,c3={'fist':(20,30),'pinch':(10,15),'phone':(10,10)}[kind]
        out[f'finger1-2.{side}']=qax(RY.T@Ra.T@tb,c2).tolist(); out[f'finger1-3.{side}']=qax(RY.T@Ra.T@tb,c3).tolist()
    json.dump(out,open(f'pose_{kind}.json','w'))
for k in ('fist','pinch','phone'): pose(k)
print('ok')
