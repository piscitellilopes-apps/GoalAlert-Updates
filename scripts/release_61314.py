#!/usr/bin/env python3
"""GoalAlert 6.13.14: worldwide catalogue, true glass TV UI, compact GOAL,
confirmed score rollbacks and deduplicated red-card notifications.

Build from SHA256-pinned published 6.13.13 package, never from a user's
receiver files. All callbacks altering Enigma2 GUI run on its main timer.
"""
from pathlib import Path, PurePosixPath
import hashlib, io, subprocess, tarfile, re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.13_all.ipk'
EXPECTED='fc1880bd2f332599a688d0e62bd7289b08a1d9b8657bcd84c2caa08ab8f574f8'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
DEST=ROOT/'source/GoalAlert'
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=EXPECTED:
    raise SystemExit('6.13.13 source must match pinned published SHA-256')
if DEST.exists():raise SystemExit('Refuse to overwrite an existing source tree')
DEST.mkdir(parents=True)
blob=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(blob),mode='r:xz') as archive:
    for member in archive:
        name=member.name.lstrip('./')
        if not member.isfile() or not name.startswith(PREFIX):continue
        rel=name[len(PREFIX):]
        if not rel or '..' in PurePosixPath(rel).parts:raise SystemExit('Unsafe IPK member')
        if (rel.endswith(('.m3u','.m3u8','.pyc','.log')) or
            'iptv_names_' in rel or '__pycache__' in rel):continue
        dst=DEST/rel
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(archive.extractfile(member).read())

path=DEST/'plugin.py'
s=path.read_text(encoding='utf-8')
def patch(before,after,count=1):
    global s
    found=s.count(before)
    if found!=count:raise SystemExit('Changed base, patch failed: %s (%s != %s)'%(before[:80],found,count))
    s=s.replace(before,after,count)

# The quick list said "all games", but was silently filtered by the starred
# league selection. Use every league from the current catalog, not only stars.
patch("futures=[pool.submit(get_games,code,day) for name,code in LEAGUES if code in globals().get(\"selected_leagues\", DEFAULT_LEAGUES)]",
      "futures=[pool.submit(get_games,code,day) for name,code in LEAGUES]")
patch("with ThreadPoolExecutor(max_workers=6) as pool:\n        futures=[pool.submit(get_games,code,day) for name,code in LEAGUES]",
      "with ThreadPoolExecutor(max_workers=18) as pool:\n        futures=[pool.submit(get_games,code,day) for name,code in LEAGUES]")
patch("targets=[(name,code) for name,code in LEAGUES if code in selected_leagues]",
      """targets=sorted(LEAGUES,key=lambda item:(
            0 if item[1] in ('sui.1','sui.2','sui.cup') else
            (1 if item[1] in selected_leagues else 2),item[0]))""")
patch("with ThreadPoolExecutor(max_workers=7) as pool:\n            futures={pool.submit(get_games,code,date):name for name,code in targets}",
      "with ThreadPoolExecutor(max_workers=18) as pool:\n            futures={pool.submit(get_games,code,date):name for name,code in targets}")
# Swiss Cup might be absent from ESPN on some days, but querying its own
# competition code does not suppress the existing two Swiss leagues.
patch("('Challenge League Schweiz', 'sui.2'),",
      "('Challenge League Schweiz', 'sui.2'), ('Schweizer Cup (sofern Daten vorhanden)', 'sui.cup'),")
# Better catalog visibility, no false worldwide-complete claims.
patch("'Keine Spiele in markierten Ligen.'","'Keine Spiele in den erreichbaren Wettbewerben.'")
patch("monitor.last[key]=(int(game.get('hs',0)),int(game.get('as',0)))",
      "monitor.last[(str(game.get('league')),key)]=(int(game.get('hs',0)),int(game.get('as',0)))")

