"""Package verified 0.1.11 for manual Vortex installation; preserve earlier versions."""
import hashlib,json,shutil,zipfile
from native_revision_0111 import HERE,OUT
DIST=HERE.parent/'dist'
DIST.mkdir(exist_ok=True)
report=json.loads((OUT/'build-report.json').read_text())
assert len(report['offline_checks'])==16
pak=OUT/'000-CompactBackpack16-0.1.11_P.pak'
assert hashlib.sha256(pak.read_bytes()).hexdigest()==report['pak_sha256']
archive=DIST/'Backpack-Deluxe-0.1.11-test-Vortex.zip'
assert not archive.exists(),'Preserve an already delivered archive.'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:z.write(pak,pak.name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None and z.namelist()==[pak.name]
    assert z.read(pak.name)==pak.read_bytes()
release={'archive':str(archive),'bytes':archive.stat().st_size,
         'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
         'pak_sha256':report['pak_sha256'],'installed':False,'gameplay_tested':False}
(OUT/'release-report.json').write_text(json.dumps(release,indent=2))
print(json.dumps(release,indent=2))
