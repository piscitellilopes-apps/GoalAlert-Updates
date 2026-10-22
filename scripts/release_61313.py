#!/usr/bin/env python3
"""GoalAlert 6.13.13: verified updater contract, animated GOAL intro, real lineups.

Build exclusively from published 6.13.12 IPK, pinned to SHA-256.
The CI test suite exercises the installed helper with a FAKE opkg and
FAKE init commands, so no receiver or runner OS is modified.
"""
from pathlib import Path, PurePosixPath
import hashlib, io, subprocess, tarfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.12_all.ipk'
EXPECTED_SHA='7c1eb6d23885a9f011fcfc0628c8fe804a710dbe6c68c3cd652ed8fc5ceb4476'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
VERSION='6.13.13'
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED_SHA:
    raise SystemExit('Refusing unverified base IPK')
if DEST.exists():raise SystemExit('Refusing to overwrite unexpected source')
DEST.mkdir(parents=True)
data=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as tar:
    for member in tar:
        path=member.name.lstrip('./')
        if not path.startswith(PREFIX) or not member.isfile():continue
        rel=path[len(PREFIX):]
        if not rel or '..' in PurePosixPath(rel).parts:raise RuntimeError('Unsafe archive entry')
        if rel.endswith(('.pyc','.m3u','.m3u8','.log')) or '__pycache__' in rel or 'iptv_names_' in rel:
            continue
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tar.extractfile(member).read())

path=DEST/'plugin.py'
s=path.read_text(encoding='utf-8')
def patch(before,after,count=1):
    global s
    n=s.count(before)
    if n!=count:raise SystemExit('Source changed: expected %d got %d for %s'%(count,n,before[:100]))
    s=s.replace(before,after,count)

# Fixed source is private to GoalAlert. Nothing from private bouquets is added.
(DEST/'goalalert_lineups.py').write_text(
    (ROOT/'scripts/goalalert_lineups_lib.py').read_text(encoding='utf-8'),encoding='utf-8')

# Existing lineups incorrectly REQUIRED the 'provider' key to be literally
# ESPN. Events obtained from the regular ESPN scoreboard often lack this
# redundant property. Instead require an authentic numeric ESPN event ID and
# a safely formatted league code, and label incomplete rosters correctly.
start=s.index('    def load(self):',s.index('class GoalAlertLineupScreen(BaseScreen):'))
end=s.index('    def display(self):',start)
s=s[:start]+'''    def load(self):
        try:
            from .goalalert_lineups import format_lineups, valid_espn_event_id, valid_league
            event_id=valid_espn_event_id(self.game.get('id'))
            league=valid_league(self.game.get('league'))
            if not event_id or not league:
                raise ValueError('Keine ESPN-Spiel-ID oder gueltige Liga vorhanden')
            from urllib.parse import quote
            url=("https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?event=%s"%
                 (quote(league,safe='.'),event_id))
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GoalAlert/6.13.13'})
            with urllib.request.urlopen(request,timeout=12) as response:
                payload=json.load(response)
            self.result=format_lineups(payload)
        except Exception as exc:
            self.result=['Aufstellungen derzeit nicht verfuegbar:',
                         str(exc)[:105], 'BLAU: erneut laden']
''' + s[end:]
# Let user retry a legitimate missing lineups request without leaving screen.
anchor='''    def display(self):
        if self.result is None:return
        self.timer.stop()
        self['menu'].setList(self.result)
        self.result=None

class GoalAlertLeagueTableScreen(BaseScreen):'''
replacement='''    def display(self):
        if self.result is None:return
        self.timer.stop()
        self['menu'].setList(self.result)
        self.result=None
    def blue(self):
        self.result=None
        self['menu'].setList(['Lade aktuelle Aufstellungen ...'])
        self.timer.start(250,False)
        threading.Thread(target=self.load,daemon=True).start()

class GoalAlertLeagueTableScreen(BaseScreen):'''
patch(anchor,replacement)
patch('''                   "Nur bestaetigte Spielerdaten | EXIT: Zurueck")
        threading.Thread(target=self.load,daemon=True).start()''',
'''                   "Spielerdaten von ESPN | BLAU: Neu laden | EXIT: Zurueck")
        threading.Thread(target=self.load,daemon=True).start()''')

