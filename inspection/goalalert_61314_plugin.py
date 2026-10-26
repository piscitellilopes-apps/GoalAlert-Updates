# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import re
import threading
import urllib.request
import os
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from enigma import eTimer, ePicLoad, eServiceReference
from Components.Pixmap import Pixmap
import subprocess
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.Label import Label
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Components.config import config, ConfigSubsection, ConfigYesNo, ConfigSelection, configfile
from . import goalalert_updater as _goalalert_updates

LEAGUE_SECTIONS=[('TOP 10 EUROPA', [('Premier League', 'eng.1'), ('La Liga', 'esp.1'), ('Serie A', 'ita.1'), ('Bundesliga Deutschland', 'ger.1'), ('Ligue 1', 'fra.1'), ('Primeira Liga Portugal', 'por.1'), ('Eredivisie', 'ned.1'), ('Super League Schweiz', 'sui.1'), ('Pro League Belgien', 'bel.1'), ('Süper Lig Türkei', 'tur.1')]), ('EUROPAPOKALE', [('Champions League', 'uefa.champions'), ('Europa League', 'uefa.europa'), ('Conference League', 'uefa.europa.conf'), ('Champions-League-Qualifikation', 'uefa.champions_qual'), ('Europa-League-Qualifikation', 'uefa.europa_qual'), ('Conference-League-Qualifikation', 'uefa.europa.conf_qual'), ('UEFA Super Cup', 'uefa.super_cup'), ('UEFA Nations League', 'uefa.nations'), ('UEFA Frauen Champions League', 'uefa.wchampions')]), ('WEITERE EUROPA LIGEN', [('Challenge League Schweiz', 'sui.2'), ('Schweizer Cup (sofern Daten vorhanden)', 'sui.cup'), ('2. Bundesliga Deutschland', 'ger.2'), ('Championship England', 'eng.2'), ('League One England', 'eng.3'), ('Segunda Division Spanien', 'esp.2'), ('Serie B Italien', 'ita.2'), ('Ligue 2 Frankreich', 'fra.2'), ('2. Liga Niederlande', 'ned.2'), ('Premiership Schottland', 'sco.1'), ('Championship Schottland', 'sco.2'), ('Bundesliga Österreich', 'aut.1'), ('Super League Griechenland', 'gre.1'), ('Superliga Dänemark', 'den.1'), ('Eliteserien Norwegen', 'nor.1'), ('Allsvenskan Schweden', 'swe.1'), ('Liga Zypern', 'cyp.1'), ('Premier Division Irland', 'irl.1'), ('Premier League Russland', 'rus.1')]), ('NATIONALE POKALE EUROPA', [('FA Cup England', 'eng.fa'), ('League Cup England', 'eng.league_cup'), ('Copa del Rey Spanien', 'esp.copa_del_rey'), ('DFB Pokal', 'ger.dfb_pokal'), ('Coppa Italia', 'ita.coppa_italia'), ('Coupe de France', 'fra.coupe_de_france'), ('KNVB Pokal', 'ned.cup'), ('Taca de Portugal', 'por.taca.portugal'), ('Scottish Cup', 'sco.tennents')]), ('SÜDAMERIKA', [('Brasilien Serie A', 'bra.1'), ('Brasilien Serie B', 'bra.2'), ('Argentinien Primera', 'arg.1'), ('Chile Primera', 'chi.1'), ('Kolumbien Primera A', 'col.1'), ('Uruguay Primera', 'uru.1'), ('Paraguay Primera', 'par.1'), ('Peru Liga 1', 'per.1'), ('Ecuador LigaPro', 'ecu.1'), ('Bolivien Primera', 'bol.1'), ('Venezuela Primera', 'ven.1'), ('Copa Libertadores', 'conmebol.libertadores'), ('Copa Sudamericana', 'conmebol.sudamericana'), ('Copa Argentina', 'arg.copa'), ('Copa do Brasil', 'bra.copa_do_brazil')]), ('NORDAMERIKA', [('MLS USA', 'usa.1'), ('Liga MX Mexiko', 'mex.1'), ('Liga Expansion Mexiko', 'mex.2'), ('USL Championship', 'usa.usl.1'), ('U.S. Open Cup', 'usa.open'), ('CONCACAF Champions Cup', 'concacaf.champions'), ('Leagues Cup', 'concacaf.leagues.cup')]), ('ASIEN & OZEANIEN', [('Saudi Pro League', 'ksa.1'), ('Japan J League', 'jpn.1'), ('China Super League', 'chn.1'), ('Indien Super League', 'ind.1'), ('Thailand Thai League', 'tha.1'), ('Malaysia Super League', 'mys.1'), ('Indonesien Liga 1', 'idn.1'), ('Singapur Premier League', 'sgp.1'), ('Australien A-League', 'aus.1'), ('AFC Champions League Elite', 'afc.champions'), ('AFC Champions League 2', 'afc.cup')]), ('AFRIKA', [('Südafrika Premiership', 'rsa.1'), ('Nigeria Premier', 'nga.1'), ('Ghana Premier', 'gha.1'), ('CAF Champions League', 'caf.champions'), ('CAF Confederation Cup', 'caf.confed'), ('Afrika-Cup', 'caf.nations')]), ('NATIONALTEAMS & JUNIOREN', [('WM', 'fifa.world'), ('WM Qualifikation Europa', 'fifa.worldq.uefa'), ('WM Qualifikation Südamerika', 'fifa.worldq.conmebol'), ('WM Qualifikation Afrika', 'fifa.worldq.caf'), ('WM Qualifikation Asien', 'fifa.worldq.afc'), ('WM Qualifikation Nordamerika', 'fifa.worldq.concacaf'), ('EURO', 'uefa.euro'), ('EURO Qualifikation', 'uefa.euroq'), ('U21 EURO', 'uefa.euro_u21'), ('U17 WM', 'fifa.world.u17'), ('U20 WM', 'fifa.world.u20'), ('Internationale Freundschaftsspiele', 'fifa.friendly'), ('Clubfreundschaftsspiele', 'club.friendly')])]
LEAGUES=[item for section,items in LEAGUE_SECTIONS for item in items]
DEFAULT_LEAGUES=set([code for name,code in LEAGUE_SECTIONS[0][1]]+["uefa.champions","uefa.europa","uefa.europa.conf"])
if not hasattr(config.plugins,"goalalert32"):
    config.plugins.goalalert32=ConfigSubsection()
    config.plugins.goalalert32.enabled=ConfigYesNo(default=True)
    config.plugins.goalalert32.duration=ConfigSelection(default="6",choices=[("4","4"),("6","6"),("10","10")])
    config.plugins.goalalert32.league=ConfigSelection(default="sui.1",choices=[(code,name) for name,code in LEAGUES])
    config.plugins.goalalert32.popup_size=ConfigSelection(default="compact", choices=[("mini","Mini"),("compact","Kompakt"),("normal","Normal")])
if not hasattr(config.plugins.goalalert32,"cheer_style"):
    config.plugins.goalalert32.cheer_style=ConfigSelection(default="classic",
        choices=[("classic","Klassisch"),("stadium","Stadion-Echo"),
                 ("double","Doppeljubel"),("short","Kurzer Tor-Ruf")])
# Favoriten bleiben in einer separaten JSON-Datei gespeichert.
FAVORITES_FILE="/etc/enigma2/goalalert_favorites.json"
favorites={}
try:
    with open(FAVORITES_FILE,"r") as f:
        favorites=json.load(f)
    if not isinstance(favorites,dict): favorites={}
except Exception:
    favorites={}
def save_favorites():
    try:
        with open(FAVORITES_FILE,"w") as f: json.dump(favorites,f)
    except Exception: pass

def _espn_team_crest_url(team):
    """Use provider crest first, ESPN team logo URL when absent."""
    if not isinstance(team,dict):return ''
    candidate=team.get('logo') or next((x.get('href') for x in team.get('logos',[]) if isinstance(x,dict) and x.get('href')), '')
    team_id=str(team.get('id') or '')
    if team_id.isdigit() and len(team_id)<=10:
        return 'https://a.espncdn.com/i/teamlogos/soccer/500/%s.png'%team_id
    if candidate and str(candidate).startswith('https://'):return candidate
    return ''

def get_games(league,date):
    url="https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s" %(league,date)
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GoalAlertTV/3.2"})
    with urllib.request.urlopen(request,timeout=9) as response:
        obj=json.load(response)
    games=[]
    for event in obj.get("events",[]):
        try:
            competition=event["competitions"][0]
            teams=competition["competitors"]
            home=next(t for t in teams if t.get("homeAway")=="home")
            away=next(t for t in teams if t.get("homeAway")=="away")
            status_obj=event.get("status",{})
            status=status_obj.get("type",{}).get("state","pre")
            display_clock=status_obj.get("displayClock") or status_obj.get("type",{}).get("shortDetail","")
            minute=None
            import re
            match=re.search(r"(\d{1,3})(?:\+\d+)?(?:['’]|\s*min)",str(display_clock),re.I)
            if match:minute=int(match.group(1))
            elif status=="in":
                match=re.search(r"^\s*(\d{1,3})",str(display_clock))
                if match:minute=int(match.group(1))
            home_name=home.get("team",{}).get("shortDisplayName") or home.get("team",{}).get("displayName","Heim")
            away_name=away.get("team",{}).get("shortDisplayName") or away.get("team",{}).get("displayName","Gast")
            score=lambda x:int(x.get("score") or 0)
            games.append({"id":str(event["id"]),"home":home_name,"away":away_name,"hs":score(home),"as":score(away),"state":status,"date":event.get("date",""),"league":league,"league_name":next((name for name,code in LEAGUES if code==league),league),
                          "country":"","minute":minute,"home_logo":_espn_team_crest_url(home.get("team",{})),
                          "away_logo":_espn_team_crest_url(away.get("team",{})),"provider":"ESPN", "home_team_id":str(home.get("team",{}).get("id") or ""),
                          "away_team_id":str(away.get("team",{}).get("id") or ""),
                          "market_odds":_espn_1x2(competition.get("odds") or [])})
        except Exception: continue
    return games


# ESPN schedule is the same free source as the working date view.
# Cache requests across the date view, live screen and background monitor.
ESPN_CACHE={}
ESPN_CACHE_LOCK=threading.RLock()
ESPN_CACHE_TTL=10
_ESPN_ORIGINAL_GET_GAMES=get_games
def get_games(league,date):
    key=(league,date)
    with ESPN_CACHE_LOCK:
        cached=ESPN_CACHE.get(key)
        if cached and time.time()-cached[0]<ESPN_CACHE_TTL:return [dict(x) for x in cached[1]]
    try:
        games=_ESPN_ORIGINAL_GET_GAMES(league,date)
        with ESPN_CACHE_LOCK:ESPN_CACHE[key]=(time.time(),games)
        return [dict(x) for x in games]
    except Exception:
        if cached:return [dict(x) for x in cached[1]]
        raise

def espn_all_games(day=None):
    day=day or datetime.now().strftime("%Y%m%d")
    games=[]
    # Fetch concurrently, rather than sequentially blocking on each league.
    with ThreadPoolExecutor(max_workers=18) as pool:
        futures=[pool.submit(get_games,code,day) for name,code in LEAGUES]
        for future in as_completed(futures):
            try:games.extend(future.result())
            except Exception:pass
    return games

API_SETTINGS="/etc/enigma2/goalalert_api.json"
def api_key():
    try:
        with open(API_SETTINGS) as f:return str(json.load(f).get("key","")).strip()
    except Exception:return ""
CACHE_DIR="/etc/enigma2/goalalert_cache"
API_LOCK=threading.RLock()
API_PAUSED_UNTIL=0
try:
    with open("/etc/enigma2/goalalert_api_pause.json") as _f:
        API_PAUSED_UNTIL=float(json.load(_f).get("until",0))
except Exception:pass
def _pause_api(now):
    global API_PAUSED_UNTIL
    # Avoid excessive requests after limit. Pause until tomorrow (max 24h).
    API_PAUSED_UNTIL=now+24*3600
    try:
        with open("/etc/enigma2/goalalert_api_pause.json","w") as f:json.dump({"until":API_PAUSED_UNTIL},f)
    except Exception:pass
CACHE_TTLS={"fixtures_live":300,"fixtures_date":21600,"odds":21600,"events":120}

def _cache_path(path,params):
    import hashlib,urllib.parse
    identity=path+"?"+urllib.parse.urlencode(sorted((str(k),str(v)) for k,v in params.items()))
    return os.path.join(CACHE_DIR,hashlib.sha256(identity.encode("utf-8")).hexdigest()+".json")

def _read_cache(filename):
    try:
        with open(filename,"r") as f:data=json.load(f)
        return data if isinstance(data,dict) and isinstance(data.get("response"),list) else None
    except Exception:return None

def api_request(path,params):
    import urllib.parse
    global API_PAUSED_UNTIL
    key=api_key()
    if not key:raise ValueError("API-Schluessel fehlt")
    filename=_cache_path(path,params)
    ttl=(CACHE_TTLS["fixtures_live"] if params.get("live") else CACHE_TTLS["fixtures_date"]) if path=="fixtures" else CACHE_TTLS.get(path,1800)
    with API_LOCK:
        cached=_read_cache(filename)
        now=time.time()
        if cached and now-cached.get("saved",0)<ttl:return cached["response"]
        if now<API_PAUSED_UNTIL:
            if cached:return cached["response"]
            raise ValueError("API-Tageslimit erreicht. Keine gespeicherten Daten vorhanden.")
        url="https://v3.football.api-sports.io/"+path+"?"+urllib.parse.urlencode(params)
        req=urllib.request.Request(url,headers={"x-apisports-key":key,"User-Agent":"GoalAlertTV/5.0"})
        try:
            with urllib.request.urlopen(req,timeout=15) as response:
                data=json.load(response)
            errors=data.get("errors") or {}
            error_text=str(errors).lower()
            if "limit" in error_text or "quota" in error_text or "requests" in error_text:
                _pause_api(now)
                if cached:return cached["response"]
                raise ValueError("API-Tageslimit erreicht; Abfragen pausiert.")
            if errors:raise ValueError(str(errors)[:160])
            result=data.get("response",[])
            if not isinstance(result,list):raise ValueError("Ungueltige API-Antwort")
            try:
                if not os.path.isdir(CACHE_DIR):os.makedirs(CACHE_DIR)
                tmp=filename+".tmp"
                with open(tmp,"w") as f:json.dump({"saved":now,"response":result},f)
                os.replace(tmp,filename)
            except Exception:pass
            return result
        except Exception as e:
            if "429" in str(e):_pause_api(now)
            if cached:return cached["response"]
            raise

def convert_api_game(item):
    f=item.get("fixture",{});t=item.get("teams",{});goals=item.get("goals",{});league=item.get("league",{})
    status=f.get("status",{}).get("short","")
    state="in" if status in ("1H","2H","HT","ET","P","BT","INT","LIVE") else ("post" if status in ("FT","AET","PEN") else "pre")
    return {"id":str(f.get("id","")),"home":t.get("home",{}).get("name","?"),"away":t.get("away",{}).get("name","?"),"hs":goals.get("home") or 0,"as":goals.get("away") or 0,"state":state,"date":f.get("date",""),"league":str(league.get("id","")),"league_name":league.get("name","?"),"country":league.get("country",""),"minute":f.get("status",{}).get("elapsed"),"home_logo":t.get("home",{}).get("logo",""),"away_logo":t.get("away",{}).get("logo",""),
            "home_team_id":str(t.get("home",{}).get("id") or ""),"away_team_id":str(t.get("away",{}).get("id") or "")}

# Match events from ESPN match summaries. These are best-effort public endpoints;
# an absent scorer/assist is explicitly shown as unavailable.
DETAIL_CACHE={}
DETAIL_LOCK=threading.RLock()
def match_events(game):
    key=str(game.get("league",""))+":"+str(game.get("id",""))
    now=time.time()
    with DETAIL_LOCK:
        cached=DETAIL_CACHE.get(key)
        if cached and now-cached[0]<25:return cached[1]
    code=game.get("league","")
    ident=str(game.get("id",""))
    if not code or not ident.isdigit():return []
    from urllib.parse import urlencode
    url="https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?%s"%(code,urlencode({"event":ident}))
    req=urllib.request.Request(url,headers={"User-Agent":"GoalAlertTV/5.4"})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:obj=json.load(response)
        events=[]
        for item in obj.get("scoringPlays",[]) or []:
            clock=item.get("clock",{}) or {}
            minute=clock.get("displayValue") or "?"
            player=(item.get("athletes") or [{}])[0]
            scorer=player.get("displayName") or player.get("athlete",{}).get("displayName") or "Nicht gemeldet"
            events.append({"minute":str(minute),"scorer":scorer,"assist":"Nicht gemeldet","text":item.get("text","")})
        # ESPN soccer summary often lists scoring plays in details, not scoringPlays.
        if not events:
            for play in obj.get("details",[]) or []:
                typ=play.get("type",{}) or {}
                description=(typ.get("text","")+" "+str(play.get("text", ""))).lower()
                if "goal" not in description and "tor" not in description:continue
                clock=play.get("clock",{}) or {}
                scorer=(play.get("athletes") or [{}])[0].get("displayName") or "Nicht gemeldet"
                events.append({"minute":str(clock.get("displayValue") or "?"),"scorer":scorer,"assist":"Nicht gemeldet","text":str(play.get("text", ""))})
        with DETAIL_LOCK:DETAIL_CACHE[key]=(now,events)
        return events
    except Exception:return []

