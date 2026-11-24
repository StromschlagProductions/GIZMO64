# GIZMO-64

GIZMO-64 ist ein nativer C64-Ultimate-Client für eine vorhandene Python-TCP-Brücke zu Ollama. Version 0.1 bietet eine Terminaloberfläche, lokale Befehle und einen durch PING/PONG bestätigten PC-Uplink. Die Brücke selbst gehört nicht zu diesem Repository.

## Bauen

Benötigt werden cc65 mit `cl65` im `PATH`, `make` und für die Hosttests ein C-Compiler. Im Repository `make`, danach liegt `GIZMO64.PRG` im Hauptverzeichnis. `make test` führt die Protokoll- und Oberflächentests auf dem Build-Rechner aus. `make clean` entfernt erzeugte Dateien. Die GitHub Action baut bei Push und Pull Request und stellt das PRG als Artefakt bereit.

Unter Windows cc65 aus den offiziellen Releases installieren und dessen `bin`-Verzeichnis zum `PATH` hinzufügen. Mit MSYS2 oder MinGW `make` beziehungsweise `mingw32-make` ausführen. Eine Schrittfolge steht in [docs/windows-build.md](docs/windows-build.md).

## Bedienung

Das PRG mit `LOAD"GIZMO64.PRG",8,1` und `RUN` starten oder direkt über den Dateibrowser des Ultimate laden. Es wählt automatisch `192.168.178.244:6464`. Der Windows-PC muss die vorhandene Brücke auf Port 6464 gestartet haben. Ohne erreichbaren PC endet der Verbindungsversuch im Offline-Modus. Die Eingabe bleibt währenddessen bedienbar.

| Befehl | Wirkung |
| --- | --- |
| `HELP` | Befehle anzeigen |
| `STATUS` | Linkstatus und Zieladresse anzeigen |
| `UPLINK` | Verbindungsaufbau erneut starten |
| `PING` | Verbindung erneut prüfen |
| `OFFLINE` | Modem per DTR trennen |
| `CLS` | Terminalbereich löschen |
| `IP` | Zieladresse anzeigen |
| `IP 192.168.178.244` | Zieladresse ändern |
| `F1` | Farbe umschalten |

Die IP-Änderung gilt bis zum nächsten Programmstart. Die Oberfläche nutzt 40 × 25 Zeichen, feststehende Headerzeilen, ein animiertes Hardware-Sprite und ein kurzes SID-Tastenfeedback.

## Ultimate einrichten

In den Ultimate-Einstellungen die ACIA/SwiftLink-Emulation auf `$DE00` und den Modem-Modus aktivieren. DTR-Verbindungsabbruch und RTS-Handshake aktivieren. Die Einstellungen heißen je nach Firmware unterschiedlich. Der Client arbeitet mit 2400 Baud, 8 Datenbits, einem Stoppbit und Polling. Die PC-Brücke muss `PING` mit `PONG // GIZMO UPLINK AKTIV` beantworten und nach dem Verbindungsaufbau `UPLINK HERGESTELLT. GIZMO ONLINE.` senden. Der Client akzeptiert CONNECT und Begrüßung in beliebiger Reihenfolge. Details stehen in [docs/acia.md](docs/acia.md).

## Aktuelle Grenzen

Die Tests prüfen Protokoll und Bildschirmberechnungen auf dem Build-Rechner. Ein Lauf auf echter Ultimate-Hardware und ein Screenshot der echten C64-Ausgabe stehen aus. Bei langen Datenströmen kann Polling Daten verlieren; ACIA-Overrun und volle Softwarepuffer werden sichtbar gemeldet. Die Firmwareeinstellungen und die Brücke müssen zusammen auf echter Hardware geprüft werden. Ollama-Gespräche und Langzeitgedächtnis sind noch nicht Teil dieser Version.
