import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import subprocess
import sys
from unittest.mock import patch

import deployment as deploy
from version import VERSION

SOURCE=Path(__file__).resolve().parent
GIT=shutil.which('git') or str(SOURCE.parent/'.local-tools/git/cmd/git.exe')


class DeploymentTest(unittest.TestCase):
    def test_runtime_imports_with_the_fixed_v031_update_manifest(self):
        legacy_files=('gizmo_lab.py','memory.py','analysis.py','version.py','deployment.py',
            'config.example.json','personality.example.txt','questions.json','variants.example.json',
            'README.md','LOCAL-DEVELOPMENT.md','MEMORY.md','ARCHITEKTUR-0.3.md')
        with tempfile.TemporaryDirectory() as temporary:
            staging=Path(temporary)
            for name in legacy_files:
                shutil.copyfile(SOURCE/name,staging/name)
            code='import sys;sys.path.insert(0,sys.argv[1]);import gizmo_lab,memory,analysis;assert gizmo_lab.VERSION==sys.argv[2]'
            subprocess.run([sys.executable,'-c',code,str(staging),VERSION],check=True,capture_output=True,timeout=15)

    def source(self,base,version='0.3.1'):
        source=base/'source'
        source.mkdir()
        for name in deploy.FILES:
            (source/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(SOURCE/name,source/name)
        (source/'version.py').write_text(f"VERSION = '{version}'\n",encoding='utf-8')
        return source

    def test_install_and_activation_never_copy_private_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            source=self.source(base)
            (source/'config.json').write_text('synthetic private config')
            (source/'personality.txt').write_text('synthetic private profile')
            root=base/'production'
            data=base/'synthetic-private'
            data.mkdir()
            sentinels={'config.json':b'custom-config','personality.txt':b'custom-profile',
                       'GIZMO_Awakening_V2_EN.txt':b'synthetic-english-profile','memory.sqlite3':b'private-sentinel'}
            for name,value in sentinels.items():
                (data/name).write_bytes(value)
            with patch.object(deploy,'git_run',return_value='git version test'):
                deploy.install(root,source,GIT,data)
            release,pointer=deploy.current_release(root)
            self.assertEqual(pointer['version'],'0.3.1')
            self.assertFalse((release/'config.json').exists())
            self.assertFalse((release/'personality.txt').exists())
            self.assertEqual({name:(data/name).read_bytes() for name in sentinels},sentinels)
            with patch.object(deploy.os,'environ',dict(os.environ,GIZMO_LAB_DATA='synthetic-development-data')),patch.object(deploy.subprocess,'call',return_value=0) as call:
                self.assertEqual(deploy.launch(root,[]),0)
                self.assertEqual(call.call_args.kwargs['env']['GIZMO_LAB_DATA'],str(data.resolve()))
            settings=json.loads((root/'installation.json').read_text())
            self.assertIn('pythonw.exe',(base/'GIZMO.cmd').read_text(encoding='utf-8'))
            self.assertIn('--terminal',(base/'GIZMO-Terminal.cmd').read_text(encoding='utf-8'))
            with patch.object(deploy.subprocess,'call',return_value=0) as call:
                deploy.launch(root,['--terminal'])
                self.assertNotIn('--gui',call.call_args.args[0])
            settings['data_directory']=None
            deploy.atomic_json(root/'installation.json',settings)
            with patch.object(deploy.os,'environ',dict(os.environ,GIZMO_LAB_DATA='synthetic-development-data')),patch.object(deploy.subprocess,'call',return_value=0) as call:
                deploy.launch(root,[])
                self.assertNotIn('GIZMO_LAB_DATA',call.call_args.kwargs['env'])

    def test_rejected_release_keeps_previous_pointer(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            source=self.source(base)
            root=base/'production'
            root.mkdir()
            deploy.activate(root,source,'first')
            before=(root/'current.json').read_bytes()
            with self.assertRaisesRegex(RuntimeError,'stimmen nicht'):
                deploy.activate(root,source,'wrong-tag',expected_version='0.4.0')
            (source/'analysis.py').write_text('invalid syntax here !')
            with self.assertRaises(SyntaxError):
                deploy.activate(root,source,'broken')
            self.assertEqual((root/'current.json').read_bytes(),before)

    def test_second_process_is_locked_out(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with deploy.installation_lock(root):
                with self.assertRaises(RuntimeError):
                    with deploy.installation_lock(root):
                        self.fail('lock did not block second launcher')

    def test_offline_start_uses_installed_release(self):
        with tempfile.TemporaryDirectory() as temporary:
            for error in (RuntimeError('offline'),SyntaxError('synthetic broken update')):
                with self.subTest(error=type(error).__name__),\
                     patch('sys.argv',['deployment.py','start','--root',temporary]),\
                     patch.object(deploy,'update',side_effect=error),\
                     patch.object(deploy,'launch',return_value=0) as launch:
                    self.assertEqual(deploy.main(),0)
                    launch.assert_called_once()

    @unittest.skipUnless(Path(GIT).is_file() or shutil.which(GIT),'Git unavailable')
    def test_update_fetches_only_stable_lab_tags_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary)
            source=self.source(base,'0.3.0')
            root=base/'production'
            with patch.object(deploy,'git_run',return_value='git version test'):
                deploy.install(root,source,GIT)
            repository=base/'repository'
            repository.mkdir()
            deploy.git_run(GIT,'init',repository)
            deploy.git_run(GIT,'-C',repository,'config','user.name','Synthetic QA')
            deploy.git_run(GIT,'-C',repository,'config','user.email','qa@example.invalid')
            shutil.copytree(SOURCE,repository/'gizmo_lab',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            deploy.git_run(GIT,'-C',repository,'add','gizmo_lab')
            deploy.git_run(GIT,'-C',repository,'commit','-m','Synthetic release fixture')
            deploy.git_run(GIT,'-C',repository,'tag','lab-v'+VERSION)
            deploy.git_run(GIT,'-C',repository,'tag','lab-v99.0.0-beta')
            with patch.object(deploy,'REPOSITORY',str(repository)):
                self.assertTrue(deploy.update(root))
                self.assertFalse(deploy.update(root))
            release,pointer=deploy.current_release(root)
            self.assertEqual(pointer['version'],VERSION)
            self.assertEqual(len(list((root/'releases').iterdir())),2)
            self.assertEqual({p.relative_to(release).as_posix() for p in release.rglob('*') if p.is_file()},set(deploy.FILES))
