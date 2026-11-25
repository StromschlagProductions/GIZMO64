# GIZMO LAB 0.2 – Memory Core Foundation

## Befund zum vergessenen Namen

LAB 0.1 erzeugte für jede Anfrage einen Systemprompt und höchstens die letzten **20 Nachrichten** (`self.context[-20:]`). Eine Runde enthält Benutzer- und Assistentennachricht; nach ungefähr zehn weiteren Runden war eine frühe Namensnennung deshalb nicht mehr in den an Ollama übergebenen Nachrichten. Der Test nach etwa 15 Runden passt zu diesem deterministischen Codepfad. Zusätzlich war `num_ctx` auf 4096 eingestellt: Bei langen Profilen und Antworten konnte Ollama ältere Teile innerhalb dieses Fensters verdrängen. Ohne lokale Ollama-Messung lässt sich nicht belegen, ob die 4096-Token-Grenze im konkreten Windows-Test zusätzlich erreicht wurde. Das nachgewiesene Problem ist die 20-Nachrichten-Grenze; 8192 Tokens sind jetzt der konfigurierbare Ausgangswert.

## Architektur

Alle privaten Daten liegen standardmäßig unter `%LOCALAPPDATA%\GizmoLab` in `memory.sqlite3` mit SQLite-WAL und FTS5. Gesprächs-ID, Rolle, Zeitstempel und Text jeder Nachricht werden archiviert. LAB setzt die letzte Gesprächs-ID nach Neustart fort. Das Modell kann gewechselt werden, ohne Datenbank oder Profil zu ändern. Nur die letzten `working_messages` (Standard 20) gehen als laufender Dialog an Ollama; ältere Daten bleiben vollständig in SQLite. Die Systemnachrichten enthalten aktuelle UTC-Zeit, Sitzungsbeginn, Zeitpunkt der letzten Nachricht vor Sitzungsbeginn und die vergangene Zeit. Es werden keine Aktivitäten während einer ausgeschalteten Sitzung behauptet.

Die Tabelle `memories` trennt `identity`, `personal`, `episodic`, `semantic`, `narrative` und `temporal`. In 0.2 ist nur die konservative Extraktion persönlicher Selbstaussagen automatisiert. Nachrichten bilden das episodische Roharchiv. Narrative und andere Bereiche sind für eine spätere Story Engine vorbereitet, ohne Fiktion als bestätigte persönliche Tatsache abzurufen. Eine spätere semantische Suche kann neben FTS5 ergänzt werden; Embeddings werden jetzt nicht erzeugt.

Erkannte Aussagen wie „My name is Alex“, „I like astronomy“ oder deutsche Entsprechungen werden **nur aus Benutzernachrichten** gespeichert, mit Quellnachricht und Zeitstempel. Antworten des Modells sind keine bestätigten persönlichen Fakten. Widerspricht ein neuer Wert einem aktiven Fakt, entsteht ein `pending`-Eintrag; der alte bleibt aktiv. `/memory` zeigt aktive und offene Einträge, `/correct ID WERT` bestätigt oder korrigiert, `/delete ID` löscht logisch. Korrekturen und Löschungen werden in `memory_events` protokolliert. Diese regelbasierte Extraktion erkennt noch keine impliziten Namen, Personenbeziehungen oder alle freien Formulierungen. Automatische Erinnerungen an erfundene Ereignisse werden nicht angelegt.

Vor einer Antwort werden wichtige bestätigte Fakten und thematisch passende FTS5-Treffer ausgewählt. `memory_token_budget` (Standard 300) begrenzt die Auswahl anhand einer konservativen Zeichenzahl-Näherung; das ist keine exakte Tokenisierung. `--debug` zeigt die tatsächlich gesendeten Nachrichten, ausgewählten Erinnerungen, Kontextgröße in Zeichen und Laufzeiten für Abruf und Extraktion. Diese Ausgabe enthält private Inhalte und gehört nicht in öffentliche Logs.

`/backup DATEI.sqlite3` erzeugt eine konsistente SQLite-Kopie. `/export DATEI.json` exportiert Gespräche, Erinnerungen und Änderungsereignisse. Beide Befehle schreiben in das lokale Datenverzeichnis. Backups und Exporte sind privat und dürfen nicht in GitHub hochgeladen werden.

## Grenzen und Tests

Automatisierte Tests mit simulierter Ollama-API prüfen Name nach 30 Runden und Neustart, Herkunft, FTS-Abruf, Widerspruch, Korrektur, Löschung, Modellwechsel, Export und Backup. Die Tests beweisen, welche Nachrichten und Erinnerungen Ollama **erhält**. Ob `gemma4:12b` die Fakten sprachlich richtig verwendet, muss unter Windows mit dem realen Modell geprüft werden. Bei 8192 Kontexttokens auf einer RTX 3060 mit 12 GB VRAM können Ladezeit und Speicherbedarf steigen; bei Engpässen `num_ctx` und `num_predict` lokal reduzieren und `ollama ps` beobachten.
