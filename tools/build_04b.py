"""Reproducible local C64 build and host regression suite; no global tools needed."""
from pathlib import Path
import os
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'build'
CL65=ROOT/'.local-tools/cc65/bin/cl65.exe'
TCC=ROOT/'.local-tools/tcc/tcc/tcc.exe'
PRG=BUILD/'GIZMO64-04B.PRG'
MAP=BUILD/'GIZMO64-04B.map'


def run(*args,env=None):
    print(' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),cwd=ROOT,env=env,check=True)


def main():
    if not CL65.is_file() or not TCC.is_file():
        raise RuntimeError('Projektlokales cc65 oder TinyCC fehlt; siehe docs/04B-C64-TERMINAL.md')
    BUILD.mkdir(exist_ok=True)
    run(sys.executable,ROOT/'assets/build_font.py')
    run(CL65,'-t','c64','-O','-I','src','-Wl',f'-m,{MAP.as_posix()}',
        '-o',PRG,'src/main.c','src/ui.c','src/link.c','src/font.s')
    segments={name:(int(start,16),int(end,16)) for name,start,end in
              re.findall(r'^([A-Z]+)\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+[0-9A-F]{6}',
                         MAP.read_text(encoding='utf-8'),re.M)}
    if not {'CODE','RODATA','DATA','BSS'} <= segments.keys():
        raise RuntimeError('Unvollständige Linker-Map')
    if max(end for name,(_start,end) in segments.items()
           if name in ('CODE','RODATA','DATA','BSS')) >= 0x6400:
        raise RuntimeError('PRG belegt reservierten Screen-RAM ab $6400')
    for name,source in (('ui','src/ui.c'),('link','src/link.c'),
                        ('charset_conversion','src/link.c')):
        flags=['-DGIZMO_TEST','-I','src','-Wall','-Wextra']
        if name=='charset_conversion':flags.append('-DGIZMO_PETSCII_TEST')
        run(TCC,*flags,'-o',BUILD/(name+'_test.exe'),'tests/'+name+'_test.c',source)
        run(BUILD/(name+'_test.exe'))
    environment=dict(os.environ,GIZMO_PRG_PATH=str(PRG))
    run(sys.executable,'tests/prg_test.py',env=environment)
    run(sys.executable,'tests/charset_test.py')
    run(sys.executable,'-m','unittest','tests.test_font','-v')
    print(f'04B build passed: {PRG} ({PRG.stat().st_size} bytes), BSS end ${segments["BSS"][1]:04X}')


if __name__=='__main__':main()
