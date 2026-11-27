# GIZMO-64 0.2.3 – Kurzanleitung

## Start

1. Auf dem PC `GIZMO.cmd` starten und **START CORE** drücken. In SETTINGS muss der Commodore Uplink aktiviert sein. Das Control Center zeigt `LISTENING` mit Port 6464.
2. `GIZMO64.PRG` aus diesem Paket auf dem C64 Ultimate starten. Die vorhandene SwiftLink-/ACIA-Konfiguration bei `$DE00` und 2400 Baud beibehalten. Der Client wählt die bereits im Programm eingetragene PC-Adresse automatisch.
3. Wenn sich die PC-Adresse geändert hat: Auf dem C64 F8 für den Servicemodus drücken, `IP <PC-Adresse>` eingeben, ENTER drücken und danach `UPLINK` eingeben. F8 schließt den Servicemodus.
4. Im normalen Gespräch eine Nachricht eingeben und mit ENTER senden. F1 wechselt zwischen Grün und Eisblau. F3/F5 blättern im sichtbaren Gesprächsverlauf, F7 kehrt zur aktuellen Antwort zurück. Technische Angaben stehen nur im Servicemodus.
5. Am PC beendet **SHUTDOWN** den Core, den Uplink, Ollama und das Control Center.

Der C64-Client nutzt dieselbe PC-Engine, dasselbe Persönlichkeitsprofil und dieselbe Gedächtnisdatenbank wie das Control Center. Dieses Paket enthält **keine** zweite PC-Brücke. Persönliche Daten und das Profil gehören nicht in das C64-Paket.

## Abnahmestand

Auf echter Ultimate-Hardware wurden Verbindung, Eingabe, Antworten und persönlicher Erinnerungsabruf für das neue PRG bestätigt. Weitere Hardwareprüfungen, insbesondere lange Antworten, Scrollback während des Empfangs, Wiederverbindung und `OV`-/`DROP`-Zähler, sind offen. Das ruckelige Scrollen ist für eine spätere Optimierung notiert. Die bisherige PRG 0.2.2 bleibt als Rückfallversion verfügbar.
