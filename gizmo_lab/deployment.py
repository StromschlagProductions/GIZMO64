"""Versioned local LAB installation. Never opens the user's data directory."""
import argparse
import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
from zipfile import ZipFile, BadZipFile

REPOSITORY = 'https://github.com/StromschlagProductions/GIZMO64.git'
FILES = ('gizmo_lab.py','memory.py','analysis.py','version.py','deployment.py','character.py',
         'config.example.json','personality.example.txt','questions.json','variants.example.json','story_lite.py',
         'character_library/GIZMO_Awakening_V3_EN.txt','character_library/character_library_en.json',
         'README.md','LOCAL-DEVELOPMENT.md','MEMORY.md','ARCHITEKTUR-0.3.md',
         'story.py','STORY-DIRECTOR.md','narrative_library/README.md','narrative_library/REFERENZEN.md',
         'narrative_library/director_prompt_en.txt','narrative_library/narrative_library.json',
         'narrative_library/narrative_library.schema.json',
         'narrative_library/origin_campaign_policy.json','narrative_library/select_dna.py')
TAG = re.compile(r'lab-v(\d+)\.(\d+)\.(\d+)$')


def release_files(source):
    """Read the file list from the release being installed, not the old updater."""
    tree=ast.parse((source/'deployment.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FILES' for t in node.targets):
            names=ast.literal_eval(node.value)
            if (not isinstance(names,tuple) or not names or
                any(not isinstance(name,str) or not name or Path(name).is_relative_to('..') or
                    Path(name).is_absolute() or '..' in Path(name).parts for name in names)):
                break
            return names
    raise RuntimeError('Ungültige Release-Dateiliste')


def atomic_json(path, value):
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,indent=2),encoding='utf-8')
    os.replace(temporary,path)


@contextmanager
def installation_lock(root):
    root.mkdir(parents=True,exist_ok=True)
    with (root/'installation.lock').open('a+b') as handle:
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            if os.fstat(handle.fileno()).st_size==0:
                handle.write(b'0');handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError as error:
                raise RuntimeError('GIZMO läuft bereits oder wird gerade aktualisiert.') from error
        else:
            import fcntl
            try:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError('GIZMO läuft bereits oder wird gerade aktualisiert.') from error
        try:
            yield
        finally:
            if os.name=='nt':
                handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                fcntl.flock(handle,fcntl.LOCK_UN)


