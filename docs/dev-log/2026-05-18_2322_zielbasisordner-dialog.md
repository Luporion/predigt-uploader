# Entwicklungsbericht: zielbasisordner-dialog

## Ziel

Die Ziel-Basisordner-Auswahl im Phase-1-Wizard so verbessern, dass Nutzer direkt Enter oder einen eigenen Pfad eingeben koennen.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `tests/test_cli.py`
- `docs/manual-test-v1.md`
- `docs/config.md`
- `STATUS.md`

## Was wurde umgesetzt?

- Die erste Ziel-Basisordner-Frage ist keine Ja/Nein-Abfrage mehr.
- Der Wizard zeigt den Vorschlag an und erklaert: Enter verwendet den Vorschlag, ein eingegebener Pfad verwendet einen anderen Ordner.
- Eigene Pfade werden direkt als Ordnerpfad behandelt und nicht mehr als ungueltige Ja/Nein-Antwort.
- Wenn der Ziel-Basisordner noch nicht existiert, fragt der Wizard mit der vorhandenen Ja/Nein-Helferfunktion, ob der Ordner erstellt werden soll.
- Wenn der Nutzer das Erstellen ablehnt, kann direkt ein anderer Ziel-Basisordner eingegeben werden.
- Existierende Ordner werden per Schreibtest geprueft.
- Fehler beim Erstellen oder Schreiben werden nutzerfreundlich mit Admin-Hinweis gemeldet; danach kann ein anderer Ordner gewaehlt werden.
- Doku in `docs/manual-test-v1.md` und `docs/config.md` beschreibt den neuen Dialog.

## Tests

- `python -m pytest`
- Ergebnis: 67 Tests bestanden.

## Offene Punkte / Risiken

- Der verbesserte Dialog sollte im manuellen Praxistest mit einem echten alternativen Zielordner erneut ausprobiert werden.

## Nächster sinnvoller Schritt

Phase 1 erneut nach `docs/manual-test-v1.md` mit kleiner MP4 testen.
