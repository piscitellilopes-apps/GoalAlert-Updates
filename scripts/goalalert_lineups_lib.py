# -*- coding: utf-8 -*-
"""GoalAlert verified ESPN lineup extraction.

Show a starting XI only if the provider marks it as a starter.
If player lists exist but no starter flags have been provided, show the
registered squad with a clear label, never invent starting lineups.
"""
from __future__ import absolute_import

def _name(obj):
    if not isinstance(obj,dict):return ''
    return str(obj.get('displayName') or obj.get('shortName') or obj.get('name') or '').strip()

def _team(group,idx):
    team=group.get('team') if isinstance(group,dict) else {}
    if not isinstance(team,dict):team={}
    return _name(team) or ("HEIM" if idx==0 else "AUSWAERTS")

def _players(group):
    if not isinstance(group,dict):return []
    candidates=(group.get('roster'),group.get('athletes'),group.get('players'),
                group.get('lineup'),group.get('startingXI'))
    for c in candidates:
        if isinstance(c,list) and c:return c
    return []

def _extract(group):
    starters=[]
    squad=[]
    for p in _players(group):
        if not isinstance(p,dict):continue
        athlete=p.get('athlete') or p.get('player') or p
        if not isinstance(athlete,dict):continue
        name=_name(athlete) or _name(p)
        if not name:continue
        nr=str(athlete.get('jersey') or p.get('jersey') or '').strip()
        pos=athlete.get('position') or p.get('position') or ''
        if isinstance(pos,dict):pos=pos.get('abbreviation') or ''
        display=("  "+nr+"  " if nr else "  ")+name[:30]+(" | "+str(pos)[:6] if pos else "")
        marker=p.get('starter',athlete.get('starter',None))
        if marker is True or str(marker).lower() in ('true','1'):
            starters.append(display)
        else:
            squad.append(display)
    return starters[:11],squad[:22]

def format_lineups(payload):
    if not isinstance(payload,dict):return ['Keine bestaetigten Aufstellungen vorhanden.']
    groups=payload.get('rosters') or []
    if not isinstance(groups,list):groups=[]
    if not groups:
        boxscore=payload.get('boxscore') or {}
        groups=boxscore.get('players') or []
    if not isinstance(groups,list):groups=[]
    lines=[]
    for idx,group in enumerate(groups[:2]):
        if not isinstance(group,dict):continue
        starters,squad=_extract(group)
        label=_team(group,idx)
        if starters:
            lines.append('STARTELF | '+label[:35])
            lines.extend(starters)
            if len(starters)<11:
                lines.append('Weitere Startspieler noch nicht bestaetigt')
        elif squad:
            lines.append('KADER (Startelf nicht bestaetigt) | '+label[:22])
            lines.extend(squad[:14])
    if not lines:return ['Fuer dieses Spiel sind noch keine bestaetigten',
                         'Aufstellungen oder Kaderdaten vorhanden.',
                         'BLAU: erneut abrufen']
    return lines

def valid_espn_event_id(value):
    value=str(value or '').strip()
    return value if value.isdigit() and len(value)<=16 else None

def valid_league(value):
    import re
    value=str(value or '').strip()
    return value if re.fullmatch(r'[a-zA-Z0-9._-]{2,45}',value) else None
