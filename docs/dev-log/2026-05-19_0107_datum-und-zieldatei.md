# Entwicklungsbericht: Datum und Zieldatei

## Ziel

Datumsauswahl im Wizard laientauglicher machen und vorhandene finale MP4-Dateien sicherer behandeln.

## Geänderte Dateien

- `src/predigt_uploader/cli.py`
- `src/predigt_uploader/ui.py`
- `tests/test_cli.py`
- `tests/test_ui.py`
- `TASKS.md`
- `STATUS.md`
- `docs/manual-test-v1-5.md`

## Was wurde umgesetzt?

- Der Wizard bietet jetzt eine Datumsauswahl statt nur freier Texteingabe.
- Typische vMix-Dateinamen mit deutschen Monatsnamen werden für das Aufnahmedatum ausgewertet.
- Falls kein Aufnahmedatum erkannt wird, kann das Dateidatum angeboten werden.
- Heutiges Datum und manuelle Datumseingabe bleiben auswählbar.
- Vorhandene finale MP4-Dateien werden per Auswahl behandelt: behalten, neuer Name, abbrechen oder überschreiben.
- Überschreiben ist nicht Standard und braucht eine zweite Sicherheitsbestätigung.
- Der Text-Fallback akzeptiert die gewünschten Kürzel und Wörter für Überschreiben.

## Tests

- `python -m pytest`
- Ergebnis: 99 bestanden

## Offene Punkte / Risiken

- Die Datumserkennung deckt bewusst einfache deutsche vMix-Dateinamen ab; weitere Namensmuster können später ergänzt werden.
- Vollständige LosslessCut- oder Vimeo-/WordPress-Automatisierung wurde nicht eingebaut.

## Nächster sinnvoller Schritt

Phase 1.5 erneut manuell mit einer echten vMix-Datei testen, besonders Datumsvorschlag und vorhandene Zieldatei.