# Semi-transparent overlay ONLY on the quick TV browser, not on every settings
# screen. Transparent PNG plus blend and widget transparency avoids black box.
skin_insert="""class QuickLiveScreen(GamesScreen):
    \"\"\"TV hotkey: today by kickoff, same-time matches by league importance.\"\"\"
    skin=(BaseScreen.skin
          .replace('backgroundColor="#07162F"', 'transparent="1" backgroundColor="transparent"')
          .replace('ga_menu.png', 'ga_live_glass.png')
          .replace('zPosition="0" alphatest="off"', 'zPosition="0" transparent="1" alphatest="blend"')
          .replace('backgroundColor="#101E3F"', 'transparent="1" backgroundColor="#0D1D35"'))
"""
patch('''class QuickLiveScreen(GamesScreen):
    """TV hotkey: today by kickoff, same-time matches by league importance."""
''',skin_insert)
patch("popup_scorer(?:_mini|_normal)?))\\.png",
      "popup_scorer(?:_mini|_normal)?|live_glass))\\.png")

# Non-goal alerts must keep real score/team identities, never play goal audio,
# and never replay the 12-frame GOAL intro.
patch("color='#94FFD8' if kind=='scorer' else '#FFDC82'",
      "color=('#FF718B' if kind in ('cancel','redcard') else ('#94FFD8' if kind=='scorer' else '#FFDC82'))")
patch("self.duration=max(7,int(duration)) if kind=='goal' and (home_url or away_url) else max(2,int(duration))",
      "self.duration=(3 if kind in ('cancel','redcard') else (max(7,int(duration)) if kind=='goal' and (home_url or away_url) else max(2,int(duration))))")

# Red cards are read only from the EXACT ESPN match ID and its own team IDs.
# No fuzzy match of the names of other fixtures. No speculative penalties.
cards_source=r'''
RED_CARD_CACHE={}
RED_CARD_LOCK=threading.RLock()
def _espn_red_cards(game):
    league=str(game.get('league') or '')
    ident=str(game.get('id') or '')
    if not re.fullmatch(r'[A-Za-z0-9_.]+',league) or not ident.isdigit():
        return []
    identity=(league,ident)
    now=time.time()
    with RED_CARD_LOCK:
        old=RED_CARD_CACHE.get(identity)
        if old and now-old[0]<45:return old[1]
    from urllib.parse import urlencode
    url=("https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?%s"
         %(league,urlencode({'event':ident})))
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GoalAlert/6.13.14'})
        with urllib.request.urlopen(req,timeout=8) as response:
            data=json.load(response)
        header=data.get('header') or {}
        ids=[str(header.get('id') or '')]+[
            str(c.get('id') or '') for c in header.get('competitions') or [] if isinstance(c,dict)]
        known=[x for x in ids if x]
        if known and ident not in known:raise ValueError('Wrong ESPN fixture')
        expected_ids={side:str(game.get(side+'_team_id') or '') for side in ('home','away')}
        for comp in header.get('competitions') or []:
            for team in comp.get('competitors') or []:
                if not isinstance(team,dict):continue
                side=team.get('homeAway')
                if side in expected_ids and expected_ids[side]:
                    if str(_team_identity(team.get('team') or team))!=expected_ids[side]:
                        raise ValueError('Wrong team IDs')
        containers=[data,header,data.get('boxscore') or {}]
        containers.extend(c for c in header.get('competitions') or [] if isinstance(c,dict))
        cards=[];seen=set()
        for parent in containers:
            if not isinstance(parent,dict):continue
            for group_name in ('keyEvents','details','plays','incidents','cards'):
                group=parent.get(group_name) or []
                if isinstance(group,dict):group=group.get('plays') or group.get('items') or []
                if not isinstance(group,list):continue
                for event in group:
                    if not isinstance(event,dict):continue
                    kind=event.get('type') or event.get('alternativeType') or {}
                    if isinstance(kind,dict):
                        kind=' '.join(str(kind.get(k) or '') for k in ('text','name','abbreviation'))
                    color=event.get('cardType') or event.get('card') or ''
                    if isinstance(color,dict):color=color.get('name') or color.get('color') or ''
                    label=' '.join(str(event.get(k) or '') for k in ('text','shortText','description'))
                    classification=(' '.join((str(kind),str(color),label))).lower()
                    if not re.search(r'\bred[\s-]*card\b|\bsecond yellow\b|\bsecond booking\b|\bsent off\b|\bsending off\b',classification):
                        if str(color).lower() not in ('red','rc'):continue
                    if re.search(r'\b(no red card|red card overturned|red card rescinded|disallowed)\b',classification):
                        continue
                    parts=event.get('athletes') or event.get('participants') or []
                    first=parts[0] if parts and isinstance(parts[0],dict) else {}
                    athlete=first.get('athlete') if isinstance(first.get('athlete'),dict) else first
                    player=athlete.get('displayName') or athlete.get('name') or event.get('playerName') or ''
                    clock=event.get('clock') or {}
                    if isinstance(clock,dict):minute=clock.get('displayValue') or event.get('minute') or '?'
                    else:minute=str(clock or event.get('minute') or '?')
                    side=_event_team_side(event,game)
                    if side not in ('home','away'):continue
                    signature=(side,str(player).strip().lower(),str(minute))
                    if signature in seen:continue
                    seen.add(signature)
                    cards.append({'side':side,'player':str(player)[:44],
                                  'minute':str(minute)[:12],'signature':signature})
        with RED_CARD_LOCK:RED_CARD_CACHE[identity]=(time.time(),cards)
        return cards
    except Exception:
        with RED_CARD_LOCK:RED_CARD_CACHE[identity]=(time.time(),[])
        return []

'''
patch("class Monitor:",cards_source+"class Monitor:")
# re imported at module level, available on the receiver too.
patch("import json\nimport threading","import json\nimport re\nimport threading")

