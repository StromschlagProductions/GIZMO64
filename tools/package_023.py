"""Package only the tested C64 client and its current instructions."""
import argparse
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
GUIDE=ROOT/'docs/kurzanleitung-0.2.3.md'


def add(archive,name,content):
    info=ZipInfo(name,(2026,11,27,0,0,0))
    info.compress_type=ZIP_DEFLATED
    archive.writestr(info,content)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prg',type=Path,default=ROOT/'build/GIZMO64-04B.PRG')
    parser.add_argument('--output',type=Path,default=ROOT/'build/GIZMO64-v0.2.3.zip')
    args=parser.parse_args()
    program=args.prg.read_bytes()
    if program[:2]!=b'\x01\x08':raise RuntimeError('Invalid C64 load address')
    guide=GUIDE.read_bytes()
    digest=sha256(program).hexdigest()
    with ZipFile(args.output,'w') as archive:
        add(archive,'GIZMO64.PRG',program)
        add(archive,'KURZANLEITUNG.md',guide)
        add(archive,'SHA256.txt',(digest+'  GIZMO64.PRG\n').encode('ascii'))
    with ZipFile(args.output) as archive:
        if archive.namelist()!=['GIZMO64.PRG','KURZANLEITUNG.md','SHA256.txt']:
            raise RuntimeError('Unexpected package contents')
        if archive.read('GIZMO64.PRG')!=program:raise RuntimeError('Package verification failed')
    print(f'{args.output}: {len(program)} PRG bytes, SHA256 {digest}')


if __name__=='__main__':main()
