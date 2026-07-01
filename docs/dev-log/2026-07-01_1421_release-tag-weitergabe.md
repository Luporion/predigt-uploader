# Entwicklungsbericht: release-tag-weitergabe

## Ziel

`scripts/release.ps1 -ReleaseTag ...` soll denselben ZIP-Namen erzeugen wie `scripts/make-release-zip.ps1 -ReleaseTag ...`.

## Geänderte Dateien

- `scripts/release.ps1`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- `release.ps1` ruft `make-release-zip.ps1` nun explizit mit `-ReleaseTag $ReleaseTag` oder `-ReleaseName $ReleaseName` auf.
- Die vorherige Array-Splatting-Weitergabe wurde entfernt, damit `ReleaseTag` nicht versehentlich als ReleaseName behandelt werden kann.
- Tests prüfen jetzt, dass `ReleaseTag` explizit als `-ReleaseTag` weitergereicht wird und kein alter Splatting-Pfad verwendet wird.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 263 passed
- `.\scripts\release.ps1 -ReleaseTag v0.1.9-textual-workflow-preview-r4`
- Ergebnis: `dist\predigt-uploader-v0.1.9-textual-workflow-preview-r4.zip` erstellt.

## Offene Punkte / Risiken

- Keine bekannten offenen Punkte für die Tag-Weitergabe.

## Nächster sinnvoller Schritt

Beim nächsten Release bevorzugt `scripts\release.ps1 -ReleaseTag <tag>` verwenden, damit Tests und ZIP-Bau zusammenlaufen.
