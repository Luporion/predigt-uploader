# Entwicklungsbericht: textual-dienstart-datum

## Ziel

Die automatische Dienstart-Vorauswahl in Textual soll nicht mehr pauschal vom heutigen Datum abhaengen, sondern vom wirksamen Aufnahmedatum der gewaehlten Datei.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Neue Helfer bestimmen Datumsoptionen aus Rohaufnahme, geschnittener MP4, Dateidatum und heutigem Datum.
- Die bevorzugte Datumsquelle priorisiert Rohaufnahme-Dateinamen vor Schnittdatei-Dateinamen.
- Die Textual-Metadatenmaske initialisiert Datum und Dienstart aus der bevorzugten Datumsquelle.
- Solange die Dienstart nicht manuell geaendert wurde, folgt sie Datumswechseln automatisch.
- Die Export-Erkennungsgruende wurden verstaendlicher formuliert.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 240 passed

## Offene Punkte / Risiken

- Die Textual-Maske bleibt Preview und sollte weiter manuell auf dem Zielrechner geprueft werden.
- Dateinamen ohne deutsches Datum fallen weiterhin auf Dateidatum oder heute zurueck.

## Naechster sinnvoller Schritt

Den Rohaufnahme-Flow mit aelteren Mittwoch-/Freitag-/Sonntag-Aufnahmen in Textual manuell pruefen.
