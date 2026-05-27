# Entwicklungsbericht: textual-startcheck-banner

## Ziel

Die Textual-Sicherheitsseite soll nicht durch grosse leere Rahmen auffallen, sondern durch gut lesbare zentrale Fragen.

## Geaenderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/dev-log/2026-05-27_1728_textual-startcheck-banner.md`

## Was wurde umgesetzt?

- Die Startcheck-Seite nutzt nun einen kompakten ASCII-/Checklisten-Banner.
- Die Fragen `AUFNAHME IN VMIX BEENDET?` und `STREAM IN VMIX BEENDET?` stehen im Blickzentrum mit Leerzeilen und Checklisten-Markern.
- Die grossen getrennten leeren Frage-Panels wurden entfernt.
- Der sichere Standardfokus bleibt auf `Nein, erst in vMix pruefen`.

## Tests

- Voller Testlauf folgt ueber `.\scripts\test.ps1`.

## Offene Punkte / Risiken

- Terminal-Text kann weiterhin nicht wirklich pro Widget groesser skaliert werden; die Hervorhebung erfolgt ueber ASCII-Banner, Grossbuchstaben und Abstand.

## Naechster sinnvoller Schritt

Die Sicherheitsseite im Zielterminal visuell pruefen und entscheiden, ob die Bannerbreite fuer den Gemeinderechner passt.
