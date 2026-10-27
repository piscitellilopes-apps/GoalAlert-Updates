#!/usr/bin/env python3
"""GoalAlert 6.13.17: safe fuzzy IPTV matching, missing-description
bouquet indexing and return straight to full-screen TV after IPTV zap."""
from pathlib import Path,PurePosixPath
import hashlib,io,tarfile,subprocess,shutil,sys,tempfile,json,gzip
ROOT=Path(__file__).resolve().parents[1]
VERSION="6.13.17"
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.16_all.ipk"
PIN="69412905926b75470ecf7d74b85aa2c77fe5cb002a0e7031d0f4558cfcc59cc7"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=PIN:
    raise ValueError("Verified 6.13.16 package unavailable or modified")
if DEST.exists():raise ValueError("Refusing to overwrite source")
DEST.mkdir(parents=True)
data=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(data),mode="r:xz") as archive:
    for member in archive:
        name=member.name.lstrip("./")
        if not member.isfile() or not name.startswith(PREFIX):continue
        relative=name[len(PREFIX):]
        if not relative or ".." in PurePosixPath(relative).parts or relative.startswith("/"):
            raise ValueError("Unsafe package path")
        if "__pycache__" in relative or relative.endswith((".pyc",".m3u",".m3u8",".log")):continue
        output=DEST/relative
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_bytes(archive.extractfile(member).read())

index=DEST/"iptv_index.py"
old=index.read_text(encoding="utf-8")
# Stable and narrow: IPTV station names must retain TV as part of Sport TV.
assert old.count("live tv premium vip") == 1
old=old.replace("live tv premium vip","live premium vip")
# Keep brand prefix and optional channel number intact. PT/Portugal and HD
# are ignored anywhere, not only at beginning or end. Lookup returns ALL
# reasonable alternatives; there is never a blind automatic zap.
start=old.index("def _rank(key,candidate):")
end=old.index("\ndef lookup(",start)
old=old[:start]+'''def _rank(key,candidate):
    """Conservative fuzzy broadcaster match, always preserve channel numbers.

    Sport TV Portugal, PT SportTV, Sport TV HD and SPORT TV share a brand.
    Sport TV 1 must never incorrectly match Sport TV 2, Sky Sport or SRF.
    If the guide gives no channel number, show numbered choices with a
    lower score instead of assuming which channel carries the match.
    """
    if key==candidate:return 100
    wanted=key.split()
    available=candidate.split()
    if not wanted or not available:return 0
    # Brand prefixes are meaningful: never map Sport TV to Sky Sport TV.
    if wanted[0]!=available[0]:return 0
    wn={w for w in wanted if w.isdigit()}
    an={w for w in available if w.isdigit()}
    if wn and wn!=an:return 0
    ws=set(wanted)
    aset=set(available)
    if wn and not wn.issubset(aset):return 0
    # Two distinguishing words prevent generic 'sport' hits and unrelated
    # channels with coincidentally shared generic tokens.
    if len(wanted)>=2 and len(available)>=2 and wanted[:2]==available[:2]:
        if ws.issubset(aset):
            return 90 if wn or not an else 80
        if aset.issubset(ws):
            return 87
        # A third descriptive part is allowed as a broadcaster variant.
        similarity=SequenceMatcher(None,key,candidate).ratio()
        return 75 if similarity>=0.70 else 0
    similarity=SequenceMatcher(None,key,candidate).ratio()
    if len(wanted)>=2 and len(available)>=2 and similarity>=0.86:
        if len(ws&aset)>=2:return 72
    return 0
''' +old[end:]
# Normalize all country/quality aliases, including country mid-name. Keep
# 'tv' token in the normalized broadcaster identity.
assert "tokens=[t for t in expanded if t not in NOISE and t not in QUALITY and t not in COUNTRIES]" in old
# Guarantee cleaned country token does not swallow Portugal when label splits.
assert "pt portugal" in old
# Use filename basename validation and replay only from own local bouquets.
index.write_text(old,encoding="utf-8")

