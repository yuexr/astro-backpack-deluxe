"""Zip the checked PAK for Vortex."""

import hashlib
import json
import zipfile

from settings import ARCHIVE_NAME, OUT, PAK_NAME, ROOT, VERSION

DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
report = json.loads((OUT / "build-report.json").read_text())
assert len(report["offline_checks"]) == 16
pak = OUT / PAK_NAME
assert hashlib.sha256(pak.read_bytes()).hexdigest() == report["pak_sha256"]
archive = DIST / ARCHIVE_NAME
assert not archive.exists(), "Preserve an already delivered archive."
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(pak, pak.name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and z.namelist() == [pak.name]
    assert z.read(pak.name) == pak.read_bytes()
release = {
    "version": VERSION,
    "archive": str(archive),
    "bytes": archive.stat().st_size,
    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
    "pak_sha256": report["pak_sha256"],
    "installed": False,
    "gameplay_tested": False,
}
(OUT / "release-report.json").write_text(json.dumps(release, indent=2))
print(f"Ready: {archive}")