patch("self.preload_running=False\n    def start(self,session):",
      """self.preload_running=False
        self.pending_corrections={}
        self.red_card_seen={}
        self.red_card_results=None
        self.red_card_busy=False
    def start(self,session):""")
patch("result=self.results;self.results=None\n            update=self.goal_update;self.goal_update=None",
      "result=self.results;self.results=None\n            card_result=self.red_card_results;self.red_card_results=None\n            update=self.goal_update;self.goal_update=None")
# Late scorer notifications can never resurrect an annulled goal.
patch("if k not in self.announced_details:\n                self.announced_details.add(k)",
      """event_match,event_side,event_count=k
            current=self.last.get(event_match)
            good=(current is not None and current[0 if event_side=='home' else 1]>=event_count)
            if good and k not in self.announced_details:
                self.announced_details.add(k)""")
old_block="""                    if old is not None and score!=old and self.is_favorite(g):
                        if score[0]>old[0] or score[1]>old[1]:
                            if config.plugins.goalalert32.enabled.value:
                                side='home' if score[0]>old[0] else 'away'
                                scoring_team=g['home'] if side=='home' else g['away']
                                self.show_goal('TOR! '+scoring_team+' | '+g['home']+' '+str(score[0])+':'+str(score[1])+' '+g['away'],
                                               g.get('home_logo_file'),g.get('away_logo_file'),kind='goal',home_url=g.get('home_logo'),away_url=g.get('away_logo'),game=g,scoring_side=side)
                                target=(key,side,score[0] if side=='home' else score[1])
                                threading.Thread(target=self.enrich_goal,args=(dict(g),target),daemon=True).start()
                    self.last[key]=score"""
