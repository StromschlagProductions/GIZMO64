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
                    self.assertIn('COMMIT '+gizmo_lab.running_revision(),window.service_info.text())
                    self.assertFalse(any('REV 0.1' in label.text() for label in window.findChildren(QLabel)))
                    window.close()
                    return 0

                with patch.object(QApplication,'exec',inspect):
                    self.assertEqual(gizmo_lab.run_gui(),0)
        finally:
            if previous is None:os.environ.pop('QT_QPA_PLATFORM',None)
            else:os.environ['QT_QPA_PLATFORM']=previous
