"""Synthetic production-launcher regression for settings, update and GUI shutdown."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

import deployment

SOURCE=Path(__file__).resolve().parent
LOCAL_GIT=SOURCE.parent/'.local-tools/git/cmd/git.exe'
GIT=str(LOCAL_GIT) if LOCAL_GIT.is_file() else shutil.which('git')


def run_gui(root,report,phase):
    env=dict(os.environ,GIZMO_CONFIG_QA_PHASE=phase,GIZMO_GUI_LOG=str(report.with_suffix('.log')))
    env.pop('GIZMO_LAB_DATA',None)
    result=subprocess.run([sys.executable,str(root/'launcher.py'),'start','--offline',
                           '--gui-config-qa-report',str(report)],env=env,
                          capture_output=True,text=True,timeout=45)
    assert result.returncode==0,(phase,result.returncode,result.stdout,result.stderr,
        report.read_text(encoding='utf-8') if report.exists() else 'no report',
        report.with_suffix('.log').read_text(encoding='utf-8') if report.with_suffix('.log').exists() else 'no log')
    evidence=json.loads(report.read_text(encoding='utf-8'))
    assert evidence['error'] is None and all(evidence['checks'].values()),evidence
    return evidence


def main():
    with tempfile.TemporaryDirectory(prefix='gizmo-stability-',dir=SOURCE.parent/'.local-test') as temporary:
        base=Path(temporary)
        data=base/'synthetic-data';data.mkdir()
        config=json.loads((SOURCE/'config.example.json').read_text(encoding='utf-8'))
        config.update(model='synthetic-model',synthetic_extra='keep-me')
        deployment.atomic_json(data/'config.json',config)
        (data/'GIZMO_Awakening_V2_EN.txt').write_bytes(b'Synthetic QA profile')
        (data/'memory.sqlite3').write_bytes(b'synthetic-memory-sentinel')
        root=base/'installation'
        deployment.install(root,SOURCE,GIT,data)
        settings=json.loads((root/'installation.json').read_text(encoding='utf-8'))
        settings['python']=sys.executable
        deployment.atomic_json(root/'installation.json',settings)
        deployment.refresh_launchers(root)
        launcher=base/'GIZMO.cmd'
        assert 'pythonw.exe' in launcher.read_text(encoding='utf-8').lower()
        first=run_gui(root,base/'first.json','save')
        saved=(data/'config.json').read_bytes()
        profile=(data/'GIZMO_Awakening_V2_EN.txt').read_bytes()
        memory=(data/'memory.sqlite3').read_bytes()

        repository=base/'synthetic-repository';repository.mkdir()
        deployment.git_run(GIT,'init',repository)
        deployment.git_run(GIT,'-C',repository,'config','user.name','Synthetic QA')
        deployment.git_run(GIT,'-C',repository,'config','user.email','qa@example.invalid')
        release=repository/'gizmo_lab';release.mkdir()
        for name in deployment.FILES:shutil.copyfile(SOURCE/name,release/name)
        version_file=release/'version.py'
        version_file.write_text(re.sub(r"(?m)^VERSION\s*=\s*['\"][^'\"]+['\"]",
            "VERSION = '0.7.99'",version_file.read_text(encoding='utf-8')),encoding='utf-8')
        deployment.git_run(GIT,'-C',repository,'add','gizmo_lab')
        deployment.git_run(GIT,'-C',repository,'commit','-m','Synthetic update')
        deployment.git_run(GIT,'-C',repository,'tag','lab-v0.7.99')
        with patch.object(deployment,'REPOSITORY',str(repository)):
            assert deployment.update(root)
        assert deployment.current_release(root)[1]['version']=='0.7.99'
        assert (data/'config.json').read_bytes()==saved
        assert (data/'GIZMO_Awakening_V2_EN.txt').read_bytes()==profile
        assert (data/'memory.sqlite3').read_bytes()==memory
        second=run_gui(root,base/'second.json','reload')
        assert (data/'config.json').read_bytes()==saved
        assert (data/'GIZMO_Awakening_V2_EN.txt').read_bytes()==profile
        assert (data/'memory.sqlite3').read_bytes()==memory
        print(json.dumps({'passed':True,'first':first['checks'],'after_update':second['checks']},indent=2))


if __name__=='__main__':main()
