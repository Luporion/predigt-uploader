# Entwicklungsbericht: dateiname-vorschau-textual

## Ziel

Freitag als Gebetsstunde vorauswaehlen, eine zentrale Dateiname-Vorschau fuer Metadaten bereitstellen und Textual als optionale experimentelle Oberflaeche vorbereiten.

## Geänderte Dateien

- `README.md`
- `TASKS.md`
- `STATUS.md`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `pyproject.toml`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/filename.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_cli.py`
- `tests/test_filename.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-22_0109_dateiname-vorschau-textual.md`

## Was wurde umgesetzt?

- Dienstart-Standard erweitert: Sonntag Predigt, Mittwoch Bibelstunde, Freitag Gebetsstunde, sonst Predigt.
- `build_filename_preview(...)` als zentrale Vorschaufunktion mit MP4- und MP3-Namen ergaenzt.
- Fehlende Vorschau-Felder bleiben sichtbar als `[Titel]`, `[Bibelstelle]`, `[Redner]` oder `[Leitung]`.
- Terminal-Wizard zeigt nach Dienstartauswahl und fachlichen Eingaben eine kompakte Dateiname-Vorschau.
- Optionales Extra `tui = ["textual>=0.80"]` ergaenzt.
- Neues CLI-Kommando `python -m predigt_uploader tui` bzw. `textual` ergaenzt.
- Neuer Textual-Prototyp mit Startscreen und Metadaten-Vorschau angelegt, ohne den normalen Wizard zu ersetzen.
- Fehlendes Textual wird verstaendlich gemeldet.

## Tests

- `python -m pytest` erfolgreich: 180 passed.
- Keine PowerShell-Syntaxpruefung noetig, da in dieser Aufgabe keine `.ps1`- oder `.cmd`-Datei geaendert wurde.

## Offene Punkte / Risiken

- Die Textual-Oberflaeche ist bewusst nur ein Prototyp und bildet den produktiven Workflow noch nicht vollstaendig ab.
- Textual wird nur ueber das optionale Extra installiert; normale Gemeinde-Nutzung bleibt beim Terminal-Wizard.

## Nächster sinnvoller Schritt

Den Textual-Prototyp in einer Entwicklungsumgebung mit `pip install -e .[tui]` manuell starten und die Live-Vorschau interaktiv pruefen.
