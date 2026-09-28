# Entwicklungsbericht: Textual-Test-Lifecycle-Races

## Ziel

Sporadische Fehler beim Mounten, Wechseln und Herunterfahren von Textual-Screens sollen ohne lange Sleeps, abgeschwächte Assertions oder Änderungen an Vimeo-/StreamingVideoProvider-Fachlogik beseitigt werden.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `docs/dev-log/2026-09-11_1927_textual-test-lifecycle-races.md`

## Was wurde umgesetzt?

Die Analyse zeigte zwei zusammenwirkende Lifecycle-Races mit Textual 8.2.7:

1. Der Vimeo-Ordnerbrowser und die Vimeo-Bibliothek starteten ihre Thread-Worker direkt in `on_mount`. Sehr schnelle Fake-Antworten konnten dadurch während des ersten Child-/DataTable-Layouts an die UI zurücklaufen. Beide Screens starten ihre initiale Cache-Anzeige beziehungsweise den initialen Worker nun über `call_after_refresh`.
2. Mehrere Tests verwendeten direktes `Button.press()` und verließen kurz nach Screenwechseln den `run_test`-Kontext. Die gemeinsame Test-Synchronisation wartet nun einen stabilen, gemounteten Screen über Textuals eigene Idle-/Message-Queue-Zyklen ab. Für erwartete Hintergrundarbeit werden registrierte Textual-Worker und anschließend deren UI-Callbacks abgewartet. Sichtbare Aktionen verwenden `Pilot.click`; bei kleinen Terminals außerhalb des Maus-Viewports wird die vorhandene Tastaturbedienung über Fokus und `Pilot.press("enter")` geprüft.

Der kombinierte Leer-/Fehlertest der Vimeo-Bibliothek wurde parametrisiert. Jeder Fall besitzt dadurch genau einen Textual-App-Lifecycle und einen `asyncio.run`-Eventloop. Das verhindert, dass noch auslaufende Framework-Callbacks des ersten Falls mit dem zweiten Test-App-Start konkurrieren.

Textuals eigener `Header` registriert asynchrone Watcher für App-/Screen-Titel. Beim Unmount fängt die verwendete Framework-Version zwar `NoScreen`, nicht aber einen bereits entfernten `HeaderTitle` ab. Die neue Synchronisation sorgt dafür, dass diese vorgesehenen Watcher vor dem nächsten Screenwechsel beziehungsweise vor dem Test-Shutdown abgearbeitet sind; Fehler werden nicht unterdrückt.

## Tests

- `test_tui_stream_recordings_empty_and_settings_controls`: bestanden
- `test_tui_settings_selects_named_vimeo_folder_without_exposing_id_input`: bestanden
- `test_tui_vimeo_library_has_clear_empty_and_error_states`: beide Parameterfälle bestanden
- Betroffene Race-Gruppe: 10/10 Wiederholungsläufe bestanden
- Besonders anfälliger Folder-Test: 10/10 Wiederholungsläufe bestanden
- Vollständige Suite, Lauf 1: 475 bestanden
- Vollständige Suite, Lauf 2: 475 bestanden
- `git diff --check`: erfolgreich; nur bekannte LF-/CRLF-Hinweise

## Offene Punkte / Risiken

Textual 8.2.7 enthält im `Header` weiterhin den beschriebenen engen Unmount-Zeitraum. Der Projektcode umgeht diesen nicht durch Fehlerunterdrückung, sondern hält seine Screen-/Worker-Lifecycles sauber ein. Bei neuen Pilot-Tests mit schnellen Thread-Fakes müssen Screenwechsel und Worker-Rückgaben weiterhin über die gemeinsamen Helfer synchronisiert werden.

Das Testskript kann im aktuellen Sandbox-Lauf den bevorzugten Ordner unter `%LOCALAPPDATA%` nicht beschreiben und weicht erwartungsgemäß auf `%TEMP%\PredigtUploader-pytest` aus.

## Nächster sinnvoller Schritt

Bei künftigen Textual-Tests `Pilot.click` oder fokussiertes `Pilot.press("enter")` für Benutzeraktionen verwenden und vor dem Verlassen eines gerade gewechselten Screens `_settle_tui` beziehungsweise bei erwarteter Hintergrundarbeit `_wait_for_tui_workers` aufrufen.
