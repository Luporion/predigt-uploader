# Entwicklungsbericht: Startmenue und Einstellungen

## Ziel

Die lokale Bedienbarkeit fuer normale Gemeindemitarbeiter verbessern: ein einfaches Hauptmenue einfuehren, Einstellungen ohne manuelles Bearbeiten von `config.toml` anbieten, Jahresordner-Format einfacher waehlen und die Startueberschrift nutzerfreundlicher machen.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/models.py`
- `src/predigt_uploader/ui.py`
- `scripts/run-wizard.ps1`
- `config.example.toml`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_manual_test_assets.py`
- `tests/test_ui.py`
- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`

## Was wurde umgesetzt?

- Ohne CLI-Argument startet `predigt_uploader` jetzt ein Hauptmenue mit „Neue Predigt vorbereiten“, „Einstellungen ändern“, Systemcheck-Hinweis, Logdateien und Beenden.
- `scripts/run-wizard.ps1` startet nicht mehr hart `wizard`, sondern den Standard-Einstieg. Direkter Wizard-Start bleibt mit `wizard` moeglich.
- Startueberschrift wurde von „lokaler Version-1-Prototyp“ auf „PredigtUploader“ mit kurzer Nutzerbeschreibung umgestellt.
- Einstellungen-Menue speichert Ziel-Basisordner, Rohaufnahme-Ordner, LosslessCut-Pfad, Jahresordner-Format und Rohaufnahme-Aufraeumen unter `%APPDATA%\PredigtUploader\config.toml`.
- Jahresordner-Format kann als „nur Jahr“ oder „Jahr mit Zusatz“ gewaehlt werden; intern bleibt `year_folder_template` erhalten.
- `raw_archive_mode` als Workflow-Einstellung ergaenzt.
- Menue-Fallback unterstuetzt jetzt eine sichtbare Standardauswahl; Enter waehlt den markierten Standard.
- Dokumentation fuer Startmenue, Einstellungen und direkte Wizard-Nutzung aktualisiert.

## Tests

- `python -m pytest` erfolgreich: 154 bestanden.
- PowerShell-Syntaxpruefung fuer `scripts/run-wizard.ps1` erfolgreich.

## Offene Punkte / Risiken

- Das Hauptmenue ist bewusst nur Terminal-UI, keine GUI.
- Logdatei-/Logordner-Oeffnen nutzt `os.startfile` und ist damit auf Windows ausgerichtet; auf anderen Systemen erscheint nur ein Hinweis.
- Keine Vimeo- oder WordPress-Automatisierung enthalten.

## Nächster sinnvoller Schritt

Auf dem Gemeinderechner per Doppelklick testen: Hauptmenue oeffnen, Einstellungen setzen, danach „Neue Predigt vorbereiten“ starten und pruefen, ob die AppData-Config korrekt verwendet wird.
