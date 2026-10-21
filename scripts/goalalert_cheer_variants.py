#!/usr/bin/env python3
"""Generate 4 GoalAlert cheers using only the included goal.wav recording.

No downloads, no user recordings, no third-party copyrighted assets.
"""
from pathlib import Path
from array import array
import wave

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'source/GoalAlert'
original=TARGET/'goal.wav'
with wave.open(str(original),'rb') as input:
    assert input.getnchannels()==1 and input.getsampwidth()==2
    rate=input.getframerate()
    assert 8000<=rate<=48000
    data=array('h')
    data.frombytes(input.readframes(input.getnframes()))
values=list(data)
assert len(values)>rate
def clamp(x):return max(-32768,min(32767,int(x)))
def write(filename, samples):
    pcm=array('h',(clamp(v) for v in samples))
    with wave.open(str(TARGET/filename),'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    assert (TARGET/filename).stat().st_size>1024
delay=int(rate*.17)
write('goal_stadium.wav',[v*.88+(values[i-delay]*.36 if i>=delay else 0)
                          for i,v in enumerate(values)])
write('goal_double.wav',values+[0]*int(rate*.14)+[v*.82 for v in values])
cut=min(len(values),int(rate*1.6))
fade=min(cut,int(rate*.2))
write('goal_short.wav',[v*min(1,max(0,(cut-i)/float(fade)))
                        for i,v in enumerate(values[:cut])])
print('Generated stadion echo, double and short variants')
