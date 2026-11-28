"""Release identity displayed by the actual Control Center widgets."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gizmo_lab


class ControlCenterVersionTest(unittest.TestCase):
    def test_header_footer_and_service_identity(self):
        from PySide6.QtWidgets import QApplication, QLabel

        previous=os.environ.get('QT_QPA_PLATFORM')
        os.environ['QT_QPA_PLATFORM']='offscreen'
        try:
            with tempfile.TemporaryDirectory() as temporary, \
                 patch.object(gizmo_lab,'private_dir',return_value=Path(temporary)):
                def inspect(app):
                    window=next(w for w in app.topLevelWidgets() if w.windowTitle().startswith('GIZMO'))
                    self.assertEqual(window.header_version.text(),'STROMSCHLAG SYSTEMS // LAB '+gizmo_lab.Lab.version)
                    self.assertEqual(window.footer_version.text(),'GIZMO CONTROL CENTER // LAB '+gizmo_lab.Lab.version)
                    window.open_settings()
                    self.assertIn('MODEL '+gizmo_lab.DEFAULT_MODEL,window.service_info.text())
                    self.assertIn('LAB '+gizmo_lab.VERSION,window.service_info.text())
                    self.assertIn('PROFILE V4.1 fixed examples',window.service_info.text())
                    window.profile_mode.setCurrentIndex(window.profile_mode.findData('v4'))
                    window.save_settings()
                    self.assertEqual(gizmo_lab.load_config(Path(temporary))['personality_variant'],'v4')
                    window.profile_mode.setCurrentIndex(window.profile_mode.findData('v3_examples'))
                    window.save_settings()
                    self.assertEqual(gizmo_lab.load_config(Path(temporary))['personality_variant'],'v3_examples')
                    original=Path(temporary)/'GIZMO_Awakening_V2_EN.txt'
                    original.write_text('Synthetic original personality',encoding='utf-8')
                    before=original.read_bytes()
                    window.profile_mode.setCurrentIndex(window.profile_mode.findData('v2'))
                    window.save_settings()
                    self.assertEqual(gizmo_lab.load_config(Path(temporary))['personality_variant'],'v2')
                    self.assertIn('PROFILE V2 original',window.service_info.text())
                    window.profile_mode.setCurrentIndex(window.profile_mode.findData('v3'))
                    window.save_settings()
                    self.assertEqual(gizmo_lab.load_config(Path(temporary))['personality_variant'],'v3')
                    custom=Path(temporary)/'my-custom-profile.txt'
                    custom.write_text('Synthetic custom personality',encoding='utf-8')
                    window.selected_profile=str(custom)
                    window.profile_mode.setCurrentIndex(window.profile_mode.findData('custom'))
                    window.save_settings()
                    self.assertTrue(Path(gizmo_lab.load_config(Path(temporary))['personality_path']).samefile(custom))
                    self.assertEqual(custom.read_text(encoding='utf-8'),'Synthetic custom personality')
                    self.assertEqual(original.read_bytes(),before)
                    self.assertIn('COMMIT '+gizmo_lab.running_revision(),window.service_info.text())
                    self.assertFalse(any('REV 0.1' in label.text() for label in window.findChildren(QLabel)))
                    window.close()
                    return 0

                with patch.object(QApplication,'exec',inspect):
                    self.assertEqual(gizmo_lab.run_gui(),0)
        finally:
            if previous is None:os.environ.pop('QT_QPA_PLATFORM',None)
            else:os.environ['QT_QPA_PLATFORM']=previous
