# Entwicklungsbericht: Windows-Starter Encoding

## Ziel

Kaputte Umlaute in den anklickbaren Windows-Startern und PowerShell-Ausgaben vermeiden.

## Geänderte Dateien

- `PredigtUploader starten.cmd`
- `PredigtUploader einrichten.cmd`
- `PredigtUploader Systemcheck.cmd`
- `scripts/setup-local.ps1`
- `scripts/check-system.ps1`
- `scripts/run-wizard.ps1`
- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/install-v1-5.md`
- `tests/test_manual_test_assets.py`

## Was wurde umgesetzt?

- Die `.cmd`-Dateien setzen vor der Ausgabe `chcp 65001 >nul`.
- Die PowerShell-Skripte initialisieren `Console.OutputEncoding`, `Console.InputEncoding` und `$OutputEncoding` auf UTF-8.
- Kritische sichtbare Startertexte in PowerShell wurden ASCII-sicher formuliert, zum Beispiel `Abhaengigkeiten`, `verfuegbar`, `Systempruefung` und `Naechster`.
- Dokumentation und Status erwähnen den Encoding-Schutz.
- Tests prüfen Codepage, Encoding-Initialisierung und ASCII-sichere Startertexte.

## Tests

- PowerShell-Syntaxprüfung für `setup-local.ps1`, `check-system.ps1` und `run-wizard.ps1`
- `python -m pytest`
- Ergebnis: 105 bestanden

## Offene Punkte / Risiken

- Die eigentliche Python-Wizard-Ausgabe enthält weiterhin normale deutsche Umlaute; die aktuelle Aufgabe betraf die Windows-Starter und PowerShell-Ausgaben.
- Sehr alte Windows-Konsolen können UTF-8 trotzdem unterschiedlich darstellen, deshalb bleiben die kritischen Startermeldungen ASCII-sicher.

## Nächster sinnvoller Schritt

Die drei `.cmd`-Dateien per Doppelklick auf dem Zielrechner testen und prüfen, ob die Ausgabe lesbar bleibt.
