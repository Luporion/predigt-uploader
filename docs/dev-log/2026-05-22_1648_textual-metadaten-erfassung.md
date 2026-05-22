# Entwicklungsbericht: textual-metadaten-erfassung

## Ziel

Textual als zweite Oberflaeche beim Metadaten-Teil produktiver machen, ohne den normalen Terminal-Wizard oder Dateiaktionen zu ersetzen.

## Geänderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `docs/dev-log/2026-05-22_1648_textual-metadaten-erfassung.md`

## Was wurde umgesetzt?

- Die Textual-Ansicht fuer neue Aufnahmen erfasst jetzt Datum, Dienstart, Titel/Bezeichnung, Hauptbibelstelle, Redner/Leitung und eine optionale Ordner-Besonderheit.
- Dienstarten kommen aus der Konfiguration inklusive zusaetzlicher Dienstarten.
- Die Vorauswahl beruecksichtigt den Wochentag: Sonntag Predigt, Mittwoch Bibelstunde, Freitag Gebetsstunde.
- Die Live-Vorschau zeigt Zielordner, finalen MP4-Dateinamen und finalen MP3-Dateinamen.
- Pflichtfelder werden passend zur Dienstart validiert; Bibelstunde und Gebetsstunde verlangen keinen Predigttitel, wenn die Dienstart das nicht vorsieht.
- Textual bleibt bewusst Metadaten-Erfassung und Vorschau. Dateiuebernahme, LosslessCut, FFmpeg und Rohaufnahme-Aufraeumen laufen weiterhin im normalen Wizard.

## Tests

- `python -m compileall -q src/predigt_uploader`
- `python -m pytest tests/test_tui.py`
- Ergebnis: `17 passed`
- `.\scripts\test.ps1`
- Ergebnis: `197 passed`

## Offene Punkte / Risiken

- Die Textual-Oberflaeche speichert die erfassten Metadaten noch nicht in einen produktiven Workflow.
- Ein manueller Start mit installiertem `.[tui]` sollte Navigation, Fokus und Lesbarkeit im echten Terminal pruefen.

## Nächster sinnvoller Schritt

Textual manuell starten und pruefen, ob die Metadaten-Erfassung fuer typische Dienstarten angenehm bedienbar ist.
