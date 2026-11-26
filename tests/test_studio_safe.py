"""No independent bridge process, profile, or legacy JSON memory remains."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


class StudioSafeAdapterTest(unittest.TestCase):
    def test_legacy_bridge_cannot_start_a_second_model(self):
        result=subprocess.run([sys.executable,str(ROOT/'bridge'/'gizmo_bridge.py')],capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('GIZMO.cmd',result.stderr)

    def test_old_starter_delegates_to_productive_launcher(self):
        source=(ROOT/'bridge'/'start-gizmo.bat').read_text(encoding='utf-8')
        self.assertIn('GIZMO.cmd',source)
        self.assertNotIn('gizmo_bridge.py',source)


if __name__=='__main__':unittest.main()
