"""Lokale TCP-Brücke zwischen Ultimate-Modem und Ollama."""
import json
import re
import socket
import subprocess
import threading
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULTS = {
    "host": "0.0.0.0",
    "port": 6464,
    "model": "richardyoung/qwen3-14b-abliterated:latest",
    "ollama_url": "http://localhost:11434/api/chat",
    "personality": (
        "Du bist GIZMO, ein loyaler, neugieriger Bordcomputer der 1980er. "
        "Antworte persoenlich, kreativ und gelegentlich trocken-humorvoll. "
        "Maximal sechs kurze Zeilen, keine Denkprozesse oder Markdown."
    ),
}
BEGIN = "[[GIZMO:BEGIN]]"
END = "[[GIZMO:END]]"


def ascii_screen(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.I | re.S)
    text = re.sub(r"<think>.*", "", text, flags=re.I | re.S)
    text = text.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    words = text.split()
    lines, current = [], ""
    for word in words:
        for part in (word[i:i + 31] for i in range(0, len(word), 31)):
            if len(current) + len(part) + bool(current) > 31:
                lines.append(current)
                current = ""
            current = (current + " " + part).strip()
            if len(lines) == 5:
                break
        if len(lines) == 5:
            break
    if current and len(lines) < 6:
        lines.append(current)
    return lines or ["SIGNAL EMPFANGEN. KEIN TEXT."]


class Bridge:
    def __init__(self, folder=ROOT, config=None):
        self.folder = Path(folder)
        self.config = dict(DEFAULTS)
        if config:
            self.config.update(config)
        self.memory_path = self.folder / "memory.json"
        self.facts = self._load_facts()
        self.context = []
        self.stop_event = threading.Event()
        self.server = None
        self.clients = set()
        self.lock = threading.Lock()
        self.ollama = None

    def _load_facts(self):
        try:
            data = json.loads(self.memory_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except FileNotFoundError:
            return []

    def _save_facts(self):
        temporary = self.memory_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.facts, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.memory_path)

    def _ollama_ready(self):
        try:
            with urllib.request.urlopen(self.config["ollama_url"].replace("/api/chat", "/api/tags"), timeout=2):
                return True
        except (OSError, urllib.error.URLError):
            return False

    def start_ollama(self):
        if self._ollama_ready():
            return
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0
        self.ollama = subprocess.Popen(["ollama", "serve"], creationflags=flags,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if self.stop_event.wait(0.25):
                return
            if self._ollama_ready():
                return
        raise RuntimeError("Ollama wurde nicht bereit")

    def stop(self):
        self.stop_event.set()
        if self.server:
            self.server.close()
            self.server = None
        with self.lock:
            clients = list(self.clients)
        for client in clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
        if self.ollama:
            self.ollama.terminate()
            try:
                self.ollama.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ollama.kill()
                self.ollama.wait()
            self.ollama = None

    def _chat(self, prompt):
        self.start_ollama()
        messages = [{"role": "system", "content": self.config["personality"]}]
        if self.facts:
            messages.append({"role": "system", "content": "Gemerkte Fakten: " + "; ".join(self.facts[-20:])})
        messages.extend(self.context[-20:])
        messages.append({"role": "user", "content": prompt})
        payload = json.dumps({"model": self.config["model"], "messages": messages,
                              "stream": False, "think": False}).encode("utf-8")
        request = urllib.request.Request(self.config["ollama_url"], data=payload,
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            answer = json.load(response)["message"]["content"]
        self.context.extend([{"role": "user", "content": prompt},
                             {"role": "assistant", "content": answer}])
        self.context = self.context[-20:]
        return answer

    def _send(self, client, text):
        client.sendall((text + "\r\n").encode("ascii"))

    def _answer(self, client, prompt):
        try:
            upper = prompt.upper()
            if upper.startswith("MERKE:"):
                fact = prompt[6:].strip()
                if fact:
                    self.facts.append(fact)
                    self._save_facts()
                    answer = "GEMERKT. BORDSPEICHER AKTUALISIERT."
                else:
                    answer = "WAS SOLL ICH MIR MERKEN?"
            elif upper == "ERINNERE":
                answer = " | ".join(self.facts[-5:]) if self.facts else "NOCH KEINE FAKTEN GESPEICHERT."
            else:
                answer = self._chat(prompt)
            self._send(client, BEGIN)
            for line in ascii_screen(answer):
                self._send(client, line)
            self._send(client, END)
        except (OSError, urllib.error.URLError, RuntimeError, KeyError, ValueError) as error:
            if not self.stop_event.is_set():
                self._send(client, BEGIN)
                self._send(client, "OLLAMA NICHT ERREICHBAR.")
                self._send(client, END)
                print(f"Anfrage fehlgeschlagen: {error}")

    def handle(self, client):
        with self.lock:
            self.clients.add(client)
        try:
            self._send(client, "UPLINK HERGESTELLT. GIZMO ONLINE.")
            buffer = bytearray()
            while not self.stop_event.is_set():
                data = client.recv(512)
                if not data:
                    break
                for byte in data:
                    if byte in (10, 13):
                        if not buffer:
                            continue
                        command = buffer.decode("ascii", "replace").strip()
                        buffer.clear()
                        if command.upper() == "PING":
                            self._send(client, "PONG // GIZMO UPLINK AKTIV")
                        elif command.upper() == "STATUS":
                            self._send(client, f"FACTS: {len(self.facts)}")
                        else:
                            self._answer(client, command)
                    elif len(buffer) < 256:
                        buffer.append(byte)
                    else:
                        buffer.clear()
                        self._send(client, "EINGABE ZU LANG")
        except OSError:
            pass
        finally:
            with self.lock:
                self.clients.discard(client)
            client.close()

    def serve(self):
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.config["host"], self.config["port"]))
        self.server.listen()
        self.server.settimeout(0.5)
        print(f"GIZMO-Bruecke auf Port {self.config['port']} bereit")
        try:
            while not self.stop_event.is_set():
                try:
                    client, address = self.server.accept()
                except socket.timeout:
                    continue
                print(f"C64 verbunden von {address[0]}:{address[1]}")
                threading.Thread(target=self.handle, args=(client,), daemon=True).start()
        finally:
            self.stop()


if __name__ == "__main__":
    path = ROOT / "config.local.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    bridge = Bridge(config=config)
    try:
        bridge.serve()
    except KeyboardInterrupt:
        bridge.stop()
