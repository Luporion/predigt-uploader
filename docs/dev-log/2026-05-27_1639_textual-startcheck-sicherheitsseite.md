# Entwicklungsbericht: textual-startcheck-sicherheitsseite

## Ziel

Der Textual-Startcheck fuer beendete vMix-Aufnahme und beendeten Stream soll deutlicher und sicherer werden, ohne den produktiven normalen Wizard zu ersetzen.

## Geaenderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-27_1639_textual-startcheck-sicherheitsseite.md`

## Was wurde umgesetzt?

- Der Textual-Startcheck ist nun eine eigene grosse Sicherheitsseite mit der Ueberschrift `WICHTIGER CHECK VOR DEM START`.
- Aufnahme- und Stream-Frage sowie der Hinweis zu Datenvolumen/Kosten werden optisch gerahmt dargestellt.
- Die sichere Aktion `Nein, erst in vMix pruefen` steht zuerst und bekommt beim Oeffnen den Fokus.
- `Ja, Aufnahme und Stream sind beendet` fuehrt erst danach zur Quelle-/Dateiauswahl.
- Die Texte sind als zentrale Konstanten in der Textual-Logik gehalten.

## Tests

- `python -m pytest tests/test_tui.py` -> 26 passed
- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Textual bleibt Preview und startet weiterhin keine produktive Dateiuebernahme.
- Die genaue optische Wirkung sollte am Zielrechner im echten Terminal gegengeprueft werden.

## Naechster sinnvoller Schritt

Textual manuell starten und pruefen, ob die Sicherheitsseite fuer normale Nutzer sofort auffaellt und der Fokus sichtbar auf `Nein` liegt.
