# Entwicklungsbericht: Textual-Feinschliff

## Ziel

Allgemeine Nutzertexte nach der Einführung von Dienstarten bereinigen und den experimentellen Textual-Prototyp vorsichtig nutzbarer machen, ohne den produktiven Terminal-Wizard zu ersetzen.

## Geänderte Dateien

- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/config.md`
- `docs/install-v1-5.md`
- `docs/manual-test-v1-5.md`
- `docs/workflow-current.md`
- `docs/workflow-target-v1.md`
- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/report.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_cli.py`
- `tests/test_tui.py`

## Was wurde umgesetzt?

- Feste Begriffe wie Predigtdaten, Predigtbereich und exportierte Predigt-MP4 wurden an fachlich allgemeinen Stellen auf Aufnahme, Veranstaltung bzw. MP4 verallgemeinert.
- Die Zusammenfassung nennt nun `Datum der Aufnahme` und die WordPress-Hinweise sind allgemeiner formuliert.
- Der Textual-Prototyp zeigt eine klarere Metadaten-Vorschau mit Hinweis, dass er experimentell ist.
- Die Textual-Vorschau zeigt jetzt MP4-Dateiname, MP3-Dateiname und Zielordner.
- Ein einfacher Textual-Einstellungen-Screen zeigt Ziel-Basisordner, Rohaufnahme-Ordner, LosslessCut-Pfad, Jahresordner-Format und Rohaufnahme-Aufräumen-Standard.
- Testbare Helfer für Textual-Vorschau und Einstellungen-Anzeige wurden ergänzt, ohne Textual als Pflichtimport für den normalen Wizard zu machen.
- README, Installationsanleitung, manuelle Testanleitung, Status und Aufgabenliste wurden aktualisiert.

## Tests

- `python -m pytest`
- Ergebnis: `182 passed`

## Offene Punkte / Risiken

- Textual bleibt ein Prototyp und bildet noch nicht den vollständigen produktiven Workflow ab.
- Die Einstellungen im Textual-Screen sind vorerst nur lesbar; Änderungen laufen weiterhin über den normalen Wizard.
- Alte Dev-Log-Dateien enthalten historische Begriffe wie Predigtbereich weiterhin bewusst unverändert.

## Nächster sinnvoller Schritt

Den Terminal-Wizard auf dem Gemeinderechner mit mehreren Dienstarten praktisch testen und den Textual-Prototyp nur ergänzend für Vorschau und Navigation ausprobieren.
