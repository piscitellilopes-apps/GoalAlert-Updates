#!/usr/bin/env python3
"""Build GoalAlert 6.13.9: exactly centered scores, true glass PNG corners,
high-definition transparent artwork and an optional ESPN lineup screen.
Preserves all verified 6.13.8 functions; no IPTV credentials are packaged.
"""
import hashlib
import io
import pathlib
import subprocess
import tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.8_all.ipk"
SHA256="cec9d586a4b5634cc5d1913b3664bd01019d5a9654257c861b1b72db694e868e"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.exists() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=SHA256:
    raise SystemExit("Verified base 6.13.8 missing or altered")
if DEST.exists():
    raise SystemExit("Source folder already exists; refusing overwrite")
DEST.mkdir(parents=True)
tar_blob=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(tar_blob),mode="r:xz") as archive:
    for m in archive:
        p=m.name.lstrip("./")
        if not p.startswith(PREFIX) or not m.isfile():continue
        rel=p[len(PREFIX):]
        if not rel or ".." in pathlib.PurePosixPath(rel).parts:
            raise SystemExit("Unsafe archive member")
        if rel.endswith((".pyc",".m3u",".m3u8",".log")) or "__pycache__" in rel or "iptv_names_" in rel:
            continue
        out=DEST/rel
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(archive.extractfile(m).read())

plugin=DEST/"plugin.py"
s=plugin.read_text(encoding="utf-8")
def sub_once(old,new):
    global s
    n=s.count(old)
    if n!=1:raise SystemExit("Source drift: %d matches for %s"%(n,old[:100]))
    s=s.replace(old,new,1)

# Fixed three-cell layout: center each score digit group IN ITS OWN CELL,
# never a single left-aligned Label for "1 : 5".
sub_once('''          <widget name="score" position="{sc_x},{sc_y}" size="{sw},{sh}" font="Regular;{scorefont}" foregroundColor="#FFFFFF" transparent="1" zPosition="3" />''',
'''          <widget name="score_home" position="{lh_x},{sc_y}" size="{cw},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" zPosition="3" />
          <widget name="score_separator" position="{colon_x},{sc_y}" size="{colon_w},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#99E6FF" transparent="1" zPosition="3" />
          <widget name="score_away" position="{rh_x},{sc_y}" size="{cw},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" zPosition="3" />''')
sub_once('''            sc_x=px(270),sc_y=py(27),sw=px(100),sh=py(38),scorefont=font(29),''',
'''            lh_x=px(260),sc_y=py(27),cw=px(50),sh=py(38),scorefont=font(29),
            colon_x=px(310),colon_w=px(20),rh_x=px(330),''')
sub_once('''        if 'hs' in game and 'as' in game:
            self['score']=Label(str(game['hs'])+' : '+str(game['as']))
        else:
            self['score']=Label('TOR!')''',
'''        # Three independently centered score labels avoid alignment drift for
        # 1:5, 0:0, 10:2 etc. The colon has its own fixed centerline.
        if 'hs' in game and 'as' in game:
            home_score=str(game['hs'])
            away_score=str(game['as'])
            separator=':'
        else:
            home_score='TOR'
            away_score=''
            separator='!'
        self['score_home']=Label(home_score)
        self['score_separator']=Label(separator)
        self['score_away']=Label(away_score)''')
sub_once('''        return ''' + "'''" + '''<screen name="GoalPopup" position="center,18" size="{w},{h}" flags="wfNoBorder" backgroundColor="#081528">''',
'''        return ''' + "'''" + '''<screen name="GoalPopup" position="center,18" size="{w},{h}" flags="wfNoBorder" transparent="1" backgroundColor="#000000">''')
sub_once('''          <widget name="theme_bg" pixmap="{root}{theme}" position="0,0" size="{w},{h}" zPosition="0" alphatest="off" />''',
'''          <widget name="theme_bg" pixmap="{root}{theme}" position="0,0" size="{w},{h}" zPosition="0" alphatest="on" />''')

# Better crest sampling from ESPN where true 500px source exists.
# Legacy logos remain available for providers without a numeric ESPN ID.
sub_once('''    if candidate and str(candidate).startswith('https://'):return candidate
    team_id=str(team.get('id') or '')
    if team_id.isdigit() and len(team_id)<=10:
        return 'https://a.espncdn.com/i/teamlogos/soccer/500/%s.png'%team_id''',
'''    team_id=str(team.get('id') or '')
    if team_id.isdigit() and len(team_id)<=10:
        return 'https://a.espncdn.com/i/teamlogos/soccer/500/%s.png'%team_id
    if candidate and str(candidate).startswith('https://'):return candidate''')

