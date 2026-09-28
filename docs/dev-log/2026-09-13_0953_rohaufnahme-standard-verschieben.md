# Entwicklungsbericht: Rohaufnahme standardmaessig verschieben

## Ziel

Fehlt eine ausdrueckliche Benutzereinstellung, soll die Rohaufnahme nach erfolgreicher lokaler Verarbeitung standardmaessig in den endgueltigen Aufnahmeordner verschoben werden. Gespeicherte abweichende Einstellungen bleiben erhalten und Fehler vor dem lokalen Abschluss duerfen die Rohaufnahme nicht verschieben.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_config.py`
- `tests/test_processing.py`
- `tests/test_tui.py`
- `STATUS.md`
- `docs/dev-log/2026-09-13_0953_rohaufnahme-standard-verschieben.md`

## Was wurde umgesetzt?

Die zentrale Konfiguration verwendete bereits `raw_archive_mode = "move"`, ebenso `config.example.toml`. Das Laden fehlender Werte greift bereits auf diesen Default zurueck und respektiert vorhandene Werte. Auch die Verarbeitungsreihenfolge war bereits sicher: MP4, MP3 und Zusammenfassung werden vor der Rohaufnahme-Aktion verarbeitet.

Diese Regeln sind nun ausdruecklich durch Regressionstests abgesichert. In der Textual-Dateipruefung wurde der widerspruechliche Zusatz `sicherer Standard` bei der Option `liegen lassen` entfernt. Alle vorhandenen Optionen bleiben bestehen; die Einstellungen uebernehmen weiterhin den wirksamen Konfigurationswert.

## Tests

- fehlender Config-Wert ergibt `move`, ohne die bestehende Datei umzuschreiben
- explizites `keep` bleibt erhalten
- Textual-Einstellungen zeigen bei fehlender Abweichung `verschieben`
- erfolgreicher lokaler Lauf verschiebt die Rohaufnahme erst nach MP4, MP3 und Zusammenfassung
- simulierter MP3-/FFmpeg-Fehler laesst die Rohaufnahme unveraendert am Quellort
- gezielte Auswahl: 5 Tests bestanden
- vollstaendige Suite ueber `scripts/test.ps1`: 479 Tests bestanden
- `git diff --check`: keine Whitespace-Fehler; nur die bekannten LF-/CRLF-Hinweise

## Offene Punkte / Risiken

Das Verschieben kann bei sehr grossen Dateien je nach Quell- und Ziellaufwerk selbst laenger dauern. Die bestehende Fortschrittsmeldung zeigt diesen Schritt an. Ein Abbruch des Betriebssystems mitten in einer laufenden Dateisystemverschiebung kann nicht transaktional ueber Laufwerksgrenzen hinweg garantiert werden.

Nachtrag vom 14.09.2026: Ein manueller Test zeigte, dass dieser Bericht die zentrale Funktion korrekt, aber den produktiven Textual-Screenuebergang nicht vollstaendig abgedeckt hatte. `TargetFolderReviewScreen` setzte die Aktion dort noch fest auf `keep`. Die Korrektur und der neue Ende-zu-Ende-Pilot-Test sind im Entwicklungsbericht `2026-09-14_1645_textual-rohaufnahme-archivierung.md` dokumentiert.

## Naechster sinnvoller Schritt

Den normalen Rohaufnahme-Workflow einmal manuell mit einer kleinen Testdatei durchlaufen und kontrollieren, dass die Rohaufnahme erst nach erfolgreicher Ausgabe im finalen Tagesordner erscheint.
