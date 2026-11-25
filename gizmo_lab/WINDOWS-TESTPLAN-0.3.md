# Windows-Testplan – Intelligent Memory Core 0.3

1. Vorher den Ordner `%LOCALAPPDATA%\GizmoLab` sichern. Das neue ZIP separat entpacken und `start-gizmo-lab.bat` starten. Beim ersten Start muss im Datenordner eine `.pre-v03-...bak`-Sicherung entstehen; alte Gespräche müssen erhalten sein.
2. Mit `--personality C:\Pfad\GIZMO_Awakening_V2_EN.txt` starten oder das private Profil im LAB-Datenordner belassen. Modell `gemma4:12b` und `num_ctx: 8192` prüfen. `ollama ps` und GPU-Auslastung beobachten.
3. Fiktive Testdaten verwenden: „My sister's name was Emma.“ Dann „She studied psychology.“ und „She loved science fiction.“ Nach kurzen Pausen `/entities`, `/relations` und `/memstatus` prüfen. Emma darf nicht mit einer anderen Person verwechselt werden; Pronomenbezüge müssen offen bleiben.
4. „My dog is named Milo.“ und „Alex and GIZMO discussed WarGames.“ testen. Quellen-ID und Beleg in `/relations` prüfen. Eine unklare Aussage wie „Maybe my sister created you“ darf nicht als bestätigter Fakt erscheinen.
5. `/reanalyze` ausführen, Fortschritt über `/memstatus` beobachten und denselben Befehl wiederholen. Anzahl identischer Beziehungen darf nicht steigen. LAB während der Analyse beenden und neu starten; offene Jobs müssen erhalten bleiben.
6. Eine bekannte Erinnerung mit `/correct ID WERT` ändern oder mit `/delete ID` löschen. Reanalyse darf den alten Wert nicht unkontrolliert wiederherstellen.
7. Modell wechseln und zurückwechseln. Archiv, Entitäten und Beziehungen müssen erhalten bleiben. Antwortzeiten, Time to First Token, Dialogdauer und Analysedauer mit realem Gemma dokumentieren.
8. Eine neue Frage während einer laufenden Analyse stellen. Die Frage hat Vorrang, Analyseauftrag bleibt zur Wiederholung. ESC, Q und Strg+C während einer Analyse sowie vollständige Ollama- und GPU-Abschaltung prüfen.
9. `/backup probe.sqlite3` und `/export probe.json` im privaten Datenordner prüfen. Keine persönlichen Dateien auf GitHub hochladen.

Die automatisierten Tests ersetzen diese Messungen auf RTX 3060 und Windows nicht.
