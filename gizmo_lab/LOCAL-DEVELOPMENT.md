# GIZMO Control Center 0.1 – lokaler Entwicklungs- und Produktivbetrieb

## C64-Uplink 0.7.0

04A integriert das unveränderte C64-PRG 0.2.2 über den ACK-TCP-Transport in die einzige LAB-Engine. In SETTINGS den Uplink einmal aktivieren; START CORE startet dann Modell und Listener gemeinsam. COMMODORE UPLINK zeigt `LISTENING`, `CONNECTED`, `DISCONNECTED` oder `ERROR` mit lokaler Adresse und Port. SHUTDOWN beendet Listener, laufende Chats und Ollama. Das Profil und die SQLite-Datenbank sind für GUI und C64 identisch; Nachrichten tragen die Herkunft `gui`, `c64` oder `terminal`. Alte `memory.json`-Dateien werden nicht automatisch eingelesen.

`test_uplink.py` und `uplink_qa.py` prüfen ACK, fehlende und verspätete ACKs, Fragmentierung, Portkonflikt, lange Streams, Wiederverbindungen, gemeinsame Sitzung und echte Gemma-Antworten mit synthetischen Daten. Die reale QA ist in `qa_local.py --real-gemma` enthalten und verlangt lokale TCP-Sockets. Der Ultimate-Hardwaretest ist in `docs/04A-C64-HARDWARE-ABNAHME.md` beschrieben und bleibt bis zur Durchführung offen. Ein C64-C-Compiler gehört nicht zur lokalen LAB-Umgebung; das unveränderte PRG 0.2.2 wird für den Test aus dem vorhandenen ZIP verwendet.

## Episodic Memory 0.6.0

Episoden werden inkrementell aus Originalgesprächen gebildet und im ARCHIVE mit Domäne, Themen, ausdrücklich genannter Bedeutung und Quellen angezeigt. Reale, hypothetische und fiktionale Episoden bleiben getrennt. Die vollständige synthetische Gemma-QA prüft Abruf nach Neustart, einen nicht genannten Detailwert, Korrektur/Löschung und Studio-Safe-Abschaltung. Das Repositorydokument `EPISODIC-MEMORY.md` enthält Architektur und Messwerte.

**Offener Prüfpunkt:** Die Messung mit 50.000 synthetischen Nachrichten umfasste den vollständigen Episodenaufbau, aber nur zwei echte Nachrichtenvektoren. Aufbauzeit, RAM-Bedarf und Suchlatenz einer vollständig mit 50.000 oder mehr Embeddings indizierten Sammlung sind noch gesondert zu prüfen.

PC-seitige Entwicklung und reale Modelltests erfolgen lokal unter Windows. Der C64-Client und die produktive Brücke gehören nicht zu diesem Update.

## Alltag

Nach der einmaligen Installation `GIZMO.cmd` im Projektordner doppelklicken. Der Starter prüft veröffentlichte `lab-vX.Y.Z`-Tags, installiert bei Bedarf ausschließlich Programmdateien und startet die grafische Oberfläche ohne dauerhaftes Konsolenfenster. Bei fehlender Internetverbindung startet die installierte Version. SHUTDOWN oder Fensterschließen beendet LAB und sämtliche Ollama-Prozesse. `GIZMO-Terminal.cmd` erhält den bisherigen Terminalmodus; dort beendet `/quit` LAB. Es gibt keinen Dienst, Autostart oder automatischen Modelldownload.

PySide6 liegt projektlokal in `.venv` und wird mit `.venv/Scripts/python.exe -m pip install PySide6==6.12.0` installiert. Beim Upgrade auf Control Center 0.1 wird der grafische Starter erneuert. Der 0.3.2-Updater kann die neue Version mit seinem bisherigen Dateikatalog übernehmen, weil die Qt-Oberfläche in einer bereits ausgelieferten Laufzeitdatei liegt. Der Updater öffnet keine persönlichen Daten.

`GIZMO-Update.cmd` aktualisiert ausschließlich den Code, ohne LAB oder Ollama zu starten. Während LAB läuft, verhindert eine Installationssperre Updates und einen zweiten produktiven Start. Vorher LAB mit `/quit` schließen. `GIZMO.cmd --offline` überspringt die Updateprüfung. Die bisherigen Codeversionen bleiben erhalten; die Aktivierung erfolgt über einen atomaren Versionszeiger. Ein fehlgeschlagenes Download- oder Validierungsverfahren ersetzt die funktionierende Version nicht. Keine automatischen Datenbank-Downgrades oder Rücksicherungen.

