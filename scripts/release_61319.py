#!/usr/bin/env python3
"""GoalAlert 6.13.19: filter LiveOnSat CSS, user-selectable popup colours,
and safer audio-mixer fallback without disrupting TV or existing crests.
"""
from pathlib import Path, PurePosixPath
import hashlib, io, tarfile, subprocess, sys, shutil

ROOT=Path(__file__).resolve().parents[1]
VERSION="6.13.19"
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.18_all.ipk"
PIN="3890135f24a45f908d1863467703fd9e6c81c85851280a3d248c7a32d24d1a0d"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=PIN:
    raise ValueError("Verified GoalAlert 6.13.18 IPK unavailable or modified")
if DEST.exists():raise ValueError("Refusing to overwrite source folder")
DEST.mkdir(parents=True)
data=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(data),mode="r:xz") as archive:
    for member in archive:
        name=member.name.lstrip("./")
        if not member.isfile() or not name.startswith(PREFIX):continue
        relative=name[len(PREFIX):]
        if not relative or ".." in PurePosixPath(relative).parts or relative.startswith("/"):
            raise ValueError("Unsafe path")
        if "__pycache__" in relative or relative.endswith((".pyc",".m3u",".m3u8",".log")):continue
        out=DEST/relative
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(archive.extractfile(member).read())

# 1. HTML/CSS from LiveOnSat is currently entering station labels.
parser=DEST/"liveonsat_parser.py"
ps=parser.read_text(encoding="utf-8")
assert "class Collector(HTMLParser):" in ps
assert "        self.parts=[]\n    def handle_data(self,data):" in ps
ps=ps.replace("        self.parts=[]\n    def handle_data(self,data):",
"""        self.parts=[]
        self._ignored=[]
    def handle_starttag(self,tag,attrs):
        if tag.lower() in ('script','style','template','noscript','svg'):
            self._ignored.append(tag.lower())
    def handle_endtag(self,tag):
        if self._ignored and tag.lower()==self._ignored[-1]:
            self._ignored.pop()
    def handle_data(self,data):
        if self._ignored:return""",1)
marker="def parse_schedule(raw, date_filter=None):"
assert ps.count(marker)==1
validate=r'''def valid_broadcast_name(value):
    """Reject style rules, injected website controls, and nonstation markup.

    Keep provider annotations such as 'YouTube: The AFC Hub' and
    'Veikkaus TV ($/geo/R)', as they are genuine broadcaster labels.
    """
    if value is None:return False
    label=' '.join(html.unescape(str(value)).split()).strip()
    if not 2<=len(label)<=125:return False
    if any(token in label for token in ('{','}',';','/*','*/','<','>','\\')):return False
    if label.startswith(('#','.','@','--','//')):return False
    if re.search(r'(?i)(?:^|\s)(?:background(?:-color)?|border(?:-[a-z]+)?|margin(?:-[a-z]+)?|padding(?:-[a-z]+)?|transition|transform|width|height|opacity|display|position|color|font(?:-[a-z]+)?|z-index)\s*:',label):
        return False
    if re.match(r'(?i)^(?:https?://|javascript:|data:|@media|@keyframes|var\s*\(|calc\s*\()',label):return False
    if re.match(r'(?i)^(?:expand-contract|document\.|window\.|function\s*\()',label):return False
    return True

'''
ps=ps.replace(marker,validate+marker,1)
old="if len(item)<130 and item not in current['channels'] and len(current['channels'])<150:"
assert ps.count(old)==1
ps=ps.replace(old,"if valid_broadcast_name(item) and item not in current['channels'] and len(current['channels'])<150:",1)
old="if channel and channel.casefold() not in existing and len(obj['channels'])<150:"
assert ps.count(old)==1
ps=ps.replace(old,"if valid_broadcast_name(channel) and channel.casefold() not in existing and len(obj['channels'])<150:",1)
parser.write_text(ps,encoding="utf-8")
compile(ps,str(parser),"exec")

# 2. Also sanitize old on-box cache right before rendering, so no stale CSS
# stays visible until next remote refresh.
plugin=DEST/"plugin.py"
s=plugin.read_text(encoding="utf-8")
before="        self.channels=[str(x).strip() for x in g.get('channels',[]) if str(x).strip()]"
assert s.count(before)==1
s=s.replace(before,
"""        from .liveonsat_parser import valid_broadcast_name
        self.channels=[str(x).strip() for x in g.get('channels',[])
                       if valid_broadcast_name(x)]""",1)

