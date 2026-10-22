"""Regenerate ignored source assets from the user's base-game PAK, never deployed mods."""
import hashlib,json,subprocess
import numpy as np
from asset_io import HERE,gltf
from investigate import UMODEL,extract

def prepare():
    # Read just the input mesh/skeleton, blueprint sources and atlas textures.
    # -notex prevents UE Viewer from resolving unrelated material dependencies.
    for asset in ['Models/backpack_mk2/backpack_mk2','Items/BackpackRail','Character/AstroCorpse']:
        extract('Astro/Content/'+asset)
    extract('Astro/Content/Models/backpack_mk2/backpack_mk2_Skeleton',as_json=False)
    meshes=['Astro/Content/Models/backpack_mk2/backpack_mk2','Engine/Content/BasicShapes/Cylinder']
    for asset in meshes:
        source=extract(asset,as_json=False)
        subprocess.run([str(UMODEL),'-export','-gltf','-noanim','-notex','-game=ue4.27',
                        '-path='+str(HERE/'vanilla'),'-out='+str(HERE/'exports'),str(source)],
                       check=True,capture_output=True,timeout=90)
    for texture in ['diffuse','masks_color','masks_shade','masks_other','masks_physical']:
        source=extract('Astro/Content/Textures/palette_exo_suit_'+texture,as_json=False)
        subprocess.run([str(UMODEL),'-export','-game=ue4.27','-path='+str(HERE/'vanilla'),
                        '-out='+str(HERE/'exports'),str(source)],check=True,capture_output=True,timeout=90)

    # The authored selection map identifies exactly which original triangles to
    # retain/replace. Reject a different source build before using its indices.
    manifest=json.loads((HERE/'mesh-parts.json').read_text())
    mesh=HERE/'vanilla/Astro/Content/Models/backpack_mk2/backpack_mk2.uexp'
    assert hashlib.sha256(mesh.read_bytes()).hexdigest()==manifest['mesh_uexp_sha256'],'Unsupported base-game mesh; expected Astroneer '+manifest['game_build']
    (HERE/'native-connected-parts.json').write_text(json.dumps(manifest['parts']))

if __name__=='__main__':prepare()
