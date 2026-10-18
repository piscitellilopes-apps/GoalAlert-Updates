#!/usr/bin/env python3
"""Build GoalAlert 6.13.6 automatically from published 6.13.5 and text-only fixes.

No private bouquets or credentials are included. Fails closed if base changes.
"""
import io
import pathlib
import shutil
import subprocess
import tarfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'enigma2-plugin-extensions-goalalert_6.13.5_all.ipk'
DEST=ROOT/'source/GoalAlert'
PREFIX='usr/lib/enigma2/python/Plugins/Extensions/GoalAlert/'
if not BASE.is_file():
    raise SystemExit('Verified base IPK 6.13.5 is missing')
DEST.mkdir(parents=True,exist_ok=True)

# Extract ONLY the public, whitelisted GoalAlert plugin files from the known base.
data=subprocess.check_output(['ar','p',str(BASE),'data.tar.xz'])
with tarfile.open(fileobj=io.BytesIO(data),mode='r:xz') as tf:
    for member in tf:
        clean=member.name.lstrip('./')
        if not clean.startswith(PREFIX) or not member.isfile():continue
        relative=clean[len(PREFIX):]
        if not relative or '..' in pathlib.PurePosixPath(relative).parts:raise RuntimeError('Unsafe member')
        if relative.endswith(('.pyc','.m3u','.m3u8','.log')) or '__pycache__' in relative or 'iptv_names_' in relative:
            continue
        target=DEST/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tf.extractfile(member).read())

path=DEST/'plugin.py'
s=path.read_text(encoding='utf-8')
if 'GOALALERT 6.13.5 | SPORT STUDIO' not in s:
    raise SystemExit('Expected base source version missing')
def swap(old,new,count=1):
    global s
    found=s.count(old)
    if found!=count:raise SystemExit('Unexpected source: expected %s matches, found %s for %s'%(count,found,old[:80]))
    s=s.replace(old,new,count)

needle='def get_games(league,date):\n    url="https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s" %(league,date)'
swap(needle,'''def _espn_team_crest_url(team):
    """Use provider crest first, ESPN team logo URL when absent."""
    if not isinstance(team,dict):return ''
    candidate=team.get('logo') or next((x.get('href') for x in team.get('logos',[]) if isinstance(x,dict) and x.get('href')), '')
    if candidate and str(candidate).startswith('https://'):return candidate
    team_id=str(team.get('id') or '')
    if team_id.isdigit() and len(team_id)<=10:
        return 'https://a.espncdn.com/i/teamlogos/soccer/500/%s.png'%team_id
    return ''

'''+needle)
swap('"home_logo":home.get("team",{}).get("logo", ""),','"home_logo":_espn_team_crest_url(home.get("team",{})),')
swap('"away_logo":away.get("team",{}).get("logo", ""),','"away_logo":_espn_team_crest_url(away.get("team",{})),')

# The preview callback previously referenced undefined 'placeholder' and silently hid errors.
preview=s.index('class CrestPreviewScreen(Screen):')
preload=s.index('def preload_favorite_crests(',preview)
part=s[preview:preload]
a='''                    if placeholder and target in self.crests_loaded:
                        return
                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                except Exception:pass'''
b='''                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                except Exception as exc:
                    _crest_log('Wappenvorschau Decode: '+str(exc)[:100])'''
if part.count(a)!=1:raise SystemExit('Missing preview bug anchor')
s=s[:preview]+part.replace(a,b)+s[preload:]

# Mark a real club badge loaded ONLY after the ePicLoad callback succeeded.
popup=s.index('class GoalPopup(Screen):')
audio=s.index('AUDIO_LOG=',popup)
part=s[popup:audio]
a='''                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                except Exception:pass'''
b='''                    if pix is not None and self[target].instance is not None:
                        self[target].instance.setPixmap(pix)
                        self[target].instance.show()
                        if not placeholder:
                            self.crests_loaded.add(target)
                    elif not placeholder:
                        _crest_log('Wappen-Decoder: keine Bilddaten fuer '+target)
                except Exception as exc:
                    _crest_log('Wappen-Decoderfehler: '+str(exc)[:100])'''
if part.count(a)!=1:raise SystemExit('Missing real badge decoder anchor')
part=part.replace(a,b)
a='''                self.crests_loaded.add(widget)
                sz=int(round(self.crest_size*_goalalert_ui_scale()))'''
b='''                sz=int(round(self.crest_size*_goalalert_ui_scale()))'''
if part.count(a)!=1:raise SystemExit('Missing early badge-loaded anchor')
part=part.replace(a,b)
a='''    def dismiss(self):
        try:
            if getattr(self,'overlay_owner',None):self.overlay_owner.hide_goal()
            else:self.close()
        except Exception:pass'''
b='''    def dismiss(self):
        try:self.close()
        except Exception:pass'''
if part.count(a)!=1:raise SystemExit('Missing popup session-close anchor')
part=part.replace(a,b)
s=s[:popup]+part+s[audio:]

