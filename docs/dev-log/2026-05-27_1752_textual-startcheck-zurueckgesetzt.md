# Entwicklungsbericht: textual-startcheck-zurueckgesetzt

## Ziel

Die Textual-Startcheck-Seite soll wieder die breite, ruhige Warnseiten-Darstellung aus dem vorherigen Stand nutzen.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-27_1752_textual-startcheck-zurueckgesetzt.md`

## Was wurde umgesetzt?

- Der kompakte ASCII-/Checklisten-Banner wurde entfernt.
- Die Sicherheitsseite zeigt wieder einen breiten Titelrahmen, ein gemeinsames Fragenpanel und ein Warnpanel.
- Die Buttons bleiben unten getrennt.
- Der Standardfokus bleibt auf `Nein, erst in vMix pruefen`.

## Tests

- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Textual kann weiterhin keine echte Schriftgroesse pro Widget garantieren; die Hervorhebung erfolgt ueber Rahmen, Abstand und Textposition.

## Naechster sinnvoller Schritt

Die Darstellung im Zielterminal visuell pruefen und nur noch kleine Abstands-/Breitenkorrekturen vornehmen.
