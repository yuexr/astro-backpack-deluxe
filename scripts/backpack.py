"""Add the extra slots and apply the backpack changes."""

import copy
import hashlib
import json
import subprocess
import uuid

from asset_io import HERE, append, es, location, name, prop, ps, setbool, xyz
from catalog import patch_catalog_startup
from game_assets import ENV, GUI, REPAK, extract
from mesh_assets import build_meshes
from settings import (
    GAME_BUILD,
    ITEM_SIZE_MULTIPLIER,
    MAIN_SLOT_SCALE,
    OUT,
    PAK_NAME,
    PKG,
    VERSION,
)
from visuals import add_visual_components

STAGE = OUT / "staging"


def add_inventory_slots(d, corpse=False):
    """Duplicate native component templates, then extend the native resource array.
    Existing eight names/order are stable for saves. New slots follow them.
    """
    original_names = [
        ("ChildSlot" + (str(i) if i else "")) if corpse else f"Item Slot {i + 1}"
        for i in range(8)
    ]
    extra_names = [
        f"ChildSlot{i}" if corpse else f"Item Slot {i + 1}" for i in range(8, 16)
    ]
    exports = es(d)
    cls = next(x for x in d["Exports"] if "ClassExport" in x["$type"])
    for i, newname in enumerate(extra_names):
        oldname = original_names[i]
        old = exports[oldname + "_GEN_VARIABLE"]
        oldid = d["Exports"].index(old) + 1
        oldnode = next(
            e
            for e in d["Exports"]
            if ps(e).get("ComponentTemplate", {}).get("Value") == oldid
        )
        oldnodeid = d["Exports"].index(oldnode) + 1
        parent = next(
            e
            for e in d["Exports"]
            if any(
                x.get("Value") == oldnodeid
                for x in ps(e).get("ChildNodes", {}).get("Value", [])
            )
        )
        scs = d["Exports"][oldnode["OuterIndex"] - 1]
        component = copy.deepcopy(old)
        component.update(
            ObjectName=name(d, newname + "_GEN_VARIABLE"), SerialSize=0, SerialOffset=0
        )
        ci = append(d, component)
        node = copy.deepcopy(oldnode)
        node.update(
            ObjectName=name(d, "SCS_CB16_" + newname.replace(" ", "")),
            SerialSize=0,
            SerialOffset=0,
        )
        ps(node)["ComponentTemplate"]["Value"] = ci
        ps(node)["InternalVariableName"]["Value"] = name(d, newname)
        ps(node)["VariableGuid"]["Value"][0]["Value"] = (
            "{"
            + str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    "compact16." + ("corpse." if corpse else "live.") + newname,
                )
            ).upper()
            + "}"
        )
        for k in [
            "CreateBeforeSerializationDependencies",
            "SerializationBeforeSerializationDependencies",
            "CreateBeforeCreateDependencies",
            "SerializationBeforeCreateDependencies",
        ]:
            node[k] = [ci if v == oldid else v for v in node.get(k, [])]
        ni = append(d, node)
        for owner, key in [(parent, "ChildNodes"), (scs, "AllNodes")]:
            values = ps(owner)[key]["Value"]
            values.append(prop(d, "Object", str(len(values)), ni))
            owner["CreateBeforeSerializationDependencies"].append(ni)
        field = copy.deepcopy(
            next(x for x in cls["LoadedProperties"] if x["Name"] == oldname)
        )
        field["Name"] = name(d, newname)
        cls["LoadedProperties"].append(field)
        cls["CreateBeforeSerializationDependencies"].append(ci)
    constructor = exports["UserConstructionScript"]
    code = constructor["ScriptBytecode"]
    arrays = [
        x for x in code if ".EX_SetArray," in x["$type"] and len(x["Elements"]) == 8
    ]
    assert len(arrays) == 1
    template = next(
        x["Expression"]
        for x in code
        if x.get("Expression", {})
        .get("ContextExpression", {})
        .get("Parameters", [{}])[0]
        .get("Value")
        == original_names[-1]
    )
    assert template["Offset"] == 23
    for variable in extra_names:
        expr = copy.deepcopy(template)
        expr["ContextExpression"]["Parameters"][0]["Value"] = name(d, variable)
        arrays[0]["Elements"].append(expr)
    # EX_Context: opcode + skip offset + result property (13), instance (9),
    # final function (10), FName constant (13) = 45 bytes per expression.
    constructor["ScriptBytecodeSize"] += 45 * 8
    assert not any("CodeOffset" in x or "PushingAddress" in x for x in code)
    return original_names + extra_names


def private_body(d):
    old = "/Game/Models/backpack_mk2/backpack_mk2"
    new = PKG + "backpack_mk2"
    name(d, new)
    for x in d["Imports"]:
        if x["ObjectName"] == old:
            x["ObjectName"] = new


