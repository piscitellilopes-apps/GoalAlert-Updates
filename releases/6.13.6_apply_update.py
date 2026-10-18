#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verified detached GoalAlert installer for OpenATV/Enigma2.

Do not stop Enigma2 before running opkg: init 4 could kill the helper before
it performs the upgrade. Restart the GUI only AFTER a successful opkg exit.
"""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from goalalert_updater import _ar_members

LOG='/home/root/goalalert_update.log'
STATE='/tmp/goalalert_update_status.json'
PKG='enigma2-plugin-extensions-goalalert'

def notify(state,message):
    data={'state':state,'message':str(message)[:220], 'time':datetime.datetime.now().isoformat()}
    try:
        temp=STATE+'.tmp'
        with open(temp,'w') as f:json.dump(data,f)
        os.replace(temp,STATE)
    except Exception:pass
    try:
        with open(LOG,'a') as f:
            f.write(data['time']+' '+state+': '+data['message']+'\n')
    except Exception:pass

def run(cmd,timeout):
    p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    output=p.stdout.decode('utf-8','replace')
    for line in output.splitlines()[-35:]:
        try:
            with open(LOG,'a') as f:f.write(line[:240]+'\n')
        except Exception:pass
    return p.returncode,output

def main(args=None):
    args=sys.argv[1:] if args is None else args
    if len(args)!=4 or args[0]!='--install' or args[2]!='--sha256':
        notify('failed','Installationsparameter ungueltig')
        return 1
    ipk=args[1]
    expected=args[3].lower()
    try:
        if os.path.dirname(os.path.realpath(ipk))!='/tmp' or not os.path.basename(ipk).startswith(PKG+'_'):
            raise ValueError('Ungueltiger Paketpfad')
        if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
            raise ValueError('Ungueltige SHA256')
        ctrl=_ar_members(ipk)
        fields={}
        for line in ctrl.splitlines():
            if ':' in line and not line[0].isspace():
                k,v=line.split(':',1);fields[k.strip()]=v.strip()
        if fields.get('Package')!=PKG:raise ValueError('Paketname stimmt nicht')
        digest=hashlib.sha256()
        with open(ipk,'rb') as f:
            for chunk in iter(lambda:f.read(65536),b''):digest.update(chunk)
        if digest.hexdigest()!=expected:raise ValueError('SHA256 hat sich veraendert')
        binary=shutil.which('opkg')
        if not binary:raise ValueError('opkg auf dieser Box nicht gefunden')
    except Exception as exc:
        notify('failed','Paketpruefung: '+str(exc))
        return 2
    notify('installing','Paket geprueft; installiere mit opkg ...')
    try:
        ret,output=run([binary,'install','--force-overwrite','--force-reinstall',ipk],timeout=240)
    except Exception as exc:
        notify('failed','opkg konnte nicht gestartet werden: '+repr(exc)[:140])
        return 3
    if ret!=0:
        notify('failed','opkg fehlgeschlagen (%s): %s'%(ret,output[-140:].replace('\n',' ')))
        return 4
    notify('installed','GoalAlert installiert; Enigma2 wird neu gestartet ...')
    time.sleep(2)
    init='/sbin/init' if os.path.isfile('/sbin/init') else shutil.which('init')
    if not init:
        notify('failed','Plugin installiert, aber init fehlt. Bitte Enigma2 im Menue neu starten.')
        return 5
    try:
        # On standard OpenATV images: runlevel 4 stops GUI, 3 restarts it.
        ret,_=run([init,'4'],timeout=40)
        if ret!=0:raise RuntimeError('init 4 Fehler %s'%ret)
        time.sleep(3)
        ret,_=run([init,'3'],timeout=40)
        if ret!=0:raise RuntimeError('init 3 Fehler %s'%ret)
        notify('restarted','GoalAlert installiert und GUI-Neustart angefordert')
    except Exception as exc:
        notify('failed','Plugin installiert; GUI-Neustart fehlgeschlagen: '+str(exc)[:110])
        return 6
    return 0

if __name__=='__main__':sys.exit(main())
