# Hardwarekorrektur nach dem ersten Ultimate-Test

Branch `develop/experimental-c64-display`. Der produktive Client 0.2.3, `GIZMO64.PRG`, LAB 0.7.1, die PC-Engine und `src/link.c` bleiben unangetastet. Die Messdaten stammen ausschließlich aus x64sc mit PAL-VIC-II 6569 und synthetischen Texten.

## Fehlerursachen

- Im Bitmap-Client löschte `ui_tick()` beim Cursorblinken regelmäßig den gesamten Eingabebereich und zeichnete `YOU:` sowie alle eingegebenen Zeichen neu. Jeder Tastendruck tat dasselbe. Der Bitmap-Prototyp zeichnet nun ausschließlich geänderte Zeichen und den Cursor. Die Beschriftung bleibt stehen.
- Bei empfangenen Zeilen musste der Bitmap-Client viele Pixel sichtbar verschieben. Auch die optimierte 6502-Kopie bleibt eine über den Gesprächsbereich wandernde Bitmap-Aktualisierung. Die synthetische Messung von sechs einzelnen Zeilen hatte diese Wahrnehmung und den vollständigen Empfangspfad nicht abgebildet.
- Das Menü reagierte nur auf eine Zeichenkombination mit dem kurzlebigen KERNAL-Modifier-Flag. Der experimentelle Hauptpfad fragt die Commodore-Taste nun direkt an CIA1, Spalte 7/Zeile 5, ab und nutzt das KERNAL-Flag als zweite Erkennung. Eine Flankensperre verhindert erneutes Umschalten beim Halten. `HELP` bleibt als Alternative. Die [CIA1-Matrix](https://github.com/bdgscotland/c64-kb/blob/main/docs/hardware/cia-reference.md) und [Modifier-Bits](https://github.com/bdgscotland/c64-kb/blob/main/docs/hardware/c64-memory-map.md) sind dokumentiert.
- Ein erster Zeichensatz-Prototyp legte den Bildschirm bei `$6400` ab, obwohl der Programmspeicher bis etwa `$6B00` reichte. Dadurch wurden Zustandsvariablen überschrieben. Außerdem lag der Zeichensatz zunächst bei `$9000`, wo der VIC-II das eingebaute Zeichen-ROM sieht; F2/F4 konnten deshalb den sichtbaren Font nicht ändern. Das Kandidaten-PRG übernimmt nun **die bewährten Adressen des funktionierenden Logos**: Bildschirm `$8400`, Logo-Sprites `$8800`, unveränderte Randroutine. Nur der Textfont liegt im freien RAM bei `$A000`. Die Linker-Map prüft BSS gegen `$8000`.

## Entscheidung zwischen A und B

Der Test speist 24 synthetische englische Antwortblöcke mit 240 Byte/s durch eine **separate Testkopie** des unveränderten RX-Parsers. BEGIN/END-Rahmen, Zeilenumbruch, 16-Byte-Verarbeitungsquote, Sendepuffer und ACKs laufen mit. Vorher werden 90 Zeichen einzeln eingegeben und eine Frage abgesendet. Alle Werte sind KERNAL-Ticks bei PAL-C64-Geschwindigkeit. Die Testkopie simuliert RX und TX; eine Ultimate-ACIA-Verbindung wird dadurch nicht behauptet.

| Variante | 90 Tasteneingaben | Gesamter RX/ACK-Dialog | Drops | gesendete Bytes |
| --- | ---: | ---: | ---: | ---: |
| Veröffentlicht 0.2.3 | 644 | 3625 | 0 | 123 |
| A: optimiertes HiRes | 254 | 890 | 0 | 123 |
| B: Zeichensatz, 6502-Scroll | 168 | 577 | 0 | 123 |

Die 123 Bytes bestehen aus 19 Bytes für die synthetische Frage und 26 mal `ACK` plus CR. Für den experimentellen Hardwaretest wird **Variante B** verwendet. Sie hält `YOU:` und vorhandenen Eingabetext stabil, setzt neue Zeichenzellen statt Pixelstreifen, nutzt das funktionierende Randlogo und behält Menü, QWERTZ, Scrollback und F8. F2/F4 wählen drei Schriftformen innerhalb der festen 8-Pixel-Zeichenzelle; dadurch ändert sich die Zahl der sichtbaren Zeilen nicht wie im Bitmap-Prototyp.

Die [Vorschau des kompilierten Textclients](../screenshots/experimental-display/text-hardware-candidate.png) und das [Optionsmenü](../screenshots/experimental-display/text-menu.png) zeigen das unveränderte Sprite-Logo mit den Adressen des bewährten Bitmap-Prototyps. Der Wechsel zwischen STANDARD und COMPACT änderte im VICE-Vergleich 947 Pixel des synthetischen Dialogausschnitts.

Die Logo-Sprite-Daten und Zeiger waren nach dem langen RX-Test unverändert; die VIC-Bank stand korrekt. Die zeitweise beschädigten Textmodus-Vorschaubilder entstanden durch die neue Speicheranordnung und den Zugriff auf das VIC-Zeichen-ROM. Mit den bewährten Sprite-Adressen und dem RAM-Font bei `$A000` zeigen die finalen Demo- und Menübilder wieder das intakte Logo. Die gelegentliche Bewegung auf Ultimate-Hardware ist damit **noch nicht als behoben** bestätigt. F6 bleibt der sichere Logo-Modus im Bildschirmbereich.

## Reproduzierbare lokale Prüfung

```powershell
python tools/build_display_prototype.py
python tools/test_text_display.py
python tools/test_display_prefs.py --text
```

Der Gesprächsbenchmark verwendet `src/display_receive_benchmark.c` mit `src/link_flow_test.c` als Testkopie. Das unveränderte produktive `src/link.c` wird beim normalen Build verwendet. Die Hardwareabnahme folgt dem [kurzen Testablauf](EXPERIMENTAL-C64-HARDWARE-TEST.md). Keine Veröffentlichung oder produktive Installation.
