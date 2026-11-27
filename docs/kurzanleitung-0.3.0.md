# GIZMO-64 0.3.0 – Kurzanleitung

## Start

1. Auf dem PC LAB 0.7.1 mit `GIZMO.cmd` starten. In SETTINGS den Commodore Uplink aktivieren und **START CORE** drücken. Der Uplink soll `LISTENING` auf Port 6464 anzeigen.
2. `GIZMO64.PRG` auf dem C64 Ultimate starten. Die vorhandene SwiftLink-/ACIA-Konfiguration bei `$DE00` und 2400 Baud beibehalten.
3. Nachricht eingeben und mit RETURN senden. Die Commodore-Taste öffnet das Menü; Cursortasten wählen, RETURN schaltet um. `HELP` öffnet das Menü ebenfalls. F1 wechselt Grün/Eisblau; F2/F4 wechseln die Schriftgröße. F3/F5/F7 steuern Scrollback, F6 schaltet auf das sichere Logo im Bildschirmbereich, F8 öffnet den Servicemodus.
4. Im Menü lassen sich QWERTY (Standard) und QWERTZ sowie Farbe und Schriftgröße einstellen. Einstellungen können auf Laufwerk 8 gespeichert werden.
5. **SHUTDOWN** im PC-Control-Center beendet Core, Uplink, Ollama und Control Center.

Wenn sich die PC-Adresse geändert hat: F8 drücken, `IP <PC-Adresse>` eingeben und danach `UPLINK` eingeben. Die PC-Engine, das Persönlichkeitsprofil und das Gedächtnis liegen ausschließlich bei LAB 0.7.1; das C64-Paket enthält keine privaten Daten.

## Rückfall

Das bisherige Paket `GIZMO64-v0.2.3.zip` und der Git-Tag `v0.2.3` bleiben verfügbar. Bei Problemen kann dessen `GIZMO64.PRG` wieder auf dem Ultimate gestartet werden; PC-Einstellungen und persönliche Erinnerungen werden dadurch nicht geändert.

## Abnahmestand

Der Benutzer bestätigte am 27.11.2026 auf echter Ultimate-Hardware: Logo im oberen Rand, Commodore-Taste, Menü, Schriftgrößenumschaltung, stabile Eingabe und sehr gute Textgeschwindigkeit. Das gelegentliche leichte Zucken des Logos wurde ausdrücklich akzeptiert. Verbindung, Eingabe, Antworten und persönlicher Erinnerungsabruf waren zuvor für 0.2.3 auf Ultimate bestätigt; die aktuelle 0.3.0-Hardwaremeldung nennt keinen erneuten Verbindungs- oder Gedächtnistest. Für 0.3.0 wurden `OV`/`DROP`-Werte und Langzeitstabilität nicht ausdrücklich geprüft.
