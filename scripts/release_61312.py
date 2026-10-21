#!/usr/bin/env python3
"""GoalAlert 6.13.12 hotfix: accept OpenATV /tmp symlink safely.

Earlier installers 6.13.6 through 6.13.11 rejected valid IPKs when
os.path.realpath('/tmp') != '/tmp'. This patch compares canonical paths to
the same canonical staging directory. SHA-256, control fields and correct
package naming remain mandatory. No private settings or bouquets included.
"""
import hashlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import os
import sys
import tempfile
import runpy

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.11_all.ipk'
EXPECTED_SHA='0fe46b5e4095521fdad3c1c294df46f6b435068e360c4cb150adeba666630831'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED_SHA:
    raise SystemExit('Pinned GoalAlert 6.13.11 base missing or SHA-256 mismatch')
if DEST.exists():
    raise SystemExit('Unexpected source already present; refusing overwrite')
DEST.mkdir(parents=True)
blob=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(blob), mode='r:xz') as tar:
    for m in tar:
        entry=m.name.lstrip('./')
        if not entry.startswith(PREFIX) or not m.isfile():continue
        relative=entry[len(PREFIX):]
        if not relative or '..' in PurePosixPath(relative).parts:
            raise SystemExit('Unsafe package member')
        if relative.endswith(('.pyc','.log','.m3u','.m3u8')) or '__pycache__' in relative or 'iptv_names_' in relative:
            continue
        dest=DEST/relative
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(tar.extractfile(m).read())

helper=DEST/'goalalert_apply_update.py'
source=helper.read_text(encoding='utf-8')
old="""        if os.path.dirname(os.path.realpath(ipk))!='/tmp' or not os.path.basename(ipk).startswith(PKG+'_'):
            raise ValueError('Ungueltiger Paketpfad')"""
new="""        if not staged_package_ok(ipk):
            raise ValueError('Ungueltiger Paketpfad (erwartet: sichere GoalAlert-IPK in /tmp)')"""
if source.count(old)!=1:
    raise SystemExit('Actual installer source differs from expected 6.13.11')
source=source.replace(old,new,1)
marker='def main(args=None):'
check='''def staged_package_ok(ipk, stage_dir='/tmp'):
    """Safe path check even if /tmp is symlinked to /var/volatile/tmp.

    Canonicalise both the actual IPK and the intended staging directory.
    Reject parent escapes and unexpected package names. The installer
    independently re-verifies sha256 and IPK control metadata below.
    """
    realdir=os.path.realpath(stage_dir)
    actual=os.path.realpath(ipk)
    basename=os.path.basename(actual)
    return (os.path.isfile(actual)
            and os.path.dirname(actual)==realdir
            and basename.startswith(PKG+'_')
            and basename.endswith('_all.ipk'))

'''
if source.count(marker)!=1:
    raise SystemExit('Installer entry anchor missing')
source=source.replace(marker,check+marker,1)
helper.write_text(source,encoding='utf-8')

# Optional improvement: error messages should not falsely claim the
# upgrade has started when path validation failed.
plugin=DEST/'plugin.py'
text=plugin.read_text(encoding='utf-8')
if text.count('6.13.11')<2:
    raise SystemExit('Expected version references absent')
text=text.replace('6.13.11','6.13.12')
plugin.write_text(text,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.12\n',encoding='utf-8')

compile(text,str(plugin),'exec')
compile(source,str(helper),'exec')

# Regression: canonical directory, OpenATV-style /tmp symlink, unsafe path,
# and file name mismatches. No root permissions or real receiver required.
sys.path.insert(0,str(DEST))
ns=runpy.run_path(str(helper),run_name='goalalert_install_test')
allowed=ns['staged_package_ok']
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    canonical=root/'var'/'volatile'/'tmp'
    canonical.mkdir(parents=True)
    logical=root/'tmp'
    logical.symlink_to(canonical, target_is_directory=True)
    right=canonical/'enigma2-plugin-extensions-goalalert_6.13.12_all.ipk'
    right.write_bytes(b'verified separately in installer')
    assert allowed(str(logical/right.name),str(logical))
    assert allowed(str(right),str(logical))
    badname=canonical/'other-plugin_6.13.12_all.ipk'
    badname.write_bytes(b'x')
    assert not allowed(str(badname),str(logical))
    outside=root/'other'
    outside.mkdir()
    escape=outside/right.name
    escape.write_bytes(b'x')
    assert not allowed(str(escape),str(logical))
    indirect=canonical/'enigma2-plugin-extensions-goalalert_6.13.13_all.ipk'
    indirect.symlink_to(escape)
    assert not allowed(str(indirect),str(logical))
    assert not allowed(str(logical/'missing.ipk'),str(logical))
print('Regression tests: symlinked /tmp, local IPK, wrong name and traversal OK')
# Imported modules can create caches; never ship generated bytecode.
import shutil
for cache in DEST.rglob('__pycache__'):
    shutil.rmtree(cache)
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('6.13.12 repair package built and checked')
