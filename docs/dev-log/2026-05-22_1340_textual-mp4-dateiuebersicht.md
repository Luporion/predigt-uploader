# Entwicklungsbericht: textual-mp4-dateiuebersicht

## Ziel

Textual als experimentelle zweite Oberfläche vorsichtig erweitern, ohne den normalen Terminal-Wizard als produktiven Standard zu verändern.

## Geänderte Dateien

- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-22_1340_textual-mp4-dateiuebersicht.md`

## Was wurde umgesetzt?

- Der Textual-Prototyp hat eine neue reine MP4-Dateiübersicht bekommen.
- Die Übersicht zeigt Orientierung zu Schnitt-/Exportordner und Rohaufnahme-Ordner, inklusive neuester MP4-Dateien, ohne Dateien zu übernehmen oder zu verarbeiten.
- Textual lädt nun die normale Config-Suchreihenfolge statt nur die eingebaute Standardconfig zu verwenden.
- Config-Fehler beim TUI-Start werden wie beim Wizard verständlich gemeldet.
- Die Export-Erkennung wurde gegen alte MP4-Dateien aus breiten Benutzerordnern wie Desktop/Downloads gehärtet, damit private lokale Dateien keine automatischen Tests und keine Exportauswahl verfälschen.
- README, Status, Aufgabenliste und manuelle Test-/Installationsdoku nennen die neue Textual-Dateiübersicht als experimentelle Orientierung.

## Tests

- `python -m compileall -q src/predigt_uploader`
- `python -m pytest tests/test_tui.py`
- `python -m pytest`
- Ergebnis: `189 passed`

## Offene Punkte / Risiken

- Die Textual-Dateiübersicht ist bewusst nur lesend. Die echte Dateiauswahl und Verarbeitung laufen weiterhin im normalen Wizard.
- Die Textual-Oberfläche ersetzt den produktiven Workflow noch nicht.

## Nächster sinnvoller Schritt

Textual mit installiertem Extra `.[tui]` manuell starten und prüfen, ob Startmenü, Metadaten-Vorschau, MP4-Dateiübersicht und Einstellungen im echten Terminal angenehm bedienbar sind.
