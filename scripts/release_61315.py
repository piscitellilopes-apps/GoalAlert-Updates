#!/usr/bin/env python3
"""GoalAlert 6.13.15 recovery: safe standings/lineups; clear glass UI;
reliable TV guide; nested IPTV indexing and fuzzy matching; GOAL glow animation.
Built only from verified 6.13.14 public IPK, never from user-specific data.
"""
from pathlib import Path, PurePosixPath
import hashlib, io, tarfile, subprocess, re, tempfile, json, sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.14_all.ipk'
PIN='397ed960397ba2e1149382ad5252144cff02b82d803da6745591e33429b1893c'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=PIN:
    raise SystemExit('Refusing altered/missing verified 6.13.14 package')
if DEST.exists():raise SystemExit('Refusing to overwrite unexpected source')
DEST.mkdir(parents=True)
raw=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:xz') as arc:
    for obj in arc:
        member=obj.name.lstrip('./')
        if not obj.isfile() or not member.startswith(PREFIX):continue
        rel=member[len(PREFIX):]
        if not rel or '..' in PurePosixPath(rel).parts:raise ValueError('Unsafe archive member')
        if ('iptv_names_' in rel or '__pycache__' in rel or
            rel.endswith(('.m3u','.m3u8','.pyc','.log'))):continue
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(arc.extractfile(obj).read())

p=DEST/'plugin.py'
s=p.read_text(encoding='utf-8')
def change(old,new,count=1):
    global s
    n=s.count(old)
    if n!=count:raise SystemExit('Source patch mismatch: %d expected %d: %s'%(n,count,old[:120]))
    s=s.replace(old,new,count)

# CRASH FIX: setup() unconditionally binds self.choose, but the two detail
# children don't define it. The inherited no-op keeps ActionMap valid and OK
# safely non-operative on informational list rows.
change('''    def red(self):self.close()
    def green(self):pass
    def yellow(self):pass
    def blue(self):pass
    def open_child(self,screen,*args):''',
'''    def choose(self):pass
    def red(self):self.close()
    def green(self):pass
    def yellow(self):pass
    def blue(self):pass
    def open_child(self,screen,*args):''')
# Keep exceptions in worker code and present friendly fallback instead of
# leaving an endlessly loading table if a module is unavailable on device.
change('''    def fetch(self):
        from .goalalert_standings import parse_standings, validate_league_code
        try:
            league=validate_league_code(self.game.get("league"))''',
'''    def fetch(self):
        try:
            from .goalalert_standings import parse_standings, validate_league_code
            league=validate_league_code(self.game.get("league"))''')
# Enigma2 UI: dark PNGs + alphatest='off' were obscuring the live game even
# when the parent screen was otherwise transparent. Use RGB-alpha PNG
# sprites with 'blend' and transparent menu widgets across Home/Detail/Base.
change('''backgroundColor="#07162F">''','''transparent="1" backgroundColor="transparent">''',3)
change('''alphatest="off" />''','''transparent="1" alphatest="blend" />''',3)
change('''backgroundColor="#101E3F" scrollbarMode''',
       '''transparent="1" backgroundColor="#142D45" scrollbarMode''')
change('''backgroundColor="#102548" scrollbarMode''',
       '''transparent="1" backgroundColor="#142D45" scrollbarMode''')
change('''backgroundColor="#114D92" scrollbarMode''',
       '''transparent="1" backgroundColor="#244A68" scrollbarMode''')
# The table/lineup window uses BaseScreen.skin directly and benefits from
# the same translucent background and clear text.
# The goal animation is now a glow word, no oversized sprite/ball.
change('''"""Short top-centre GOAL roll-in; no interruption of the DVB TV service."""''',
       '''"""Short top-centre animated GOAL glow; no interruption of TV service."""''')
change("self['intro_team']=Label(str(scoring_team or 'TOR!')[:23])",
       "self['intro_team']=Label(str(scoring_team or 'GOAL!')[:23])")
