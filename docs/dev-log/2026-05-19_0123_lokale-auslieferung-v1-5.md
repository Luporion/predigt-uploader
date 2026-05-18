# Entwicklungsbericht: lokale Auslieferung v1.5

## Ziel

Die lokale Phase 1.5 für einen Zielrechner vorbereiten, ohne Vimeo- oder WordPress-Automatisierung einzubauen.

## Geänderte Dateien

- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/install-v1-5.md`
- `scripts/setup-local.ps1`
- `scripts/check-system.ps1`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- `scripts/setup-local.ps1` erstellt bei Bedarf `.venv`, prüft Python 3.11+ und installiert den PredigtUploader mit Abhängigkeiten.
- `scripts/check-system.ps1` prüft Python, `.venv`, Startbarkeit des Wizards, FFmpeg und optional einen gesetzten `losslesscut_path`.
- `docs/install-v1-5.md` beschreibt Installation, FFmpeg, LosslessCut, `config.toml`, Start und Testdurchlauf auf einem Zielrechner.
- README, STATUS und TASKS wurden um die lokale Nutzung und Auslieferungsdateien ergänzt.
- Tests prüfen, dass die neuen Skripte und die Installationsdoku die wichtigsten Hinweise enthalten.

## Tests

- PowerShell-Syntaxprüfung für `setup-local.ps1` und `check-system.ps1`
- `python -m pytest`
- Ergebnis: 102 bestanden

## Offene Punkte / Risiken

- Die Skripte sind bewusst PowerShell-/Windows-orientiert.
- FFmpeg- und LosslessCut-Installation bleiben externe Schritte und werden nur geprüft, nicht automatisch installiert.

## Nächster sinnvoller Schritt

Auf einem Zielrechner `.\scripts\setup-local.ps1`, danach `.\scripts\check-system.ps1` ausführen und einen kleinen echten Phase-1.5-Testlauf machen.
