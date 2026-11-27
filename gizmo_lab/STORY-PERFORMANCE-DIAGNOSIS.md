# LAB 0.8.1 – lokale Story-Latenzdiagnose

Stand: 27. November 2026. Ausschließlich synthetische Profile, Gesprächsdaten und Story-Welten. Das produktive Profil und die private Gedächtnisdatenbank wurden nicht geöffnet. Die produktive Versionsdatei meldete 0.8.1 und Commit `3b5e49db63adfca0408a768baa6f18fb42a189ee`.

## Reproduktion und Messung

`story_latency_qa.py` misst den GUI-Aufrufpfad `Lab.chat(..., origin='gui')` mit echtem lokalem `gemma4:12b`. Die angegebene Zeit bis zum ersten sichtbaren Text ist die erste Übergabe an den GUI-Streaming-Callback; Qt-Zeichnung und Monitorlatenz sind nicht enthalten. Ollama-Metriken trennen Modellladen, Prompt-Auswertung und Generierung. Der Test variiert ein rein synthetisches Profil und die Hintergrundanalyse. Er schreibt ausschließlich numerische Metriken in `.local-test`.

| Eingabe/Pfad | Erster Callback | Gesamt | Modellladen | Kontext |
| --- | ---: | ---: | ---: | ---: |
| Gewöhnliche Frage nach Start | 8,30 s | 9,18 s | 4,61 s | 8192 |
| Story-Frage „What do you see?“ | 3,56 s | 3,97 s | 0,00 s | 6144 |
| „Tell me what you see“ vor Fix | 10,55 s | 10,55 s | 0,00 s | 6144 |
| Story-Frage mit größerem synthetischen Profil | 8,26 s | 8,48 s | 4,62 s | 8192 |
| Vollständig warmer Minimalprompt | 2,13 s bis Token 1 | 2,26 s | 0,005 s | 6144 |

Ein zweiter Lauf ohne Hintergrundanalyse ergab nahezu dieselben Werte: 8,02 s, 3,38 s, 11,02 s und 8,49 s bis zum ersten Callback. Die Hintergrundanalyse war hier nicht der dominante Engpass. Die normale Kontextaufbereitung einschließlich Speicherabruf dauerte rund 1,02 s; im Story-Pfad lag sie unter 1 ms. Prompt-Auswertung lag meist bei 0,6–1,3 s. Für kurze Dialogantworten meldete Ollama rund 0,7–1,1 s Generierung. Der Director brauchte für die gemessene Handlung etwa 6,47 s; anschließend folgte ein zweiter Dialogaufruf von rund 4,08 s. Die vollständig gepufferte Handlungsantwort erschien daher erst nach beiden Aufrufen.

Die Vorladung nutzt Ollamas Standardfenster von 4096 Tokens; der normale Dialog nutzt 8192. Story und Director nutzen 6144, bei größerem Profil weicht der Dialog auf 8192 aus. Jeder Wechsel auf eine andere Kontextgröße verursachte im Test etwa 4,6–4,9 s erneutes Laden. Ollama meldete für den aktiven Runner `size_vram == size`; `nvidia-smi` zeigte nach Anfragen rund 11.200 MiB gesamte GPU-Belegung bei 12.288 MiB. Eine wesentliche CPU-Auslagerung war in diesen Läufen nicht erkennbar. Die API-Werte zur Runnergröße sind kleiner als die gesamte GPU-Belegung und sollten nicht als vollständige Modellbelegung gelesen werden.

## Nachgewiesener Routingfehler

`StoryDirector.intent()` behandelte „Tell me what you see“ als Handlung und rief Director plus Dialogmodell auf. Der lokale Fix behandelt „Tell/Show me/us …“ als reine Frage nach verfügbaren Beobachtungen. „Tell the witness …“ bleibt eine Handlung. Ein echter Gemma-Test des korrigierten Satzes benötigte einen Modellaufruf, 3,43 s bis zum ersten Callback und 3,88 s insgesamt. Der Weltzustand blieb unverändert. Synthetische Regressionstests decken englische Varianten und die Unterscheidung zur Handlung ab.

## Architekturentscheidung

Ein vollständig warmer Minimalprompt mit Gemma 4 12B erreicht ungefähr zwei Sekunden bis zum ersten Token. Dieser Wert gilt nicht für die tatsächliche GIZMO-Persönlichkeit, das Gedächtnis oder eine Story-Handlung. Mit dem aktuellen zweistufigen, vor Ausgabe validierten Handlungspfad ist ein sinnvoller erster Text in 1–3 s auf dieser Hardware nicht erreichbar: Bereits der Director-Aufruf allein benötigte rund 6–7 s. Asynchrone Verarbeitung oder vorberechnete Ereignisse können spätere Wartezeit verschieben, aber nicht für jede freie, unvorhersehbare Handlung in 1–3 s eine geprüfte Konsequenz liefern. Eine sofortige bloße Empfangsbestätigung wäre keine sinnvolle Antwort.

Ein Modellaufruf pro Handlung wäre nur mit geändertem Vertrauensmodell möglich: Das eine Modell müsste zugleich verborgene Wahrheit, Konsequenz und GIZMOs öffentlichen Antworttext bearbeiten. Ohne vollständige Prüfung vor Anzeige drohen Spoiler; mit vollständiger Prüfung bleibt der erste Text bis zum Ende des Aufrufs zurückgehalten. Diese Architektur wurde deshalb nicht ungeprüft produktiv eingeführt.

Nach ausdrücklicher Freigabe wurde [`gemma4:e2b`](https://ollama.com/library/gemma4/tags) lokal geladen und mit demselben synthetischen Testprofil geprüft. Ein warmer Minimalprompt benötigte 2,07 s bis Token 1. Eine einfache Story-Frage benötigte 2,42 s bis zum ersten Callback und 2,52 s insgesamt; eine Handlung benötigte 5,33 s bis zur vollständig geprüften Antwort. Bei der normalen Frage direkt nach Start fielen jedoch erneut rund 4,4 s Modellladen an; der erste Text erschien nach 7,26 s. Die gesamte GPU-Belegung lag während der Fragen bei rund 4.800 MiB.

Der vollständige `story_qa.py`-Abnahmelauf für `gemma4:e2b` erreichte die Origin-Initialisierung, scheiterte dort aber trotz des begrenzten Reparaturversuchs an der strukturierten Ausgabe. Das kleinere Modell ist deshalb **nicht freigegeben** und wurde produktiv weder aktiviert noch installiert. Die vorherigen Testabschnitte und ein separater kurzer Handlungsablauf waren erfolgreich; daraus folgt keine Freigabe für den gesamten Story Director. [`qwen3:4b`](https://ollama.com/library/qwen3) ist ein weiterer offizieller Kandidat, wurde hier weder geladen noch getestet. Weitere Downloads benötigen eine eigene Freigabe.

Die vom Benutzer beobachteten 25–45 s wurden mit dem synthetischen Profil nicht vollständig reproduziert. Das echte Profil und private Gespräche wurden nicht untersucht. Die Zahlen oben sind deshalb eine Untergrenze beziehungsweise ein kontrollierter Vergleich, keine Messung des persönlichen produktiven Dialogs.