Ab LAB 0.9.2 gehört die Versionsanzeige zur Release-Abnahme: Die zwei Kennungen im Control Center müssen die `VERSION` der gestarteten Engine anzeigen. SETTINGS zeigt im Servicebereich das konfigurierte beziehungsweise aktive Modell und den kurzen Commit des tatsächlich gestarteten Release-Verzeichnisses. Bei jedem künftigen LAB-Tag sind Versionsdatei, Tag und Installationszeiger sowie Anzeige nach Update und Rollback mit einer synthetischen Installation zu prüfen. Ältere Releases vor 0.9.2 behalten bei einem Rollback ihre damalige statische Beschriftung.

LAB 0.9.3 ergänzt in SETTINGS die Profilwahl `V3 + situational examples` (Standard), `V3 without dynamic examples`, `V2 original` und den bestehenden eigenen Dateipfad. V3 und die Character Library 1.0 sind Release-Dateien; V2 bleibt ausschließlich am privaten Datenort. Die Auswahl wird in der privaten Konfiguration gespeichert und nach Updates wieder geladen. Die Beispiele sind auf zwei pro normaler Eingabe begrenzt, werden ohne Modellaufruf bestimmt und sind keine Fakten oder Story-Ereignisse. Der Servicebereich zeigt zusätzlich LAB-Version und tatsächlich gewähltes Profil. Ein Wechsel schreibt keine Profildatei um.

Die einmalige lokale Installation (Git-Pfad bei Bedarf anpassen):

```powershell
python gizmo_lab/deployment.py install --root .lab-production --git .local-tools/git/cmd/git.exe
```

Der Installer liest **keine** privaten Daten. Standard bleibt der vorhandene Windows-Datenort `%LOCALAPPDATA%\GizmoLab`. Falls bisher ein anderer Ort über `GIZMO_LAB_DATA` verwendet wurde, bei der Installation `--data-directory "D:\Eigener\Datenort"` angeben. Dieser Pfad wird lediglich hinterlegt. Der produktive Starter ignoriert bewusst ein geerbtes `GIZMO_LAB_DATA` aus einer Entwicklungsshell. Persönlichkeitsprofil, config.json und memory.sqlite3 werden vom Updater weder kopiert, geöffnet noch ersetzt. Das vorhandene private Awakening-Profil hat dieselbe Priorität wie bisher. Nur LAB selbst öffnet diese Dateien beim Gesprächsstart.

## Sicherung und Altaufträge

Beim ersten Öffnen einer bestehenden Datenbank mit einer neuen LAB-/Schemaversion legt LAB **vor Änderungen** eine konsistente SQLite-Sicherung mit Mikrosekunden-Zeitstempel im selben privaten Verzeichnis an (`memory.sqlite3.pre-v0.3.2-...bak`). Die Sicherung umfasst auch committed WAL-Daten; `integrity_check` muss erfolgreich sein. Bei einem Fehler wird der Start abgebrochen. Normale Gesprächseinträge benötigen keine vollständige Sicherung vor jeder einzelnen Nachricht. Sicherungen werden nicht automatisch gelöscht oder übertragen.

LAB 0.3.2 verwendet Schema 5 mit Such-, Quellen- und Normalisierungsmetadaten. Beim Upgrade wird das Benutzerarchiv einmal für die verbesserte Analyse eingereiht. Rohgespräche und manuelle Entscheidungen bleiben erhalten. Marker und Auftragsänderungen werden gemeinsam committet. Der Analyzer verarbeitet die Warteschlange nach dem Start. `/retry-analysis` wiederholt Fehler, `/reanalyze` auch bereits erledigte Aufträge. Ein älterer Code darf eine neuere Schemaversion nicht öffnen.

## Lokale Qualitätssicherung

```powershell
.venv/Scripts/python.exe gizmo_lab/qa_local.py
.venv/Scripts/python.exe gizmo_lab/qa_local.py --real-gemma
```

Alternativ `gizmo_lab/run-local-qa.cmd` doppelklicken. Ein QA-Lauf legt immer einen neuen Ordner unter `.local-test/qa` an, erzwingt eigene Daten- und Temporärpfade und verwendet ausschließlich synthetische Repository-Profile. Er öffnet keine privaten Erinnerungen oder Konfigurationen. Ohne Flag werden nur automatisierte Tests ausgeführt. Der reale Windows-Test startet die vorhandene Ollama-Installation, nutzt das bereits installierte `gemma4:12b` und für den Modellwechsel nur ein ebenfalls bereits vorhandenes Modell. Anschließend beendet er sämtliche Ollama-Prozesse. Kein Cloud-Fallback. Kein Modell wird heruntergeladen.

