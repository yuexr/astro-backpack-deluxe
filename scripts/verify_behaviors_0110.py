"""Offline checks for generated VM guards, startup lifecycle, and frozen geometry."""
import copy,hashlib,json,struct
from pathlib import Path
from catalog_startup_0110 import kismet_size,op_type
from native_revision_0110 import HERE,OUT


class VM:
    """Small interpreter for only the generated helpers; never calls the game."""
    def __init__(self,asset,actor):self.d=asset;self.actor=actor;self.timers={}
    def name(self,ptr):return ptr['New']['Path'][0]
    def set(self,expr,value,obj,local):
        t=op_type(expr)
        if t=='EX_InstanceVariable':
            n=self.name(expr['Variable']);(self.actor if n in self.actor else obj)[n]=value;return
        if t=='EX_Context':self.set(expr['ContextExpression'],value,self.eval(expr['ObjectExpression'],obj,local),local);return
        raise AssertionError(t)
    def eval(self,x,obj,local):
        t=op_type(x)
        if t in ['EX_InstanceVariable','EX_LocalVariable']:
            n=self.name(x['Variable'])
            return (self.actor if t=='EX_InstanceVariable' and n in self.actor else obj if t=='EX_InstanceVariable' else local)[n]
        if t in ['EX_True','EX_False']:return t=='EX_True'
        if t=='EX_Self':return self.actor
        if t in ['EX_IntZero','EX_Nothing']:return 0
        if t in ['EX_StringConst','EX_FloatConst']:return x['Value']
        if t=='EX_Context':return self.eval(x['ContextExpression'],self.eval(x['ObjectExpression'],obj,local),local)
        if t=='EX_LetBool':
            self.set(x['VariableExpression'],self.eval(x['AssignmentExpression'],obj,local),obj,local);return
        if t in ['EX_FinalFunction','EX_LocalFinalFunction']:
            args=[self.eval(a,obj,local) for a in x['Parameters']];node=x['StackNode']
            if node>0:return self.run(self.d['Exports'][node-1]['ObjectName'],args)
            name=self.d['Imports'][-node-1]['ObjectName']
            if name=='IsValid':return args[0] is not None
            if name=='GetFullyClosed':return obj['fully_closed']
            if name=='K2_SetTimer':self.timers[args[1]]={'seconds':args[2],'loop':args[3]};return
            if name=='K2_ClearTimer':self.timers.pop(args[1],None);return
            if name=='IsCreativeMode':return self.actor['creative']
            if name=='GetMaterial':return obj['material']
            if name=='SetMaterial':obj['material']=args[1];return
            if name=='SetVisibility':obj['visible']=args[0];return
            raise AssertionError(name)
        raise AssertionError(t)
    def run(self,name,args=()):
        e=next(x for x in self.d['Exports'] if x['ObjectName']==name)
        local={p['Name']:v for p,v in zip(e['LoadedProperties'],args)}
        for x in e['ScriptBytecode']:
            t=op_type(x)
            if t=='EX_Return':return
            if t=='EX_JumpIfNot':
                assert x['CodeOffset']==e['ScriptBytecodeSize']-3
                if not self.eval(x['BooleanExpression'],self.actor,local):return
            else:self.eval(x,self.actor,local)


