# Kompakter Hardwaretest: experimentelles C64-Display

Dieser Ablauf betrifft nur `build/GIZMO64-DISPLAY-EXPERIMENT.PRG`. Das produktive `GIZMO64.PRG` bleibt der Rückfallstand. Die folgenden Prüfpunkte sind **vorbereitet, nicht als bestanden markiert**.

1. PRG auf dem Ultimate starten. Logo im oberen Rand, Wellenform, freie Trennung zum Gespräch und keine dauerhafte Hilfszeile prüfen. F6 einmal zum sicheren Logo im Bild und zurück schalten. Falls der Rand flackert oder Elemente überlagert, den sicheren Modus verwenden und den Befund notieren.
2. `HELP` eingeben. Mit Cursor hoch/runter die inverse Auswahl bewegen; mit RETURN Grün/Eisblau, STANDARD/COMPACT/DENSE und QWERTY/QWERTZ umschalten. Y/Z und SHIFT+Y/Z in einer unkritischen Eingabe prüfen. F8 muss weiterhin den Servicemodus öffnen.
3. Falls ein beschreibbares Laufwerk 8 vorhanden ist: `SAVE SETTINGS TO DRIVE 8` wählen, PRG vollständig neu starten und Farbe, Schriftgröße und Tastaturbelegung vergleichen. Bei fehlendem Laufwerk muss eine klare Fehlermeldung erscheinen; der Standard QWERTY muss funktionieren.
4. Eine kurze und eine lange Antwort über die echte ACIA-Brücke empfangen. F3/F5/F7 und Eingabe während des Scrollbacks prüfen. Nach F8 `DIAG` ausführen und Verbindungsstatus sowie OV/DROP notieren. Keine Änderungen an Ultimate- oder PC-Einstellungen nötig.
5. Bei Kommunikationsfehler, instabilem Rand oder beschädigter Darstellung zum produktiven `GIZMO64.PRG` zurückkehren. PRG-Dateien nicht überschreiben.

**Noch offen:** alle obigen Punkte auf echter Ultimate-Hardware, insbesondere Randtiming, lange Antworten, Scrollgefühl und Kommunikation unter Last. VICE emuliert die Ultimate-ACIA hier nicht.
