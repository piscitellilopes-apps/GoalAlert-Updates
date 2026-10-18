#!/usr/bin/env python3
"""GoalAlert 6.13.10: league table hotkey and clear glass overlays.

Rebuild from exact previously published 6.13.9 package. No user settings,
private IPTV index or credentials are packaged. GitHub publishes on success.
"""
from __future__ import print_function
import hashlib
import io
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.9_all.ipk"
EXPECTED="5098969a7ef7d29dd52fbaca4da60d62dea565d4c303cf763c169886cfc55c01"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED:
    raise SystemExit("Verified 6.13.9 package missing or changed")
if DEST.exists():
    raise SystemExit("Refusing to overwrite unexpected source data")
DEST.mkdir(parents=True)
tar_blob=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(tar_blob),mode="r:xz") as archive:
    for member in archive:
        p=member.name.lstrip("./")
        if not p.startswith(PREFIX) or not member.isfile():
            continue
        rel=p[len(PREFIX):]
        if not rel or ".." in PurePosixPath(rel).parts:
            raise SystemExit("Unsafe IPK member: "+p)
        if rel.endswith((".pyc",".log",".m3u",".m3u8")) or "__pycache__" in rel or "iptv_names_" in rel:
            continue
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())

plugin=DEST/"plugin.py"
s=plugin.read_text(encoding="utf-8")
def patch_once(old,new):
    global s
    found=s.count(old)
    if found!=1:
        raise SystemExit("Patch mismatch: %s matches for %s"%(found,old[:90]))
    s=s.replace(old,new,1)

# Enigma2 ARGB uses INVERTED opacity: 0xFF = fully transparent.
# Previous 6.13.9 frame was set to opaque #000000 beneath its RGBA graphic.
# On receiver skins with no window alpha blending, that produced a BLACK BOX
# outside otherwise transparent rounded corners.
patch_once('flags="wfNoBorder" transparent="1" backgroundColor="#000000"',
           'flags="wfNoBorder" transparent="1" backgroundColor="#FF000000"')

# GameDetailScreen 6.13.9 already has:
#   OK first row: TV
#   OK second row: official lineups, yellow hotkey
# Now add: OK third row: table, and RED hotkey for standings.
old='"OK: AUFSTELLUNGEN (falls verfuegbar)"'
if s.count(old)!=2:
    raise SystemExit("Expected two GameDetail action lists, found "+str(s.count(old)))
s=s.replace(old,old+',"OK: LIGA-TABELLE"',2)
patch_once('''    def choose(self):
        if self['menu'].getSelectedIndex()==1:
            self.open_child(GoalAlertLineupScreen,self.game)
        else:
            self.open_child(LiveOnSatScreen,self.game)
    def yellow(self):
        self.open_child(GoalAlertLineupScreen,self.game)
    def green(self):''',
'''    def choose(self):
        choice=self['menu'].getSelectedIndex()
        if choice==1:
            self.open_child(GoalAlertLineupScreen,self.game)
        elif choice==2:
            self.open_child(GoalAlertLeagueTableScreen,self.game)
        else:
            self.open_child(LiveOnSatScreen,self.game)
    def yellow(self):
        self.open_child(GoalAlertLineupScreen,self.game)
    def red(self):
        self.open_child(GoalAlertLeagueTableScreen,self.game)
    def green(self):''')
patch_once('''"OK: Auswaehlen  GELB: Aufstellungen  GRUEN: Favorit  BLAU: Neu"''',
           '''"ROT: Tabelle  GELB: Aufstellungen  GRUEN: Favorit  BLAU: Neu"''')