new_block="""                    if old is not None and score!=old and self.is_favorite(g):
                        if score[0]<old[0] or score[1]<old[1]:
                            # Two consecutive polls must agree: ignore a single
                            # stale/out-of-order response, including after VAR.
                            candidate=self.pending_corrections.get(key)
                            if candidate!=score:
                                self.pending_corrections[key]=score
                                continue
                            self.pending_corrections.pop(key,None)
                            if config.plugins.goalalert32.enabled.value:
                                self.show_goal('TOR ABERKANNT - Spielstand '+str(score[0])+':'+str(score[1]),
                                               g.get('home_logo_file'),g.get('away_logo_file'),
                                               kind='cancel',home_url=g.get('home_logo'),
                                               away_url=g.get('away_logo'),game=g)
                            self.announced_details={x for x in self.announced_details if x[0]!=key}
                        elif score[0]>old[0] or score[1]>old[1]:
                            self.pending_corrections.pop(key,None)
                            if config.plugins.goalalert32.enabled.value:
                                side='home' if score[0]>old[0] else 'away'
                                scoring_team=g['home'] if side=='home' else g['away']
                                self.show_goal('TOR! '+scoring_team+' | '+g['home']+' '+str(score[0])+':'+str(score[1])+' '+g['away'],
                                               g.get('home_logo_file'),g.get('away_logo_file'),kind='goal',home_url=g.get('home_logo'),away_url=g.get('away_logo'),game=g,scoring_side=side)
                                target=(key,side,score[0] if side=='home' else score[1])
                                threading.Thread(target=self.enrich_goal,args=(dict(g),target),daemon=True).start()
                    elif score==old:
                        self.pending_corrections.pop(key,None)
                    self.last[key]=score"""
patch(old_block,new_block)

cards_tick="""        if card_result is not None:
            for key,g,cards in card_result:
                signatures={tuple(card.get('signature') or ()) for card in cards}
                if key not in self.red_card_seen:
                    self.red_card_seen[key]=signatures  # existing cards: baseline, no retro-alerts
                    continue
                fresh=[card for card in cards if tuple(card.get('signature') or ())
                       not in self.red_card_seen[key]]
                self.red_card_seen[key].update(signatures)
                if fresh and self.is_favorite(g) and config.plugins.goalalert32.enabled.value:
                    card=fresh[-1]
                    team=str(g.get(card['side']) or 'Unbekannt')
                    player=card.get('player') or ''
                    detail='ROTE KARTE: '+team+((' - '+player) if player else '')
                    detail+=' | '+str(card.get('minute') or '?')+"'"
                    self.show_goal(detail,g.get('home_logo_file'),
                                   g.get('away_logo_file'),kind='redcard',
                                   home_url=g.get('home_logo'),
                                   away_url=g.get('away_logo'),game=g)
"""
patch("        if not self.busy:\n            self.busy=True",cards_tick+"        if not self.busy:\n            self.busy=True")
# Trigger red-card checker separately after publishing score results, with
# its own workers so a slow summary endpoint cannot delay GOAL notifications.
patch("            with self.lock:self.results=[g for g in games if g.get('state')=='in']",
      """            live=[g for g in games if g.get('state')=='in']
            with self.lock:self.results=live
            if not self.red_card_busy and live:
                self.red_card_busy=True
                threading.Thread(target=self.fetch_red_cards,args=(list(live),),
                                 daemon=True).start()""")
patch("    def fetch(self):\n        try:\n            codes={v.get('league') for v in favorites.values() if v.get('league')}",
      """    def fetch_red_cards(self,games):
        try:
            jobs=[]
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures={pool.submit(_espn_red_cards,g):g for g in games
                         if g.get('provider')=='ESPN' and self.is_favorite(g)}
                for future in as_completed(futures):
                    g=futures[future]
                    try:
                        cards=future.result()
                    except Exception:
                        cards=[]
                    jobs.append(((str(g.get('league')),str(g.get('id'))),g,cards))
            with self.lock:self.red_card_results=jobs
        finally:
            self.red_card_busy=False
    def fetch(self):
        try:
            codes={v.get('league') for v in favorites.values() if v.get('league')}""")

# Compact, shaded, detailed football rendered by supersampling and centered
# vertically instead of being cropped at 117% of the entire 104px frame.
intro=(ROOT/'scripts/goalalert_intro_art.py').read_text(encoding='utf-8')
def intro_patch(a,b):
    global intro
    if intro.count(a)!=1:raise SystemExit('Original goal intro changed: '+a[:70])
    intro=intro.replace(a,b,1)
