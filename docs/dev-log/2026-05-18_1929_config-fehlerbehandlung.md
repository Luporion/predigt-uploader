# Entwicklungsbericht: Config-Fehlerbehandlung

## Ziel

Config-Fehler im Phase-1-CLI-Wizard nutzerfreundlich behandeln und Python-Tracebacks fuer normale Nutzer vermeiden.

## Geänderte Dateien

- `src/predigt_uploader/config.py`
- `src/predigt_uploader/cli.py`
- `tests/test_config.py`
- `tests/test_cli.py`
- `TASKS.md`
- `STATUS.md`
- `docs/dev-log/2026-05-18_1929_config-fehlerbehandlung.md`

## Was wurde umgesetzt?

- `ConfigLoadError` fuer fachliche Config-Ladefehler ergaenzt.
- Angegebene, fehlende Config-Dateien fuehren zu einer verstaendlichen Meldung.
- Nicht lesbare Config-Dateien fuehren zu einer verstaendlichen Meldung.
- Ungueltiges TOML fuehrt zu einer verstaendlichen Meldung.
- Technische Details stehen nur im Admin-Hinweis.
- Der Wizard bricht bei Config-Problemen kontrolliert ab.
- Ohne angegebene Config werden weiterhin Standardwerte genutzt.
- Keine Vimeo- oder WordPress-Automatisierung ergaenzt.
- `TASKS.md` und `STATUS.md` aktualisiert.

## Tests

- `python -m pytest`
- Ergebnis: `41 passed in 0.19s`

## Offene Punkte / Risiken

- Die Logdatei-Anforderung aus `SPEC.md` ist weiterhin offen.

## Nächster sinnvoller Schritt

Klaeren und umsetzen, wie die Version-1-Logdatei geschrieben werden soll.
