#!/usr/bin/env python3
"""Build GoalAlert 6.13.11 from cryptographically pinned 6.13.10.

Replace the incorrect alpha-off renderer; add true glass blending,
high-quality badge edges, four user-selectable cheer sounds and mixer-first
playback with diagnostics. Changes must pass static tests before publishing.
"""
import hashlib
import io
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.10_all.ipk'
CHECKSUM='59ff3629a31c749991b4f554f52dd92819d9798771253aa821840909a2449d08'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=CHECKSUM:
    raise SystemExit('Verified 6.13.10 base package missing or modified')
if DEST.exists():
    raise SystemExit('Refuse to overwrite source directory')
DEST.mkdir(parents=True)
data=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as tf:
    for item in tf:
        name=item.name.lstrip('./')
        if not name.startswith(PREFIX) or not item.isfile():continue
        rel=name[len(PREFIX):]
        if not rel or '..' in PurePosixPath(rel).parts:raise RuntimeError('Unsafe IPK entry')
        if rel.endswith(('.pyc','.m3u','.m3u8','.log')) or '__pycache__' in rel or 'iptv_names_' in rel:
            continue
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tf.extractfile(item).read())

path=DEST/'plugin.py'
s=path.read_text(encoding='utf-8')
def patch(old,new):
    global s
    count=s.count(old)
    if count!=1:
        raise SystemExit('Patch anchor mismatch %d for %s'%(count,old[:100]))
    s=s.replace(old,new,1)

# 6.13.10 made SCREEN transparent but left ePixmap alphatest='off',
# which can render an opaque black rectangular pixmap over the TV.
patch('name="theme_bg" pixmap="{root}{theme}" position="0,0" size="{w},{h}" zPosition="0" alphatest="off"',
      'name="theme_bg" pixmap="{root}{theme}" position="0,0" size="{w},{h}" zPosition="0" transparent="1" alphatest="blend"')
patch('<screen name="GoalPopup" position="center,18" size="{w},{h}" flags="wfNoBorder" transparent="1" backgroundColor="#FF000000">',
      '<screen name="GoalPopup" position="center,18" size="{w},{h}" flags="wfNoBorder" transparent="1" backgroundColor="transparent">')
# Smooth anti-aliased edges of high-res ESPN crests.
for name in ('homecrest','awaycrest'):
    anchor='name="%s" position='%name
    start=s.index(anchor,s.index('class GoalPopup(Screen):'))
    stop=s.index('/>',start)+2
    tag=s[start:stop]
    if 'alphatest="on"' not in tag:raise RuntimeError('Missing logo pixmap '+name)
    s=s[:start]+tag.replace('alphatest="on"','alphatest="blend" transparent="1"')+s[stop:]

# Extra config is declared independently of the existing subsection to avoid
# resetting users' prior favourites, source settings and popup dimensions.
patch('# Favoriten bleiben in einer separaten JSON-Datei gespeichert.',
'''if not hasattr(config.plugins.goalalert32,"cheer_style"):
    config.plugins.goalalert32.cheer_style=ConfigSelection(default="classic",
        choices=[("classic","Klassisch"),("stadium","Stadion-Echo"),
                 ("double","Doppeljubel"),("short","Kurzer Tor-Ruf")])
# Favoriten bleiben in einer separaten JSON-Datei gespeichert.''')

# Settings menu indices: 0 alarm, 1 duration, 2 popup size,
# 3 new cheering choice, 4 goal test, 5 silent scorer test,
# 6 IPTV index, 7 API key.
patch('''            "Popup-Groesse: "+size_names.get(c.popup_size.value,'Kompakt'),
            "Test-Toralarm anzeigen",''',
'''            "Popup-Groesse: "+size_names.get(c.popup_size.value,'Kompakt'),
            "Torjubel: "+{"classic":"Klassisch","stadium":"Stadion-Echo",
                         "double":"Doppeljubel","short":"Kurzer Tor-Ruf"}.get(c.cheer_style.value,"Klassisch"),
            "Test-Toralarm anzeigen",''')
patch('''        if i==6:
            self.session.openWithCallback(self.save_api_key,VirtualKeyBoard,title="API-Football Schluessel",text=api_key())''',
'''        if i==7:
            self.session.openWithCallback(self.save_api_key,VirtualKeyBoard,title="API-Football Schluessel",text=api_key())''')