Geprüft werden echte Chatgenerierung, Schwester-/Hundbeziehungen, Pronomenauflösung mit offenem Status, deutsche Hypothesen und Fiktion, erneute Verarbeitung eines synthetischen Fehlauftrags sowie API- und Prozessabschluss. Zusätzlich wird eine eigene synthetische Produktivinstallation über den ausgelieferten Starter geöffnet und mit `/quit` geschlossen; Testprofil und Testkonfiguration müssen unverändert bleiben. Antworten und Messdaten bleiben lokal in ignorierten QA-Verzeichnissen. Tests sind keine Garantie für beliebige Modellformulierungen; ein Fehler stoppt die Freigabe. Diese QA soll außerhalb der Codex-Sandbox laufen, falls lokale API-/Socketverbindungen dort blockiert sind. Nicht parallel zu einer produktiven Unterhaltung ausführen: Studio-Safe beendet alle Ollama-Prozesse.

## Veröffentlichung

Die reale Qt-QA startet die Oberfläche mit synthetischem Datenordner, lädt Gemma, misst Streaming und GUI-Reaktionsfähigkeit, verarbeitet eine synthetische Erinnerung, bricht eine laufende Generierung kontrolliert ab und prüft danach, dass kein Ollama-Prozess verbleibt. Der Screenshot und das JSON-Protokoll bleiben unter `.local-test/qa/.../control-center/` und werden nicht veröffentlicht.

1. Unit-Tests und reale lokale Gemma-QA ausführen; Änderungen und `git diff --check` prüfen.
2. VERSION in version.py und Dokumentation aktualisieren. Bei neuer Analysekorrektur ANALYSIS_REVISION ändern; Schema nur bei tatsächlicher Strukturänderung erhöhen.
3. Nur geprüfte Quelldateien committen. Keine Profile, Datenbanken, Backups oder lokalen Berichte hinzufügen.
4. Entwicklungsbranch und den Tag `lab-vX.Y.Z` desselben geprüften Commits nach GitHub pushen. Nur solche Tags gelten als produktiv freigegeben. Nicht neu markieren oder nachträglich verändern.

Die existierende Cloud-C64-Pipeline wird durch reine LAB-Veröffentlichungen nicht als Entwicklungsumgebung genutzt. Modelltests benötigen den lokalen Studio-PC. Die alte ZIP-Paketierung bleibt optional; der produktive Updateprozess benötigt keine ZIP-Handarbeit.

## Fehlerkorrekturen 0.3.1

Die reale Gemma-Analyse verbrauchte ohne `think:false` das 350-Token-Limit für Thinking und lieferte leeren JSON-Inhalt. Der Extraktionsauftrag deaktiviert Thinking jetzt ausdrücklich. JSON-Schema und Prompt enthalten das tatsächlich erlaubte Vokabular; ungültige Beziehungstypen werden vermieden. Abgeschnittene Antworten erhalten eine klare Fehlermeldung. Deutsche Unsicherheits-, Fiktions- und Pronomenmarker werden konservativ behandelt. SQLite-Backupverbindungen und Testinstanzen werden unter Windows korrekt geschlossen. Keine neuen Memory-Core-Funktionen.

## Active-Memory-Abnahme 0.3.2

Die neue Laufzeit passt in den festen Programmdatei-Katalog des 0.3.1-Updaters. Kein manuelles Bootstrap-Update ist nötig; ein Regressionstest importiert die Laufzeit ausschließlich aus diesem alten Dateikatalog.

active_memory_qa.py prüft in getrennten Prozessen 30 Gesprächsrunden, tatsächliche englische Antworten, Neustart mit leerem Dialog, einen bereits installierten Modellwechsel und ein synthetisches Altarchiv. qa_personality.en.txt ist ein öffentliches englisches QA-Profil im Stil der neutralen GIZMO-Persönlichkeit, keine Kopie eines privaten Profils. Die bisherigen deutschen Tests und eine deutsche Gedächtnisfrage mit leerem Dialog bleiben erhalten. Faktenprüfungen akzeptieren inhaltlich richtige Übersetzungen. Konkrete Charaktertests schließen Standardfloskeln, unangebrachte Gedächtnisaufzählungen, unnötige Rückfragen und erfundene Offline-Aktivität aus. Antworten und Profilprüfsummen bleiben lokal nachvollziehbar.

Wichtige Einstellungen: num_ctx (8192), num_predict (768), memory_token_budget (900), history_token_budget (null = adaptiv). Vorhandene private Werte bleiben erhalten; fehlende Schlüssel erhalten Laufzeit-Standardwerte. Konfigurationsdateien werden nicht umgeschrieben. working_messages ist keine starre Obergrenze mehr. Das UTF-8-Budget ist konservativ und reserviert zusätzlich Antwort-/Template-Platz. Tatsächliche Ollama-Tokenzahlen werden in der QA protokolliert. Grenzen und Abrufverhalten sind in README.md beschrieben.
