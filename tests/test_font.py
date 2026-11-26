import unittest
import hashlib
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
        self.assertEqual(hashlib.sha256(font[:1024]).hexdigest(),
                         'c7109638231ac7eef443a7f553d7ebf40aa00fc1afe3518a81239ea8eb2143bc')
        tiles, header = module.header_art()
        self.assertEqual(len(header), 120)
        self.assertLessEqual(len(tiles), 128)
        self.assertTrue(all(header[row * 40 + column] == 32
                            for row in range(3) for column in range(30, 36)))
        self.assertTrue(all(code == 32 or code >= 128 for code in header))
        self.assertGreater(sum(code >= 128 for code in header), 40)
        for code, tile in enumerate(tiles, 128):
            self.assertEqual(font[code * 8:code * 8 + 8], tile)
        for code in range(len(tiles), 128):
            self.assertEqual(bytes(b ^ 255 for b in font[code * 8:code * 8 + 8]),
                             font[(code + 128) * 8:(code + 128) * 8 + 8])