def configure(d, slot_names, front, corpse=False):
    ex = es(d)
    parent = "ItemSlots" if corpse else "Item Slots"
    origin = xyz(ps(ex[parent + "_GEN_VARIABLE"])["RelativeLocation"])
    setbool(d, ex[parent + "_GEN_VARIABLE"], "bUseAttachParentBound", True)
    # Keep the native item attachment-to-visible-socket depth offset.
    native_cx = json.loads((OUT / "socket-source.json").read_text())["centre"][0]
    geometry = json.loads((OUT / "geometry-report.json").read_text())
    target_x = geometry["socket_centre_native_x"] + (-15.1315727234 - native_cx)
    for n, var in enumerate(slot_names):
        e = ex[var + "_GEN_VARIABLE"]
        side = (1 if n % 2 == 0 else -1) if corpse else (-1 if n % 2 == 0 else 1)
        y = side * (40 if n < 8 else 18)
        z = [47.0, 14.3, -18.1, -51.0][n % 8 // 2]
        location(d, e, [target_x - origin["X"], y - origin["Y"], z - origin["Z"]])
        # Resize the items, leaving the socket meshes alone.
        assert all(
            abs(float(xyz(ps(e)["RelativeScale3D"])[k]) - 0.25) < 1e-7 for k in "XYZ"
        )
        xyz(ps(e)["RelativeScale3D"]).update(
            X=MAIN_SLOT_SCALE, Y=MAIN_SLOT_SCALE, Z=MAIN_SLOT_SCALE
        )
        setbool(d, e, "SlotVisible", False)
        setbool(d, e, "bVisible", False)
    for key in ["Power Bar_GEN_VARIABLE"] + (
        [] if corpse else ["PowerBarOverlay_GEN_VARIABLE"]
    ):
        p = ps(ex[key])
        scale = xyz(p["RelativeScale3D"])
        scale.update(X=0.09, Y=0.09)
        xyz(p["RelativeLocation"]).update(X=geometry["battery_centre_native_x"], Y=0.0)
    if not corpse:
        # Suppress only the original mount visual; its attachment slot stays native.
        setbool(d, ex["Creative Drone Slot_GEN_VARIABLE"], "SlotVisible", False)
        # Hide the tiny printer speck while the printer is closed.
        printer = ex["CLIENT Printer View"]["ScriptBytecode"]
        for i in [1, 7, 13]:
            assert abs(printer[i]["Expression"]["Value"] - 0.1) < 1e-7
            printer[i]["Expression"]["Value"] = 0.001
        for i in [4, 10, 16]:
            assert abs(printer[i]["Expression"]["Parameters"][1]["Value"] - 0.1) < 1e-7
            printer[i]["Expression"]["Parameters"][1]["Value"] = 0.001
    private_body(d)
    add_visual_components(d, front, corpse)


def write_asset(d, target, label):
    for gen in d["Generations"]:
        gen["NameCount"] = len(d["NameMap"])
        gen["ExportCount"] = len(d["Exports"])
    source = OUT / (label + ".json")
    source.write_text(json.dumps(d, separators=(",", ":")))
    target = STAGE / target
    target.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [str(GUI), "--portable", "fromjson", str(source), str(target), "Astro"],
        env=ENV,
        check=True,
        timeout=120,
        capture_output=True,
    )
    assert target.exists() and target.with_suffix(".uexp").exists(), (
        label,
        r.stdout,
        r.stderr,
    )


def build():
    meshes, geometry = build_meshes()
    for label, d in meshes.items():
        write_asset(d, f"Astro/Content/Mods/CompactBackpack16/{label}.uasset", label)
    provenance = {}
    for asset, corpse in [
        ("Items/BackpackRail", False),
        ("Character/AstroCorpse", True),
    ]:
        path = HERE / "vanilla/Astro/Content" / asset
        d = extract("Astro/Content/" + asset)
        provenance[asset] = {
            ext: hashlib.sha256(path.with_suffix(ext).read_bytes()).hexdigest()
            for ext in [".uasset", ".uexp"]
        }
        names = add_inventory_slots(d, corpse)
        configure(d, names, geometry["front_components"], corpse)
        write_asset(d, "Astro/Content/" + asset + ".uasset", asset.rsplit("/", 1)[-1])
    catalog = patch_catalog_startup()
    write_asset(
        catalog, "Astro/Content/Items/Catalog/BackpackCatalog.uasset", "BackpackCatalog"
    )
    metadata = {
        "schema_version": 2,
        "name": "Backpack Pro Max (test)",
        # Keep the same mod ID when replacing an older version.
        "mod_id": "CompactBackpack16",
        "author": "yuexr",
        "description": "16 backpack slots. Main-slot items are 80% of vanilla size.",
        "version": VERSION,
        "game_build": GAME_BUILD,
        "sync": "serverclient",
    }
    (STAGE / "metadata.json").write_text(json.dumps(metadata, indent=2))
    pak = OUT / PAK_NAME
    subprocess.run(
        [str(REPAK), "pack", str(STAGE), str(pak)],
        check=True,
        timeout=120,
        capture_output=True,
    )
    report = {
        "version": VERSION,
        "vanilla_sources": provenance,
        "geometry": geometry,
        "main_slot_scale": MAIN_SLOT_SCALE,
        "item_size_multiplier": ITEM_SIZE_MULTIPLIER,
        "native_auxiliaries_unchanged": True,
        "controls_and_drone": "vanilla transforms and drone geometry; separate mount shares backpack material and native socket UVs",
        "installed": False,
        "gameplay_tested": False,
        "pak_sha256": hashlib.sha256(pak.read_bytes()).hexdigest(),
    }
    (OUT / "build-report.json").write_text(json.dumps(report, indent=2))
    print("Built", pak)


if __name__ == "__main__":
    build()
