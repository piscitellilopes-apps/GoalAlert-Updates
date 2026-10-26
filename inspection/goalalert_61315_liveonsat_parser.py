# -*- coding: utf-8 -*-
"""HTML-only LiveOnSat parsing. No imported libraries other than Python stdlib.

Extract data from the site; no network requests in this module. Parse untrusted
HTML conservatively: only match real team-v-team rows followed by a kickoff.
"""
import re
import html
from html.parser import HTMLParser

_PAIR = re.compile(r'^(.{2,90}?)\s+v(?:s)?\.?\s+(.{2,90}?)$', re.I)
_DAY = re.compile(r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\d{1,2}(?:st|nd|rd|th)?\s+',re.I)
_CLOCK = re.compile(r'^ST:\s*(\d{1,2}:\d{2})',re.I)
_LEAGUE = re.compile(r'\b(?:League|Liga|Ligue|Serie [A-C]|Bundesliga|Cup|Pokal|Division|Championship|Champions|Premiership|Ekstraklasa|Primera|Allsvenskan|Superliga|UEFA|AFC|CAF|ML[BS]|National|Friendly|HNL)\b',re.I)
_NOISE=('Please Note','Website Last','Members 1.0','Quick Index','No schedules','Timezone =','Site Map')

class Collector(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self,convert_charrefs=True)
        self.parts=[]
    def handle_data(self,data):
        for piece in re.split(r'[\r\n]+',html.unescape(data)):
            clean=' '.join(piece.split())
            if clean:self.parts.append(clean)

def text_nodes(raw):
    c=Collector()
    c.feed(raw)
    out=[];i=0
    while i<len(c.parts):
        line=c.parts[i]
        # Most common HTML variant: a fixture broken across span/img tags.
        if line.lower().strip() in ('v','vs','v.','vs.') and out and i+1<len(c.parts):
            prev=out.pop();nxt=c.parts[i+1]
            if len(prev)<100 and len(nxt)<100:
                out.append(prev+' v '+nxt)
                i+=2;continue
            out.append(prev)
        if re.search(r'\s+v(?:s)?\.?$',line,re.I) and i+1<len(c.parts):
            line=line+' '+c.parts[i+1]
            i+=1
        if re.match(r'^v(?:s)?\.?\s+',line,re.I) and out and len(out[-1])<90:
            line=out.pop()+' '+line
        # Time may also be split into a label and a span containing the clock.
        if line.upper()=='ST:' and i+1<len(c.parts):
            line+=' '+c.parts[i+1];i+=1
        out.append(line);i+=1
    return out

def parse_schedule(raw, date_filter=None):
    if isinstance(raw,bytes):raw=raw.decode('utf-8','replace')
    lines=text_nodes(raw)
    games=[];day='';league='';current=None;seen=set();after_start=False
    for item in lines:
        if any(item.lower().startswith(x.lower()) for x in _NOISE):
            current=None;after_start=False;continue
        if _DAY.match(item):
            day=item;current=None;after_start=False;continue
        # Reject fragments from other dates if the user selected a specific day.
        pair=_PAIR.match(item)
        if pair:
            home,away=pair.group(1).strip(),pair.group(2).strip()
            # Some website headings have 'v' in the prose, but not an actual match.
            if len(home)>74 or len(away)>74 or '://' in item:continue
            key=(day.lower(),home.lower(),away.lower())
            if key in seen:
                current=None;after_start=False;continue
            seen.add(key)
            current={'day':day or 'Spielplan','league':league,'home':home,'away':away,
                     'time':'--:--','channels':[]}
            games.append(current);after_start=False
            continue
        tm=_CLOCK.match(item)
        if tm and current:
            current['time']=tm.group(1)
            after_start=True
            continue
        # Date/time lines and headings are never television channels.
        if _LEAGUE.search(item) and len(item)<100 and not after_start and not item.startswith(('ST:','http')):
            league=item
            continue
        if current and after_start:
            # A new competition heading terminates the previous station list.
            if _LEAGUE.search(item) and (
                re.search(r'\s+-\s+(?:Week|Round|[Gg]roup|[Qq]uarter|[Ss]emi|[Ff]inal|\d)',item)
                or (item.startswith(('Italian Serie','English Premier','German Bundesliga','UEFA ','Swiss Cup','Spanish La Liga')))
            ) and len(item)<115:
                current=None;after_start=False;league=item;continue
            # Auxiliary badges may be split from the actual station name.
            if item.upper() in ('HD','UHD','4K','FHD') and current['channels']:
                current['channels'][-1]+=' '+item
                continue
            if len(item)<130 and item not in current['channels'] and len(current['channels'])<150:
                if not _CLOCK.match(item) and not _DAY.match(item):
                    current['channels'].append(item)
        elif _LEAGUE.search(item) and len(item)<115:
            league=item
    # Do not include accidental fixture phrases without a time, or stale pages.
    games=[g for g in games if g['time']!='--:--']
    return games


# Shared by desktop/mobile/previous-cache schedules. No clock-based
# start-time cutoff: a fixture never disappears merely because it has started.
def _listed_date(day_heading, local_today):
    from datetime import date
    month_names={"january":1,"february":2,"march":3,"april":4,
       "may":5,"june":6,"july":7,"august":8,"september":9,
       "october":10,"november":11,"december":12}
    match=re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\b",str(day_heading),re.I)
    if not match:return None
    month=month_names.get(match.group(2).lower())
    if not month:return None
    candidates=[]
    for year in (local_today.year-1,local_today.year,local_today.year+1):
        try:candidates.append(date(year,month,int(match.group(1))))
        except ValueError:pass
    return min(candidates,key=lambda d:abs((d-local_today).days)) if candidates else None

def merge_day_schedules(source_lists, day, keep_overnight=False):
    """Combine schedules without losing in-progress fixtures or TV stations.

    source_lists is ordered: current desktop, current mobile, previous cache.
    Returns only the requested local date. For early morning, a caller may
    enable keeping yesterday's late fixtures, which can still be in progress.
    No live/finished state is inferred from kickoff alone.
    """
    from datetime import datetime,timedelta
    if isinstance(day,str):day=datetime.strptime(day,'%Y-%m-%d').date()
    out={};seq=0
    for source in source_lists:
        for g in source or []:
            if not isinstance(g,dict):continue
            home=' '.join(str(g.get('home') or '').split())
            away=' '.join(str(g.get('away') or '').split())
            if not home or not away:continue
            d=_listed_date(g.get('day',''),day)
            if d and d!=day:
                if not keep_overnight or d!=day-timedelta(days=1):continue
                # Previous-day late games are relevant around midnight only.
                clock=str(g.get('time',''))
                try:hh=int(clock.split(':',1)[0])
                except Exception:continue
                if hh<21:continue
            if not d and g.get('day') not in ('','Spielplan'):
                # Ignore unrecognised dates instead of merging next week's games.
                continue
            date_key=d.isoformat() if d else day.isoformat()
            norm=lambda s:re.sub(r'[^a-z0-9]+','',s.casefold())
            key=(date_key,norm(home),norm(away))
            if key not in out:
                obj=dict(g)
                obj['channels']=[]
                obj['_order']=seq;seq+=1
                out[key]=obj
            obj=out[key]
            if not obj.get('league') and g.get('league'):obj['league']=g['league']
            if obj.get('time') in ('','--:--',None) and g.get('time'):obj['time']=g['time']
            existing={s.casefold().strip() for s in obj['channels']}
            for channel in g.get('channels') or []:
                channel=' '.join(str(channel).split())
                if channel and channel.casefold() not in existing and len(obj['channels'])<150:
                    obj['channels'].append(channel)
                    existing.add(channel.casefold())
    def sorting(g):
        t=str(g.get('time',''))
        h,m=(t.split(':',1)+[''])[:2]
        clock=(int(h)*60+int(m)) if h.isdigit() and m.isdigit() else 9999
        return (_listed_date(g.get('day',''),day) or day,clock,g['_order'])
    return [{k:v for k,v in g.items() if k!='_order'} for g in sorted(out.values(),key=sorting)]