# Both blue and green test popups must use actual game crests.
swap('''            test=getattr(self,'pending_test_goal',None)
            self.pending_test_goal=None
        if test is not None:
            if test is False:
                _crest_log('Test-Toralarm: keine Live-Spiel-Wappen verfuegbar')
                self.show_goal('TEST: Wappen fehlen, siehe Wappen-Diagnose',kind='goal')
            else:
                self.show_goal('TEST: ECHTE WAPPEN | TORALARM',test.get('home_logo_file'),test.get('away_logo_file'),
                               kind='goal',home_url=test.get('home_logo'),away_url=test.get('away_logo'),game=test)''',
'''            test=getattr(self,'pending_test_goal',None)
            test_kind=getattr(self,'pending_test_kind','goal')
            self.pending_test_goal=None
        if test is not None:
            if test is False:
                _crest_log('Test-Popup: keine Live-Spiel-Wappen verfuegbar')
                self.show_goal('TEST: Wappen fehlen, siehe Wappen-Diagnose',kind=test_kind)
            else:
                title='TEST: TORSCHUETZE (OHNE TON)' if test_kind=='scorer' else 'TEST: ECHTE WAPPEN | TORALARM'
                self.show_goal(title,test.get('home_logo_file'),test.get('away_logo_file'),
                               kind=test_kind,home_url=test.get('home_logo'),away_url=test.get('away_logo'),game=test)''')
swap('''    def test_goal(self):
        # Never present demo logos as real: obtain a real game in a worker.
''','''    def test_goal(self,kind='goal'):
        # Never present demo logos as real: obtain a real game in a worker.
''')
swap('''        with self.lock:
            self.pending_test_goal=None
        if getattr(self,'test_goal_busy',False):return''',
'''        with self.lock:
            self.pending_test_goal=None
            self.pending_test_kind=kind if kind in ('goal','scorer') else 'goal'
        if getattr(self,'test_goal_busy',False):return''')
swap('''    def test_scorer(self):
        self.show_goal('TEST: GRUEN | TORSCHUETZE (OHNE TON)',kind='scorer')
''','''    def test_scorer(self):
        self.test_goal(kind='scorer')
''')

# instantiateDialog().show() was under GoalAlert menus: use a real session popup.
start=s.index("    def show_goal(self,message,logo_path=None,away_logo_path=None,kind='goal',home_url=None,away_url=None,game=None):")
end=s.index('    def fetch(self):',start)
s=s[:start]+'''    def _popup_closed(self,token):
        if getattr(self,'popup_token',None)==token:
            self.popup=None
    def show_goal(self,message,logo_path=None,away_logo_path=None,kind='goal',home_url=None,away_url=None,game=None):
        """Open transient overlay through Session; it stays above menus."""
        try:
            self.hide_goal()
            self.popup_token=getattr(self,'popup_token',0)+1
            token=self.popup_token
            self.popup=self.session.openWithCallback(
                lambda *args:self._popup_closed(token),GoalPopup,message,
                config.plugins.goalalert32.duration.value,logo_path,kind=='goal',
                away_logo_path,kind,home_url,away_url,game)
        except Exception as exc:
            self.popup=None
            _crest_log('Popup kann nicht angezeigt werden: '+str(exc)[:100])
    def hide_goal(self):
        if self.dismiss_timer is not None:self.dismiss_timer.stop()
        if self.popup is not None:
            popup=self.popup;self.popup=None
            try:popup.close()
            except Exception as exc:_crest_log('Popup-Schliessen: '+str(exc)[:100])
'''+s[end:]

# Real updater progress, correct Python executable, no optimistic success message.
start=s.index('class GoalAlertUpdateScreen(BaseScreen):')
end=s.index('class Home(BaseScreen):',start)
part=s[start:end]
a='''        if self.pending is None:return
        self.timer.stop()
        self.busy=False'''
b='''        if self.pending is None:
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
        self.busy=False'''
if part.count(a)!=1:raise SystemExit('Missing install poll anchor')
part=part.replace(a,b)
a='''        else:
            self._status(val)
    def yellow(self):'''
b='''        else:
            self._status(val)
            if kind=='installing':
                self.install_waiting=True
                self.busy=True
                self.timer.start(500,False)
    def yellow(self):'''
if part.count(a)!=1:raise SystemExit('Missing install result anchor')
part=part.replace(a,b)
part=part.replace("                with open('/home/root/goalalert_update_launcher.log','ab') as log:\n",
                  "                try:os.unlink('/tmp/goalalert_update_status.json')\n                except OSError:pass\n                with open('/home/root/goalalert_update_launcher.log','ab') as log:\n")
part=part.replace("subprocess.Popen(['/usr/bin/python3',helper,",
                  "subprocess.Popen([__import__('sys').executable,helper,")
part=part.replace("result=('info','Installation laeuft, TV startet danach neu ...')",
                  "result=('installing','Paket geprueft. Installiere GoalAlert ...')")
s=s[:start]+part+s[end:]
s=s.replace('6.13.5','6.13.6')
path.write_text(s,encoding='utf-8')
shutil.copyfile(ROOT/'releases/6.13.6_apply_update.py',DEST/'goalalert_apply_update.py')
(ROOT/'source/VERSION').write_text('6.13.6\n')
subprocess.run(['python3','-m','py_compile',str(path),str(DEST/'goalalert_apply_update.py')],check=True)
# Syntaxcheck erzeugt __pycache__; niemals kompilierte lokale Artefakte paketieren.
for cache in DEST.rglob('__pycache__'):
    shutil.rmtree(cache)
subprocess.run(['python3','scripts/build_ipk.py'],check=True,cwd=ROOT)
print('GoalAlert 6.13.6 repaired IPK assembled from base, with no personal IPTV credentials')
