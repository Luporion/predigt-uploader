# Entwicklungsbericht: TUI-Umbenennen-Scroll-Race

## Ziel

Die im Konfliktscreen dynamisch eingeblendeten Felder für neue Dateinamen sollen nach Klick auf „Neue Dateien umbenennen“ zuverlässig fokussiert und sichtbar sein. Der reproduzierbar flakey Textual-Pilot-Test darf weder entfernt noch in seiner Sichtbarkeitsprüfung abgeschwächt werden.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- diese Datei

## Was wurde umgesetzt?

Die bisherige Ereigniskette kombinierte einen sofort angestoßenen Fokus mit eigenem Auto-Scroll, `call_after_refresh` und zwei festen Timern. Gleichzeitig blendete `display = True` die Felder ein und die aktualisierte Dateivorschau veränderte erneut das Layout. Je nach Reihenfolge konnten die Timer noch auf alten Regionen arbeiten oder `wait_for_animation()` im Test zurückkehren, bevor der verzögert geplante Scroll überhaupt als Animation registriert war.

Der Konfliktscreen führt die Schritte jetzt in einer eindeutigen Reihenfolge aus:

1. Umbenennen-Modus setzen und Felder einblenden.
2. Vorschau und Validierungsstatus vollständig aktualisieren.
3. Über Textuals `call_after_refresh` das abgeschlossene Layout abwarten.
4. Das erste MP4-Namensfeld mit `scroll_visible=False` fokussieren, damit kein konkurrierender Fokus-Scroll entsteht.
5. Das Feld über `scroll_visible()` mit Textuals eigener Scrollanimation sichtbar machen.

Die beiden zeitbasierten Timer wurden entfernt. Der Pilot-Test wartet zustandsbasiert darauf, dass `can_view_partial()` wahr ist, und führt anschließend weiterhin dieselbe explizite Sichtbarkeits-Assertion aus.

Vimeo-TUS-, Resume-, Upload-, Polling- und Credential-Logik wurden für diese Korrektur nicht verändert.

## Tests

- Zieltest in zehn getrennten pytest-Läufen: **10/10 bestanden**.
- Vollständige Suite über `.\scripts\test.ps1`: **399 Tests bestanden**.
- `git diff --check`: erfolgreich; nur die bekannten LF/CRLF-Hinweise wurden ausgegeben.

## Offene Punkte / Risiken

Keine bekannte offene Race in diesem Ablauf. Der Test prüft weiterhin bei 100×32 Terminalzellen, dass die Bottom-Actions sichtbar bleiben und das erste dynamische Namensfeld tatsächlich erreichbar ist.

## Nächster sinnvoller Schritt

Den Konfliktscreen einmal manuell bei kleiner Terminalhöhe öffnen, „Neue Dateien umbenennen“ anklicken und Fokus, sichtbares MP4-Feld sowie Tab-Reihenfolge kurz bestätigen. Danach kann die bereits vorbereitete Vimeo-Fortschrittsanzeige mit einer größeren MP4 manuell geprüft werden.
