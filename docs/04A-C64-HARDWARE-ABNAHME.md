# LAB 0.7.0 – C64-Uplink und Hardwareabnahme

Die C64-PRG und die Kommunikationsquellen stammen unverändert aus dem hardwaregetesteten Stand `v0.2.2`. Die neue PC-Seite hängt den Uplink an dieselbe LAB-Engine wie das Control Center. Der bisherige eigenständige Bridge-Prozess mit eigenem Modell und `memory.json` wird nicht mehr gestartet.

## Gemeldeter Teilbefund zum Ultimate (26.11.2026)

Der Benutzer meldete für den ersten realen Test von LAB 0.7.0 auf dem C64 Ultimate funktionierende Gespräche, `DIAG` mit `OV:0` und `DROP:0` sowie eine wahrgenommene Latenz von etwa 1–3 Sekunden bis zum ersten Antworttext. Das bestätigt diesen einzelnen Dialog-/Transportversuch. Ein Test mit mindestens 100 empfangenen Antwortzeilen, Scrollen und Tippen während des Empfangs sowie eine dokumentierte Wiederverbindung wurden dabei noch nicht gemeldet; sie gelten weiterhin als offen. Am 27.11.2026 wurde zusätzlich der erfolgreiche Grundbetrieb des neuen 04B-PRG auf dem Ultimate gemeldet; Details und offene Prüfungen stehen in `04B-C64-TERMINAL.md`.

## Einfacher Start

1. `GIZMO.cmd` starten. Im Control Center unter SETTINGS **ENABLE COMMODORE UPLINK WHEN CORE STARTS** einschalten, `UPLINK HOST` auf `auto` und `UPLINK PORT` auf `6464` setzen und speichern. Die Einstellung bleibt lokal erhalten. `auto` benötigt genau eine private LAN-IPv4-Adresse; bei mehreren Adressen dort die richtige private IPv4-Adresse eintragen. Es wird keine Firewall-Regel angelegt.
2. **START CORE** drücken. COMMODORE UPLINK muss `LISTENING` und die tatsächliche lokale IP mit Port 6464 anzeigen. `ERROR` nennt einen Bindefehler; erst diesen beheben. Die historische Anleitung `kurzanleitung-0.2.2.md` beschreibt noch den alten separaten Bridge-Starter und gilt für LAB 0.7.0 nicht als PC-Startanleitung.
3. Die originale `GIZMO64.PRG` aus `GIZMO64-v0.2.2.zip` auf dem Ultimate starten. SwiftLink/ACIA bei `$DE00` und 2400 Baud wie im bewährten Setup belassen. Das PRG-Ziel ist standardmäßig `192.168.178.244:6464`. Bei abweichender PC-IP auf dem C64 `IP <adresse>` und dann `UPLINK` eingeben.
4. Eine kurze Frage und danach eine längere Frage mit mehreren Absätzen und Satzzeichen stellen. Das Control Center soll `CONNECTED` anzeigen. Auf dem C64 muss die Antwort ohne fehlende oder verdoppelte Zeilen enden. Danach `DIAG` eingeben und `OV:0` sowie `DROP:0` prüfen.
5. Verbindung am C64 trennen und mit `UPLINK` erneut herstellen. Eine weitere Frage stellen; auf dem PC müssen `DISCONNECTED` und anschließend `CONNECTED` sichtbar werden. Zum Schluss **SHUTDOWN** drücken und prüfen, dass kein Ollama-Prozess mehr läuft.

Nur ein tatsächlich durchgeführter Test auf dem Ultimate mit diesen Ergebnissen ist eine Hardwareabnahme. Die automatisierten TCP-Tests sind ein Simulator, kein Nachweis für ACIA- oder Modemstabilität.

## Datenschutz und Rückkehr zum vorherigen Stand

Das Control Center benutzt das bestehende lokale Profil und die bestehende SQLite-Datenbank. Die Schema-Aktualisierung erstellt vor Änderungen eine lokale Sicherung. Die veraltete `memory.json` wird weder importiert noch gelöscht. Kein Gesprächsinhalt wird im normalen Uplink-Status protokolliert.

Die Installation behält ältere Programm-Releases. Bei einem Problem `GIZMO.cmd` schließen und **SHUTDOWN** abwarten; den vorherigen Programm-Release nur mit einer passend gesicherten Datenbank zurücksetzen. Die neue SQLite-Schema-Version nicht mit einer älteren LAB-Version öffnen. Fehlerbericht und lokale Sicherung aufbewahren, bevor eine Rückkehr ausgeführt wird.
