# GIZMO LAB 0.3 – Intelligent Memory Core, Stufe 1

## Implementiert

Diese Stufe ergänzt GIZMO LAB 0.2 um modellgestützte Extraktion, Personen/Beziehungen und eine fortsetzbare Reanalyse. Der C64-Client und die produktive Brücke bleiben unverändert. Die Dialogantwort verwendet weiter `gemma4:12b` oder das lokal konfigurierte Modell. Der Analyseauftrag nutzt **dasselbe bereits geladene Modell**, `temperature: 0`, höchstens 350 Ausgabetokens und Ollamas JSON-Schema-Ausgabe. Er beginnt nach der sichtbaren Antwort. Bei einer neuen Benutzereingabe wird ein laufender Analyseaufruf abgebrochen und der Auftrag bleibt zur Wiederholung gespeichert. Es gibt kein zusätzlich dauerhaft geladenes Modell.

`analysis_jobs` speichert je Benutzernachricht höchstens einen Auftrag. `/reanalyze` reiht bisherige Benutzernachrichten ein; erledigte Aufträge bleiben erledigt. `/retry-analysis` setzt fehlgeschlagene Aufträge erneut auf `pending`. Aufträge mit Status `processing` werden nach Neustart wieder `pending`. `/memstatus` zeigt Schema-Version 3, Statuszahlen und letzte Analysedauer. `/entities` und `/relations` zeigen die erkannten Entitäten und Beziehungen samt Quellen. `/approve-relation ID` bestätigt einen offenen Bezug, `/delete-relation ID` löscht ihn logisch. Diese Eingriffe bleiben in `relation_events` erhalten. `/memory`, Korrektur, Löschung, Backup und Export aus 0.2 bleiben erhalten. Vor der Schema-Erweiterung erstellt LAB eine konsistente SQLite-Sicherung mit `.pre-v03-...bak` im privaten Datenordner.

Die Modellantwort muss ein begrenztes JSON-Schema erfüllen. Nur erlaubte Entitätstypen, Prädikate und Bereiche werden akzeptiert. Jede Aussage benötigt einen **wörtlichen Beleg aus der aktuellen Benutzernachricht**; Aussagen ohne solchen Beleg werden verworfen. Modellantworten dienen nie selbst als biografische Quelle. Hypothesen und Pronomenbezüge werden `pending`, fiktionale Aussagen `fictional`. Klare direkte Aussagen mit hoher Modellkonfidenz können aktiv werden. Das ist eine konservative Validierung, keine Garantie gegen alle Fehlinterpretationen. Die 0.2-Regeln für eindeutige Namens- und Interessensaussagen bleiben als schneller Pfad erhalten.

Entitäten und Beziehungen liegen in SQLite. Wiederholte gleiche Beziehungen werden über einen inhaltlichen Fingerabdruck zusammengeführt; `relation_sources` erhält alle zugehörigen Quellnachrichten. Neue widersprechende Angaben zu `lives_in` oder `works_as` werden offen gespeichert. Gelöschte oder überholte Quellen werden bei der Reanalyse konservativ übersprungen. Das unveränderte Roharchiv bleibt erhalten.

## Noch nicht implementiert

Die **hybride semantische Suche, automatische Episodenzusammenfassungen, umfassende Konsolidierung und eine tokenbudgetorientierte Dialogkompression** gehören zu späteren Stufen. Der Dialogabruf verwendet weiterhin FTS5 und ein konfigurierbares Näherungsbudget. Beziehungen werden in dieser Stufe diagnostisch gespeichert und nicht automatisch als bestätigte persönliche Fakten in den Dialogprompt eingefügt. Pronomen wie „She“ können in der Analyse einer bestehenden Entität zugeordnet werden, bleiben aber bis zur Prüfung offen. Es gibt noch keine automatische Freigabe fiktionalen Kanons.

## Embedding-Entscheidung vor Stufe 2

Ollamas lokale `/api/embed`-Schnittstelle ist eine passende spätere Anbindung ohne Cloud-Dienst. Kandidaten: `all-minilm` (klein, geringer Ressourcenbedarf, begrenztere semantische Qualität), `nomic-embed-text` (größer, gute englische Textsuche) und `mxbai-embed-large` (größerer Speicherbedarf). Diese Angaben sind eine technische Vorauswahl, **keine Messung auf der RTX 3060**. Bei 12 GB VRAM soll `gemma4:12b` Vorrang behalten. Vor einer Implementierung sind Qualität mit synthetischen Fragen, Ladezeit, VRAM-Auslastung und CPU-Betrieb mit Ollama lokal zu messen. Es wird jetzt kein Embedding-Modell automatisch installiert oder geladen. Bis dahin bleibt FTS5 aktiv. Die Datenbank kann später eine optionale Vektor-Spalte oder separate Embedding-Tabelle erhalten.

## Datenschutz und Tests

Alle Archive, Migrationssicherungen, Analyseaufträge und Debug-Ausgaben liegen im lokalen `%LOCALAPPDATA%\GizmoLab`. `--debug` kann private Inhalte enthalten. Automatisierte Tests verwenden ausschließlich fiktive Namen und simulierte Ollama-Antworten. Sie prüfen JSON-Validierung, Belege, Beziehungen über mehrere Nachrichten, offene Pronomenbezüge, Hypothesen/Fiktion, Reanalyse, Quellen, Widersprüche, Abbruch und Migration. Ob Gemma die Zusammenhänge im realen Gespräch zuverlässig extrahiert, muss auf dem Windows-PC geprüft werden.