anchor="class AllLiveScreen(BaseScreen):"
new_screen='''class GoalAlertLeagueTableScreen(BaseScreen):
    """Non-blocking league standings, only confirmed provider records."""
    def __init__(self,session,game):
        BaseScreen.__init__(self,session)
        self.game=dict(game)
        self.result=None
        self.timer=eTimer()
        self.timer.callback.append(self.show_table)
        self.onClose.append(self.timer.stop)
        title=str(game.get("league_name") or game.get("league") or "Liga")[:44]
        self.setup("LIGA-TABELLE | "+title,
                   ["Lade Ligatabelle ..."],
                   "ESPN-Tabellendaten | BLAU: Aktualisieren  EXIT: Zurueck")
        self.blue()
    def blue(self):
        self.result=None
        self["menu"].setList(["Lade aktuelle Ligatabelle ..."])
        self.timer.start(250,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def fetch(self):
        from .goalalert_standings import parse_standings, validate_league_code
        try:
            league=validate_league_code(self.game.get("league"))
            from urllib.parse import quote
            url=("https://site.api.espn.com/apis/v2/sports/soccer/%s/standings"%
                 quote(league,safe="."))
            request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GoalAlert/6.13.10"})
            with urllib.request.urlopen(request,timeout=12) as response:
                payload=json.load(response)
            self.result=parse_standings(payload)
        except Exception as exc:
            self.result=["Keine bestaetigte Ligatabelle abrufbar.",
                         "Grund: "+str(exc)[:110],
                         "BLAU: erneut abrufen"]
    def show_table(self):
        if self.result is None:return
        rows=self.result
        self.result=None
        self.timer.stop()
        self["menu"].setList(rows)


'''
patch_once(anchor,new_screen+anchor)
parser=(ROOT/"scripts/goalalert_standings_lib.py").read_text(encoding="utf-8")
(DEST/"goalalert_standings.py").write_text(parser,encoding="utf-8")

# Lower alpha while preserving original luminous artwork. The whole screen
# is transparent. Artwork remains a bounded RGBA graphic with real alpha=0
# outside rounded corners. No static black rectangle or invented TV blur.
from PIL import Image, ImageDraw
art_files=sorted(DEST.glob("ga_popup_*.png"))
if len(art_files)<8:
    raise SystemExit("HD popup artwork set missing")
for image_path in art_files:
    with Image.open(image_path) as raw:
        im=raw.convert("RGBA")
    w,h=im.size
    alpha=im.getchannel("A")
    # Soften large blue body; tiny translucent pixels keep the glass glow.
    soft=alpha.point(lambda value:int(value*0.72))
    im.putalpha(soft)
    # Exactly transparent outer corners even at HD resolutions.
    assert im.getpixel((0,0))[3]==0, str(image_path)
    assert im.getpixel((w-1,h-1))[3]==0, str(image_path)
    im.save(image_path,optimize=True)

if s.count('6.13.9')<1:
    raise SystemExit("Version identifier missing")
s=s.replace('6.13.9','6.13.10')
plugin.write_text(s,encoding="utf-8")
(ROOT/"source/VERSION").write_text("6.13.10\n",encoding="utf-8")

# Code tests run without an Enigma2 receiver.
compile(s,str(plugin),"exec")
compile(parser,"goalalert_standings.py","exec")
scope={}
exec(compile(parser,"goalalert_standings.py","exec"),scope)
fake={"children":[{"name":"Premier League","standings":{"entries":[
    {"team":{"id":"1","displayName":"Arsenal"},"stats":[
      {"name":"rank","displayValue":"1"},{"name":"gamesPlayed","displayValue":"8"},
      {"name":"pointDifferential","displayValue":"+15"},
      {"name":"points","displayValue":"22"}]}]}}]}
rows=scope["parse_standings"](fake)
assert any("Arsenal" in line and "22" in line and "+15" in line for line in rows)
assert "Keine bestaetigten" in " ".join(scope["parse_standings"]({}))
assert scope["validate_league_code"]("eng.1")=="eng.1"
for malformed in ("/etc/passwd","", "../eng.1"):
    try:scope["validate_league_code"](malformed)
    except ValueError:pass
    else:raise AssertionError("Unsafe league code accepted: "+malformed)
assert 'backgroundColor="#FF000000"' in s
assert 'self.open_child(GoalAlertLeagueTableScreen,self.game)' in s
assert 'goalalert_standings' in s
subprocess.run(["python3","scripts/build_ipk.py"],cwd=ROOT,check=True)
print("GoalAlert 6.13.10: compiled, transparency + table UI verified; release ready")
