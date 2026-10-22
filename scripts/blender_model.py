"""Load the editable .blend model while retaining the vanilla animated rear body."""
import json,os,shutil,subprocess
from pathlib import Path
import numpy as np
from asset_io import HERE,gltf

def load_model():
    configured=os.environ.get('BPD_BLENDER') or shutil.which('blender')
    if not configured:
        installed=sorted(Path('C:/Program Files/Blender Foundation').glob('Blender */blender.exe'))
        configured=str(installed[-1]) if installed else ''
    if not configured or not Path(configured).is_file():raise RuntimeError('Set BPD_BLENDER to the Blender executable.')
    model=HERE.parent/'models/backpack-deluxe.blend'
    out=HERE/'blender-export'
    subprocess.run([configured,'--background',str(model),'--python',str(HERE/'export_blender_model.py'),'--',str(out)],check=True,capture_output=True,timeout=120)
    data=json.loads((out/'model.json').read_text());arrays=np.load(out/'geometry.npz')
    parts=[{'name':p['name'],'mat':p['mat'],'v':arrays[p['key']+'_v'],'f':arrays[p['key']+'_f']} for p in data['parts']]

    # Keep native animations, shoulder joints and rear geometry. These objects
    # in the Blender file are reference meshes; editable front objects above
    # are the geometry actually supplied by the Blender source.
    _,a,indices=gltf(HERE/'exports/Models/backpack_mk2/backpack_mk2.gltf')
    positions=a['POSITION'][:,[0,2,1]]*100
    groups=json.loads((HERE/'native-connected-parts.json').read_text())
    keep=np.ones(len(indices),bool)
    for group in groups:
        ids=np.array(group['indices']);points=positions[np.unique(indices[ids])]
        if group['root_only'] and group['id']!=8663 and points[:,0].max()<0:keep[ids]=False
    main=next(g for g in groups if g['id']==8663)
    for i in main['indices']:
        centre=positions[indices[i]].mean(0)
        if centre[0]<-5.5 and centre[2]<75 and abs(centre[1])<59:keep[i]=False
    return {'parts':parts,'keep':keep,'PALETTE_BINDINGS':data['palette_bindings']}
