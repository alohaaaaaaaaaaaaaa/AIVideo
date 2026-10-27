"""Rebuild the name-only transparent watermark from its preserved glyph mask.

Requires Pillow. Run this file with Python; no system fonts or video files needed.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageFilter

ROOT=Path(__file__).resolve().parents[1]


def shift(mask,dx,dy):
    result=Image.new('L',mask.size)
    result.paste(mask,(dx,dy))
    return result


def tint(mask,rgb,opacity):
    result=Image.new('RGBA',mask.size,rgb+(0,))
    result.putalpha(mask.point(lambda v:round(v*opacity)))
    return result


def build():
    mask=Image.open(ROOT/'源文件/字形蒙版.png').convert('L')
    assert mask.size==(896,280)
    highlight=ImageChops.subtract(mask,shift(mask,5,5)).filter(ImageFilter.GaussianBlur(.5))
    shadow=ImageChops.subtract(mask,shift(mask,-5,-5)).filter(ImageFilter.GaussianBlur(.5))
    rim=ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)),mask.filter(ImageFilter.MinFilter(3)))
    master=Image.alpha_composite(tint(rim,(244,245,238),.12),tint(shadow,(0,5,13),.60))
    master=Image.alpha_composite(master,tint(highlight,(250,250,243),.78))
    folder=ROOT/'透明PNG';folder.mkdir(exist_ok=True)
    for name,size in [('高清母版',(896,280)),('1080p',(224,70)),('4K',(448,140))]:
        im=master if size==master.size else master.resize(size,Image.Resampling.LANCZOS)
        im.save(folder/f'啊子牙_悠哉_B站无账号_{name}.png')
    return master


if __name__=='__main__':
    build()
    print('透明PNG已按保存的原始字形重建。')