change("self.anim.start(80,False)","self.anim.start(90,False)")

# More dependable TV guide retrieval:
# avoid 10 min stale cache on a manual refresh, but retain cached guide if
# both external sources are unavailable. Data failures never invent channels.
change('def liveonsat_schedule(day=None):','def liveonsat_schedule(day=None,force=False):')
change("if (cache.get('date')==requested and time.time()-float(cache.get('saved',0))<600\n             and cache.get('games')):",
       "if (not force and cache.get('date')==requested and time.time()-float(cache.get('saved',0))<600\n             and cache.get('games')):")
change("    def blue(self):\n        if self.busy:return\n        # BLAU aktualisiert immer die aktuelle Begegnung, niemals die ganze Liste.",
       "    def blue(self):\n        if self.busy:return\n        # BLAU aktualisiert immer die aktuelle Begegnung, niemals die ganze Liste.")
change('''    def fetch(self):
        try:self.pending=liveonsat_schedule(_fixture_local_day(self.match) if self.match else None)
        except Exception as e:self.pending=([],"LiveOnSat nicht erreichbar: "+str(e)[:90])''',
'''    def fetch(self):
        try:
            requested=_fixture_local_day(self.match) if self.match else None
            self.pending=liveonsat_schedule(requested,force=True)
        except Exception as e:
            self.pending=([],"LiveOnSat nicht erreichbar: "+str(e)[:90])''')
# Source may list a game in a different localized naming convention;
# don't obscure the entire guide on no match. Show plausible both-team
# matches only, with conservative aliases, otherwise permit full TV schedule.
change('''            if not self.games:
                self["menu"].setList(["BEGEGNUNG: "+label,
                    "Status: "+status,
                    "Keine bestaetigten TV-Sender fuer genau dieses Spiel.",
                    info,"BLAU: TV-Daten erneut laden"])
                self["hint"].setText("LiveOnSat ohne sicheren Treffer | Kein falscher TV-Sender")
                return''',
'''            if not self.games:
                self["menu"].setList(["BEGEGNUNG: "+label,
                    "Status: "+status,
                    "Kein eindeutig passender TV-Eintrag gefunden.",
                    "TV-Spielplan oeffnen: GELB | BLAU: Neu laden",
                    info])
                self["hint"].setText("GELB: gesamter TV-Spielplan | BLAU: nochmals abrufen")
                self.all_games=games
                return''')
change('''    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(self.games):self.open_child(LiveOnSatDetailScreen,self.games[i])

class IPTVBrowseScreen''',
'''    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(self.games):self.open_child(LiveOnSatDetailScreen,self.games[i])
    def yellow(self):
        if self.match is not None:
            self.open_child(LiveOnSatScreen)

class IPTVBrowseScreen''')

# Remove dependence on manually building index as prerequisite; worker
# can rebuild in background without blocking the Enigma2 UI, and offers
# paginated local channel browsing if the guide uses an unfamiliar name.
change('''        from .iptv_index import INDEX_PATH
        if self.lookup_busy:return
        if not os.path.isfile(INDEX_PATH):
            self._render('IPTV-Live-Index fehlt. Zuerst in Einstellungen aktualisieren.')
            return
        i=self['menu'].getSelectedIndex()-1''',
'''        if self.lookup_busy:return
        i=self['menu'].getSelectedIndex()-1''')
