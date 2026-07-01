# Entwicklungsbericht: textual-verarbeitungsplan

## Ziel

Textual soll nach Datei-Auswahl und Metadaten nicht nur eine Vorschau zeigen, sondern einen echten Verarbeitungsplan anzeigen und testbar ausfuehren koennen, ohne die produktive Wizard-Bedienung zu gefaehrden.

## Geänderte Dateien

- `src/predigt_uploader/processing.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_processing.py`
- `tests/test_tui.py`
- `STATUS.md`

## Was wurde umgesetzt?

- Ein zentrales `PreparedRecordingPlan`-Datenobjekt mit Quelle, Zielordner, finalen Medienpfaden, Zusammenfassungspfad, Metadaten, Rohaufnahme-Aktion und Warnungen wurde ergaenzt.
- Eine zentrale `execute_processing_plan`-Funktion bereitet Zielordner, MP4, MP3, Zusammenfassung, Rohaufnahme-Aktion und optionales Zielordner-Oeffnen mit Statusmeldungen vor.
- Textual zeigt nach erfolgreicher Metadatenpruefung eine finale Seite `Vorbereitung pruefen` mit Plan, Warnungen und dem Button `Dateien jetzt vorbereiten`.
- Textual zeigt waehrend der Ausfuehrung Statusmeldungen im rechten Statusbereich an.
- Die bestehende breite Startcheck-Seite wurde nicht umgestaltet.

## Tests

- Vor den Aenderungen: `.\scripts\test.ps1` mit 212 passed.
- Nach den Aenderungen: `.\scripts\test.ps1` mit 219 passed.

## Offene Punkte / Risiken

- Die produktive Wizard-Bedienlogik wurde bewusst nicht gross umgebaut. Der neue Verarbeitungsservice wird zunaechst von Textual genutzt und ist fuer weitere vorsichtige CLI-Refactorings vorbereitet.
- Textual fuehrt die Dateioperationen synchron aus; fuer sehr grosse Dateien kann spaeter ein echter Hintergrund-Worker sinnvoll werden.
- Manuelle Zielrechner-Tests bleiben wichtig, besonders fuer FFmpeg, Explorer-Oeffnen und Rohaufnahme-Aktion.

## Nächster sinnvoller Schritt

Textual auf dem Zielrechner mit einer kleinen echten MP4 testen: finale Pruefseite, Statusmeldungen, MP3-Erstellung, Zusammenfassung, Zielordner-Oeffnen und Fehleranzeige bei fehlendem FFmpeg.
