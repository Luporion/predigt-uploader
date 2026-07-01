# Entwicklungsbericht: textual-konfliktentscheidung

## Ziel

Die finale Textual-Pruefseite soll bei vorhandenen Zieldateien klar zeigen, was passiert und welche Entscheidung noetig ist.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Die Konfliktliste wurde kompakter als MP4, MP3 und Zusammenfassung dargestellt.
- Bei vorhandenen Zieldateien erscheint rechts ein eigener Achtung-Bereich mit klaren Optionen.
- "Vorhandene Dateien ersetzen" ist jetzt ein bewusster Button und setzt intern `mp4_action="overwrite"` sowie `overwrite_existing_outputs=True`.
- Der finale Button bleibt gesperrt, bis diese Entscheidung bewusst getroffen wurde.
- Die Zurueck-Aktion fuehrt von der finalen Pruefung wieder zur Zielordnerpruefung.

## Tests

- `.\scripts\test.ps1`
- Ergebnis: 253 passed

## Offene Punkte / Risiken

- Die Darstellung sollte noch einmal manuell im echten Textual-Terminal geprueft werden.

## Naechster sinnvoller Schritt

Textual mit einem vorhandenen Zielordner und vorhandenen Ziel-MP4/MP3-Dateien manuell durchspielen.