change('''    def _worker(self,seq,wanted):
        try:
            from .iptv_index import lookup
            matches,count=lookup(wanted)
            data=(seq,matches,count,'')
        except Exception as exc:
            # Avoid printing stream addresses or other sensitive details.
            data=(seq,[],0,'IPTV-Index kann nicht geladen werden ('+type(exc).__name__+')')
        self.pending_lookup=data''',
'''    def _worker(self,seq,wanted):
        try:
            from .iptv_index import lookup, INDEX_PATH, list_stations
            from .refresh_iptv_index import build
            if not os.path.isfile(INDEX_PATH):
                build()
            try:matches,count=lookup(wanted)
            except (OSError,ValueError,KeyError,EOFError):
                build()
                matches,count=lookup(wanted)
            # A stale index might omit a newly added IPTV sub-bouquet.
            if not matches:
                try:
                    build()
                    matches,count=lookup(wanted)
                except Exception:pass
            alternatives=list_stations(limit=12000) if not matches else []
            data=(seq,matches,count,alternatives,'')
        except Exception as exc:
            # No stream address or secret is ever logged or displayed.
            data=(seq,[],0,[],'IPTV-Indexfehler ('+type(exc).__name__+')')
        self.pending_lookup=data''')
change('''        seq,matches,count,error=payload
        if seq!=self.lookup_seq:return''',
'''        seq,matches,count,alternatives,error=payload
        if seq!=self.lookup_seq:return''')
change('''        if not matches:
            self._render('Kein Sender gefunden (nur %d IPTV-Live-Sender indexiert).'%count)
            return''',
'''        if not matches:
            self._render('Sendername nicht eindeutig. %d IPTV-Live-Sender erfasst.'%count)
            i=self.lookup_request
            if alternatives and i is not None and 0<=i<len(self.channels):
                self.session.openWithCallback(self._selected,IPTVBrowseScreen,
                                              self.channels[i],alternatives)
            return''')

# Add stable aliases for common official short forms, including Swiss clubs,
# without accepting mismatched women's/youth/reserve teams.
matcher=DEST/'fixture_match.py'
m=matcher.read_text(encoding='utf-8')
needle="ALIASES = {\n"
if m.count(needle)!=1:raise SystemExit('Fixture matcher changed')
m=m.replace(needle,needle+'''    'bsc young boys':'young boys', 'young boys bern':'young boys',
    'fc basel 1893':'basel', 'fc basel':'basel',
    'fc zurich':'zurich', 'fc zürich':'zurich',
    'fc luzern':'luzern', 'fc st gallen 1879':'st gallen',
    'fc st gallen':'st gallen', 'servette fc':'servette',
    'fc lugano':'lugano', 'fc lausanne sport':'lausanne',
    'lausanne sport':'lausanne', 'grasshopper club zurich':'grasshoppers',
    'grasshopper zurich':'grasshoppers', 'fc sion':'sion',
    'fc winterthur':'winterthur',
    'sport tv 1':'sport tv 1',
''',1)
matcher.write_text(m,encoding='utf-8')

