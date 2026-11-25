# GIZMO LAB 0.3.1

Lokale Windows-Terminalumgebung für Modell- und Persönlichkeitstests. Der C64-Client und die produktive Brücke werden nicht verwendet oder verändert. Die neutrale Persönlichkeit in `personality.example.txt` entspricht dem 0.2.1-Prompt.

## Start

Python 3 und Ollama installieren. Das bevorzugte Modell **vorher manuell** mit `ollama pull gemma4:12b` laden. `start-gizmo-lab.bat` ausführen. LAB startet Ollama und lädt das Modell vor. Freie deutsche Texte werden gestreamt. `/model NAME` wechselt das Modell. `/quit` und Strg+C beenden LAB. ESC und Q brechen während Modellladen, Generierung oder Benchmark ab. Während normaler Texteingabe ist `Q` ein gewöhnliches Zeichen; ESC beendet die Eingabe.

Mit `--personality C:\Pfad\profil.txt` kann ein externes UTF-8-Profil für einen gesamten Testlauf gewählt werden. Der Benchmark protokolliert dessen SHA-256-Prüfsumme, sodass alle Modellvarianten nachweisbar dasselbe Profil verwenden. Das private Profil `GIZMO_Awakening_V2_EN.txt` kann in `%LOCALAPPDATA%\GizmoLab` liegen oder mit `--personality C:\Pfad\GIZMO_Awakening_V2_EN.txt` gewählt werden. Es wird nicht mitgeliefert. Ohne private Datei dient das neutrale Beispielprofil als Fallback. Persönliche Dateien liegen unter `%LOCALAPPDATA%\GizmoLab` (oder `GIZMO_LAB_DATA`). `config.example.json` dort als `config.json` und `personality.example.txt` als `personality.txt` kopieren. Nur diese lokalen Kopien bearbeiten. Berichte landen unter `reports`; sie werden nicht im öffentlichen Repository abgelegt. `keep_alive: -1` hält ein Modell geladen; beim Modellwechsel wird das alte Modell mit `keep_alive: 0` freigegeben. Keine Modelle werden automatisch heruntergeladen.

## Benchmark

`start-gizmo-lab.bat --benchmark` nutzt `questions.json`. Für einen Vergleich das mitgelieferte Referenzmodell über `--variants variants.example.json` prüfen. Für andere Varianten eine eigene JSON-Datei über `--variants C:\Pfad\variants.json` angeben. Format: `[{"model":"modell-a","start":"cold","options":{"temperature":0.5}},{"model":"modell-b","start":"warm","options":{"temperature":0.8}}]`. JSON und Markdown enthalten Modell, Parameter, Zeiten, Tokenwerte, Ollama-Tempo, Abbruchgrund und vollständige Antwort. `start: cold` entlädt das Modell unmittelbar vor der ersten Testfrage. `start: warm` lädt es vor der Frage; die Vorladezeit wird getrennt als `preload_s` erfasst. Nachfolgende Fragen derselben Variante sind Warmstarts. Der Bericht enthält außerdem `load_duration` aus Ollamas Metriken. Kreativität wird nicht durch erfundene Punktwerte bewertet.

Ollama ignoriert je nach Modell oder Version einige Optionen. API-Fehler erscheinen im Ergebnis als Abbruchgrund. Reale Ollama- und Windows-Studio-Tests wurden hier nicht durchgeführt; insbesondere Q/ESC während Modellladen und Generierung, GPU-Freigabe und Prozessbaum-Abschaltung brauchen einen Test am Studio-PC.

## Geplante Memory-Core-Schnittstellen

- `IdentityCore.load() -> system_prompt`: editierbares Profil.
- `WorkingMemory.append(role, text)` und `recent(limit)`: aktueller Dialog.
- `SemanticMemory.add(fact, source)` und `search(query)`: dauerhafte Fakten in SQLite mit FTS5.
- `EpisodicMemory.add(event, timestamp)` und `search(query)`: datierte Ereignisse.
- `NarrativeMemory.summarize(events)`: verdichtete Erzählstränge.
- `MemoryRetrieval.retrieve(query, budget)`: kombinierte FTS5-Suche, optional lokale semantische Suche.
- `MemoryConsolidation.run()`: kontrolliertes Verdichten mit Herkunftsnachweis.
- `ModelAdapter.chat(messages, options)`: austauschbares Modellinterface.

Diese Schnittstellen sind Entwurf; es wird noch kein Memory Core implementiert. SQLite und FTS5 reichen als geplante Basis ohne zusätzliche Infrastruktur.

## Gedächtnis und Prüfung

Das lokale SQLite/FTS5-Gedächtnis archiviert Gespräche und ruft bestätigte Fakten ab. `/memory`, `/correct ID WERT`, `/delete ID`, `/backup DATEI.sqlite3` und `/export DATEI.json` verwalten es. `--debug` zeigt Abruf, gesendete Nachrichten und Zeitmessungen; die Ausgabe enthält private Daten. [Architektur und Grenzen](MEMORY.md) sowie [manueller Windows-Testplan](WINDOWS-TESTPLAN.md) gehören zum Paket. Standard sind `num_ctx: 8192`, `working_messages: 20` und `memory_token_budget: 300`.

## Intelligente Analyse 0.3

Nach sichtbaren Antworten analysiert LAB Benutzernachrichten mit demselben lokalen Ollama-Modell. `/entities`, `/relations`, `/memstatus`, `/reanalyze` und `/retry-analysis` zeigen Entitäten, Beziehungen und die persistente Auftragswarteschlange. [Architektur, Validierung und Grenzen](ARCHITEKTUR-0.3.md) sowie der [Windows-Testplan 0.3](WINDOWS-TESTPLAN-0.3.md) erläutern die erste Entwicklungsstufe. Hypothesen, fiktionale Aussagen und Pronomenbezüge werden konservativ gekennzeichnet.

## Analyse-Hotfix und Selbsttest

`/analysis-errors` zeigt fehlgeschlagene Aufträge und Gründe; `/retry-analysis` verarbeitet sie erneut. `selftest.bat` startet Ollama und Gemma, prüft automatisch mit einer temporären synthetischen Datenbank und beendet Ollama anschließend. [Hotfix-Anleitung](HOTFIX-0.3.1.md). Das ZIP enthält keine private Konfiguration, Persönlichkeitsdatei oder Datenbank; diese bleiben im lokalen LAB-Datenordner erhalten.
