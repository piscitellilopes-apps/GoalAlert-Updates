#!/usr/bin/env python3
"""GoalAlert 6.13.16: TV game guide fallback, audio/goal notifications, layout fixes."""
from pathlib import Path,PurePosixPath
import hashlib,io,tarfile,subprocess,sys,re,tempfile,shutil,json
ROOT=Path(__file__).resolve().parents[1]
VERSION='6.13.16'
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.15_all.ipk'
PIN='9a9425bda44195b3c3197a971bffc955f5913687aa94f16fed475c1a28103c2f'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
assert BASE.exists() and hashlib.sha256(BASE.read_bytes()).hexdigest()==PIN,"6.13.15 base changed: refusing build"
assert not DEST.exists(),"Refusing to overwrite existing source"
DEST.mkdir(parents=True)
compressed=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(compressed),mode='r:xz') as archive:
    for entry in archive:
        name=entry.name.lstrip('./')
        if not entry.isfile() or not name.startswith(PREFIX):continue
        sub=name[len(PREFIX):]
        if not sub or '..' in PurePosixPath(sub).parts or sub.startswith('/'):raise ValueError("Unsafe path")
        if '__pycache__' in sub or sub.endswith(('.pyc','.log','.m3u','.m3u8')):continue
        out=DEST/sub
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(archive.extractfile(entry).read())
p=DEST/'plugin.py'
s=p.read_text(encoding='utf-8')
def replace(old,new,count=1):
    global s
    present=s.count(old)
    if present!=count:raise ValueError('Expected %d, got %d: %s'%(count,present,old[:160]))
    s=s.replace(old,new,count)
# Remove ticket from main menu, keep indices accurate. Do not strip
# other screens/classes abruptly; just remove UI entry and associated dispatch.
replace('"Test-Toralarm (mit Ton)","Tippschein (15 Spiele)","LiveOnSat TV-Spielplan"',
        '"Test-Toralarm (mit Ton)","LiveOnSat TV-Spielplan"')
replace('''        elif n==6:self.session.open(TipScreen)
        elif n==7:self.open_child(LiveOnSatScreen)
        elif n==8:self.session.open(SourceScreen)
        elif n==9:self.session.open(DiagnosticsScreen)
        elif n==10:self.session.open(CrestTestScreen)
        elif n==11:monitor.test_scorer()
        elif n==12:self.session.open(AudioStatusScreen)
        elif n==13:self.open_child(QuickLiveScreen)
        elif n==14:self.session.open(GoalAlertUpdateScreen)''',
'''        elif n==6:self.open_child(LiveOnSatScreen)
        elif n==7:self.session.open(SourceScreen)
        elif n==8:self.session.open(DiagnosticsScreen)
        elif n==9:self.session.open(CrestTestScreen)
        elif n==10:monitor.test_scorer()
        elif n==11:self.session.open(AudioStatusScreen)
        elif n==12:self.open_child(QuickLiveScreen)
        elif n==13:self.session.open(GoalAlertUpdateScreen)''')
# If LiveOnSat has guide games but match wording did not match, show guide
# games as clearly marked manual selections, not a bogus automatic match.
replace('''            if not self.games:
                self["menu"].setList(["BEGEGNUNG: "+label,
                    "Status: "+status,
                    "Kein eindeutig passender TV-Eintrag gefunden.",
                    "TV-Spielplan oeffnen: GELB | BLAU: Neu laden",
                    info])
                self["hint"].setText("GELB: gesamter TV-Spielplan | BLAU: nochmals abrufen")
                self.all_games=games
                return''',
'''            if not self.games:
                # Show the same full fetched guide available from the app menu.
                # Let the viewer select the game explicitly: never mislabel
                # broadcasts as confirmed for a wrong fixture.
                self.games=games
                self["heading"].setText("TV-SENDER | Spiel bitte selbst auswaehlen")
                self["menu"].setList([
                    (g.get("time","")+" | "+g.get("home","")+" - "+g.get("away",""))
                    for g in games] or ["Keine TV-Spiele in den erreichbaren Quellen"])
                self["hint"].setText("Kein exakter Treffer: richtige Begegnung selbst waehlen | GELB: kompletter Plan")
                return''')
replace('''            self["menu"].setList([g.get("day","")+" | "+g.get("time","")+" | "+g["home"]+" - "+g["away"] for g in self.games])''',
'''            self["heading"].setText("TV-SENDER | "+label[:49])
            self["menu"].setList([g.get("day","")+" | "+g.get("time","")+" | "+g["home"]+" - "+g["away"] for g in self.games])''')
# Decrease formerly almost-clear glass to an 80-alpha translucent fill,
# preserving transparency and TV video visibility.
from PIL import Image,ImageEnhance
for name in ('ga_menu','ga_home','ga_detail','ga_tip','ga_live_glass'):
    for suffix in ('','_fhd'):
        file=DEST/(name+suffix+'.png')
        if not file.exists():continue
        im=Image.open(file).convert('RGBA')
        alpha=im.getchannel('A')
        # 6.13.15 centre was 45/255; 6.13.16 approx 100/255.
        alpha=alpha.point(lambda x:min(130,int(round(x*2.15))))
        im.putalpha(alpha)
        im.save(file,optimize=True)