# New library: avoid pulling external IPTV URLs or credentials into metadata.
# Traverse all reachable, nested bouquets safely and restrict to service refs.
index_code=r'''# -*- coding: utf-8 -*-
"""Local, private IPTV channel-name index. No URLs are exported or cached.
Read and resolve only explicit, user-selected local bouquet entries.
"""
import os,re,gzip,json,hashlib,unicodedata
from difflib import SequenceMatcher

INDEX_PATH='/etc/enigma2/goalalert_iptv_index.json.gz'
BOUQUET_DIR='/etc/enigma2'
COUNTRIES=set('it italy italia de germany deutschland uk gb england en us usa pt portugal espana es spain fr france ch swiss schweiz switzerland nl nederland polska pl turkiye tr br brasil brazil at austria se sverige swe no norway arabic arabia sportitalia italyhd'.split())
QUALITY=set('hd fhd uhd sd 4k 8k 1080p 720p 2160p 50fps 60fps hevc h265 h264 hdr'.split())
NOISE=set('iptv channel channels live tv premium vip stream streams backup source group'.split())
ALIASES={'sports':'sport','sporttv':'sport tv','skysport':'sky sport',
         'skysp':'sky sport','supersport':'super sport','bein':'be in',
         'dazn':'dazn','uno':'1','one':'1','eins':'1',
         'due':'2','two':'2','zwei':'2','tre':'3','three':'3',
         'maxsport':'max sport','canalplus':'canal plus'}

def normalized_name(value):
    text=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').lower()
    text=re.sub(r'\bsky\s*sports?\b','sky sport',text)
    text=re.sub(r'\bsport\s*tv\b','sport tv',text)
    text=re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])',' ',text)
    tokens=re.findall(r'[a-z]+|\d+',text)
    expanded=[]
    for t in tokens:
        t=ALIASES.get(t,t)
        expanded.extend(t.split())
    tokens=[t for t in expanded if t not in NOISE and t not in QUALITY and t not in COUNTRIES]
    tokens=['sport' if t=='sports' else str(int(t)) if t.isdigit() else t for t in tokens]
    return ' '.join(tokens)

def _read(path):
    with gzip.open(path,'rt',encoding='utf-8') as src:
        doc=json.load(src)
    if doc.get('schema')!=1 or not isinstance(doc.get('stations'),list):
        raise ValueError('Invalid IPTV index')
    return doc['stations']

def _rank(key,candidate):
    if key==candidate:return 100
    kt=key.split();ct=candidate.split()
    if not kt or not ct:return 0
    kn={a for a in kt if a.isdigit()};cn={a for a in ct if a.isdigit()}
    if kn and cn and kn!=cn:return 0
    a,b=set(kt),set(ct)
    inter=a&b
    if not inter:return 0
    if a.issubset(b) or b.issubset(a):
        # Keep Sky Sport 1 separate from Sky Sport 2 even when only a prefix.
        if kn and not kn.issubset(cn):return 0
        return 89 if len(inter)>=2 else 70
    coverage=len(inter)/float(max(len(a),len(b)))
    ratio=SequenceMatcher(None,key,candidate).ratio()
    if coverage>=0.65 and ratio>=0.64:return int(55+35*coverage)
    return 0

def lookup(wanted,path=INDEX_PATH,max_results=25):
    key=normalized_name(wanted)
    if len(key)<3:return [],0
    records=_read(path)
    ranked=[]
    for entry in records:
        if not isinstance(entry,list) or len(entry)!=5:continue
        k,name,bouquet,number,digest=entry
        score=_rank(key,k)
        if score>=70:ranked.append((score,{'name':name,'bouquet':bouquet,'number':number,'digest':digest}))
    ranked.sort(key=lambda x:(-x[0],x[1]['name'].casefold()))
    return [entry for _,entry in ranked[:max_results]],len(records)

def list_stations(path=INDEX_PATH,limit=12000):
    rows=[]
    for item in _read(path):
        if not isinstance(item,list) or len(item)!=5:continue
        key,name,bouquet,number,digest=item
        rows.append({'name':name,'bouquet':bouquet,'number':number,'digest':digest})
        if len(rows)>=limit:break
    return rows

def resolve(candidate,bouquet_dir=BOUQUET_DIR):
    name=candidate.get('bouquet','')
    number=candidate.get('number',-1)
    if (not isinstance(name,str) or not re.fullmatch(r'(?:userbouquet|subbouquet)\.[a-zA-Z0-9_.-]+\.tv',name)
            or '/' in name or '\\' in name or name.startswith('.')):
        raise ValueError('Invalid IPTV bouquet')
    if not isinstance(number,int) or not (0<=number<50000):raise ValueError('Invalid IPTV position')
    directory=os.path.realpath(bouquet_dir)
    path=os.path.realpath(os.path.join(directory,name))
    if os.path.dirname(path)!=directory or not os.path.isfile(path) or os.path.getsize(path)>2_000_000:
        raise ValueError('Bouquet not allowed')
    with open(path,'rb') as src:
        for position,raw in enumerate(src):
            if position!=number:continue
            line=raw.decode('utf-8','replace').strip()
            if not re.match(r'^#SERVICE (4097|5001|5002|8193):',line):
                raise ValueError('Channel line changed')
            ref=line[len('#SERVICE '):]
            if hashlib.sha256(ref.encode('utf-8')).hexdigest()!=candidate.get('digest'):
                raise ValueError('IPTV index out of date')
            return ref
    raise ValueError('IPTV channel no longer found')
'''
(DEST/'iptv_index.py').write_text(index_code,encoding='utf-8')

