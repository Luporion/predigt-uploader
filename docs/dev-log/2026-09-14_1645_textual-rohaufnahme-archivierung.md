# Entwicklungsbericht: Textual-Rohaufnahme-Archivierung

## Ziel

Den im manuellen Realtest gefundenen Produktionsfehler beheben: Im vollstaendigen Textual-Zuschneideworkflow soll die urspruengliche Rohaufnahme nach erfolgreicher lokaler Verarbeitung gemaess `raw_archive_mode` behandelt werden.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_processing.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/config.md`
- `docs/dev-log/2026-09-13_0953_rohaufnahme-standard-verschieben.md`
- `docs/dev-log/2026-09-14_1645_textual-rohaufnahme-archivierung.md`

## Was wurde umgesetzt?

Der Rohaufnahme-Pfad ging nicht verloren: `FileSelectionScreen`, `LosslessCutScreen`, `CutMp4DetectionScreen`, `MetadataPreviewScreen` und `TargetFolderReviewScreen` reichten ihn korrekt weiter. Der Fehler entstand erst beim Aufbau des `PreparedRecordingPlan`: Dort wurde bei vorhandener Rohaufnahme stets `raw_action="keep"` gesetzt und damit der Configwert ueberschrieben.

Schritt 6 uebergibt nun `app_config.raw_archive_mode`. Die gemeinsame Verarbeitungsfunktion fuehrt die Aktion weiterhin erst nach MP4-Uebernahme, MP3-Erstellung und Zusammenfassung aus. `WorkflowState` speichert den Originalpfad in `paths.raw_recording`, den Export in `paths.cut_mp4`, die fertige Datei in `paths.final_mp4` und nach erfolgreicher Archivierung den neuen Pfad in `paths.archived_raw_recording`.

Die Textual-Einstellungen zeigen einen eigenen erklaerten Bereich `Rohaufnahme nach Verarbeitung` mit eindeutigen Auswahltexten. Die bestehende Persistenz unter `[workflow] raw_archive_mode` bleibt unveraendert. Die Abschlussanzeige unterscheidet verschoben, kopiert, liegen gelassen und keine Rohaufnahme. Scheitert erst der Move, obwohl die fertigen lokalen Ausgaben bereits vorhanden sind, bleibt der Originalpfad sichtbar und die UI erklaert diesen Teilzustand.

## Tests

- kompletter Textual-Pilotpfad Rohaufnahme -> LosslessCut-Export -> Metadaten -> Zielordner -> reale gemeinsame Verarbeitung mit `move`
- derselbe Pfad mit `keep`
- getrennte Pruefung von Original-Rohaufnahme, Export-MP4 und finaler MP4 im Workflow-State
- Fehler vor dem lokalen Abschluss laesst die Rohaufnahme am Quellort
- Move-Fehler nach fertigen Ausgaben laesst die Originaldatei bestehen
- bereits geschnittene MP4 und Direct-Vimeo enthalten keine Rohaufnahme
- Textual-Einstellung speichert `keep` und wird ueber `load_config` wieder geladen
- klare Abschluss- und Fehlertexte fuer die Rohaufnahme-Aktion
- gezielte Config-/Processing-/Textual-Auswahl: 50 Tests bestanden
- vollstaendige Suite ueber `scripts/test.ps1`: 484 Tests bestanden
- `git diff --check`: keine Whitespace-Fehler; nur die bekannten LF-/CRLF-Hinweise

## Offene Punkte / Risiken

Ein Verschieben ueber Laufwerksgrenzen kann bei grossen Rohaufnahmen laenger dauern. Die gemeinsame Verarbeitung meldet diesen Schritt. Ein harter Rechner- oder Prozessabbruch waehrend einer laufenden systemseitigen Move-Operation kann nicht vollstaendig transaktional abgesichert werden; vor Beginn des Moves sind die lokalen Ausgabedateien jedoch bereits erstellt.

## Naechster sinnvoller Schritt

Den korrigierten Textual-Zuschneideworkflow mit einer kleinen Test-MP4 je einmal fuer `verschieben` und `liegen lassen` manuell pruefen und dabei Quell-, Export- und Zielpfad kontrollieren.