def release_version(source):
    for name in release_files(source):
        path=source/name
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'Unvollständige LAB-Version: {name}')
        if path.suffix=='.py':
            compile(path.read_text(encoding='utf-8'),str(path),'exec')
    tree=ast.parse((source/'version.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in node.targets):
            version=ast.literal_eval(node.value)
            if isinstance(version,str) and TAG.fullmatch('lab-v'+version):
                return version
    raise RuntimeError('Ungültige Versionskennung')


def current_release(root):
    pointer=json.loads((root/'current.json').read_text(encoding='utf-8'))
    release=(root/pointer['directory']).resolve()
    if not release.is_relative_to((root/'releases').resolve()):
        raise RuntimeError('Ungültiger Installationspfad')
    return release,pointer


def activate(root, source, revision, expected_version=None):
    version=release_version(source)
    if expected_version and version!=expected_version:
        raise RuntimeError('Release-Tag und Programmversion stimmen nicht überein')
    releases=root/'releases'
    releases.mkdir(parents=True,exist_ok=True)
    # Previous releases remain available; only the pointer changes atomically.
    destination=releases/('lab-v'+version+'-'+uuid.uuid4().hex)
    with tempfile.TemporaryDirectory(prefix='stage-',dir=root) as temporary:
        staging=Path(temporary)/'app'
        staging.mkdir()
        for name in release_files(source):
            (staging/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source/name,staging/name)
        release_version(staging)
        os.replace(staging,destination)
    atomic_json(root/'current.json',{'version':version,'revision':revision,'directory':str(destination.relative_to(root))})
    return version


def git_run(git, *arguments, timeout=20):
    # Never pass application config, profile, database, or reports to Git.
    result=subprocess.run([git,*map(str,arguments)],capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError('Git-Abruf fehlgeschlagen: '+result.stderr.strip()[:500])
    return result.stdout


def update(root):
    settings=json.loads((root/'installation.json').read_text(encoding='utf-8'))
    git=settings['git']
    refs=git_run(git,'ls-remote','--tags',REPOSITORY)
    candidates=[]
    for line in refs.splitlines():
        _sha,ref=line.split('\t',1)
        match=TAG.fullmatch(ref.removeprefix('refs/tags/'))
        if match:
            candidates.append((tuple(map(int,match.groups())),match.group(0)))
    if not candidates:
        raise RuntimeError('Keine veröffentlichte LAB-Version gefunden.')
    number,tag=max(candidates)
    _release,pointer=current_release(root)
    if number<=tuple(map(int,pointer['version'].split('.'))):
        return False
    cache=root/'repository.git'
    if not cache.exists():
        git_run(git,'init','--bare',cache)
    git_run(git,'--git-dir',cache,'fetch','--no-tags',REPOSITORY,f'refs/tags/{tag}:refs/tags/{tag}',timeout=90)
    revision=git_run(git,'--git-dir',cache,'rev-parse',tag+'^{commit}').strip()
    with tempfile.TemporaryDirectory(prefix='download-',dir=root) as temporary:
        temporary=Path(temporary)
        archive=temporary/'release.zip'
        git_run(git,'--git-dir',cache,'archive','--format=zip','--output',archive,tag,'gizmo_lab',timeout=30)
        source=temporary/'source'
        source.mkdir()
        with ZipFile(archive) as bundle:
            manifest=bundle.getinfo('gizmo_lab/deployment.py')
            if manifest.file_size>2_000_000:
                raise RuntimeError('Release-Datei unerwartet groß')
            (source/'deployment.py').write_bytes(bundle.read(manifest))
            for name in release_files(source):
                info=bundle.getinfo('gizmo_lab/'+name)
                if info.file_size>2_000_000:
                    raise RuntimeError('Release-Datei unerwartet groß')
                (source/name).parent.mkdir(parents=True,exist_ok=True)
                (source/name).write_bytes(bundle.read(info))
        version=activate(root,source,revision,expected_version=tag.removeprefix('lab-v'))
    refresh_launchers(root)
    print(f'[+] LAB {version} installiert. Persönliche Dateien bleiben unverändert.',flush=True)
    return True


def launch(root, arguments):
    release,_pointer=current_release(root)
    settings=json.loads((root/'installation.json').read_text(encoding='utf-8'))
    env=os.environ.copy()
    # A development shell must never redirect the production installation.
    env.pop('GIZMO_LAB_DATA',None)
    if settings.get('data_directory'):
        env['GIZMO_LAB_DATA']=settings['data_directory']
    # The child receives console interrupts and performs Studio-Safe shutdown.
    # Keep the waiting launcher alive; subprocess.call otherwise kills the child
    # when the launcher itself receives KeyboardInterrupt.
    signals=[signal.SIGINT]
    if os.name=='nt':
        signals.append(signal.SIGBREAK)
    previous={number:signal.signal(number,lambda *_:None) for number in signals}
    local_python=root.parent/'.venv'/'Scripts'/'python.exe'
    python=str(local_python) if os.name=='nt' and local_python.is_file() else settings['python']
    try:
        if '--terminal' in arguments:
            arguments=[value for value in arguments if value!='--terminal']
            return subprocess.call([python,str(release/'gizmo_lab.py'),*arguments],cwd=release,env=env)
        if os.name=='nt':
            return subprocess.call([python,str(release/'gizmo_lab.py'),'--gui',*arguments],cwd=release,env=env,
                                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        return subprocess.call([python,str(release/'gizmo_lab.py'),'--gui',*arguments],cwd=release,env=env)
    finally:
        for number,handler in previous.items():
            signal.signal(number,handler)


BOOTSTRAP = '''import json, pathlib, runpy, sys
root=pathlib.Path(__file__).resolve().parent
pointer=json.loads((root/'current.json').read_text(encoding='utf-8'))
release=(root/pointer['directory']).resolve()
if not release.is_relative_to((root/'releases').resolve()):
    raise SystemExit('Ungültiger Installationspfad')
sys.argv=[str(release/'deployment.py'),sys.argv[1] if len(sys.argv)>1 else 'start','--root',str(root),*sys.argv[2:]]
runpy.run_path(str(release/'deployment.py'),run_name='__main__')
'''


def refresh_launchers(root):
    """Keep the public starters stable across versioned code updates."""
    settings=json.loads((root/'installation.json').read_text(encoding='utf-8'))
    python=settings['python']
    local=root.parent/'.venv'/'Scripts'/'python.exe'
    if os.name=='nt' and local.is_file():
        python=str(local)
    pythonw=str(Path(python).with_name('pythonw.exe'))
    launcher=str(root/'launcher.py')
    files={
        'GIZMO.cmd':f'@echo off\r\nstart "" "{pythonw}" "{launcher}" start %*\r\n',
        'GIZMO-Terminal.cmd':f'@echo off\r\n"{python}" "{launcher}" start --terminal %*\r\nif errorlevel 1 pause\r\n',
        'GIZMO-Update.cmd':f'@echo off\r\n"{python}" "{launcher}" update %*\r\nif errorlevel 1 pause\r\n',
    }
    for name,content in files.items():
        (root.parent/name).write_text(content,encoding='utf-8')


def install(root, source, git, data_directory=None, revision=None):
    if (root/'installation.json').exists():
        raise RuntimeError('Installation existiert bereits; bitte den Update-Starter verwenden.')
    git=str(Path(git).resolve())
    git_run(git,'--version')
    version=activate(root,source,revision or 'local-tested-'+release_version(source))
    python=str(Path(getattr(sys,'_base_executable',sys.executable)).resolve())
    atomic_json(root/'installation.json',{'git':git,'python':python,'data_directory':str(Path(data_directory).resolve()) if data_directory else None})
    (root/'launcher.py').write_text(BOOTSTRAP,encoding='utf-8')
    refresh_launchers(root)
    print(f'[+] LAB {version} installiert. Start: {root.parent / "GIZMO.cmd"}',flush=True)


def main():
    diagnostic=os.environ.get('GIZMO_GUI_LOG',os.devnull)
    if sys.stdout is None: sys.stdout=open(diagnostic,'a',encoding='utf-8')
    if sys.stderr is None: sys.stderr=open(diagnostic,'a',encoding='utf-8')
    parser=argparse.ArgumentParser(description='GIZMO LAB – lokale Installation und sichere Code-Updates')
    parser.add_argument('action',choices=('install','start','update'))
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--git',default=shutil.which('git'))
    parser.add_argument('--revision',help='Geprüfter Git-Commit der Erstinstallation')
    parser.add_argument('--data-directory',type=Path,help='Bestehender privater Datenort; wird bei Installation nicht geöffnet')
    parser.add_argument('--offline',action='store_true',help='Ohne Updateprüfung starten')
    args,lab_arguments=parser.parse_known_args()
    root=args.root.resolve()
    try:
        with installation_lock(root):
            if args.action=='install':
                if not args.git:
                    raise RuntimeError('Git fehlt; --git PFAD angeben')
                install(root,args.source.resolve(),args.git,args.data_directory,args.revision)
                return 0
            if lab_arguments and args.action!='start':
                raise RuntimeError('Unbekannte Update-Argumente')
            if not args.offline:
                try:
                    print('[.] Prüfe veröffentlichte LAB-Updates...',flush=True)
                    changed=update(root)
                    if args.action=='update' and not changed:
                        print('[+] Installierte LAB-Version ist aktuell.',flush=True)
                except (OSError,RuntimeError,ValueError,KeyError,SyntaxError,BadZipFile,subprocess.SubprocessError) as error:
                    if args.action=='update':
                        raise
                    print(f'[i] Update nicht verfügbar; starte installierte Version. {error}',flush=True)
            if args.action=='start':
                return launch(root,lab_arguments)
            return 0
    except (OSError,RuntimeError,ValueError,KeyError,SyntaxError,BadZipFile,subprocess.SubprocessError) as error:
        print(f'[!] {error}',file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
