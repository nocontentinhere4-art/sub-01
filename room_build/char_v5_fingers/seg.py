import numpy as np, json
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
P=np.fromfile('b_pos.bin',np.float32).reshape(-1,3).astype(np.float64); I=np.fromfile('b_idx.bin',np.uint32).reshape(-1,3)
J=np.fromfile('b_j.bin',np.uint16).reshape(-1,4); W=np.fromfile('b_w.bin',np.float32).reshape(-1,4)
s=json.load(open('b_skin.json')); names=s['joints']; ibm=np.array(s['ibm']).reshape(-1,4,4).transpose(0,2,1)
_,wid=np.unique(np.round(P*1e5).astype(np.int64),axis=0,return_inverse=True); wid=wid.ravel()
def comps(mask):
    t=I[mask[I].all(1)]; tw=wid[t]; n=wid.max()+1
    g=coo_matrix((np.ones(len(tw)*3),(np.r_[tw[:,0],tw[:,1],tw[:,2]],np.r_[tw[:,1],tw[:,2],tw[:,0]])),shape=(n,n))
    _,lab=connected_components(g,directed=False); return lab[wid]
def frame(side):
    h=names.index(f'{side}_Hand'); B=np.linalg.inv(ibm[h]); w0=B[:3,3]
    hw=(W*(J==h)).sum(1); m=hw>0.3
    Q=P[m]; far=Q[np.argsort(-np.linalg.norm(Q-w0,axis=1))[:200]].mean(0); d=(far-w0)/np.linalg.norm(far-w0)
    return h,w0,d,m
if __name__=='__main__':
    for side in 'LR':
        h,w0,d,m=frame(side); t=(P-w0)@d
        print(side,'wrist',w0.round(4),'dir',d.round(3),'len',t[m].max().round(4))
        for cut in np.linspace(0.3,0.75,10)*t[m].max():
            mk=m&(t>cut); lab=comps(mk); u,c=np.unique(lab[mk],return_counts=True); c=sorted(c,reverse=True)[:7]
            print('  cut %.4f'%cut, c)
