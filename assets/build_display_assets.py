"""Generate experimental bitmap fonts and border sprites from the released art."""
from pathlib import Path
import importlib.util
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gizmo_font',ROOT/'assets/build_font.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

ROWS=((0,1,2,3,4,5,6),(0,1,2,3,5,6),(0,1,3,5,6))
WAVE=(10,10,10,9,8,6,4,3,5,8,10,11,12,14,16,17,15,12,10,9,10,10,10,10)


def build():
    original=module.build()
    fonts=bytearray()
    for rows in ROWS:
        for code in range(128):
            glyph=original[code*8:code*8+8]
            fonts.extend(glyph[row] for row in rows)
            fonts.extend(b'\0'*(8-len(rows)))
    _,header=module.header_art()
    def pixel(x,y):
        code=header[(y//8)*40+x//8]
        return bool(original[code*8+y%8] & (0x80>>(x%8)))
    sprites=bytearray(11*64)
    for sprite in range(7):
        for y in range(21):
            sy=1+y
            for x in range(24):
                sx=sprite*48+x*2
                if sx<320 and (pixel(sx,sy) or pixel(sx+1,sy)):
                    sprites[sprite*64+y*3+x//8]|=0x80>>(x%8)
    for frame in range(4):
        base=(7+frame)*64
        for x in range(24):
            value=WAVE[(x+frame*2)%24]
            previous=WAVE[(x-1+frame*2)%24] if x else value
            for y in range(min(value,previous),max(value,previous)+1):
                if y<21:sprites[base+y*3+x//8]|=0x80>>(x%8)
    return bytes(fonts+sprites)


if __name__=='__main__':
    data=build()
    path=ROOT/'assets/display-prototype.bin'
    path.write_bytes(data)
    (ROOT/'assets/display-prototype.json').write_text(json.dumps({
        'font_modes':['standard-5x7-8','compact-5x6-7','dense-5x5-6'],
        'font_bytes':3072,'sprite_bytes':704,'sha256':hashlib.sha256(data).hexdigest()
    },indent=2)+'\n',encoding='utf-8')
    print(path,len(data),hashlib.sha256(data).hexdigest())
