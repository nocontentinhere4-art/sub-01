# a dark crew-neck T-shirt: a round collar band (about 1.5 cm high, rounded) that follows his neck's bottom edge and
# covers it, then the T-shirt continuing down inside the hood. Appended to the head geometry (headx_*.bin), coloured
# from a dark texel of his hair; graft.mjs reads it.
import numpy as np, os
from PIL import Image
P=np.fromfile('headlo_pos.bin',np.float32).reshape(-1,3); N=np.fromfile('headlo_nrm.bin',np.float32).reshape(-1,3)
UV=np.fromfile('headlo_uv.bin',np.float32).reshape(-1,2); I=np.fromfile('headlo_idx.bin',np.uint32).reshape(-1,3)
PE=np.fromfile(os.environ['EDGE'],np.float32).reshape(-1,3) if os.environ.get('EDGE') else P
ymin=PE[:,1].min(); ring=PE[:,1]<ymin+0.012
c=np.array([PE[ring,0].mean(),PE[ring,2].mean()]); SEG=72
a=np.arctan2(PE[:,2]-c[1],PE[:,0]-c[0]); r=np.hypot(PE[:,0]-c[0],PE[:,2]-c[1])
neck=(r<float(os.environ.get('NR','0.045')))&(PE[:,1]<ymin+0.035)
edges=np.linspace(-np.pi,np.pi,SEG+1); E=np.full((SEG,3),np.nan)
for i in range(SEG):
    k=np.nonzero(neck&(a>=edges[i])&(a<edges[i+1]))[0]
    if len(k)==0: continue
    yl=PE[k,1].min(); kk=k[PE[k,1]<yl+0.004]; E[i]=((edges[i]+edges[i+1])/2,yl,np.median(r[kk]))
for col in (1,2):
    bad=np.isnan(E[:,col]); E[bad,col]=np.interp(np.nonzero(bad)[0],np.nonzero(~bad)[0],E[~bad,col],period=SEG)
E[:,0]=(edges[:-1]+edges[1:])/2
for _ in range(3):
    for col in (1,2): E[:,col]=(np.roll(E[:,col],1)+2*E[:,col]+np.roll(E[:,col],-1))/4
E[:,2]=np.clip(E[:,2],0.022,None)
H=0.0084                                                             # 1.5 cm at 1.786 m per Tripo unit
# profile, top to bottom: (dy from the edge, dr from the neck radius); the top tucks onto the skin
prof=[(0.6*H,-0.0003),(0.45*H,0.0015),(0.2*H,0.0028),(-0.05*H,0.0032),(-0.3*H,0.0028),(-0.4*H,0.0022)]
YB=float(os.environ.get('TY','0.775')); RB=float(os.environ.get('TR','0.012'))
im=np.asarray(Image.open('headlo_base.jpeg').convert('RGB')).astype(np.float32); h,w=im.shape[:2]
hair=np.nonzero(P[:,1]>P[:,1].max()-0.01)[0]
cols=im[(UV[hair,1]%1*h).astype(int).clip(0,h-1),(UV[hair,0]%1*w).astype(int).clip(0,w-1)].mean(1)
SK=UV[hair[np.argsort(np.abs(cols-np.percentile(cols,30)))[0]]]
D=float(os.environ.get('NECKD','0.02'))                              # neck continued straight down below his edge
band=np.nonzero((np.hypot(P[:,0]-c[0],P[:,2]-c[1])<0.045)&(P[:,1]<P[:,1].min()+0.03))[0]
x_=(UV[band,0]%1*w).astype(int).clip(4,w-5); y_=(UV[band,1]%1*h).astype(int).clip(4,h-5); colb=im[y_,x_]; med=np.median(colb,0)
var=np.array([im[yy-4:yy+5,xx-4:xx+5].reshape(-1,3).std(0).sum() for xx,yy in zip(x_,y_)]); med=med*float(os.environ.get('BRIGHT','1.12'))
SKN=UV[band[np.argmin(np.abs(colb-med).sum(1)+2*var)]]
rows=[]; uvs=[]
for dy,dr in ([] if D==0 else [(float(os.environ.get('TOPDY','0.009')),-0.0018),(0.003,-0.0006),(-0.3*D,0.0),(-0.65*D,0.0003),(-D-0.001,0.0006)]):      # skin, starting just inside his edge
    rows.append([(E[i,0],E[i,1]+dy,E[i,2]+dr) for i in range(SEG)]); uvs.append(SKN)
E=E.copy(); E[:,1]-=D; E[:,2]+=0.0006*(D>0)
nskin=len(rows)
for dy,dr in prof: rows.append([(E[i,0],E[i,1]+dy,E[i,2]+dr) for i in range(SEG)]); uvs.append(SK)
for f in (0.25,0.5,0.75,1.0):                                      # the T-shirt below the collar, flaring into the hood
    rows.append([(E[i,0],(E[i,1]-0.4*H)*(1-f)+YB*f,E[i,2]+0.0022+RB*f**1.3) for i in range(SEG)]); uvs.append(SK)
V=[];NN=[];UVX=[]
for j,row in enumerate(rows):
    for th,y,rad in row:
        UVX.append(uvs[j])
        V.append([c[0]+rad*np.cos(th),y,c[1]+rad*np.sin(th)])
        jj=j-nskin; ny=0.0 if jj<0 else (0.6 if jj==0 else (0.3 if jj==1 else (-0.3 if jj in (4,5) else 0.0))); NN.append([np.cos(th),ny,np.sin(th)])
V=np.array(V,np.float32); NN=np.array(NN,np.float32); NN/=np.linalg.norm(NN,axis=1,keepdims=True); n0=len(P); T=[]
for j in range(len(rows)-1):
    for i in range(SEG):
        p=n0+j*SEG+i; q=n0+j*SEG+(i+1)%SEG; T+=[[p,q,p+SEG],[q,q+SEG,p+SEG]]
np.concatenate([P,V]).astype(np.float32).tofile('headx_pos.bin'); np.concatenate([N,NN]).astype(np.float32).tofile('headx_nrm.bin')
np.concatenate([UV,np.array(UVX,np.float32)]).astype(np.float32).tofile('headx_uv.bin'); np.concatenate([I,np.array(T,np.uint32)]).astype(np.uint32).tofile('headx_idx.bin')
print('neck centre',c.round(4),'edge y',E[:,1].min().round(3),E[:,1].max().round(3),'r',E[:,2].min().round(3),E[:,2].max().round(3))