# 3. Three independent and persistent colour selections.
anchor="# Favoriten bleiben in einer separaten JSON-Datei gespeichert."
assert s.count(anchor)==1
colors=r'''# Strong popup text colours, selectable independently from the TV menu.
GOALALERT_TEXT_COLORS=[
    ('orange','Orange'),('yellow','Gelb'),('pink','Rosa'),
    ('red','Rot'),('turquoise','Tuerkis'),('lime','Hellgruen'),
    ('white','Weiss')]
GOALALERT_COLOR_HEX={
    'orange':'#FF9C19','yellow':'#FFF04D','pink':'#FF55BB',
    'red':'#FF4A50','turquoise':'#44EEE7','lime':'#B4FF5C',
    'white':'#FFFFFF'}
if not hasattr(config.plugins.goalalert32,'name_color'):
    config.plugins.goalalert32.name_color=ConfigSelection(
        default='orange',choices=GOALALERT_TEXT_COLORS)
if not hasattr(config.plugins.goalalert32,'score_color'):
    config.plugins.goalalert32.score_color=ConfigSelection(
        default='yellow',choices=GOALALERT_TEXT_COLORS)
if not hasattr(config.plugins.goalalert32,'message_color'):
    config.plugins.goalalert32.message_color=ConfigSelection(
        default='pink',choices=GOALALERT_TEXT_COLORS)
def _goalalert_color_label(value):
    return dict(GOALALERT_TEXT_COLORS).get(value,'Orange')
def _goalalert_next_color(field):
    keys=[k for k,_ in GOALALERT_TEXT_COLORS]
    field.value=keys[(keys.index(field.value)+1)%len(keys)] if field.value in keys else keys[0]

'''
s=s.replace(anchor,colors+anchor,1)

# 4. Add settings without disturbing existing keypad/action mapping.
start=s.index("class SettingsScreen(BaseScreen):")
end=s.index("TIP_LEAGUES=[",start)
sec=s[start:end]
anchor='''            "Test-Toralarm anzeigen",'''
assert sec.count(anchor)==1
sec=sec.replace(anchor,'''            "Teamnamen-Farbe: "+_goalalert_color_label(c.name_color.value),
            "Spielstand-Farbe: "+_goalalert_color_label(c.score_color.value),
            "Tor-/Torschuetzen-Farbe: "+_goalalert_color_label(c.message_color.value),
'''+anchor,1)
assert sec.count("if i==7:")==1
sec=sec.replace("if i==7:","if i==10:",1)
old='''        elif i==4:monitor.test_goal()
        elif i==5:monitor.test_scorer()
        elif i==6:self.rebuild_index()'''
new='''        elif i==4:_goalalert_next_color(c.name_color)
        elif i==5:_goalalert_next_color(c.score_color)
        elif i==6:_goalalert_next_color(c.message_color)
        elif i==7:monitor.test_goal()
        elif i==8:monitor.test_scorer()
        elif i==9:self.rebuild_index()'''
assert sec.count(old)==1
sec=sec.replace(old,new,1)
old='''c.enabled.save();c.duration.save();c.popup_size.save();c.cheer_style.save();configfile.save()'''
assert sec.count(old)==1
sec=sec.replace(old,'''c.enabled.save();c.duration.save();c.popup_size.save();c.cheer_style.save()
        c.name_color.save();c.score_color.save();c.message_color.save();configfile.save()''',1)
s=s[:start]+sec+s[end:]

# 5. Change only runtime text colour of goal popup, never the PNG background
# or official team crest fetching/decoding.
start=s.index("class GoalPopup(Screen):")
end=s.index("AUDIO_LOG=",start)
pop=s[start:end]
anchor="        root='/usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'"
assert pop.count(anchor)>=1
insert='''        c=config.plugins.goalalert32
        name_color=GOALALERT_COLOR_HEX.get(c.name_color.value,'#FF9C19')
        score_color=GOALALERT_COLOR_HEX.get(c.score_color.value,'#FFF04D')
        message_color=(color if kind in ('cancel','redcard')
                       else GOALALERT_COLOR_HEX.get(c.message_color.value,'#FF55BB'))
'''
pop=pop.replace(anchor,insert+anchor,1)
assert pop.count('foregroundColor="#EAF8FF" transparent="1" zPosition="3" />')==2
pop=pop.replace('foregroundColor="#EAF8FF" transparent="1" zPosition="3" />',
                'foregroundColor="{name_color}" transparent="1" zPosition="3" />',2)
assert pop.count('foregroundColor="#FFFFFF" transparent="1" zPosition="3" />')==2
pop=pop.replace('foregroundColor="#FFFFFF" transparent="1" zPosition="3" />',
                'foregroundColor="{score_color}" transparent="1" zPosition="3" />',2)
assert pop.count('foregroundColor="{color}" transparent="1" zPosition="3" />')==1
pop=pop.replace('foregroundColor="{color}" transparent="1" zPosition="3" />',
                'foregroundColor="{message_color}" transparent="1" zPosition="3" />',1)
anchor='msgfont=font(16),color=color)'
assert pop.count(anchor)==1
pop=pop.replace(anchor,
'''msgfont=font(16),name_color=name_color,score_color=score_color,
             message_color=message_color)''',1)
