#!/usr/bin/env python3
"""Temporary engineering inspection of public 6.13.12 IPK source.
Print only selected PUBLIC code regions to GitHub CI log.
"""
import io
import subprocess
import tarfile
from pathlib import Path
base=Path("enigma2-plugin-extensions-goalalert_6.13.12_all.ipk")
tarraw=subprocess.check_output(["ar","p",str(base),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(tarraw),mode="r:xz") as tar:
    files={}
    for entry in tar:
        if entry.isfile() and entry.name.endswith(("/plugin.py","/goalalert_apply_update.py","/goalalert_updater.py","/goalalert_audio.py")):
            files[entry.name.split("/")[-1]]=tar.extractfile(entry).read().decode("utf-8")
for name,code in files.items():
    lines=code.splitlines()
    print("\n###",name,"TOTAL LINES",len(lines))
    if name!="plugin.py":
        for i,line in enumerate(lines):
            if i<170:print("%4d %s"%(i+1,line))
        continue
    anchors=("class GoalPopup(","class Monitor:","class GoalAlertLineupScreen(","class GameDetailScreen(","class GoalAlertUpdateScreen(",
      "class GoalAlertAudio", "class Home(", "def _make_popup_skin(", "def show_goal(self", "def show_lineup(", "def _check_online(", "def begin_install(",
      "def _download(", "def Plugins(", "def _espn_", "class AllLiveScreen(")
    candidates=[i for i,line in enumerate(lines) if any(line.lstrip().startswith(x) for x in anchors)]
    blocks=set()
    for idx in candidates:
        size=180 if "GoalAlertUpdateScreen" in lines[idx] else 110
        if "GoalPopup" in lines[idx]:size=210
        for j in range(max(0,idx-4),min(len(lines),idx+size)):blocks.add(j)
    # add filenames, plugin descriptor, update calls
    for i,line in enumerate(lines):
        if any(x in line for x in ('goalalert_apply_update.py','goalalert_updater','session.openWithCallback','_play_goal_sound','standings','PluginDescriptor(')):
            for j in range(max(0,i-2),min(len(lines),i+5)):blocks.add(j)
    last=-2
    for i in sorted(blocks):
        if i>last+1:print("------")
        print("%4d %s"%(i+1,lines[i]))
        last=i
