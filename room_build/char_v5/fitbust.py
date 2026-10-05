# fit the Tripo bust (head + bare neck) onto the owner's placed head: similarity ICP on the face and hair, starting from
# the upper-head bounding boxes. Writes bust_fit.npy (scale, rotation, translation) for stage1.
import numpy as np, os
from scipy.spatial import cKDTree
exec(open('load.py').read())
S=0.166; T=np.array([0.078-S*0.418, 0.873-S*0.365-float(os.environ.get('DROPHEAD','0.005')), -0.006])
hP,*_=load('head',True); Q=hP*S+T                                   # owner head in body space
Bp=np.fromfile('bust_pos.bin',np.float32).reshape(-1,3).astype(np.float64)
def upper(P,f): y0=P[:,1].max()-(P[:,1].max()-P[:,1].min())*f; return P[P[:,1]>y0]
tq=upper(Q,0.55)                                                   # owner: face and hair, above the collar
sb=upper(Bp,0.45)                                                  # bust: face and hair, above the neck
s=(np.ptp(tq,0)/np.ptp(sb,0)).mean(); R=np.eye(3); t=tq.mean(0)-s*sb.mean(0)
rng=np.random.default_rng(0); tree=cKDTree(tq); src=sb[rng.choice(len(sb),min(20000,len(sb)),replace=False)]
for it in range(40):
    X=s*src@R.T+t; d,k=tree.query(X); keep=d<np.percentile(d,85); A=src[keep]; B=tq[k[keep]]
    ma,mb=A.mean(0),B.mean(0); Ac,Bc=A-ma,B-mb; U,Sg,Vt=np.linalg.svd(Bc.T@Ac/len(A)); D=np.eye(3); D[2,2]=np.sign(np.linalg.det(U@Vt))
    R=U@D@Vt; s=(Sg*np.diag(D)).sum()/((Ac**2).sum()/len(A)); t=mb-s*R@ma
    if it%10==9: print(it,'median dist',np.median(d).round(5),'scale',round(s,4))
np.save('bust_fit.npy',np.concatenate([[s],R.ravel(),t])); print('rotation deg',np.degrees(np.arccos(np.clip((np.trace(R)-1)/2,-1,1))).round(2))
