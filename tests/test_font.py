import unittest
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("build_font", ROOT / "assets" / "build_font.py")
module = module_from_spec(spec)
spec.loader.exec_module(module)


class FontTest(unittest.TestCase):
    def test_binary_and_glyphs(self):
        font = (ROOT / "assets" / "gizmo-font.bin").read_bytes()
        self.assertEqual(font, module.build())
        self.assertEqual(len(font), 2048)
        for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789?!,.:;\"'()-=/":
            code = ord(char) - 64 if char.isalpha() else ord(char)
            self.assertTrue(any(font[code * 8:code * 8 + 8]), char)
        self.assertNotEqual(font[ord("0") * 8:ord("0") * 8 + 8],
                            font[(ord("O") - 64) * 8:(ord("O") - 64) * 8 + 8])
        self.assertEqual(font[95 * 8 + 3], 255)
        for code in range(128):
            self.assertEqual(bytes(b ^ 255 for b in font[code * 8:code * 8 + 8]),
                             font[(code + 128) * 8:(code + 128) * 8 + 8])
