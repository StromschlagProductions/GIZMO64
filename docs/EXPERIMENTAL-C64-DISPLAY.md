# C64 Display Experiment (unveröffentlicht)

Basis: C64-Client 0.2.3, Commit `930a4ea`. Branch `develop/experimental-c64-display`. Der veröffentlichte Client `GIZMO64.PRG`, `src/ui.c`, `src/main.c` und die Kommunikationsroutine `src/link.c` bleiben unverändert. PC Control Center, Gedächtnis, Modell und Profil sind nicht Teil dieses Experiments.

## Reproduzierbarer Aufbau

```powershell
python tools/test_border_probe.py
python tools/build_display_prototype.py --capture
python tools/test_display_keys.py
```

Die Skripte benutzen das projektlokale cc65 und `x64sc` aus `.local-tools`. `BORDER-PROBE-BASE.PRG` und `BORDER-PROBE-IRQ.PRG` werden mit `ca65` getrennt assembliert; der Test verifiziert, dass die Dateien verschieden sind. Der erste Build ohne IRQ ist die Kontrollgruppe. Das zweite PRG schaltet RSEL auf Rasterzeile 249 aus und auf Zeile 0 wieder ein. Nur ein weißes Sprite ist aktiv. Die Screenshots vergleichen VIC-II 6569 und 8565 mit `-VICIIborders 1` (vollständiger Rand, 408×293 Pixel) und `2` (Debug-Rand, 504×312 Pixel). Die automatische Pixelprüfung nutzt den Vollrandmodus: Rand oben geschlossen schwarz, mit IRQ Hintergrundfarbe und weißes Sprite sichtbar. Normaler VICE-Ausschnitt 384×272 schneidet einen Teil des Randes ab.

