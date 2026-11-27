# Kompakter Hardwaretest: experimentelles C64-Display

Dieser Ablauf betrifft nur `build/GIZMO64-TEXT-EXPERIMENT.PRG` nach der [Hardwarekorrektur](EXPERIMENTAL-C64-HARDWARE-CORRECTION.md). Das produktive `GIZMO64.PRG` bleibt der Rückfallstand. Die folgenden Prüfpunkte sind **vorbereitet, nicht als bestanden markiert**.

1. PRG auf dem Ultimate starten und eine normale Frage eingeben. `YOU:` und der bereits getippte Text müssen stabil bleiben; bei der Antwort darf kein zeilenweiser Neuaufbau des gesamten Bildes sichtbar sein. Das Randlogo und seine gelegentliche Bewegung kurz beobachten.
2. Commodore-Taste einmal drücken, halten und loslassen: Das Menü soll **einmal** öffnen. Mit Cursor hoch/runter und RETURN einen Wert wechseln. `HELP` als alternative Öffnung prüfen; F8 muss den Servicemodus öffnen. F6 kann bei Randproblemen das sichere Logo im Bild zeigen.
3. Eine längere Antwort empfangen, F3/F5/F7 kurz prüfen und im F8-Servicemodus `DIAG` ausführen. OV/DROP und den wahrgenommenen Antwortaufbau notieren. Bei einer Störung zum produktiven `GIZMO64.PRG` zurückkehren; keine Einstellungen am Ultimate oder PC ändern.

**Noch offen:** alle obigen Punkte auf echter Ultimate-Hardware, insbesondere C=-Erkennung, Cursorstabilität, Randtiming und Kommunikation unter Last. VICE emuliert die Ultimate-ACIA hier nicht.
