"""Local game files and external tools."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
PAK = Path(
    os.environ.get(
        "BPM_GAME_PAK",
        r"C:/Program Files (x86)/Steam/steamapps/common/ASTRONEER/Astro/Content/Paks/pakchunk0-WindowsNoEditor.pak",
    )
)
REPAK = Path(os.environ.get("BPM_REPAK", str(REPO / "tools/repak.exe")))
GUI = Path(os.environ.get("BPM_UASSETGUI", str(REPO / "tools/UAssetGUI.exe")))
UMODEL = Path(os.environ.get("BPM_UMODEL", str(REPO / "tools/umodel.exe")))
ENV = dict(os.environ, DOTNET_ROLL_FORWARD="Major")


def extract(asset, as_json=True):
    dst = ROOT / "vanilla" / asset
    dst.parent.mkdir(parents=True, exist_ok=True)
    for extension in (".uasset", ".uexp"):
        target = dst.with_suffix(extension)
        if not target.exists():
            payload = subprocess.check_output(
                [str(REPAK), "get", str(PAK), asset + extension]
            )
            target.write_bytes(payload)
    if not as_json:
        return dst.with_suffix(".uasset")
    target = dst.with_suffix(".json")
    if not target.exists():
        subprocess.run(
            [
                str(GUI),
                "--portable",
                "tojson",
                str(dst.with_suffix(".uasset")),
                str(target),
                "VER_UE4_27",
                "Astro",
            ],
            env=ENV,
            check=True,
            capture_output=True,
            timeout=90,
        )
    return json.loads(target.read_text())
