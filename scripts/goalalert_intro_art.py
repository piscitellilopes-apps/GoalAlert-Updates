#!/usr/bin/env python3
"""Render original, glossy GoalAlert GOAL roll-in animation frames.

Two OSD sprite sets: 720p and 1080p. The 4K-style football is rendered
at high supersampling, then downscaled to the actual receiver overlay.
All backgrounds are true RGBA with transparent exterior corners.
"""
from pathlib import Path
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont
OUT=Path(__file__).resolve().parents[1]/'source'/'GoalAlert'
OUT.mkdir(parents=True,exist_ok=True)
FRAMES=12

def font(size):
    for fp in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
               '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf'):
        if Path(fp).is_file():return ImageFont.truetype(fp,size)
    return ImageFont.load_default()

def football(diameter):
    im=Image.new('RGBA',(diameter,diameter),(0,0,0,0))
    cx=cy=diameter/2
    rr=diameter*.48
    p=im.load()
    for y in range(diameter):
        for x in range(diameter):
            dx=(x-cx)/rr
            dy=(y-cy)/rr
            r2=dx*dx+dy*dy
            if r2>=1:continue
            z=math.sqrt(1-r2)
            light=max(0,(.35*-dx+.72*-dy+.6*z))
            shininess=max(0,1-((dx+.38)**2+(dy+.52)**2)*7)**6
            shade=int(78+155*light+80*shininess)
            shade=max(0,min(255,shade))
            p[x,y]=(shade, min(255,shade+5),min(255,shade+10),255 if r2<.985 else int((1-r2)/.015*255))
    draw=ImageDraw.Draw(im,'RGBA')
    # High-gloss panel outlines suggesting a classic football without
    # third-party art or copyrighted logos.
    def polygon(cx,cy,rad,sides,rotation,fill):
        return [(int(cx+rad*math.cos(rotation+k*2*math.pi/sides)),
                 int(cy+rad*math.sin(rotation+k*2*math.pi/sides))) for k in range(sides)]
    draw.polygon(polygon(cx,cy,diameter*.15,5,-math.pi/2,(24,31,48,250)),fill=(16,29,49,245))
    for k in range(5):
        t=-math.pi/2+2*math.pi*k/5
        nx=cx+diameter*.29*math.cos(t)
        ny=cy+diameter*.29*math.sin(t)
        draw.polygon(polygon(nx,ny,diameter*.11,5,t/2,(18,28,46,220)),fill=(30,48,65,235))
        draw.line([(cx+diameter*.14*math.cos(t),cy+diameter*.14*math.sin(t)),(nx,ny)],fill=(9,30,48,200),width=max(1,diameter//85))
    draw.ellipse((cx-diameter*.37,cy-diameter*.41,cx+diameter*.04,cy-diameter*.22),
                 fill=(255,255,255,35))
    return im

def render(outw,outh,suffix):
    ss=2
    w,h=outw*ss,outh*ss
    ball=football(int(h*1.17))
    for k in range(FRAMES):
        t=k/(FRAMES-1)
        frame=Image.new('RGBA',(w,h),(0,0,0,0))
        glow=Image.new('RGBA',(w,h),(0,0,0,0))
        gd=ImageDraw.Draw(glow)
        gd.rounded_rectangle((12*ss,5*ss,w-12*ss,h-5*ss),radius=18*ss,
            fill=(20,150,255,34),outline=(22,209,255,120),width=5*ss)
        frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5*ss)))
        d=ImageDraw.Draw(frame,'RGBA')
        d.rounded_rectangle((6*ss,7*ss,w-6*ss,h-7*ss),radius=18*ss,
            fill=(9,32,76,115),outline=(75,222,255,225),width=2*ss)
        d.rounded_rectangle((10*ss,12*ss,w-10*ss,h-12*ss),radius=14*ss,
            outline=(200,250,255,90),width=1*ss)
        d.line((38*ss,23*ss,(outw-38)*ss,23*ss),fill=(101,240,255,70),width=ss)
        face=font(int(58*ss))
        text='GOAL'
        # Reveal the luminous GOAL word behind the incoming ball
        tx,ty=205*ss,14*ss
        for offset,alpha in ((7,20),(4,48),(2,130)):
            d.text((tx,ty),text,font=face,fill=(0,205,255,alpha),stroke_width=offset*ss,stroke_fill=(0,159,255,alpha))
        d.text((tx,ty),text,font=face,fill=(248,252,255,int(65+190*min(1,t*1.6))),
               stroke_width=1*ss,stroke_fill=(123,234,255,240))
        # Bright rolling football arrives ahead of the GOAL title.
        bx=int((-115+220*(t**.68))*ss)
        by=int((outh-136)/2*ss)
        sprite=ball.rotate(-k*35,resample=Image.Resampling.BICUBIC,expand=False)
        frame.alpha_composite(sprite,(bx,by))
        # Slim light streak from ball, not a rectangular solid underlay.
        trail=max(0,bx+30*ss)
        if trail>0:
            d.line((max(12,trail-38*ss),h//2,trail,h//2),
                   fill=(70,228,255,int(120*(1-t))),width=2*ss)
        frame.resize((outw,outh),Image.Resampling.LANCZOS).save(
            OUT/('ga_goal_intro_%02d%s.png'%(k,suffix)),optimize=True)
        final=Image.open(OUT/('ga_goal_intro_%02d%s.png'%(k,suffix)))
        assert final.getpixel((0,0))[3]==0 and final.getpixel((outw-1,outh-1))[3]==0
    print('Rendered',suffix,'frames',FRAMES)

render(640,104,'')
render(960,156,'_fhd')
