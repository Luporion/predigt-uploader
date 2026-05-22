# Entwicklungsbericht: Textual-Bedienbarkeit

## Ziel

Den experimentellen Textual-Prototyp lesbarer und bedienbarer machen, ohne den produktiven Terminal-Wizard zu ersetzen oder den Gesamtworkflow umzubauen.

## Geänderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`

## Was wurde umgesetzt?

- Der Startscreen zeigt nun neben den Buttons einen Statusbereich mit Hinweis auf die experimentelle Oberfläche, den normalen Wizard als produktiven Workflow sowie Ziel-Basisordner und Rohaufnahme-Ordner.
- Der Metadaten-Screen hat sichtbare Labels für Dienstart, Datum, Titel, Hauptbibelstelle und Redner/Leitung.
- Je nach Dienstart werden nicht benötigte oder optionale Felder klar markiert und im Prototyp passend deaktiviert.
- Die Live-Vorschau ist klarer getrennt in MP4-Dateiname, MP3-Dateiname und Zielordner.
- Der Hinweis auf den normalen Wizard ist jetzt eine feste Hinweisbox im Screen statt wiederholter Toast-Meldungen.
- Die Einstellungen-Ansicht bleibt reine Anzeige mit klaren Labels.
- Tests prüfen weiter, dass Textual optional bleibt und die neuen TUI-Helfer ohne Pflichtimport von Textual funktionieren.

## Tests

- `python -m pytest`
- Ergebnis: `185 passed`

## Offene Punkte / Risiken

- Der Textual-Prototyp bildet weiterhin nicht den vollständigen Workflow ab.
- Die Feld-Deaktivierung ist bewusst einfacher Prototyp-Stand; spätere UI-Arbeit kann die Felder noch dynamischer ein-/ausblenden.

## Nächster sinnvoller Schritt

Den Prototyp mit installiertem `.[tui]` manuell starten und prüfen, ob Navigation, Fokus und Feldzustände im echten Terminal angenehm wirken.
