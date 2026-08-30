# Entwicklungsbericht: textual-blindtest-nutzerfuehrung

## Ziel

Die Textual-Oberflaeche soll nach einem Blindtest verstaendlichere Begriffe, sichtbare Schritte, klare Zurueck-Navigation und weniger unnoetige Bestaetigungen verwenden.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `src/predigt_uploader/folders.py`
- `tests/test_tui.py`
- `tests/test_folders.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Textual zeigt `Gottesdienst` als Veranstaltungsart, speichert intern aber weiterhin `Predigt` und nutzt das bestehende Predigt-Dateinamenschema.
- Alte Werte `Predigt` bleiben kompatibel.
- Die Hauptschritte sind als `Schritt X/7` beschriftet.
- Jede Workflow-Seite erklaert Aufgabe, Wirkung des naechsten Klicks und die Zurueck-Moeglichkeit.
- Die Quellenwahl verwendet konkrete Aktionen statt Ja/Nein.
- Datei-, Export-, Zielordner- und Finalbuttons sind konkreter benannt.
- Textual verwendet fuer Rohaufnahmen `liegen lassen` als sicheren Standard; Verschieben muss bewusst ausgewaehlt werden.
- Es wird kein unbekanntes `-1` an Gottesdienst-Ordner angehaengt. Ein zentraler Marker-Hook in `folders.py` haelt kuenftige Regeln an einer Stelle.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 269 passed

## Offene Punkte / Risiken

- Schrittanzeige, Buttonpositionen und der sichere Rohaufnahme-Standard sollten in einem erneuten Blindtest praktisch geprueft werden.

## Nächster sinnvoller Schritt

Einen kompletten Textual-Durchlauf mit fertiger MP4 sowie einen Rohaufnahme-Durchlauf mit LosslessCut durch einen Nutzer ohne Vorwissen testen lassen.
