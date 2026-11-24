import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
import gizmo_bridge


class StudioSafeTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.bridge = gizmo_bridge.Bridge(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_preload_and_stream_keep_model_resident(self):
        requests = []

        def urlopen(request, timeout):
            requests.append((request, timeout))
            if request.full_url.endswith("/api/generate"):
                return io.BytesIO(b'{"done":true}')
            return io.BytesIO(b'{"message":{"content":"Hallo "},"done":false}\n'
                              b'{"message":{"content":"Welt"},"done":false}\n'
                              b'{"done":true,"eval_count":2}\n')

        with patch.object(gizmo_bridge.urllib.request, "urlopen", side_effect=urlopen):
            self.bridge.preload_model()
            self.assertEqual(list(self.bridge._chat("Frage?")), ["Hallo ", "Welt"])
        preload = json.loads(requests[0][0].data)
        chat = json.loads(requests[1][0].data)
        self.assertEqual(preload["keep_alive"], -1)
        self.assertEqual(chat["keep_alive"], -1)
        self.assertTrue(chat["stream"])
        self.assertFalse(chat["think"])
        self.assertEqual(chat["model"], gizmo_bridge.DEFAULTS["model"])

    def test_windows_shutdown_includes_previously_started_processes(self):
        seen = []

        def run(command, **_kwargs):
            seen.append(command)
            if command[0] == "tasklist":
                output = '"ollama.exe","1234"\n' if sum(c[0] == "tasklist" for c in seen) == 1 else ""
                return Mock(stdout=output)
            return Mock(returncode=0)

        with patch.object(gizmo_bridge.sys, "platform", "win32"), \
             patch.object(gizmo_bridge.subprocess, "run", side_effect=run):
            self.bridge.stop()
        self.assertIn(["taskkill", "/F", "/T", "/IM", "ollama app.exe"], seen)
        self.assertIn(["taskkill", "/F", "/T", "/IM", "ollama.exe"], seen)
        self.assertIn(["taskkill", "/F", "/T", "/PID", "1234"], seen)
