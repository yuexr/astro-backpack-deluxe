"""Read authored meshes from Blender for packaging; creates no model geometry."""
import json,sys
from pathlib import Path
import bpy
import numpy as np

out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True)
parts=[];arrays={}
objects=sorted((o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('build_role')=='custom_front'),key=lambda o:int(o['part_order']))
assert objects,'No custom_front components in the Blender model.'
depsgraph=bpy.context.evaluated_depsgraph_get()
for index,obj in enumerate(objects):
    evaluated=obj.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh();mesh.calc_loop_triangles()
    world=np.array([evaluated.matrix_world@v.co for v in mesh.vertices],dtype=float)
    vertices=world[:,[0,2,1]]*np.array([100,100,-100])
    # glTF imports can duplicate positions at flat-normal seams. The native
    # mesh builder computes its own normals, so weld positions for its capacity.
    vertices,remap=np.unique(np.round(vertices,6),axis=0,return_inverse=True)
    faces=remap[np.array([t.vertices[:] for t in mesh.loop_triangles],dtype=int)]
    assert len(faces) and np.isfinite(vertices).all(),obj.name
    assert not np.any((faces[:,0]==faces[:,1])|(faces[:,1]==faces[:,2])|(faces[:,0]==faces[:,2])),obj.name
    key=f'p{index}'
    arrays[key+'_v']=vertices;arrays[key+'_f']=faces
    parts.append({'name':obj['component_name'],'mat':obj['palette_role'],'key':key})
    evaluated.to_mesh_clear()
np.savez_compressed(out/'geometry.npz',**arrays)
(out/'model.json').write_text(json.dumps({'parts':parts,'palette_bindings':json.loads(bpy.context.scene['native_palette_bindings'])},indent=2))
print(f'Exported {len(parts)} existing Blender mesh components for packaging.')
