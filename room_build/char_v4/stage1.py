# owner head: cut collar, fit to body (glTF coords), save hi-poly .blend
import bpy, bmesh, numpy as np, time, os
exec(open('load.py').read())
S=0.166; T=np.array([0.078-S*0.418, 0.873-S*0.365, -0.006])
hP,hUV,hI,_=load('head',True); hs=skin(colors('head',hUV))
keep=(hP[:,1]>0.13+(0.25-hP[:,0])*0.42)|(hs&(hP[:,1]>0.10)&(hP[:,0]>-0.1))   # slanted cut just above the owner's collar line; skin in front of the ears always kept (jaw)
keep&=~((hP[:,1]<0.33)&(np.abs(hP[:,2])>0.25)&(hP[:,0]>-0.15))   # collar sides outside the jaw
if os.environ.get('FULL'): keep[:]=True   # the owner's whole bust: neck and collar kept
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
_,wid=np.unique(np.round(hP*2e5).astype(np.int64),axis=0,return_inverse=True); wid=wid.ravel()
f=wid[hI[keep[hI].all(1)]]; n=wid.max()+1
g=coo_matrix((np.ones(len(f)*2),(np.r_[f[:,0],f[:,1]],np.r_[f[:,1],f[:,2]])),shape=(n,n))
nc,lab=connected_components(g,directed=False); lab=lab[wid]; cnt=np.bincount(lab[keep],minlength=nc)
keep&=cnt[lab]>=5000
print('keep',keep.sum(),'of',len(keep),'components kept',(cnt>=5000).sum())
bpy.ops.wm.read_factory_settings(use_empty=True)
t=time.time(); bpy.ops.import_scene.gltf(filepath='head_owner.glb'); print('import',time.time()-t)
ob=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]; me=ob.data
print('blender verts',len(me.vertices))
assert len(me.vertices)==len(keep)
Hs=hP.copy(); ST=float(os.environ.get('STRETCH','0')); Y0=0.08
if ST: Hs[:,1]=np.where(Hs[:,1]<Y0, Hs[:,1]-(Y0-Hs[:,1])*ST, Hs[:,1])   # stretch only the band below the chin (collar, lower neck) downward
Q=Hs*S+T                                  # glTF coords, body space
co=np.stack([Q[:,0],-Q[:,2],Q[:,1]],1)    # to Blender Z-up
ob.matrix_world.identity()
for p in [ob.parent] if ob.parent else []: pass
me.vertices.foreach_set('co',co.astype(np.float32).ravel()); me.update()
bm=bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[bm.verts[i] for i in np.nonzero(~keep)[0]],context='VERTS'); bm.to_mesh(me); bm.free()
# drop tiny loose pieces
bpy.context.view_layer.objects.active=ob; ob.select_set(True)
print('after cut verts',len(me.vertices),'polys',len(me.polygons))
ob.name='head_hi'
bpy.ops.wm.save_as_mainfile(filepath='head_hi.blend')
bpy.ops.export_scene.gltf(filepath='head_hi.glb',use_selection=True,export_yup=True,export_format='GLB')
