#!/usr/bin/env python3
"""Release 6.13.8 from verified 6.13.7; fix LIVE | WELTWEIT fake matches.

Only fully named fixtures in an explicit in-progress state qualify as live.\nDo not label missing-club records as live scores.
If the third-party LiveScore API returns invalid or no fixtures, show
verified ESPN fixtures with transparent coverage/source labels.
"""
import ast
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.7_all.ipk'
SHA='c96bb298f25b298593623df7a79af98350fd62b078a304fa801cc162141844c3'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'

if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=SHA:
    raise SystemExit('6.13.7 base checksum mismatch; refusing to publish')
if DEST.exists():
    raise SystemExit('Refusing to overwrite existing source tree')

DEST.mkdir(parents=True)
data=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as archive:
    for item in archive:
        p=item.name.lstrip('./')
        if not p.startswith(PREFIX) or not item.isfile():
            continue
        rel=p[len(PREFIX):]
        if not rel or '..' in PurePosixPath(rel).parts:
            raise SystemExit('Unsafe archive path')
        if rel.endswith(('.pyc','.m3u','.m3u8','.log')) or '__pycache__' in rel or 'iptv_names_' in rel:
            continue
        target=DEST/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(archive.extractfile(item).read())

path=DEST/'plugin.py'
s=path.read_text(encoding='utf-8')
def replace_once(old,new):
    global s
    count=s.count(old)
    if count!=1:
        raise SystemExit('Expected exactly one patch anchor, found %s: %s'%(count,old[:100]))
    s=s.replace(old,new,1)

start=s.index('    if ACTIVE_SOURCE=="livescore":',s.index('def selected_live_games():'))
end=s.index('    if ACTIVE_SOURCE=="eurobet":',start)
replacement='''    if ACTIVE_SOURCE=="livescore":
        # The optional GitHub LiveScore endpoint frequently returns incomplete
        # structures. A missing club name is NEVER a legitimate live match.
        root="https://worldcup26.ir/get/soccer"
        games=[]
        seen=set()
        reason="keine gueltigen Live-Spiele"
        try:
            leagues=source_json(root+"/leagues")
            if isinstance(leagues,dict):
                leagues=leagues.get("leagues") or leagues.get("data") or []
            if not isinstance(leagues,list):
                raise ValueError("Ligenliste ungueltig")
            for league in leagues[:12]:
                slug=(league.get("slug") or league.get("id")) if isinstance(league,dict) else None
                if not slug:continue
                from urllib.parse import quote
                try:
                    payload=source_json(root+"/"+quote(str(slug),safe="")+"/scoreboard?date="+datetime.now().strftime("%Y-%m-%d"))
                    if isinstance(payload,dict):
                        events=payload.get("events") or payload.get("matches") or payload.get("data") or []
                    else:events=payload
                    if isinstance(events,dict):
                        events=events.get("events") or events.get("matches") or events.get("items") or []
                    if not isinstance(events,list):continue
                    for event in events:
                        if not isinstance(event,dict):continue
                        try:
                            g=_external_game(event,"LiveScore Football")
                            if g.get("state")!="in" or not _real_team_names(g):continue
                            key=(g.get("id"),g["home"],g["away"])
                            if key in seen:continue
                            seen.add(key);games.append(g)
                        except (ValueError,TypeError,KeyError,OverflowError):continue
                except Exception:continue
        except Exception as exc:
            reason="Abfrage fehlgeschlagen ("+type(exc).__name__+")"
        if games:
            return games,"LiveScore Football: "+str(len(games))+" gueltige Live-Spiele (Teilabdeckung)"
        fallback,info=_espn_live_recovery()
        return fallback,info+" | LiveScore: "+reason
'''
s=s[:start]+replacement+s[end:]

