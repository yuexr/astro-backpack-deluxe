"""Independent sixteen-slot patch built exclusively from installed vanilla assets.
No original Backpack16 PAK, JSON, functions, or components are build inputs.
"""
import base64,copy,hashlib,json,subprocess,uuid
from investigate import GUI,REPAK,ENV,extract
from native_revision_017 import HERE,OUT,PKG,build_meshes
from visual_components_017 import add_visual_components

STAGE=OUT/'staging'
def ps(e):return {p['Name']:p for p in e.get('Data',[])}
def xyz(p):return p['Value'][0]['Value']
def name(d,n):
    if n not in d['NameMap']:d['NameMap'].append(n)
    return n
def prop(d,t,n,v):return {'$type':f'UAssetAPI.PropertyTypes.Objects.{t}PropertyData, UAssetAPI','Name':name(d,n),'ArrayIndex':0,'PropertyGuid':None,'IsZero':False,'PropertyTagFlags':'None','PropertyTypeName':None,'PropertyTagExtensions':'NoExtension','Value':v}
def setbool(d,e,n,v):
    if n in ps(e):ps(e)[n]['Value']=v
    else:e['Data'].append(prop(d,'Bool',n,v))
def location(d,e,values):
    if 'RelativeLocation' not in ps(e):
        e['Data'].append(copy.deepcopy(next(p for x in d['Exports'] for p in x.get('Data',[]) if p['Name']=='RelativeLocation')))
    xyz(ps(e)['RelativeLocation']).update(dict(zip('XYZ',map(float,values))))
def append(d,e):d['Exports'].append(e);d['DependsMap'].append([]);return len(d['Exports'])
def es(d):return {e['ObjectName']:e for e in d['Exports']}

def add_inventory_slots(d,corpse=False):
    """Duplicate native component templates, then extend the native resource array.
    Existing eight names/order are stable for saves. New slots follow them.
    """
    original_names=[('ChildSlot'+(str(i) if i else '')) if corpse else f'Item Slot {i+1}' for i in range(8)]
    extra_names=[f'ChildSlot{i}' if corpse else f'Item Slot {i+1}' for i in range(8,16)]
    exports=es(d);cls=next(x for x in d['Exports'] if 'ClassExport' in x['$type'])
    for i,newname in enumerate(extra_names):
        oldname=original_names[i];old=exports[oldname+'_GEN_VARIABLE'];oldid=d['Exports'].index(old)+1
        oldnode=next(e for e in d['Exports'] if ps(e).get('ComponentTemplate',{}).get('Value')==oldid)
        oldnodeid=d['Exports'].index(oldnode)+1
        parent=next(e for e in d['Exports'] if any(x.get('Value')==oldnodeid for x in ps(e).get('ChildNodes',{}).get('Value',[])))
        scs=d['Exports'][oldnode['OuterIndex']-1]
        component=copy.deepcopy(old);component.update(ObjectName=name(d,newname+'_GEN_VARIABLE'),SerialSize=0,SerialOffset=0)
        ci=append(d,component)
        node=copy.deepcopy(oldnode);node.update(ObjectName=name(d,'SCS_CB16_'+newname.replace(' ','')),SerialSize=0,SerialOffset=0)
        ps(node)['ComponentTemplate']['Value']=ci;ps(node)['InternalVariableName']['Value']=name(d,newname)
        ps(node)['VariableGuid']['Value'][0]['Value']='{'+str(uuid.uuid5(uuid.NAMESPACE_DNS,'compact16.'+('corpse.' if corpse else 'live.')+newname)).upper()+'}'
        for k in ['CreateBeforeSerializationDependencies','SerializationBeforeSerializationDependencies','CreateBeforeCreateDependencies','SerializationBeforeCreateDependencies']:
            node[k]=[ci if v==oldid else v for v in node.get(k,[])]
        ni=append(d,node)
        for owner,key in [(parent,'ChildNodes'),(scs,'AllNodes')]:
            values=ps(owner)[key]['Value'];values.append(prop(d,'Object',str(len(values)),ni))
            owner['CreateBeforeSerializationDependencies'].append(ni)
        field=copy.deepcopy(next(x for x in cls['LoadedProperties'] if x['Name']==oldname));field['Name']=name(d,newname)
        cls['LoadedProperties'].append(field);cls['CreateBeforeSerializationDependencies'].append(ci)
    constructor=exports['UserConstructionScript'];code=constructor['ScriptBytecode']
    arrays=[x for x in code if '.EX_SetArray,' in x['$type'] and len(x['Elements'])==8];assert len(arrays)==1
    template=next(x['Expression'] for x in code if x.get('Expression',{}).get('ContextExpression',{}).get('Parameters',[{}])[0].get('Value')==original_names[-1])
    assert template['Offset']==23
    for variable in extra_names:
        expr=copy.deepcopy(template);expr['ContextExpression']['Parameters'][0]['Value']=name(d,variable)
        arrays[0]['Elements'].append(expr)
    # EX_Context: opcode + skip offset + result property (13), instance (9),
    # final function (10), FName constant (13) = 45 bytes per expression.
    constructor['ScriptBytecodeSize']+=45*8
    assert not any('CodeOffset' in x or 'PushingAddress' in x for x in code)
    return original_names+extra_names

