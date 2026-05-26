# Entwicklungsbericht: test-launcher-ascii-name

## Ziel

Die Umbenennung des anklickbaren Test-Launchers auf den Windows-robusten Dateinamen `Tests ausfuehren.cmd` vollstaendig nachvollziehen.

## Geänderte Dateien

- `STATUS.md`
- `scripts/make-release-zip.ps1`
- `tests/test_manual_test_assets.py`
- `docs/dev-log/2026-05-22_1430_pytest-lokale-temp-ordner.md`
- `docs/dev-log/2026-05-22_1630_test-launcher-ascii-name.md`

## Was wurde umgesetzt?

- Alle konkreten Dateipfad-Referenzen auf die Umlautvariante wurden durch `Tests ausfuehren.cmd` ersetzt.
- Der Launcher wurde im Repo auf `Tests ausfuehren.cmd` umbenannt. Das Nutzer-Release enthaelt spaeter bewusst nur die drei Gemeinde-Launcher.
- Die Asset-Tests erwarten den ASCII-Dateinamen in Script-Liste, Launcher-Dict und Release-Assertions.
- Status und bestehender Dev-Log nennen den konkreten Dateinamen ebenfalls ASCII-sicher.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: `191 passed`
- `.\scripts\make-release-zip.ps1`
- Ergebnis: Release-ZIP wurde erstellt.

## Offene Punkte / Risiken

- Keine bekannten offenen Punkte zu dieser Umbenennung.

## Nächster sinnvoller Schritt

Das erzeugte Release-ZIP auf dem Zielrechner entpacken und pruefen, dass nur die drei Gemeinde-Launcher sichtbar sind.
