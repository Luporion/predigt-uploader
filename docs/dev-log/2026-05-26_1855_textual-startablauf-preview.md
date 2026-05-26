# Entwicklungsbericht: textual-startablauf-preview

## Ziel

Die experimentelle Textual-Oberflaeche zu einer nutzbaren Startoberflaeche ausbauen, ohne den normalen Wizard als produktiven Workflow zu ersetzen.

## Geänderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `src/predigt_uploader/report.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-26_1855_textual-startablauf-preview.md`

## Was wurde umgesetzt?

- Textual bietet fuer neue Aufnahmen nun einen gefuehrten Start: geschnittene MP4 oder Rohaufnahme.
- Die Datei-Auswahl zeigt die neuesten MP4-Dateien aus dem passenden Ordner und kann per Suchfeld gefiltert werden.
- Zurueck und Abbrechen fuehren kontrolliert zur vorherigen Ansicht bzw. ins Hauptmenue zurueck.
- Die Metadaten-Erfassung nutzt Dateivorschlaege aus Quelle/Dateiname und erzeugt ein Preview-Uebergabeobjekt.
- Das Preview-Uebergabeobjekt enthaelt Quelle, Rohaufnahme, Zielordner, finale MP4, finale MP3 und Zusammenfassungspfad.
- Dateiname, Zielordner und Zusammenfassungspfad nutzen gemeinsame bestehende Helfer statt eigene TUI-Sonderlogik.
- Der normale Wizard, LosslessCut, FFmpeg und Rohaufnahme-Aufraeumen wurden nicht umgestellt.

## Tests

- `python -m compileall -q src/predigt_uploader`
- `python -m pytest tests/test_tui.py`
- Ergebnis: `21 passed`
- `.\scripts\test.ps1`
- Ergebnis: `201 passed`
- `.\scripts\make-release-zip.ps1`
- Ergebnis: Release-ZIP wurde erstellt.

## Offene Punkte / Risiken

- Textual verarbeitet weiterhin keine Dateien und startet keinen produktiven Abschluss.
- Die echte interaktive Bedienbarkeit sollte mit installiertem `.[tui]` manuell im Terminal geprueft werden.

## Nächster sinnvoller Schritt

Textual manuell starten und den neuen Ablauf mit einem echten vMix-/Schnittordner durchklicken.