# Goal animation is a separate brief session dialog. Its closing callback
# opens the existing results popup immediately; goal sound plays only ONCE
# on the animation and never on the green silent scorer popup.
anchor='class GoalPopup(Screen):'
intro='''class GoalIntroScreen(Screen):
    """Short top-centre GOAL roll-in; no interruption of the DVB TV service."""
    def __init__(self,session,scoring_team='',crest_path=None):
        markup=('<screen name="GoalIntro" position="center,18" size="640,104" '
                'flags="wfNoBorder" transparent="1" backgroundColor="transparent">'
                '<widget name="intro_frame" position="0,0" size="640,104" '
                'transparent="1" alphatest="blend" zPosition="0" />'
                '<widget name="intro_crest" position="554,21" size="62,62" '
                'transparent="1" alphatest="blend" zPosition="2" />'
                '<widget name="intro_team" position="421,77" size="192,22" '
                'font="Regular;14" foregroundColor="#DBFAFF" transparent="1" '
                'halign="center" zPosition="3" />'
                '</screen>')
        self.skin=_goalalert_hd_skin(markup)
        Screen.__init__(self,session)
        self['intro_frame']=Pixmap()
        self['intro_crest']=Pixmap()
        self['intro_team']=Label(str(scoring_team or 'TOR!')[:23])
        self.crest_path=crest_path
        self.index=0
        self.anim=eTimer()
        self.anim.callback.append(self.advance)
        self.onShown.append(self.begin)
        self.onClose.append(self.anim.stop)
        self.started=False
        self.crest_decoder=None
    def begin(self):
        if self.started:return
        self.started=True
        if self.crest_path and os.path.isfile(self.crest_path):
            try:
                sz=int(round(62*_goalalert_ui_scale()))
                self.crest_decoder=ePicLoad()
                def crest_ready(info=None):
                    try:
                        pix=self.crest_decoder.getData()
                        if pix is not None and self['intro_crest'].instance is not None:
                            self['intro_crest'].instance.setPixmap(pix)
                            self['intro_crest'].instance.show()
                    except Exception as exc:
                        _crest_log('Tor-Intro Wappen: '+str(exc)[:90])
                self.crest_decoder.PictureData.get().append(crest_ready)
                self.crest_decoder.setPara((sz,sz,1,1,False,1,'#00000000'))
                self.crest_decoder.startDecode(self.crest_path)
            except Exception as exc:_crest_log('Tor-Intro Dekoder: '+str(exc)[:90])
        # The scorer popup is silent. Playing before GOAL screen transition
        # prevents an unintended second cheer.
        try:
            from .goalalert_audio import cheer_path,play
            root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
            play(cheer_path(root,config.plugins.goalalert32.cheer_style.value))
        except Exception as exc:_audio_log('Tor-Intro Audio: '+str(exc)[:110])
        self.advance()
        self.anim.start(80,False)
    def advance(self):
        if self.index>=12:
            self.anim.stop()
            self.close()
            return
        try:
            from Tools.LoadPixmap import LoadPixmap
            scale='_fhd' if _goalalert_ui_scale()>1.2 else ''
            root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
            name='ga_goal_intro_%02d%s.png'%(self.index,scale)
            pix=LoadPixmap(path=root+name,cached=True)
            if pix is not None and self['intro_frame'].instance is not None:
                self['intro_frame'].instance.setPixmap(pix)
        except Exception as exc:
            _crest_log('Tor-Intro Bild: '+str(exc)[:95])
        self.index+=1


'''
patch(anchor,intro+anchor)

