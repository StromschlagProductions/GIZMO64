# Flexibles semantisches Gedächtnis (LAB 0.4.2)

Schema 6 speichert frei benannte, normalisierte `property_key`-Werte an Entitäten und Beziehungen. Ein `attribute` besitzt einen Wert; `related_to` verbindet benannte Entitäten. Quellen, Bestätigungsstatus, Duplikaterkennung, manuelle Korrekturen sowie Fiktions- und Löschschutz gelten auch für diese Einträge.

Vor der Schemaänderung erstellt LAB eine konsistente SQLite-Sicherung. Der Analyseversionswechsel reiht vorhandene Benutzernachrichten erneut ein. Gelöschte und korrigierte Fakten werden dabei nicht wiederhergestellt.

ARCHIVE zeigt Eigenschaften, Beziehungen mit Quellen-ID und Gespräche. Suche und Seitennavigation laden je 100 Einträge ohne starre Gesamtgrenze. Änderungen der Analyseverbindung aktualisieren die geöffnete Ansicht automatisch. `CORRECT PROPERTY` protokolliert den alten und den neuen Wert.

`qa_local.py --real-gemma` führt auch `flexible_memory_qa.py` aus: synthetische englische Gespräche über Haustier, Gegenstand, Person und Erlebnis, anschließend echte Antworten nach vollständigem Neustart. Die GUI-QA prüft automatische Archivaktualisierung, Suche und Navigation über 500 Einträge hinaus. Nach jeder Testphase wird Ollama vollständig beendet.