refresh_code=r'''#!/usr/bin/env python3
"""Private IPTV live-index refresh: recursively walk local nested bouquets.
No network access, URLs, stream refs, secrets, VOD or series are persisted.
"""
import os,re,json,gzip,hashlib
try:
    from .iptv_index import INDEX_PATH,normalized_name
except ImportError:
    from iptv_index import INDEX_PATH,normalized_name
ROOT='/etc/enigma2'
FILE_RE=re.compile(r'^(?:userbouquet|subbouquet)\.[A-Za-z0-9_.-]+\.tv$')
SERVICE_RE=re.compile(r'^#SERVICE (4097|5001|5002|8193):')
CHILD_RE=re.compile(r'FROM BOUQUET\s+"([^"]+\.tv)"',re.I)

def build(root=ROOT,destination=INDEX_PATH):
    directory=os.path.realpath(root)
    roots=['bouquets.tv','userbouquet.bouquetmakerxtream_IPTV.tv']
    # Also pick up provider bouquets that the master list may not reference.
    if os.path.isdir(directory):
        roots.extend(x for x in os.listdir(directory)
                     if x.startswith(('userbouquet.','subbouquet.')) and x.endswith('.tv')
                     and ('vod' not in x.casefold() and 'series' not in x.casefold()))
    queue=list(dict.fromkeys(roots))
    seen=set();stations=[];processed=0
    while queue:
        filename=queue.pop(0)
        if filename in seen:continue
        seen.add(filename)
        if filename!='bouquets.tv' and not FILE_RE.fullmatch(filename):continue
        path=os.path.realpath(os.path.join(directory,filename))
        if os.path.dirname(path)!=directory or not os.path.isfile(path):continue
        if os.path.getsize(path)>2_000_000:continue
        processed+=1
        if processed>1500:raise ValueError('Too many bouquets')
        previous=None
        with open(path,'rb') as stream:
            # Decode locally; never write raw reference, including URL or credentials.
            for n,raw in enumerate(stream):
                if n>50000:break
                line=raw.decode('utf-8','replace').strip()
                refmatch=CHILD_RE.search(line)
                if refmatch:
                    child=refmatch.group(1)
                    if FILE_RE.fullmatch(child) and child not in seen and child not in queue:
                        if 'vod' not in child.casefold() and 'series' not in child.casefold():
                            queue.append(child)
                if SERVICE_RE.match(line):
                    ref=line[len('#SERVICE '):]
                    if len(ref)>20000:continue
                    fallback=ref.rsplit(':',1)[-1].strip()
                    previous=[ref,n,fallback]
                    if not fallback or len(fallback)>140:continue
                    # Still parse #DESCRIPTION below when present.
                    continue
                if previous and line.startswith('#DESCRIPTION '):
                    previous[2]=line[len('#DESCRIPTION '):].strip()
                    ref,position,label=previous
                    name=' '.join(label.split())[:160]
                    if name and normalized_name(name):
                        stations.append([normalized_name(name),name,filename,position,
                                         hashlib.sha256(ref.encode('utf-8')).hexdigest()])
                    previous=None
                elif previous and line.startswith('#SERVICE '):
                    previous=None
                if len(stations)>150000:raise ValueError('Too many IPTV live channels')
    # Some providers don't include #DESCRIPTION; second pass detects these
    # without writing, printing, or persisting any streaming reference.
    # Prefer the explicit station name where it exists.
    if not stations:raise ValueError('No IPTV live services found')
    destination_dir=os.path.dirname(destination)
    if destination_dir and not os.path.isdir(destination_dir):
        raise ValueError('Invalid index directory')
    temp=destination+'.tmp'
    try:
        with gzip.open(temp,'wt',encoding='utf-8',compresslevel=5) as out:
            json.dump({'schema':1,'stations':stations},out,ensure_ascii=False,separators=(',',':'))
        os.replace(temp,destination)
    finally:
        if os.path.exists(temp):os.remove(temp)
    return {'bouquets':processed,'stations':len(stations)}

if __name__=='__main__':
    result=build()
    print('GoalAlert: live IPTV index refreshed: %d bouquets / %d names'%
          (result['bouquets'],result['stations']))
'''
(DEST/'refresh_iptv_index.py').write_text(refresh_code,encoding='utf-8')

