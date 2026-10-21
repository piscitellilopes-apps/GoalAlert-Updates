# -*- coding: utf-8 -*-
"""GoalAlert 6.13.11 audio, multiple cheers, mixer-first backends.

This module is imported from GoalAlert/plugin.py. All audio playback is
non-blocking; NEVER stop or replace the currently playing TV service.
"""
from __future__ import absolute_import
import os
import shutil
import subprocess
import threading
from datetime import datetime

AUDIO_LOG='/etc/enigma2/goalalert_audio.log'
CHEER_VARIANTS={'classic':'goal.wav','stadium':'goal_stadium.wav',
                'double':'goal_double.wav','short':'goal_short.wav'}

def _log(msg):
    try:
        with open(AUDIO_LOG,'a') as f:
            f.write('%s: %s\n'%(datetime.now().isoformat(),str(msg)[:320]))
    except Exception:pass

def cheer_path(root,choice):
    filename=CHEER_VARIANTS.get(str(choice),'goal.wav')
    candidate=os.path.join(root,filename)
    if os.path.isfile(candidate):return candidate
    return os.path.join(root,'goal.wav')

def available_backends(path):
    # Prefer software mixers; generic devices may fail if DVB audio is playing.
    gst=['gst-launch-1.0','-q','filesrc','location='+path,'!','wavparse',
         '!','audioconvert','!','audioresample','!']
    options=[
        ('GStreamer PulseAudio',gst+['pulsesink','sync=false']),
        ('GStreamer PipeWire',gst+['pipewiresink','sync=false']),
        ('GStreamer ALSA dmix',gst+['alsasink','device=plug:dmix','sync=false']),
        ('ALSA plug:dmix',['aplay','-q','-D','plug:dmix',path]),
        ('GStreamer auto',gst+['autoaudiosink','sync=false']),
        ('ALSA default',['aplay','-q',path]),
        ('MPV',['mpv','--no-video','--really-quiet',path]),
        ('FFplay',['ffplay','-nodisp','-autoexit','-loglevel','error',path])]
    return [(name,cmd) for name,cmd in options if shutil.which(cmd[0])]

def play(path):
    """True simultaneous sound needs Pulse/PipeWire/ALSA dmix support on box.

    A bitstream-passthrough or exclusive PCM sink cannot be overridden
    without changing device-wide TV audio. Fail visibly in the log instead.
    """
    if not os.path.isfile(path):
        _log('Audio-Datei fehlt: '+str(path))
        return False
    backends=available_backends(path)
    if not backends:
        _log('Kein Audio-Player installiert (GStreamer/ALSA fehlen)')
        return False
    def worker():
        for label,cmd in backends:
            try:
                p=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                    start_new_session=True,close_fds=True)
                try:_,err=p.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    p.kill()
                    _,err=p.communicate()
                if p.returncode==0:
                    _log(label+': Playback OK; TV-Ton-Mischung nur am Receiver pruefbar')
                    return
                details=err.decode('utf-8','replace').replace('\n',' ')[-145:]
                _log(label+': Exit %d %s'%(p.returncode,details))
            except Exception as exc:
                _log(label+': '+type(exc).__name__+': '+str(exc)[:140])
        _log('Audiomixer belegt / nicht verfuegbar. Bei PCM-Downmix testen; '
             'AC3/DTS-Passthrough verhindert oft PCM-Mischung.')
    threading.Thread(target=worker,daemon=True).start()
    return True
