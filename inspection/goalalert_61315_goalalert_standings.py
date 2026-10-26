# -*- coding: utf-8 -*-
"""Parse ESPN /apis/v2 soccer standings for GoalAlert.

Actual standings endpoint:
https://site.api.espn.com/apis/v2/sports/soccer/{league}/standings

The /apis/site/v2 variant is a stub, not a standings feed.
Never substitute fake zeroes for missing statistics.
"""
from __future__ import absolute_import

def _number(entry, *keys):
    stats = entry.get("stats") or []
    for key in keys:
        for stat in stats:
            if not isinstance(stat, dict):
                continue
            if stat.get("name") == key or stat.get("type") == key or stat.get("abbreviation") == key:
                value = stat.get("displayValue")
                if value is None or value == "":
                    value = stat.get("value")
                if value is not None and value != "":
                    return str(value)
    return "-"

def parse_standings(data):
    """Return human readable table rows; don't mix separate qualification groups."""
    if not isinstance(data, dict):
        raise ValueError("Tabellendaten ungueltig")
    root = data.get("children") or [data]
    if not isinstance(root, list):
        raise ValueError("Tabellengruppen ungueltig")
    result = []
    seen = set()
    for group in root[:10]:
        if not isinstance(group, dict):
            continue
        standings = group.get("standings") or {}
        entries = standings.get("entries") or group.get("entries") or []
        if not isinstance(entries, list) or not entries:
            continue
        name = group.get("name") or group.get("abbreviation") or data.get("name") or "Tabelle"
        if len(root)>1:
            result.append(str(name)[:48])
        result.append("PL  VEREIN                 SP  TD  PKT")
        for n, row in enumerate(entries[:34], 1):
            if not isinstance(row, dict):
                continue
            team = row.get("team") or {}
            if not isinstance(team, dict):
                continue
            ident = str(team.get("id") or team.get("displayName") or "")
            if ident and ident in seen:
                continue
            if ident:
                seen.add(ident)
            teamname = team.get("shortDisplayName") or team.get("displayName") or team.get("name")
            if not isinstance(teamname, str) or not teamname.strip():
                continue
            rank = _number(row, "rank", "playoffSeed")
            if rank == "-":
                rank = str(n)
            played = _number(row, "gamesPlayed", "GP")
            goal_diff = _number(row, "pointDifferential", "goalDifference", "GD")
            points = _number(row, "points", "PTS")
            result.append("%2s  %-20.20s %3s %4s %4s" %
                          (rank[:2], teamname, played[-3:], goal_diff[-4:], points[-4:]))
    if not result:
        return ["Fuer diesen Wettbewerb sind keine bestaetigten",
                "Ligatabellen abrufbar."]
    return result

def validate_league_code(value):
    import re
    code = str(value or "").strip()
    if not re.match(r"^[a-zA-Z0-9._-]{2,45}$", code):
        raise ValueError("Kein gueltiger Liga-Code fuer die Tabelle")
    return code