def private_body(d):
    old='/Game/Models/backpack_mk2/backpack_mk2';new=PKG+'backpack_mk2';name(d,new)
    for x in d['Imports']:
        if x['ObjectName']==old:x['ObjectName']=new

def configure(d,slot_names,front,corpse=False):
    ex=es(d);parent='ItemSlots' if corpse else 'Item Slots'
    origin=xyz(ps(ex[parent+'_GEN_VARIABLE'])['RelativeLocation'])
    setbool(d,ex[parent+'_GEN_VARIABLE'],'bUseAttachParentBound',True)
    # Keep the native item attachment-to-visible-socket depth offset.
    native_cx=json.loads((OUT/'socket-source.json').read_text())['centre'][0]
    target_x=-13.9+(-15.1315727234-native_cx)
    for n,var in enumerate(slot_names):
        e=ex[var+'_GEN_VARIABLE'];side=(1 if n%2==0 else -1) if corpse else (-1 if n%2==0 else 1)
        y=side*(40 if n<8 else 18);z=[47.,14.3,-18.1,-51.][n%8//2]
        location(d,e,[target_x-origin['X'],y-origin['Y'],z-origin['Z']])
        # Original .25 native component scale, with no item-size reduction.
        assert all(abs(float(xyz(ps(e)['RelativeScale3D'])[k])-.25)<1e-7 for k in 'XYZ')
        setbool(d,e,'SlotVisible',False);setbool(d,e,'bVisible',False)
    for key in ['Power Bar_GEN_VARIABLE']+([] if corpse else ['PowerBarOverlay_GEN_VARIABLE']):
        p=ps(ex[key]);scale=xyz(p['RelativeScale3D']);scale.update(X=.09,Y=.09)
        xyz(p['RelativeLocation']).update(X=-13.8,Y=0.)
    if not corpse:
        # Native casing width allows native control/drone locations again.
        printer=ex['CLIENT Printer View']['ScriptBytecode']
        for i in [1,7,13]:
            assert abs(printer[i]['Expression']['Value']-.1)<1e-7;printer[i]['Expression']['Value']=.001
        for i in [4,10,16]:
            assert abs(printer[i]['Expression']['Parameters'][1]['Value']-.1)<1e-7;printer[i]['Expression']['Parameters'][1]['Value']=.001
    private_body(d);add_visual_components(d,front,corpse)

def write_asset(d,target,label):
    for gen in d['Generations']:gen['NameCount']=len(d['NameMap']);gen['ExportCount']=len(d['Exports'])
    source=OUT/(label+'.json');source.write_text(json.dumps(d,separators=(',',':')))
    target=STAGE/target;target.parent.mkdir(parents=True,exist_ok=True)
    r=subprocess.run([str(GUI),'--portable','fromjson',str(source),str(target),'Astro'],env=ENV,check=True,timeout=120,capture_output=True)
    assert target.exists() and target.with_suffix('.uexp').exists(),(label,r.stdout,r.stderr)

def build():
    meshes,geometry=build_meshes()
    for label,d in meshes.items():write_asset(d,f'Astro/Content/Mods/CompactBackpack16/{label}.uasset',label)
    provenance={}
    for asset,corpse in [('Items/BackpackRail',False),('Character/AstroCorpse',True)]:
        path=HERE/'vanilla/Astro/Content'/asset
        d=extract('Astro/Content/'+asset)
        provenance[asset]={ext:hashlib.sha256(path.with_suffix(ext).read_bytes()).hexdigest() for ext in ['.uasset','.uexp']}
        names=add_inventory_slots(d,corpse);configure(d,names,geometry['front_components'],corpse)
        write_asset(d,'Astro/Content/'+asset+'.uasset',asset.rsplit('/',1)[-1])
    metadata={'schema_version':2,'name':'Compact Backpack 16 (test)','mod_id':'CompactBackpack16','author':'yue','description':'Independent vanilla-based sixteen-slot inventory and death backpack, approved native-style model, full-size items, dynamic palette materials.','version':'0.1.7','game_build':'1.45.1.0','sync':'serverclient'}
    (STAGE/'metadata.json').write_text(json.dumps(metadata,indent=2))
    pak=OUT/'000-CompactBackpack16-0.1.7_P.pak'
    subprocess.run([str(REPAK),'pack',str(STAGE),str(pak)],check=True,timeout=120,capture_output=True)
    report={'version':'0.1.7','vanilla_sources':provenance,'original_Backpack16_required':False,'geometry':geometry,
            'main_slot_scale':.25,'item_size_multiplier':1.,'native_auxiliaries_unchanged':True,'controls_and_drone':'vanilla transforms',
            'installed':False,'gameplay_tested':False,'pak_sha256':hashlib.sha256(pak.read_bytes()).hexdigest()}
    (OUT/'build-report.json').write_text(json.dumps(report,indent=2))
    print('Built',pak)

if __name__=='__main__':build()
