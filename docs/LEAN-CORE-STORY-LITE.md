# GIZMO LAB 0.9.0 – Lean Core Phase 2: Story Lite

## Verhalten

Story Lite verwendet den vorhandenen Story Director und die Narrative Library v1.1. Gemma 4 12B und Ollama bleiben die einzigen Inferenzkomponenten. Die alte Engine bleibt über den Phase-1-Commit `d767852` und die aufbewahrte LAB-0.8.1-Installation als Rückfall erhalten.

Nach mindestens zwei normalen Gesprächsrunden kann GIZMO in einer Pause von mindestens 90 Sekunden eine kurze fiktionale Entdeckung vorbereiten. Standardmäßig liegt die Chance pro geeigneter Pause bei 10 %, der Mindestabstand zwischen Welten bei 72 Stunden; eine vorbereitete Szene verfällt nach sieben Tagen. Damit kann normale Unterhaltung auch längere Zeit ohne Story-Ereignis stattfinden. Die Origin-Kampagne wird gelegentlich berücksichtigt, ihre verborgene Wahrheit entsteht weiterhin erst lokal zur Laufzeit. Weder Geheimnisse noch Profil oder reale Erinnerungen werden in die sichtbare Szene übernommen.

Eine vorbereitete Szene liegt mit Status `prepared` im bestehenden lokalen Story-Archiv. Vor der Freigabe werden Alter, Narrative-Library-Version, Weltzug und Spoilerregeln erneut geprüft. Zwei konkrete gemeinsame Themenwörter oder ein ausdrücklicher Story-Wunsch sind für die Freigabe erforderlich. Normale Gespräche werden ansonsten direkt beantwortet. Die sichtbare Antwort entsteht mit **einem Dialog-Modellaufruf** und wird Satz für Satz vor dem Streaming auf verborgene Begriffe geprüft. Fiktionale Eingaben und Antworten werden nicht als reale Gedächtnisfakten gespeichert.

Bei Benutzereingaben unterbricht ein abbrechbarer lokaler HTTP-Kanal die Hintergrundgenerierung. Die Hintergrundarbeit pausiert auch die bestehende Analyse; alle Komponenten enden beim kontrollierten Shutdown. Director, Dialog und Analyse verwenden im Story-Lite-Betrieb denselben 8192er Modellkontext, damit ein Wechsel zwischen 6144 und 8192 keinen zusätzlichen Modell-Reload auslöst. Es gibt keine zweite Modellinstanz und keine Cloud-API.

## Echte Gemma-Abnahme mit synthetischen Daten

Die Tests benutzten nur ein synthetisches Profil und getrennte synthetische SQLite-Welten. Der Bericht enthält keine generierten Geheimnisse, Szenen oder Auflösung.

| Fall | Erster sinnvoller Text | Gesamtzeit | Befund |
|---|---:|---:|---|
| Erste normale Antwort nach Start | 9,12 s | 10,81 s | Kaltstart einschließlich 4,86 s Modellladen |
| Normale Antwort während Hintergrundvorbereitung | 4,53 s | 5,78 s | Hintergrund abgebrochen, kein Modell-Reload |
| Spontane vorbereitete Szene | 3,47 s | 3,70 s | Ohne `/story`, kein Director-Aufruf bei Eingabe |
| Normale Antwort nach Neustart | 7,64 s | 8,05 s | Welt erhalten; Alltagsfrage blieb normale Unterhaltung |
| Unerwartete Handlung, einheitlicher Kontext | 11,12 s | 11,12 s | Konsequenz geprüft; kein Kontext-Reload |
| Vorbereitete Origin-Szene | 3,38 s | 3,81 s | Verborgene Kampagne blieb vom Dialog getrennt |

Ein gezielter Wiederholungstest trennte den Hintergrundabbruch von der Antwort: Der Abbruch dauerte **2,00 s**, der erste Text kam nach **4,41 s**, die Antwort endete nach **6,21 s**. Modellladen betrug dabei nur 0,006 s und Prompt-Verarbeitung 0,201 s. Die restliche Wartezeit ist auf Abbruch/Runner-Umschaltung und Generierung zurückzuführen; der 1–3-Sekunden-Zielbereich wurde in dieser Situation nicht erreicht. Beim ersten Handlungstest verursachte ein alter 6144er Dialogkontext 4,87 s erneutes Modellladen und insgesamt 16,70 s. Nach der gezielten Vereinheitlichung waren es 11,12 s ohne nennenswertes Nachladen. Diese Handlung bleibt bewusst synchron, damit keine ungeprüfte Konsequenz erfunden wird.

Alle **17 spoilerfreien Integrationsprüfungen** bestanden: Hintergrundstart und Unterbrechung, vorbereitete spontane Szene, ein Dialogaufruf bei Freigabe, Trennung von Realität/Fiktion, keine Geheimnisse im Dialog, Fortsetzung nach Neustart, normale Unterhaltung, tatsächliche Handlungsfolge und Origin-Abschirmung. Zusätzlich bestanden **90 lokale Unit- und Regressionstests** sowie die synthetische Control-Center-/Updateprüfung mit Profil- und Datenerhalt.

## Grenzen und Freigabe

Die gemessenen 3,38–3,47 s für vorbereitete Ereignisse und 4,41–4,53 s nach einem Hintergrundabbruch liegen über dem warmen Ziel von 1–3 s. Eine unerwartete Handlung braucht weiterhin einen Director-Aufruf und etwa 11 s. Die thematische Freigabe ist bewusst streng; semantisch passende Formulierungen ohne genügend gemeinsame Wörter können ein vorbereitetes Ereignis ungenutzt lassen. Bestehende aktive Langgeschichten blockieren die Vorbereitung einer zweiten Welt. Die Tests belegen weder C64-Langzeitbetrieb noch eine vollständige kreative Qualitätsbewertung.

Die produktive Erprobung wurde ausdrücklich freigegeben. Die Installation erfolgt über den bestehenden Updater; der vorherige LAB-0.8.1-Release bleibt als Rückfall erhalten. Das persönliche Profil, private Erinnerungen und bestehende Geschichten liegen außerhalb des Release-Verzeichnisses und werden vom Updater nicht überschrieben. Der C64-Client bleibt unverändert. Die lokale Sicherung aus Phase 1 bleibt in `.local-test/lean-core/private-backup-20261128-local/` erhalten; vor diesem Update wird zusätzlich eine frische Sicherung erstellt.
