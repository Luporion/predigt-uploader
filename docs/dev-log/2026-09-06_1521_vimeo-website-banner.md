# Entwicklungsbericht: Vimeo-Website-Banner

## Ziel

Den bereits funktionierenden Early-Link-/Early-Embed-Hinweis im Vimeo-Uploadscreen deutlich hervorheben, ohne Publishing-, Pause-, Resume-, Abbruch- oder Workflowlogik zu verändern.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `tests/test_tui.py`
- `STATUS.md`
- `docs/dev-log/2026-09-06_1521_vimeo-website-banner.md`

## Was wurde umgesetzt?

Der Website-Hinweis wurde aus der rechten Box `Status / Entscheidung` herausgelöst. Sobald Vimeo-Link und Einbettungscode gemeinsam vorhanden sind, erscheint am Anfang des scrollbaren Vimeo-Inhalts direkt unter dem festen orangefarbenen Sicherheitsbanner ein eigener vollbreiter grüner Banner.

Seine fett und zentriert gesetzte Hauptaussage lautet `DU KANNST JETZT DIE PREDIGT AUF DER WEBSITE ANLEGEN`. Darunter stehen kompakter die Hinweise, dass Link und Einbettungscode bereits verwendbar sind und – solange zutreffend – der Video-Upload weiterläuft. Die rechte Statusbox enthält weiterhin die technischen Einzelzustände. Die vorhandenen grünen Buttons `Vimeo öffnen` und `Embed-Code kopieren` bleiben unverändert gekoppelt.

Der Banner hängt ausschließlich von den tatsächlich vorhandenen Werten `video_url` und `embed_html` ab. Deshalb bleibt er auch bei laufender Transkodierung und bei einem nachgelagerten Fehler der Ordnerzuordnung sichtbar. Vor Verfügbarkeit beider Werte bleibt er ausgeblendet.

Der Banner liegt innerhalb des vorhandenen Scrollcontainers statt als weiteres festes Höhenelement im Screen. Dadurch ist er beim Einstieg oben und über die ganze Breite sichtbar, während die feste untere Aktionsleiste auch bei einer Pilot-Größe von 100×32 erreichbar bleibt.

## Tests

- Sichtbarkeit vor Early-Link/Early-Embed
- Sichtbarkeit und Hauptaussage während des laufenden Uploads
- fortbestehende Sichtbarkeit bei `transcode_status=in_progress`
- fortbestehende Sichtbarkeit nach einem Fehler der Vimeo-Ordnerzuordnung
- feste untere Aktionen bei 100×32
- vollständige Projektsuite
- `git diff --check`

Ergebnis: 454 Tests bestanden. Zwei unveränderte asynchrone Bibliotheks-/Settings-Tests überschritten im ersten Gesamtlauf ihr Testzeitfenster, bestanden danach gemeinsam isoliert und im wiederholten vollständigen Lauf. Es wurden keine echten Vimeo-Aufrufe ausgeführt.

## Offene Punkte / Risiken

Der Banner scrollt zusammen mit dem Vimeo-Inhalt, damit kleine Terminalhöhen nicht die Aktionsleiste verdrängen. Direkt nach dem Einblenden befindet er sich am Anfang des Inhalts; nach bewusstem Herunterscrollen ist er entsprechend nicht mehr fest angeheftet. Das sollte im manuellen Realtest bei der typischen Windows-Terminalgröße noch einmal visuell beurteilt werden.

## Nächster sinnvoller Schritt

Den grünen Banner bei einem realen Upload gemeinsam mit dem orangefarbenen Sicherheitsbanner und den aktivierten Link-/Embed-Buttons in der normalen Windows-Terminalgröße kontrollieren.