Die minimale Routine folgt dem [Top/Bottom-Border-Rezept](https://github.com/bdgscotland/c64-kb/blob/main/docs/recipes/kickassembler/topbottom-border-open.md) und den [VIC-II-RSEL-Vergleichszeilen](https://github.com/rhmoller/commodore64/blob/master/docs/part-3-vic.md). Die [VICE-Dokumentation](https://vice-emu.sourceforge.io/manual/vice.pdf) nennt die Rand- und Modellparameter. Die tatsächlich installierte VICE-Version erwartet `-VICIIborders` mit kleinem `b`.

## Integrierter Prototyp

Erst nach dem isolierten Nachweis wurde die PAL-Rasterroutine in den experimentellen Bitmap-Client aufgenommen. Sie bearbeitet nur VIC-Raster-IRQs; CIA/KERNAL-Ticks für Tastatur und Uhr bleiben aktiv. Die acht Hardware-Sprites zeigen das vorhandene Logo und die Welle im oberen Rand. Der zweite PAL-Sprite-Abdruck am unteren Rand wird auf Rasterzeile 249 deaktiviert und auf Zeile 0 wieder zugeschaltet. Auf NTSC bleibt die sichere Logo-Darstellung im Bildbereich aktiv; die PAL-Routine wird dort nicht installiert.

Der 40-Spalten-HiRes-Renderer verwendet echte Zeilenhöhen. Die zwei Eingabezeilen und die Trennlinie sind in der Zahl der Gesprächszeilen bereits abgezogen:

| Modus | Zeichen | Zeilenhöhe | Gesprächszeilen mit Randlogo | Gesprächszeilen mit sicherem Bildlogo |
| --- | --- | ---: | ---: | ---: |
| STANDARD | 5×7 | 8 Pixel | 22 | 19 |
| COMPACT | 5×6 | 7 Pixel | 26 | 22 |
| DENSE | 5×5 | 6 Pixel | 31 | 27 |

F1 wechselt zwischen Grün und Eisblau. F2/F4 ändern die Zeilenhöhe; F3/F5/F7 bedienen Scrollback, F8 den Servicemodus. Commodore+H und das Eingabekommando `HELP` öffnen das Optionsmenü. Dort bewegen Cursortasten die inverse Auswahlzeile und RETURN ändert Farbe, Schriftgröße, Tastaturbelegung, Logo oder Ton. QWERTY ist Standard; QWERTZ vertauscht Y/Z einschließlich Großbuchstaben. Der Menüpunkt `SAVE SETTINGS TO DRIVE 8` speichert Farbe, Schriftgröße und Tastaturbelegung in `GIZMOPRF` auf einem beschreibbaren Laufwerk 8. Beim Start werden gültige Werte automatisch geladen; ohne Datei gelten die Standardwerte. Der Menüpunkt meldet Schreibfehler. Während einer laufenden Antwort wird Speichern zurückgestellt. F6 schaltet auf PAL zwischen Randlogo und sicherem Bildlogo. Während eines Moduswechsels bleiben der 112-Zeilen-Ring und der Eingabepuffer erhalten. Die produktive Version 0.2.3 bleibt der vollständige Rückfallstand.

Alle drei Vergleichsbilder zeigen denselben synthetischen englischen Dialog. VICE-Bilder inklusive oberem und unterem Rand: [STANDARD](../screenshots/experimental-display/standard.png), [COMPACT](../screenshots/experimental-display/compact.png), [DENSE](../screenshots/experimental-display/dense.png). Die [Build-Metadaten](../screenshots/experimental-display/display-manifest.json) nennen PRG-Hashes und Segmentgrenzen. Die [Border-Probe-Metadaten](../screenshots/experimental-display/border-probe-manifest.json) nennen alle acht Kontrollbilder. Die PNG-Pixelprüfung bestätigt in jedem Modus das Logo, den Dialog und eine leere untere Randzone.

Zusätzlich wurden am laufenden PRG F2 aus STANDARD und F4 aus DENSE per VICE-Tastaturpuffer betätigt. Der Gesprächsbereich ist in beiden Fällen pixelgleich mit dem direkt gestarteten COMPACT-Modus. F6 zeigt das Logo im Bildbereich und erhält den Dialog. Die [Tasten-Prüfdaten](../screenshots/experimental-display/display-key-manifest.json) und das [F6-Bild](../screenshots/experimental-display/f6-fallback.png) sind gespeichert.

F1 wechselte im Emulator den Gesprächs-Farbwert von Phosphorgrün `(94,214,56)` zu Eisblau `(135,240,203)`; das [F1-Bild](../screenshots/experimental-display/f1-ice.png) ist abgelegt.

F3 zeigt im Emulator eine ältere Dialogseite. F5 und F7 stellen danach jeweils den pixelgleichen Live-Ausschnitt wieder her. Die Aufnahmen liegen mit den übrigen Tastentests im Screenshot-Verzeichnis.

F8 öffnete im Emulator den Servicemodus; das eingegebene Kommando `HELP` öffnete das getrennte Optionsmenü. [Service-Bild](../screenshots/experimental-display/f8-service.png) und [Menübild](../screenshots/experimental-display/help-command.png) sind gespeichert. Die Kombination Commodore+H ist damit noch nicht separat bestätigt.

Der VICE-Tastaturpuffer führte `HELP`, zweimal Cursor abwärts und RETURN aus: Die Zeile `KEYBOARD` ist invers markiert und zeigt `QWERTZ` ([Bild](../screenshots/experimental-display/menu-keyboard.png)). Die anschließende echte Eingabe von `YZ` erschien als `ZY`; ein Pixelvergleich mit den Fontzeichen prüft diese Zuordnung. Eine getrennte C64-Prüfroutine kontrollierte zusätzlich die Vertauschung von `Y`, `Z`, `y`, `z` sowie der Großbuchstaben-PETSCII-Codes und den unveränderten QWERTY-Standard.

Ein weiterer Lauf mit NTSC-VIC-II 6567 und vollständigem Rand ergab ein [Bild mit dem sicheren Logo im Display](../screenshots/experimental-display/ntsc-safe.png) (424×253 Pixel). Die PAL-Rasterroutine wurde dabei nicht aktiviert. Das ist eine Emulatorprüfung, keine NTSC-Hardwareabnahme.

## Speicher und aktueller Prüfstand

- Release 0.2.3: 14 423 Byte PRG, BSS-Ende `$5590`.
- Experiment: 19 006 Byte PRG, BSS-Ende `$6778`; Zuwachs 4 583 Byte. Die synthetischen Demodialoge sind nur in den Demo-PRGs enthalten. Der VIC-Bank-2-Bereich beginnt bei `$8000`. Bildschirm `$8400`, Sprites `$8800`, Bitmap `$A000`; `$BFFF` ist das auf Null gesetzte Idle-Byte. Die Linker-Map wird automatisch auf Überlappung geprüft.
- `src/link.c` ist inhaltlich unverändert gegenüber `930a4ea:src/link.c`; nur die Zeilenenden der Windows-Arbeitskopie unterscheiden sich vom Git-Blob. Vorhandener Host-Test für die Kommunikation sowie PRG- und Zeichensatzprüfung wurden lokal ausgeführt. Die VICE-Aufnahmen emulieren **keine** Ultimate-ACIA-Verbindung.
- Der Raster-IRQ besteht aus zwei kurzen Handlern pro PAL-Bild. Ein Zyklusprofil für den integrierten Client ist noch offen; aus den VICE-Bildern allein lässt sich keine belastbare CPU-Prozentzahl ableiten.
- Eine isolierte synthetische C64-Messung in x64sc (PAL 6569, KERNAL-Ticks) ergab vor der Optimierung: sechs neue Zeilen 1008 Ticks, sechs Seitenwechsel 1010 Ticks, zwei Farbwechsel 352 Ticks. Nach inkrementellem Gesprächs-Scrollen und einer 6502-Glyphenroutine: 44, 434 und 160 Ticks. Das sind rund 23-fach schnellere Zeilenanhänge, 2,3-fach schnellere Seitenwechsel und 2,2-fach schnellere Farbwechsel in diesem Messfall. Der Gesprächsbereich des STANDARD-Demobildes ist pixelgleich zum vorherigen Renderer. Die Messung bildet weder Ultimate-ACIA-Empfang noch die subjektive Hardwarewirkung ab; diese Punkte bleiben Teil der Hardwareabnahme.
- Die Messbilder [vorher](../screenshots/experimental-display/benchmark-before.png) und [nachher](../screenshots/experimental-display/benchmark-after.png) wurden aus dem synthetischen C64-Timing-Harness aufgenommen. Sie zeigen Tickzahlen, keine Bildschirmaufnahme eines echten Ultimate.
- Der Menüzustand ist nicht dauerhaft; Farbe, Schriftgröße und QWERTY/QWERTZ werden auf ausdrückliche Wahl von `SAVE SETTINGS TO DRIVE 8` gespeichert. Ein D64-Test in VICE bestätigte Speichern, Überschreiben und Laden nach einem vollständigen Emulatorneustart. Ohne beschreibbares Laufwerk 8 bleibt die Auswahl nur für die aktuelle Sitzung erhalten. Der PC-Konfigurationsmechanismus wurde nicht verändert.
- Commodore+H, Scrollback während Empfang, lange Antworten, Wiederverbindung sowie OV/DROP sind auf echter Ultimate-Hardware noch **nicht** mit diesem experimentellen Client geprüft. Der einzelne erfolgreiche LAB-0.7.1-Hardwarebefund gilt nicht automatisch für diesen Prototyp.

**Freigabestatus:** ausschließlich lokaler Prototyp zur visuellen und technischen Beurteilung. Der [kompakte Hardwaretest](EXPERIMENTAL-C64-HARDWARE-TEST.md) ist vorbereitet, aber noch nicht ausgeführt. Kein Tag, kein Push, keine produktive Installation. Die Cinematic Effects Engine gehört zu einem späteren Auftrag.