refresh=DEST/"refresh_iptv_index.py"
f=refresh.read_text(encoding="utf-8")
a=f.index("        previous=None\n        with open(path,'rb') as stream:")
b=f.index("    # Some providers don't include #DESCRIPTION;",a)
f=f[:a]+'''        previous=None
        def flush_pending():
            # Save the readable name only. Keep local IPTV stream
            # references out of the compressed metadata index.
            nonlocal previous
            if previous is None:return
            ref,position,label=previous
            previous=None
            name=' '.join(str(label or '').split())[:160]
            normalized=normalized_name(name)
            if not name or not normalized:return
            stations.append([normalized,name,filename,position,
                             hashlib.sha256(ref.encode('utf-8')).hexdigest()])
            if len(stations)>150000:
                raise ValueError('Too many IPTV live channels')
        with open(path,'rb') as stream:
            # #DESCRIPTION is optional in OpenATV bouquets. Use the service
            # name when it is absent and flush a pending row at EOF.
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
                    flush_pending()
                    ref=line[len('#SERVICE '):]
                    if len(ref)>20000:continue
                    fallback=ref.rsplit(':',1)[-1].strip()
                    if not fallback or len(fallback)>160:continue
                    previous=[ref,n,fallback]
                    continue
                if previous is not None and line.startswith('#DESCRIPTION '):
                    previous[2]=line[len('#DESCRIPTION '):].strip() or previous[2]
                    flush_pending()
            flush_pending()
''' + f[b:]
f=f.replace('''    # Some providers don't include #DESCRIPTION; second pass detects these
    # without writing, printing, or persisting any streaming reference.
    # Prefer the explicit station name where it exists.''',
'''    # Both types of Live-TV bouquet work: with or without #DESCRIPTION.''')
refresh.write_text(f,encoding="utf-8")

plugin=DEST/"plugin.py"
s=plugin.read_text(encoding="utf-8")
def patch(a,b,n=1):
    global s
    count=s.count(a)
    if count!=n:raise ValueError("Patch anchor count %d, expected %d: %s"%(count,n,a[:110]))
    s=s.replace(a,b,n)

# Do not start IPTV channel from an unsupported or malformed reference.
# On success the existing close-result propagation will unwind every
# GoalAlert screen. A delayed GUI-thread cleanup dismisses originating
# PluginBrowser / Enigma2 Menu that would otherwise remain onscreen.
hook='''    def _selected(self,candidate=None):
        if candidate is None:return
        try:
            from .iptv_index import resolve'''
assert s.count(hook)==1
patch(hook,'''    def _selected(self,candidate=None):
        if candidate is None:return
        try:
            from .iptv_index import resolve''')
patch('''            self.close('goalalert_zapped')
        except Exception as exc:''',
'''            self.close('goalalert_zapped')
            _goalalert_schedule_fullscreen_tv(self.session)
        except Exception as exc:''')

