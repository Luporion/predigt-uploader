# Entwicklungsbericht: lokale-testversion-v1

## Ziel

Phase 1 als erste lokale Testversion nutzbar machen, ohne neue Produktfeatures, Vimeo-/WordPress-Automatisierung oder GUI einzubauen.

## Geänderte Dateien

- `docs/manual-test-v1.md`
- `scripts/run-wizard.ps1`
- `STATUS.md`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- Eine manuelle Testanleitung fuer Version 1 wurde erstellt.
- Die Anleitung beschreibt Voraussetzungen, Python/venv, FFmpeg, optionale `config.toml`, Wizard-Start, Test mit kleiner MP4, erwartete Zielordner-Ergebnisse, Logdateien und Fehlerhilfe.
- Ein PowerShell-Skript `scripts/run-wizard.ps1` startet den vorhandenen CLI-Wizard.
- Das Skript meldet verstaendlich, wenn `.venv` oder Python fehlt.
- `STATUS.md` wurde um die lokale Testversion und den naechsten manuellen Testschritt ergaenzt.
- Ein statischer Test stellt sicher, dass Anleitung und Startskript vorhanden bleiben und zentrale Hinweise enthalten.

## Tests

- `python -m pytest`
- Ergebnis: 46 Tests bestanden.

## Offene Punkte / Risiken

- Der manuelle Praxistest mit einer echten kleinen MP4 steht noch aus.
- FFmpeg muss auf dem Testrechner installiert oder passend in `config.toml` eingetragen sein, damit die MP3-Erzeugung erfolgreich laeuft.

## Nächster sinnvoller Schritt

Phase 1 nach `docs/manual-test-v1.md` lokal mit einer kleinen MP4 testen und Beobachtungen dokumentieren.
