# GIZMO Lean Core – Phase 1 (lokaler Entwicklungsstand)

## Umfang

Branch `develop/lean-core-phase1` beginnt beim gesicherten Entwicklungsstand `5db0de6`. Die produktive LAB-0.8.1-Installation, private Daten und der C64-Client 0.3.0 wurden nicht geändert. `lean_core_enabled` ist im Entwicklungsbranch standardmäßig aktiv. Der Story Director wird dadurch nicht geladen; vorhandene Story-Datenbanken und der Code bleiben erhalten. Ohne Lean-Schalter ist der bisherige Story-Pfad weiter testbar.

Der Dialog verwendet weiterhin Gemma 4 12B über Ollama und genau einen Dialog-Modellaufruf je Eingabe. Streaming, konstanter Kontext von 8192 und die bestehende Unterbrechung der Hintergrundanalyse bleiben bestehen. Der vollständige aktive Profiltext ist weiterhin die erste Systemnachricht. Eine kürzere Gedächtnisrichtlinie ersetzt den langen Standardblock; eine dynamische Zeitnachricht wird nur für tatsächliche Zeitfragen ergänzt. Das Abrufbudget für Gedächtnis sinkt von 900 auf 450 konservativ gezählte UTF-8-Bytes, ohne Retrieval- oder Löschlogik zu ändern. Die Antwortobergrenze ist im Beispiel von 768 auf 256 Tokens gesenkt. Der Kontext wird nicht stillschweigend abgeschnitten.

## Lokaler Vergleich mit echtem Gemma

Identische sieben Gesprächsrunden nutzten ausschließlich synthetische Namen, Gegenstände und Fakten. Getestet wurden Englisch, eine deutsche Eingabe mit Tippfehler, Humor, fiktionale Kreativität und ein unbestätigtes Datum. Das tatsächliche aktive Persönlichkeitsprofil wurde nur lokal gelesen und nicht kopiert oder veröffentlicht. Gemessen wurde der erste sinnvolle sichtbare Text im Streaming-Callback. Die projektlokale Python-Umgebung indizierte die synthetischen Quellen zusätzlich mit dem vorhandenen multilingual-e5-small auf der CPU.

| Pfad/Profil | Median erster Text, sechs warme Runden | Mittlere Gesamtdauer | Mittlere Prompt-Verarbeitung | Profilgröße |
|---|---:|---:|---:|---:|
| Bisheriger Pfad, Originalprofil | 3,27 s | 4,09 s | 1,16 s | 3231 Bytes |
| Lean-Pfad, Originalprofil | 3,01 s | 3,79 s | 0,94 s | 3231 Bytes |
| Lean-Pfad, kompakte lokale Testvariante | 2,76 s | 3,70 s | 0,67 s | 555 Bytes |

Die erste Antwort nach Start brauchte beim bisherigen Pfad 7,45 s. Die späteren Profilvarianten liefen im selben warmen Ollama-Prozess, daher taugen ihre ersten Antworten nicht als eigener Kaltstartvergleich. Die Ollama-Metriken zeigten nach dem ersten Laden keine nennenswerte erneute Modellladezeit (in Summe rund 0,02 s über die Folgerunden). Die reine Gedächtnisabfrage benötigte in diesem kleinen Datensatz im Mittel etwa 0,005 s. Der gemessene GPU-Gesamtspeicher erreichte je nach Lauf etwa 11,6–11,8 GiB einschließlich anderer Desktop-Prozesse; die 12-GB-Karte hat dabei wenig Reserve. Das ist keine exklusive Modellbelegung.

Beide Pfade mit Gedächtnis nannten die synthetische Hunderasse und die beteiligte Person korrekt und hielten das vermutete Baujahr unbestätigt. Ohne Gedächtniskontext war der Median erster Text 2,48 s, doch die Hunderasse ging verloren; diese Variante ist ungeeignet. Zwei zusätzliche kompakte Profilformulierungen und eine Temperatur von 0,55 wurden ebenfalls verglichen. Sie waren ähnlich schnell, wirkten in der kleinen Stichprobe aber häufiger generisch, mit Ausrufen, Floskeln oder unnötigen Gegenfragen. Auch die beste kompakte Variante war charakterlich nicht klar überzeugender. **Das private Originalprofil bleibt daher der Standard.** Eine feinere, lokal erarbeitete Persönlichkeit ist ein eigener späterer Qualitätsentscheid.

Kurze synthetische Vergleichsantworten:

> Bisheriger Pfad: “Your friend Lina gave you the radio, and Nori is a terrier.”

> Lean-Pfad mit Originalprofil: “Lina was the one who gave you the radio. And I believe Nori is a terrier.”

> Ohne Gedächtnis: “As for Nori, I don't actually know his breed yet …”

Die Messung zeigt eine moderate Verbesserung des Gesprächspfads, keine generelle Garantie von 1–3 Sekunden. Bei vollem Profil lagen die warmen Antworten meist um 3 Sekunden; längere Eingaben, Verlauf, GPU-Konkurrenz und Hintergrundarbeit können mehr kosten. Der kleine synthetische Datensatz beweist noch keine dauerhaft überzeugende, E.T.-artige Gesprächsqualität. Weitere Optimierungsschleifen ohne neuen konkreten Engpass sind nicht vorgesehen.

## Qualitätssicherung und Rückfall

Die 85 projektlokalen Unit- und Regressionstests bestanden. Die synthetische Control-Center-Prüfung bestand einschließlich Einstellungen, Neustart, simuliertem Update, Profilerhalt und vollständigem Fenster-Shutdown. Zusätzliche Tests belegen, dass Lean Core ein bestehendes Story-Archiv unangetastet lässt, bei normalen Eingaben genau einen Modellaufruf verwendet und die relevante Hunderasse auch zwischen vielen anderen Erinnerungen mit dem kleineren Budget findet. Der alte Story-Pfad bleibt mit `lean_core_enabled=false` testbar.

Vor dem lokalen Commit wurden die produktiven `memory.sqlite3`, `story.sqlite3`, `config.json` und das Profil in `.local-test/lean-core/private-backup-20261128-local/` gesichert. Beide SQLite-Kopien bestanden `PRAGMA integrity_check`; Konfiguration und Profil wurden bytegenau verifiziert. Das Verzeichnis wird von Git ignoriert. Ollama wurde nach allen echten Modellläufen beendet; vor einer produktiven Freigabe sind weiterhin längere Gespräche und ein realer Studio-Betriebstest sinnvoll. Keine Veröffentlichung oder produktive Installation wurde vorgenommen.