# Functions use only Enigma2 event-loop timers, never shell commands,
# key simulation, stream URL logging, or screen changes from a worker.
needle='''monitor=Monitor()
def open_plugin(session,**kwargs):'''
replacement='''# Keep one timer alive until the successful service zap returns all
# nested GoalAlert dialogs to the Enigma2 origin. This is required when
# GoalAlert was opened from the OpenATV plugin list.
_GOALALERT_FULLSCREEN_TIMERS=[]
def _goalalert_schedule_fullscreen_tv(session):
    timer=eTimer()
    status={'attempts':0}
    def finish():
        status['attempts']+=1
        retry=False
        try:
            current=getattr(session,'current_dialog',None)
            if current is None:return
            name=type(current).__name__
            module=type(current).__module__
            own=(module==__name__ and name in
                 ('Home','QuickLiveScreen','GamesScreen','GameDetailScreen',
                  'LiveOnSatScreen','LiveOnSatDetailScreen','IPTVCandidateScreen',
                  'IPTVBrowseScreen'))
            navigation=(name in ('PluginBrowser','PluginSelection','Menu')
                        and (module.startswith('Screens.') or
                             module.startswith('Plugins.')))
            if own or navigation:
                current.close()
                # Enigma2 shows the previous dialog after closing this one.
                # Continue only for an eligible navigation stack.
                if status['attempts']<7:
                    retry=True
                    timer.start(170,True)
        except Exception as exc:
            retry=False
            _crest_log('TV-Vollbild-Aufraeumen: '+type(exc).__name__)
        finally:
            if not retry:
                try:_GOALALERT_FULLSCREEN_TIMERS.remove(timer)
                except ValueError:pass
    # Retain timer until stack is completely unwound; start after callbacks.
    timer.callback.append(finish)
    _GOALALERT_FULLSCREEN_TIMERS.append(timer)
    timer.start(450,True)

monitor=Monitor()
def open_plugin(session,**kwargs):'''
patch(needle,replacement)
# The player must leave the TV full-screen with no plugin selector. The
# popup and alert monitor are still available in background as before.
s=s.replace('6.13.16','6.13.17')
plugin.write_text(s,encoding="utf-8")
(ROOT/"source/VERSION").write_text(VERSION+"\n",encoding="utf-8")
compile(s,str(plugin),"exec")
compile(f,str(refresh),"exec")
compile(old,str(index),"exec")
# Regression: normalize real-world alternatives AND prevent number mistakes.
sys.path.insert(0,str(DEST))
import iptv_index as idx
tests=['Sport TV Portugal','SPORTTV PT','PT: Sport TV HD',
       'SPORT TV 4K (PT)','Sport TV']
norms={idx.normalized_name(name) for name in tests}
assert norms=={'sport tv'},norms
assert idx._rank('sport tv',idx.normalized_name('PT SPORTTV HD'))==100
assert idx._rank('sport tv 1',idx.normalized_name('PT Sport TV 2 HD'))==0
assert idx._rank('sport tv',idx.normalized_name('Sky Sport TV'))==0
assert idx._rank('sport tv',idx.normalized_name('Sport TV 1'))>=70
assert idx._rank('sport tv 1',idx.normalized_name('Sport TV'))==0
assert idx._rank('sport tv',idx.normalized_name('Sport TV 1'))<100
import refresh_iptv_index as builder
with tempfile.TemporaryDirectory() as tmp:
    td=Path(tmp)
    base='userbouquet.sport.tv'
    sub='subbouquet.pt_channels.tv'
    (td/'bouquets.tv').write_text('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "'+base+'" ORDER BY bouquet\n')
    (td/base).write_text('#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "'+sub+'" ORDER BY bouquet\n')
    ref1='4097:0:1:0:0:0:0:0:0:0:http%3a//private.example.invalid/id:PT SPORT TV 1 HD'
    ref2='5001:0:1:0:0:0:0:0:0:0:http%3a//private.example.invalid/id2:Sport TV Portugal'
    (td/sub).write_text('#SERVICE '+ref1+'\n#SERVICE '+ref2+'\n#DESCRIPTION Sport TV Portugal\n')
    out=str(td/'index.json.gz')
    assert builder.build(root=tmp,destination=out)['stations']==2
    found,total=idx.lookup('Sport TV Portugal',path=out)
    assert total==2 and any(c['name']=='Sport TV Portugal' for c in found)
    assert any(c['name']=='PT SPORT TV 1 HD' for c in found)
    for c in found:
        assert idx.resolve(c,bouquet_dir=tmp) in (ref1,ref2)
    with gzip.open(out,'rt',encoding='utf-8') as fh:
        indexed=json.load(fh)
    assert 'private.example.invalid' not in str(indexed)
assert '_goalalert_schedule_fullscreen_tv(self.session)' in s
assert "navigation=(name in ('PluginBrowser','PluginSelection','Menu')" in s
for cache in DEST.rglob("__pycache__"):shutil.rmtree(cache)
subprocess.run(["python3","scripts/build_ipk.py"],cwd=ROOT,check=True)
print("GoalAlert 6.13.17 passed source, IPTV fuzzy search, nested no-description index and IPK tests.")
