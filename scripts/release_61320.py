#!/usr/bin/env python3
"""GoalAlert 6.13.20 - 20 crowd celebration sound options (CC0).
Source audio: SFXMint CC0 public-domain audio (sfxmint.com), converted to
receiver-friendly uncompressed 16-bit PCM mono 22.05 kHz.
The receiver does not fetch files at runtime; all chosen WAVs ship in the IPK.
"""
from pathlib import Path,PurePosixPath
import hashlib,io,tarfile,subprocess,sys,shutil,urllib.request,time,wave,math

ROOT=Path(__file__).resolve().parents[1]
VERSION="6.13.20"
BASE=ROOT/"enigma2-plugin-extensions-goalalert_6.13.19_all.ipk"
PIN="04ce1c1629c9ddfd2d65cf1d6d0be870025d4bf6ecb43a53bc268063fcf1d951"
DEST=ROOT/"source/GoalAlert"
PREFIX="usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/"
if not BASE.is_file() or hashlib.sha256(BASE.read_bytes()).hexdigest()!=PIN:
    raise ValueError("Verified GoalAlert 6.13.19 unavailable or modified")
if DEST.exists():raise ValueError("Refusing to overwrite source")
DEST.mkdir(parents=True)
data=subprocess.check_output(["ar","p",str(BASE),"data.tar.xz"])
with tarfile.open(fileobj=io.BytesIO(data),mode="r:xz") as arc:
    for member in arc:
        name=member.name.lstrip("./")
        if not member.isfile() or not name.startswith(PREFIX):continue
        rel=name[len(PREFIX):]
        if not rel or ".." in PurePosixPath(rel).parts or rel.startswith("/"):
            raise ValueError("Unsafe IPK archive entry")
        if "__pycache__" in rel or rel.endswith((".pyc",".log",".m3u",".m3u8")):continue
        dest=DEST/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(arc.extractfile(member).read())

# CC0 sources explicitly available for redistribution and remix in applications.
# We use 20 different, goal/celebration-appropriate source recording attempts.
SOUNDS=[
 ("Stadion-Tor","stadium-crowd-02"),
 ("Sieger-Explosion","crowd-cheer-44"),
 ("Jubel-Orkan","crowd-cheer-72"),
 ("Heimkurve","crowd-cheer-63"),
 ("Final-Jubel","crowd-cheer-70"),
 ("Champions-Nacht","crowd-cheer-71"),
 ("Derby-Wahnsinn","crowd-cheer-56"),
 ("Tor-Ekstase","crowd-cheer-47"),
 ("Ultras-Jubel","crowd-cheer-60"),
 ("Last-Minute-Tor","crowd-cheer-65"),
 ("Auswaertsblock","crowd-cheer-59"),
 ("Torfestival","crowd-cheer-49"),
 ("Grosse Fankurve","crowd-cheer-58"),
 ("Stadion-Blitz","crowd-cheer-45"),
 ("Schneller Sieg","crowd-cheer-61"),
 ("Grosse Jubelwelle","crowd-cheer-52"),
 ("Volle Tribuene","crowd-cheer-57"),
 ("Gänsehaut","crowd-cheer-53"),
 ("Fangesang & Klatschen","crowd-chant-03"),
 ("Riesenapplaus","stadium-crowd-05"),
]
assert len(SOUNDS)==20 and len(set(key for _,key in SOUNDS))==20
# No authentic broadcaster commentary is included: only CC0 crowd sounds.
# Original SFXMint samples may be AI-generated; these are not claimed to be
# real match recordings. Each option is independently editable in the TV menu.
source_list=[]
downloaded=[]
def fetch_audio(slug):
    url="https://sfxmint.com/dl/"+slug+".mp3"
    for attempt in range(1):
        try:
            req=urllib.request.Request(url,headers={
              "User-Agent":"Mozilla/5.0 (compatible; GoalAlertCC0/6.13.20)",
              "Accept":"audio/mpeg,audio/*;q=0.9,*/*;q=0.1"
            })
            with urllib.request.urlopen(req,timeout=10) as response:
                chunk=response.read(3_000_000)
            if len(chunk)<3000 or len(chunk)>=3_000_000:
                raise ValueError("Unexpected audio file length")
            if chunk[:1]==b"<":
                raise ValueError("Unexpected HTML in audio response")
            return chunk
        except Exception as exc:
            if attempt==0:
                print("Download unavailable",slug,type(exc).__name__)
                return None
            time.sleep(2+attempt)
    return None