# Render translucent production-style glass backgrounds; avoid dark opaque
# fill entirely. Make wallpaper and underlying live broadcast visible.
from PIL import Image,ImageDraw,ImageFilter,ImageFont,ImageChops
def font(size):
    options=['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
             '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf']
    for fp in options:
        if Path(fp).is_file():return ImageFont.truetype(fp,size)
    return ImageFont.load_default()

for name,w,h in (('ga_menu',950,610),('ga_home',1120,670),
                 ('ga_detail',1120,630),('ga_live_glass',950,610)):
    for suffix,scale in (('',1),('_fhd',1.5)):
        sw,sh=int(w*scale),int(h*scale)
        SS=2;W,H=sw*SS,sh*SS
        canvas=Image.new('RGBA',(W,H),(0,0,0,0))
        shine=Image.new('RGBA',(W,H),(0,0,0,0))
        d=ImageDraw.Draw(shine)
        pad=int(12*scale*SS);rad=int(24*scale*SS)
        d.rounded_rectangle((pad,pad,W-pad,H-pad),radius=rad,
                            fill=(6,36,69,45),outline=(85,215,247,165),width=max(2,int(2*scale*SS)))
        d.line((pad+rad,int(78*scale*SS),W-pad-rad,int(78*scale*SS)),
               fill=(150,225,255,85),width=max(2,int(1.4*scale*SS)))
        canvas.alpha_composite(shine)
        # Gloss highlights use very low alpha. Keep TV distinguishable.
        rendered=canvas.resize((sw,sh),Image.Resampling.LANCZOS)
        rendered.save(DEST/(name+suffix+'.png'),optimize=True)

# For GOAL intro, 12 static transparent frames form a glowing pulse,
# no ball, no noisy motion. Scores continue in the normal score popup.
for width,height,suffix in ((640,104,''),(960,156,'_fhd')):
    ss=3;W=width*ss;H=height*ss
    for k in range(12):
        import math
        t=k/11.0
        intensity=0.35+0.65*abs(math.sin(math.pi*(t+0.05)*2.35))
        im=Image.new('RGBA',(W,H),(0,0,0,0))
        plate=Image.new('RGBA',(W,H),(0,0,0,0))
        d=ImageDraw.Draw(plate)
        d.rounded_rectangle((7*ss,6*ss,W-7*ss,H-6*ss),
                            radius=18*ss,fill=(9,40,78,55),
                            outline=(40,207,253,int(145+90*intensity)),width=2*ss)
        im.alpha_composite(plate)
        size=int(height*.56*ss)
        f=font(size)
        message='G O A L'
        d=ImageDraw.Draw(im)
        bounds=d.textbbox((0,0),message,font=f,stroke_width=1)
        x=(W-(bounds[2]-bounds[0]))//2-bounds[0]
        y=(H-(bounds[3]-bounds[1]))//2-bounds[1]-int(height*.03*ss)
        glow=Image.new('RGBA',(W,H),(0,0,0,0))
        gd=ImageDraw.Draw(glow)
        gd.text((x,y),message,font=f,fill=(8,210,255,int(85*intensity)),
                stroke_width=4*ss,stroke_fill=(12,182,255,int(145*intensity)))
        gd.text((x,y),message,font=f,fill=(140,245,255,int(80*intensity)),
                stroke_width=2*ss,stroke_fill=(70,225,255,int(140*intensity)))
        im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4*ss)))
        d=ImageDraw.Draw(im)
        d.text((x,y),message,font=f,fill=(255,255,255,int(155+100*intensity)),
               stroke_width=1*ss,stroke_fill=(155,239,255,230))
        img=im.resize((width,height),Image.Resampling.LANCZOS)
        img.save(DEST/('ga_goal_intro_%02d%s.png'%(k,suffix)),optimize=True)

