"""Build and package Backpack Pro Max."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    from game_assets import GUI, PAK, REPAK, UMODEL
    from settings import VERSION

    parser = argparse.ArgumentParser(
        description=f"Backpack Pro Max {VERSION} build tools.",
        epilog=(
            "Install requirements.txt first. Set BPM_REPAK, BPM_UASSETGUI and "
            "BPM_UMODEL, or put the tools in tools/. Set BPM_GAME_PAK if needed. "
            "The model comes from models/backpack-pro-max.glb. Blender is optional. "
            "Builds stay local; nothing is installed into the game."
        ),
    )
    parser.add_argument("command", choices=["prepare", "build", "verify", "package"])
    args = parser.parse_args()
    for label, path in [
        ("BPM_GAME_PAK", PAK),
        ("BPM_REPAK", REPAK),
        ("BPM_UASSETGUI", GUI),
        ("BPM_UMODEL", UMODEL),
    ]:
        if not path.is_file():
            parser.error(f"{label}: file not found: {path}")

    steps = {
        "prepare": ["prepare_assets.py"],
        "build": ["prepare_assets.py", "backpack.py", "verify.py"],
        "verify": ["verify.py"],
        "package": ["verify.py", "package.py"],
    }
    for script in steps[args.command]:
        subprocess.run([sys.executable, str(ROOT / "scripts" / script)], check=True)


if __name__ == "__main__":
    main()
