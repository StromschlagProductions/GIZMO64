# First Contact 0.2

## Windows-Betrieb

Python 3 und Ollama installieren. Das Modell `richardyoung/qwen3-14b-abliterated:latest` einmalig mit `ollama pull richardyoung/qwen3-14b-abliterated:latest` laden. Danach [start-gizmo.bat](../bridge/start-gizmo.bat) auf dem Windows-PC starten. Die Brücke lauscht auf TCP-Port 6464 und ruft bei einer ersten KI-Anfrage `http://localhost:11434/api/chat` auf. Falls Ollama noch nicht läuft, startet die Brücke `ollama serve` selbst. Beim Beenden mit Strg+C beendet sie den von ihr gestarteten Prozess und schließt aktive C64-Verbindungen. Ein bereits vorher laufender Ollama-Prozess bleibt unter der Kontrolle seines Besitzers. Es werden keine Python-Pakete zusätzlich benötigt.

Die Windows-Firewall muss eingehende TCP-Verbindungen vom Ultimate auf Port 6464 zulassen. Im C64-Client ist `192.168.178.244` voreingestellt. `IP <adresse>` ändert das Ziel bis zum nächsten Programmstart.

Für eine eigene Persönlichkeit [config.example.json](../bridge/config.example.json) nach `bridge/config.local.json` kopieren und anpassen. Diese Datei und `bridge/memory.json` werden von Git ignoriert. Das Gedächtnis liegt nur auf dem PC. `MERKE: <fakt>` speichert einen Fakt dauerhaft, `ERINNERE` gibt die letzten Fakten aus. Bis zu 20 Gesprächsnachrichten werden für laufenden Kontext im Arbeitsspeicher gehalten. Der C64-Header zeigt die vom Server gemeldete Faktzahl.

## Übertragung

Der vorhandene Verbindungsaufbau und PING/PONG bleiben erhalten. Freie Texteingaben von bis zu 120 Zeichen werden als ASCII-Zeile mit CR gesendet. Die Brücke sendet jede Antwort in diesem Format:

```
[[GIZMO:BEGIN]]
ERSTE ANTWORTZEILE
ZWEITE ANTWORTZEILE
[[GIZMO:END]]
```

Jede Zeile endet mit CRLF. Der Client verarbeitet fragmentierte Daten und zeigt nur den Inhalt zwischen den Markierungen als GIZMO-Antwort. Pro Antwort sind höchstens sechs Zeilen mit je höchstens 31 ASCII-Zeichen vorgesehen. Die Brücke entfernt `<think>`-Blöcke, wandelt Umlaute um und entfernt nicht druckbare Bytes. `STATUS` vom C64 liefert `FACTS: <anzahl>` für den Header. Der lokale C64-Befehl `STATUS` zeigt weiterhin die ACIA-Diagnose.

Während einer Anfrage pulsiert die Wellenform schneller und eine dezente Anzeige erscheint in der Fußzeile. Nach 120 Sekunden ohne Antwortende meldet der C64 einen Antwort-Timeout, hält den Uplink aber offen. `OFFLINE` und `UPLINK` verwalten die Verbindung wie in 0.1.2. Bei Überlauf erscheinen ACIA- und Pufferwarnungen.

## Prüfstand

`make test` führt C-Hosttests und Python-Brückentests aus, `make` baut das PRG. Der [VICE-Screenshot](../screenshots/vice-0.2.png) zeigt den Boot- und Offline-Zustand. VICE lief ohne Ultimate-ACIA, daher konnte eine KI-Unterhaltung dort nicht geprüft werden. Die erste echte Unterhaltung auf dem Ultimate muss noch verifiziert werden.
