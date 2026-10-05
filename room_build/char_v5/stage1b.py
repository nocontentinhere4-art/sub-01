# the Tripo bust (head and bare neck) placed by fitbust.py, cut below the neck inside the hood; hi-poly GLB for simp.mjs
import bpy, bmesh, numpy as np, os
f=np.load('bust_fit.npy'); s=f[0]; R=f[1:10].reshape(3,3); t=f[10:13]; CUT=float(os.environ.get('CUT','0.79'))
P=np.fromfile('bust_pos.bin',np.float32).reshape(-1,3).astype(np.float64); Q=s*P@R.T+t
c=np.array([Q[(Q[:,1]>0.83)&(Q[:,1]<0.84),0].mean(),Q[(Q[:,1]>0.83)&(Q[:,1]<0.84),2].mean()])
rr=np.hypot(Q[:,0]-c[0],Q[:,2]-c[1])
keep=(Q[:,1]>CUT)&~((Q[:,1]<float(os.environ.get('SHY','0.845')))&(rr>float(os.environ.get('SHR','0.05')))&(Q[:,0]<c[0]+0.03))   # no shoulders: neck only below the jaw line
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath='../v5/bust3d.glb')
ob=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]; me=ob.data; assert len(me.vertices)==len(Q)
ob.matrix_world.identity()
me.vertices.foreach_set('co',np.stack([Q[:,0],-Q[:,2],Q[:,1]],1).astype(np.float32).ravel()); me.update()
bm=bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[bm.verts[i] for i in np.nonzero(~keep)[0]],context='VERTS')
edges=[e for e in bm.edges if e.is_boundary]                                     # close small holes (nostrils), not the neck cut
loops=bmesh.ops.holes_fill(bm,edges=edges,sides=40)
bm.to_mesh(me); bm.free()
bpy.context.view_layer.objects.active=ob; ob.select_set(True)
print('bust verts kept',int(keep.sum()),'faces',len(me.polygons))
bpy.ops.export_scene.gltf(filepath='head_hi.glb',use_selection=True,export_yup=True,export_format='GLB')
