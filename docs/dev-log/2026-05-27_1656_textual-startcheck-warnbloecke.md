# Entwicklungsbericht: textual-startcheck-warnbloecke

## Ziel

Die Fragen der Textual-Sicherheitsseite sollen im Terminal deutlich groesser und auffaelliger wirken.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-27_1656_textual-startcheck-warnbloecke.md`

## Was wurde umgesetzt?

- Die Fragen `AUFNAHME IN VMIX BEENDET?` und `STREAM IN VMIX BEENDET?` werden als getrennte Warnbloecke dargestellt.
- Beide Fragen nutzen Grossbuchstaben, zentrierte Ausrichtung, schweren Rahmen und mehr vertikalen Abstand.
- Der Datenvolumen-/Kostenhinweis bleibt als eigener Warnbereich sichtbar.
- Der Standardfokus bleibt auf `Nein, erst in vMix pruefen`.

## Tests

- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Textual-Terminals koennen keine echte Schriftgroesse garantieren; die optische Groesse entsteht ueber Rahmen, Abstand und Grossbuchstaben.

## Naechster sinnvoller Schritt

Die Sicherheitsseite im Zielterminal manuell anschauen und bei Bedarf die Panelhoehe oder Buttonbreite nachjustieren.
