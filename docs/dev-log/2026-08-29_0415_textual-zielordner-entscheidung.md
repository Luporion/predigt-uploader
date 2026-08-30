# Entwicklungsbericht: textual-zielordner-entscheidung

## Ziel

Den Zustand „neuer Ordner mit Zusatz“ in Textual-Schritt 6 als eindeutige Entscheidung darstellen, ohne die responsive Scroll- und Bottom-Action-Struktur zu verschlechtern.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`

## Was wurde umgesetzt?

- Schritt 6 besitzt nun einen einzigen dynamischen grossen Primaerbutton.
- Im Normalzustand bestaetigt er weiterhin den vorhandenen Tagesordner.
- Nach „Neuen Ordner mit Zusatz erstellen“ bestaetigt er stattdessen den neuen Zusatzordner.
- Die bisherige Sekundaeraktion wechselt in diesem Zustand zu „Doch vorhandenen Tagesordner verwenden“.
- Das Zusatzfeld bleibt sichtbar und fokussiert; leere oder reine Leerzeichen deaktivieren die Primaeraktion.
- Der rechte Status zeigt live den vollstaendigen Zielpfad aus der gemeinsamen `suggest_folder`-Fachlogik.
- Existiert der berechnete Zusatzordner bereits, wird dies orange und ausdruecklich gemeldet. Die Dateikonfliktpruefung in Schritt 7 bleibt bestehen.
- Beim Rueckwechsel werden Status, Primaeraktion und Zusatzfeld wieder auf den normalen Tagesordnerzustand gesetzt.
- Der direkte horizontale Inhalt des Schritt-6-Scrollcontainers und seine beiden Panels verwenden inhaltsabhaengige Hoehen. Dadurch erzeugen lange Pfade bei kleinen Terminals echten Overflow, statt das Zusatzfeld ausserhalb eines nicht scrollbaren `1fr`-Bereichs abzulegen.

## Tests

- Logiktests fuer Live-Zielpfad, leeren Zusatz und bereits vorhandenen Zusatzordner.
- Bestehende Tests fuer fehlende, einzelne und mehrere Tagesordner bleiben erhalten.
- Textual-Pilot bei `100x32` fuer Normalzustand, Moduswechsel, Fokus, dynamische Primaeraktion, Live-Pfad, leeren Zusatz, vorhandenen Zusatzordner, Rueckwechsel, beide Bestaetigungsrouten, Scrollbarkeit und sichtbare Bottom-Actions.
- Gesamter TUI-Testbestand: 87 Tests bestanden.
- Komplette Testsuite ueber `.\scripts\test.ps1`: 290 Tests bestanden.

## Offene Punkte / Risiken

- Sehr lange Netzwerkpfade koennen im Status mehr Zeilen benoetigen; sie liegen bewusst im scrollbaren Inhaltsbereich und sollten auf dem Zielrechner einmal visuell geprueft werden.
- Die Textual-Oberflaeche bleibt experimentell. Der produktive Wizard wurde nicht veraendert.

## Nächster sinnvoller Schritt

Schritt 6 auf dem Zielrechner einmal mit kurzem Zusatz, langem Zusatz und einem bereits vorhandenen Zusatzordner bei normaler sowie kleiner Fensterhoehe durchklicken.
