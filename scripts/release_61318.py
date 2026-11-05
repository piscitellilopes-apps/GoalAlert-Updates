#!/usr/bin/env python3
"""GoalAlert 6.13.18: restore fixture-specific TV broadcaster lists.
Do not substitute the complete daily schedule when no fixture is matched.
"""
from pathlib import Path, PurePosixPath
import hashlib, io, tarfile, subprocess, sys, shutil

ROOT=Path(__file__).resolve().parents[1]
VERSION="6.13.18"
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.17_all.ipk"
PIN="7c3dd03e69c62b79a12eb2fcdbd010aaf936ac90aa2f6ccae68c83ec73efbc08"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=PIN:
    raise ValueError("Version 6.13.17 IPK missing or modified")
if DEST.exists(): raise ValueError("Refuse to overwrite source/GoalAlert")
DEST.mkdir(parents=True)
data=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(data),mode="r:xz") as archive:
    for member in archive:
        name=member.name.lstrip("./")
        if not member.isfile() or not name.startswith(PREFIX):continue
        relative=name[len(PREFIX):]
        if not relative or ".." in PurePosixPath(relative).parts or relative.startswith("/"):
            raise ValueError("Unsafe archive entry")
        if "__pycache__" in relative or relative.endswith((".pyc",".log",".m3u",".m3u8")):
            continue
        output=DEST/relative
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(archive.extractfile(member).read())

plugin=DEST/"plugin.py"
source=plugin.read_text(encoding="utf-8")
start=source.index("class LiveOnSatScreen(BaseScreen):")
end=source.index("class IPTVBrowseScreen(BaseScreen):",start)
section=source[start:end]
fallback_start=section.index("            if not self.games:\n")
fallback_end=section.index('            self["heading"].setText("TV-SENDER | "+label[:49])',fallback_start)
old=section[fallback_start:fallback_end]
assert "self.games=games" in old and "Spiel bitte selbst auswaehlen" in old, "Fallback changed unexpectedly"
replacement='''            if not self.games:
                # The red-key -> match -> OK TV path MUST NEVER silently
                # become an unrelated day-wide list of TV fixtures.
                # It is safe to offer the day guide only after a deliberate
                # separate YELLOW press, with clear context.
                from .fixture_match import team_similarity
                reverse=[candidate for candidate in games
                         if min(team_similarity(self.match.get('home'),candidate.get('away')),
                                team_similarity(self.match.get('away'),candidate.get('home')))>=90]
                if len(reverse)==1:
                    self.games=reverse
                else:
                    self.games=[]
                    self['heading'].setText("TV-SENDER | "+label[:49])
                    self['menu'].setList([
                        "BEGEGNUNG: "+label,
                        "Keine bestaetigten TV-Sender fuer diese Partie gefunden.",
                        "BLAU: nur diese Begegnung erneut abfragen.",
                        "GELB: gesamten TV-Spielplan manuell anzeigen.",
                        str(info)[:100]])
                    self['hint'].setText("Keine fremden Spiele als Senderliste | BLAU: Neu | GELB: Alle")
                    return
'''
section=section.replace(old,replacement,1)
# Matched broadcast: show the actual broadcasters (not an intermediate
# fixture list) as the next screen. Merge duplicate source rows but only
# for the already-verified same fixture.
pre='''            self["heading"].setText("TV-SENDER | "+label[:49])'''
new='''            if len(self.games)>1:
                combined=dict(self.games[0])
                seen=set()
                channels=[]
                for broadcast in self.games:
                    for name in broadcast.get('channels',[]) or []:
                        name=str(name).strip()
                        if name and name.casefold() not in seen:
                            seen.add(name.casefold())
                            channels.append(name)
                combined['channels']=channels
                self.games=[combined]
            self["heading"].setText("TV-SENDER | "+label[:49])'''
assert section.count(pre)==1,"Match list anchor changed"
section=section.replace(pre,new,1)
assert 'self.games=games' not in section[:section.index('        # Only opening LiveOnSat from the main menu')]
assert "if len(self.games)==1:" in section
source=source[:start]+section+source[end:]
if source.count("6.13.17")<1:raise ValueError("No version marker")
source=source.replace("6.13.17","6.13.18")
compile(source,str(plugin),"exec")
plugin.write_text(source,encoding="utf-8")
(ROOT/"source/VERSION").write_text(VERSION+"\n",encoding="utf-8")

sys.path.insert(0,str(DEST))
from fixture_match import match_fixtures, team_similarity
match={'home':'FC Basel','away':'Young Boys'}
game={'home':'Basel','away':'BSC Young Boys','channels':['blue Sport 1','SRF zwei']}
other={'home':'FC Zurich','away':'FC Lugano','channels':['DAZN 1']}
assert match_fixtures(match,[game,other])==[game]
assert match_fixtures(match,[other])==[]
assert min(team_similarity(match['home'],other['away']),team_similarity(match['away'],other['home']))<90
assert "Keine bestaetigten TV-Sender fuer diese Partie gefunden." in section
assert "self.open_child(LiveOnSatDetailScreen,self.games[0])" in section
assert "self.games=games" in section[section.index('        # Only opening LiveOnSat from the main menu'):]
# Preserve images, audio and saved settings from the verified original.
for cache in DEST.rglob("__pycache__"):shutil.rmtree(cache)
subprocess.run(["python3","scripts/build_ipk.py"],cwd=ROOT,check=True)
print("GoalAlert 6.13.18 built; fixture TV navigation and no-cross-match regressions passed.")