patch('''        elif i==3:monitor.test_goal()
        elif i==4:monitor.test_scorer()
        elif i==5:self.rebuild_index()''',
'''        elif i==3:
            values=["classic","stadium","double","short"]
            c.cheer_style.value=values[(values.index(c.cheer_style.value)+1)%len(values)]
        elif i==4:monitor.test_goal()
        elif i==5:monitor.test_scorer()
        elif i==6:self.rebuild_index()''')
patch('''        c.enabled.save();c.duration.save();c.popup_size.save();configfile.save()''',
'''        c.enabled.save();c.duration.save();c.popup_size.save();c.cheer_style.save();configfile.save()''')

patch('''    def play_sound(self,root):
        _play_goal_sound(root+'goal.wav')''',
'''    def play_sound(self,root):
        from .goalalert_audio import cheer_path, play
        play(cheer_path(root,config.plugins.goalalert32.cheer_style.value))''')

# Keep the public _play_goal_sound API for audio diagnosis and other callers.
# All detailed mixer error messages live in the new module.
start=s.index('def _play_goal_sound(path):',s.index("AUDIO_LOG='/etc/enigma2/goalalert_audio.log'"))
end=s.index('\ndef _audio_log(line):',start)
s=s[:start]+'''def _play_goal_sound(path):
    from .goalalert_audio import play
    return play(path)

'''+s[end:]

patch("        self.setup('TORJUBEL | AUDIO-DIAGNOSE', [],\n                   'OK: Torjubel erneut abspielen | BLAU: Protokoll aktualisieren')",
      "        self.setup('TORJUBEL | AUDIO-DIAGNOSE', [],\n                   'OK: Testen | GELB: Jubel wechseln | BLAU: Protokoll aktualisieren')")
patch("        rows=['OK: TORJUBEL TESTEN',",
'''        choice=config.plugins.goalalert32.cheer_style.value
        labels={"classic":"Klassisch","stadium":"Stadion-Echo","double":"Doppeljubel","short":"Kurzer Tor-Ruf"}
        rows=['OK: TORJUBEL TESTEN | '+labels.get(choice,choice),''')
patch('''            path='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/goal.wav'
            if _play_goal_sound(path):''',
'''            from .goalalert_audio import cheer_path
            path=cheer_path('/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/',
                            config.plugins.goalalert32.cheer_style.value)
            if _play_goal_sound(path):''')
patch('\nclass Monitor:\n',
'''    def yellow(self):
        c=config.plugins.goalalert32.cheer_style
        values=["classic","stadium","double","short"]
        c.value=values[(values.index(c.value)+1)%len(values)]
        c.save();configfile.save()
        self.blue()
        self["hint"].setText("Jubel gespeichert | OK: Bei laufendem TV-Ton testen")

class Monitor:
''')

# Generate strictly licensed local sound variants, not remote copyrighted files.
(DEST/'goalalert_audio.py').write_text(
    (ROOT/'scripts/goalalert_audio_lib.py').read_text(encoding='utf-8'),encoding='utf-8')
subprocess.run(['python3','scripts/goalalert_cheer_variants.py'],cwd=ROOT,check=True)
# Further reduce opaque glass fill. The PNG alpha is now actually blended.
from PIL import Image
pngs=list(DEST.glob('ga_popup_*.png'))
assert len(pngs)>=12
for file in pngs:
    with Image.open(file) as handle:im=handle.convert('RGBA')
    im.putalpha(im.getchannel('A').point(lambda v:int(v*0.72)))
    w,h=im.size
    assert im.getpixel((0,0))[3]==0 and im.getpixel((w-1,h-1))[3]==0
    im.save(file,optimize=True)

if s.count('6.13.10')<2:raise SystemExit('Version references absent')
s=s.replace('6.13.10','6.13.11')
path.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.11\n',encoding='utf-8')
compile(s,str(path),'exec')
for name in ('goalalert_audio.py','goalalert_standings.py'):
    compile((DEST/name).read_text(encoding='utf-8'),name,'exec')
assert 'alphatest="blend"' in s
assert 'backgroundColor="transparent"' in s
assert 'GELB: Jubel wechseln' in s
assert 'c.cheer_style.save()' in s
for name in ('goal_stadium.wav','goal_double.wav','goal_short.wav'):
    assert (DEST/name).stat().st_size>5000
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('6.13.11: alpha-blended glass, HQ crest edges and audio presets checked')
