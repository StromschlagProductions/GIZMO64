"""Capture the compiled PRG in VICE; the Ultimate ACIA is not emulated."""
from pathlib import Path
import hashlib
import json
import subprocess

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

ROOT=Path(__file__).resolve().parents[1]
VICE=ROOT/'.local-tools/vice/SDL2VICE-3.9-win64/x64sc.exe'
PRG=ROOT/'build/GIZMO64-04B.PRG'
SHOTS=ROOT/'screenshots'


def capture(name,keys=None):
    target=SHOTS/f'vice-04b-{name}.png'
    log=ROOT/'build'/f'vice-04b-{name}.log'
    command=[str(VICE),'-logfile',str(log),'-autostartprgmode','1',
             '-autostart',str(PRG),'-exitscreenshot',str(target),
             '-limitcycles','30000000','-silent']
    if keys:command[1:1]=['-keybuf',keys]
    target.unlink(missing_ok=True)
    result=subprocess.run(command,cwd=VICE.parent,check=False,timeout=120)
    if result.returncode not in (0,1) or 'cycle limit reached' not in log.read_text(encoding='utf-8',errors='replace'):
        raise RuntimeError(f'VICE did not reach its planned cycle limit: {result.returncode}')
    if not target.is_file():raise RuntimeError(f'VICE screenshot missing: {target}')
    shot=QImage(str(target))
    if shot.isNull() or shot.width()!=384 or shot.height()!=272:
        raise RuntimeError(f'Invalid VICE screenshot: {target}')
    def ink(x1,y1,x2,y2):
        return sum(shot.pixelColor(x,y).name()!='#000000'
                   for y in range(y1,y2) for x in range(x1,x2))
    if ink(35,35,350,59)<500:
        raise RuntimeError(f'Compiled header did not render in VICE: {target}')
    if name=='service' and ink(35,68,350,155)<500:
        raise RuntimeError('Service diagnostics did not finish drawing')
    if name=='input' and ink(35,68,350,95)<100:
        raise RuntimeError('Synthetic keyboard input was not displayed')
    shot.scaled(shot.width()*3,shot.height()*3,Qt.IgnoreAspectRatio,
                Qt.FastTransformation).save(str(SHOTS/f'vice-04b-{name}-3x.png'))
    print(target)


def main():
    if not VICE.is_file() or not PRG.is_file():
        raise RuntimeError('Build PRG and unpack project-local VICE first')
    SHOTS.mkdir(exist_ok=True)
    capture('green')
    capture('ice',r'\x85')
    capture('input',r'HELLO GIZMO?\x0d')
    capture('service',r'\x8c')
    green=QImage(str(SHOTS/'vice-04b-green.png'))
    ice=QImage(str(SHOTS/'vice-04b-ice.png'))
    if green.pixelColor(150,45)==ice.pixelColor(150,45):
        raise RuntimeError('F1 did not change the palette in VICE')
    digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'program':'build/GIZMO64-04B.PRG','program_sha256':digest(PRG),
              'emulator':'VICE 3.9 SDL2','hardware_link_emulated':False,
              'screenshots':{name:digest(SHOTS/f'vice-04b-{name}.png')
                             for name in ('green','ice','input','service')}}
    (SHOTS/'vice-04b-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
