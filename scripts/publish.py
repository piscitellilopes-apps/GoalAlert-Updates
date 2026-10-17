#!/usr/bin/env python3
"""Validate public GoalAlert IPKs and generate latest.json on GitHub Actions."""
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

PKG = 'enigma2-plugin-extensions-goalalert'
MAX_BYTES = 16 * 1024 * 1024
PATTERN = re.compile(r'^enigma2-plugin-extensions-goalalert_(\d+(?:\.\d+){1,4})_all\.ipk$')

def read_member(ipk, part):
    return subprocess.check_output(['ar', 'p', str(ipk), part])

def validate(ipk):
    match = PATTERN.fullmatch(ipk.name)
    if not match or ipk.stat().st_size > MAX_BYTES:
        raise ValueError('Filename or size not allowed: ' + ipk.name)
    members = subprocess.check_output(['ar', 't', str(ipk)], text=True).splitlines()
    if 'control.tar.xz' not in members or 'data.tar.xz' not in members:
        raise ValueError('Missing IPK sections')
    with tarfile.open(fileobj=io.BytesIO(read_member(ipk, 'control.tar.xz')), mode='r:xz') as t:
        control = t.extractfile(next(m for m in t.getmembers() if m.name.lstrip('./') == 'control')).read().decode('utf-8')
    fields = {}
    for line in control.splitlines():
        if ':' in line and not line[0].isspace():
            key, value = line.split(':', 1)
            fields[key] = value.strip()
    if fields.get('Package') != PKG or fields.get('Version') != match.group(1) or fields.get('Architecture') != 'all':
        raise ValueError('IPK control does not match filename/package')
    with tarfile.open(fileobj=io.BytesIO(read_member(ipk, 'data.tar.xz')), mode='r:xz') as t:
        for m in t.getmembers():
            name = m.name.lower()
            if ('iptv_names_' in name or name.endswith(('.m3u', '.m3u8')) or '/etc/enigma2/' in name):
                raise ValueError('Potentially private IPTV data in release: ' + m.name)
    return match.group(1)

def main():
    files = list(Path('.').glob('enigma2-plugin-extensions-goalalert_*_all.ipk'))
    if not files:
        raise SystemExit('No public GoalAlert IPK found')
    versions = [(tuple(map(int, validate(p).split('.'))), p) for p in files]
    _, newest = max(versions, key=lambda x: x[0])
    version = validate(newest)
    digest = hashlib.sha256(newest.read_bytes()).hexdigest()
    repo = os.environ.get('GITHUB_REPOSITORY', 'piscitellilopes-apps/GoalAlert-Updates')
    manifest = {
        'package': PKG,
        'version': version,
        'url': f'https://raw.githubusercontent.com/{repo}/main/{newest.name}',
        'sha256': digest,
        'notes': 'GoalAlert Update. Vor Installation Hinweise und bekannte Probleme pruefen.'
    }
    Path('latest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Validated {newest.name} SHA-256 {digest}; latest.json published for {version}')

if __name__ == '__main__':
    main()
