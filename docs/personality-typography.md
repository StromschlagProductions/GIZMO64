# GIZMO-64 0.2.1 – Personality & Typography

Das Standardmodell ist `richardyoung/qwen2.5-7b-instruct-abliterated:latest`. Die Brücke lädt es beim Start über Ollamas `/api/generate` mit `keep_alive: -1` vor. Antworten kommen über `/api/chat` als JSON-Zeilenstream, ebenfalls mit `keep_alive: -1` und maximal 768 Generierungstokens. Im PC-Fenster erscheinen Zeit bis zum ersten Text, Gesamtdauer und Tokenrate. Die Brücke entfernt auch fragmentierte `<think>`-Blöcke vor der ASCII-Umwandlung. Eine vollständige Bildschirmzeile wird mit einer Pause entsprechend 2400 Baud gesendet; `[[GIZMO:BEGIN]]` und `[[GIZMO:END]]` bleiben unverändert. Die sechszeilige Begrenzung entfällt.

Die Persönlichkeit liegt in `bridge/gizmo_bridge.py`. Eine lokale `bridge/config.local.json` kann `model` und `personality` überschreiben; die Beispieldatei zeigt das Format. `bridge/memory.json` bleibt lokal und wird durch normale Builds nicht überschrieben. Die Brücke löscht Ollama-Prozesse beim Beenden gemäß der gewünschten Studio-Betriebsweise, auch wenn sie vor der Brücke gestartet wurden.

## VIC-II-Speicherkarte

| Bereich | Adresse | Zweck |
| --- | --- | --- |
| Programm samt BSS | `$0801`–`$3E4B` im geprüften Build | Code und Daten |
| Bildschirm | `$6400`–`$67E7` | 40 × 25 Zeichen |
| Sprite-Pointer | `$67F8`–`$67F9` | zwei Wellenform-Sprites |
| Zeichensatz | `$7000`–`$77FF` | 256 Zeichen à 8 Bytes |
| Sprites | `$7800`–`$79FF` | vier Frames mit je zwei Sprites |

VIC-Bank 1, Textmodus und `$D018 = $9C` werden ausdrücklich gesetzt. `assets/build_font.py` definiert die 5×7-Glyphen; `assets/gizmo-font.bin` ist die daraus erzeugte 2048-Byte-Ressource. Buchstaben liegen auch auf C64-Screen-Codes 1–26; Satzzeichen sind an ASCII-Positionen. Die zweite Hälfte enthält Inversglyphen. Code 95 ist die durchgehende Rahmenlinie, Code 96 ein schmaler Cursor. Die Null trägt einen diagonalen Strich. Die feste Kopf- und Fußzeile sowie die Sprite-Welle bleiben außerhalb des scrollenden Gesprächsbereichs.

## Zeichenkodierung

cc65 kodiert Buchstabenliterale im C64-Ziel als PETSCII `$C1`–`$DA`; ASCII-Satzzeichen bleiben im geprüften Literal als `$21` für `!` und `$3F` für `?` erhalten. `src/link.c` setzt Buchstaben auf ASCII `$41`–`$5A` um und lässt Satzzeichen unverändert. `src/ui.c` wandelt Buchstaben in Screen-Codes 1–26 um und nutzt für Satzzeichen die Positionen des eigenen Zeichensatzes. Die Hosttests prüfen den ganzen unterstützten Satzzeichenkatalog; `tests/charset_test.py` prüft zusätzlich die tatsächliche cc65-Ausgabe.

## Prüfung und Grenzen

`make test`, `make package`, `python3 -m py_compile bridge/gizmo_bridge.py` und ein cc65-Neubau liefen erfolgreich. [VICE-Start](../screenshots/vice-0.2.1.png) zeigt die echte PRG. Im [VICE-Gesprächsbild](../screenshots/vice-0.2.1-conversation.png) wurde nach dem echten PRG-Start Testtext per VICE-Monitor in den Bildschirmbereich geschrieben, um Schrift und Hierarchie zu prüfen. Der Inhalt ist eine Simulation, keine Ollama-Antwort. VICE emulierte die Ultimate-ACIA hier nicht; die reale Verbindung, Ollama auf dem Windows-PC und die Abschaltung seiner Prozessbäume brauchen den Hardwaretest des Nutzers.