# The public ESPN provider is already used by the main game calendar;
# extend recovery coverage across several continents without a massive
# full-bouquet/network scan.
needle='def selected_live_games():'
addon='''def _real_team_names(g):
    if not isinstance(g,dict):return False
    names=[g.get("home"),g.get("away")]
    for name in names:
        if not isinstance(name,str) or len(name.strip())<2:
            return False
        if name.strip().lower() in ("?","unknown","none","null","tbd","-", "home", "away"):
            return False
    if names[0].strip().casefold()==names[1].strip().casefold():
        return False
    return True

def _espn_live_recovery():
    """Fallback to independent ESPN scores; only real, live fixtures."""
    # 27 major competitions: transparent partial-world coverage.
    codes=("eng.1","esp.1","ita.1","ger.1","fra.1","por.1","ned.1",
           "sui.1","bel.1","tur.1","sco.1","aut.1","gre.1","eng.2",
           "uefa.champions","uefa.europa","uefa.europa.conf",
           "bra.1","arg.1","usa.1","mex.1","ksa.1","jpn.1",
           "aus.1","rsa.1","conmebol.libertadores","afc.champions")
    from concurrent.futures import ThreadPoolExecutor,as_completed
    today=datetime.now().strftime("%Y%m%d")
    games=[];seen=set();ok=0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures=[pool.submit(get_games,code,today) for code in codes]
        for future in as_completed(futures):
            try:
                data=future.result();ok+=1
            except Exception:continue
            for g in data:
                if g.get("state")!="in" or not _real_team_names(g):continue
                key=(g.get("league"),g.get("id"))
                if key in seen:continue
                seen.add(key);games.append(g)
    return games,"ESPN Live: %d/%d Wettbewerbe erreichbar (keine weltweite Vollabdeckung)"%(ok,len(codes))

'''
replace_once(needle,addon+needle)

# Pass actual provider label to the screen: previously it always displayed
# selected source even when a fallback provider supplied the match data.
replace_once('''            games,info=selected_live_games()
            self.result=(games,None)
        except Exception as e:self.result=([],SOURCE_NAMES.get(ACTIVE_SOURCE,"Quelle")+": "+str(e)[:75])''',
'''            games,info=selected_live_games()
            self.result=(games,None,info)
        except Exception as e:self.result=([],SOURCE_NAMES.get(ACTIVE_SOURCE,"Quelle")+": "+str(e)[:75],"")''')
replace_once('''        self.games,error=self.result;self.result=None
        if error:self["menu"].setList(["Fehler: "+error]);return
        self["menu"].setList([game_line(g) for g in self.games] or ["Derzeit keine laufenden Spiele in den erfassten Ligen."])
        self["hint"].setText("%d Live | %s | BLAU: Laden"%(len(self.games),SOURCE_NAMES.get(ACTIVE_SOURCE,"?")))''',
'''        self.games,error,info=self.result;self.result=None
        if error:
            self["menu"].setList(["Fehler: "+error])
            self["hint"].setText("Keine Live-Daten | BLAU: erneut laden")
            return
        self.games=[g for g in self.games if g.get("state")=="in" and _real_team_names(g)]
        self["menu"].setList([game_line(g) for g in self.games] or ["Derzeit keine bestaetigten Live-Spiele in den erfassten Wettbewerben."])
        self["hint"].setText(("%d Live | %s | BLAU: Laden"%(len(self.games),info))[:165])''')
# "Worldwide" is false advertising for limited ESPN coverage.
replace_once('self.setup("LIVE | WELTWEIT",','self.setup("LIVE | FUSSBALL",')

count=s.count('6.13.7')
if count<1:raise SystemExit('Expected version marker absent')
s=s.replace('6.13.7','6.13.8')
path.write_text(s,encoding='utf-8')
(ROOT/'source/VERSION').write_text('6.13.8\n')

for name in ('plugin.py','fixture_match.py','liveonsat_parser.py'):
    code=(DEST/name).read_text(encoding='utf-8')
    compile(code,name,'exec')

# Real parser and screen regression tests without needing Enigma2 runtime.
tree=ast.parse(s)
func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_real_team_names')
module=ast.Module(body=[func],type_ignores=[])
ns={}
exec(compile(module,'_real_team_names','exec'),ns)
valid=ns['_real_team_names']
assert valid({'home':'Leeds United','away':'Manchester United'})
for game in ({'home':'?','away':'?'},{'home':None,'away':'Manchester United'},
             {'home':'Leeds','away':'Leeds'},{'home':'unknown','away':'Manchester United'}):
    assert not valid(game),game
assert 'self.result=(games,None,info)' in s
assert 'fallback,info=_espn_live_recovery()' in s
assert 'LIVE | FUSSBALL' in s

subprocess.run(['python3','scripts/build_ipk.py'],cwd=ROOT,check=True)
print('6.13.8: blocked phantom ?-? games and enabled verified ESPN fallback')
