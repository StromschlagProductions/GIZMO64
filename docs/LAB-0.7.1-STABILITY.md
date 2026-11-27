# LAB 0.7.1 – Control-Center-Stabilität

## Befund

Die produktive `installation.json` hat kein eigenes Datenverzeichnis; der Launcher verwendet daher `%LOCALAPPDATA%\GizmoLab`. In der tatsächlichen produktiven `config.json` standen beim Prüfen `uplink_enabled=true`, `uplink_host=auto`, `uplink_port=6464` und `model=gemma4:12b`. Die Adresse `auto` löste sich auf genau eine lokale LAN-Adresse auf. Beim fehlgeschlagenen C64-Versuch zeigte das Control Center nach Angabe des Benutzers `LISTENING`. Ein Verlust dieser produktiven Uplink-Einstellungen ist für diesen Versuch nicht nachgewiesen.

Vor der Korrektur konnte `SAVE SETTINGS` nur nach `START CORE` speichern. Bei einer mehrdeutigen `auto`-Adresswahl brach die Schaltfläche vor dem Schreiben **aller** Einstellungen ab. Jetzt lassen sich Einstellungen auch bei ausgeschaltetem Core laden und speichern. Eine mehrdeutige automatische Adresse bleibt gespeichert; ein Bindefehler erscheint im Uplink-Status. Die Auswahl einer neuen Persönlichkeitsdatei erfordert weiterhin den laufenden Core. Das bestehende Profil wird durch Einstellungen und Code-Updates nicht verändert.

Der SHUTDOWN-Button schließt nach dem kontrollierten Stoppen von Core, Uplink und Ollama auch das Control Center. Während eines laufenden Auftrags wird dessen Ende abgewartet.

## Isolierte Abnahme

- `gizmo_lab/stability_qa.py` installiert den echten produktiven Launcher mit synthetischem Datenverzeichnis. Die GUI speichert sämtliche sichtbaren Modellparameter und Uplink-Werte, schließt über SHUTDOWN, durchläuft einen lokalen Git-Tag-Updatevorgang und startet erneut. Alle Werte, eine zusätzliche Konfigurationsoption, das synthetische Profil und eine synthetische Datenbanksentinel bleiben bytegleich. Es werden keine produktiven Daten geöffnet.
- Der vorhandene reale GUI-Test mit synthetischem Profil und installiertem Gemma-Modell bestand einschließlich SHUTDOWN und vollständigem Ollama-Ende.
- Die bestehende Python-Suite bestand mit 72 Tests. Der Standard-Sandboxlauf blockierte Windows-Sockettests; außerhalb dieser Sandbox bestanden alle 72.

## C64-Befund und Grenze

`src/link.c` ist gegenüber dem hardwaregetesteten Stand 0.2.2 unverändert. In der 04B-Linker-Map endet BSS vor dem Screen-RAM ab `$6400`; Font und Sprites liegen bei `$7000` und `$7800`. Ein synthetischer VICE-3.9-SwiftLink-Test zeigte für beide PRGs dasselbe Verhalten: `ATDT` wurde gesendet, eingehende Modemdaten konnten über diese Emulationsanordnung nicht verlässlich geprüft werden. Dieser VICE-Test allein war keine Ultimate-Hardwareabnahme und kein Nachweis einer Ursache.

Nachtrag vom 27.11.2026: Der Benutzer meldete, dass beide PRGs auf echter Ultimate-Hardware eine Verbindung herstellen und Gespräche mit persönlichem Erinnerungsabruf funktionieren. Für 04B weiter offene Hardwareprüfungen sind in `04B-C64-TERMINAL.md` aufgeführt.
