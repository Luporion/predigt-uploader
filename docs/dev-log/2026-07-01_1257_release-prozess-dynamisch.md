# Entwicklungsbericht: release-prozess-dynamisch

## Ziel

Der Release-ZIP-Name soll nicht mehr pro Preview-Release hart in `make-release-zip.ps1` und Tests angepasst werden muessen.

## Geaenderte Dateien

- `scripts/make-release-zip.ps1`
- `scripts/release.ps1`
- `tests/test_manual_test_assets.py`
- `README.md`
- `docs/release-v1-5.md`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- `make-release-zip.ps1` akzeptiert nun `-ReleaseName` und `-ReleaseTag`.
- Aus `-ReleaseTag v0.1.9-textual-workflow-preview-r3` wird `predigt-uploader-v0.1.9-textual-workflow-preview-r3.zip`.
- Ohne Parameter sucht das Skript einen passenden Git-Tag auf `HEAD`.
- Ohne passenden Tag faellt das Skript auf `predigt-uploader-v<pyproject-version>-local.zip` zurueck.
- Das Skript gibt Release-Name und ZIP-Ziel am Anfang aus.
- `scripts/release.ps1` fuehrt erst Tests aus und erstellt das ZIP nur bei Erfolg.
- Die Tests pruefen ReleaseItems, Ausschluesse und dynamische Namenslogik statt eines festen Preview-Suffixes.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 263 passed
- `.\scripts\make-release-zip.ps1 -ReleaseTag v0.1.9-textual-workflow-preview-r3`
- Ergebnis: `dist\predigt-uploader-v0.1.9-textual-workflow-preview-r3.zip` erstellt.

## Offene Punkte / Risiken

- Der empfohlene Ablauf setzt voraus, dass Release-Tags sauber auf dem Commit liegen, der ausgeliefert werden soll.

## Nächster sinnvoller Schritt

Vor dem naechsten Preview-Release committen, Git-Tag setzen und dann `.\scripts\make-release-zip.ps1` ohne Parameter testen.
