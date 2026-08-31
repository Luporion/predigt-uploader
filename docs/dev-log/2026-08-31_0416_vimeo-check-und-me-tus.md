# Entwicklungsbericht: Vimeo-Check und /me-tus

## Ziel

Den falschen harten Upload-Capability-Test auf `metadata.connections.videos.options` entfernen, `vimeo-check` auf belastbare nicht-destruktive Prüfungen begrenzen und den expliziten tus-Testupload an Vimeos dokumentierten `/me/videos`-Ablauf anpassen. Der normale Wizard, Textual und WordPress bleiben unverändert.

## Geänderte Dateien

- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/workflow_state.py`
- `src/predigt_uploader/cli.py`
- `tests/test_vimeo.py`
- `tests/test_workflow_state.py`
- `README.md`, `STATUS.md`, `TASKS.md`
- `docs/publishing-architecture.md`, `docs/vimeo-development.md`

## Was wurde umgesetzt?

Der reale Kontobefund und die aktuelle offizielle Vimeo-Dokumentation stimmen darin überein, dass ein tus-Upload mit `POST /me/videos` beginnt. Das reale Konto liefert in `metadata.connections.videos.options` trotzdem nur `GET`; der bewusst ungültige POST wurde von Vimeo fachlich bis zur Body-Validierung verarbeitet. Die Connection-Options sind deshalb kein verlässlicher Upload-Berechtigungsnachweis.

`vimeo-check` prüft weiterhin Token, `/me`, den explizit konfigurierten Team-Owner, numerische Folder-ID, Folder-Existenz, exakte Folder-ID, optionalen Kontrollnamen und Folder-Owner. Fehlendes `POST` in den Connection-Options führt nicht mehr zum Abbruch. Stattdessen erscheint: „Die eigentliche Upload-Berechtigung wird beim Upload geprüft.“ Der Check legt keinen Video-Platzhalter an.

Der ausdrücklich mit `--confirm-vimeo-upload` freigegebene Upload sendet den tus-Body an `/me/videos`, speichert URI/ID und tus-Link unmittelbar, streamt ab dem per `HEAD` bestätigten Offset und verifiziert `upload.status`. Anschließend wird die Folder-Mitgliedschaft zuerst gelesen; nur wenn sie fehlt, wird das Video unter dem konfigurierten Team-Owner hinzugefügt und danach erneut verifiziert.

Workflow-State-Schema 3 verwendet `upload_status`, `uploaded_at`, `target_folder_id`, `target_folder_uri` und `target_folder_name`. Alte Schema-2-Felder `folder_id`, `folder_uri` und `folder_name` werden beim Laden übernommen. Eine vorhandene `video_uri` reicht bereits für den Doppelschutz und wird bei Bedarf zur `video_id` normalisiert. Ein bestätigter Remote-Upload wird vor Folder-/Embed-Schritten atomar gespeichert; spätere Fehler vergessen ihn nicht.

`vimeo-embed` normalisiert URI/ID, aktualisiert Video-URL, `embed_html` und `player_embed_url` und bleibt ohne erneuten Upload ausführbar.

## Tests

- keine echten Vimeo-Netzwerkzugriffe in pytest
- gezielte Fake-Transport-Tests für Connection-Options nur mit `GET`, `/me/videos`, Owner-/Folder-Fehler, tus-Erstellung, Fehler, Resume, URI-basierte Idempotenz, Folder-Zuordnung, Embed-Nachladen und Schema-Migration
- vollständige Suite: `350 passed`
- `git diff --check`: erfolgreich
- CLI-Hilfe und Windows-Systemcheck: erfolgreich

## Offene Punkte / Risiken

- Vimeo bietet keinen verlässlichen vollständig nicht-destruktiven Nachweis für Upload- und Folder-Schreibrechte. Die tatsächlichen Rechte können erst bei den ausdrücklich ausgelösten POST-Anfragen bestätigt werden.
- Ein echter tus-Testupload wurde in diesem Auftrag nicht automatisch gestartet.
- Privacy-, Unlisted- und Domain-Embed-Verhalten müssen weiterhin mit einem kleinen bewussten Testvideo geprüft werden.
- WordPress und eine Vimeo-UI-Anbindung sind weiterhin nicht implementiert.

## Nächster sinnvoller Schritt

Mit der bereits bestätigten Team-/Folder-Konfiguration zuerst `vimeo-check` erneut ausführen. Wenn die Ausgabe korrekt ist, einen kleinen unkritischen State mit `vimeo-upload --confirm-vimeo-upload` bewusst testen und anschließend Folder-Mitgliedschaft, Video-Link, Privacy und Embed sowohl per State als auch in Vimeo kontrollieren.
