# Entwicklungsbericht: geschnittene MP4-Auswahl

## Ziel

Den Workflow fuer Nutzer verbessern, die bereits eine fertig geschnittene MP4-Datei haben: sichtbarer Standardordner, Auswahlmenue, bevorzugte geschnittene Dateien und optionales Merken eines abweichenden Ordners.

## Geänderte Dateien

- `src/predigt_uploader/models.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/cli.py`
- `tests/test_config.py`
- `tests/test_cli.py`
- `config.example.toml`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-21_2330_geschnittene-mp4-auswahl.md`

## Was wurde umgesetzt?

- Neue optionale Config-Einstellung `paths.cut_mp4_folder` ergaenzt.
- Bei bereits fertiger MP4 zeigt der Wizard einen vorgeschlagenen Ordner statt eines leeren Pfadprompts.
- Standardordner-Prioritaet: gemerkter `cut_mp4_folder`, danach `vmix_storage`, danach `recordings_base`.
- Im vorhandenen Standardordner gibt es ein Menue fuer Suche/Auswahl, neueste geschnittene MP4, neueste MP4-Liste, manuelle Eingabe und Zurueck.
- Dateien mit `_geschnitten`, `geschnitten` oder finalem Predigt-Dateinamen werden bevorzugt.
- Wenn keine eindeutig geschnittene Datei gefunden wird, bleibt die MP4-Auswahl moeglich und der Wizard warnt verstaendlich.
- Ein manuell eingegebener Ordner kann unter `%APPDATA%\PredigtUploader\config.toml` gemerkt werden.

## Tests

- `python -m pytest` erfolgreich: 161 passed.

## Offene Punkte / Risiken

- Der Workflow bleibt terminalbasiert. Eine echte Windows-Dateiauswahl ist weiterhin bewusst nicht Teil dieser Aufgabe.

## Nächster sinnvoller Schritt

Den Ablauf auf dem Zielrechner mit echten vMix-/LosslessCut-Ordnern manuell pruefen, besonders `Zurueck`, Textmodus und das Merken von `cut_mp4_folder`.
