"""Lokale TCP-Brücke zwischen Ultimate-Modem und Ollama."""
import csv
import io
import json
import re
import socket
import subprocess
import sys
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
    text = re.sub(r"<think\b[^>]*>.*?</think\s*>", "", text, flags=re.I | re.S)
    text = re.sub(r"<think\b[^>]*>.*\Z", "", text, flags=re.I | re.S)
    text = re.sub(r"</think\s*>", "", text, flags=re.I)
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
        self.stop_lock = threading.Lock()
        self.ollama_lock = threading.Lock()
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
        with self.ollama_lock:
            if self.stop_event.is_set():
                raise RuntimeError("Bruecke wird beendet")
            if self._ollama_ready():
                print("[+] Ollama bereit", flush=True)
                return
            print("[+] Starte Ollama...", flush=True)
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0
            self.ollama = subprocess.Popen(["ollama", "serve"], creationflags=flags,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(80):
                if self.stop_event.wait(0.25):
                    raise RuntimeError("Ollama-Start abgebrochen")
                if self._ollama_ready():
                    print("[+] Ollama bereit", flush=True)
                    return
            raise RuntimeError("Ollama wurde nicht bereit")

    def _stop_ollama(self):
        if sys.platform == "win32":
            # Zuerst Eltern samt Prozessbaum beenden, dann verbliebene Ollama-Prozesse.
            try:
                for image in ("ollama app.exe", "ollama.exe", "ollama_llama_server.exe"):
                    subprocess.run(["taskkill", "/F", "/T", "/IM", image],
                                   capture_output=True, check=False, timeout=10)
                for _ in range(3):
                    listing = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                                             capture_output=True, text=True, check=True, timeout=10)
                    processes = [row for row in csv.reader(io.StringIO(listing.stdout))
                                 if len(row) > 1 and "ollama" in row[0].lower()]
                    if not processes:
                        break
                    for process in processes:
                        subprocess.run(["taskkill", "/F", "/T", "/PID", process[1]],
                                       capture_output=True, check=False, timeout=10)
                else:
                    print("[!] Ollama-Prozesse noch sichtbar", flush=True)
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                print(f"[!] Ollama-Prozesspruefung fehlgeschlagen: {error}", flush=True)
        if self.ollama:
            if self.ollama.poll() is None:
                self.ollama.terminate()
                try:
                    self.ollama.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.ollama.kill()
                    self.ollama.wait()
            self.ollama = None
        print("[+] Ollama-Prozesse geprueft", flush=True)

    def stop(self):
        with self.stop_lock:
            if self.stop_event.is_set():
                return
            print("[.] Fahre GIZMO-Bruecke herunter...", flush=True)
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
            self._stop_ollama()
            print("[+] Bruecke beendet", flush=True)

    def _chat(self, prompt):
        if self.stop_event.is_set():
            raise RuntimeError("Bruecke wird beendet")
        messages = [{"role": "system", "content": self.config["personality"] + " /no_think"}]
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
            lines = ascii_screen(answer)
            self._send(client, BEGIN)
            for line in lines:
                self._send(client, line)
            self._send(client, END)
            for line in lines:
                print(f"GIZMO > {line}", flush=True)
        except (OSError, urllib.error.URLError, RuntimeError, KeyError, ValueError) as error:
            if not self.stop_event.is_set():
                self._send(client, BEGIN)
                self._send(client, "OLLAMA NICHT ERREICHBAR.")
                self._send(client, END)
                print("GIZMO > OLLAMA NICHT ERREICHBAR.", flush=True)
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
                            print(f"C64 > {command}", flush=True)
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
        print("[.] GIZMO-64 // PC-UPLINK", flush=True)
        try:
            self.start_ollama()
            self.server = socket.socket()
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.config["host"], self.config["port"]))
            self.server.listen()
            self.server.settimeout(0.5)
            print(f"[+] TCP-Port {self.config['port']} bereit", flush=True)
            print("[i] ESC, Q, ENTER oder STRG+C beendet Bruecke und Ollama", flush=True)
            if sys.platform == "win32":
                threading.Thread(target=self._watch_keys, daemon=True).start()
            while not self.stop_event.is_set():
                try:
                    client, address = self.server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.stop_event.is_set():
                        break
                    raise
                print(f"[+] C64 verbunden von {address[0]}:{address[1]}", flush=True)
                threading.Thread(target=self.handle, args=(client,), daemon=True).start()
        finally:
            self.stop()

    def _watch_keys(self):
        import msvcrt

        while not self.stop_event.is_set():
            key = msvcrt.getwch()
            if key in ("\x1b", "q", "Q", "\r", "\n", "\x03"):
                self.stop()
                return


if __name__ == "__main__":
    path = ROOT / "config.local.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    bridge = Bridge(config=config)
    try:
        bridge.serve()
    except KeyboardInterrupt:
        bridge.stop()
    except (OSError, RuntimeError) as error:
        print(f"[!] Start fehlgeschlagen: {error}", flush=True)
        raise SystemExit(1)
