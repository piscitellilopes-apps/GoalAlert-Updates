#!/usr/bin/env python3
"""Generate truly transparent rounded GoalAlert popup backgrounds.

No blue/RGB corners; RGBA transparent outside clipping mask. Supersampled
at 3x for clean antialiasing, with 720p and native 1080p variants.
"""
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "source" / "GoalAlert"
SIZES = {"mini": (520, 90), "compact": (640, 104), "normal": (780, 122)}

def make(w,h,kind,ratio,path):
    w,h=int(round(w*ratio)),int(round(h*ratio))
    s=3
    size=(w*s,h*s)
    glow=(30,195,255) if kind=="goal" else (10,255,182)
    base=Image.new("RGBA",size,(0,0,0,0))
    margin=max(4,int(5*ratio*s))
    radius=max(12,int(18*ratio*s))
    # Rounded clipping mask includes all raster layers.
    mask=Image.new("L",size,0)
    md=ImageDraw.Draw(mask)
    rect=(margin,margin,size[0]-margin-1,size[1]-margin-1)
    md.rounded_rectangle(rect,radius=radius,fill=255)
    # Dark, glossy navy tinted glass; no opaque rectangle outside curve.
    g=Image.new("RGBA",size,(0,0,0,0))
    pix=g.load()
    for y in range(size[1]):
        for x in range(size[0]):
            v=y/max(1,size[1])
            spec=max(0,1-abs(v-.10)/.28)
            px=(int(6+12*spec),int(22+25*spec),int(46+26*spec),int(231-19*v))
            pix[x,y]=px
    g.putalpha(Image.composite(g.getchannel('A'),Image.new('L',size,0),mask))
    base.alpha_composite(g)
    # Highlighted upper arc + luminous border, no out-of-mask overpainting.
    strokes=Image.new("RGBA",size,(0,0,0,0))
    draw=ImageDraw.Draw(strokes)
    draw.rounded_rectangle(rect,radius=radius,outline=(*glow,235),width=max(2,int(1.6*ratio*s)))
    inset=int(3*ratio*s)
    draw.rounded_rectangle((rect[0]+inset,rect[1]+inset,rect[2]-inset,rect[3]-inset),
                           radius=max(3,radius-inset),outline=(175,241,255,72),width=max(1,int(ratio*s)))
    # Top glass sheen and bottom footer strip.
    y_top=rect[1]+int(8*ratio*s)
    draw.line((rect[0]+radius//2,y_top,rect[2]-radius//2,y_top),fill=(220,247,255,110),width=max(1,int(ratio*s)))
    footer_y=int((h-26*ratio)*s)
    draw.line((rect[0]+12*s,footer_y,rect[2]-12*s,footer_y),fill=(*glow,140),width=max(1,int(1.2*ratio*s)))
    # Central glass plate on which the score is typeset.
    cx=size[0]//2
    plate_w=int(w*120/640*s)
    plate_h=int(h*49/104*s)
    platerect=(cx-plate_w//2,int(22*ratio*s),cx+plate_w//2,int(22*ratio*s)+plate_h)
    draw.rounded_rectangle(platerect,radius=int(8*ratio*s),fill=(21,67,110,200),outline=(*glow,195),width=max(1,int(1.1*ratio*s)))
    # Soft exterior glow is clipped to the same rounded silhouette.
    soft=strokes.filter(ImageFilter.GaussianBlur(max(3,3*ratio*s)))
    soft.putalpha(Image.composite(soft.getchannel("A"),Image.new("L",size,0),mask))
    base.alpha_composite(soft)
    base.alpha_composite(strokes)
    # Clip again: no blue corner artifacts on any layer.
    base.putalpha(Image.composite(base.getchannel('A'),Image.new('L',size,0),mask))
    # High-quality antialiasing from oversampled vector-like primitives.
    base=base.resize((w,h),Image.Resampling.LANCZOS)
    base.save(path,optimize=True)

def main():
    for variant,(w,h) in SIZES.items():
        for kind in ("goal","scorer"):
            suffix="" if variant=="compact" else "_"+variant
            for hd,ratio in ((False,1),(True,1.5)):
                name=f"ga_popup_{kind}{suffix}{'_fhd' if hd else ''}.png"
                make(w,h,kind,ratio,OUT/name)
                im=Image.open(OUT/name)
                assert im.mode=="RGBA" and im.getpixel((0,0))[3]==0,(name,im.getpixel((0,0)))
    print("Generated 12 fully transparent glass overlays with real rounded corners")
if __name__=="__main__":
    main()