s=s[:start]+pop+s[end:]

# 6. Audio: current diagnostic shows mixer-busy / plug:dmix failure.
# Try broadly supported default PCM sinks before the exclusive device.
# Do not stop TV, change the selected service, edit volume or force AC3 settings.
audio=DEST/"goalalert_audio.py"
a=audio.read_text(encoding="utf-8")
anchor="        ('ALSA default',['aplay','-q',path]),"
assert a.count(anchor)==1
a=a.replace(anchor,
"""        ('GStreamer ALSA default',gst+['alsasink','device=default','sync=false']),
        ('GStreamer ALSA sysdefault',gst+['alsasink','device=sysdefault','sync=false']),
        ('ALSA sysdefault',['aplay','-q','-D','sysdefault',path]),
"""+anchor,1)
a=a.replace(
"    A bitstream-passthrough or exclusive PCM sink cannot be overridden\n    without changing device-wide TV audio. Fail visibly in the log instead.",
"    Bitstream passthrough or an exclusive PCM sink may prevent mixing.\n    Never interrupt DVB service. Record the backend error for TV diagnosis."
)
a=a.replace(
"                if p.returncode==0:\n                    _log(label+': Playback OK; TV-Ton-Mischung nur am Receiver pruefbar')",
"                if p.returncode==0:\n                    _log(label+': Audio-Prozess erfolgreich; Hoerbarkeit nur am TV pruefbar')"
)
audio.write_text(a,encoding="utf-8")
compile(a,str(audio),"exec")
# Less misleading UI status (an asynchronous attempt is not confirmed audible).
s=s.replace(
"self['hint'].setText('Audio gestartet; BLAU: Status pruefen. Hoerbarkeit nur am TV pruefbar.')",
"self['hint'].setText('Audiotest laeuft; BLAU: Protokoll pruefen. Bei Stille PCM-Downmix aktivieren.')"
)
assert "self['hint'].setText('Audiotest laeuft;" in s

s=s.replace("6.13.18","6.13.19")
compile(s,str(plugin),"exec")
plugin.write_text(s,encoding="utf-8")
(ROOT/"source/VERSION").write_text(VERSION+"\n",encoding="utf-8")

# 7. Deterministic offline regressions: provider data, cached CSS and channel text.
sys.path.insert(0,str(DEST))
from liveonsat_parser import parse_schedule,valid_broadcast_name,merge_day_schedules
good=["YouTube: The AFC Hub","Veikkaus TV ($/geo/R)","D Smart GO ($/geo/R)","Sport TV 1 HD","SRF zwei"]
bad=["#expand-contract631586 {","margin-top: -500%;","transition: all 0.3s;","width:100%;",
     "}","#expand-contract631586.expanded {","border-bottom: 1px solid red;"]
assert all(valid_broadcast_name(x) for x in good),good
assert not any(valid_broadcast_name(x) for x in bad),bad
page="""<html><style>#expand-contract631586 {margin-top:-500%;}</style>
<div>Thursday, 5th November 2026</div><div>FC Basel v Young Boys</div>
<div>ST: 19:30</div><div>YouTube: The AFC Hub</div>
<div>Veikkaus TV ($/geo/R)</div><div>#expand-contract631586 {</div>
<div>border-bottom: 1px solid red;</div><script>window.foo={};</script>
<div>D Smart GO ($/geo/R)</div><div>width:100%;</div></html>"""
rows=parse_schedule(page)
assert len(rows)==1,rows
assert rows[0]['channels']==["YouTube: The AFC Hub","Veikkaus TV ($/geo/R)","D Smart GO ($/geo/R)"],rows[0]
dated=merge_day_schedules([[dict(rows[0],channels=good+bad)]],"2026-11-05")
assert len(dated)==1 and dated[0]['channels']==good,dated
# Preserve match-specific navigation from 6.13.18
assert 'Keine bestaetigten TV-Sender fuer diese Partie gefunden.' in s
assert 'self.open_child(LiveOnSatDetailScreen,self.games[0])' in s
assert "if valid_broadcast_name(x)" in s
# Validate all three bindings to dynamic label properties.
assert "foregroundColor=\"{name_color}\"" in s
assert "foregroundColor=\"{score_color}\"" in s
assert "foregroundColor=\"{message_color}\"" in s
assert "c.name_color.save();c.score_color.save();c.message_color.save()" in s
assert "alsa" in a.lower() and "sysdefault" in a
# Existing PNG crests left untouched; no new hardware tools required.
for cache in DEST.rglob("__pycache__"):shutil.rmtree(cache)
subprocess.run(["python3","scripts/build_ipk.py"],cwd=ROOT,check=True)
print("GoalAlert 6.13.19: CSS filtering, cached lists, colour settings, audio fallbacks and match routing PASS")
