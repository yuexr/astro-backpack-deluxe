"""Local vanilla asset reader; generated inputs live beside the source and are ignored by Git."""
import json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def gltf(path):
    d=json.loads(path.read_text());blob=path.with_suffix('.bin').read_bytes()
    def ac(i):
        a=d['accessors'][i];b=d['bufferViews'][a['bufferView']]
        n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        return np.frombuffer(blob,{5126:'<f4',5123:'<u2',5121:'u1'}[a['componentType']],count=a['count']*n,offset=b.get('byteOffset',0)+a.get('byteOffset',0)).reshape(-1,n)
    p=d['meshes'][0]['primitives'][0]
    return d,{k:ac(i).copy() for k,i in p['attributes'].items()},ac(p['indices']).reshape(-1,3).copy()
