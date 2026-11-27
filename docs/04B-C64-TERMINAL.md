# Auftrag 04B – C64 Terminal Refresh

Status: als C64-Client 0.2.3 ausgeliefert; LAB 0.7.1 auf dem PC bleibt unverändert. Der Benutzer meldete am 27.11.2026 einen erfolgreichen Test **beider** PRGs auf echter C64-Ultimate-Hardware: Verbindung zum PC, Eingabe und Antworten sowie persönlichen Erinnerungsabruf. Der frühere `OV:0`-/`DROP:0`-Befund und die wahrgenommene Latenz von 1–3 Sekunden betreffen ausschließlich das alte PRG 0.2.2. Für das neue PRG wurden diese Zähler und die Latenz nicht gemeldet.

## Oberfläche

- Der Header ist eine 320×24-Pixelkomposition aus 53 eigens erzeugten C64-Grafikzeichen. Breiter GIZMO-Schriftzug, abgeschrägter Rahmen und Doppellinien stammen aus `assets/build_font.py`; die beiden vorhandenen 24×21-Sprites sitzen in einer freien Lücke rechts und bewegen sich nur bei tatsächlicher Aktivität. Es gibt kein Planeten- oder Robotersymbol.
- Die unteren 128 Textzeichen des RAM-Fonts sind bytegleich zum filigranen 5×7-Stand des 0.2.1-Commits `99850d6`. Die Grafikzeichen belegen nur den zuvor für inverse Zeichen verwendeten oberen Bereich. F1 wechselt ausschließlich Grün (Text 5, Akzent 13) und Eisblau (Text 3, Akzent 14).
- Zeilen 0–2 bilden das Logo; Zeile 3 bleibt im verbundenen Normalbetrieb als optischer Abstand frei und zeigt nur bei Bedarf `INITIALIZING`, `SYSTEM UNAVAILABLE`, den Scrollback-Hinweis oder den Servicemodus. Zeilen 4–20 zeigen den Dialog. Zeile 21 trennt die feste zweizeilige Eingabe in 22–23 ab; Zeile 24 nennt F1 COLOR, F3 BACK, F5 NEXT, F7 LIVE.
- Ein Ring mit 112 darstellbaren 40-Zeichen-Zeilen hält Sprecher- und Absatzzeilen. F3/F5 blättern um neun Zeilen, F7 kehrt live zurück. Neue Antworten werden während des Lesens aufgenommen und bestätigt, ohne die Ansicht zu verschieben. Bei vollem Ring entfallen nur die ältesten sichtbaren C64-Zeilen; das PC-Archiv bleibt vollständig. Die Eingabe bleibt unabhängig davon erhalten und zeigt bei mehr als 74 Zeichen das Ende des 120-Zeichen-Puffers.
- F8 öffnet und schließt den Servicemodus. Nur dort stehen IP, Port, ACIA, Status, RX/TX, OV/DROP, `DIAG`, `HEX`, `PING`, `UPLINK`, `OFFLINE` und `SOUND` zur Verfügung. Im Normalbild erscheinen keine technischen Verbindungsdetails. SID-Tastentöne sind standardmäßig aus und über `SOUND` im Service schaltbar.

## Projektlokaler Build

Alle Werkzeuge liegen unter `.local-tools/`, bleiben außerhalb von Git und ändern keine Windows-Systemeinstellungen:

| Werkzeug | Quelle | SHA-256 des lokal verwendeten ZIP |
| --- | --- | --- |
| cc65 Snapshot Win64 (`cl65 V2.19`) | `https://downloads.sourceforge.net/project/cc65/cc65-snapshot-win64.zip` | `F90F804B881862353E22AA640499ADE3F091D442CDDDD9FDC9410A3D1CCBF468` |
| TinyCC 0.9.27 Win64 | `https://download.savannah.gnu.org/releases/tinycc/tcc-0.9.27-win64-bin.zip` | `34A721949A2583FDFF725312DA092FA0F5F1F284B702E6F811C6954714FAABB2` |
| VICE 3.9 SDL2 Win64 | `https://downloads.sourceforge.net/project/vice-emu/releases/binaries/windows/SDL2VICE-3.9-win64.zip` | `B2E637B9F0D179C096F5C60CCDBDEBED79D8F2A2AE846C14A65D28ECFACD0332` |

Nach dem Entpacken in `.local-tools/cc65`, `.local-tools/tcc` und `.local-tools/vice`:

```powershell
.\.venv\Scripts\python.exe tools\build_04b.py
.\.venv\Scripts\python.exe tools\vice_capture_04b.py
.\.venv\Scripts\python.exe tools\package_023.py
```

Der Build erzeugt `build/GIZMO64-04B.PRG`, Font und Header-Kachelkarte, prüft die C-Hosttests und weist anhand der Linker-Map nach, dass Programm und BSS unterhalb des reservierten Screen-RAM ab `$6400` enden. Der zuletzt gemessene BSS-Endpunkt war `$5590`. `src/link.c` mit ACK je Datensatz, ACIA `$DE00` und 2400 Baud wurde nicht verändert. Das Paket `build/GIZMO64-v0.2.3.zip` enthält nur das PRG, eine aktuelle Kurzanleitung und dessen SHA-256; insbesondere keine zweite PC-Brücke oder persönliche Daten.

Die VICE-Screenshots unter `screenshots/vice-04b-*.png` stammen vom tatsächlich gebauten PRG; die `-3x`-Dateien sind pixelgetreu ohne Glättung vergrößert. `vice-04b-manifest.json` enthält den PRG-Hash. VICE emuliert die Ultimate-ACIA hier nicht, deshalb zeigt die normale Aufnahme wahrheitsgemäß `SYSTEM UNAVAILABLE`. Die Screenshots belegen Rendering, Farben und F8-Serviceansicht, keine Hardware-Verbindungsstabilität.

## Hardwarebefund und offene Prüfungen

Auf dem Ultimate bestätigt: Verbindungsaufbau des neuen PRG, Texteingabe, empfangene Antworten und Zugriff auf persönliche Erinnerungen über die gemeinsame LAB-Engine. Nicht ausdrücklich geprüft oder gemeldet: mindestens 100 Antwortzeilen, F3/F5/F7-Scrollback während des Empfangs, Tippen während langer Antworten, F1-Farbwechsel, F8-Service, `OV`/`DROP`, Verbindungsabbruch und Wiederverbindung sowie Laufzeit- und Latenzmessungen. Automatisierte Tests prüfen diese Oberflächen- und Protokollwege nur lokal; sie ersetzen keinen Hardwarebefund. Das alte PRG 0.2.2 bleibt als Rückfallversion verfügbar. Der PC-Updater verändert keinen C64-Datenträger.

Das teilweise ruckelige Scrollen bleibt ein späterer Optimierungspunkt. Es wurde für 0.2.3 nicht verändert.