intro_patch('ball=football(int(h*1.17))','ball=football(int(h*.67))')
intro_patch('bx=int((-115+220*(t**.68))*ss)','bx=int((-78+218*(t**.70))*ss)')
intro_patch('by=int((outh-136)/2*ss)','by=(h-ball.height)//2')
intro_patch('fill=(9,32,76,115)','fill=(9,32,76,66)')
intro_patch('shade=int(78+155*light+80*shininess)',
            'shade=int(68+160*light+95*shininess)')
# Surface detailing: tapered specular edges remain realistic and readable
# when downsampled to 65-70px instead of a massive rotating sphere.
intro_patch('fill=(255,255,255,35)', 'fill=(255,255,255,52)')
exec(compile(intro,'goalalert_intro_art_61314.py','exec'),{'__name__':'__main__','__file__':str(ROOT/'scripts/goalalert_intro_art.py')})

# Dark translucent 4K-glass panel for live scores; transparent everywhere
# else; all rounded edges have anti-aliased RGBA with no black corners.
from PIL import Image,ImageDraw,ImageFilter
for width,height,suffix in ((950,610,''),(1425,915,'_fhd')):
    ss=2;w=width*ss;h=height*ss
    frame=Image.new('RGBA',(w,h),(0,0,0,0))
    glow=Image.new('RGBA',(w,h),(0,0,0,0))
    d=ImageDraw.Draw(glow)
    inset=16*ss
    d.rounded_rectangle((inset,inset,w-inset,h-inset),radius=30*ss,
                        outline=(45,208,255,145),width=6*ss)
    frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8*ss)))
    d=ImageDraw.Draw(frame)
    d.rounded_rectangle((inset,inset,w-inset,h-inset),radius=28*ss,
                        fill=(7,24,45,64),outline=(130,226,255,192),width=2*ss)
    d.rounded_rectangle((inset+6*ss,inset+6*ss,w-inset-6*ss,h-inset-6*ss),
                        radius=25*ss,outline=(182,245,255,56),width=ss)
    d.line((47*ss,133*ss,(width-47)*ss,133*ss),fill=(50,208,255,90),width=2*ss)
    d.line((47*ss,(height-85)*ss,(width-47)*ss,(height-85)*ss),
           fill=(50,208,255,65),width=ss)
    frame.resize((width,height),Image.Resampling.LANCZOS).save(
        DEST/('ga_live_glass'+suffix+'.png'),optimize=True)

# Reduce existing goal and scorer glass darkness without affecting typography.
for png in DEST.glob('ga_popup_*.png'):
    with Image.open(png) as im:
        art=im.convert('RGBA')
    art.putalpha(art.getchannel('A').point(lambda x:int(x*.66)))
    art.save(png,optimize=True)

if s.count('6.13.13')<2:raise SystemExit('Missing expected base version fields')
s=s.replace('6.13.13','6.13.14')
path.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.14\n',encoding='utf-8')
compile(s,str(path),'exec')
# Regression checks on text and concrete art images. No live receiver needed.
assert 'targets=[(name,code) for name,code in LEAGUES if code in selected_leagues]' not in s
assert "kind='cancel'" in s and "kind='redcard'" in s
assert 'self.pending_corrections' in s and 'self.red_card_seen' in s
assert "backgroundColor=\"transparent\"" in s
assert 'ga_live_glass.png' in s
assert "ball=football(int(h*.67))" in intro
for name in ('ga_live_glass.png','ga_live_glass_fhd.png',
             'ga_goal_intro_11.png','ga_goal_intro_11_fhd.png'):
    im=Image.open(DEST/name)
    assert im.mode=='RGBA' and im.getpixel((0,0))[3]==0 and im.getpixel((im.width-1,im.height-1))[3]==0
# The 4K UI remains simple RGBA, no undocumented IPK data.
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('6.13.14 fully built: Swiss+global fixtures, translucency, compact GOAL, rollback, red card')