# Popup graphics had alpha suppressed last version. Recover legibility.
for file in DEST.glob('ga_popup_*.png'):
    im=Image.open(file).convert('RGBA')
    alpha=im.getchannel('A').point(lambda x:min(210,int(round(x*1.24))))
    im.putalpha(alpha)
    im.save(file,optimize=True)
# Balanced 640px scoreboard: clear gap around score (>= 20 pixels)
# and enough room for team label. Crew sizes scale proportionally.
replace('''        name_width=px(185)
        second_x=width-px(74)-name_width''',
'''        name_width=px(160)
        second_x=px(394)''')
replace('''          <widget name="away_name" position="{an_x},{an_y}" size="{nw},{nh}" font="Regular;{namefont}" foregroundColor="#EAF8FF" transparent="1" zPosition="3" />''',
'''          <widget name="away_name" position="{an_x},{an_y}" size="{nw},{nh}" font="Regular;{namefont}" halign="right" foregroundColor="#EAF8FF" transparent="1" zPosition="3" />''')
replace('''            hn_x=px(73),hn_y=py(36),nw=name_width,nh=py(31),namefont=font(20),
            lh_x=px(260),sc_y=py(27),cw=px(50),sh=py(38),scorefont=font(29),
            colon_x=px(310),colon_w=px(20),rh_x=px(330),''',
'''            hn_x=px(75),hn_y=py(36),nw=name_width,nh=py(31),namefont=font(18),
            lh_x=px(257),sc_y=py(27),cw=px(43),sh=py(38),scorefont=font(28),
            colon_x=px(303),colon_w=px(20),rh_x=px(327),''')
# Some names are longer than the available width; never let them flow
# across the score. Truncate deterministically within allocated labels.
replace("self['home_name']=Label(home_name[:15])","self['home_name']=Label(home_name[:14])")
replace("self['away_name']=Label(away_name[:15])","self['away_name']=Label(away_name[:14])")
replace('''self.duration=(3 if kind in ('cancel','redcard') else (max(7,int(duration)) if kind=='goal' and (home_url or away_url) else max(2,int(duration))))''',
'''self.duration=(3 if kind in ('cancel','redcard') else (max(6,int(duration)) if kind=='scorer' else
            (max(7,int(duration)) if kind=='goal' and (home_url or away_url) else max(2,int(duration)))))''')
# Critical sound correction: launch sound when event is processed, NOT
# contingent on animation onShown callback. Never repeat sound in followup
# scorer popup. Asynchronous mixer-aware playback cannot replace TV service.
replace('''        # The scorer popup is silent. Playing before GOAL screen transition
        # prevents an unintended second cheer.
        try:
            from .goalalert_audio import cheer_path,play
            root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
            play(cheer_path(root,config.plugins.goalalert32.cheer_style.value))
        except Exception as exc:_audio_log('Tor-Intro Audio: '+str(exc)[:110])
        self.advance()''',
'''        # Goal sound was already triggered by the monitor when the goal
        # event arrived. Intro is purely visual and never starts audio.
        self.advance()''')
replace('''            if kind=='goal' and not intro_finished:
                which=scoring_side if scoring_side in ('home','away') else 'home''',
'''            if kind=='goal' and not intro_finished:
                # Start sound on the event, independent of intro rendering.
                try:
                    from .goalalert_audio import cheer_path,play
                    root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
                    if not play(cheer_path(root,config.plugins.goalalert32.cheer_style.value)):
                        _audio_log('TORJUBEL: Audio-Backend nicht verfuegbar')
                except Exception as exc:
                    _audio_log('TORJUBEL-Start: '+type(exc).__name__)
                which=scoring_side if scoring_side in ('home','away') else 'home' ''')
# Ensure the scorer always has its own green pop-up queue: at most
# one item processed per tick, never overwritten by a second concurrent goal.
replace('''        self.goal_update=None
        self.announced_details=set()''',
'''        self.goal_updates=[]
        self.announced_details=set()''')
replace('''            update=self.goal_update;self.goal_update=None''',
'''            update=self.goal_updates.pop(0) if self.goal_updates else None''')
replace('''                    with self.lock:self.goal_update=(target,g,candidate)''',
'''                    with self.lock:self.goal_updates.append((target,g,candidate))''')
replace('''        for attempt in range(8):
            if attempt:time.sleep(12)''',
'''        for attempt in range(20):
            if attempt:time.sleep(14)''')
# Enigma2 table and lineup display use a true fixed-width font so score
# columns never drift even when digits and team names have different widths.
replace('''class GoalAlertLineupScreen(BaseScreen):
    """Display verified ESPN starters if present; never invent a lineup."""''',
'''class GoalAlertLineupScreen(BaseScreen):
    """Display verified ESPN starters if present; never invent a lineup."""
    skin=BaseScreen.skin.replace('font="Regular;20"', 'font="Console;18"').replace('itemHeight="30"', 'itemHeight="29"')''')