# Optional unofficial match-event provider. Never use LiveOnSat for scoring data.
SOFA_BASE="https://www.sofascore.com/api/v1/"
SOFA_CACHE={}
def sofa_events(game):
    import urllib.parse,unicodedata,re
    def norm(x):
        x=unicodedata.normalize("NFKD",str(x or "")).encode("ascii","ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]","",x)
    key=str(game.get("date", ""))[:10]+":"+norm(game.get("home"))+":"+norm(game.get("away"))
    item=SOFA_CACHE.get(key)
    if item and time.time()-item[0]<40:return item[1]
    def read(url):
        req=urllib.request.Request(url,headers={"User-Agent":"GoalAlertTV/5.5","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=7) as response:return json.load(response)
    try:
        date=str(game.get("date", ""))[:10]
        if len(date)!=10:return []
        data=read(SOFA_BASE+"sport/football/scheduled-events/"+date)
        matches=[]
        for ev in data.get("events",[]):
            h=norm((ev.get("homeTeam") or {}).get("name"))
            a=norm((ev.get("awayTeam") or {}).get("name"))
            home=norm(game.get("home"));away=norm(game.get("away"))
            if len(home)>=4 and len(away)>=4 and ((home in h or h in home) and (away in a or a in away)):
                matches.append(ev)
        if len(matches)!=1:return []  # never attach a different match's scorers
        data=read(SOFA_BASE+"event/"+str(matches[0]["id"])+"/incidents")
        events=[]
        for ev in data.get("incidents",[]):
            if ev.get("incidentType")!="goal":continue
            player=ev.get("player") or {}
            assist=ev.get("assist1") or ev.get("assist") or {}
            if isinstance(assist,dict):assist=assist.get("name") or assist.get("shortName") or "Nicht gemeldet"
            events.append({"minute":str(ev.get("time") or "?")+ ("+"+str(ev["addedTime"]) if ev.get("addedTime") else ""),
                "scorer":ev.get("playerName") or player.get("name") or "Nicht gemeldet",
                "assist":str(assist) if assist else "Nicht gemeldet", "text":"Sofascore (inoffiziell)",
                'side':('home' if ev.get('isHome') is True else ('away' if ev.get('isHome') is False else None))})
        SOFA_CACHE[key]=(time.time(),events)
        return events
    except Exception:return []

def detailed_events(game):
    # A Sofascore fixture already carries the correct event ID. Never
    # rematch by team names (ambiguous for youth/women/reserve sides).
    if game.get("provider")=="SofaScore":
        ident=str(game.get("id") or "")
        if ident.isdigit():
            try:
                payload=source_json(SOFA_BASE+"event/"+ident+"/incidents")
                events=[]
                for ev in payload.get("incidents",[]):
                    if ev.get("incidentType")!="goal":continue
                    player=ev.get("player") or {}
                    assist=ev.get("assist1") or ev.get("assist") or {}
                    if isinstance(assist,dict):assist=assist.get("name") or assist.get("shortName") or "Nicht gemeldet"
                    minute=str(ev.get("time") or "?")
                    if ev.get("addedTime"):minute+="+"+str(ev["addedTime"])
                    events.append({"minute":minute,"scorer":ev.get("playerName") or player.get("name") or "Nicht gemeldet", "assist":str(assist or "Nicht gemeldet"),"text":"SofaScore",
                                   'side':('home' if ev.get('isHome') is True else ('away' if ev.get('isHome') is False else None))})
                return events
            except Exception:return []
        return []
    events=sofa_events(game)
    return events if events else match_events(game)


# 6.5: Provider-aware goal extraction. Source errors are NOT mistaken for goals.
def _team_identity(value):
    # Provider team IDs are meaningful only inside that provider.
    if isinstance(value,dict):
        for field in ('id','teamId','teamID','team_id'):
            if value.get(field) not in (None,''):
                return str(value[field])
        if isinstance(value.get('team'),dict):
            return _team_identity(value['team'])
        return ''
    return str(value) if value not in (None,'') else ''


def _event_team_side(event,game):
    # Explicit side first, then provider-specific team ID, never scorer name guesses.
    for obj in (event,event.get('team'),event.get('competitor'),event.get('scoringTeam')):
        if not isinstance(obj,dict):continue
        val=obj.get('homeAway') or obj.get('side')
        if val in ('home','away'):return val
        if obj.get('isHome') is True:return 'home'
        if obj.get('isHome') is False:return 'away'
    home_id=str(game.get('home_team_id') or '')
    away_id=str(game.get('away_team_id') or '')
    if home_id and away_id and home_id!=away_id:
        for field in ('team','teamId','teamID','team_id','competitor','scoringTeam','scoringTeamId'):
            tid=_team_identity(event.get(field))
            if tid and tid==home_id:return 'home'
            if tid and tid==away_id:return 'away'
        # Some ESPN scoring plays store the team only on the scoring participant.
        for p in event.get('participants') or event.get('athletes') or []:
            if not isinstance(p,dict):continue
            tid=_team_identity(p.get('team')) or _team_identity((p.get('athlete') or {}).get('team') if isinstance(p.get('athlete'),dict) else None)
            if tid and tid==home_id:return 'home'
            if tid and tid==away_id:return 'away'
    return None


def _extract_api_football_goals(rows,game=None):
    result=[]
    for ev in rows or []:
        if str(ev.get('type') or '').lower()!='goal':continue
        if 'missed' in str(ev.get('detail') or '').lower():continue
        t=ev.get('time') or {};p=ev.get('player') or {};a=ev.get('assist') or {}
        minute=str(t.get('elapsed') or '?')
        if t.get('extra'):minute+='+'+str(t['extra'])
        scorer=p.get('name') or 'Nicht gemeldet'
        if 'own' in str(ev.get('detail') or '').lower():scorer+=' (Eigentor)'
        side=_event_team_side(ev,game or {})
        result.append({'minute':minute,'scorer':scorer,'assist':a.get('name') or 'Nicht gemeldet','text':'API-Football','side':side})
    return result


def _normalised_goal_minute(value):
    # ESPN uses both "10:00" and "10'" for the same minute.
    import re
    m=re.search(r"(\d{1,3})(?:\s*\+\s*(\d{1,2}))?",str(value or ""))
    return (int(m.group(1)),int(m.group(2) or 0)) if m else (999,0)


def _goal_player_key(value):
    import re,unicodedata
    name=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode('ascii').lower()
    words=re.findall(r'[a-z0-9]+',name)
    if words and words[-1] in ('own','goal','eigentor'):words=words[:-1]
    return words[-1] if words else ''


def _deduplicate_goals(events):
    # The same ESPN incident may occur in scoringPlays/keyEvents/details with
    # different provider IDs, extra clock formatting or full/short player names.
    unique=[];seen=set()
    known={( _normalised_goal_minute(e.get('minute')), _goal_player_key(e.get('scorer')))
           for e in events or [] if e.get('side') in ('home','away')}
    for e in events or []:
        if (e.get('side') not in ('home','away') and
           (_normalised_goal_minute(e.get('minute')),_goal_player_key(e.get('scorer'))) in known):
            continue
        minute=_normalised_goal_minute(e.get('minute'))
        scorer=_goal_player_key(e.get('scorer'))
        side=e.get('side') if e.get('side') in ('home','away') else 'unknown'
        kind='own' if 'eigentor' in str(e.get('scorer') or '').lower() else 'normal'
        key=(minute,scorer,side,kind)
        if key in seen:continue
        seen.add(key)
        unique.append(e)
    return unique


def _goals_from_espn(obj,game=None):
    # Collect and identify scoring events without assigning unknowns to HOME.
    items=[];seen=set();g=dict(game or {})
    if not g.get('home_team_id') or not g.get('away_team_id'):
        competitions=(obj.get('header') or {}).get('competitions') or []
        for comp in competitions:
            for team in comp.get('competitors') or []:
                if not isinstance(team,dict):continue
                side=team.get('homeAway')
                if side in ('home','away'):
                    g[side+'_team_id']=_team_identity(team.get('team') or team)
    containers=[obj,obj.get('header') or {},obj.get('boxscore') or {}]
    competitions=(obj.get('header') or {}).get('competitions') or []
    containers.extend(c for c in competitions if isinstance(c,dict))
    for parent in containers:
        if not isinstance(parent,dict):continue
        for key in ('scoringPlays','keyEvents','details','plays','scoringSummary'):
            group=parent.get(key) or []
            if isinstance(group,dict):group=group.get('plays') or group.get('items') or []
            if not isinstance(group,list):continue
            for ev in group:
                if not isinstance(ev,dict):continue
                typ=ev.get('type') or ev.get('alternativeType') or {}
                if isinstance(typ,dict):typ=typ.get('text') or typ.get('name') or typ.get('abbreviation') or ''
                else:typ=str(typ)
                description=' '.join(str(ev.get(k) or '') for k in ('text','shortText','description'))
                label=typ.lower()
                if not (ev.get('scoringPlay') is True or ev.get('isScore') is True or
                        ('goal' in label and 'goal kick' not in label and 'goalkeeper' not in label) or
                        'penalty scored' in description.lower()):continue
                if 'missed' in (typ+description).lower() or 'disallowed' in description.lower():continue
                clock=ev.get('clock') or {}
                if not isinstance(clock,dict):clock={'displayValue':str(clock)}
                minute=str(clock.get('displayValue') or ev.get('minute') or '?')
                athletes=ev.get('athletes') or ev.get('participants') or []
                first=athletes[0] if athletes and isinstance(athletes[0],dict) else {}
                player=first.get('athlete') if isinstance(first.get('athlete'),dict) else first
                scorer=player.get('displayName') or player.get('name') or ev.get('scorer') or 'Nicht gemeldet'
                assist='Nicht gemeldet'
                if len(athletes)>1 and isinstance(athletes[1],dict):
                    helper=athletes[1].get('athlete') or athletes[1]
                    if isinstance(helper,dict):assist=helper.get('displayName') or helper.get('name') or assist
                side=_event_team_side(ev,g)
                # Same ESPN goal can appear in scoringPlays, keyEvents and details.
                dedupe=(str(ev.get('id') or ''),minute,str(scorer).lower().strip(),side)
                if dedupe in seen:continue
                seen.add(dedupe)
                items.append({'minute':minute,'scorer':scorer,'assist':assist,'text':description,'side':side})
    return _deduplicate_goals(items)

def _espn_goals(game):
    code=str(game.get("league") or "");ident=str(game.get("id") or "")
    if not code or not ident.isdigit():return []
    from urllib.parse import urlencode
    req=urllib.request.Request("https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?%s"%(code,urlencode({"event":ident})),headers={"User-Agent":"Mozilla/5.0 GoalAlertTV/6.5"})
    with urllib.request.urlopen(req,timeout=12) as r:data=json.load(r)
    # Refuse a summary that identifies another fixture.
    header=data.get('header') or {}
    fixture_ids=[str(header.get('id') or '')]
    fixture_ids += [str(c.get('id') or '') for c in header.get('competitions') or [] if isinstance(c,dict)]
    known=[value for value in fixture_ids if value]
    if known and ident not in known:
        raise ValueError('ESPN hat ein anderes Spiel zurueckgegeben')
    header_comp=(header.get('competitions') or [{}])[0]
    teams={str(x.get('homeAway')):str(_team_identity(x.get('team') or x))
           for x in header_comp.get('competitors') or [] if isinstance(x,dict)}
    for side in ('home','away'):
        expected=str(game.get(side+'_team_id') or '')
        if expected and teams.get(side) and expected!=teams[side]:
            raise ValueError('ESPN-Team-ID stimmt nicht zur Begegnung')
    return _deduplicate_goals(_goals_from_espn(data,game))

def _football_fixture_for_game(game):
    # Return the fixture AND its own provider-specific team IDs.
    if game.get('provider')=='API-Football' and str(game.get('id') or '').isdigit():
        return {'fixture_id':str(game['id']),
                'home_team_id':str(game.get('home_team_id') or ''),
                'away_team_id':str(game.get('away_team_id') or '')}
    league_id=TIP_API_IDS.get(game.get('league'))
    if not league_id:return None
    date=str(game.get('date') or '')[:10]
    if len(date)!=10:return None
    rows=api_request('fixtures',{'date':date})
    a=_norm_team(game.get('home'));b=_norm_team(game.get('away'))
    def similar(x,y):return bool(x and y and (x==y or (len(x)>5 and x in y) or (len(y)>5 and y in x)))
    matches=[]
    for item in rows:
        if int((item.get('league') or {}).get('id') or -1)!=league_id:continue
        teams=item.get('teams') or {}
        if similar(a,_norm_team((teams.get('home') or {}).get('name'))) and similar(b,_norm_team((teams.get('away') or {}).get('name'))):
            fixture_id=str((item.get('fixture') or {}).get('id') or '')
            if fixture_id:
                matches.append({'fixture_id':fixture_id,
                                'home_team_id':_team_identity(teams.get('home')),
                                'away_team_id':_team_identity(teams.get('away'))})
    return matches[0] if len(matches)==1 else None

_OLD_DETAILED_EVENTS=detailed_events
EVENT_FETCH_STATUS={}
def detailed_events(game):
    # ESPN and SofaScore have real event IDs; mixing their incident data risks
    # crediting a scorer from a DIFFERENT match. Never fuzzy-rematch an ESPN game.
    key=str(game.get('league'))+':'+str(game.get('id'))
    provider=str(game.get('provider') or 'ESPN')
    if provider in ('ESPN','GnomeFootball'):
        try:
            goals=_deduplicate_goals(_espn_goals(game))
            EVENT_FETCH_STATUS[key]='ESPN: %d eindeutige Tore'%len(goals)
            return goals
        except Exception as exc:
            EVENT_FETCH_STATUS[key]='ESPN: '+str(exc)[:90]
            return []
    if provider=='API-Football':
        try:
            fixture=_football_fixture_for_game(game)
            if not fixture or not fixture['home_team_id'] or not fixture['away_team_id']:
                EVENT_FETCH_STATUS[key]='API: Spiel-ID/Team-IDs nicht eindeutig'
                return []
            result=_deduplicate_goals(_extract_api_football_goals(
                api_request('fixtures/events',{'fixture':fixture['fixture_id']}), fixture))
            EVENT_FETCH_STATUS[key]='API-Football: %d Tore'%len(result)
            return result
        except Exception as exc:
            EVENT_FETCH_STATUS[key]='API-Football: '+str(exc)[:90]
            return []
    if provider=='SofaScore':
        try:
            result=_deduplicate_goals(_OLD_DETAILED_EVENTS(game))
            EVENT_FETCH_STATUS[key]='SofaScore: %d Tore'%len(result)
            return result
        except Exception as exc:
            EVENT_FETCH_STATUS[key]='SofaScore: '+str(exc)[:90]
            return []
    EVENT_FETCH_STATUS[key]='Quelle ohne eindeutige Spiel-ID'
    return []

def kickoff_ch(value):
    if not value:return "--:--"
    try:
        from datetime import timezone
        dt=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            return dt.astimezone(ZoneInfo("Europe/Zurich")).strftime("%d.%m. %H:%M")
        except Exception:
            return datetime.fromtimestamp(dt.timestamp()).strftime("%d.%m. %H:%M")
    except Exception:return "--:--"

def game_line(g):
    if g.get("state")=="in":
        when=(str(g.get("minute"))+"' LIVE") if g.get("minute") is not None else "LIVE"
    elif g.get("state")=="post":when="ENDE"
    else:when=kickoff_ch(g.get("date"))
    score=("  %s:%s"%(g.get("hs",0),g.get("as",0))) if g.get("state")!="pre" else ""
    return ("★" if str(g.get("id")) in favorites else "☆")+" "+when+" | "+g.get("home","?")+" - "+g.get("away","?")+score


# Free fallback: TheSportsDB public test API. Data may be delayed/incomplete.
SPORTSDB_BASE="https://www.thesportsdb.com/api/v1/json/123/eventsday.php"
def sportsdb_games(day):
    import urllib.parse
    req=urllib.request.Request(SPORTSDB_BASE+"?"+urllib.parse.urlencode({"d":day,"s":"Soccer"}),
                               headers={"User-Agent":"GoalAlertTV/5.1"})
    with urllib.request.urlopen(req,timeout=12) as r: data=json.load(r)
    games=[]
    for e in data.get("events") or []:
        try:
            status=(e.get("strStatus") or "").lower()
            state="post" if status in ("match finished","ft","finished") else ("in" if status in ("live","1h","2h","ht") else "pre")
            dt=(e.get("strTimestamp") or (e.get("dateEvent","")+"T"+(e.get("strTime") or "00:00:00")+"Z"))
            games.append({"id":"tsdb-"+str(e.get("idEvent","")),"home":e.get("strHomeTeam") or "?",
              "away":e.get("strAwayTeam") or "?","hs":int(e.get("intHomeScore") or 0),
              "as":int(e.get("intAwayScore") or 0),"state":state,"date":dt,
              "league":str(e.get("idLeague") or ""),"league_name":e.get("strLeague") or "Fussball",
              "country":"","minute":None,"home_logo":e.get("strHomeTeamBadge") or "",
              "away_logo":e.get("strAwayTeamBadge") or "","tv_station":e.get("strTVStation") or "",
              "provider":"TheSportsDB"})
        except Exception:continue
    return games

# LiveOnSat is an independent schedule site, not an official API.
# Extract public schedule text conservatively; never infer a channel from a near-match.
LIVEONSAT_URL="https://www.liveonsat.com/2day.php"
LIVEONSAT_CACHE="/etc/enigma2/goalalert_liveonsat.json"
def _norm_team(value):
    import re,unicodedata
    s=unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+"," ",s).strip()
def liveonsat_channels(home,away):
    import re,html
    from html.parser import HTMLParser
    class Lines(HTMLParser):
        def __init__(self):super(Lines,self).__init__();self.parts=[]
        def handle_data(self,data):
            x=html.unescape(data).strip()
            if x:self.parts.append(x)
    cache={}
    try:
        with open(LIVEONSAT_CACHE) as f:cache=json.load(f)
    except Exception:pass
    now=time.time()
    lines=cache.get("lines",[])
    # Limit requests to at most one every six hours.
    if now-float(cache.get("saved",0))>21600:
        try:
            req=urllib.request.Request(LIVEONSAT_URL,headers={"User-Agent":"Mozilla/5.0 GoalAlertTV/5.1"})
            with urllib.request.urlopen(req,timeout=12) as r:
                raw=r.read(900000).decode("utf-8","replace")
            parser=Lines();parser.feed(raw);lines=parser.parts
            try:
                with open(LIVEONSAT_CACHE+".tmp","w") as f:json.dump({"saved":now,"lines":lines},f)
                os.rename(LIVEONSAT_CACHE+".tmp",LIVEONSAT_CACHE)
            except Exception:pass
        except Exception:pass
    a,b=_norm_team(home),_norm_team(away)
    if not a or not b:return [],"Kein eindeutiger Spielname"
    for i,line in enumerate(lines):
        candidate=_norm_team(line)
        if (" v " in " "+candidate+" " or " vs " in " "+candidate+" ") and a in candidate and b in candidate:
            # Never guess: only take immediate listed broadcast lines.
            result=[]
            for entry in lines[i+1:i+36]:
                entry=entry.strip()
                if re.search(r"\s+v(?:s)?\s+",entry,re.I) or entry.startswith("ST:"):break
                if re.search(r"\b(HD|UHD|Sport|Sports|TV|Sky|DAZN|beIN|Canal|SRF|RTS|RAI|ARD|ZDF|ESPN|Arena|Blue)\b",entry,re.I):
                    if entry not in result:result.append(entry)
            return result[:22],"LiveOnSat (Angaben ohne Gewaehr)"
    return [],"Keine eindeutige LiveOnSat-Zuordnung"

LIVEONSAT_SCHEDULE_CACHE="/etc/enigma2/goalalert_liveonsat_schedule_v6128.json"
def _fixture_local_day(game):
    """Use the selected fixture date, not today's guide. Convert UTC to box local time."""
    raw=str((game or {}).get('date') or '').strip()
    try:
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
        if dt.tzinfo is not None:
            dt=dt.astimezone()
        return dt.strftime('%Y-%m-%d')
    except (ValueError,TypeError,OverflowError):
        return datetime.now().strftime('%Y-%m-%d')

def liveonsat_schedule(day=None):
    """Retain every match from today's full programme, including started games.

    Some LiveOnSat pages are rolling/partial. Combine their fixtures and the
    previous same-day cache rather than replacing the entire day from one page.
    Do not label an event as LIVE merely from its scheduled kick-off time.
    """
    from .liveonsat_parser import parse_schedule, merge_day_schedules
    from datetime import timedelta
    cache={}
    try:
        with open(LIVEONSAT_SCHEDULE_CACHE) as f:cache=json.load(f)
    except Exception:pass
    from datetime import date as _date
    today=datetime.now().strftime('%Y-%m-%d')
    try:
        requested=_date.fromisoformat(str(day or today)).isoformat()
    except (ValueError,TypeError):
        requested=today
    overnight=(requested==today and datetime.now().hour<3)
    cache_file=(LIVEONSAT_SCHEDULE_CACHE if requested==today else
        LIVEONSAT_SCHEDULE_CACHE.replace('.json','_'+requested+'.json'))
    if cache_file!=LIVEONSAT_SCHEDULE_CACHE:
        try:
            with open(cache_file) as f:cache=json.load(f)
        except Exception:cache={}
    if (cache.get('date')==requested and time.time()-float(cache.get('saved',0))<600
            and cache.get('games')):
        return cache['games'],'LiveOnSat: %s (%d Begegnungen)'%(requested,len(cache['games']))
    days_apart=abs((_date.fromisoformat(requested)-_date.fromisoformat(today)).days)
    urls=(['https://www.liveonsat.com/2day.php'] if days_apart<=1 else [])
    urls.append('https://m.liveonsat.com/daily-'+requested)
    if overnight:
        urls.append('https://m.liveonsat.com/daily-'+(datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d'))
    source_lists=[];errors=[];network_sources=0
    for url in urls:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0',
                'Accept-Language':'en-US,en;q=0.8'})
            with urllib.request.urlopen(req,timeout=8) as response:
                raw=response.read(4_000_000)
            games=parse_schedule(raw)
            if not games:raise ValueError('Keine Begegnungen aus HTML')
            source_lists.append(games)
            network_sources+=1
        except Exception as exc:errors.append(type(exc).__name__)
    if cache.get('games') and cache.get('date')==requested:
        source_lists.append(cache['games'])
    games=merge_day_schedules(source_lists,requested,keep_overnight=overnight)
    if games:
        # A failed refresh must not erase previously known transmissions.
        if network_sources>0:
            payload={'saved':time.time(),'date':requested,'games':games}
            try:
                with open(cache_file+'.tmp','w') as f:json.dump(payload,f)
                os.rename(cache_file+'.tmp',cache_file)
            except Exception:pass
        info='LiveOnSat: %s | %d Begegnungen'%(requested,len(games))
        if errors:info+=' | Quellen teilweise nicht erreichbar'
        return games,info
    raise ValueError('LiveOnSat: keine TV-Daten fuer %s (%s)'%(requested,','.join(errors) or 'keine Spiele'))

def _goalalert_ui_scale():
    """Scale overlays to the skin desktop (720p or 1080p), not video output pixels."""
    try:
        from enigma import getDesktop
        dims=getDesktop(0).size()
        sw=float(dims.width());sh=float(dims.height())
        # Never make a skin larger than the on-screen desktop.
        return max(1.0,min(1.5,sw/1280.0,sh/720.0))
    except Exception:
        return 1.0

def _goalalert_hd_skin(markup):
    """Scale integer geometry and fonts for FHD skins; preserve positions with center."""
    scale=_goalalert_ui_scale()
    if scale<1.08:return markup
    # Match every 720p theme sprite with its FHD-sized counterpart.
    import re
    markup=re.sub(r"(ga_(?:menu|home|detail|tip|popup_goal(?:_mini|_normal)?|popup_scorer(?:_mini|_normal)?|live_glass))\.png",r"\1_fhd.png",markup)
    def dim(value):return str(max(1,int(round(int(value)*scale))))
    def pos(match):
        x,y=match.group(2),match.group(3)
        return match.group(1)+'="'+(x if x=='center' else dim(x))+','+(y if y=='center' else dim(y))+'"'
    markup=re.sub(r'(position|size)="(center|[0-9]+),(center|[0-9]+)"',pos,markup)
    markup=re.sub(r'(font="[A-Za-z0-9_]+;)([0-9]+)(")',lambda m:m.group(1)+dim(m.group(2))+m.group(3),markup)
    markup=re.sub(r'(itemHeight=")([0-9]+)(")',lambda m:m.group(1)+dim(m.group(2))+m.group(3),markup)
    return markup

class BaseScreen(Screen):
    def __init__(self,session):
        # Main menus and match/pop-up details use the native skin resolution.
        self.skin=_goalalert_hd_skin(type(self).skin)
        Screen.__init__(self,session)
        self["theme_bg"]=Pixmap()
    skin="""<screen name="GoalAlertView" position="center,center" size="950,610" flags="wfNoBorder" backgroundColor="#07162F">
    <widget name="theme_bg" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/ga_menu.png" position="0,0" size="950,610" zPosition="0" alphatest="off" />
    <widget name="heading" position="36,116" size="880,47" font="Regular;28" foregroundColor="#E8F6FF" transparent="1" zPosition="2" />
    <widget name="menu" position="38,177" size="874,328" itemHeight="30" font="Regular;20" foregroundColor="#FFFFFF" backgroundColor="#101E3F" scrollbarMode="showOnDemand" zPosition="2" />
    <widget name="hint" position="38,528" size="880,54" font="Regular;18" foregroundColor="#B5D6F4" transparent="1" zPosition="2" />
    </screen>"""
    def setup(self,title,items,hint="OK: Auswaehlen     EXIT: Zurueck"):
        self["heading"]=Label(title)
        self["menu"]=MenuList(items)
        self["hint"]=Label(hint)
        self["actions"]=ActionMap(["OkCancelActions","ColorActions"],{"ok":self.choose,"cancel":self.close,"red":self.red,"green":self.green,"yellow":self.yellow,"blue":self.blue},-1)
    def red(self):self.close()
    def green(self):pass
    def yellow(self):pass
    def blue(self):pass
    def open_child(self,screen,*args):
        # When IPTV zap succeeds, propagate the close all the way to TV.
        self.session.openWithCallback(self._child_closed,screen,*args)
    def _child_closed(self,result=None):
        if result=="goalalert_zapped":self.close(result)

class LiveOnSatScreen(BaseScreen):
    def __init__(self,session,match=None):
        BaseScreen.__init__(self,session)
        self.match=match
        self.games=[];self.pending=None;self.busy=False
        self.setup("LIVEONSAT | TV-SENDER",["Lade passende TV-Uebertragung ..."],
                   "OK: Sender anzeigen   BLAU: Aktualisieren   EXIT: Zurueck")
        self.timer=eTimer();self.timer.callback.append(self.update);self.onClose.append(self.timer.stop)
        self.blue()
    def blue(self):
        if self.busy:return
        # BLAU aktualisiert immer die aktuelle Begegnung, niemals die ganze Liste.
        self.busy=True;self.pending=None
        self["menu"].setList(["Suche Sender fuer ausgewaehlte Begegnung ..." if self.match else "Lade TV-Spielplan ..."])
        self.timer.start(250,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def fetch(self):
        try:self.pending=liveonsat_schedule(_fixture_local_day(self.match) if self.match else None)
        except Exception as e:self.pending=([],"LiveOnSat nicht erreichbar: "+str(e)[:90])
    def update(self):
        if self.pending is None:return
        self.timer.stop();self.busy=False
        games,info=self.pending;self.pending=None
        if self.match is not None:
            # Shared same-match lookup for main LiveOnSat and red-hotkey LiveScore.
            # Handles AS Roma vs Roma, Genoa CFC vs Genoa, but never wrong opponents.
            from .fixture_match import match_fixtures
            self.games=match_fixtures(self.match,games)
            label=self.match.get("home","?")+" - "+self.match.get("away","?")
            state=self.match.get('state')
            # LIVE comes only from the score provider, not an assumed kickoff.
            status=('LIVE (Spielstandquelle)' if state=='in' else
                    'BEENDET' if state=='post' else 'GEPLANT / LIVE nicht bestaetigt')
            if not self.games:
                self["menu"].setList(["BEGEGNUNG: "+label,
                    "Status: "+status,
                    "Keine bestaetigten TV-Sender fuer genau dieses Spiel.",
                    info,"BLAU: TV-Daten erneut laden"])
                self["hint"].setText("LiveOnSat ohne sicheren Treffer | Kein falscher TV-Sender")
                return
            self["menu"].setList([g.get("day","")+" | "+g.get("time","")+" | "+g["home"]+" - "+g["away"] for g in self.games])
            self["hint"].setText(status+" | %d passende TV-Eintraege | OK: Sender anzeigen"%len(self.games))
            if len(self.games)==1:
                # Go directly to channel details for the specifically selected game.
                self.open_child(LiveOnSatDetailScreen,self.games[0])
            return
        # Only opening LiveOnSat from the main menu is a full TV schedule.
        self.games=games
        if not games:self["menu"].setList([info]);return
        self["menu"].setList([g["day"]+" | "+g["time"]+" | "+g["home"]+" - "+g["away"] for g in games])
        self["hint"].setText("OK: Sender anzeigen | "+info)
    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(self.games):self.open_child(LiveOnSatDetailScreen,self.games[i])

class IPTVBrowseScreen(BaseScreen):
    """Safe paginated fallback to select a sender even when no spelling matches."""
    PAGE_SIZE=60
    def __init__(self,session,broadcast,stations):
        BaseScreen.__init__(self,session)
        self.broadcast=broadcast
        self.stations=sorted(stations,key=lambda x:x.get('name','').lower())
        self.page=0
        self.setup('IPTV | Senderliste durchsuchen',[],
            'OK: Sender | BLAU: Naechste Seite | GELB: Vorige Seite')
        self.render()
    def render(self):
        count=len(self.stations)
        start=self.page*self.PAGE_SIZE
        rows=self.stations[start:start+self.PAGE_SIZE]
        self.visible=rows
        self['menu'].setList([x.get('name','?') for x in rows] or ['IPTV-Bouquet leer'])
        self['hint'].setText('Seite %d/%d | %d Sender | OK: Einschalten | GELB/BLAU: Blaettern'%(
            self.page+1,max(1,(count+self.PAGE_SIZE-1)//self.PAGE_SIZE),count))
    def blue(self):
        if (self.page+1)*self.PAGE_SIZE<len(self.stations):self.page+=1;self.render()
    def yellow(self):
        if self.page>0:self.page-=1;self.render()
    def choose(self):
        i=self['menu'].getSelectedIndex()
        if 0<=i<len(self.visible):self.close(self.visible[i])

class IPTVCandidateScreen(BaseScreen):
    def __init__(self,session,broadcast,matches):
        BaseScreen.__init__(self,session)
        self.matches=matches
        self.setup('IPTV | '+broadcast,
            [x['name'] for x in matches],
            'OK: Diesen Sender einschalten | EXIT: Zurueck')
    def choose(self):
        i=self['menu'].getSelectedIndex()
        if 0<=i<len(self.matches):self.close(self.matches[i])

class LiveOnSatDetailScreen(BaseScreen):
    """Index-only IPTV lookup; never traverses on-box IPTV folders in the UI.

    The prebuilt index contains channel names and row positions, never stream URLs.
    The single chosen service reference is read from one tiny bouquet file only
    after explicit OK confirmation.  This screen never starts a child process.
    """
    def __init__(self,session,g):
        BaseScreen.__init__(self,session)
        self.game=g
        self.channels=[str(x).strip() for x in g.get('channels',[]) if str(x).strip()]
        self.pending_lookup=None
        self.lookup_busy=False
        self.lookup_closed=False
        self.lookup_seq=0
        self.lookup_request=None
        self.lookup_timer=eTimer()
        self.lookup_timer.callback.append(self._check_lookup)
        self.onClose.append(self._stop_lookup)
        self.setup('LIVEONSAT | TV-SENDER',[],
            'OK: Nur diesen Sender in IPTV suchen | EXIT: Zurueck')
        self._render()

    def _stop_lookup(self):
        self.lookup_closed=True
        self.lookup_seq+=1
        try:self.lookup_timer.stop()
        except Exception:pass

    def _render(self,message=''):
        g=self.game
        lines=[str(g.get('day',''))+' | '+str(g.get('time',''))+' | '+
               str(g.get('home',''))+' - '+str(g.get('away',''))]
        lines.extend(self.channels or ['Keine TV-Sender fuer diese Begegnung bekannt'])
        try:old=self['menu'].getSelectedIndex()
        except Exception:old=0
        self['menu'].setList(lines)
        try:self['menu'].moveToIndex(min(max(old,0),len(lines)-1))
        except Exception:pass
        hint='OK: Sender in IPTV-Index suchen (kein Vollscan)'
        if self.lookup_busy:hint='Suche nur im vorbereiteten Live-TV-Index ...'
        if message:hint=message[:145]
        self['hint'].setText(hint)

    def choose(self):
        # Only the explicitly selected TV-station is searched. No bouquet scan
        # or blocking IO in Enigma2's GUI thread. The private index is built
        # separately in Settings > IPTV Live-Index aktualisieren.
        from .iptv_index import INDEX_PATH
        if self.lookup_busy:return
        if not os.path.isfile(INDEX_PATH):
            self._render('IPTV-Live-Index fehlt. Zuerst in Einstellungen aktualisieren.')
            return
        i=self['menu'].getSelectedIndex()-1
        if not (0<=i<len(self.channels)):
            self._render('Bitte TV-Senderzeile auswaehlen.')
            return
        self.lookup_busy=True
        self.lookup_request=i
        self.lookup_seq+=1
        seq=self.lookup_seq
        self.pending_lookup=None
        self._render()
        threading.Thread(target=self._worker,args=(seq,self.channels[i]),daemon=True).start()
        self.lookup_timer.start(125,False)

    def _worker(self,seq,wanted):
        try:
            from .iptv_index import lookup
            matches,count=lookup(wanted)
            data=(seq,matches,count,'')
        except Exception as exc:
            # Avoid printing stream addresses or other sensitive details.
            data=(seq,[],0,'IPTV-Index kann nicht geladen werden ('+type(exc).__name__+')')
        self.pending_lookup=data

    def _check_lookup(self):
        if self.lookup_closed:return
        payload=self.pending_lookup
        if payload is None:return
        self.lookup_timer.stop()
        self.pending_lookup=None
        seq,matches,count,error=payload
        if seq!=self.lookup_seq:return
        self.lookup_busy=False
        if error:
            self._render(error)
            return
        if not matches:
            self._render('Kein Sender gefunden (nur %d IPTV-Live-Sender indexiert).'%count)
            return
        i=self.lookup_request
        self._render('%d passende IPTV-Kanaele gefunden – bitte auswaehlen.'%len(matches))
        if i is not None and 0<=i<len(self.channels):
            self.session.openWithCallback(self._selected,IPTVCandidateScreen,self.channels[i],matches)

    def _selected(self,candidate=None):
        if candidate is None:return
        try:
            from .iptv_index import resolve
            # Read only the chosen IPTV file/line; no full on-box search.
            service=resolve(candidate)
            reference=eServiceReference(service)
            if not reference.valid():raise ValueError('Ungueltige Senderreferenz')
            result=self.session.nav.playService(reference)
            if result not in (None,0,True):raise ValueError('Senderwechsel abgelehnt')
            self.close('goalalert_zapped')
        except Exception as exc:
            # No IPTV URL or ref may ever appear in messages.
            self.session.open(MessageBox,
                'IPTV-Sender konnte nicht gestartet werden ('+type(exc).__name__+'). Bitte Bouquet-Index pruefen.',
                MessageBox.TYPE_ERROR,timeout=7)

# Three selectable experimental providers; keep the working date/TV screens unchanged.
SOURCE_FILE="/etc/enigma2/goalalert_source.json"
SOURCE_NAMES={"gnome":"GnomeFootball (ESPN)","livescore":"LiveScore Football (GitHub)","sofa":"SofaScore (inoffiziell)","euro365":"Euro365 (API-Schluessel)","eurobet":"Eurobet (kein API-Zugriff)"}
try:
    with open(SOURCE_FILE) as f:ACTIVE_SOURCE=json.load(f).get("source","gnome")
except Exception:ACTIVE_SOURCE="gnome"
if ACTIVE_SOURCE not in SOURCE_NAMES:ACTIVE_SOURCE="gnome"

def set_active_source(value):
    global ACTIVE_SOURCE
    if value not in SOURCE_NAMES:return
    ACTIVE_SOURCE=value
    try:
        with open(SOURCE_FILE,"w") as f:json.dump({"source":value},f)
    except Exception:pass

def source_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"GoalAlertTV/5.8 Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=9) as response:return json.load(response)

def _external_game(e,provider):
    home=e.get("homeTeam") or e.get("home") or {}
    away=e.get("awayTeam") or e.get("away") or {}
    if not isinstance(home,dict):home={"name":str(home)}
    if not isinstance(away,dict):away={"name":str(away)}
    status=e.get("status") or {}
    if isinstance(status,dict):status=status.get("type") or status.get("description") or ""
    status=str(status).lower()
    state="in" if any(x in status for x in ("progress","live","1st","2nd","halftime")) else ("post" if any(x in status for x in ("finish","ended","ft")) else "pre")
    score=e.get("homeScore",0);other=e.get("awayScore",0)
    if isinstance(score,dict):score=score.get("current",0)
    if isinstance(other,dict):other=other.get("current",0)
    league=e.get("tournament") or e.get("league") or {}
    if not isinstance(league,dict):league={"name":str(league)}
    start=e.get("startTimestamp")
    date=datetime.fromtimestamp(int(start)).isoformat() if start else str(e.get("date") or "")
    return {"id":str(e.get("id") or e.get("eventId") or ""),"home":home.get("name") or "?","away":away.get("name") or "?",
            "hs":int(score or 0),"as":int(other or 0),"state":state,"date":date,
            "league":str(league.get("id") or ""),"league_name":league.get("name") or "Fussball",
            "minute":e.get("minute"),"home_logo":home.get("logo") or "","away_logo":away.get("logo") or "",
            "provider":provider}

def _real_team_names(g):
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

def selected_live_games():
    if ACTIVE_SOURCE=="gnome":
        # GnomeFootball itself is a GNOME extension, not a remotely callable API.
        # This comparison mode retains the existing working ESPN transport.
        return [g for g in espn_all_games() if g.get("state")=="in"],"GnomeFootball-Vergleich (ESPN-Daten)"
    if ACTIVE_SOURCE=="livescore":
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
    if ACTIVE_SOURCE=="eurobet":
        raise ValueError("Eurobet: keine erlaubte oeffentliche API. Kein automatischer Datenzugriff.")
    if ACTIVE_SOURCE=="euro365":
        keyfile="/etc/enigma2/goalalert_euro365_key.txt"
        try:
            with open(keyfile,"r") as f:key=f.read().strip()
        except Exception:key=""
        if not key:
            raise ValueError("Euro365: API-Key fehlt in /etc/enigma2/goalalert_euro365_key.txt")
        from urllib.parse import urlencode
        url="https://api.euro365.bet/widget-events?"+urlencode({"api_key":key})
        try:payload=source_json(url)
        except Exception:raise ValueError("Euro365 API nicht erreichbar oder Schluessel ungueltig")
        events=payload if isinstance(payload,list) else (payload.get("events") or payload.get("data") or payload.get("results") or [])
        if isinstance(events,dict):events=events.get("events") or events.get("items") or []
        games=[]
        for event in events:
            if not isinstance(event,dict):continue
            try:
                g=_external_game(event,"Euro365")
                if g["state"]=="in":games.append(g)
            except Exception:continue
        return games,"Euro365: experimentelle API (Format nicht verifiziert)"
    # Inofficial public endpoint; errors are shown explicitly, no fabricated data.
    data=source_json("https://www.sofascore.com/api/v1/sport/football/scheduled-events/"+datetime.now().strftime("%Y-%m-%d"))
    games=[]
    for e in data.get("events",[]):
        if not isinstance(e,dict):continue
        g=_external_game(e,"SofaScore")
        if g["state"]=="in":games.append(g)
    return games,"SofaScore (inoffizielle Quelle)"

class SourceScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.codes=["gnome","livescore","sofa","euro365","eurobet"]
        self.setup("DATENQUELLE AUSWAEHLEN",[],"OK: Waehlen und speichern | EXIT: Zurueck")
        self.refresh()
    def refresh(self):
        self["menu"].setList([("★ " if ACTIVE_SOURCE==code else "  ")+SOURCE_NAMES[code] for code in self.codes])
    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(self.codes):
            set_active_source(self.codes[i]);self.refresh()
            self["hint"].setText("Gespeichert: "+SOURCE_NAMES[ACTIVE_SOURCE]+" | EXIT: Zurueck")



# GoalAlert online/local updater. Enigma2 UI changes happen only in timer callbacks.
class GoalAlertUpdateScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.busy=False
        self.pending=None
        self.candidate=None
        self.request_generation=0
        self.timer=eTimer()
        self.timer.callback.append(self._poll)
        self.onClose.append(self._shutdown)
        self.setup("GOALALERT | UPDATES",[
            "Online nach neuer Version suchen",
            "Neue IPK aus /tmp waehlen",
            "Version installieren (nach Bestaetigung)",
            "Update-Adresse anzeigen"],
            "OK: Auswahl  BLAU: Online  GRUEN: lokal  GELB: installieren")
        self._status('Installiert: 6.13.14 | keine Installation gestartet')
    def _status(self,message):
        try:self['hint'].setText(message[:150])
        except Exception:pass
    def _shutdown(self):
        self.request_generation+=1
        try:self.timer.stop()
        except Exception:pass
    def choose(self):
        i=self['menu'].getSelectedIndex()
        if i==0:self.blue()
        elif i==1:self.green()
        elif i==2:self.yellow()
        elif i==3:self._status('Quelle: '+_goalalert_updates.get_source())
    def blue(self):
        if self.busy:return
        self.candidate=None
        self._run('online')
    def green(self):
        if self.busy:return
        self.candidate=None
        self._run('lokal')
    def _run(self,kind):
        self.busy=True
        self.pending=None
        self.request_generation+=1
        gen=self.request_generation
        self._status('Update wird geprueft ...')
        self.timer.start(250,False)
        def worker():
            try:
                if kind=='lokal':
                    candidate=_goalalert_updates.newest_local_ipk('6.13.14')
                    result=('ok',candidate)
                else:
                    data=_goalalert_updates.check_manifest(_goalalert_updates.get_source(),'6.13.14')
                    if not data.get('newer'):
                        result=('info','Bereits aktuell (Online: '+data['version']+')')
                    else:
                        result=('ok',dict(data,origin='online'))
            except Exception as exc:
                result=('err','Update-Pruefung: '+str(exc)[:100])
            if gen==self.request_generation:
                self.pending=result
        threading.Thread(target=worker,daemon=True).start()
    def _poll(self):
        if self.pending is None:
            if getattr(self,'install_waiting',False):
                try:
                    with open('/tmp/goalalert_update_status.json') as f:
                        state=json.load(f)
                    msg=str(state.get('message') or '')[:145]
                    if msg:self._status(msg)
                    if state.get('state') in ('failed','restarted'):
                        self.install_waiting=False
                        self.timer.stop()
                        self.busy=False
                except Exception:pass
            return
        self.timer.stop()
        self.busy=False
        kind,val=self.pending
        self.pending=None
        if kind=='ok':
            self.candidate=val
            self._status('Version '+val['version']+' bereit | GELB: installieren')
        else:
            self._status(val)
            if kind=='installing':
                self.install_waiting=True
                self.busy=True
                self.timer.start(500,False)
    def yellow(self):
        if self.busy or not self.candidate:
            self._status('Zuerst Online oder lokale IPK pruefen')
            return
        item=self.candidate
        message=('GoalAlert %s installieren?\n\n'%item['version']+
                 'Das Plugin wird aktualisiert und Enigma2 neu gestartet.\n'+
                 'Live-TV wird waehrend der Installation unterbrochen.')
        self.session.openWithCallback(self._confirm_install,MessageBox,message,type=MessageBox.TYPE_YESNO)
    def _confirm_install(self,accepted):
        if not accepted or not self.candidate:return
        if self.busy:return
        self._run_install(self.candidate)
    def _run_install(self,item):
        self.busy=True
        self.pending=None
        self.request_generation+=1
        gen=self.request_generation
        self._status('Paket wird geladen und vor Installation ueberprueft ...')
        self.timer.start(250,False)
        def worker():
            try:
                if item['origin']=='online':
                    ready=_goalalert_updates.download_update(item,'6.13.14')
                else:
                    # Reverify local package before handing over to detached installer.
                    version=_goalalert_updates.verify_ipk(item['path'],'6.13.14')
                    ready=dict(item,version=version)
                path=ready['path']
                import hashlib
                h=hashlib.sha256()
                with open(path,'rb') as f:
                    for chunk in iter(lambda:f.read(65536),b''):h.update(chunk)
                sha=h.hexdigest()
                helper=os.path.join(os.path.dirname(__file__),'goalalert_apply_update.py')
                if not os.path.isfile(helper):raise RuntimeError('Update-Installationshilfe fehlt')
                with open('/home/root/goalalert_update.log','a') as log:
                    log.write('Update bestaetigt: %s\n'%ready['version'])
                # Independent process; never block the Enigma2 GUI on opkg/init.
                try:os.unlink('/tmp/goalalert_update_status.json')
                except OSError:pass
                with open('/home/root/goalalert_update_launcher.log','ab') as log:
                    subprocess.Popen([__import__('sys').executable,helper,'--install',path,'--sha256',sha],
                        stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                        close_fds=True,start_new_session=True)
                result=('installing','Paket geprueft. Installiere GoalAlert ...')
            except Exception as exc:
                result=('err','Installation nicht gestartet: '+str(exc)[:95])
            if gen==self.request_generation:self.pending=result
        threading.Thread(target=worker,daemon=True).start()

class Home(BaseScreen):
    skin="""<screen name="GoalAlertHome" position="center,center" size="1120,670" flags="wfNoBorder" backgroundColor="#07162F">
    <widget name="theme_bg" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/ga_home.png" position="0,0" size="1120,670" zPosition="0" alphatest="off" />
    <widget name="heading" position="581,27" size="502,39" font="Regular;23" foregroundColor="#B7E8FF" transparent="1" zPosition="2" />
    <widget name="menu" position="46,135" size="513,440" itemHeight="27" font="Regular;18" foregroundColor="#FFFFFF" backgroundColor="#102548" scrollbarMode="showOnDemand" zPosition="2" />
    <widget name="hint" position="46,602" size="1040,41" font="Regular;19" foregroundColor="#D9ECFF" transparent="1" zPosition="2" />
    </screen>"""
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("GOALALERT 6.13.14 | SPORT STUDIO",["Spiele nach Datum","Live-Spiele","Meine Favoriten","Liga auswaehlen","Einstellungen","Test-Toralarm (mit Ton)","Tippschein (15 Spiele)","LiveOnSat TV-Spielplan","Datenquelle auswaehlen","Verbindung pruefen","Echte Vereinswappen testen","Gruenen Torschuetzenhinweis testen","Audio-Diagnose anzeigen","GoalAlert Live (heute)","Updates installieren"])
    def choose(self):
        n=self["menu"].getSelectedIndex()
        if n==0:self.open_child(GamesScreen,0)
        elif n==1:self.open_child(AllLiveScreen)
        elif n==2:self.open_child(FavoritesScreen)
        elif n==3:self.session.open(LeagueScreen)
        elif n==4:self.session.open(SettingsScreen)
        elif n==5:monitor.test_goal()
        elif n==6:self.session.open(TipScreen)
        elif n==7:self.open_child(LiveOnSatScreen)
        elif n==8:self.session.open(SourceScreen)
        elif n==9:self.session.open(DiagnosticsScreen)
        elif n==10:self.session.open(CrestTestScreen)
        elif n==11:monitor.test_scorer()
        elif n==12:self.session.open(AudioStatusScreen)
        elif n==13:self.open_child(QuickLiveScreen)
        elif n==14:self.session.open(GoalAlertUpdateScreen)

LEAGUE_FILE="/etc/enigma2/goalalert_leagues.json"
try:
    with open(LEAGUE_FILE,"r") as f:
        selected_leagues=set(json.load(f))
except Exception:
    selected_leagues=set(DEFAULT_LEAGUES)
def save_leagues():
    try:
        with open(LEAGUE_FILE,"w") as f:json.dump(sorted(selected_leagues),f)
    except Exception:pass

class LeagueScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.row_codes=[]
        self.setup("LIGEN MIT STERN MARKIEREN",[],"OK: Stern umschalten  GRUEN: Fertig  EXIT: Speichern")
        self.refresh()
    def refresh(self):
        lines=[];self.row_codes=[]
        for label,entries in LEAGUE_SECTIONS:
            lines.append("--- "+label+" ---");self.row_codes.append(None)
            for name,code in entries:
                lines.append(("★ " if code in selected_leagues else "☆ ")+name)
                self.row_codes.append(code)
        self["menu"].setList(lines)
        self["hint"].setText("%d Ligen markiert | OK: Stern setzen/entfernen | EXIT: Speichern"%len(selected_leagues))
    def choose(self):
        idx=self["menu"].getSelectedIndex()
        if idx<0 or idx>=len(self.row_codes):return
        code=self.row_codes[idx]
        if code is None:return
        if code in selected_leagues:selected_leagues.remove(code)
        else:selected_leagues.add(code)
        self.refresh()
        try:self["menu"].moveToIndex(idx)
        except Exception:pass
    def green(self):self.close()
    def close(self,*args,**kwargs):
        save_leagues()
        if selected_leagues:
            preferred=config.plugins.goalalert32.league
            if preferred.value not in selected_leagues:
                preferred.value=next((code for name,code in LEAGUES if code in selected_leagues),"eng.1")
                preferred.save();configfile.save()
        BaseScreen.close(self,*args,**kwargs)

class GamesScreen(BaseScreen):
    def __init__(self,session,offset=0,live=False):
        BaseScreen.__init__(self,session)
        self.offset=offset;self.live=live;self.games=[];self.row_games=[]
        self.setup("SPIELE",["Spiele werden geladen ..."],"ROT: Vortag   BLAU: Folgetag   OK: Details   GRUEN: Favorit   EXIT: Zurueck")
        self.timer=eTimer();self.timer.callback.append(self.load);self.timer.start(50,True)
        self.onClose.append(self.cleanup)
    def cleanup(self):
        self.timer.stop()
        if hasattr(self,"wait"):self.wait.stop()
    def load(self):
        league=config.plugins.goalalert32.league.value
        date=(datetime.now()+timedelta(days=self.offset)).strftime("%Y%m%d")
        self["heading"].setText(("LIVE" if self.live else "ALLE SPIELE")+"  |  "+date)
        self["menu"].setList(["Lade Spielplan ..."])
        self.pending=None
        threading.Thread(target=self.fetch,args=(league,date),daemon=True).start()
        if not hasattr(self,"wait"):
            self.wait=eTimer();self.wait.callback.append(self.display)
        self.wait.start(300,False)
    def fetch(self,league,date):
        games=[];errors=[]
        targets=sorted(LEAGUES,key=lambda item:(
            0 if item[1] in ('sui.1','sui.2','sui.cup') else
            (1 if item[1] in selected_leagues else 2),item[0]))
        if not targets:
            self.pending=([],"Bitte zuerst Ligen mit Stern markieren")
            return
        # Parallel fetch prevents a long serial wait when many leagues are starred.
        with ThreadPoolExecutor(max_workers=18) as pool:
            futures={pool.submit(get_games,code,date):name for name,code in targets}
            for future in as_completed(futures):
                name=futures[future]
                try:
                    for game in future.result():
                        game["league_name"]=name
                        games.append(game)
                except Exception:errors.append(name)
        self.pending=(games,"Keine Datenverbindung" if not games and errors else None)
    def display(self):
        if self.pending is None:return
        self.wait.stop()
        games,error=self.pending
        if self.live:games=[g for g in games if g["state"]=="in"]
        self.games=games
        if error:self["menu"].setList([error])
        elif not games:self["menu"].setList(["Keine Spiele fuer diesen Tag."])
        else:
            self.render_games()
    def choose(self):
        idx=self["menu"].getSelectedIndex()
        if 0<=idx<len(self.row_games) and self.row_games[idx]:self.open_child(GameDetailScreen,self.row_games[idx])
    def green(self):
        idx=self["menu"].getSelectedIndex()
        if idx<0 or idx>=len(self.row_games) or not self.row_games[idx]:return
        g=self.row_games[idx];key=str(g["id"])
        if key in favorites:del favorites[key]
        else:favorites[key]={"league":g["league"],"home":g["home"],"away":g["away"]}
        save_favorites();preload_favorite_crests(g) if key in favorites else None;self.display_again()
    def display_again(self):self.render_games()
    def render_games(self):
        lines=[];self.row_games=[]
        for league in sorted(set(g.get("league_name") or g.get("league") or "Andere" for g in self.games)):
            group=[g for g in self.games if (g.get("league_name") or g.get("league") or "Andere")==league]
            lines.append("==== "+league.upper()+" ====");self.row_games.append(None)
            for g in sorted(group,key=lambda x:x.get("date", "")):
                lines.append(game_line(g));self.row_games.append(g)
        self["menu"].setList(lines)
    def red(self):
        self.offset-=1;self.load()
    def yellow(self):
        # Vorversionen verwendeten GELB. ROT ist die beschriftete Taste.
        self.red()
    def blue(self):
        self.offset+=1;self.load()



# TV-Schnellansicht: nach Anstosszeit, bei gleicher Minute nach Liga-Prioritaet.
# Separate priorities make important European competitions appear before
# smaller leagues without altering the ESPN match feed or stored favorites.
QUICK_LEAGUE_RANK={
    'uefa.champions':0,'uefa.europa':1,'uefa.europa.conf':2,
    'fifa.world':3,'uefa.euro':4,'uefa.nations':5,
    'eng.1':10,'esp.1':11,'ita.1':12,'ger.1':13,'fra.1':14,
    'por.1':15,'ned.1':16,'sui.1':17,'bel.1':18,'tur.1':19,
}
for _section_index,(_section_name,_section_leagues) in enumerate(LEAGUE_SECTIONS):
    for _name,_code in _section_leagues:
        QUICK_LEAGUE_RANK.setdefault(_code,30+_section_index*15)

def quick_match_sort_key(game):
    # ESPN date is normally an ISO-8601 UTC timestamp. Compare absolute minutes
    # first: 20:45 Serie A therefore comes before 20:45 Saudi Pro League.
    from datetime import timezone
    try:
        dt=datetime.fromisoformat(str(game.get('date') or '').replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        minute=int(dt.timestamp()//60)
    except (ValueError,TypeError,OverflowError):
        minute=99999999999
    return (minute,QUICK_LEAGUE_RANK.get(str(game.get('league') or ''),200),
            str(game.get('league_name') or '').casefold(),
            str(game.get('home') or '').casefold(),str(game.get('id') or ''))


def quick_match_line(game):
    # Show kickoff even for live/finished matches (game_line only shows LIVE/ENDE).
    kickoff=kickoff_ch(game.get('date'))
    kickoff=kickoff[-5:] if kickoff!='--:--' else kickoff
    return kickoff+' | '+game_line(game)

class QuickLiveScreen(GamesScreen):
    """TV hotkey: today by kickoff, same-time matches by league importance."""
    skin=(BaseScreen.skin
          .replace('backgroundColor="#07162F"', 'transparent="1" backgroundColor="transparent"')
          .replace('ga_menu.png', 'ga_live_glass.png')
          .replace('zPosition="0" alphatest="off"', 'zPosition="0" transparent="1" alphatest="blend"')
          .replace('backgroundColor="#101E3F"', 'transparent="1" backgroundColor="#0D1D35"'))
    def __init__(self,session):
        self.only_live=False
        self.today_games=[]
        GamesScreen.__init__(self,session,offset=0,live=False)
        self['heading'].setText('GOALALERT LIVE | HEUTE')
        self['hint'].setText('ROT: nur LIVE | BLAU: alle | GRUEN: Favorit | GELB: neu laden')
    def display(self):
        if self.pending is None:return
        self.wait.stop()
        self.today_games,error=self.pending
        self.pending=None
        self.error=error
        self._render_quick()
    def _render_quick(self,selected_id=None):
        all_games=self.today_games
        active=[g for g in all_games if g.get('state')=='in']
        self['heading'].setText('GOALALERT LIVE | %d LIVE / %d HEUTE'%(len(active),len(all_games)))
        self.games=active if self.only_live else all_games
        self.row_games=sorted(self.games,key=quick_match_sort_key)
        if not self.row_games:
            self['menu'].setList([self.error or ('Zurzeit keine laufenden Spiele.' if self.only_live else 'Keine Spiele in den erreichbaren Wettbewerben.')])
        else:
            self['menu'].setList([quick_match_line(g) for g in self.row_games])
            if selected_id is not None:
                for index,game in enumerate(self.row_games):
                    if str(game.get('id'))==str(selected_id):
                        try:self['menu'].moveToIndex(index)
                        except Exception:pass
                        break
        self['hint'].setText('ROT: LIVE | BLAU: alle | GRUEN: ★ Favorit | GELB: laden | OK: Details | EXIT: TV')
    def green(self):
        # The TV quick list needs its own handler: the parent GamesScreen.green()
        # redraws a league-grouped view and loses the chronological sort.
        index=self['menu'].getSelectedIndex()
        if index<0 or index>=len(self.row_games):return
        game=self.row_games[index]
        key=str(game.get('id') or '')
        if not key:return
        if key in favorites:
            del favorites[key]
            label='Toralarm AUS'
        else:
            favorites[key]={'league':str(game.get('league') or ''),
                            'home':game.get('home',''),
                            'away':game.get('away',''),
                            'provider':game.get('provider','ESPN')}
            label='Toralarm EIN'
            # Baseline: do not report an old goal as new immediately after
            # pressing green during a match.
            try:
                monitor.last[(str(game.get('league')),key)]=(int(game.get('hs',0)),int(game.get('as',0)))
            except (TypeError,ValueError):pass
        save_favorites()
        if key in favorites:preload_favorite_crests(game)
        self._render_quick(selected_id=key)
        self['hint'].setText(label+' fuer '+str(game.get('home','?'))+' - '+str(game.get('away','?'))+' | GRUEN: umschalten')
    def red(self):
        self.only_live=True;self._render_quick()
    def blue(self):
        self.only_live=False;self._render_quick()
    def yellow(self):
        self.offset=0;self.load()


class GameDetailScreen(BaseScreen):
    # Up to 12 scoring incidents (e.g. 6:5) fit in two columns without scrolling.
    skin="""<screen name="GoalAlertDetails" position="center,center" size="1120,630" flags="wfNoBorder" backgroundColor="#07162F">
    <widget name="theme_bg" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/ga_detail.png" position="0,0" size="1120,630" zPosition="0" alphatest="off" />
    <widget name="heading" position="310,30" size="765,40" font="Regular;24" foregroundColor="#DDF6FF" transparent="1" zPosition="2" />
    <widget name="summary" position="39,107" size="1042,40" font="Regular;24" foregroundColor="#FFE588" transparent="1" zPosition="2" />
    <widget name="events_title" position="45,160" size="1030,42" font="Regular;26" foregroundColor="#92EDFF" transparent="1" zPosition="2" />
    <widget name="events_left" position="50,210" size="493,265" font="Regular;22" foregroundColor="#EAF9FF" transparent="1" zPosition="2" />
    <widget name="events_right" position="578,210" size="490,265" font="Regular;22" foregroundColor="#EAF9FF" transparent="1" zPosition="2" />
    <widget name="events_unassigned" position="45,478" size="1030,27" font="Regular;17" foregroundColor="#F9DE86" transparent="1" zPosition="2" />
    <widget name="menu" position="43,526" size="1032,47" itemHeight="43" font="Regular;23" foregroundColor="#FFFFFF" backgroundColor="#114D92" scrollbarMode="showNever" zPosition="2" />
    <widget name="hint" position="44,585" size="1020,34" font="Regular;18" foregroundColor="#AECFEB" transparent="1" zPosition="2" />
    </screen>"""
    def __init__(self,session,game):
        BaseScreen.__init__(self,session)
        self.game=game;self.result=None;self.wait=eTimer()
        self.wait.callback.append(self.show_result)
        self.onClose.append(self.wait.stop)
        self.setup("SPIEL | "+game.get("home","")+" - "+game.get("away",""),
          ["OK: TV-SENDER DIESER BEGEGNUNG","OK: AUFSTELLUNGEN (falls verfuegbar)","OK: LIGA-TABELLE"],
          "ROT: Tabelle  GELB: Aufstellungen  GRUEN: Favorit  BLAU: Neu")
        self["summary"]=Label("Lade Spieldetails ...")
        self["events_title"]=Label("TORE & VORLAGEN")
        self["events_left"]=Label("Lade Tore ...")
        self["events_right"]=Label("")
        self["events_unassigned"]=Label("")
        self.blue()
    def choose(self):
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
    def green(self):
        g=self.game;k=str(g["id"])
        if k in favorites:del favorites[k];status="Favorit entfernt"
        else:
            favorites[k]={"league":g.get("league",""),"home":g["home"],"away":g["away"]}
            status="Favorit gespeichert"
        save_favorites();preload_favorite_crests(g) if k in favorites else None;self["hint"].setText(status+" | BLAU: Aktualisieren")
    def blue(self):
        self.result=None
        self["events_left"].setText("Lade Tore ...")
        self["events_right"].setText("")
        self["events_unassigned"].setText("")
        threading.Thread(target=self.fetch,daemon=True).start()
        self.wait.start(250,False)
    def fetch(self):
        events=detailed_events(self.game)
        self.result=([],"OK auf TV-Sender: passende LiveOnSat-Uebertragung oeffnen",events)
    def show_result(self):
        if self.result is None:return
        self.wait.stop()
        channels,info,events=self.result
        g=self.game
        status=(str(g.get("minute") or "LIVE") if g.get("state")=="in" else ("Beendet" if g.get("state")=="post" else "Geplant"))
        self["summary"].setText("  %s:%s  |  %s  |  %s  |  Anstoss: %s"%(
            g.get("hs",0),g.get("as",0),g.get("league_name") or g.get("league", "Fussball"),status,kickoff_ch(g.get("date"))))
        if events:
            def fmt(e):
                scorer=str(e.get('scorer') or 'Unbekannt')
                assist=str(e.get('assist') or '')
                if assist.lower() in ('unbekannt','-','keine angabe','nicht verfuegbar','nicht verfügbar','nicht gemeldet'):
                    assist=''
                line=str(e.get('minute') or '?')+"' "+scorer
                if assist:line+='  (A: '+assist+')'
                return line[:48]
            home=[fmt(e) for e in events if e.get('side')=='home']
            away=[fmt(e) for e in events if e.get('side')=='away']
            unknown=[fmt(e) for e in events if e.get('side') not in ('home','away')]
            self['events_title'].setText(g.get('home','')+'  -  '+g.get('away',''))
            def compact(rows):
                if len(rows)>7:return '\n'.join(rows[:7])+"\n+%d weitere"%(len(rows)-7)
                return '\n'.join(rows)
            # Never display unassigned goals in either team's column.
            if unknown:
                self['events_unassigned'].setText('Team nicht zugeordnet: '+', '.join(unknown)[:94])
            else:self['events_unassigned'].setText('')
            self['events_left'].setText(compact(home))
            self['events_right'].setText(compact(away))
        elif g.get("state")=="pre" or int(g.get("hs") or 0)+int(g.get("as") or 0)==0:
            self["events_unassigned"].setText("")
            self["events_left"].setText("")
            self["events_right"].setText("")
        else:
            self["events_unassigned"].setText("")
            self["events_left"].setText("")
            key=str(g.get("league"))+":"+str(g.get("id"))
            self["events_right"].setText("")
        self["menu"].setList(["OK: TV-SENDER DIESER BEGEGNUNG",
                              "OK: AUFSTELLUNGEN (falls verfuegbar)","OK: LIGA-TABELLE"])

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
                   "Spielerdaten von ESPN | BLAU: Neu laden | EXIT: Zurueck")
        threading.Thread(target=self.load,daemon=True).start()
        self.timer.start(250,False)
    def load(self):
        try:
            from .goalalert_lineups import format_lineups, valid_espn_event_id, valid_league
            event_id=valid_espn_event_id(self.game.get('id'))
            league=valid_league(self.game.get('league'))
            if not event_id or not league:
                raise ValueError('Keine ESPN-Spiel-ID oder gueltige Liga vorhanden')
            from urllib.parse import quote
            url=("https://site.api.espn.com/apis/site/v2/sports/soccer/%s/summary?event=%s"%
                 (quote(league,safe='.'),event_id))
            request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 GoalAlert/6.13.14'})
            with urllib.request.urlopen(request,timeout=12) as response:
                payload=json.load(response)
            self.result=format_lineups(payload)
        except Exception as exc:
            self.result=['Aufstellungen derzeit nicht verfuegbar:',
                         str(exc)[:105], 'BLAU: erneut laden']
    def display(self):
        if self.result is None:return
        self.timer.stop()
        self['menu'].setList(self.result)
        self.result=None
    def blue(self):
        self.result=None
        self['menu'].setList(['Lade aktuelle Aufstellungen ...'])
        self.timer.start(250,False)
        threading.Thread(target=self.load,daemon=True).start()

class GoalAlertLeagueTableScreen(BaseScreen):
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
            request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GoalAlert/6.13.14"})
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


class AllLiveScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("LIVE | FUSSBALL",["BLAU: Live-Spiele laden"],"BLAU: Aktualisieren | OK: TV-Sender | GRUEN: Favorit")
        self.games=[];self.result=None;self.busy=False
        self.timer=eTimer();self.timer.callback.append(self.update);self.onClose.append(self.timer.stop)
        self.blue()
    def blue(self):
        if self.busy:return
        self.busy=True;self.result=None
        self["menu"].setList(["Lade alle Live-Spiele ..."])
        self.timer.start(300,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def fetch(self):
        try:
            games,info=selected_live_games()
            self.result=(games,None,info)
        except Exception as e:self.result=([],SOURCE_NAMES.get(ACTIVE_SOURCE,"Quelle")+": "+str(e)[:75],"")
    def update(self):
        if self.result is None:return
        self.timer.stop();self.busy=False
        self.games,error,info=self.result;self.result=None
        if error:
            self["menu"].setList(["Fehler: "+error])
            self["hint"].setText("Keine Live-Daten | BLAU: erneut laden")
            return
        self.games=[g for g in self.games if g.get("state")=="in" and _real_team_names(g)]
        self["menu"].setList([game_line(g) for g in self.games] or ["Derzeit keine bestaetigten Live-Spiele in den erfassten Wettbewerben."])
        self["hint"].setText(("%d Live | %s | BLAU: Laden"%(len(self.games),info))[:165])
    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(self.games):self.open_child(GameDetailScreen,self.games[i])
    def green(self):
        i=self["menu"].getSelectedIndex()
        if i<0 or i>=len(self.games):return
        g=self.games[i];k=g["id"]
        if k in favorites:del favorites[k]
        else:favorites[k]={"league":g["league"],"home":g["home"],"away":g["away"],"provider":"api-football"}
        save_favorites()
        self.update_favorite(i)
    def update_favorite(self,i):
        g=self.games[i];self["menu"].l.setItemHeight(48)
        self["menu"].setList([("★" if x["id"] in favorites else "☆")+" "+x["league_name"]+" | "+x["home"]+" - "+x["away"]+" %s:%s"%(x["hs"],x["as"])+" | "+(str(x.get("minute"))+chr(39) if x.get("minute") is not None else kickoff_ch(x.get("date"))) for x in self.games])
        self["menu"].moveToIndex(i)

class FavoritesScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.ids=list(favorites)
        self.setup("MEINE SPIELE",["%s - %s"%(favorites[k].get("home","?"),favorites[k].get("away","?")) for k in self.ids] or ["Keine Favoriten gewaehlt"],"OK: Favorit entfernen     EXIT: Zurueck")
    def choose(self):
        i=self["menu"].getSelectedIndex()
        if i<0 or i>=len(self.ids):return
        favorites.pop(self.ids[i],None);save_favorites()
        self.ids=list(favorites)
        self["menu"].setList(["%s - %s"%(favorites[k].get("home","?"),favorites[k].get("away","?")) for k in self.ids] or ["Keine Favoriten gewaehlt"])

class SettingsScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("GOALALERT | EINSTELLUNGEN",[],"OK: Aendern   GRUEN: Speichern   EXIT: Zurueck")
        self.index_busy=False
        self.index_result=None
        self.index_timer=eTimer()
        self.index_timer.callback.append(self._index_ready)
        self.onClose.append(self.index_timer.stop)
        self.refresh()
    def refresh(self):
        c=config.plugins.goalalert32
        size_names={'mini':'Mini','compact':'Kompakt','normal':'Normal'}
        from .iptv_index import INDEX_PATH
        index_state=('vorhanden' if os.path.isfile(INDEX_PATH) else 'fehlt')
        self["menu"].setList([
            "Toralarme: "+("Ein" if c.enabled.value else "Aus"),
            "Popup-Dauer: "+c.duration.value+" Sekunden",
            "Popup-Groesse: "+size_names.get(c.popup_size.value,'Kompakt'),
            "Torjubel: "+{"classic":"Klassisch","stadium":"Stadion-Echo",
                         "double":"Doppeljubel","short":"Kurzer Tor-Ruf"}.get(c.cheer_style.value,"Klassisch"),
            "Test-Toralarm anzeigen",
            "Test-Torschuetze (stumm)",
            "IPTV-Live-Index erneuern ("+('laeuft' if self.index_busy else index_state)+")",
            "API-Schluessel: "+("hinterlegt" if api_key() else "fehlt")])
    def choose(self):
        i=self["menu"].getSelectedIndex();c=config.plugins.goalalert32
        if i==7:
            self.session.openWithCallback(self.save_api_key,VirtualKeyBoard,title="API-Football Schluessel",text=api_key())
            return
        if i==0:c.enabled.value=not c.enabled.value
        elif i==1:
            values=["4","6","10"];c.duration.value=values[(values.index(c.duration.value)+1)%len(values)]
        elif i==2:
            values=["mini","compact","normal"]
            c.popup_size.value=values[(values.index(c.popup_size.value)+1)%len(values)]
        elif i==3:
            values=["classic","stadium","double","short"]
            c.cheer_style.value=values[(values.index(c.cheer_style.value)+1)%len(values)]
        elif i==4:monitor.test_goal()
        elif i==5:monitor.test_scorer()
        elif i==6:self.rebuild_index()
        self.refresh()
    def rebuild_index(self):
        if self.index_busy:return
        self.index_busy=True
        self.index_result=None
        self.refresh()
        self['hint'].setText('Der private Live-TV-Index wird im Hintergrund erstellt ...')
        def work():
            try:
                from .refresh_iptv_index import build
                build()
                value=(True,'IPTV-Live-Index aktualisiert. Sender jetzt sicher suchbar.')
            except Exception as exc:
                value=(False,'Index nicht erstellt: '+type(exc).__name__+' (BouquetMakerXtream pruefen)')
            self.index_result=value
        threading.Thread(target=work,daemon=True).start()
        self.index_timer.start(400,False)
    def _index_ready(self):
        if self.index_result is None:return
        self.index_timer.stop()
        self.index_busy=False
        ok,message=self.index_result
        self.index_result=None
        self.refresh()
        self['hint'].setText(message)
    def save_api_key(self,value):
        if value is None:return
        try:
            with open(API_SETTINGS,"w") as f:json.dump({"key":value.strip()},f)
            os.chmod(API_SETTINGS,0o600)
        except Exception:pass
        self.refresh()
    def green(self):
        c=config.plugins.goalalert32
        c.enabled.save();c.duration.save();c.popup_size.save();c.cheer_style.save();configfile.save()
        self.session.open(MessageBox,"Gespeichert",MessageBox.TYPE_INFO,timeout=2)


TIP_LEAGUES=[
("Champions League","uefa.champions"),("Europa League","uefa.europa"),
("Premier League","eng.1"),("Serie A","ita.1"),("La Liga","esp.1"),
("Bundesliga","ger.1"),("Ligue 1","fra.1"),("Primeira Liga","por.1"),
("Super League Schweiz","sui.1"),("Eredivisie","ned.1"),
("Pro League Belgien","bel.1"),("Süper Lig","tur.1"),
("Bundesliga Österreich","aut.1")]
TIP_CONFIG="/etc/enigma2/goalalert_tip_leagues.json"
try:
    with open(TIP_CONFIG,"r") as f: tip_codes=set(json.load(f))
except Exception:
    tip_codes=set(code for name,code in TIP_LEAGUES)
def save_tip_codes():
    try:
        with open(TIP_CONFIG,"w") as f:json.dump(sorted(tip_codes),f)
    except Exception:pass

class TipLeagueScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("TIPPSCHEIN | LIGEN",[],"OK: Stern umschalten  GRUEN/EXIT: Speichern")
        self.refresh()
    def refresh(self):
        self["menu"].setList([("★ " if code in tip_codes else "☆ ")+name for name,code in TIP_LEAGUES])
    def choose(self):
        i=self["menu"].getSelectedIndex()
        if 0<=i<len(TIP_LEAGUES):
            code=TIP_LEAGUES[i][1]
            if code in tip_codes:tip_codes.remove(code)
            else:tip_codes.add(code)
            self.refresh()
            try:self["menu"].moveToIndex(i)
            except Exception:pass
    def green(self):self.close()
    def close(self,*args,**kwargs):
        save_tip_codes()
        BaseScreen.close(self,*args,**kwargs)

TIP_API_IDS={'uefa.champions': 2, 'uefa.europa': 3, 'eng.1': 39, 'ita.1': 135, 'esp.1': 140, 'ger.1': 78, 'fra.1': 61, 'por.1': 94, 'sui.1': 207, 'ned.1': 88, 'bel.1': 144, 'tur.1': 203, 'aut.1': 218}

# Public ESPN soccer bookmaker odds. Real prices only, never probability estimates
# masquerading as bookmaker odds. No API-Football subscription is required.
ESPN_ODDS_CACHE="/etc/enigma2/goalalert_espn_odds.json"
ESPN_ODDS_LOCK=threading.RLock()
ESPN_ODDS_MEMORY={}

def _decimal_price(v):
    if isinstance(v,dict):
        for key in ("decimal","value","decimalOdds"):
            x=v.get(key)
            if x is not None:
                try:
                    n=float(x)
                    if 1.001 <= n <= 1000: return round(n,3)
                except Exception:pass
        summary=str(v.get("summary") or "")
        if "/" in summary:
            try:
                n,d=summary.split("/",1)
                result=1.0+float(n)/float(d)
                if 1.001 <= result <= 1000:return round(result,3)
            except Exception:pass
        ml=v.get("moneyLine")
        if ml is not None:
            try:
                ml=float(ml)
                if ml>0:return round(1+ml/100,3)
                if ml<0:return round(1+100/abs(ml),3)
            except Exception:pass
    else:
        try:
            value=float(v)
            if 1.001<=value<=1000:return round(value,3)
        except Exception:pass
    return None

def _espn_1x2(items):
    if isinstance(items,dict):items=items.get("items") or [items]
    for market in items or []:
        if not isinstance(market,dict):continue
        # Requires ALL THREE outcomes from the SAME book to avoid mixing prices.
        h=_decimal_price(market.get("homeTeamOdds"))
        d=_decimal_price(market.get("drawOdds"))
        a=_decimal_price(market.get("awayTeamOdds"))
        if h and d and a:return {"1":h,"X":d,"2":a}
    return None

def _odds_core_one(game):
    # Core endpoint: /events/{id}/competitions/{id}/odds.
    # Follow ESPN-owned $ref pointers if returned.
    import urllib.parse
    ident=str(game.get("id") or "")
    league=str(game.get("league") or "")
    if not ident.isdigit() or league not in (code for name,code in TIP_LEAGUES):return None
    key=league+":"+ident
    now=time.time()
    with ESPN_ODDS_LOCK:
        cached=ESPN_ODDS_MEMORY.get(key)
        if cached and now-cached[0]<7200:return cached[1]
    url="https://sports.core.api.espn.com/v2/sports/soccer/leagues/%s/events/%s/competitions/%s/odds"%(league,ident,ident)
    def fetch_json(url):
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 GoalAlertTV/6.6","Accept":"application/json"})
        with urllib.request.urlopen(req,timeout=7) as r:return json.load(r)
    try:
        data=fetch_json(url)
        if not isinstance(data,dict):data={}
        items=data.get("items") or []
        resolved=[]
        for item in items[:4]:
            if not isinstance(item,dict):continue
            pointer=item.get("$ref")
            if pointer and not item.get("homeTeamOdds"):
                pointer=pointer.replace("http://","https://",1)
                parsed=urllib.parse.urlparse(pointer)
                if parsed.scheme!="https" or parsed.hostname not in ("sports.core.api.espn.com","site.api.espn.com"):
                    continue
                try:item=fetch_json(pointer)
                except Exception:continue
            resolved.append(item)
        odds=_espn_1x2(resolved)
    except Exception:odds=None
    with ESPN_ODDS_LOCK:ESPN_ODDS_MEMORY[key]=(now,odds)
    return odds

class TipScreen(BaseScreen):
    # ESPN fixtures always load independently from API-Football quota.
    # ESPN odds (scoreboard then ESPN Core) are opportunistic, never invented.
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("TIPPSCHEIN | ESPN + ECHTE QUOTEN",
                   ["BLAU: Spiele und Quoten laden","GRUEN: Ligen waehlen"],
                   "OK: Tipp 1/X/2/Aus | Erste Zeile: Mein Schein | GELB: 10/15")
        self.games=[];self.quotes={};self.odds_error="";self.last_checked="";self.busy=False
        self.result=None;self.view10=False;self.selected=set();self.choices={};self.stake=10.0
        self.visible_games=[];self.timer=eTimer();self.timer.callback.append(self.show_results)
        self.onClose.append(self.timer.stop)
    def green(self):self.session.open(TipLeagueScreen)
    def yellow(self):self.view10=not self.view10;self.render()
    def choose(self):
        i=self["menu"].getSelectedIndex()
        # First selectable row opens the accumulated ticket at CHF 10 stake.
        if i==0:
            self.session.open(TipSlipScreen,self.games,self.quotes,self.selected,self.choices,self.stake)
            return
        i-=1
        if not (0<=i<len(self.visible_games)):return
        g=self.visible_games[i];ident=g["id"]
        available=self.quotes.get(ident) or {}
        choices=("1","X","2")
        if ident not in self.selected:
            if len(self.selected)>=(10 if self.view10 else 15):
                self["hint"].setText("Maximal %d Spiele: zuerst einen Tipp entfernen"%(10 if self.view10 else 15))
                return
            self.selected.add(ident)
            # Standard 1/X/2 selection: first OK always selects home win (1).
            # Following OK presses switch to X, then 2, then deselect.
            self.choices[ident]="1"
        else:
            current=self.choices.get(ident,"1")
            i_next=choices.index(current)+1 if current in choices else 0
            if i_next==len(choices):
                self.selected.discard(ident);self.choices.pop(ident,None)
            else:self.choices[ident]=choices[i_next]
        self.render()
        try:self["menu"].moveToIndex(i+1)  # first row is the ticket
        except Exception:pass
    def blue(self):
        if self.busy:return
        self.busy=True;self.result=None;self.odds_error=""
        self["menu"].setList(["Lade ESPN-Spiele (OHNE API-Football) ..."])
        self.timer.start(300,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def fetch(self):
        if not tip_codes:
            self.result=([],{},"Bitte zuerst GRUEN: Ligen waehlen")
            return
        # Up to seven dates, selected leagues, parallel calls; shared get_games cache.
        # Never trigger API-Football (daily limit exhausted on the user's box).
        schedule=[];failed=0
        def fetch_days(day_range):
            nonlocal failed
            jobs=[(code,(datetime.now()+timedelta(days=d)).strftime("%Y%m%d"))
                  for code in sorted(tip_codes) for d in day_range]
            with ThreadPoolExecutor(max_workers=7) as pool:
                pending=[pool.submit(get_games,code,day) for code,day in jobs]
                for future in as_completed(pending):
                    try:
                        for g in future.result():
                            if g.get("state")=="pre" and g.get("home") and g.get("away"):
                                schedule.append(g)
                    except Exception:failed+=1
            return len(jobs)
        total_jobs=fetch_days(range(4))
        # Avoid hammering ESPN unnecessarily if the current weekend suffices.
        if len(schedule)<15:total_jobs+=fetch_days(range(4,7))
        schedule.sort(key=lambda g:g.get("date") or "")
        unique={}
        for g in schedule:
            unique[g.get("league", "")+":"+g["id"]]=g
        games=list(unique.values())[:50]
        quotes={g["id"]:g["market_odds"] for g in games if g.get("market_odds")}
        # For fixtures not carrying embedded odds, query a limited number of
        # ESPN core odds pages, in parallel, with a 2h in-memory negative cache.
        missing=[g for g in games if g["id"] not in quotes][:18]
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures={pool.submit(_odds_core_one,g):g for g in missing}
            for future in as_completed(futures):
                try:
                    price=future.result()
                    if price:quotes[futures[future]["id"]]=price
                except Exception:pass
        if not games:
            status=("ESPN nicht erreichbar" if failed==total_jobs else
                    "Keine kommenden Partien in den gewaehlten Ligen (7 Tage)")
        else:
            status="%d Spiele | %d mit echten ESPN-Quoten | %d ESPN-Abfragen fehlgeschlagen"%(len(games),len(quotes),failed)
        self.result=(games,quotes,status)
    def show_results(self):
        if self.result is None:return
        self.timer.stop();self.busy=False
        self.games,self.quotes,self.last_checked=self.result;self.result=None
        valid=set(g["id"] for g in self.games)
        self.selected.intersection_update(valid)
        self.render()
    def render(self):
        max_tips=10 if self.view10 else 15
        self["heading"].setText("TIPPSCHEIN | %d TIPPS | ESPN (OHNE API-LIMIT)"%max_tips)
        self.visible_games=self.games[:50]
        if not self.games:
            self["menu"].setList(["BLAU: Spiele laden",self.last_checked or "GRUEN: Ligen waehlen"])
            self["hint"].setText(self.last_checked or "BLAU: Laden | GRUEN: Ligen")
            return
        lines=[];total=1.0;quoted=0
        for g in self.visible_games:
            ident=g["id"];market=self.quotes.get(ident)
            pick=self.choices.get(ident)
            if pick and ident in self.selected:
                if market and pick in market:
                    quote=market[pick];total*=quote;quoted+=1
                    right="TIPP %s @ %.2f"%(pick,quote)
                else:right="TIPP %s (ohne Quote)"%pick
            elif market:
                right="1 %.2f | X %.2f | 2 %.2f"%(market["1"],market["X"],market["2"])
            else:right="Keine Wettquote vorhanden"
            lines.append(("★" if ident in self.selected else "☆")+" "+kickoff_ch(g.get("date"))+" "+g["home"]+" - "+g["away"]+" | "+right)
        # Put the ticket first: visible without scrolling through 50 fixtures.
        lines.insert(0,"★ MEIN TIPPSCHEIN ANZEIGEN | %d ausgewaehlt | CHF 10 Einsatz"%len(self.selected))
        self["menu"].setList(lines)
        count=len(self.selected)
        if count and count==quoted:
            self["hint"].setText("%d/%d Tipps | Kombiquote %.2f | Einsatz CHF %.2f | rechnerisch CHF %.2f"%(
                count,max_tips,total,self.stake,total*self.stake))
        elif count:
            self["hint"].setText("%d/%d Tipps | %d davon mit echten Quoten; keine Gesamtquote moeglich"%(count,max_tips,quoted))
        else:
            self["hint"].setText("Erste Zeile: Tippschein | OK auf Spiel: Tipp 1/X/2/Aus")

class TipSlipScreen(BaseScreen):
    # Sporttip-inspired readable two-column TV slip; all amounts are simulations.
    skin="""<screen name="GoalAlertTicket" position="center,center" size="1120,660" flags="wfNoBorder" backgroundColor="#07162F">
    <widget name="theme_bg" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/ga_tip.png" position="0,0" size="1120,660" zPosition="0" alphatest="off" />
    <widget name="heading" position="317,30" size="755,42" font="Regular;27" foregroundColor="#E2F7FF" transparent="1" zPosition="2" />
    <widget name="ticket_sub" position="42,93" size="1034,40" font="Regular;24" foregroundColor="#FFD966" transparent="1" zPosition="2" />
    <widget name="ticket_left" position="47,177" size="501,286" font="Regular;21" foregroundColor="#FFFFFF" transparent="1" zPosition="2" />
    <widget name="ticket_right" position="574,177" size="496,286" font="Regular;21" foregroundColor="#FFFFFF" transparent="1" zPosition="2" />
    <widget name="ticket_totals" position="44,520" size="1032,84" font="Regular;25" foregroundColor="#8DFFC3" transparent="1" zPosition="2" />
    <widget name="hint" position="43,610" size="1030,35" font="Regular;18" foregroundColor="#BDDFFF" transparent="1" zPosition="2" />
    <widget name="menu" position="0,0" size="1,1" itemHeight="1" font="Regular;1" foregroundColor="#07162F" backgroundColor="#07162F" />
    </screen>"""
    def __init__(self,session,games,quotes,selected,choices,stake=10.0):
        BaseScreen.__init__(self,session)
        self.setup("MEIN TIPPSCHEIN | KOMBI",[],"EXIT: Zurueck | Nur Beispielrechnung, keine Wettabgabe")
        self["ticket_sub"]=Label("KOMBI | 1 / X / 2 | CHF %.2f Einsatz"%stake)
        self["ticket_left"]=Label("")
        self["ticket_right"]=Label("")
        self["ticket_totals"]=Label("")
        self.render_ticket(games,quotes,selected,choices,stake)
    def render_ticket(self,games,quotes,selected,choices,stake):
        import math
        picked=[g for g in games if g.get("id") in selected]
        rows=[];total=1.0;complete=bool(picked)
        for i,g in enumerate(picked,1):
            pick=choices.get(g.get("id"),"?")
            odd=(quotes.get(g.get("id")) or {}).get(pick)
            if not isinstance(odd,(float,int)) or not math.isfinite(odd) or odd<=1:
                complete=False
                odd_txt="Quote fehlt"
            else:
                total*=odd;odd_txt="%.2f"%odd
            line="%02d | %s - %s"%(i,g.get("home","?"),g.get("away","?"))
            # One match + pick/odds per line, max 15 tips across 2 columns.
            if len(line)>43:line=line[:40]+"..."
            rows.append(line[:33]+" | %s @ %s"%(pick,odd_txt))
        if not rows:rows=["Keine Tipps ausgewaehlt"]
        self["ticket_left"].setText("\n".join(rows[:8]))
        self["ticket_right"].setText("\n".join(rows[8:15]))
        if complete:
            gross=round(stake*total+1e-8,2)
            self["ticket_totals"].setText("Kombiquote: %.2f  |  Einsatz: CHF %.2f\nAuszahlung: CHF %.2f  |  Reingewinn: CHF %.2f"%(total,stake,gross,gross-stake))
        else:
            self["ticket_totals"].setText("Einsatz: CHF %.2f  |  %d Tipps\nKeine Gesamtquote - eine oder mehrere Quoten fehlen"%(stake,len(picked)))
    def choose(self):pass

def build_tip_slip(games,quotes,selected,choices,stake=10.0):
    """Return (visible rows, summary, number of tips). Pure for easy testing."""
    import math
    picked=[g for g in games if g.get("id") in selected]
    if not picked:return (["Noch keine Tipps ausgewaehlt.",
                           "Zurueck und eine Begegnung mit OK markieren.",
                           "OK wechselt jeweils: 1 -> X -> 2 -> Aus"],
                          "Einsatz CHF %.2f"%stake,0)
    lines=["EINSATZ: CHF %.2f | %d SPIELE"%(stake,len(picked))]
    total=1.0;complete=True
    for idx,g in enumerate(picked,1):
        code=choices.get(g.get("id"),"")
        market=quotes.get(g.get("id")) or {}
        price=market.get(code)
        if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=1:
            complete=False
            odds_str="Quote fehlt"
        else:
            total*=price
            odds_str="Quote %.2f"%price
        lines.append("%d. %s - %s | %s | %s"%(idx,g.get("home","?"),g.get("away","?"),code or "?",odds_str))
    if complete:
        gross=round(stake*total+1e-8,2)
        profit=round(gross-stake,2)
        lines.extend(["--------------------------------", "GESAMTQUOTE: %.2f"%total,
                      "MOEGLICHE AUSZAHLUNG: CHF %.2f"%gross,
                      "MOEGLICHER REINGEWINN: CHF %.2f"%profit,
                      "Nur falls alle Tipps richtig sind; ohne Gewaehr."])
        return lines,"Gesamt %.2f | CHF %.2f Auszahlung"%(total,gross),len(picked)
    lines.extend(["--------------------------------", "Keine berechenbare Gesamtquote:",
                  "Mindestens eine Auswahl hat keine gueltige Quote."])
    return lines,"Quote unvollstaendig",len(picked)

def _parse_1x2_odds(rows):
    # API-Football odds?fixture=N&bet=1 -> response[*].bookmakers[*].bets[*].values
    for match in rows or []:
        for book in (match.get("bookmakers") or []):
            for bet in (book.get("bets") or []):
                if str(bet.get("id"))!="1" and str(bet.get("name") or "").lower() not in ("match winner","1x2"):
                    continue
                vals={}
                for outcome in (bet.get("values") or []):
                    name=str(outcome.get("value") or "").strip().lower()
                    mapping={"home":"1","draw":"X","away":"2","1":"1","x":"X","2":"2"}
                    kind=mapping.get(name)
                    if not kind:continue
                    try:price=float(outcome.get("odd"))
                    except Exception:continue
                    if 1.0<=price<=1000:vals[kind]=price
                if all(x in vals for x in ("1","X","2")):
                    return vals
    return None

class DiagnosticsScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("GOALALERT | VERBINDUNGSTEST",["BLAU: Jetzt testen"],"BLAU: ESPN, LiveOnSat, API-Football testen")
        self.timer=eTimer();self.timer.callback.append(self.update);self.onClose.append(self.timer.stop)
        self.result=None;self.busy=False;self.blue()
    def choose(self):self.blue()
    def blue(self):
        if self.busy:return
        self.busy=True;self.result=None;self["menu"].setList(["Teste die Quellen von dieser Vu+ aus ..."])
        self.timer.start(300,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def fetch(self):
        results=[]
        tests=[("ESPN Spiele","https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
               ("LiveOnSat TV","https://www.liveonsat.com/2day.php")]
        for name,url in tests:
            try:
                req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req,timeout=8) as r:
                    data=r.read(140000)
                    if name.startswith("LiveOnSat") and b" v " not in data and b"Football" not in data:
                        raise ValueError("Spielplan-Format unklar")
                    results.append(name+": OK (HTTP %s)"%r.getcode())
            except Exception as e:results.append(name+": FEHLER "+str(e)[:65])
        if api_key():
            try:
                r=api_request("fixtures",{"date":datetime.now().strftime("%Y-%m-%d")})
                results.append("API-Football: OK")
            except Exception as e:results.append("API-Football: "+str(e)[:80])
        else:results.append("API-Football: Kein Schluessel hinterlegt")
        try:
            fixture=get_games("eng.1",datetime.now().strftime("%Y%m%d"))
            if fixture:
                have=sum(bool(g.get("market_odds")) for g in fixture)
                results.append("ESPN-Quoten: %d/%d Partien im Spielplan"%(have,len(fixture)))
            else:results.append("ESPN-Quoten: heute keine EPL-Spiele")
        except Exception as e:results.append("ESPN-Quoten-Test: "+str(e)[:55])
        results.append("Tippschein laeuft ohne API-Football; Quote wenn ESPN sie liefert")
        import shutil
        players=[x for x in ('gst-launch-1.0','gst-play-1.0','aplay','ffplay','mpv','paplay') if shutil.which(x)]
        results.append('Audio: '+(', '.join(players) if players else 'KEIN unterstützter Player erkannt'))
        results.append('Ton-Test unter GOALALERT: TEST-TORALARM (blau)')
        self.result=results
    def update(self):
        if self.result is None:return
        self.timer.stop();self.busy=False
        self["menu"].setList(self.result);self.result=None

LOGO_CACHE="/etc/enigma2/goalalert-logos-v67"
def cached_logo(url):
    # ESPN, API-Football and TheSportsDB HTTPS crest URLs.
    if not url or not url.startswith("https://"):return None
    import hashlib
    name=hashlib.sha256(url.encode("utf-8")).hexdigest()+".png"
    path=os.path.join(LOGO_CACHE,name)
    if os.path.isfile(path):
        try:
            with open(path,"rb") as old:
                hdr=old.read(24)
            if os.path.getsize(path)>100 and hdr.startswith(b"\x89PNG\r\n\x1a\n") and hdr[12:16]==b"IHDR":
                with open(path,'rb') as chk:
                    chk.seek(-12,os.SEEK_END)
                    trailer=chk.read(12)
                if trailer[4:8]==b'IEND':return path
        except Exception:pass
        try:os.unlink(path)
        except Exception:pass
    try:
        if not os.path.isdir(LOGO_CACHE):os.makedirs(LOGO_CACHE)
        req=urllib.request.Request(url,headers={"User-Agent":"GoalAlertTV/5.6"})
        with urllib.request.urlopen(req,timeout=8) as response:
            data=response.read(1500001)
        if len(data)>1500000:
            _crest_log('Originalbild zu gross: %d Bytes'%len(data))
            return None
        # Validate enough PNG structure to avoid caching HTTP placeholder pages,
        # incomplete images, or a JPEG renamed to PNG on Enigma2.
        if len(data)>100 and data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16]==b"IHDR":
            import struct
            width,height=struct.unpack(">II",data[16:24])
            # Do not accept truncated PNG files as valid cached crests.
            if 16<=width<=4096 and 16<=height<=4096 and data[-12:-8]==b'\x00\x00\x00\x00' and data[-8:-4]==b'IEND':
                with open(path,"wb") as f:f.write(data)
                return path
            _crest_log('Ungueltiger PNG-Datensatz (%d Bytes)'%len(data))
        # Convert JPEG/WebP/SVG only if a compatible decoder is installed.
        # Never save a JPEG under a .png filename.
        try:
            from PIL import Image
            from io import BytesIO
            im=Image.open(BytesIO(data))
            im.thumbnail((256,256))
            im.convert("RGBA").save(path,"PNG")
            return path
        except Exception:
            return None
    except Exception as exc:
        _crest_log('Wappen-Download fehlgeschlagen: '+type(exc).__name__)
        return None

class CrestTestScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup("ECHTE VEREINSWAPPEN PRUEFEN",["Lade reale Mannschaftswappen ..."],
                   "Vorschau ohne Ball- oder Demografiken")
        self.timer=eTimer();self.timer.callback.append(self.update);self.onClose.append(self.timer.stop)
        self.pending=None;self.timer.start(300,False)
        threading.Thread(target=self.fetch,daemon=True).start()
    def choose(self):
        if getattr(self,"preview",None):
            g,h,a=self.preview
            self.session.open(CrestPreviewScreen,g,h,a)
    def fetch(self):
        info=None
        for offset in range(4):
            try:
                games=get_games(config.plugins.goalalert32.league.value,(datetime.now()+timedelta(days=offset)).strftime("%Y%m%d"))
                for g in games:
                    if g.get("home_logo") or g.get("away_logo"):
                        home=cached_logo(g.get("home_logo"))
                        away=cached_logo(g.get("away_logo"))
                        info=(g,home,away)
                        if home or away:break
                if info and (info[1] or info[2]):break
            except Exception:pass
        self.pending=info or False
    def update(self):
        if self.pending is None:return
        self.timer.stop()
        if not self.pending:
            self["menu"].setList(["Keine Partie mit abrufbaren Vereinswappen gefunden.",
                                  "Es werden keine Testgrafiken vorgetaeuscht."])
            return
        g,h,a=self.pending
        self.preview=(g,h,a) if (h or a) else None
        self["menu"].setList(["Partie: "+g["home"]+" - "+g["away"],
                              "Heim: "+("Originaldatei geladen" if h else "Kein Wappen geladen"),
                              "Gast: "+("Originaldatei geladen" if a else "Kein Wappen geladen"),
                              "OK: Reale Wappen bildlich ansehen" if self.preview else "Kein Wappen zum Anzeigen",
                              "Keine Fussball-Ball-Grafik als Ersatz!"])
        self["hint"].setText("OK: Wappenvorschau | EXIT: Zurueck" if self.preview else "Keine Bilder abgerufen")

class CrestPreviewScreen(Screen):
    # No bundled ball, demo or '?': both images come from the selected game.
    skin="""<screen name="CrestPreviewScreen" position="center,center" size="980,420" flags="wfNoBorder" backgroundColor="#102536">
    <widget name="title" position="30,15" size="920,70" font="Regular;30" foregroundColor="#FFFFFF" backgroundColor="#102536" />
    <widget name="homelabel" position="30,90" size="435,50" font="Regular;25" foregroundColor="#FFFFFF" backgroundColor="#102536" />
    <widget name="awaylabel" position="510,90" size="435,50" font="Regular;25" foregroundColor="#FFFFFF" backgroundColor="#102536" />
    <widget name="homecrest" position="145,150" size="185,185" alphatest="on" />
    <widget name="awaycrest" position="640,150" size="185,185" alphatest="on" />
    <widget name="hint" position="30,365" size="920,45" font="Regular;21" foregroundColor="#B9C8D8" backgroundColor="#102536" />
    </screen>"""
    def __init__(self,session,game,home_path,away_path):
        self.skin=_goalalert_hd_skin(type(self).skin)
        Screen.__init__(self,session)
        self.paths=(home_path,away_path)
        self.decoders=[]
        self["title"]=Label("ORIGINALWAPPEN - VOLLSTAENDIG")
        self["homelabel"]=Label(game.get("home", "Heim"))
        self["awaylabel"]=Label(game.get("away", "Gast"))
        self["hint"]=Label("Bild fehlt = keine Datei | EXIT: Zurueck")
        self["homecrest"]=Pixmap();self["awaycrest"]=Pixmap()
        self["actions"]=ActionMap(["OkCancelActions"],{"ok":self.close,"cancel":self.close},-1)
        self.onLayoutFinish.append(self.display)
    def display(self):
        for widget,path in zip(("homecrest","awaycrest"),self.paths):
            if not path or not os.path.isfile(path):continue
            # ePicLoad scales the ORIGINAL PNG into the allocated 185px square.
            # Direct LoadPixmap put a 500px asset into a 185px widget and cropped it.
            side=int(round(185*_goalalert_ui_scale()))
            if self.render_scaled(widget,path,side,side):continue
            self["hint"].setText("Bilddecoder fehlt: Grosses Wappen kann nicht sicher skaliert werden")
    def render_scaled(self,widget,path,width,height):
        try:
            dec=ePicLoad()
            def ready(info=None,loader=dec,target=widget):
                try:
                    pix=loader.getData()
                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                except Exception as exc:
                    _crest_log('Wappenvorschau Decode: '+str(exc)[:100])
            dec.PictureData.get().append(ready)
            dec.setPara((width,height,1,1,False,1,"#00000000"))
            self.decoders.append((dec,ready))
            dec.startDecode(path)
            return True
        except Exception:return False

def preload_favorite_crests(game):
    # Asynchronous prefetch; neither sender UI nor goal popup waits for network.
    if not isinstance(game,dict):return
    urls=[game.get('home_logo'),game.get('away_logo')]
    urls=[u for u in urls if u and str(u).startswith('https://')]
    if not urls:return
    def run():
        for url in urls:
            try:cached_logo(url)
            except Exception:pass
    threading.Thread(target=run,daemon=True).start()

class GoalIntroScreen(Screen):
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


class GoalPopup(Screen):
    """Blue goal notification with sound; green scorer update without sound."""
    # Compact by default. The 720p geometry is rendered at the native skin
    # resolution; on a 1080p OpenATV skin it scales to 1.5x automatically.
    @staticmethod
    def _make_skin(kind, size_setting):
        presets={'mini':(520,90,43),'compact':(640,104,51),'normal':(780,122,61)}
        setting=size_setting if size_setting in presets else 'compact'
        width,height,crest=presets[setting]
        px=lambda n:max(1,int(round(n*width/640.0)))
        py=lambda n:max(1,int(round(n*height/104.0)))
        font=lambda n:max(13,int(round(n*min(width/640.0,height/104.0))))
        name_width=px(185)
        second_x=width-px(74)-name_width
        variant=('_'+setting) if setting!='compact' else ''
        theme='ga_popup_'+('scorer' if kind=='scorer' else 'goal')+variant+'.png'
        color=('#FF718B' if kind in ('cancel','redcard') else ('#94FFD8' if kind=='scorer' else '#FFDC82'))
        root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
        # The assets are background visuals only; all scores and names remain
        # real runtime labels, not static/fake data in an image.
        return '''<screen name="GoalPopup" position="center,18" size="{w},{h}" flags="wfNoBorder" transparent="1" backgroundColor="transparent">
          <widget name="theme_bg" pixmap="{root}{theme}" position="0,0" size="{w},{h}" zPosition="0" transparent="1" alphatest="blend" />
          <widget name="homecrest" position="{hc_x},{hc_y}" size="{cr},{cr}" alphatest="blend" transparent="1" zPosition="3" />
          <widget name="home_name" position="{hn_x},{hn_y}" size="{nw},{nh}" font="Regular;{namefont}" foregroundColor="#EAF8FF" transparent="1" zPosition="3" />
          <widget name="score_home" position="{lh_x},{sc_y}" size="{cw},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" zPosition="3" />
          <widget name="score_separator" position="{colon_x},{sc_y}" size="{colon_w},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#99E6FF" transparent="1" zPosition="3" />
          <widget name="score_away" position="{rh_x},{sc_y}" size="{cw},{sh}" font="Regular;{scorefont}" halign="center" valign="center" foregroundColor="#FFFFFF" transparent="1" zPosition="3" />
          <widget name="away_name" position="{an_x},{an_y}" size="{nw},{nh}" font="Regular;{namefont}" foregroundColor="#EAF8FF" transparent="1" zPosition="3" />
          <widget name="awaycrest" position="{ac_x},{hc_y}" size="{cr},{cr}" alphatest="blend" transparent="1" zPosition="3" />
          <widget name="msg" position="{msg_x},{msg_y}" size="{msg_w},{msg_h}" font="Regular;{msgfont}" foregroundColor="{color}" transparent="1" zPosition="3" />
          <widget name="ball" position="0,0" size="1,1" alphatest="on" zPosition="1" />
        </screen>'''.format(w=width,h=height,root=root,theme=theme,cr=crest,
            hc_x=px(14),hc_y=py(22),
            hn_x=px(73),hn_y=py(36),nw=name_width,nh=py(31),namefont=font(20),
            lh_x=px(260),sc_y=py(27),cw=px(50),sh=py(38),scorefont=font(29),
            colon_x=px(310),colon_w=px(20),rh_x=px(330),
            an_x=second_x,an_y=py(36),ac_x=width-px(14)-crest,
            msg_x=px(85),msg_y=py(77),msg_w=width-px(170),msg_h=py(22),msgfont=font(16),color=color)
    def __init__(self,session,message,duration,logo=None,sound=True,away_logo=None,kind='goal',home_url=None,away_url=None,game=None):
        self.skin=_goalalert_hd_skin(self._make_skin(kind,config.plugins.goalalert32.popup_size.value))
        Screen.__init__(self,session)
        # Real team names and current score from the matching fixture only.
        game=game if isinstance(game,dict) else {}
        home_name=str(game.get('home') or 'GOALALERT')
        away_name=str(game.get('away') or 'TEST')
        self['home_name']=Label(home_name[:15])
        self['away_name']=Label(away_name[:15])
        # Three independently centered score labels avoid alignment drift for
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
        self['score_away']=Label(away_score)
        if kind=='scorer':
            footer=message.split('| TORSCHUETZE: ')[-1] if '| TORSCHUETZE: ' in message else message
            footer='TORSCHUETZE: '+footer
        else:
            footer=message.split('|')[0] if '|' in message else message
        self['msg']=Label(footer[:74])
        self['theme_bg']=Pixmap()
        self['ball']=Pixmap()
        self['homecrest']=Pixmap()
        self['awaycrest']=Pixmap()
        self.duration=(3 if kind in ('cancel','redcard') else (max(7,int(duration)) if kind=='goal' and (home_url or away_url) else max(2,int(duration))))
        self.logo_path=logo
        self.away_logo_path=away_logo
        self.logo_urls=(home_url,away_url)
        self.crest_size=self._crest_size()
        self.crests_loaded=set()
        self.crest_attempts=0
        self.crest_retry=eTimer()
        self.crest_retry.callback.append(self.refresh_crests)
        self.sound=(bool(sound) and kind=='goal')
        self.decoders=[]
        self.displayed=False
        self.timer=eTimer()
        self.timer.callback.append(self.dismiss)
        self.onShown.append(self.display)  # once only; old code did it twice
        self.onClose.append(self.timer.stop)
        self.onClose.append(self.crest_retry.stop)
    def _crest_size(self):
        return {'mini':43,'compact':51,'normal':61}.get(
            config.plugins.goalalert32.popup_size.value,51)
    def load_png(self,widget,path,w,h,placeholder=False):
        root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
        if widget=='ball' and not path:path=root+'ball.png'
        if not path or not os.path.isfile(path):return
        try:
            decoder=ePicLoad()
            def ready(info=None,loader=decoder,target=widget):
                try:
                    pix=loader.getData()
                    if placeholder and target in self.crests_loaded:
                        return
                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                        if not placeholder:
                            self.crests_loaded.add(target)
                    elif not placeholder:
                        _crest_log('Wappen-Decoder: keine Bilddaten fuer '+target)
                except Exception as exc:
                    _crest_log('Wappen-Decoderfehler: '+str(exc)[:100])
            decoder.PictureData.get().append(ready)
            decoder.setPara((w,h,1,1,False,1,'#00000000'))
            self.decoders.append((decoder,ready))
            result=decoder.startDecode(path)
            if result not in (None,0):_crest_log('Bild-Decoder Rueckgabe: '+str(result))
        except Exception as exc:_crest_log('Bild-Decoder: '+str(exc)[:110])
    def display(self):
        if self.displayed:return
        self.displayed=True
        root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
        factor=_goalalert_ui_scale()
        # Full-width sports TV scoreboard; no fake ball replaces missing club crests.
        if not any(self.logo_urls):
            _crest_log('Toralarm: keine Vereinswappen-URLs in den Spieldaten')
        # Neutral placeholders appear immediately; only downloaded official
        # club crests can replace them (never invent club identity).
        placeholder=root+'unknown_crest.png'
        if os.path.isfile(placeholder):
            side=int(round(self.crest_size*_goalalert_ui_scale()))
            for w in ('homecrest','awaycrest'):
                self.load_png(w,placeholder,side,side,placeholder=True)
        self.refresh_crests()
        if self.sound:
            # Playback stays external so the live TV service is never stopped.
            self.play_sound(root)
        self.timer.start(self.duration*1000,True)
    def refresh_crests(self):
        # Thread only downloads bytes. Pixmap operations ALWAYS run in GUI thread.
        self.crest_attempts+=1
        missing=False
        for widget,path,url in (('homecrest',self.logo_path,self.logo_urls[0]),
                                ('awaycrest',self.away_logo_path,self.logo_urls[1])):
            cached=path if path and os.path.isfile(path) else _cached_logo_local(url)
            if cached and widget not in self.crests_loaded:
                sz=int(round(self.crest_size*_goalalert_ui_scale()))
                self.load_png(widget,cached,sz,sz)
            elif not cached and url:
                missing=True
        if missing and self.crest_attempts<=16:
            if not getattr(self,'crest_fetch_started',False):
                self.crest_fetch_started=True
                def download_missing():
                    for url in self.logo_urls:
                        if url and not _cached_logo_local(url):cached_logo(url)
                threading.Thread(target=download_missing,daemon=True).start()
            self.crest_retry.start(350,True)
        elif missing:
            _crest_log('Toralarm-Wappen: Download/Decoder nicht rechtzeitig bereit')
    def play_sound(self,root):
        from .goalalert_audio import cheer_path, play
        play(cheer_path(root,config.plugins.goalalert32.cheer_style.value))
    def dismiss(self):
        try:self.close()
        except Exception:pass

AUDIO_LOG='/etc/enigma2/goalalert_audio.log'
def _play_goal_sound(path):
    from .goalalert_audio import play
    return play(path)


def _audio_log(line):
    try:
        with open(AUDIO_LOG,'a') as f:f.write('%s: %s\n'%(datetime.now().isoformat(),line))
    except Exception:pass

class AudioStatusScreen(BaseScreen):
    def __init__(self,session):
        BaseScreen.__init__(self,session)
        self.setup('TORJUBEL | AUDIO-DIAGNOSE', [],
                   'OK: Testen | GELB: Jubel wechseln | BLAU: Protokoll aktualisieren')
        self.blue()
    def blue(self):
        import shutil
        names=['gst-launch-1.0','gst-play-1.0','aplay','ffplay','mpv','paplay']
        available=[n for n in names if shutil.which(n)]
        choice=config.plugins.goalalert32.cheer_style.value
        labels={"classic":"Klassisch","stadium":"Stadion-Echo","double":"Doppeljubel","short":"Kurzer Tor-Ruf"}
        rows=['OK: TORJUBEL TESTEN | '+labels.get(choice,choice),
              'Audioplayer: '+(', '.join(available) if available else 'KEINER GEFUNDEN'),
              'TV-Ton an: PCM-Mischung benoetigt. Bei Stille AC3-Downmix pruefen.',
              'ALSA: '+('vorhanden' if os.path.isdir('/dev/snd') else 'kein /dev/snd erkannt')] 
        try:
            with open(AUDIO_LOG) as f:rows+=['LOG: '+r.strip()[-125:] for r in f.readlines()[-4:]]
        except Exception:rows.append('Noch kein Audio-Protokoll')
        self['menu'].setList(rows)
    def choose(self):
        if self['menu'].getSelectedIndex()==0:
            from .goalalert_audio import cheer_path
            path=cheer_path('/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/',
                            config.plugins.goalalert32.cheer_style.value)
            if _play_goal_sound(path):
                self['hint'].setText('Audio gestartet; BLAU: Status pruefen. Hoerbarkeit nur am TV pruefbar.')
            else:self['hint'].setText('Kein Player erreichbar; BLAU: Fehler anzeigen')
    def yellow(self):
        c=config.plugins.goalalert32.cheer_style
        values=["classic","stadium","double","short"]
        c.value=values[(values.index(c.value)+1)%len(values)]
        c.save();configfile.save()
        self.blue()
        self["hint"].setText("Jubel gespeichert | OK: Bei laufendem TV-Ton testen")


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

class Monitor:
    def __init__(self):
        self.timer=None
        self.session=None
        self.busy=False
        self.results=None
        self.last={}
        self.lock=threading.Lock()
        self.initialized=False
        self.popup=None
        self.dismiss_timer=None
        self.goal_update=None
        self.announced_details=set()
        self.preload_running=False
        self.pending_corrections={}
        self.red_card_seen={}
        self.red_card_results=None
        self.red_card_busy=False
    def start(self,session):
        if self.timer:return
        self.session=session
        self.timer=eTimer()
        self.timer.callback.append(self.tick)
        self.timer.start(5000,False)
        self.tick()
    def is_favorite(self,g):
        if str(g.get('id')) in favorites:return True
        for fav in favorites.values():
            if (fav.get('home')==g.get('home') and fav.get('away')==g.get('away')):
                return True
        return False
    def tick(self):
        with self.lock:
            result=self.results;self.results=None
            card_result=self.red_card_results;self.red_card_results=None
            update=self.goal_update;self.goal_update=None
            test=getattr(self,'pending_test_goal',None)
            test_kind=getattr(self,'pending_test_kind','goal')
            self.pending_test_goal=None
        if test is not None:
            if test is False:
                _crest_log('Test-Popup: keine Live-Spiel-Wappen verfuegbar')
                self.show_goal('TEST: Wappen fehlen, siehe Wappen-Diagnose',kind=test_kind)
            else:
                title='TEST: TORSCHUETZE (OHNE TON)' if test_kind=='scorer' else 'TEST: ECHTE WAPPEN | TORALARM'
                self.show_goal(title,test.get('home_logo_file'),test.get('away_logo_file'),
                               kind=test_kind,home_url=test.get('home_logo'),away_url=test.get('away_logo'),game=test)
        if update is not None:
            # Another blue alert takes priority; otherwise show a silent green one.
            k,g,goal_event=update
            event_match,event_side,event_count=k
            current=self.last.get(event_match)
            good=(current is not None and current[0 if event_side=='home' else 1]>=event_count)
            if good and k not in self.announced_details:
                self.announced_details.add(k)
                message="%s - %s | TORSCHUETZE: %s | %s'"%(g.get('home','?'),g.get('away','?'),goal_event.get('scorer','?'),goal_event.get('minute','?'))
                if goal_event.get('assist') not in (None,'','Nicht gemeldet'):
                    message+=' | Vorlage: '+str(goal_event['assist'])
                self.show_goal(message,g.get('home_logo_file'),g.get('away_logo_file'),kind='scorer',home_url=g.get('home_logo'),away_url=g.get('away_logo'),game=g)
        if result is not None:
            if not self.initialized:
                self.last={(str(g.get('league')),str(g['id'])):(g['hs'],g['as']) for g in result}
                self.initialized=True
            else:
                for g in result:
                    key=(str(g.get('league')),str(g['id']))
                    old=self.last.get(key)
                    score=(int(g['hs']),int(g['as']))
                    if old is not None and score!=old and self.is_favorite(g):
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
                    self.last[key]=score
        if card_result is not None:
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
        if not self.busy:
            self.busy=True
            threading.Thread(target=self.fetch,daemon=True).start()
    def enrich_goal(self,g,target):
        # Delayed scorer attribution is sound-free; never guess from another fixture.
        key,side,target_number=target
        for attempt in range(8):
            if attempt:time.sleep(12)
            try:
                events=detailed_events(g)
                for_side=[e for e in events if e.get('side')==side]
                def minute_value(e):
                    import re
                    m=re.search(r'\d+',str(e.get('minute','')))
                    return int(m.group()) if m else 999
                for_side.sort(key=minute_value)
                candidate=for_side[target_number-1] if len(for_side)>=target_number else None
                if candidate and candidate.get('scorer') not in ('Nicht gemeldet','Unbekannt','?',''):
                    with self.lock:self.goal_update=(target,g,candidate)
                    return
            except Exception:pass
    def test_goal(self,kind='goal'):
        # Never present demo logos as real: obtain a real game in a worker.
        # UI is opened in the Enigma2 main thread on the next timer tick.
        with self.lock:
            self.pending_test_goal=None
            self.pending_test_kind=kind if kind in ('goal','scorer') else 'goal'
        if getattr(self,'test_goal_busy',False):return
        self.test_goal_busy=True
        def work():
            selected=None
            try:
                for game in getattr(self,'last_seen_games',[]):
                    if game.get('home_logo') and game.get('away_logo'):
                        selected=dict(game);break
                if not selected:
                    code=config.plugins.goalalert32.league.value
                    for offset in range(4):
                        games=get_games(code,(datetime.now()+timedelta(days=offset)).strftime('%Y%m%d'))
                        selected=next((dict(g) for g in games if g.get('home_logo') and g.get('away_logo')),None)
                        if selected:break
            except Exception as exc:
                _crest_log('Test-Toralarm Spielabruf: '+type(exc).__name__)
            if selected:
                for side in ('home','away'):
                    selected[side+'_logo_file']=cached_logo(selected.get(side+'_logo'))
            with self.lock:
                self.pending_test_goal=selected if selected else False
            self.test_goal_busy=False
        threading.Thread(target=work,daemon=True).start()
    def test_scorer(self):
        self.test_goal(kind='scorer')
    def _popup_closed(self,token):
        if getattr(self,'popup_token',None)==token:
            self.popup=None
    def _after_goal_intro(self,token,details):
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
    def hide_goal(self):
        if self.dismiss_timer is not None:self.dismiss_timer.stop()
        if self.popup is not None:
            popup=self.popup;self.popup=None
            try:popup.close()
            except Exception as exc:_crest_log('Popup-Schliessen: '+str(exc)[:100])
    def fetch_red_cards(self,games):
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
            codes={v.get('league') for v in favorites.values() if v.get('league')}
            day=datetime.now().strftime('%Y%m%d')
            games=[]
            if codes:
                with ThreadPoolExecutor(max_workers=4) as pool:
                    futures=[pool.submit(get_games,code,day) for code in codes]
                    for future in as_completed(futures):
                        try:games.extend(future.result())
                        except Exception:pass
            # Checking the cache is instant; downloading crests must not delay score alerts.
            self.last_seen_games=[dict(x) for x in games if x.get('home_logo') and x.get('away_logo')][:40]
            for g in games:
                g['home_logo_file']=_cached_logo_local(g.get('home_logo'))
                g['away_logo_file']=_cached_logo_local(g.get('away_logo'))
            live=[g for g in games if g.get('state')=='in']
            with self.lock:self.results=live
            if not self.red_card_busy and live:
                self.red_card_busy=True
                threading.Thread(target=self.fetch_red_cards,args=(list(live),),
                                 daemon=True).start()
            if not self.preload_running:
                self.preload_running=True
                def loader():
                    try:
                        for g in games:
                            if self.is_favorite(g):
                                cached_logo(g.get('home_logo'))
                                cached_logo(g.get('away_logo'))
                    finally:self.preload_running=False
                threading.Thread(target=loader,daemon=True).start()
        except Exception as exc:
            self.last_error=str(exc)[:120]
        finally:self.busy=False

def _cached_logo_local(url):
    if not url or not str(url).startswith('https://'):return None
    import hashlib
    name=hashlib.sha256(url.encode('utf-8')).hexdigest()+'.png'
    path=os.path.join(LOGO_CACHE,name)
    try:
        if os.path.getsize(path)<100:return None
        with open(path,'rb') as f:
            if f.read(8)!=b'\x89PNG\r\n\x1a\n':return None
            f.seek(-12,os.SEEK_END)
            if f.read(12)[4:8]!=b'IEND':return None
        return path
    except Exception:return None


def _crest_log(msg):
    try:
        with open('/etc/enigma2/goalalert_wappen.log','a') as f:
            f.write(datetime.now().isoformat()+' '+str(msg)[:180]+'\n')
    except Exception:pass

monitor=Monitor()
def open_plugin(session,**kwargs):
    monitor.start(session)
    session.open(Home)

def open_live_direct(session,**kwargs):
    """Dedicated entry to bind via OpenATV MENU > Settings > Hotkey > Red."""
    monitor.start(session)
    session.open(QuickLiveScreen)
def session_start(reason,session=None,**kwargs):
    if reason==0 and session is not None:monitor.start(session)
def goalalert_mainmenu(menuid,**kwargs):
    # OpenATV passes "mainmenu" to WHERE_MENU providers (also on Vu+).
    if menuid=="mainmenu":
        return [("GoalAlert",open_plugin,"goalalert_mainmenu",42)]
    return []

def Plugins(**kwargs):
    return [
        PluginDescriptor(name="GoalAlert",description="GoalAlert TV Edition",where=PluginDescriptor.WHERE_PLUGINMENU,icon="plugin.png",fnc=open_plugin),
        PluginDescriptor(name="GoalAlert Live",description="LiveScore-Schnellstart fuer rote TV-Taste",where=PluginDescriptor.WHERE_BUTTONSETUP,fnc=open_live_direct),
        PluginDescriptor(name="GoalAlert Hauptmenue",where=PluginDescriptor.WHERE_MENU,fnc=goalalert_mainmenu),
        PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART,fnc=session_start)
    ]
