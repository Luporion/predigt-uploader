# Entwicklungsbericht: dienstarten-und-bedienhilfen

## Ziel

Metadaten-Eingabe, Suchfeld-Zurueck, Strg+C-Hinweise und fachliche Dienstarten fuer den lokalen Workflow verbessern.

## Geänderte Dateien

- `PredigtUploader starten.cmd`
- `scripts/run-wizard.ps1`
- `config.example.toml`
- `src/predigt_uploader/models.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/filename.py`
- `src/predigt_uploader/report.py`
- `src/predigt_uploader/ui.py`
- `src/predigt_uploader/cli.py`
- `tests/test_config.py`
- `tests/test_filename.py`
- `tests/test_ui.py`
- `tests/test_cli.py`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-22_0032_dienstarten-und-bedienhilfen.md`

## Was wurde umgesetzt?

- Metadaten-Hilfetext vor den fachlichen Eingaben ergaenzt.
- `Strg+C` wird im Starttext und Starter als Abbruch erklaert.
- Suchfelder zeigen eine Zurueck-Hilfe; im Textmodus funktionieren `zurück`, `z` und `back`.
- Dienstarten eingefuehrt: Predigt, Bibelstunde, Vortrag, Lobpreis, Gebetsstunde, Zeugnis, Seminar und Sonstiges.
- Standardauswahl: Sonntag Predigt, Mittwoch Bibelstunde, sonst Predigt.
- Dateinamen werden je Dienstart passend gebildet.
- Zusaetzliche Dienstarten koennen im Einstellungsmenue angelegt und in `%APPDATA%\PredigtUploader\config.toml` gespeichert werden.
- Zusammenfassung und WordPress-Hinweise verwenden jetzt allgemeinere Begriffe.

## Tests

- `python -m pytest` erfolgreich: 171 passed.
- PowerShell-Syntaxpruefung erfolgreich fuer `scripts/run-wizard.ps1`, `scripts/setup-local.ps1` und `scripts/check-system.ps1`.

## Offene Punkte / Risiken

- Zusaetzliche Dienstarten koennen in Version 1 hinzugefuegt, aber noch nicht komfortabel bearbeitet oder entfernt werden.
- Die `.cmd`-Windows-Rueckfrage nach `Strg+C` kann nicht vollstaendig verhindert werden; sie wird jetzt dokumentiert und vorab erklaert.

## Nächster sinnvoller Schritt

Manueller Zielrechner-Test mit Predigt, Bibelstunde, Vortrag/Lobpreis/Sonstiges sowie Zurueck aus Suchfeldern und `Strg+C`-Abbruch.
