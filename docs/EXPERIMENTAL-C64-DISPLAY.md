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

F1 wechselt zwischen Grün und Eisblau. F2/F4 ändern die Zeilenhöhe; F3/F5/F7 bedienen Scrollback, F8 den Servicemodus. Commodore+H und das Eingabekommando `HELP` öffnen das Hilfsmenü. F6 schaltet auf PAL zwischen Randlogo und sicherem Bildlogo. Während eines Moduswechsels bleibt der 112-Zeilen-Ring und der Eingabepuffer erhalten. Die produktive Version 0.2.3 bleibt der vollständige Rückfallstand.

Alle drei Vergleichsbilder zeigen denselben synthetischen englischen Dialog. VICE-Bilder inklusive oberem und unterem Rand: [STANDARD](../screenshots/experimental-display/standard.png), [COMPACT](../screenshots/experimental-display/compact.png), [DENSE](../screenshots/experimental-display/dense.png). Die [Build-Metadaten](../screenshots/experimental-display/display-manifest.json) nennen PRG-Hashes und Segmentgrenzen. Die [Border-Probe-Metadaten](../screenshots/experimental-display/border-probe-manifest.json) nennen alle acht Kontrollbilder. Die PNG-Pixelprüfung bestätigt in jedem Modus das Logo, den Dialog und eine leere untere Randzone.

Zusätzlich wurden am laufenden PRG F2 aus STANDARD und F4 aus DENSE per VICE-Tastaturpuffer betätigt. Der Gesprächsbereich ist in beiden Fällen pixelgleich mit dem direkt gestarteten COMPACT-Modus. F6 zeigt das Logo im Bildbereich und erhält den Dialog. Die [Tasten-Prüfdaten](../screenshots/experimental-display/display-key-manifest.json) und das [F6-Bild](../screenshots/experimental-display/f6-fallback.png) sind gespeichert.

F1 wechselte im Emulator den Gesprächs-Farbwert von Phosphorgrün `(94,214,56)` zu Eisblau `(135,240,203)`; das [F1-Bild](../screenshots/experimental-display/f1-ice.png) ist abgelegt.

F3 zeigt im Emulator eine ältere Dialogseite. F5 und F7 stellen danach jeweils den pixelgleichen Live-Ausschnitt wieder her. Die Aufnahmen liegen mit den übrigen Tastentests im Screenshot-Verzeichnis.

F8 öffnete im Emulator den Servicemodus; das eingegebene Kommando `HELP` öffnete das getrennte Hilfsmenü. [Service-Bild](../screenshots/experimental-display/f8-service.png) und [Hilfe-Bild](../screenshots/experimental-display/help-command.png) sind gespeichert. Die Kombination Commodore+H ist damit noch nicht separat bestätigt.

Ein weiterer Lauf mit NTSC-VIC-II 6567 und vollständigem Rand ergab ein [Bild mit dem sicheren Logo im Display](../screenshots/experimental-display/ntsc-safe.png) (424×253 Pixel). Die PAL-Rasterroutine wurde dabei nicht aktiviert. Das ist eine Emulatorprüfung, keine NTSC-Hardwareabnahme.

## Speicher und aktueller Prüfstand

- Release 0.2.3: 14 423 Byte PRG, BSS-Ende `$5590`.
- Experiment: 19 006 Byte PRG, BSS-Ende `$6778`; Zuwachs 4 583 Byte. Die synthetischen Demodialoge sind nur in den Demo-PRGs enthalten. Der VIC-Bank-2-Bereich beginnt bei `$8000`. Bildschirm `$8400`, Sprites `$8800`, Bitmap `$A000`; `$BFFF` ist das auf Null gesetzte Idle-Byte. Die Linker-Map wird automatisch auf Überlappung geprüft.
- `src/link.c` ist inhaltlich unverändert gegenüber `930a4ea:src/link.c`; nur die Zeilenenden der Windows-Arbeitskopie unterscheiden sich vom Git-Blob. Vorhandener Host-Test für die Kommunikation sowie PRG- und Zeichensatzprüfung wurden lokal ausgeführt. Die VICE-Aufnahmen emulieren **keine** Ultimate-ACIA-Verbindung.
- Der Raster-IRQ besteht aus zwei kurzen Handlern pro PAL-Bild. Ein Zyklusprofil für den integrierten Client ist noch offen; aus den VICE-Bildern allein lässt sich keine belastbare CPU-Prozentzahl ableiten.
- Der Bitmap-Renderer baut beim Scrollen aktuell noch den sichtbaren Bereich vollständig neu auf. Eine quantitative Scroll-Messung und gezielte Assembler-Optimierung stehen aus. Das ist keine abgenommene Verbesserung des ruckeligen Scrollens.
- Farb- und Schriftgrößenwahl werden nur für die laufende Sitzung gehalten. Dauerhafte Speicherung würde eine zusätzliche Konfigurationsentscheidung erfordern und wurde nicht in den bestehenden PC-Mechanismus geschrieben.
- Commodore+H, Scrollback während Empfang, lange Antworten, Wiederverbindung sowie OV/DROP sind auf echter Ultimate-Hardware noch **nicht** mit diesem experimentellen Client geprüft. Der einzelne erfolgreiche LAB-0.7.1-Hardwarebefund gilt nicht automatisch für diesen Prototyp.

**Freigabestatus:** ausschließlich lokaler Prototyp zur visuellen und technischen Beurteilung. Kein Tag, kein Push, keine produktive Installation.
