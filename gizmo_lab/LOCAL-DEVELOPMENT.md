# LAB 0.3.1 – lokaler Entwicklungs- und Produktivbetrieb

PC-seitige Entwicklung und reale Modelltests erfolgen lokal unter Windows. Der C64-Client und die produktive Brücke gehören nicht zu diesem Update.

## Alltag

Nach der einmaligen Installation `GIZMO.cmd` im Projektordner doppelklicken. Der Starter prüft veröffentlichte `lab-vX.Y.Z`-Tags, installiert bei Bedarf ausschließlich Programmdateien und startet LAB. Bei fehlender Internetverbindung startet die installierte Version. `/quit` beendet LAB und sämtliche Ollama-Prozesse. Es gibt keinen Dienst, Autostart oder automatischen Modelldownload.

`GIZMO-Update.cmd` aktualisiert ausschließlich den Code, ohne LAB oder Ollama zu starten. Während LAB läuft, verhindert eine Installationssperre Updates und einen zweiten produktiven Start. Vorher LAB mit `/quit` schließen. `GIZMO.cmd --offline` überspringt die Updateprüfung. Die bisherigen Codeversionen bleiben erhalten; die Aktivierung erfolgt über einen atomaren Versionszeiger. Ein fehlgeschlagenes Download- oder Validierungsverfahren ersetzt die funktionierende Version nicht. Keine automatischen Datenbank-Downgrades oder Rücksicherungen.

Die einmalige lokale Installation (Git-Pfad bei Bedarf anpassen):

```powershell
python gizmo_lab/deployment.py install --root .lab-production --git .local-tools/git/cmd/git.exe
```

Der Installer liest **keine** privaten Daten. Standard bleibt der vorhandene Windows-Datenort `%LOCALAPPDATA%\GizmoLab`. Falls bisher ein anderer Ort über `GIZMO_LAB_DATA` verwendet wurde, bei der Installation `--data-directory "D:\Eigener\Datenort"` angeben. Dieser Pfad wird lediglich hinterlegt. Der produktive Starter ignoriert bewusst ein geerbtes `GIZMO_LAB_DATA` aus einer Entwicklungsshell. Persönlichkeitsprofil, config.json und memory.sqlite3 werden vom Updater weder kopiert, geöffnet noch ersetzt. Das vorhandene private Awakening-Profil hat dieselbe Priorität wie bisher. Nur LAB selbst öffnet diese Dateien beim Gesprächsstart.

## Sicherung und Altaufträge

Beim ersten Öffnen einer bestehenden Datenbank mit einer neuen LAB-/Schemaversion legt LAB **vor Änderungen** eine konsistente SQLite-Sicherung mit Mikrosekunden-Zeitstempel im selben privaten Verzeichnis an (`memory.sqlite3.pre-v0.3.1-...bak`). Die Sicherung umfasst auch committed WAL-Daten; `integrity_check` muss erfolgreich sein. Bei einem Fehler wird der Start abgebrochen. Normale Gesprächseinträge benötigen keine vollständige Sicherung vor jeder einzelnen Nachricht. Sicherungen werden nicht automatisch gelöscht oder übertragen.

LAB 0.3.1 verwendet Schema 4 für Versions- und Migrationsmetadaten. Beim Upgrade werden bisher fehlgeschlagene Analyseaufträge genau einmal erneut auf `pending` gesetzt; erledigte Aufträge, Rohgespräche und manuelle Korrekturen bleiben erhalten. Die Marker und Auftragsänderungen werden gemeinsam committet. Der Analyzer verarbeitet die Warteschlange nach dem Start. Weitere Fehler bleiben sichtbar und lassen sich mit dem vorhandenen `/retry-analysis` erneut einreihen. `/reanalyze` und Löschschutz bleiben erhalten. Ein älterer Code darf eine neuere Schemaversion nicht öffnen.

## Lokale Qualitätssicherung

```powershell
.venv/Scripts/python.exe gizmo_lab/qa_local.py
.venv/Scripts/python.exe gizmo_lab/qa_local.py --real-gemma
```

Alternativ `gizmo_lab/run-local-qa.cmd` doppelklicken. Ein QA-Lauf legt immer einen neuen Ordner unter `.local-test/qa` an, erzwingt eigene Daten- und Temporärpfade und verwendet ausschließlich das neutrale Repository-Profil. Er öffnet keine privaten Erinnerungen oder Konfigurationen. Ohne Flag werden nur automatisierte Tests ausgeführt. Der reale Windows-Test startet die vorhandene Ollama-Installation, nutzt ausschließlich das bereits installierte `gemma4:12b` und beendet anschließend sämtliche Ollama-Prozesse. Kein Cloud-Fallback. Kein Modell wird heruntergeladen.

Geprüft werden echte Chatgenerierung, Schwester-/Hundbeziehungen, Pronomenauflösung mit offenem Status, deutsche Hypothesen und Fiktion, erneute Verarbeitung eines synthetischen Fehlauftrags sowie API- und Prozessabschluss. Zusätzlich wird eine eigene synthetische Produktivinstallation über den ausgelieferten Starter geöffnet und mit `/quit` geschlossen; Testprofil und Testkonfiguration müssen unverändert bleiben. Antworten und Messdaten bleiben lokal in ignorierten QA-Verzeichnissen. Tests sind keine Garantie für beliebige Modellformulierungen; ein Fehler stoppt die Freigabe. Diese QA soll außerhalb der Codex-Sandbox laufen, falls lokale API-/Socketverbindungen dort blockiert sind. Nicht parallel zu einer produktiven Unterhaltung ausführen: Studio-Safe beendet alle Ollama-Prozesse.

## Veröffentlichung

1. Unit-Tests und reale lokale Gemma-QA ausführen; Änderungen und `git diff --check` prüfen.
2. VERSION in version.py und Dokumentation aktualisieren. Bei neuer Analysekorrektur ANALYSIS_REVISION ändern; Schema nur bei tatsächlicher Strukturänderung erhöhen.
3. Nur geprüfte Quelldateien committen. Keine Profile, Datenbanken, Backups oder lokalen Berichte hinzufügen.
4. Entwicklungsbranch und den Tag `lab-vX.Y.Z` desselben geprüften Commits nach GitHub pushen. Nur solche Tags gelten als produktiv freigegeben. Nicht neu markieren oder nachträglich verändern.

Die existierende Cloud-C64-Pipeline wird durch reine LAB-Veröffentlichungen nicht als Entwicklungsumgebung genutzt. Modelltests benötigen den lokalen Studio-PC. Die alte ZIP-Paketierung bleibt optional; der produktive Updateprozess benötigt keine ZIP-Handarbeit.

## Fehlerkorrekturen 0.3.1

Die reale Gemma-Analyse verbrauchte ohne `think:false` das 350-Token-Limit für Thinking und lieferte leeren JSON-Inhalt. Der Extraktionsauftrag deaktiviert Thinking jetzt ausdrücklich. JSON-Schema und Prompt enthalten das tatsächlich erlaubte Vokabular; ungültige Beziehungstypen werden vermieden. Abgeschnittene Antworten erhalten eine klare Fehlermeldung. Deutsche Unsicherheits-, Fiktions- und Pronomenmarker werden konservativ behandelt. SQLite-Backupverbindungen und Testinstanzen werden unter Windows korrekt geschlossen. Keine neuen Memory-Core-Funktionen.
