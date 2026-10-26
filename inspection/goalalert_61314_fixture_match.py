# -*- coding: utf-8 -*-
"""Shared, conservative fixture matching for GoalAlert and LiveOnSat.

Both the shortcut LiveScore -> fixture -> TV and the main LiveOnSat path
use the same parsed daily schedule. No IPTV data is examined here.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# Genuine club aliases, not generic substring matching against league names.
ALIASES = {
    'as roma':'roma', 'roma as':'roma', 'roma fc':'roma',
    'inter milan':'inter', 'inter milano':'inter',
    'internazionale':'inter', 'internazionale milano':'inter',
    'fc internazionale':'inter', 'fc internazionale milano':'inter',
    'ac milan':'milan', 'milan ac':'milan',
    'paris saint germain':'psg', 'paris st germain':'psg',
    'paris sg':'psg', 'paris s g':'psg',
    'bayern munich':'bayern munchen', 'bayern munchen':'bayern munchen',
    'fc bayern munchen':'bayern munchen',
    'borussia monchengladbach':'monchengladbach',
    'manchester utd':'manchester united', 'man utd':'manchester united',
    'man united':'manchester united', 'man u':'manchester united',
    'manchester u':'manchester united', 'manchester united fc':'manchester united',
    'man united fc':'manchester united',
    'leeds':'leeds united', 'leeds utd':'leeds united',
    'leeds united fc':'leeds united', 'leeds united afc':'leeds united',
    'manchester city fc':'manchester city',
    'atletico de madrid':'atletico madrid',
    'real betis balompie':'real betis',
    'ss lazio':'lazio', 'ssc napoli':'napoli',
    'genoa cfc':'genoa', 'genoa cricket and football club':'genoa',
    'as monaco':'monaco',
    'olympique de marseille':'marseille',
    'olympique lyonnais':'lyon',
    'sporting cp':'sporting lisbon', 'sporting clube de portugal':'sporting lisbon',
    'fc barcelona':'barcelona',
}
STOP_PREFIX = {'fc','ac','as','ssc','sc','cf','afc','fk','sk','sv','cd','rc','us','ud','ss'}
STOP_SUFFIX = {'fc','cf','afc','cfc','sc','ac','fk','calcio','football','club'}
RISK = {'women','woman','fem','feminine','w','u21','u20','u19','u18','u17','u16','reserves','reserve','ii','iii','b','youth'}

def normalized(name):
    s=unicodedata.normalize('NFKD',str(name or '')).encode('ascii','ignore').decode('ascii').lower()
    s=s.replace('&',' and ')
    s=re.sub(r'[^a-z0-9]+',' ',s).strip()
    s=re.sub(r'\bu\s+(1[6-9]|2[0-3])\b', r'u\1', s)
    s=re.sub(r'\s+',' ',s)
    if s in ALIASES:return ALIASES[s]
    words=s.split()
    # Do not discard category suffixes such as U19/Women: protect against wrong match.
    while len(words)>1 and words[0] in STOP_PREFIX:words=words[1:]
    while len(words)>1 and words[-1] in STOP_SUFFIX:words=words[:-1]
    s=' '.join(words)
    return ALIASES.get(s,s)

def team_similarity(a,b):
    a=normalized(a);b=normalized(b)
    if not a or not b:return 0
    if a==b:return 100
    wa,wb=set(a.split()),set(b.split())
    if wa.symmetric_difference(wb) & RISK:return 0
    if a.replace(' ','') == b.replace(' ',''):return 99
    # Expanded official names: all tokens of the short name must appear.
    short,long=(wa,wb) if len(wa)<=len(wb) else (wb,wa)
    if short.issubset(long) and len(''.join(short))>=5 and len(long-short)<=2:
        return 88
    # Minor spelling differences only, with substantial shared team stem.
    similarity=SequenceMatcher(None,a,b).ratio()
    if similarity>=0.88 and (wa & wb) and len(a)>=7 and len(b)>=7:
        return int(similarity*90)
    return 0

def match_fixtures(match,games):
    """Return high-confidence matches only, with clear ties left selectable.

    Require both teams in their proper positions. Dates are already filtered
    by liveonsat_schedule(). No other fixture can be silently substituted.
    """
    scores=[]
    for g in games:
        home=team_similarity(match.get('home'),g.get('home'))
        away=team_similarity(match.get('away'),g.get('away'))
        if min(home,away)<75:continue
        scores.append((home+away,g))
    if not scores:return []
    best=max(x[0] for x in scores)
    # Accept multiple equally plausible same-day listings, don't guess.
    return [g for points,g in scores if points>=best-8]
