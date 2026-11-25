# GIZMO Control Center 0.1 // LAB 0.4.1

MODEL LAB setzt den Fokus beim Öffnen und nach Antworten auf die Eingabe. ENTER sendet; während der Generierung kann die nächste Nachricht geschrieben und per ENTER eingereiht werden. Der Verlauf folgt neuen Textstücken nur, wenn er zuvor am Ende stand. SETTINGS zeigt Namen und vollständigen Pfad der tatsächlich geladenen Persönlichkeitsdatei und warnt ausdrücklich, wenn das englische Awakening-Profil fehlt. Profiltexte werden unverändert als erste Systemnachricht übergeben; Zeitkontext und lokale Gedächtnisregeln folgen als zusätzliche Systemnachrichten.

Die Windows-Anwendung startet mit `GIZMO.cmd` als grafische technische Schaltzentrale. Das dunkle Instrumentenlayout orientiert sich an der bereitgestellten Designvorlage. Angezeigte Zustände und Zahlen stammen aus der laufenden LAB-Engine, SQLite und `nvidia-smi`; nicht verbundene C64-/Story-Komponenten werden ausdrücklich markiert. START CORE lädt das vorhandene Modell, MODEL LAB bietet Streaming-Dialog und Modellwechsel, SETTINGS speichert Parameter und ein ausdrücklich gewähltes Profil lokal, ARCHIVE zeigt Erinnerungen, Entitäten, Beziehungen und Jobs. Löschungen und Korrekturen erfordern Bestätigung. SHUTDOWN und Fensterschließen führen die Studio-Safe-Abschaltung aus. `GIZMO-Terminal.cmd` hält den bisherigen Diagnosemodus bereit.

PySide6 6.12.0 wird ausschließlich in `.venv` installiert (`.venv/Scripts/python.exe -m pip install PySide6==6.12.0`). Der Versions-Updater übernimmt weiterhin nur freigegebene Laufzeitdateien. Die Qt-Oberfläche liegt aus Kompatibilitätsgründen im bestehenden `gizmo_lab.py`; Engine und Oberfläche bleiben als getrennte Klassen/Funktionen organisiert. Es gibt keinen zusätzlichen Modellaufruf für Statusanzeigen.

Lokale Windows-Dialogumgebung mit Ollama und SQLite/FTS5. Bestätigte persönliche Informationen und zusammengehörige Personen-/Haustierbeziehungen werden aktiv abgerufen. C64-Client und produktive Brücke bleiben unverändert. Keine Cloud-Modellaufrufe, zusätzlichen Modelle, Dienste oder Autostarts.

## Alltag und Updates

Die bestehende Installation mit `GIZMO.cmd` starten. Veröffentlichte LAB-Tags werden automatisch geprüft; offline startet die vorhandene Version. `GIZMO-Update.cmd` aktualisiert ausschließlich Programmdateien, ohne private Dateien zu öffnen. `GIZMO-Terminal.cmd` bietet `/quit` und den bisherigen Konsolenbetrieb. Kein manuelles ZIP-Entpacken oder BAT-Bearbeiten. [Installation, Sicherungen und lokale QA](LOCAL-DEVELOPMENT.md).

Profil, config.json und memory.sqlite3 bleiben am bisherigen Datenort (standardmäßig LOCALAPPDATA/GizmoLab). Das öffentliche personality.example.txt dient nur als Fallback. Das englische Testprofil ändert keine produktive Persönlichkeit. Vorhandene Konfigurationswerte bleiben erhalten; fehlende Schlüssel erhalten Laufzeit-Standardwerte.

## Active Memory

Eine Frage nach dem Studienfach der Schwester ruft sowohl die Schwesterbeziehung als auch das zugehörige Studienfach ab. Namen und persönliche Anker sind priorisiert. Lokale FTS5-Suche, lexikalische Hilfen für Englisch/Deutsch und bis zu zwei Graphschritte verbinden passende Angaben. Kein zusätzlicher Modellaufruf vor einer Antwort, kein Embedding-Modell. Die Graphstruktur und normalisierten Behauptungsschlüssel sind unabhängig von der Dialogsprache.

