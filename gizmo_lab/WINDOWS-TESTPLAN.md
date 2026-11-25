# Manueller Windows-Testplan – GIZMO LAB 0.2

1. ZIP in einen neuen Ordner entpacken. Python 3 und Ollama prüfen. `ollama pull gemma4:12b` bei Bedarf **manuell** ausführen.
2. `GIZMO_Awakening_V2_EN.txt` privat unter `%LOCALAPPDATA%\GizmoLab` ablegen oder mit `--personality C:\Pfad\GIZMO_Awakening_V2_EN.txt` starten. Die Datei gehört nicht ins öffentliche Repository. `start-gizmo-lab.bat` starten und Modellbereitschaft beobachten.
3. „My name is Alex“ schreiben, dann mindestens 30 neutrale Gesprächsrunden führen. „What is my name?“ fragen. Mit `--debug` prüfen, ob `name: Alex` als abgerufene Erinnerung und in den Ollama-Nachrichten steht.
4. LAB mit `/quit` beenden und neu starten. Dieselbe Namensfrage wiederholen. Gesprächs-ID und archivierte Nachrichten in der lokalen Datenbank prüfen.
5. „I like astronomy“ nennen, danach längere thematische Ablenkung. Später nach dem Interesse fragen und mit `--debug` den FTS5-Abruf prüfen.
6. „My name is Blake“ nennen. `/memory` muss Alex aktiv und Blake offen zeigen. Mit `/correct ID Blake` korrigieren; danach nur Blake als aktiven Namen prüfen. Mit `/delete ID` löschen und fehlenden Abruf prüfen.
7. Mit `/model MODELLNAME` zu einem bereits installierten Modell wechseln. Archiv, Profil-SHA und Erinnerungen müssen erhalten bleiben. Danach zum Ausgangsmodell zurückwechseln.
8. `/backup test-backup.sqlite3` und `/export test-export.json` ausführen. Dateien nur im privaten LAB-Datenordner prüfen. Testkopien anschließend sicher verwahren oder löschen.
9. ESC, Q und Strg+C während Laden und Generierung testen. Danach im Task-Manager prüfen, dass `ollama.exe`, `ollama app.exe` und Modellprozesse beendet sind und die GPU-Auslastung zurückgeht.
10. Reale Antwortqualität, VRAM-Auslastung, `num_ctx: 8192` und Antwortzeit mit `gemma4:12b` dokumentieren. Automatisierte Tests ersetzen diesen Schritt nicht.
