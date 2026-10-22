"""Independent cooked-asset, native behavior, SCS and geometry verification."""
import base64,copy,hashlib,json,subprocess
import numpy as np
from native_revision_017 import HERE,OUT,gltf
from investigate import REPAK,GUI,ENV,UMODEL
from build_game_prototype_017 import ps,xyz,es
STAGE=OUT/'staging'

def norm(x):
    if isinstance(x,float):return float(np.float32(x))
    if isinstance(x,str) and x in ['+0','-0']:return 0.
    if isinstance(x,list):return [norm(a) for a in x]
    if isinstance(x,dict):return {k:norm(v) for k,v in x.items()}
    return x
def vec(p):return np.array([float(xyz(p)[k]) for k in 'XYZ'])
def walk(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():yield from walk(v)
    elif isinstance(x,list):
        for v in x:yield from walk(v)
def type_(e):return e.get('$type','').split('.')[-1].split(',')[0]
def size(e):
    t=type_(e)
    if t in ['EX_IntZero','EX_Nothing','EX_EndOfScript']:return 1
    if t in ['EX_InstanceVariable','EX_LocalVariable']:return 9
    if t=='EX_NameConst':return 13
    if t in ['EX_FinalFunction','EX_LocalFinalFunction']:return 10+sum(map(size,e['Parameters']))
    if t=='EX_Context':
        assert e['Offset']==size(e['ContextExpression'])
        return 13+size(e['ObjectExpression'])+size(e['ContextExpression'])
    if t=='EX_JumpIfNot':return 5+size(e['BooleanExpression'])
    if t=='EX_Return':return 1+size(e['ReturnExpression'])
    raise AssertionError(t)

assets={}
for path in STAGE.rglob('*.uasset'):
    label=path.stem;dest=OUT/f'verified-{label}.json'
    subprocess.run([str(GUI),'--portable','tojson',str(path),str(dest),'VER_UE4_27','Astro'],env=ENV,check=True,timeout=90,capture_output=True)
    d=json.loads(dest.read_text());expected=json.loads((OUT/(label+'.json')).read_text());assets[label]=d
    assert d['Imports']==expected['Imports'] and d['NameMap']==expected['NameMap'],label
    assert len(d['Exports'])==len(expected['Exports'])
    for a,b in zip(d['Exports'],expected['Exports']):
        assert a['ObjectName']==b['ObjectName']
        for field in ['Data','ScriptBytecode','LoadedProperties','FuncMap','Children','Extras']:
            assert norm(a.get(field))==norm(b.get(field)),(label,a['ObjectName'],field)
        if 'FunctionExport' in a['$type']:
            assert len(base64.b64decode(a['Extras']))>=(10 if 'FUNC_Net,' in a['FunctionFlags'] else 8)
        for field in ['CreateBeforeSerializationDependencies','SerializationBeforeSerializationDependencies','CreateBeforeCreateDependencies','SerializationBeforeCreateDependencies']:
            assert all(-len(d['Imports'])<=v<=len(d['Exports']) for v in a.get(field,[]))

geometry=json.loads((OUT/'geometry-report.json').read_text())
front_labels=geometry['front_components']
positions={};resource_order={}
for label,path,corpse in [('BackpackRail','Items/BackpackRail',False),('AstroCorpse','Character/AstroCorpse',True)]:
    d=assets[label];original=json.loads((HERE/'vanilla/Astro/Content'/path).with_suffix('.json').read_text())
    ex,old=es(d),es(original)
    # Native behavior is untouched except extension of the resource array,
    # our material-sharing calls and the existing closed-printer speck correction.
    for n,e in old.items():
        if not e.get('ScriptBytecode'):continue
        expected=copy.deepcopy(e['ScriptBytecode']);actual=copy.deepcopy(ex[n]['ScriptBytecode'])
        added=0
        if n=='UserConstructionScript':
            arrays=[x for x in actual if type_(x)=='EX_SetArray' and len(x['Elements'])==16];assert len(arrays)==1
            extra=arrays[0]['Elements'][8:];assert len(extra)==8
            assert all(size(x)==45 for x in extra)
            arrays[0]['Elements']=arrays[0]['Elements'][:8];added=360
        if n in ['ReceiveBeginPlay','ReceiveTick']:
            assert type_(actual.pop(0))=='EX_LocalFinalFunction';added=10
        if n=='CLIENT Printer View':
            for i in [1,7,13]:expected[i]['Expression']['Value']=.001
            for i in [4,10,16]:expected[i]['Expression']['Parameters'][1]['Value']=.001
        assert norm(actual)==norm(expected),(label,n)
        assert ex[n]['ScriptBytecodeSize']==e['ScriptBytecodeSize']+added
    names=[('ChildSlot'+(str(n) if n else '')) if corpse else f'Item Slot {n+1}' for n in range(16)]
    parent='ItemSlots' if corpse else 'Item Slots';origin=vec(ps(ex[parent+'_GEN_VARIABLE'])['RelativeLocation'])
    positions[label]=[]
    for var in names:
        e=ex[var+'_GEN_VARIABLE'];p=ps(e)
        assert np.array_equal(vec(p['RelativeScale3D']),[.25]*3)
        assert not p['bVisible']['Value'] and not p['SlotVisible']['Value']
        positions[label].append(vec(p['RelativeLocation'])+origin)
        component_id=d['Exports'].index(e)+1
        nodes=[x for x in d['Exports'] if ps(x).get('ComponentTemplate',{}).get('Value')==component_id]
        assert len(nodes)==1 and ps(nodes[0])['InternalVariableName']['Value']==var
        ni=d['Exports'].index(nodes[0])+1
        assert any(any(x.get('Value')==ni for x in ps(owner).get('ChildNodes',{}).get('Value',[])) for owner in d['Exports'])
    assert len(np.unique(np.round(positions[label],3),axis=0))==16
    code=ex['UserConstructionScript']['ScriptBytecode'];refs={}
    for op in code:
        expr=op.get('Expression',{});call=expr.get('ContextExpression',{})
        if call.get('StackNode',0)<0 and d['Imports'][-call['StackNode']-1]['ObjectName']=='MakeReference' and call.get('Parameters'):
            refs[op['Variable']['Variable']['New']['Path'][0]]=call['Parameters'][0]['Value']
    array=next(x for x in code if type_(x)=='EX_SetArray' and len(x['Elements'])==16)
    resolved=[]
    for x in array['Elements']:
        if type_(x)=='EX_LocalVariable':resolved.append(refs[x['Variable']['New']['Path'][0]])
        else:resolved.append(x['ContextExpression']['Parameters'][0]['Value'])
    assert resolved==names,(label,resolved);resource_order[label]=resolved
    assert ex['Slots_GEN_VARIABLE']['Data']==old['Slots_GEN_VARIABLE']['Data']
    if not corpse:
        for n in ['Printer Scene_GEN_VARIABLE','Printer Head_GEN_VARIABLE','Oxygen Bar_GEN_VARIABLE','MissionLog_GEN_VARIABLE','Catalog_GEN_VARIABLE','CatalogCreative_GEN_VARIABLE','Creative Drone Slot_GEN_VARIABLE']:
            assert ex[n]['Data']==old[n]['Data'],n
    fn=ex['CB_ShareSocketMaterial'];assert sum(map(size,fn['ScriptBytecode']))==fn['ScriptBytecodeSize']
    assert all(x['CodeOffset']==fn['ScriptBytecodeSize']-3 for x in fn['ScriptBytecode'] if 'CodeOffset' in x)
    assert sum(type_(x)=='EX_Context' for x in fn['ScriptBytecode'])==16+len(front_labels)
    for n in [f'NativeBackpackSocket{i}' for i in range(1,17)]+['Compact_'+label for label in front_labels]:
        component=ex[n+'_GEN_VARIABLE'];p=ps(component)
        assert np.allclose(vec(p['RelativeScale3D']),.88 if n.startswith('Native') else 1.)
        fields={x['Name']:x for x in p['BodyInstance']['Value']}
        assert fields['CollisionEnabled']['EnumValue']=='ECollisionEnabled::NoCollision'
distances=np.linalg.norm(np.array(positions['BackpackRail'])[:,None,:]-np.array(positions['AstroCorpse'])[None,:,:],axis=2)
assert np.all(distances.min(1)<1e-4) and len(set(distances.argmin(1)))==16

# Independent UE Viewer re-exports verify that the serialized vertex/index buffers
# describe the intended shape, normals, palette UVs and root-only skinning.
umodel=UMODEL
original,oa,oi=gltf(HERE/'exports/Models/backpack_mk2/backpack_mk2.gltf')
for label in ['backpack_mk2','backpack_socket']+front_labels:
    subprocess.run([str(umodel),'-export','-gltf','-noanim','-game=ue4.27','-path='+str(STAGE),'-out='+str(OUT/'mesh-check'),label+'.uasset'],check=True,timeout=60,capture_output=True)
    gd,a,indices=gltf(OUT/f'mesh-check/Mods/CompactBackpack16/{label}.gltf')
    nodes=copy.deepcopy(gd['nodes']);nodes[0]['name']=original['nodes'][0]['name']
    assert nodes==original['nodes'] and gd['skins']==original['skins']
    if label.startswith('front'):
        expected=np.load(OUT/(label+'-expected.npz'))
        wanted=expected['indices'];active=(wanted[:,0]!=wanted[:,1])&(wanted[:,1]!=wanted[:,2])
        assert np.array_equal((indices[:,0]!=indices[:,1])&(indices[:,1]!=indices[:,2]),active)
        # UE Viewer compacts unused vertices, so compare triangle attributes.
        assert np.allclose(a['POSITION'][indices[active]][:,:,[0,2,1]]*100,expected['positions'][wanted[active]],atol=2e-5)
        assert np.array_equal(a['TEXCOORD_0'][indices[active]],expected['uv'][wanted[active]])
        used=np.unique(indices);assert np.all((a['JOINTS_0'][used]==0)|(a['WEIGHTS_0'][used]==0))
        normal=np.zeros_like(expected['positions']);normal[expected['allocated']]=expected['normals']
        assert np.allclose(a['NORMAL'][indices[active]][:,:,[0,2,1]],normal[wanted[active]],atol=.009)
    elif label=='backpack_mk2':
        expected=np.load(OUT/'body-expected.npz');keep=expected['keep']
        for k in oa:assert np.array_equal(a[k][indices[keep]],oa[k][oi[keep]]),k
        animated=~np.all((oa['JOINTS_0'][oi]==0)|(oa['WEIGHTS_0'][oi]==0),axis=(1,2))
        assert animated.sum()==2380 and keep[animated].all()
    else:
        info=json.loads((OUT/'socket-source.json').read_text());sel=np.array(info['triangles'])
        for k in ['TEXCOORD_0','NORMAL','TANGENT','JOINTS_0','WEIGHTS_0']:assert np.array_equal(a[k][indices[sel]],oa[k][oi[sel]])

pak=OUT/'000-CompactBackpack16-0.1.7_P.pak'
listing=subprocess.check_output([str(REPAK),'list',str(pak)],text=True).splitlines()
expected=sorted(p.relative_to(STAGE).as_posix() for p in STAGE.rglob('*') if p.is_file())
assert sorted(listing)==expected and len(listing)==2*(4+len(front_labels))+1
for member in listing:
    data=subprocess.check_output([str(REPAK),'get',str(pak),member]);assert data==(STAGE/member).read_bytes(),member
report=json.loads((OUT/'build-report.json').read_text());assert hashlib.sha256(pak.read_bytes()).hexdigest()==report['pak_sha256']
report['offline_checks']=[f'{len(assets)} assets reparsed including function trailers and dependencies','vanilla bytecode preserved except declared changes',
 'sixteen unique slot references and registered components on live and death backpacks','native .25 main item scale; auxiliary data untouched',
 'matching live and corpse attachment positions','original control and printer transforms retained','material helper bytecode and offsets verified',
 'approved model geometry and palette UVs re-exported','new visible meshes root weighted and collision disabled','all 2380 animated native triangles preserved',
 f'{len(listing)} PAK entries independently extracted and byte matched']
report['resource_order']=resource_order
(OUT/'build-report.json').write_text(json.dumps(report,indent=2))
print('All 0.1.7 offline checks passed. In-game appearance, item behavior, save/load and death retrieval still need testing.')
