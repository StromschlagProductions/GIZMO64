# Oberfläche und Zeichencodierung

Version 0.1.1 korrigiert den ersten Hardwarebefund. Die Zeichen im PRG waren lesbar zu machen, weil cc65 Großbuchstaben in Stringliteralen für das C64-Target als PETSCII `$C1` bis `$DA` speichert. Der erste Renderer behandelte diese Bytes wie ASCII. Das führte zu falschen oder invers wirkenden Bildschirmzeichen. Der aktuelle Renderer bildet PETSCII `$C1` bis `$DA` auf Bildschirmcodes `$01` bis `$1A` ab. Inversschrift wird ausschließlich für den Schriftzug im Header gesetzt. Tastatureingaben aus dem C64-KERNAL bleiben PETSCII. Netzwerkzeilen werden von ASCII nach PETSCII gewandelt, ausgehende Befehle zurück nach ASCII.

Die Tests prüfen die tatsächliche cc65-Assemblerausgabe und die fertige PRG auf PETSCII-Bytefolgen. Der Sendetest prüft das ASCII-Zeilenende `$0D`. Er deckt außerdem die Trennung von CR, LF und CRLF ab. `make test` führt die Hosttests aus; `make` prüft zusätzlich die fertige PRG.

## VIC-II

CIA2 `$DD02` setzt die beiden Bankbits als Ausgänge, `$DD00` wählt Bank 0. `$D011` aktiviert Textausgabe und löscht Bitmap- sowie Extended-Color-Modus. `$D016` wählt 40 Spalten und löscht Multicolor-Text. `$D018=$14` ordnet Bildschirm `$0400` und Zeichensatz `$1000` zu. Hintergrund und Rahmen sind schwarz. Die erste Zeile enthält den inversen Schriftzug, darunter stehen Systemkennung, dynamischer Linkstatus und Zieladresse. Zeile 4 trennt den Header vom Terminal. Nur Zeilen 5 bis 22 scrollen. Zeilen 23 und 24 bilden eine feststehende Fußzeile.

Die Sprite-Daten belegen `$3800` bis `$39FF`, deutlich oberhalb der aktuellen Programmsegmente. Zwei Sprites stehen nebeneinander bei X=280 und X=304, Y=50. Beide verwenden Priorität vor dem Text, einfarbigen Modus und normale Größe. Vier vollständige Frames werden vor dem Aktivieren erzeugt. Jede der 48 Spalten enthält einen verbundenen Abschnitt der Wellenform. Im Leerlauf wechseln die Frames langsamer, während der Kommunikation schneller.

Die Paletten verwenden C64-Grün, Cyan und Orange als Hauptfarben. Hellgrün, Hellblau und Gelb setzen Akzente. F1 schaltet die Farben um. Die vorhandene SID-Tastenrückmeldung bleibt aktiv.

## Emulatorprüfung

Die kompilierte PRG wurde in VICE 3.9 mit PAL-C64 gestartet. Der [Screenshot](../screenshots/vice-0.1.1.png) stammt aus dem VICE-Videopuffer. Text, zwei Sprites, feste Bildschirmbereiche und Offline-Diagnose waren sichtbar. VICE lief ohne emulierte Ultimate-ACIA; deshalb zeigt der Client `ACIA $DE00 NICHT VERFUEGBAR`. Der nächste Hardwaretest muss die reale Anzeige, Tastatureingabe und den Uplink bestätigen.
