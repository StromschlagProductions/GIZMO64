# GIZMO LAB 0.1

Lokale Windows-Terminalumgebung für Modell- und Persönlichkeitstests. Der C64-Client und die produktive Brücke werden nicht verwendet oder verändert. Die neutrale Persönlichkeit in `personality.example.txt` entspricht dem 0.2.1-Prompt.

## Start

Python 3 und Ollama installieren. Das gewünschte Modell **vorher manuell** mit `ollama pull richardyoung/qwen2.5-7b-instruct-abliterated:latest` laden. `start-gizmo-lab.bat` ausführen. LAB startet Ollama und lädt das Modell vor. Freie deutsche Texte werden gestreamt. `/model NAME` wechselt das Modell, `/quit`, ESC, Q und Strg+C beenden LAB. ESC/Q werden als globale Konsolentasten erkannt und können daher beim Tippen einer Eingabe zum Beenden führen.

Persönliche Dateien liegen unter `%LOCALAPPDATA%\GizmoLab` (oder `GIZMO_LAB_DATA`). `config.example.json` dort als `config.json` und `personality.example.txt` als `personality.txt` kopieren. Nur diese lokalen Kopien bearbeiten. Berichte landen unter `reports`; sie werden nicht im öffentlichen Repository abgelegt. `keep_alive: -1` hält ein Modell geladen; beim Modellwechsel wird das alte Modell mit `keep_alive: 0` freigegeben. Keine Modelle werden automatisch heruntergeladen.

## Benchmark

`start-gizmo-lab.bat --benchmark` nutzt `questions.json`. Für mehrere Modelle `--variants C:\Pfad\variants.json` angeben. Format: `[{"model":"modell-a","options":{"temperature":0.5}},{"model":"modell-b","options":{"temperature":0.8}}]`. JSON und Markdown enthalten Modell, Parameter, Zeiten, Tokenwerte, Ollama-Tempo, Abbruchgrund und vollständige Antwort. Die `cold_model_start`-Kennzeichnung bedeutet einen Modellwechsel vor dem Test; LAB lädt das Modell vor der ersten Frage. Für einen echten Kaltstart muss die getrennte Vorladezeit zusätzlich gemessen werden. Kreativität wird nicht durch erfundene Punktwerte bewertet.

Ollama ignoriert je nach Modell oder Version einige Optionen. API-Fehler erscheinen im Ergebnis als Abbruchgrund. Reale Ollama- und Windows-Studio-Tests wurden hier nicht durchgeführt; insbesondere ESC/Q während einer laufenden Eingabe, GPU-Freigabe und Prozessbaum-Abschaltung brauchen einen Test am Studio-PC.

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