def check_behaviors(assets,geometry):
    def exports(d):return {e['ObjectName']:e for e in d['Exports']}
    # The drone mesh is always unclickable/no-collision; only its native slot
    # handles gameplay, and the replacement visual follows the native mode.
    d=assets['BackpackRail'];ex=exports(d)
    actor={'creative':False,'backpack_mk2':{'material':object()}}
    for n in [f'NativeBackpackSocket{i}' for i in range(1,17)]+['Compact_'+n for n in geometry['front_components']]+['NativeDroneSocket']:actor[n]={'visible':False}
    vm=VM(d,actor)
    for mode in [False,True,False,True]:
        actor['creative']=mode;vm.run('CB_ShareSocketMaterial')
        assert actor['NativeDroneSocket']['visible']==mode
        assert actor['NativeDroneSocket']['material'] is actor['backpack_mk2']['material']
    # The new mount is a child of the real mesh, with unchanged world placement.
    comp=ex['NativeDroneSocket_GEN_VARIABLE'];cid=d['Exports'].index(comp)+1
    ps=lambda x:{p['Name']:p for p in x.get('Data',[])}
    node=next(e for e in d['Exports'] if ps(e).get('ComponentTemplate',{}).get('Value')==cid)
    ni=d['Exports'].index(node)+1
    owner=next(e for e in d['Exports'] if any(p['Value']==ni for p in ps(e).get('ChildNodes',{}).get('Value',[])))
    assert ps(owner)['InternalVariableName']['Value']=='backpack_mk2'

    # All vanilla catalog logic remains unchanged; only small post-callback
    # hooks defer its initial skeleton freeze. Creative inherits this class.
    d=assets['BackpackCatalog'];ex=exports(d)
    original=json.loads((HERE/'vanilla/Astro/Content/Items/Catalog/BackpackCatalog.json').read_text());old=exports(original)
    wrappers={'ReceiveBeginPlay':10,
      'BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_0_OnCrackedStateChanged__DelegateSignature':10,
      'BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_1_OnCrackedStateChanged__DelegateSignature':19}
    for n,e in old.items():
        if e.get('ScriptBytecode'):
            code=copy.deepcopy(ex[n]['ScriptBytecode'])
            if n in wrappers:
                i=next(i for i,x in enumerate(code) if op_type(x)=='EX_Return');hook=code.pop(i-1)
                assert op_type(hook)=='EX_LocalFinalFunction' and kismet_size(hook)==wrappers[n]
            assert code==e['ScriptBytecode'],n
            assert ex[n]['ScriptBytecodeSize']==e['ScriptBytecodeSize']+wrappers.get(n,0)
        if e.get('Data') and n!='Default__BackpackCatalog_C':assert ex[n]['Data']==e['Data'],n
    for n,e in ex.items():
        if n.startswith('CB_'):
            assert sum(map(kismet_size,e['ScriptBytecode']))==e['ScriptBytecodeSize']
    def fresh():return {'CB_CatalogWarmingUp':True,'SkeletalMesh':{'bNoSkeletonUpdate':True},'CrackableActorComponent':{'fully_closed':True}}
    # Ordinary startup: allow evaluation, undo premature close freeze, freeze once settled.
    actor=fresh();vm=VM(d,actor);vm.run('CB_StartCatalogWarmup')
    assert not actor['SkeletalMesh']['bNoSkeletonUpdate']
    assert vm.timers=={'CB_FinishCatalogWarmup':{'seconds':1.,'loop':False}}
    actor['SkeletalMesh']['bNoSkeletonUpdate']=True;vm.run('CB_KeepCatalogStartupPoseUpdating')
    assert not actor['SkeletalMesh']['bNoSkeletonUpdate']
    vm.run('CB_CancelCatalogWarmupIfOpened',[False]);assert vm.timers
    vm.run('CB_FinishCatalogWarmup');assert actor['SkeletalMesh']['bNoSkeletonUpdate'] and not actor['CB_CatalogWarmingUp']
    actor['SkeletalMesh']['bNoSkeletonUpdate']=True;vm.run('CB_KeepCatalogStartupPoseUpdating');assert actor['SkeletalMesh']['bNoSkeletonUpdate']
    # Opening during warmup cancels the timer and leaves native animation controls in charge.
    actor=fresh();vm=VM(d,actor);vm.run('CB_StartCatalogWarmup');vm.run('CB_CancelCatalogWarmupIfOpened',[True])
    assert not vm.timers and not actor['CB_CatalogWarmingUp']
    actor['SkeletalMesh']['bNoSkeletonUpdate']=True;vm.run('CB_KeepCatalogStartupPoseUpdating');assert actor['SkeletalMesh']['bNoSkeletonUpdate']
    actor=fresh();vm=VM(d,actor);vm.run('CB_StartCatalogWarmup');actor['CrackableActorComponent']['fully_closed']=False;vm.run('CB_FinishCatalogWarmup')
    assert not actor['SkeletalMesh']['bNoSkeletonUpdate']
    # Uninitialized or missing skeletal components fail closed, without a crash.
    actor=fresh();actor['SkeletalMesh']=None;vm=VM(d,actor);vm.run('CB_StartCatalogWarmup');vm.run('CB_FinishCatalogWarmup')

    def read_glb(path):
        b=path.read_bytes();n=struct.unpack_from('<I',b,12)[0];return json.loads(b[20:20+n]),b[20+n:]
    from model_mesh_0110 import MODEL,INFO
    newdoc,newbin=read_glb(MODEL);reference=json.loads(INFO.read_text())
    # Fingerprints record the approved 0.1.9 geometry and the sole palette-role
    # edit, without needing another release or a private authoring directory.
    assert hashlib.sha256(newbin).hexdigest()==reference['approved_base_binary_sha256'],'Approved base geometry or normals changed'
    canonical=json.dumps(newdoc,sort_keys=True,separators=(',',':')).encode()
    assert hashlib.sha256(canonical).hexdigest()==reference['approved_model_document_sha256'],'Unrequested model changes'
    trim=next(i for i,m in enumerate(newdoc['materials']) if m['name']=='trim')
    assert next(m for m in newdoc['meshes'] if m['name']=='LowerBatteryAccent')['primitives'][0]['material']==trim
    creative=json.loads((HERE/'vanilla/Astro/Content/Items/Catalog/BackpackCatalog_Creative.json').read_text())
    superclass=next(e for e in creative['Exports'] if e['ObjectName']=='BackpackCatalog_Creative_C')['SuperStruct']
    assert superclass<0 and creative['Imports'][-superclass-1]['ObjectName']=='BackpackCatalog_C'
    return ['Creative-only visibility helper tested through mode changes and real mesh bounds parent verified',
        'native catalog behavior preserved except startup hooks; inherited by Creative catalog',
        'catalog warmup lifecycle checked including early opening, closing, missing mesh and idle restoration',
        'frozen base geometry and normals identical; only lower accent palette binding changed']
