# Entwicklungsbericht: textual-setup-installation

## Ziel

Nach `PredigtUploader einrichten.cmd` soll auch die experimentelle Textual-Oberflaeche startbar sein.

## Geaenderte Dateien

- `scripts/setup-local.ps1`
- `scripts/check-system.ps1`
- `scripts/run-tui.ps1`
- `tests/test_manual_test_assets.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Das lokale Setup installiert standardmaessig `.[tui]`.
- Mit `-IncludeDev` installiert das Setup `.[dev,tui]`.
- Die Setup-Ausgabe nennt Wizard und Textual-Oberflaeche und meldet nach Erfolg: `Textual-Oberflaeche ist installiert.`
- Der Systemcheck prueft `python -c "import textual"` und gibt eine klare Warnung aus, wenn Textual fehlt.
- `run-tui.ps1` prueft Textual vor dem Start und nennt konkret `PredigtUploader einrichten.cmd`, falls Textual fehlt.
- Die doppelte Startmeldung wurde reduziert: die `.cmd`-Datei meldet den Start, `run-tui.ps1` gibt nur noch den experimentellen Hinweis aus.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 262 passed
- `.\scripts\make-release-zip.ps1`
- Ergebnis: Release-ZIP erfolgreich erstellt.

## Offene Punkte / Risiken

- `PredigtUploader einrichten.cmd` sollte auf dem Zielrechner erneut ausgefuehrt werden, damit Textual wirklich in der lokalen `.venv` installiert wird.

## Naechster sinnvoller Schritt

Auf dem Zielrechner Setup erneut starten, Systemcheck pruefen und danach `PredigtUploader Textual starten.cmd` per Doppelklick testen.
