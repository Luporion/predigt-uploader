# Entwicklungsbericht: textual-dateiauswahl-validierung

## Ziel

Die experimentelle Textual-Oberflaeche soll Datei-Auswahl und Metadatenpruefung besser bedienbar machen, ohne den produktiven normalen Wizard zu ersetzen.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-26_1918_textual-dateiauswahl-validierung.md`

## Was wurde umgesetzt?

- Eine wiederverwendbare MP4-Auswahlkonfiguration fuer geschnittene MP4-Dateien und Rohaufnahmen wurde ergaenzt.
- Die Textual-Dateiauswahl zeigt MP4-Dateien nun als Tabelle mit Dateiname, Aenderungsdatum und Groesse statt als Dateiknoepfe.
- Neueste Datei, Tabellen-Auswahl, Suche/Filter sowie manuelle Datei- oder Ordner-Eingabe sind in derselben Auswahloberflaeche verfuegbar.
- Fehlende Metadaten-Pflichtfelder werden direkt in den Feldbeschriftungen markiert.
- Der Pruefbutton wird deaktiviert, solange Pflichtfelder fehlen, und die Vorschau zeigt einen klaren Bitte-ergaenzen-Hinweis.

## Tests

- `python -m pytest tests/test_tui.py` -> 24 passed
- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Textual bleibt bewusst eine Preview. Dateiuebernahme, LosslessCut, FFmpeg und Rohaufnahme-Aufraeumen bleiben beim normalen Wizard.
- Die manuelle Textual-Dateiauswahl nutzt vorerst Pfadeingabe statt nativen Windows-Dateidialog.

## Naechster sinnvoller Schritt

Textual auf dem Zielrechner manuell mit echten Rohaufnahme- und Schnittordnern pruefen und danach entscheiden, ob weitere Wizard-Schritte als reine Vorschau vorbereitet werden sollen.
