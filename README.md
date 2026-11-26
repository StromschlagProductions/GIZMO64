# GIZMO-64

## Aktuell: LAB 0.7.0 / C64-Uplink 04A

Das PC-Control-Center und das originale C64-PRG 0.2.2 benutzen dieselbe LAB-Engine, dasselbe Modell, Persönlichkeitsprofil und lokale Gedächtnisdatenbank. `GIZMO.cmd` startet das Control Center; der C64-Uplink wird einmalig unter SETTINGS aktiviert und startet danach mit START CORE. Der alte eigenständige Bridge-Starter startet keine zweite Engine mehr. Die [04A-Anleitung und Hardwareabnahme](docs/04A-C64-HARDWARE-ABNAHME.md) beschreibt den einfachen Start und die noch offene Ultimate-Prüfung. Die folgenden Abschnitte dokumentieren ältere C64-Versionen und deren damalige Bridge.

GIZMO-64 ist ein nativer C64-Ultimate-Client mit einer lokalen Python-TCP-Brücke zu Ollama. Version 0.2.1 ergänzt gestreamte, längere Antworten, eine ausgearbeitete Persönlichkeit und einen eigenen 5×7-Zeichensatz. Der hardwaregetestete Stand 0.1.2 ist als Git-Tag `v0.1.2` gesichert.

Die [Kurzanleitung 0.2.1](docs/kurzanleitung-0.2.1.md) beschreibt Installation und Bedienung. [Technik und VICE-Prüfung](docs/personality-typography.md) dokumentieren Zeichensatz, Speicherkarte, Kodierung und Grenzen.

Die [Anleitung für First Contact](docs/first-contact.md) dokumentiert die ältere Version 0.2 und ihren Verbindungsaufbau.

## Version 0.1.1 und Hardwarekorrektur

Der historische Stand 0.1.1 verwendete VIC-Bank 0, Bildschirm `$0400` und den ROM-Zeichensatz. Zwei Hardware-Sprites bilden eine zusammenhängende Wellenform. Header und Fußzeile bleiben beim Scrollen stehen. ASCII vom Netzwerk, cc65-PETSCII und Bildschirmcodes werden getrennt konvertiert. Die damaligen Details und der [VICE-Screenshot](screenshots/vice-0.1.1.png) stehen in [docs/oberflaeche.md](docs/oberflaeche.md). Version 0.2.1 nutzt VIC-Bank 1 mit dem neuen RAM-Zeichensatz.

Version 0.1.2 korrigiert die ACIA-Empfangskonfiguration und ergänzt die Uplink-Diagnose. Der Hardwaretest von 0.1.1 bestätigte eine TCP-Verbindung, aber noch keinen empfangenen Handshake. [docs/acia.md](docs/acia.md) beschreibt die Registerprüfung und die neuen Diagnosebefehle.

## Bauen

Benötigt werden cc65 mit `cl65` im `PATH`, `make` und für die Hosttests ein C-Compiler. Im Repository `make`, danach liegt `GIZMO64.PRG` im Hauptverzeichnis. `make test` führt die Protokoll- und Oberflächentests auf dem Build-Rechner aus. `make package` erzeugt `GIZMO64-v0.2.1.zip` mit PRG, Brücke, BAT, Konfigurationsbeispiel und deutscher Kurzanleitung. Die GitHub Action stellt dieses Paket als Artefakt bereit.

Unter Windows cc65 aus den offiziellen Releases installieren und dessen `bin`-Verzeichnis zum `PATH` hinzufügen. Mit MSYS2 oder MinGW `make` beziehungsweise `mingw32-make` ausführen. Eine Schrittfolge steht in [docs/windows-build.md](docs/windows-build.md).

## Bedienung

Das PRG mit `LOAD"GIZMO64.PRG",8,1` und `RUN` starten oder direkt über den Dateibrowser des Ultimate laden. Es wählt automatisch `192.168.178.244:6464`. Der Windows-PC muss die vorhandene Brücke auf Port 6464 gestartet haben. Ohne erreichbaren PC endet der Verbindungsversuch im Offline-Modus. Die Eingabe bleibt währenddessen bedienbar.

| Befehl | Wirkung |
| --- | --- |
| `HELP` | Befehle anzeigen |
| `STATUS` | Linkstatus und Zieladresse anzeigen |
| `UPLINK` | Verbindungsaufbau erneut starten |
| `PING` | Verbindung erneut prüfen |
| `DIAG` | RX-/TX-Zähler, ACIA-Status und Fehlerzähler anzeigen |
| `HEX` | Letzte 16 empfangene Bytes als Hex anzeigen |
| `OFFLINE` | Modem per DTR trennen |
| `CLS` | Terminalbereich löschen |
| `IP` | Zieladresse anzeigen |
| `IP 192.168.178.244` | Zieladresse ändern |
| `F1` | Farbe umschalten |
| `MERKE: ...` | Fakt über die Brücke lokal speichern |
| `ERINNERE` | Gespeicherte Fakten abrufen |

Die IP-Änderung gilt bis zum nächsten Programmstart. Die Oberfläche nutzt 40 × 25 Zeichen, feststehende Header- und Fußzeilen, zwei animierte Hardware-Sprites und ein kurzes SID-Tastenfeedback.

## Ultimate einrichten

In den Ultimate-Einstellungen die ACIA/SwiftLink-Emulation auf `$DE00` und den Modem-Modus aktivieren. DTR-Verbindungsabbruch und RTS-Handshake aktivieren. Die Einstellungen heißen je nach Firmware unterschiedlich. Der Client arbeitet mit 2400 Baud, 8 Datenbits, einem Stoppbit und Polling. Die PC-Brücke muss `PING` mit `PONG // GIZMO UPLINK AKTIV` beantworten und nach dem Verbindungsaufbau `UPLINK HERGESTELLT. GIZMO ONLINE.` senden. Der Client akzeptiert CONNECT und Begrüßung in beliebiger Reihenfolge. Details stehen in [docs/acia.md](docs/acia.md).

## Aktuelle Grenzen

Version 0.1.2 wurde auf dem echten Ultimate mit CONNECT, Begrüßung, PING und PONG erfolgreich geprüft; die 0.2-Kommunikation wurde laut Hardwarebericht ebenfalls erfolgreich getestet. Version 0.2.1 wurde kompiliert, mit Hosttests geprüft und in VICE gestartet. Der neue Streaming-Pfad, das lokale Modell und der Windows-Prozessabschluss brauchen noch einen echten Test auf Ultimate und Studio-PC. Ohne emulierte Ultimate-ACIA bleibt VICE offline. ACIA-Overrun und volle Softwarepuffer werden sichtbar gemeldet.