Nur aktive, belegte Beziehungen werden als Fakten eingeblendet. Unsichere, widersprüchliche und fiktionale Angaben bleiben unbestätigt. Gelöschte/korrigierte Quellen und widersprüchliche Dialogrunden werden nicht erneut als Wahrheit an Gemma gesendet; das Roharchiv bleibt vollständig erhalten. Eindeutige Pronomen werden anhand faktischer Benutzeraussagen aufgelöst; mehrdeutige Bezüge bleiben offen. Erinnerungen sind zitierte Daten, keine Anweisungen. GIZMO soll sie situationsgerecht statt als Dossier verwenden, fehlende Details nicht erfinden und unnötige Rückfragen vermeiden.

## Kontext und Analyse

Persönlichkeit, Zeitinformationen, Erinnerungen, vollständige Dialogrunden und Antwortreserve teilen sich ein konservatives Kontextbudget nach UTF-8-Bytegrenzen mit zusätzlicher Template-Reserve. num_ctx und num_predict werden tatsächlich an Ollama gesendet. working_messages: 20 ist keine starre Obergrenze mehr. history_token_budget begrenzt optional den Verlauf, memory_token_budget den Erinnerungsanteil. Zu große Persönlichkeit oder aktuelle Nachricht führen zu einer sichtbaren Meldung statt stillem Abschneiden. Alte Nachrichten bleiben in SQLite.

Nach Antworten analysiert dasselbe lokale Modell Benutzeraussagen im Hintergrund. Thinking ist aus; Schema, Typen und wörtliche Belege werden geprüft. Die Analyse streamt und kann bei neuer Eingabe unterbrochen werden. Teilantworten werden nicht gespeichert. Beim ersten Start von 0.3.2 wird eine bestehende Datenbank vor der Migration gesichert und das Benutzerarchiv einmal zur verbesserten Analyse eingereiht. Schema 5 ergänzt Quellen-, Such- und Normalisierungsmetadaten. Nachrichten, IDs, manuelle Entscheidungen und Sicherungen bleiben erhalten. Alte Angaben müssen nicht erneut erzählt werden.

`/reanalyze` verarbeitet auch erledigte Archivaufträge erneut. Identische Objekt-/Wertdarstellungen werden zusammengeführt; zusätzliche Quellen bleiben erhalten. Gelöschte und manuell überholte Angaben werden nicht automatisch wiederhergestellt. `/retry-analysis` reiht Fehler erneut ein. `/memory`, `/entities`, `/relations`, `/memstatus`, `/correct ID WERT`, `/delete ID`, `/approve-relation ID`, `/delete-relation ID`, `/backup DATEI.sqlite3` und `/export DATEI.json` bleiben verfügbar.

## Lokale Abnahme

Die grafische Abnahme öffnet eine eigens installierte Testkopie per `pythonw`, lädt Gemma, prüft echte Streaming- und Erinnerungsantworten sowie den Abbruch während einer Generierung. Der tatsächliche Fenster-Screenshot und ein JSON-Bericht bleiben unter `.local-test/qa`.

```powershell
.venv/Scripts/python.exe gizmo_lab/qa_local.py
.venv/Scripts/python.exe gizmo_lab/qa_local.py --real-gemma
```

Alternativ gizmo_lab/run-local-qa.cmd. Die reale QA umfasst deutsche Tests und englische End-to-End-Gespräche mit dem öffentlichen synthetischen Profil qa_personality.en.txt: tatsächliche Antworten nach 30 Runden, neuer Python-Prozess und leeres Dialogfenster, indirekte Bezüge, ältere Themen, Charaktergrenzen, Fakten/Fiktion, Archive, Löschschutz, Modellwechsel, Zeiten, VRAM und Studio-Safe-Abschaltung. Daten/Berichte liegen ausschließlich in einem neuen ignorierten .local-test/qa-Verzeichnis. Private Gespräche, Einstellungen und Profile werden nicht geöffnet. Für den Modellwechsel wird nur ein bereits installiertes qwen2.5:7b verwendet; fehlt es, meldet die QA einen Fehler statt es herunterzuladen.

## Grenzen

Extraktion und Wortwahl bleiben modellabhängig. Symbolische Graphsuche ersetzt keine umfassende semantische Suche; die lexikalischen Sprachhilfen decken Englisch und Deutsch ab. Kleine Budgets und mehrdeutige Quellen können Fakten zurückhalten. Lösch-/Korrekturschutz blendet konservativ ganze betroffene Dialogrunden aus, ohne das Roharchiv zu löschen. Charaktertests prüfen konkrete Eigenschaften, keine allgemeine Persönlichkeitstreue. Vektorsuche, automatische Episodenzusammenfassungen und umfassende Konsolidierung sind weiterhin nicht implementiert.