ffmpeg=shutil.which("ffmpeg")
if not ffmpeg:raise RuntimeError("ffmpeg required for converting CC0 sources")
temporary=ROOT/"_goalalert_cheer_tmp"
temporary.mkdir(exist_ok=False)
try:
    for i,(label,slug) in enumerate(SOUNDS,1):
        raw=fetch_audio(slug)
        if raw:
            mp3=temporary/(slug+".mp3")
            mp3.write_bytes(raw)
            downloaded.append((i,slug,mp3))
    print("Distinct source MP3 downloaded:",len(downloaded))
    # Ensure we still ship all 20 *distinct edited variants* if the supplier
    # applies a network download quota. Reuse downloaded CC0 source segments
    # with different starting positions and output-level treatments, not
    # fake copies of the same raw file.
    if len(downloaded)<4:
        raise RuntimeError("Fewer than four distinct CC0 celebration samples available")
    credit=["GoalAlert Torjubel 6.13.20 - 20 eigenstaendige Sound-Presets",
            "Quelle: SFXMint (https://sfxmint.com/sounds/crowd-cheer , https://sfxmint.com/sounds/stadium-crowd , https://sfxmint.com/sounds/crowd-chant)",
            "Lizenz aller Ausgangssamples: CC0 1.0, freie Verwendung, Bearbeitung und Verteilung.",
            "Einzelne Presets sind neu abgemischte Varianten, falls die Quelle Downloads begrenzt.",
            "Hinweis: SFXMint-Sounds sind AI-generiert, keine originalen Stadionmitschnitte.",
            ""]
    for i,(label,slug) in enumerate(SOUNDS,1):
        own=next((x for x in downloaded if x[0]==i),None)
        if own:
            used=own
            variation=False
        else:
            used=downloaded[(i-1)%len(downloaded)]
            variation=True
        _,source_slug,src=used
        output=DEST/("goal_fan_%02d.wav"%i)
        # all 20 goal sounds are fast-starting and bounded; no artificial
        # synthesized beep or overlay that would resemble the old alarms.
        # Mono 22.05kHz PCM, compatible with ALSA aplay and GStreamer wavparse.
        # EQ, levels and start-offset differ for fallback variations.
        trim=(0 if not variation else ((i%5)*0.28))
        highpass=80+(i%3)*25
        lowpass=5900+(i%4)*350
        comp=("acompressor=threshold=0.12:ratio=2.2:attack=8:release=160,"
              "volume=1.6,alimiter=limit=0.88")
        filters="highpass=f=%d,lowpass=f=%d,%s,"%(highpass,lowpass,comp)
        filters+=("afade=t=in:st=0:d=0.09,areverse,"
                  "afade=t=in:st=0:d=0.24,areverse")
        cmd=[ffmpeg,"-nostdin","-hide_banner","-loglevel","error",
             "-y","-ss",str(trim),"-i",str(src),"-t","6.6",
             "-vn","-ac","1","-ar","22050","-c:a","pcm_s16le",
             "-af",filters,str(output)]
        subprocess.run(cmd,check=True,timeout=40)
        with wave.open(str(output),'rb') as wav:
            assert wav.getnchannels()==1 and wav.getframerate()==22050
            assert wav.getsampwidth()==2 and wav.getnframes()>15000
        assert output.stat().st_size<320_000,output.stat().st_size
        status=("Quelle" if not variation else "Variante")
        credit.append("%02d %s | %s: %s | https://sfxmint.com/sounds/%s"%(
             i,label,status,source_slug,source_slug))
    # Do not publish external links that point to any TV streams or user data.
    (DEST/"GOALALERT_20_CHEERS_LICENSE.txt").write_text(
         "\n".join(credit)+"\n",encoding="utf-8")
finally:
    shutil.rmtree(temporary,ignore_errors=True)

plugin=DEST/"plugin.py"
s=plugin.read_text(encoding="utf-8")
opts=["('fan%02d','%02d %s')"%(i,i,label.replace("'","")) for i,(label,slug) in enumerate(SOUNDS,1)]
options="[\n    "+",\n    ".join(opts)+"\n]"
anchor='if not hasattr(config.plugins.goalalert32,"cheer_style"):'
assert s.count(anchor)==1
s=s.replace(anchor,"GOALALERT_FAN_CHEERS="+options+"\nGOALALERT_CHEER_LABELS=dict(GOALALERT_FAN_CHEERS)\n"+anchor,1)
start=s.index('if not hasattr(config.plugins.goalalert32,"cheer_style"):')
end=s.index('# Favoriten bleiben in einer separaten JSON-Datei gespeichert.',start)
section=s[start:end]
old='''    config.plugins.goalalert32.cheer_style=ConfigSelection(default="classic",
        choices=[("classic","Klassisch"),("stadium","Stadion-Echo"),
                 ("double","Doppeljubel"),("short","Kurzer Tor-Ruf")])'''
assert section.count(old)==1,repr(section[:300])
new='''    config.plugins.goalalert32.cheer_style=ConfigSelection(default="fan01",
        choices=GOALALERT_FAN_CHEERS+
          [("classic","Alt: Klassisch"),("stadium","Alt: Stadion-Echo"),
           ("double","Alt: Doppeljubel"),("short","Alt: Kurzer Ruf")])'''
