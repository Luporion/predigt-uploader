# Entwicklungsbericht: textual-starter-abschluss

## Ziel

Textual soll einen eigenen einfachen Start-Shortcut bekommen und nach erfolgreicher Verarbeitung deutlicher als abgeschlossen wirken.

## Geaenderte Dateien

- `PredigtUploader Textual starten.cmd`
- `scripts/run-tui.ps1`
- `scripts/make-release-zip.ps1`
- `.gitignore`
- `README.md`
- `src/predigt_uploader/tui_app.py`
- `tests/test_manual_test_assets.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Neuer Doppelklick-Starter `PredigtUploader Textual starten.cmd` fuer die experimentelle Textual-Oberflaeche.
- Neues PowerShell-Skript `scripts/run-tui.ps1`, das die lokale `.venv` nutzt und `python -m predigt_uploader tui` startet.
- Release-ZIP nimmt den Textual-Starter auf und schliesst `.lnk`-Verknuepfungen aus.
- Der Textual-Erfolgsstatus zeigt Zielordner, finale MP4/MP3, Zusammenfassung, Kontrollliste und manuelle Vimeo-/WordPress-Schritte.
- Wenn Dateien ersetzt wurden, meldet der Erfolgsstatus das deutlich.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 262 passed
- `.\scripts\make-release-zip.ps1`
- Ergebnis: `dist\predigt-uploader-v0.1.8-textual-metadata-preview.zip` erstellt.

## Offene Punkte / Risiken

- Der neue Textual-Starter sollte auf dem Zielrechner per Doppelklick getestet werden.
- Textual bleibt experimentell; der normale Wizard bleibt produktiver Standard.

## Naechster sinnvoller Schritt

Release-ZIP auf dem Zielrechner entpacken und beide Starts testen: normaler Wizard und Textual.
