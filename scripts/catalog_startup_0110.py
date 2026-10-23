"""One-time closed-pose warmup; preserve native interaction and idle-freeze logic."""
import base64,copy,json
from investigate import extract


def op_type(x):return x['$type'].split('.')[-1].split(',')[0]

def kismet_size(x):
    t=op_type(x)
    if t in ['EX_True','EX_False','EX_Self','EX_IntZero','EX_Nothing','EX_EndOfScript']:return 1
    if t in ['EX_InstanceVariable','EX_LocalVariable','EX_ObjectConst']:return 9
    if t=='EX_FloatConst':return 5
    if t=='EX_StringConst':return len(x['Value'].encode('ascii'))+2
    if t in ['EX_FinalFunction','EX_LocalFinalFunction','EX_CallMath']:return 10+sum(map(kismet_size,x['Parameters']))
    if t=='EX_Context':
        assert x['Offset']==kismet_size(x['ContextExpression'])
        return 13+kismet_size(x['ObjectExpression'])+kismet_size(x['ContextExpression'])
    if t=='EX_LetBool':return 1+kismet_size(x['VariableExpression'])+kismet_size(x['AssignmentExpression'])
    if t=='EX_JumpIfNot':return 5+kismet_size(x['BooleanExpression'])
    if t=='EX_Return':return 1+kismet_size(x['ReturnExpression'])
    raise ValueError(t)


