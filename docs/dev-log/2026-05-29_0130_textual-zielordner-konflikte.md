# Entwicklungsbericht: textual-zielordner-konflikte

## Ziel

Textual soll nach der Metadatenpruefung Zielordner und bestehende Zieldateien bewusst pruefen, bevor finale Dateien geschrieben werden.

## Geaenderte Dateien

- `src/predigt_uploader/processing.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_processing.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Die zentrale Planerzeugung unterstuetzt einen expliziten Zielordner-Override.
- `execute_processing_plan` verhindert vorhandene MP3- und Zusammenfassungsdateien ohne bewusste Ueberschreib-Erlaubnis.
- Textual zeigt nach den Metadaten eine Zielordner-Pruefseite mit fehlenden, einzelnen vorhandenen und mehreren vorhandenen Tagesordnern.
- Die finale Pruefseite erkennt vorhandene MP4, MP3 und Zusammenfassung und deaktiviert die Verarbeitung bis zur bewussten Ersetzen-Entscheidung.
- Bei bewusster Ersetzen-Entscheidung setzt Textual `mp4_action="overwrite"` und erlaubt bestehende Ausgabedateien.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 249 passed

## Offene Punkte / Risiken

- Die neue Textual-Zielordnerseite sollte noch manuell im Terminal mit echten Tagesordnern geprueft werden.
- Feingranulare Optionen wie "MP4 behalten, nur MP3 neu erstellen" sind bewusst noch nicht umgesetzt.

## Naechster sinnvoller Schritt

Textual manuell mit vorhandenen Tagesordnern und vorhandenen Ziel-MP4/MP3-Dateien testen.
