"""Version and build settings."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = "0.2.2"
GAME_BUILD = "1.45.1.0"
ITEM_SIZE_MULTIPLIER = 0.8
MAIN_SLOT_SCALE = 0.25 * ITEM_SIZE_MULTIPLIER
OUT = ROOT / "build" / VERSION
# Keep this path stable for existing saves.
PKG = "/Game/Mods/CompactBackpack16/"
PAK_NAME = f"000-BackpackProMax-{VERSION}_P.pak"
ARCHIVE_NAME = f"Backpack-Pro-Max-{VERSION}-Vortex.zip"

# Vanilla catalog transition and mission-log slide fixes; disable after a native fix.
PANEL_RETRACTION_FIX = True
