# Entwicklungsbericht: release-zip-nutzerpaket

## Ziel

Das Release-ZIP wieder klar als Nutzerpaket fuer den Gemeinderechner ausliefern und keinen sichtbaren Test-Launcher im Paket anzeigen.

## Geänderte Dateien

- `STATUS.md`
- `scripts/make-release-zip.ps1`
- `tests/test_manual_test_assets.py`
- `docs/dev-log/2026-05-22_1630_test-launcher-ascii-name.md`
- `docs/dev-log/2026-05-26_1842_release-zip-nutzerpaket.md`

## Was wurde umgesetzt?

- `Tests ausfuehren.cmd` wurde aus den `ReleaseItems` entfernt.
- Der Release-Test erwartet weiterhin die drei Nutzer-Launcher und prueft nun, dass der Test-Launcher nicht als ReleaseItem enthalten ist.
- Die Ausschluesse fuer lokale Test-/Cache-/Dev-Artefakte bleiben erhalten.
- `scripts/test.ps1` bleibt durch den kopierten `scripts`-Ordner technisch im Paket, aber ohne sichtbaren Top-Level-Launcher.
- `STATUS.md` und der vorherige Dev-Log wurden an den Nutzerpaket-Stand angepasst.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: `197 passed`
- `.\scripts\make-release-zip.ps1`
- Ergebnis: `predigt-uploader-v0.1.8-textual-metadata-preview.zip` wurde erstellt.
- `Expand-Archive .\dist\predigt-uploader-v0.1.8-textual-metadata-preview.zip -DestinationPath .\dist\test-extract-v018 -Force`
- Ergebnis: Oberste Ebene enthaelt nur die drei Nutzer-Launcher, keinen Test-Launcher.

## Offene Punkte / Risiken

- Keine bekannten offenen Punkte fuer die Release-Aufraeumung.

## Nächster sinnvoller Schritt

Das ZIP auf dem Gemeinderechner entpacken und die drei sichtbaren Launcher per Doppelklick pruefen.
