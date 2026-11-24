# Windows-Build

1. cc65 aus den offiziellen [cc65-Releases](https://github.com/cc65/cc65/releases) herunterladen und entpacken.
2. Das `bin`-Verzeichnis von cc65 zum Windows-`PATH` hinzufügen. In einer neuen Konsole mit `cl65 --version` prüfen.
3. MSYS2 mit `make` und GCC installieren oder MinGW `mingw32-make` verwenden.
4. Im Repository `make` beziehungsweise `mingw32-make` ausführen. Die Datei `GIZMO64.PRG` entsteht im Hauptverzeichnis.
5. Mit `make test` beziehungsweise `mingw32-make test` die Hosttests ausführen.

Die Builddateien im Verzeichnis `build/` und das PRG sind generiert und werden von Git ignoriert. Die GitHub Action kann ohne lokale Windows-Werkzeugkette ein PRG erzeugen.