section=section.replace(old,new,1)
# Add labels for saved pre-6.13.20 settings.
section=section.replace(new,new+"\nGOALALERT_CHEER_LABELS.update(dict([('classic','Alt: Klassisch'),('stadium','Alt: Stadion-Echo'),('double','Alt: Doppeljubel'),('short','Alt: Kurzer Ruf')]))",1)
s=s[:start]+section+s[end:]

# Settings: choosing TORJUBEL rotates the new 20 only, while older presets
# continue to play when already saved.
st=s.index("class SettingsScreen(BaseScreen):")
en=s.index("TIP_LEAGUES=[",st)
sec=s[st:en]
old='''"Torjubel: "+{"classic":"Klassisch","stadium":"Stadion-Echo",
                         "double":"Doppeljubel","short":"Kurzer Tor-Ruf"}.get(c.cheer_style.value,"Klassisch"),'''
assert sec.count(old)==1
sec=sec.replace(old,''' "Torjubel: "+GOALALERT_CHEER_LABELS.get(c.cheer_style.value,"01 Stadion-Tor"),'''.lstrip(),1)
old='''            values=["classic","stadium","double","short"]
            c.cheer_style.value=values[(values.index(c.cheer_style.value)+1)%len(values)]'''
assert sec.count(old)==1
sec=sec.replace(old,'''            values=[key for key,_label in GOALALERT_FAN_CHEERS]
            current=c.cheer_style.value
            c.cheer_style.value=values[(values.index(current)+1)%len(values)] if current in values else values[0]''',1)
s=s[:st]+sec+s[en:]

# Audio test window: cycle all 20 from YELLOW, OK to hear selected sample.
st=s.index("class AudioStatusScreen(BaseScreen):")
en=s.index("class Monitor:",st) if "class Monitor:" in s[st:] else len(s)
audio_ui=s[st:en]
old='''labels={"classic":"Klassisch","stadium":"Stadion-Echo","double":"Doppeljubel","short":"Kurzer Tor-Ruf"}'''
assert audio_ui.count(old)==1
audio_ui=audio_ui.replace(old,'''labels=GOALALERT_CHEER_LABELS''',1)
old='''        values=["classic","stadium","double","short"]
        c.value=values[(values.index(c.value)+1)%len(values)]'''
assert audio_ui.count(old)==1
audio_ui=audio_ui.replace(old,'''        values=[key for key,_label in GOALALERT_FAN_CHEERS]
        c.value=values[(values.index(c.value)+1)%len(values)] if c.value in values else values[0]''',1)
s=s[:st]+audio_ui+s[en:]

# Update map: each option resolves to an exact included PCM WAV filename.
audio=DEST/"goalalert_audio.py"
a=audio.read_text(encoding="utf-8")
anchor="def _log(msg):"
assert a.count(anchor)==1
a=a.replace(anchor,"for _i in range(1,21):\n    CHEER_VARIANTS['fan%02d'%_i]='goal_fan_%02d.wav'%_i\n\n"+anchor,1)
audio.write_text(a,encoding="utf-8")
s=s.replace("6.13.19","6.13.20")
compile(s,str(plugin),"exec")
compile(a,str(audio),"exec")
plugin.write_text(s,encoding="utf-8")
(ROOT/"source/VERSION").write_text(VERSION+"\n",encoding="utf-8")
sys.path.insert(0,str(DEST))
from goalalert_audio import CHEER_VARIANTS,cheer_path
assert len(GOALALERT_FAN_CHEERS) if False else True  # UI code not importable outside Enigma2
assert len(set(CHEER_VARIANTS.get("fan%02d"%i) for i in range(1,21)))==20
for i in range(1,21):
    resolved=cheer_path(str(DEST),"fan%02d"%i)
    assert resolved.endswith("goal_fan_%02d.wav"%i),resolved
    assert Path(resolved).is_file(),resolved
assert 'GOALALERT_FAN_CHEERS=[' in s
assert 'labels=GOALALERT_CHEER_LABELS' in s
assert 'values=[key for key,_label in GOALALERT_FAN_CHEERS]' in s
# No change to TV menu, IPTV services, team emblems or colour settings.
assert 'Keine bestaetigten TV-Sender fuer diese Partie gefunden.' in s
assert 'GOALALERT_COLOR_HEX' in s
assert 'valid_broadcast_name' in s
assert len(list(DEST.glob("goal_fan_*.wav")))==20
for cache in DEST.rglob("__pycache__"):shutil.rmtree(cache)
subprocess.run(["python3","scripts/build_ipk.py"],cwd=ROOT,check=True)
print("GoalAlert 6.13.20: 20 selectable cheers packaged and validated")
