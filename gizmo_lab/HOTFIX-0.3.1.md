# GIZMO LAB 0.3.1 – Analyse-Hotfix

## Befund

Der Windows-Status `done: 2, failed: 8, pending: 10, processing: 1` beweist, dass Analyseaufträge scheiterten, enthält aber **nicht deren gespeicherte Fehlertexte**. Ohne die lokale Datenbank oder `/analysis-errors` lässt sich die konkrete Ursache der acht Fehler nicht seriös bestimmen. Der Code von 0.3 hatte zwei nachgewiesene Schwachstellen: ein festes Analyse-Limit von 350 Ausgabetokens und ausschließlich einen strikten JSON-Schema-Aufruf ohne Kompatibilitäts-Fallback. Zusätzlich wurden ungültige Claims still verworfen; ein Auftrag konnte `done` sein, obwohl keine Entität entstand. LAB 0.3.1 macht API- und JSON-Fehler sichtbar und prüfbar.

Die Analyse fordert nun `think: false`, maximal acht kompakte Claims, 1024 Ausgabetokens und ein Schema mit erlaubten Entitätstypen, Prädikaten und Bereichen an. Bei HTTP 400/422 oder ungültigem beziehungsweise abgeschnittenem JSON erfolgt **höchstens ein** zweiter Versuch mit Ollamas `format: "json"` und 1536 Tokens. Ein weiterhin fehlerhafter Auftrag bleibt mit Fehlergrund `failed`; es werden keine halben JSON-Antworten in die Datenbank übernommen. `/analysis-errors` zeigt Job-ID, Quellnachricht-ID, Versuchszahl und Fehlergrund. `/retry-analysis` reiht fehlgeschlagene Aufträge nach der Reparatur erneut ein. Archiv, Erinnerungen und korrigierte/gelöschte Werte bleiben erhalten.

## Automatischer Windows-Test

`selftest.bat` doppelklicken. Der Selbsttest startet Ollama bei Bedarf, lädt `gemma4:12b`, legt eine **temporäre synthetische Datenbank** an und prüft Personen, Haustier, Familienbeziehung, Archiv, Wiederabruf sowie Erkennung ungültiger und abgeschnittener JSON-Ausgaben. Er erstellt einen kompakten Bericht unter `%LOCALAPPDATA%\GizmoLab\selftest-reports` und beendet Ollama samt Modellprozessen über die Studio-Safe-Routine. Er liest und ändert keine persönlichen Erinnerungen, keine lokale Konfiguration und keine private Persönlichkeitsdatei. Die fiktiven Testnamen sind Alex, Emma und Milo.

Das Paket enthält außerdem `diagnose_gemma.py` für einen einzelnen echten API-Test mit synthetischen Daten. Der opt-in Integrationstest `test_real_gemma.py` läuft mit `GIZMO_REAL_OLLAMA=1 python -m unittest test_real_gemma.py`, sofern Ollama und das Modell bereits lokal verfügbar sind. Er verwendet eine separate temporäre Datenbank.

Persönliche Daten liegen weiterhin außerhalb des ZIP unter `%LOCALAPPDATA%\GizmoLab`. `config.json`, `GIZMO_Awakening_V2_EN.txt`, `memory.sqlite3` und Backups werden beim Entpacken einer neuen Version **nicht überschrieben**. Das ZIP nur in einen Programmordner entpacken; den privaten Datenordner beibehalten.

## Prüfung und Grenzen

Die automatisierten Tests prüfen JSON-Fehler, Schema-Fallback, Wiederholung und bestehende Memory-Funktionen mit simulierten Antworten. Ein echter Gemma-Test kann nur auf einem Rechner mit Ollama und installiertem `gemma4:12b` erfolgen. Wenn `/analysis-errors` nach dem Update weiterhin Fehler meldet, den **Fehlergrund ohne persönliche Nachrichtentexte** weitergeben. Der Selbsttestbericht enthält ausschließlich synthetische Testdaten.
