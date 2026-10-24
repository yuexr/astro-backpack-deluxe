"""Evaluate the native closed catalog pose before freezing its skeleton."""

import base64
import copy

from asset_io import append as append_export
from asset_io import name as asset_name
from asset_io import prop
from game_assets import extract
from kismet import kismet_size, op_type


def patch_catalog_startup():
    d = extract("Astro/Content/Items/Catalog/BackpackCatalog")

    def name(n):
        return asset_name(d, n)

    def imp(n, outer, kind="Class", pkg="/Script/CoreUObject"):
        for i, x in enumerate(d["Imports"]):
            if (x["ObjectName"], x["OuterIndex"], x["ClassName"]) == (n, outer, kind):
                return -i - 1
        d["Imports"].append(
            {
                "$type": "UAssetAPI.Import, UAssetAPI",
                "ObjectName": name(n),
                "OuterIndex": outer,
                "ClassPackage": name(pkg),
                "ClassName": name(kind),
                "PackageName": None,
                "bImportOptional": False,
            }
        )
        return -len(d["Imports"])

    def append(e):
        return append_export(d, e)

    def ex(t, **kw):
        return {
            "$type": "UAssetAPI.Kismet.Bytecode.Expressions." + t + ", UAssetAPI",
            **kw,
        }

    def ptr(owner, n=None):
        return {
            "$type": "UAssetAPI.Kismet.Bytecode.KismetPropertyPointer, UAssetAPI",
            "New": {
                "$type": "UAssetAPI.UnrealTypes.FFieldPath, UAssetAPI",
                "Path": [name(n)] if n else [],
                "ResolvedOwner": owner,
            },
        }

    def var(n, owner=None):
        return ex(
            "EX_InstanceVariable", Variable=ptr(cid if owner is None else owner, n)
        )

    def call(f, *args, local=False):
        return ex(
            "EX_LocalFinalFunction" if local else "EX_FinalFunction",
            StackNode=f,
            Parameters=list(args),
        )

    def ctx(obj, expr):
        return ex(
            "EX_Context",
            ObjectExpression=obj,
            Offset=kismet_size(expr),
            PropertyType=0,
            RValuePointer=ptr(0),
            ContextExpression=expr,
        )

    def assign(obj, val):
        return ex("EX_LetBool", VariableExpression=obj, AssignmentExpression=val)

    def guard(test):
        return ex("EX_JumpIfNot", CodeOffset=0, BooleanExpression=test)

    cls = next(e for e in d["Exports"] if e["ObjectName"] == "BackpackCatalog_C")
    cid = d["Exports"].index(cls) + 1
    cdo = next(
        e for e in d["Exports"] if e["ObjectName"] == "Default__BackpackCatalog_C"
    )
    field = copy.deepcopy(
        next(p for p in cls["LoadedProperties"] if p["Name"] == "ExtendPanel")
    )
    field.update(Name=name("BPM_CatalogPosePending"), PropertyFlags="CPF_None")
    cls["LoadedProperties"].append(field)
    cdo["Data"].append(prop(d, "Bool", "BPM_CatalogPosePending", True))
    started_field = copy.deepcopy(field)
    started_field["Name"] = name("BPM_CatalogPoseStarted")
    cls["LoadedProperties"].append(started_field)
    cdo["Data"].append(prop(d, "Bool", "BPM_CatalogPoseStarted", False))
    eng = imp("/Script/Engine", 0, "Package")
    astro = imp("/Script/Astro", 0, "Package")
    skel = imp("SkeletalMeshComponent", eng)
    control = imp("ControlPanel", astro)
    crack = imp("CrackableActorComponent", astro)
    system = imp("KismetSystemLibrary", eng)
    valid = imp("IsValid", system, "Function")
    set_timer = imp("K2_SetTimer", system, "Function")
    clear_timer = imp("K2_ClearTimer", system, "Function")
    fully_closed = imp("GetFullyClosed", crack, "Function")
    actor_class = imp("Actor", eng)
    recent = imp("WasRecentlyRendered", actor_class, "Function")
    scene = imp("SceneComponent", eng)
    visible = imp("IsVisible", scene, "Function")
    actor_component = imp("ActorComponent", eng)
    tick = imp("SetComponentTickEnabled", actor_component, "Function")
    mesh = lambda: var("SkeletalMesh", control)
    component = lambda: var("CrackableActorComponent", control)
    freeze = lambda state: assign(
        ctx(mesh(), var("bNoSkeletonUpdate", skel)),
        ex("EX_True" if state else "EX_False"),
    )
    active = lambda: var("BPM_CatalogPosePending")
    started = lambda: var("BPM_CatalogPoseStarted")
    stop_poll = lambda: call(
        clear_timer,
        ex("EX_Self"),
        ex("EX_StringConst", Value="BPM_TrySetCatalogClosedPose"),
    )
    begin = next(e for e in d["Exports"] if e["ObjectName"] == "ReceiveBeginPlay")
    closed_handler = next(
        e
        for e in d["Exports"]
        if e["ObjectName"]
        == "BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_0_OnCrackedStateChanged__DelegateSignature"
    )
    opened_handler = next(
        e
        for e in d["Exports"]
        if e["ObjectName"]
        == "BndEvt__CrackableActorComponent_K2Node_ComponentBoundEvent_1_OnCrackedStateChanged__DelegateSignature"
    )

    def function(n, make, param=False):
        fn = copy.deepcopy(begin)
        fid = len(d["Exports"]) + 1
        fn.update(
            ObjectName=name(n),
            SerialSize=0,
            SerialOffset=0,
            SuperStruct=0,
            SuperIndex=0,
            LoadedProperties=[],
            FunctionFlags="FUNC_Public, FUNC_BlueprintCallable",
        )
        if param:
            f = copy.deepcopy(
                next(
                    p
                    for p in opened_handler["LoadedProperties"]
                    if p["Name"] == "bIsCracked"
                )
            )
            f["Name"] = name("Opened")
            fn["LoadedProperties"] = [f]
        body = make(fid)
        end = sum(map(kismet_size, body))
        for x in body:
            if "CodeOffset" in x:
                x["CodeOffset"] = end
        body.extend(
            [ex("EX_Return", ReturnExpression=ex("EX_Nothing")), ex("EX_EndOfScript")]
        )
        fn.update(ScriptBytecode=body, ScriptBytecodeSize=sum(map(kismet_size, body)))
        assert base64.b64decode(fn["Extras"]) == b"\0" * 8
        fn["CreateBeforeSerializationDependencies"] = [
            cid,
            valid,
            set_timer,
            clear_timer,
            fully_closed,
            control,
            skel,
            recent,
            visible,
            tick,
        ]
        fn["SerializationBeforeSerializationDependencies"] = []
        fn["CreateBeforeCreateDependencies"] = [cid]
        assert append(fn) == fid
        cls["FuncMap"].append([name(n), fid])
        cls["Children"].insert(0, fid)
        cls["CreateBeforeSerializationDependencies"].append(fid)
        return fid

    keep = function(
        "BPM_KeepCatalogClosedPoseUpdating",
        lambda _: [
            guard(active()),
            guard(started()),
            guard(call(valid, mesh())),
            # Vanilla closes with the handle extended and the controls flat.
            # The unevaluated startup mesh can still show the opening pose.
            assign(var("ExtendTop"), ex("EX_True")),
            assign(var("ExtendPanel"), ex("EX_False")),
            freeze(False),
        ],
    )
    function(
        "BPM_FreezeCatalogClosedPose",
        lambda _: [
            assign(active(), ex("EX_False")),
            stop_poll(),
            guard(call(valid, component())),
            guard(ctx(component(), call(fully_closed))),
            guard(call(valid, mesh())),
            freeze(True),
        ],
    )
    attempt = function(
        "BPM_TrySetCatalogClosedPose",
        lambda _: [
            guard(active()),
            guard(call(valid, mesh())),
            guard(ctx(mesh(), call(visible))),
            guard(call(recent, ex("EX_FloatConst", Value=0.25))),
            guard(call(valid, component())),
            guard(ctx(component(), call(fully_closed))),
            assign(started(), ex("EX_True")),
            call(keep, local=True),
            ctx(mesh(), call(tick, ex("EX_True"))),
            stop_poll(),
            call(
                set_timer,
                ex("EX_Self"),
                ex("EX_StringConst", Value="BPM_FreezeCatalogClosedPose"),
                ex("EX_FloatConst", Value=1.0),
                ex("EX_False"),
                ex("EX_FloatConst", Value=0.0),
                ex("EX_FloatConst", Value=0.0),
            ),
        ],
    )
    start = function(
        "BPM_StartCatalogClosedPose",
        lambda _: [
            assign(active(), ex("EX_True")),
            assign(started(), ex("EX_False")),
            call(
                set_timer,
                ex("EX_Self"),
                ex("EX_StringConst", Value="BPM_TrySetCatalogClosedPose"),
                # Begin promptly after the native close transition finishes.
                ex("EX_FloatConst", Value=0.05),
                ex("EX_True"),
                ex("EX_FloatConst", Value=0.0),
                ex("EX_FloatConst", Value=0.0),
            ),
            call(attempt, local=True),
        ],
    )
    cancel = function(
        "BPM_ReleaseCatalogClosedPoseIfOpened",
        lambda fid: [
            guard(ex("EX_LocalVariable", Variable=ptr(fid, "Opened"))),
            assign(active(), ex("EX_False")),
            stop_poll(),
            call(
                clear_timer,
                ex("EX_Self"),
                ex("EX_StringConst", Value="BPM_FreezeCatalogClosedPose"),
            ),
        ],
        param=True,
    )

    def post(wrapper, expr, dependency, before=False):
        code = wrapper["ScriptBytecode"]
        i = next(i for i, x in enumerate(code) if op_type(x) == "EX_Return")
        code.insert(0 if before else i, expr)
        wrapper["ScriptBytecodeSize"] += kismet_size(expr)
        wrapper["CreateBeforeSerializationDependencies"].append(dependency)

    post(begin, call(start, local=True), start)
    post(closed_handler, call(keep, local=True), keep)
    opened_id = d["Exports"].index(opened_handler) + 1
    post(
        opened_handler,
        call(
            cancel,
            ex("EX_LocalVariable", Variable=ptr(opened_id, "bIsCracked")),
            local=True,
        ),
        cancel,
        before=True,
    )
    return d
