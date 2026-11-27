# LAB 0.8.0 – Story Director / First Adventure

Der Story Director ist ein optionaler, ausdrücklich aktivierter Teil der gemeinsamen PC-Engine. GUI und C64 nutzen dieselbe `Lab.chat`-Schnittstelle und dieselbe lokale Gemma-Instanz nacheinander. C64-Protokoll, Persönlichkeitsprofil und reales Gedächtnisschema bleiben unverändert.

## Bedienung

In SETTINGS **ENABLE STORY DIRECTOR** aktivieren und lokal speichern. Im MODEL LAB oder auf dem C64 beginnt `/story` ein neues unabhängiges fiktionales Abenteuer. `/story <kurzer Stilwunsch>` beeinflusst die kreative Ausrichtung. `/origin` startet nach ausdrücklicher Eingabe den optionalen übergreifenden fiktionalen Bogen. `/pause` kehrt zum normalen Gespräch zurück; `/story` setzt fort. `/abandon` beendet das aktuelle Abenteuer, ohne persönliche Erinnerungen zu ändern. Die Eingabe während des Abenteuers ist freie natürliche Sprache. Statusanzeigen zeigen nur `READY`, `ACTIVE`, `PAUSED`, `COMPLETED`, `ABANDONED` oder `DISABLED`.

## Daten- und Wissensgrenzen

`story.sqlite3` liegt ausschließlich im privaten LAB-Datenverzeichnis und ist von `memory.sqlite3` getrennt. Die Director-Anfrage enthält ausgewählte Narrative-Library-DNA, fiktionalen Weltzustand und bei ausdrücklich aktivierter Kampagne deren privaten Kanon. Sie enthält weder persönliche Gesprächsarchive noch das Persönlichkeitsprofil. GIZMOs Dialogmodell erhält seine unveränderte Persönlichkeit, aber ausschließlich die nach Validierung freigegebenen Story-Beobachtungen. Story-Nutzereingaben und Story-Antworten werden nur im Story-Ereignisjournal gespeichert; sie werden nicht als reale Fakten extrahiert. Normale Gespräche benötigen keinen Director-Aufruf.

Der Director liefert strukturiertes JSON. Die Engine prüft IDs, Zustandsversion, alternative Zugänge bei Rätseln, Feldgrößen und die Freigabegrenze. Höchstens ein Reparaturversuch ist erlaubt. Eine ungültige oder unvollständige Entscheidung ändert den Weltzustand nicht. Sichtbarer Story-Text wird vor Ausgabe vollständig geprüft; deshalb erfolgt seine Ausgabe erst nach der Modellgenerierung. Der Schutz gegen semantische Umschreibungen von Geheimnissen ist modellabhängig und keine absolute Garantie. Der produktive Kampagnenkanon entsteht erst bei tatsächlicher `/origin`-Benutzung; Tests verwenden ausschließlich synthetische Daten.

## Abnahme

`test_story.py` prüft isolierte Datenbanken, Neustart, Abbruch/Pause, Rollback und die getrennten Modellkontexte. `story_qa.py` nutzt das lokal installierte Gemma 4 12B, ein synthetisches englisches Profil und temporäre Testwelten. Der QA-Bericht enthält nur Prüfergebnisse und Leistungswerte. Die vollständige LAB-Regression läuft in der projektlokalen `.venv`.

Letzte Abnahme: **77/77** LAB-Tests bestanden. Der echte Gemma-Lauf bestätigte unterschiedliche Handlungsfolgen, getrennte Modellkontexte, fiktionale und reale Datenhaltung, alternative Hinweiswege, eine unveränderte verborgene Grundlage nach falscher Hypothese, Fortsetzung nach vollständigem Neustart sowie eine offline geschaltete Ollama-API nach Ende. In diesem synthetischen Lauf: normales Gespräch 8,81 s, erster Abenteuerstart 22,30 s, Handlungsschritte 23,13–24,00 s, einmalige Origin-Aktivierung 47,09 s, Fortsetzung nach Neustart 29,30 s. Die mit `nvidia-smi` gesampelte **gesamte** GPU-Belegung lag während eines Story-Schritts bei 11.134 MiB und nach Studio-Safe-Abschaltung bei 1.871 MiB; dies ist keine exklusive Modellbelegung und keine Langzeitmessung. Ein früherer Lauf erlitt einen lokalen Ollama-Verbindungsabbruch; nach Begrenzung des Director-Kontextes auf 6.144 Tokens bestand die vollständige Abnahme. Langzeitstabilität bleibt unbelegt.

Die Narrative Library v1.1 wird unverändert als kreativer Wortschatz eingebunden. Ihr Selektor wählt einen begrenzten Satz von Bausteinen mit persistentem Seed, IDs und Versionskennung. Es werden keine fertigen Abenteuer ausgeliefert. Spätere STORYFORGE-Nutzung kann das frontendunabhängige `story.py` verwenden; ein Autorenmodus ist nicht Teil dieser Version.
