import socket
import select
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from gizmo_bridge import BEGIN, END, Bridge, ThinkFilter, ascii_screen


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.bridge = Bridge(self.folder.name)
        self.bridge._chat = lambda prompt: iter(["<thi", "nk>geheim</think>Ärger? ", prompt * 20])
        self.client, server = socket.socketpair()
        self.client.settimeout(2)
        self.thread = threading.Thread(target=self.bridge.handle, args=(server,), daemon=True)
        self.thread.start()
        self.stream = self.client.makefile("rb")
        self.assertEqual(self.stream.readline().strip(), b"UPLINK HERGESTELLT. GIZMO ONLINE.")

    def tearDown(self):
        self.bridge.stop()
        self.stream.close()
        self.client.close()
        self.thread.join(timeout=2)
        self.folder.cleanup()

    def read_reply(self):
        line = self.stream.readline().strip()
        self.client.sendall(b"ACK\r")
        return line

    def test_fragmented_ping_and_framed_reply(self):
        self.client.sendall(b"PI")
        self.client.sendall(b"NG\r")
        self.assertEqual(self.stream.readline().strip(), b"PONG // GIZMO UPLINK AKTIV")
        self.client.sendall(b"HALLO GIZMO\r\n")
        self.assertEqual(self.read_reply(), BEGIN.encode())
        lines = []
        while True:
            line = self.read_reply()
            if line == END.encode():
                break
            lines.append(line)
        self.assertTrue(lines)
        self.assertGreater(len(lines), 6)
        self.assertTrue(all(len(line) <= 31 and line.isascii() for line in lines))
        self.assertNotIn(b"geheim", b" ".join(lines))
        self.assertIn(b"Aerger", b" ".join(lines))

    def test_memory_and_status(self):
        self.client.sendall(b"MERKE: Der Kompass zeigt Norden\r")
        self.assertEqual(self.read_reply(), BEGIN.encode())
        self.assertIn(b"GEMERKT", self.read_reply())
        while self.read_reply() != END.encode():
            pass
        self.client.sendall(b"STATUS\r")
        self.assertEqual(self.stream.readline().strip(), b"FACTS: 1")
        self.assertEqual(Bridge(self.folder.name).facts, ["Der Kompass zeigt Norden"])

    def test_long_answer_and_stop(self):
        lines = ascii_screen("Wort " * 300)
        self.assertGreater(len(lines), 6)
        self.assertTrue(all(len(line) <= 31 for line in lines))
        self.bridge.stop()
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def test_fragmented_think_tags_and_empty_tail(self):
        thought = ThinkFilter()
        self.assertEqual(thought.feed("Hallo <thi"), "Hallo ")
        self.assertEqual(thought.feed("nk>privat</thi"), "")
        self.assertEqual(thought.feed("nk>Welt"), "Welt")
        self.assertEqual(thought.finish(), "")
        thought = ThinkFilter()
        self.assertEqual(thought.feed("Antwort <think>geheim"), "Antwort ")
        self.assertEqual(thought.finish(), "")

    def test_stream_failure_has_single_frame(self):
        def broken(_prompt):
            yield "Erster vollstaendiger Satz. Noch ein "
            raise RuntimeError("Verbindung abgebrochen")
        self.bridge._chat = broken
        self.client.sendall(b"FRAGE\r")
        lines = []
        while True:
            line = self.read_reply()
            lines.append(line)
            if line == END.encode():
                break
        self.assertEqual(lines.count(BEGIN.encode()), 1)
        self.assertIn(b"ANTWORT UNTERBROCHEN", b" ".join(lines))

    def test_hundred_lines_and_paragraphs(self):
        self.bridge._chat = lambda _: iter(["Test? Satz!\n\n" + "Wort " * 800])
        self.client.sendall(b"LANG\r")
        lines = []
        while True:
            line = self.read_reply()
            if line == END.encode():
                break
            lines.append(line)
        self.assertEqual(lines[0], BEGIN.encode())
        self.assertIn(b"[[GIZMO:PARA]]", lines)
        self.assertGreaterEqual(len(lines), 100)
        self.assertEqual(sum(line.count(b"Wort") for line in lines), 800)

    def test_slow_receiver_controls_next_line(self):
        self.bridge._chat = lambda _: iter(["Erste Zeile. Zweite Zeile. Dritte Zeile."])
        self.client.sendall(b"FRAGE\r")
        self.assertEqual(self.stream.readline().strip(), BEGIN.encode())
        self.assertFalse(select.select([self.client], [], [], 0.05)[0])
        self.client.sendall(b"A")
        self.client.sendall(b"CK\r")
        first = self.stream.readline().strip()
        self.assertTrue(first)
        self.assertFalse(select.select([self.client], [], [], 0.05)[0])
        self.client.sendall(b"ACK\r")
        while self.read_reply() != END.encode():
            pass


if __name__ == "__main__":
    unittest.main()
