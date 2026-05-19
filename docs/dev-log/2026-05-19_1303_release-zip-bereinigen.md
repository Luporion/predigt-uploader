# Entwicklungsbericht: Release-ZIP bereinigen

## Ziel

Automatisch erzeugte Python-Packaging-Artefakte aus der lokalen Release-ZIP ausschließen.

## Geänderte Dateien

- `scripts/make-release-zip.ps1`
- `docs/release-v1-5.md`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- `scripts/make-release-zip.ps1` entfernt jetzt zusätzlich `build`, `*.egg-info` und `*.pyc` aus dem Staging-Ordner.
- Dadurch wird insbesondere `src/predigt_uploader.egg-info/` nicht mehr in die Release-ZIP übernommen.
- Die Release-Doku nennt die zusätzlichen Build-/Packaging-Ausschlüsse.
- Tests prüfen die neuen Ausschlussregeln im Skript und in der Doku.

## Tests

- PowerShell-Syntaxprüfung für `scripts/make-release-zip.ps1`
- `python -m pytest`
- Ergebnis: 107 bestanden

## Offene Punkte / Risiken

- Die ZIP wurde in dieser Aufgabe nicht neu gebaut; die Änderung betrifft das Release-Skript für den nächsten Build.

## Nächster sinnvoller Schritt

`scripts/make-release-zip.ps1` erneut ausführen und die ZIP kurz prüfen, ob `src/predigt_uploader.egg-info/` nicht mehr enthalten ist.