def patch_catalog_startup():
    from build_game_prototype_0110 import ps,prop
    d=extract('Astro/Content/Items/Catalog/BackpackCatalog')
    def name(n):
        if n not in d['NameMap']:d['NameMap'].append(n)
        return n
    def imp(n,outer,kind='Class',pkg='/Script/CoreUObject'):
        for i,x in enumerate(d['Imports']):
            if (x['ObjectName'],x['OuterIndex'],x['ClassName'])==(n,outer,kind):return -i-1
        d['Imports'].append({'$type':'UAssetAPI.Import, UAssetAPI','ObjectName':name(n),'OuterIndex':outer,'ClassPackage':name(pkg),'ClassName':name(kind),'PackageName':None,'bImportOptional':False})
        return -len(d['Imports'])
    def append(e):d['Exports'].append(e);d['DependsMap'].append([]);return len(d['Exports'])
    def ex(t,**kw):return {'$type':'UAssetAPI.Kismet.Bytecode.Expressions.'+t+', UAssetAPI',**kw}
    def ptr(owner,n=None):return {'$type':'UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI','New':{'$type':'UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI','Path':[name(n)] if n else [],'ResolvedOwner':owner}}
    def var(n,owner=None):return ex('EX_InstanceVariable',Variable=ptr(cid if owner is None else owner,n))
    def call(f,*args,local=False):return ex('EX_LocalFinalFunction' if local else 'EX_FinalFunction',StackNode=f,Parameters=list(args))
    def ctx(obj,expr):return ex('EX_Context',ObjectExpression=obj,Offset=kismet_size(expr),PropertyType=0,RValuePointer=ptr(0),ContextExpression=expr)
    def assign(obj,val):return ex('EX_LetBool',VariableExpression=obj,AssignmentExpression=val)
    def guard(test):return ex('EX_JumpIfNot',CodeOffset=0,BooleanExpression=test)
    cls=next(e for e in d['Exports'] if e['ObjectName']=='BackpackCatalog_C');cid=d['Exports'].index(cls)+1
    cdo=next(e for e in d['Exports'] if e['ObjectName']=='Default__BackpackCatalog_C')
    field=copy.deepcopy(next(p for p in cls['LoadedProperties'] if p['Name']=='ExtendPanel'))
    field.update(Name=name('CB_CatalogWarmingUp'),PropertyFlags='CPF_None');cls['LoadedProperties'].append(field)
    cdo['Data'].append(prop(d,'Bool','CB_CatalogWarmingUp',True))
    eng=imp('/Script/Engine',0,'Package');astro=imp('/Script/Astro',0,'Package')
    skel=imp('SkeletalMeshComponent',eng);control=imp('ControlPanel',astro);crack=imp('CrackableActorComponent',astro)
    system=imp('KismetSystemLibrary',eng);valid=imp('IsValid',system,'Function')
    set_timer=imp('K2_SetTimer',system,'Function');clear_timer=imp('K2_ClearTimer',system,'Function')
    fully_closed=imp('GetFullyClosed',crack,'Function')
    mesh=lambda:var('SkeletalMesh',control)
    component=lambda:var('CrackableActorComponent',control)
    freeze=lambda state:assign(ctx(mesh(),var('bNoSkeletonUpdate',skel)),ex('EX_True' if state else 'EX_False'))
    active=lambda:var('CB_CatalogWarmingUp')
    begin=next(e for e in d['Exports'] if e['ObjectName']=='ReceiveBeginPlay')
    closed_handler=next(e for e in d['Exports'] if e['ObjectName']=='BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_0_OnCrackedStateChanged__DelegateSignature')
    opened_handler=next(e for e in d['Exports'] if e['ObjectName']=='BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_1_OnCrackedStateChanged__DelegateSignature')
    def function(n,make,param=False):
        fn=copy.deepcopy(begin);fid=len(d['Exports'])+1
        fn.update(ObjectName=name(n),SerialSize=0,SerialOffset=0,SuperStruct=0,SuperIndex=0,LoadedProperties=[],FunctionFlags='FUNC_Public, FUNC_BlueprintCallable')
        if param:
            f=copy.deepcopy(next(p for p in opened_handler['LoadedProperties'] if p['Name']=='bIsCracked'));f['Name']=name('Opened');fn['LoadedProperties']=[f]
        body=make(fid);end=sum(map(kismet_size,body))
        for x in body:
            if 'CodeOffset' in x:x['CodeOffset']=end
        body.extend([ex('EX_Return',ReturnExpression=ex('EX_Nothing')),ex('EX_EndOfScript')])
        fn.update(ScriptBytecode=body,ScriptBytecodeSize=sum(map(kismet_size,body)))
        assert base64.b64decode(fn['Extras'])==b'\0'*8
        fn['CreateBeforeSerializationDependencies']=[cid,valid,set_timer,clear_timer,fully_closed,control,skel]
        fn['SerializationBeforeSerializationDependencies']=[];fn['CreateBeforeCreateDependencies']=[cid]
        assert append(fn)==fid
        cls['FuncMap'].append([name(n),fid]);cls['Children'].insert(0,fid);cls['CreateBeforeSerializationDependencies'].append(fid)
        return fid
    keep=function('CB_KeepCatalogStartupPoseUpdating',lambda _: [guard(active()),guard(call(valid,mesh())),freeze(False)])
    finish=function('CB_FinishCatalogWarmup',lambda _: [assign(active(),ex('EX_False')),guard(call(valid,component())),guard(ctx(component(),call(fully_closed))),guard(call(valid,mesh())),freeze(True)])
    start=function('CB_StartCatalogWarmup',lambda _: [call(keep,local=True),call(set_timer,ex('EX_Self'),ex('EX_StringConst',Value='CB_FinishCatalogWarmup'),ex('EX_FloatConst',Value=1.0),ex('EX_False'),ex('EX_FloatConst',Value=0.),ex('EX_FloatConst',Value=0.))])
    cancel=function('CB_CancelCatalogWarmupIfOpened',lambda fid: [guard(ex('EX_LocalVariable',Variable=ptr(fid,'Opened'))),assign(active(),ex('EX_False')),call(clear_timer,ex('EX_Self'),ex('EX_StringConst',Value='CB_FinishCatalogWarmup'))],param=True)
    def post(wrapper,expr,dependency):
        code=wrapper['ScriptBytecode'];i=next(i for i,x in enumerate(code) if op_type(x)=='EX_Return');code.insert(i,expr)
        wrapper['ScriptBytecodeSize']+=kismet_size(expr);wrapper['CreateBeforeSerializationDependencies'].append(dependency)
    post(begin,call(start,local=True),start)
    post(closed_handler,call(keep,local=True),keep)
    opened_id=d['Exports'].index(opened_handler)+1
    post(opened_handler,call(cancel,ex('EX_LocalVariable',Variable=ptr(opened_id,'bIsCracked')),local=True),cancel)
    return d
