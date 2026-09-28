# Entwicklungsbericht: Vimeo-Uploadscreen-Sicherheit

## Ziel

Den produktiv bewährten Vimeo-Uploadscreen um klare Beenden-Warnungen, verständliche Übergangszustände, sofort erkennbare Early-Link-/Embed-Aktionen und einen direkten Zugriff auf den lokalen Aufnahmeordner ergänzen, ohne Transport-, Resume- oder Cleanup-Fachlogik umzubauen.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `TASKS.md`
- `docs/vimeo-development.md`
- `docs/dev-log/2026-09-02_1747_vimeo-uploadscreen-sicherheit.md`

## Was wurde umgesetzt?

Der Vimeo-Screen besitzt nun eine kleine UI-Zustandsschicht für `running`, `pausing`, `paused` und `aborting`. Während aktiver Vimeo-Operationen warnt ein prominenter orangefarbener Block vor dem Beenden. Beim Pausieren bleibt die Warnung sichtbar, bis der laufende PATCH beendet und der bestätigte tus-Offset persistiert ist. Danach bestätigt ein grüner Block, dass die App sicher geschlossen und später mit derselben Remote-ID fortgesetzt werden kann.

Beim endgültigen Abbruch werden konkurrierende Aktionen gesperrt. Der Screen unterscheidet sichtbar das Beenden der Datenübertragung, das Entfernen des Vimeo-Eintrags und das Bereinigen des Upload-State. Die bestehende sichere Backend-Semantik und die vorhandenen Erfolgs-/Cleanup-Fehlerscreens bleiben unverändert.

Sind Vimeo-Link und Embed-Code verfügbar, erklärt der grüne Aktionsblock nun ohne WordPress-Vorgriff, dass die Predigt bereits auf der Website angelegt werden kann. Beide Aktionen bleiben unabhängig vom Upload- und Transkodierungsfortschritt verfügbar. Ein neuer neutraler Button öffnet das tatsächliche Elternverzeichnis der finalen MP4. Die App-interne Beenden-Aktion verlangt während laufender, pausierender oder abbrechender Vimeo-Arbeit eine ausdrückliche Bestätigung und empfiehlt zuerst die sichere Pause.

Die Buttons sind in primäre Uploadaktion, Transfersteuerung, Hilfsaktionen und Workflowaktionen gegliedert. Die Bereiche bleiben außerhalb des scrollbaren Inhalts dauerhaft erreichbar; die ausführlichen Statusblöcke liegen im scrollbaren Vimeo-Inhalt.

## Tests

- Pilot-Test für prominente Warnung und Website-bereite Early-Aktionen während laufendem Upload
- Pilot-Test für Pause-Übergang, gesperrte Konkurrenzaktionen und sicheren Pausenzustand
- Pilot-Test für endgültigen Abbruch mit sichtbarem Cleanup-Fortschritt und gesperrten Aktionen
- Pilot-Test für App-interne Exit-Bestätigung während aktivem Upload
- Pilot-/Fake-Test für den exakten MP4-Elternordner sowie fehlenden Ordner und `PermissionError`
- bestehende Erfolgs- und Cleanup-Fehlertests bleiben aktiv

Die vollständige Suite über `scripts/test.ps1` besteht mit 449 Tests. Der komplette TUI-Testbestand sowie die gezielten neuen Vimeo-Pilot-Tests sind grün. `git diff --check` meldet keine Whitespace-Fehler; sichtbar sind ausschließlich die im Repository bekannten LF/CRLF-Hinweise.

## Offene Punkte / Risiken

- Ein hartes Schließen des Windows-Terminalfensters kann Textual nicht zuverlässig verhindern. Die Absicherung umfasst die kontrollierbaren App-Aktionen und einen deutlichen Dauerhinweis.
- Ein bereits laufender HTTP-PATCH wird weiterhin bewusst nicht hart unterbrochen. Die Pause beziehungsweise der endgültige Abbruch wird erst nach dessen sicherem Ende bestätigt.
- Die reale Lesbarkeit bei einer großen MP4 sollte einmal bei normaler und kleiner Windows-Terminalhöhe geprüft werden.

## Nächster sinnvoller Schritt

Den Screen mit einer großen Datei manuell prüfen: Early-Link/Embed, Pause-Übergang, sicheres Schließen nach Pause, Resume und endgültigen Abbruch jeweils anhand der sichtbaren Hinweise nachvollziehen. Danach kann der Vimeo-Meilenstein abgeschlossen werden; WordPress bleibt ein eigener Folgeauftrag.
