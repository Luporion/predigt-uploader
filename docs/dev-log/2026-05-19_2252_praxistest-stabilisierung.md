# Entwicklungsbericht: Praxistest-Stabilisierung

## Ziel

Die lokale Version 1.5/1.6 nach dem Gemeinderechner-Praxistest stabilisieren: Dateiauswahl, Suche, Zurueck-Logik, gemerkte Einstellungen, Jahresordnerstruktur, Wartehinweise und LosslessCut-Export-Erkennung verbessern.

## Geänderte Dateien

- `src/predigt_uploader/ui.py`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/folders.py`
- `src/predigt_uploader/models.py`
- `config.example.toml`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_folders.py`
- `tests/test_ui.py`
- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`

## Was wurde umgesetzt?

- Eindeutiger `BACK`-Sentinel fuer Datei-Unterauswahlen ergaenzt, damit „Zurueck“ keine zweite nummerierte Fallback-Liste ausloest.
- Questionary-Auswahlen lesbarer gestylt und Echo-Ausgaben nach erfolgreichen Auswahlen reduziert.
- Such-Fallback verbessert: leeres Suchfeld zeigt eine begrenzte vollstaendige Liste, Suchtext filtert wie erwartet.
- Benutzer-Config unter `%APPDATA%\PredigtUploader\config.toml` ergaenzt, damit Ziel-Basisordner, Rohaufnahme-Ordner und funktionierende LosslessCut-Pfade auf Wunsch gemerkt werden koennen.
- Log-Config-Ursprung klarer benannt: explizite Config, Projekt-Config, Benutzer-Config oder Standardconfig.
- `year_folder_template` eingefuehrt, z. B. fuer Jahresordner wie `2026 Video+Audio`.
- Kurze Bitte-warten-Hinweise fuer Kopieren, Verschieben, Rohaufnahme-Archivierung und MP3-Erzeugung ergaenzt.
- LosslessCut-Export-Erkennung priorisiert jetzt auch plausible Exportnamen mit Bezug zum Rohdateinamen.
- Dokumentation fuer AppData-Config, Jahresordner-Template, Suche, Textmodus und manuelle Tests aktualisiert.

## Tests

- `python -m pytest` erfolgreich: 138 bestanden.
- PowerShell-Syntaxpruefung fuer `scripts/make-release-zip.ps1` erfolgreich.

## Offene Punkte / Risiken

- Keine Vimeo- oder WordPress-Automatisierung enthalten.
- Die Terminal-Darstellung haengt weiterhin vom jeweiligen Windows-Terminal ab; bei Problemen kann `PREDIGT_UPLOADER_TEXT_UI=1` genutzt werden.
- AppData-Config speichert lokale Pfade nur nach Nutzerbestaetigung und gehoert nicht ins Repository.

## Nächster sinnvoller Schritt

Release-ZIP neu erstellen und den verbesserten Ablauf auf dem Gemeinderechner mit echten Ordnern, `year_folder_template = "{year} Video+Audio"` und AppData-Merkliste testen.