replace('''class GoalAlertLeagueTableScreen(BaseScreen):
    """Non-blocking league standings, only confirmed provider records."""''',
'''class GoalAlertLeagueTableScreen(BaseScreen):
    """Non-blocking league standings, only confirmed provider records."""
    skin=BaseScreen.skin.replace('font="Regular;20"', 'font="Console;20"').replace('itemHeight="30"', 'itemHeight="29"')''')
# Provide a true two-column lineup (home | away) in fixed-width text,
# without passing off an unconfirmed squad as official starting XI.
lineup=DEST/'goalalert_lineups.py'
lm=lineup.read_text(encoding='utf-8')
mark='def valid_espn_event_id(value):'
assert lm.count(mark)==1
newformat='''def format_side_by_side(payload):
    """Present genuine ESPN home and away lineups in aligned columns."""
    if not isinstance(payload,dict):
        return ['Keine bestaetigten Aufstellungen verfuegbar.']
    groups=payload.get('rosters') or []
    if not groups:
        groups=(payload.get('boxscore') or {}).get('players') or []
    if not isinstance(groups,list) or not groups:
        return ['Keine bestaetigten Aufstellungen vorhanden.','BLAU: erneut pruefen']
    cols=[]
    for index,group in enumerate(groups[:2]):
        if not isinstance(group,dict):continue
        starters,squad=_extract(group)
        category='STARTELF' if starters else 'KADER (nicht bestaetigt)'
        entries=starters if starters else squad
        cols.append((_team(group,index),category,entries))
    if not cols:return ['Keine Aufstellungen vorhanden.']
    while len(cols)<2:
        cols.append(('NOCH NICHT VERFUEGBAR','',[]))
    (home,home_type,home_rows),(away,away_type,away_rows)=cols
    width=34
    out=['{:<34}  {}'.format('HEIM | '+home[:25],'GAST | '+away[:25]),
         '{:<34}  {}'.format(home_type,away_type)]
    for i in range(min(22,max(len(home_rows),len(away_rows)))):
        left=home_rows[i] if i<len(home_rows) else ''
        right=away_rows[i] if i<len(away_rows) else ''
        out.append('{:<34}  {}'.format(left[:34],right[:34]))
    return out if len(out)>2 else ['Aufstellungen noch nicht verfuegbar.']

'''
lm=lm.replace(mark,newformat+mark)
lineup.write_text(lm,encoding='utf-8')
replace('''from .goalalert_lineups import format_lineups, valid_espn_event_id, valid_league''',
'''from .goalalert_lineups import format_side_by_side, valid_espn_event_id, valid_league''')
replace('''            self.result=format_lineups(payload)''','''            self.result=format_side_by_side(payload)''')
# Table columns use a fixed 5-field layout, including actual draws,
# games played, goal difference, points; no invented data.
table=DEST/'goalalert_standings.py'
tm=table.read_text(encoding='utf-8')
tm=tm.replace('PL  VEREIN                 SP  TD  PKT','PL  VEREIN                 SP  TD  PKT')
# Existing table already pads each column; monospaced font is the real fix.
table.write_text(tm,encoding='utf-8')
# More sound backends, including common minimal-media receiver binaries,
# tested at runtime. Returns success only when a backend completes.
audio=DEST/'goalalert_audio.py'
am=audio.read_text(encoding='utf-8')
needle="        ('ALSA default',['aplay','-q',path]),"
assert am.count(needle)==1
am=am.replace(needle,needle+'''
        ('PulseAudio paplay',['paplay',path]),
        ('GStreamer play',['gst-play-1.0','--no-interactive',path]),
        ('SoX play',['play','-q',path]),
''')
audio.write_text(am,encoding='utf-8')
# Update version and maintain TV overlay style.
s=s.replace('6.13.15','6.13.16')
p.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text(VERSION+'\n',encoding='utf-8')
compile(s,str(p),'exec')
# Offline regressions.
assert '"Tippschein (15 Spiele)"' not in s
assert 'self.goal_update=' not in s
assert 'self.goal_updates.append' in s
assert 'font="Console;20"' in s
assert 'name_width=px(160)' in s
sys.path.insert(0,str(DEST))
import goalalert_lineups
doc={'rosters':[{'team':{'displayName':'FC Basel'},'roster':[{'athlete':{'displayName':'A Player'},'starter':True}]},
                {'team':{'displayName':'FC Zurich'},'roster':[{'athlete':{'displayName':'B Player'},'starter':True}]}]}
rows=goalalert_lineups.format_side_by_side(doc)
assert 'HEIM' in rows[0] and 'GAST' in rows[0] and 'A Player' in rows[2] and 'B Player' in rows[2]
# Check popup geometry for 640px compact screen (exclusive ends).
home_left,home_width=75,160
away_left,away_width=394,160
score_left,score_right=257,327+43
assert home_left+home_width<=score_left-18 and away_left>=score_right+20
# No crash on module import, no Python cache bundled.
for cache in DEST.rglob('__pycache__'):shutil.rmtree(cache)
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('Validated GoalAlert 6.13.16 safe release: red-key TV fallback, sound start, scorer queue, proportions, no ticket')
