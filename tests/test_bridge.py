"""The legacy entrypoint delegates transport to the one LAB engine."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
sys.path.insert(0,str(ROOT/'gizmo_lab'))
import gizmo_bridge
Uplink=gizmo_bridge.Uplink
c64_records=gizmo_bridge.c64_records
UPLINK_PARA=gizmo_bridge.UPLINK_PARA


class BridgeAdapterTest(unittest.TestCase):
    def test_legacy_import_is_same_uplink_class(self):
        self.assertIs(gizmo_bridge.Uplink,Uplink)

    def test_display_conversion_preserves_long_answer_and_paragraphs(self):
        records=c64_records('Test? Satz!\n\n'+'Wort '*800)
        self.assertIn(UPLINK_PARA,records)
        self.assertGreaterEqual(len(records),100)
        self.assertEqual(sum(line.count('Wort') for line in records),800)
        self.assertTrue(all(len(line)<=31 and line.isascii() for line in records if line!=UPLINK_PARA))

    def test_display_conversion_does_not_send_thinking_or_markdown(self):
        text='**Ärger?** <think>hidden</think> [source](https://invalid.example)'
        output=' '.join(c64_records(text))
        self.assertIn('Aerger?',output)
        self.assertNotIn('hidden',output)
        self.assertNotIn('https://',output)
        self.assertIn('craft - there',' '.join(c64_records('craft—there')))


if __name__=='__main__':unittest.main()