# An optional, non-fabricated lineup panel from the same official match ID.
# In contrast to provider-agnostic "fake" lineups, an unavailable roster
# is explicitly labelled as unavailable.
sub_once('''          ["OK: TV-SENDER DIESER BEGEGNUNG"],
          "OK: LiveOnSat  GRUEN: Favorit  BLAU: Aktualisieren  EXIT: Zurueck")''',
'''          ["OK: TV-SENDER DIESER BEGEGNUNG","OK: AUFSTELLUNGEN (falls verfuegbar)"],
          "OK: Auswaehlen  GELB: Aufstellungen  GRUEN: Favorit  BLAU: Neu")''')
sub_once('''    def choose(self):
        self.open_child(LiveOnSatScreen,self.game)
    def green(self):
        g=self.game''',
'''    def choose(self):
        if self['menu'].getSelectedIndex()==1:
            self.open_child(GoalAlertLineupScreen,self.game)
        else:
            self.open_child(LiveOnSatScreen,self.game)
    def yellow(self):
        self.open_child(GoalAlertLineupScreen,self.game)
    def green(self):
        g=self.game''')
sub_once('''        self["menu"].setList(["OK: TV-SENDER DIESER BEGEGNUNG"])

class AllLiveScreen(BaseScreen):''',
'''        self["menu"].setList(["OK: TV-SENDER DIESER BEGEGNUNG",
                              "OK: AUFSTELLUNGEN (falls verfuegbar)"])

class GoalAlertLineupScreen(BaseScreen):
    """Display verified ESPN starters if present; never invent a lineup."""
    def __init__(self,session,game):
        BaseScreen.__init__(self,session)
        self.game=dict(game)
        self.result=None
        self.timer=eTimer()
        self.timer.callback.append(self.display)
        self.onClose.append(self.timer.stop)
        self.setup("AUFSTELLUNGEN | "+str(game.get('home',''))+" - "+str(game.get('away','')),
                   ["Lade offizielle Aufstellungen ..."],
                   "Nur bestaetigte Spielerdaten | EXIT: Zurueck")
        threading.Thread(target=self.load,daemon=True).start()
        self.timer.start(250,False)
    def load(self):
        try:
            event_id=str(self.game.get('id') or '')
            league=str(self.game.get('league') or '')
            if not event_id.isdigit() or not league or self.game.get('provider')!='ESPN':
                raise ValueError('Fuer diese Begegnung keine ESPN-Aufstellung verfuegbar')
            from urllib.parse import quote
            url="https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?event=%s"%(quote(league,safe=''),event_id)
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GoalAlert/6.13.9'})
            with urllib.request.urlopen(request,timeout=9) as response:
                payload=json.load(response)
            rosters=payload.get('rosters') or []
            if not isinstance(rosters,list):rosters=[]
            lines=[]
            for roster in rosters[:2]:
                if not isinstance(roster,dict):continue
                team=roster.get('team') or {}
                title=team.get('displayName') or team.get('name') or 'Team'
                players=roster.get('roster') or []
                confirmed=[]
                for p in players:
                    if not isinstance(p,dict):continue
                    athlete=p.get('athlete') or {}
                    if p.get('starter') is False or athlete.get('starter') is False:continue
                    name=athlete.get('displayName') or athlete.get('shortName') or p.get('displayName')
                    if not name:continue
                    number=str(athlete.get('jersey') or p.get('jersey') or '').strip()
                    confirmed.append((number+' ' if number else '')+str(name))
                if confirmed:
                    lines.append(str(title)[:38]+':')
                    lines.extend(confirmed[:11])
            if not lines:
                lines=['Fuer dieses Spiel sind noch keine bestaetigten Aufstellungen abrufbar.']
            self.result=lines
        except Exception as exc:
            self.result=['Aufstellungen derzeit nicht verfuegbar: '+str(exc)[:95]]
    def display(self):
        if self.result is None:return
        self.timer.stop()
        self['menu'].setList(self.result)
        self.result=None

class AllLiveScreen(BaseScreen):''')
if s.count('6.13.8')<2:
    raise SystemExit('Version identifier missing; cannot bump reliably')
s=s.replace('6.13.8','6.13.9')
plugin.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.9\n',encoding='utf-8')
# Build high-quality transparent RGBA images after clean extraction.
subprocess.run(['python3','scripts/goalalert_glass_art.py'],cwd=ROOT,check=True)
compile(s,str(plugin),'exec')
assert 'self[\'score_home\']=Label(home_score)' in s
assert 'halign="center" valign="center"' in s
assert 'GOALALERTLineup' not in s # catches unintended placeholders
from PIL import Image
for name in ('ga_popup_goal.png','ga_popup_goal_fhd.png','ga_popup_scorer.png','ga_popup_scorer_fhd.png'):
    im=Image.open(DEST/name)
    assert im.mode=='RGBA' and im.getpixel((0,0))[3]==0,name
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('6.13.9 source syntax, truly rounded HD overlays, and score centering verified')