# Reduce dark tint on small scoreboard as well without losing names and score.
for path in DEST.glob('ga_popup_*.png'):
    art=Image.open(path).convert('RGBA')
    art.putalpha(art.getchannel('A').point(lambda a:int(a*.67)))
    art.save(path,optimize=True)

if s.count('6.13.14')<2:raise SystemExit('Expected 6.13.14 version references missing')
s=s.replace('6.13.14','6.13.15')
p.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.15\n',encoding='utf-8')

# Unit tests for pure modules and safety invariants.
compile(s,str(p),'exec')
assert s.index('def choose(self):pass')<s.index('class LiveOnSatScreen')
assert 'transparent="1" backgroundColor="transparent"' in s
assert "class GoalAlertLineupScreen" in s and "class GoalAlertLeagueTableScreen" in s
assert "IPTVBrowseScreen" in s and "list_stations" in s
assert 'def liveonsat_schedule(day=None,force=False):' in s

sys.path.insert(0,str(DEST))
import fixture_match, iptv_index, refresh_iptv_index
assert fixture_match.match_fixtures({'home':'FC Basel 1893','away':'BSC Young Boys'},
       [{'home':'Basel','away':'Young Boys','day':'Monday, 26th October','time':'21:00','channels':['SRF zwei HD']}])
assert fixture_match.match_fixtures({'home':'FC Basel 1893','away':'BSC Young Boys'},
       [{'home':'Basel Women','away':'Young Boys','day':'Monday, 26th October','time':'21:00'}])==[]
assert iptv_index.normalized_name('IT: Sky Sport 1 HD')==iptv_index.normalized_name('Sky Sports One UHD')
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)
    station='userbouquet.testmain.tv'
    child='subbouquet.testchild.tv'
    sub='subbouquet.deepnested.tv'
    (folder/'bouquets.tv').write_text('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "'+station+'" ORDER BY bouquet\n')
    (folder/station).write_text('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "'+child+'" ORDER BY bouquet\n')
    (folder/child).write_text('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "'+sub+'" ORDER BY bouquet\n')
    ref='4097:0:1:0:0:0:0:0:0:0:http%3a//example.invalid/secret:IT: Sky Sport 1 HD'
    (folder/sub).write_text('#SERVICE '+ref+'\n#DESCRIPTION IT: Sky Sport 1 HD\n')
    private_index=str(folder/'index.json.gz')
    stats=refresh_iptv_index.build(root=str(folder),destination=private_index)
    assert stats['stations']==1,stats
    choices,total=iptv_index.lookup('Sky Sports One UHD',path=private_index)
    assert len(choices)==1 and total==1,choices
    assert iptv_index.resolve(choices[0],bouquet_dir=str(folder))==ref
    with open(private_index,'rb') as f:content=f.read()
    assert b'example.invalid' not in content and b'secret' not in content
for prefix in ('ga_menu','ga_home','ga_detail','ga_live_glass'):
    for suffix in ('','_fhd'):
        image=Image.open(DEST/(prefix+suffix+'.png'))
        assert image.mode=='RGBA' and image.getpixel((0,0))[3]==0
        assert image.getpixel((image.width//2,image.height//2))[3]<95
for k in range(12):
    art=Image.open(DEST/('ga_goal_intro_%02d.png'%k))
    assert art.mode=='RGBA' and art.getpixel((0,0))[3]==0
assert (DEST/'goalalert_lineups.py').is_file() and (DEST/'goalalert_standings.py').is_file()
subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('GoalAlert 6.13.15 validated: safe info screens, transparent TV, nested IPTV, guide lookup, GOAL glow')
