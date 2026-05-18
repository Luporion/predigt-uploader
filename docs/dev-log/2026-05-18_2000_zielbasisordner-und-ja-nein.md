# Entwicklungsbericht: zielbasisordner-und-ja-nein

## Ziel

Die im manuellen Praxistest gefundenen Phase-1-Probleme beheben: kein fest verdrahteter Zielordner fuer einen bestimmten Windows-Benutzer und klarere Ja/Nein-Abfragen.

## Geänderte Dateien

- `src/predigt_uploader/config.py`
- `src/predigt_uploader/cli.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `config.example.toml`
- `docs/config.md`
- `docs/manual-test-v1.md`
- `SPEC.md`
- `STATUS.md`

## Was wurde umgesetzt?

- Der Standard-Zielbasisordner kommt ohne `config.toml` jetzt aus dem aktuellen Windows-Benutzer: `Path.home() / "Desktop" / "Aufnahmen"`.
- Der Wizard zeigt den Ziel-Basisordner vor der Ordnerpruefung an.
- Nutzer koennen im Wizard fuer den aktuellen Lauf einen anderen Ziel-Basisordner angeben.
- Der Ziel-Basisordner wird erstellt und per Schreibtest geprueft.
- Bei ungueltigen Pfaden, fehlenden Berechtigungen oder Schreibproblemen gibt es eine verstaendliche Meldung mit Admin-Hinweis.
- Nach einem Zielbasisordner-Fehler kann direkt ein anderer Ordner angegeben werden, ohne dass der Wizard hart abbricht.
- Ja/Nein-Fragen zeigen die erlaubten Eingaben klar an.
- Akzeptiert werden jetzt `j`, `ja`, `y`, `yes`, `n`, `nein`, `no`, jeweils unabhaengig von Gross-/Kleinschreibung.
- Enter verwendet weiterhin den angezeigten Standardwert.
- Dokumentation und Beispiel-Config wurden vom alten Benutzerpfad `C:\Users\micro` entkoppelt.

## Tests

- `python -m pytest`
- Ergebnis: 66 Tests bestanden.

## Offene Punkte / Risiken

- Der neue Zielbasisordner-Schritt sollte erneut manuell auf einem zweiten Windows-Benutzer getestet werden.
- `config.toml` kann weiterhin einen festen Zielbasisordner vorgeben; dieser wird beim Start angezeigt und kann pro Lauf ueberschrieben werden.

## Nächster sinnvoller Schritt

Den manuellen Phase-1-Test mit kleiner MP4 erneut nach `docs/manual-test-v1.md` ausfuehren.
