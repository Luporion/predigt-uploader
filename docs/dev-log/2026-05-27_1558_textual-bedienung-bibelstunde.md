# Entwicklungsbericht: textual-bedienung-bibelstunde

## Ziel

Die experimentelle Textual-Oberflaeche soll in der Dateiauswahl und Metadatenpruefung besser bedienbar werden, ohne den produktiven normalen Wizard zu ersetzen.

## Geaenderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `SPEC.md`
- `config.example.toml`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/filename.py`
- `src/predigt_uploader/models.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_cli.py`
- `tests/test_filename.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-27_1558_textual-bedienung-bibelstunde.md`

## Was wurde umgesetzt?

- Die doppelte reine Textliste unter der Textual-MP4-Tabelle wurde entfernt.
- Die Textual-MP4-Tabelle hat eine feste Hoehe und wird beim Oeffnen fokussiert, damit Maus- und Tastaturbedienung klarer sind.
- Vor dem Textual-Startablauf erscheint ein bewusster Hinweis, ob Aufnahme und Stream in vMix beendet wurden.
- Im normalen Hauptmenue erscheint derselbe Hinweis vor dem Start des produktiven Wizards.
- Bibelstunde unterstuetzt nun optional eine Themenreihe im gemeinsamen Dateinamen: mit Titel `Bibelstunde (Titel_Bibelstelle)_Redner`, ohne Titel weiterhin `Bibelstunde (Bibelstelle)_Redner`.

## Tests

- `python -m pytest tests/test_filename.py tests/test_tui.py tests/test_cli.py` -> 165 passed
- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Textual bleibt Preview und fuehrt weiterhin keine Dateiuebernahme, FFmpeg-Erzeugung oder Rohaufnahme-Aufraeumung aus.
- Mausrad-Scrollen sollte auf dem Zielrechner manuell mit echter Dateiliste gegengeprueft werden.

## Naechster sinnvoller Schritt

Textual auf dem Gemeinderechner mit vielen MP4-Dateien testen und pruefen, ob Tabellenhoehe, Fokus und Suchfeld im echten Terminal angenehm sind.
