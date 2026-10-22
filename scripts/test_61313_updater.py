#!/usr/bin/env python3
"""End-to-end offline updater contract for the GoalAlert release.

Tests publication manifest, downloaded-IPK-equivalent bytes, control metadata,
SHA-256, /tmp resolution, and mocked opkg plus GUI restart. NEVER restarts OS.
"""
import hashlib, io, json, os, pathlib, runpy, shutil, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
V='6.13.13'
NAME='enigma2-plugin-extensions-goalalert_'+V+'_all.ipk'
PKG=ROOT/NAME
UPDATER=ROOT/'source/GoalAlert/goalalert_updater.py'
APPLY=ROOT/'source/GoalAlert/goalalert_apply_update.py'
FIXED='https://raw.githubusercontent.com/piscitellilopes-apps/GoalAlert-Updates/main/latest.json'
manifest=json.loads((ROOT/'latest.json').read_text(encoding='utf-8'))
assert PKG.exists() and PKG.stat().st_size>100000
digest=hashlib.sha256(PKG.read_bytes()).hexdigest()
assert manifest['sha256']==digest
assert manifest['package']=='enigma2-plugin-extensions-goalalert'
assert manifest['version']==V
assert manifest['url']==FIXED.replace('latest.json',NAME)
sys.path.insert(0,str(UPDATER.parent))
u=runpy.run_path(str(UPDATER),run_name='goalalert_updater_test')
assert u['DEFAULT_SOURCE']==FIXED
# urllib mock – the exact JSON that the TV reads, no network required.
u['check_manifest'].__globals__['_open_https']=lambda url,timeout=10: io.BytesIO((ROOT/'latest.json').read_bytes())
info=u['check_manifest'](FIXED,'6.13.12')
assert info['newer'] and info['version']==V and info['sha256']==digest
assert u['check_manifest'](FIXED,V)['newer'] is False
assert u['verify_ipk'](str(PKG),'6.13.12')==V
g=runpy.run_path(str(APPLY),run_name='goalalert_installer_test')
assert callable(g['staged_package_ok'])
stage=pathlib.Path('/tmp')/NAME
if stage.exists():raise SystemExit('Staged file path collision; refusing test')
shutil.copy2(PKG,stage)
try:
    assert g['staged_package_ok'](str(stage))
    trace=[]
    g['main'].__globals__['notify']=lambda state,msg:trace.append(('status',state,msg))
    g['main'].__globals__['run']=lambda argv,timeout: (trace.append(('command',list(argv))) or (0,'TEST opkg installed; GUI restart simulated'))
    which=g['shutil'].which
    g['shutil'].which=lambda name:'/usr/bin/opkg' if name=='opkg' else which(name) or '/sbin/init'
    g['time'].sleep=lambda seconds:None
    outcome=g['main'](['--install',str(stage),'--sha256',digest])
    assert outcome==0,(outcome,trace)
    assert any(t[:2]==('status','installed') for t in trace)
    assert any(t[0]=='command' and t[1][0]=='/usr/bin/opkg' and str(stage) in t[1] for t in trace)
    assert any(t[0]=='command' and t[1][1:] == ['4'] for t in trace)
    assert any(t[0]=='command' and t[1][1:] == ['3'] for t in trace)
    trace.clear()
    outcome=g['main'](['--install',str(stage),'--sha256','0'*64])
    assert outcome!=0 and not any(t[0]=='command' for t in trace)
    print('OK: fake online metadata, SHA-256, IPK parsing, mocked opkg, GUI restart, corrupt-hash rejection')
finally:
    stage.unlink(missing_ok=True)
