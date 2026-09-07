# Entwicklungsbericht: Vimeo-Abschluss-Herkunft

## Ziel

Den vollständigen normalen Schritt-1-bis-8-Workflow sicher vom Direct-Vimeo-Sonderweg unterscheiden und redundante Early-Link-/Embed-Notifications entfernen.

## Geänderte Dateien

- `src/predigt_uploader/workflow_state.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_workflow_state.py`
- `tests/test_tui.py`
- `STATUS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`
- `docs/dev-log/2026-09-06_1548_vimeo-abschluss-herkunft.md`

## Was wurde umgesetzt?

Die bisherige Endscreen-Auswahl beruhte ausschließlich auf dem flüchtigen Screen-Parameter `direct_mode`. Der Workflow-State enthielt keine Herkunft, sodass die Auswahl bei erneutem Öffnen oder Resume nicht aus der Aufnahme selbst rekonstruiert werden konnte.

Workflow-State-Schema 7 ergänzt deshalb `workflow_origin` mit den Werten `normal` und `direct_vimeo`. Die lokale Verarbeitung erzeugt weiterhin standardmäßig einen normalen State und übergibt diesen Ursprung beim Wechsel von Schritt 7 nach 8 ausdrücklich. Der Direct-Vimeo-Vorbereitungsweg kennzeichnet sowohl neue als auch passend wiederverwendete States als `direct_vimeo`. Der Vimeo-Screen leitet seine Darstellung beim Resume aus diesem Feld ab. Alle Publishing-Updates verwenden weiterhin denselben State und erhalten das Top-Level-Feld automatisch.

Alte States ohne `workflow_origin` werden sicher als `normal` gelesen. Damit bleiben bestehende vollständige Aufnahmen auf dem ausführlichen Abschluss; ein bewusst gestarteter Direct-Vimeo-Weg setzt seine Herkunft vor dem Upload explizit.

Der normale Erfolgsscreen zeigt Zielordner, finale MP4, MP3, Zusammenfassung, Vimeo-Titel, Zielordner, URL, Upload- und Verarbeitungsstatus sowie den Hinweis auf die nun mögliche Website-Arbeit. Eine noch laufende Vimeo-Transkodierung bleibt ein neutraler offener Status und blockiert den Abschluss nicht. Direct-Vimeo zeigt nur lokale MP4 und Vimeo-Daten und behauptet keine MP3- oder Zusammenfassungserstellung.

Die Early-Link- und Early-Embed-Erfolgs-Toasts wurden entfernt. Ihre Information ist bereits durch den vollbreiten grünen Website-Banner, die technische Statusliste und die grün aktivierten Buttons sichtbar. Fehler- und Warn-Notifications wurden nicht verändert.

## Tests

- State-Roundtrip für `normal` und `direct_vimeo`
- Migration alter States ohne Herkunft
- echter Pilot-Übergang Schritt 7 → 8 → vollständiger Abschluss
- Direct-Vimeo-Resume anhand gespeicherter Herkunft
- keine falschen MP3-/Zusammenfassungsangaben im Direct-Abschluss
- normaler Abschluss trotz `transcode_status=in_progress`
- Early-Website-Banner ohne redundante Erfolgs-Toasts
- vollständige Projektsuite
- `git diff --check`

Ergebnis: Alle 455 Tests bestehen in den vollständigen getrennten TUI- und Nicht-TUI-Läufen. Im kombinierten `scripts/test.ps1`-Lauf bestanden zuletzt 454 Tests; ein unveränderter asynchroner Vimeo-Bibliotheks-Pilot überschritt nur dort sein bestehendes Acht-Sekunden-Zeitfenster und besteht isoliert sowie im vollständigen TUI-Lauf. Die 15 gezielten State-/Endscreen-/Herkunftstests bestanden gemeinsam. Es wurden keine echten Vimeo-Aufrufe ausgeführt.

## Offene Punkte / Risiken

Ein alter State ohne Herkunft wird aus Kompatibilitätsgründen als normal behandelt. Wird er bewusst über Direct-Vimeo ausgewählt, wird das Feld vor dem Öffnen des Publishing-Screens eindeutig auf `direct_vimeo` gesetzt.

## Nächster sinnvoller Schritt

Den normalen End-to-End-Ablauf und den Direct-Vimeo-Sonderweg jeweils einmal bis zum Abschluss durchklicken und die unterschiedlichen Titel, Dateidetails und Aktionen visuell kontrollieren.