# Callback token guards preserve correct match identity if a second goal
# arrives while the first GOAL intro is still playing.
start=s.index('    def show_goal(self,message,logo_path=None,away_logo_path=None,kind=',s.index('class Monitor:'))
end=s.index('    def hide_goal(self):',start)
s=s[:start]+'''    def _after_goal_intro(self,token,details):
        if getattr(self,'popup_token',None)!=token:return
        self.popup=None
        message,logo_path,away_logo_path,home_url,away_url,game,scoring_side=details
        self.show_goal(message,logo_path,away_logo_path,kind='goal',
                       home_url=home_url,away_url=away_url,game=game,
                       scoring_side=scoring_side,intro_finished=True)
    def show_goal(self,message,logo_path=None,away_logo_path=None,kind='goal',
                  home_url=None,away_url=None,game=None,scoring_side=None,
                  intro_finished=False):
        """A brief animated intro precedes goal scoreboard; scorer is silent."""
        try:
            self.hide_goal()
            self.popup_token=getattr(self,'popup_token',0)+1
            token=self.popup_token
            g=game if isinstance(game,dict) else {}
            if kind=='goal' and not intro_finished:
                which=scoring_side if scoring_side in ('home','away') else 'home'
                badge=(logo_path or _cached_logo_local(home_url)) if which=='home' else (
                       away_logo_path or _cached_logo_local(away_url))
                team=g.get(which) or 'TOR!'
                args=(message,logo_path,away_logo_path,home_url,away_url,game,scoring_side)
                self.popup=self.session.openWithCallback(
                    lambda *r:self._after_goal_intro(token,args),GoalIntroScreen,team,badge)
                return
            self.popup=self.session.openWithCallback(
                lambda *r:self._popup_closed(token),GoalPopup,message,
                config.plugins.goalalert32.duration.value,logo_path,
                False if intro_finished else (kind=='goal'),
                away_logo_path,kind,home_url,away_url,game)
        except Exception as exc:
            self.popup=None
            _crest_log('Tor-Popup: '+str(exc)[:110])
''' +s[end:]

# Ensure the GOAL intro shows the badge of the team which actually scored.
patch("kind='goal',home_url=g.get('home_logo'),away_url=g.get('away_logo'),game=g)",
      "kind='goal',home_url=g.get('home_logo'),away_url=g.get('away_logo'),game=g,scoring_side=side)")

# Audio diagnosis: indicate that simultaneous audio needs PCM mixing.
patch("'WICHTIG: TV-Ton muss weiterhin laufen.'",
      "'TV-Ton an: PCM-Mischung benoetigt. Bei Stille AC3-Downmix pruefen.'")

# Keep the proven stable GitHub update channel and current-version comparisons.
if 'DEFAULT_SOURCE' not in (DEST/'goalalert_updater.py').read_text(encoding='utf-8'):
    raise SystemExit('Online update source not bundled')
if 'staged_package_ok(ipk)' not in (DEST/'goalalert_apply_update.py').read_text(encoding='utf-8'):
    raise SystemExit('6.13.12 symlink-safe installer is missing')
if s.count('6.13.12')<2:raise SystemExit('Expected pinned version references missing')
s=s.replace('6.13.12','6.13.13')
path.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.13\n',encoding='utf-8')
subprocess.run(['python3','scripts/goalalert_intro_art.py'],cwd=ROOT,check=True)
compile(s,str(path),'exec')
compile((DEST/'goalalert_lineups.py').read_text(encoding='utf-8'),'lineups','exec')

# Pure deterministic parser and UI assertions.
import runpy
lineups=runpy.run_path(str(DEST/'goalalert_lineups.py'))
mock={'rosters':[{'team':{'displayName':'Arsenal'},
                  'roster':[{'athlete':{'displayName':'Player A','jersey':'7'},
                             'starter':True},
                            {'athlete':{'displayName':'Player B'},'starter':False}]},
                 {'team':{'displayName':'Leeds'},
                  'roster':[{'athlete':{'displayName':'Player C'},'starter':False}]}]}
rows=lineups['format_lineups'](mock)
assert any('STARTELF | Arsenal' in row for row in rows)
assert any('Player A' in row for row in rows)
assert not any('Player B' in row for row in rows if 'STARTELF' in row)
assert any('KADER (Startelf nicht bestaetigt)' in row for row in rows)
assert lineups['valid_espn_event_id']('4012345')=='4012345'
assert lineups['valid_espn_event_id']('random') is None
assert "self.game.get('provider')!='ESPN'" not in s
assert 'GOALALERT' in s and "class GoalIntroScreen(Screen)" in s
assert "self._after_goal_intro(token,args)" in s
assert "intro_finished=True" in s
assert "scoring_side=side" in s
assert 'staged_package_ok' in (DEST/'goalalert_apply_update.py').read_text(encoding='utf-8')
assert len(list(DEST.glob('ga_goal_intro_??.png')))==12
assert len(list(DEST.glob('ga_goal_intro_??_fhd.png')))==12
from PIL import Image
with Image.open(DEST/'ga_goal_intro_00.png') as im:
    assert im.mode=='RGBA' and im.size==(640,104) and im.getpixel((0,0))[3]==0
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('GoalAlert 6.13.13: goal intro, validated lineup and canonical updater source passed')
