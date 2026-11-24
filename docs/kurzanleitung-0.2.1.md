# GIZMO-64 0.2.1 – Kurzanleitung

1. Auf dem Windows-PC Python 3 und Ollama installieren. Einmalig `ollama pull richardyoung/qwen2.5-7b-instruct-abliterated:latest` ausführen.
2. Alle Dateien dieses Pakets in denselben Ordner entpacken. `start-gizmo.bat` starten. Die Brücke startet Ollama bei Bedarf und lädt das Modell vor. Das Fenster meldet, wenn TCP-Port 6464 bereit ist.
3. In der Windows-Firewall TCP-Port 6464 für den C64 Ultimate freigeben. Im Ultimate die bestehende SwiftLink/ACIA-Modemkonfiguration auf `$DE00` verwenden.
4. `GIZMO64.PRG` auf dem Ultimate starten. Die voreingestellte PC-Adresse ist `192.168.178.244`. Bei anderer PC-Adresse `IP <adresse>` und danach `UPLINK` eingeben.
5. Nach `UPLINK VERIFIZIERT` freie Texte eingeben. `F1` wechselt die Farbe. `HELP`, `DIAG` und `HEX` zeigen weitere Befehle. `MERKE: <fakt>` speichert lokal, `ERINNERE` ruft Fakten ab.
6. Das PC-Fenster mit ESC, Q, ENTER oder Strg+C schließen. Die Brücke beendet dabei Ollama samt Modellprozessen. Sie installiert keinen Hintergrunddienst.

Für ein anderes Modell oder einen eigenen Persönlichkeitstext `config.example.json` als `config.local.json` kopieren und bearbeiten. `memory.json` und `config.local.json` bleiben lokal und dürfen nicht veröffentlicht werden. Das Antwortprotokoll nutzt `[[GIZMO:BEGIN]]` und `[[GIZMO:END]]`; die Brücke überträgt ASCII-Zeilen mit höchstens 31 Zeichen.

Die reale ACIA-Verbindung und das lokale Ollama-Modell können abschließend nur am Ultimate und am Windows-PC geprüft werden. Der VICE-Prüflauf nutzt keine Ultimate-ACIA und zeigt deshalb einen Offline-Zustand.
