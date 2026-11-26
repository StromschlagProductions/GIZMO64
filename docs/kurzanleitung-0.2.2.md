# GIZMO-64 0.2.2 – Kurzanleitung

1. Auf dem Windows-PC Python 3 und Ollama installieren. Das vorhandene Modell `richardyoung/qwen2.5-7b-instruct-abliterated:latest` beibehalten.
2. **Brücke und PRG gemeinsam aktualisieren.** Die neue Brücke wartet nach jeder Antwortzeile auf `ACK` vom C64. Ein alter Client kann mit dieser Brücke keine Antworten vollständig empfangen.
3. `start-gizmo.bat` starten. Das Fenster meldet, wann Ollama und TCP-Port 6464 bereit sind. Das Ultimate benötigt SwiftLink/ACIA bei `$DE00` wie bisher; die ACIA-Register und 2400 Baud wurden nicht geändert.
4. `GIZMO64.PRG` starten. Standardziel ist `192.168.178.244:6464`. Bei abweichender Adresse `IP <adresse>` und `UPLINK` eingeben.
5. Eine kurze und eine längere Frage stellen. Während GIZMO antwortet, bleiben getippte Zeichen im Eingabepuffer und werden nach Antwortende angezeigt; Enter dann erneut drücken. `DIAG` aufrufen: Zielwerte `OV:0` und `DROP:0`. Bei Übertragungsfehlern trennt der Client und verbindet erneut. `F1` schaltet weiterhin die drei Farben um.
6. PC-Brücke mit ESC, Q, ENTER oder Strg+C beenden. Sie beendet Ollama und überprüft laufende Ollama-Prozesse.

Die Brücke speichert `memory.json` und `config.local.json` nur lokal. Beide Dateien sind nicht Teil des ZIP. An der Persönlichkeit und dem Standardmodell wurde nichts geändert.

## Technischer Befund

Die vorherige Brücke sendete aufeinanderfolgende Zeilen nach einer festen Zeitpause. Das Scrollen auf dem 1-MHz-C64 kann länger dauern als diese Pause; dann füllt sich der 128-Byte-RX-Ring und `DROP` steigt ohne ACIA-Overrun. Version 0.2.2 sendet `BEGIN`, jede Textzeile, Absatzmarkierungen und `END` einzeln. Nach dem vollständig verarbeiteten Datensatz sendet der C64 `ACK`, erst dann folgt der nächste. Der Client verlängert die Antwortfrist bei tatsächlicher RX-Aktivität. Ein nicht beendeter Antwortblock führt zur sauberen Modemtrennung und automatischen Wiederwahl.

`[[GIZMO:PARA]]` kennzeichnet einen Absatz. Für den Hardwaretest bitte auch mehrere Absätze, Satzzeichen und mindestens 100 Antwortzeilen prüfen. Die automatisierten Tests simulieren die ACIA und die TCP-Schnittstelle; sie beweisen keinen realen `DROP:0`-Wert auf Ultimate-Hardware. Der [VICE-Screenshot](../screenshots/vice-0.2.2.png) zeigt die echte PRG mit dem 5×6-Zeichensatz im Offline-Modus. VICE emuliert hier die Ultimate-ACIA nicht.
