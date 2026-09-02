# Entwicklungsbericht: Vimeo-Robustheit, Stop und Bibliotheks-Cache

## Ziel

Den praktisch bewährten Vimeo-TUS-Pfad ohne grundlegenden Umbau gegen extern gelöschte Remote-Videos absichern, kontrolliertes Stoppen/Fortsetzen ermöglichen und die Bibliothek mit mehreren hundert Videos progressiv nutzbar machen. Early-Link und Early-Embed sollen während des Uploads unübersehbar, aber ruhig dargestellt werden.

## Geänderte Dateien

- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/workflow_state.py`
- `src/predigt_uploader/tui_app.py`
- `src/predigt_uploader/cli.py`
- `tests/test_vimeo.py`
- `tests/test_tui.py`
- `tests/test_workflow_state.py`
- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`
- dieser Entwicklungsbericht

## Was wurde umgesetzt?

### Extern gelöschte Vimeo-Videos

Vor Wiederverwendung einer gespeicherten Video-ID läuft weiterhin die Remote-Prüfung. Die Konto-, Team-Owner- und Folder-Vorprüfung erfolgt nun vor der Entscheidung über einen veralteten Video-State. Nur wenn `GET /videos/{id}` anschließend explizit HTTP 404 meldet, wird ausschließlich `WorkflowState.vimeo` auf einen frischen Pending-Zustand zurückgesetzt. Aufnahmeinformationen, lokale Pfade und Dateien bleiben unverändert. Der neue Upload darf danach genau einen neuen Remote-Platzhalter anlegen.

Timeouts sowie 401/403, 429, 5xx und andere unklare API-Fehler werden nicht als Löschung interpretiert. Der bekannte Vimeo-State bleibt bytegleich erhalten und `POST /me/videos` wird nicht aufgerufen. Damit bleibt der Doppelschutz konservativ.

Textual und die CLI-Vorschau erklären den eindeutigen Reset: Das alte Vimeo-Video existiert nicht mehr, die lokale Aufnahme bleibt unverändert und ein neuer Upload ist wieder möglich.

### Upload stoppen und fortsetzen

Workflow-State-Schema 5 ergänzt `step.status=stopped`. Der vorhandene `VimeoPublishingService.publish()` akzeptiert eine UI-neutrale Cancellation-Prüfung. Textual setzt dafür nach einem Modal-Dialog ein `threading.Event`; `Weiter hochladen` ist die sichere, fokussierte Standardaktion.

Das Flag wird zwischen Vimeo-Phasen und tus-Blöcken geprüft. Ein laufender HTTP-PATCH wird nicht hart beendet. Nach erfolgreichem PATCH wird zuerst dessen bestätigter Offset atomar gespeichert, anschließend wird gestoppt. Video-ID/-URI, tus-Link, Gesamtgröße und bestätigter Offset bleiben erhalten. Die TUI meldet bestätigte Bytes und bietet `Vimeo-Upload fortsetzen`. Ein Retry führt erneut Remote-Prüfung und tus-HEAD aus und legt keinen zweiten Platzhalter an. Ein Stop vor der Remote-Anlage erzeugt keine erfundenen Remote-Daten. Es erfolgt ausdrücklich kein Vimeo-DELETE.

### Progressive Vimeo-Bibliothek

Das vorhandene Bibliotheksbackend meldet nach jeder API-Seite ein kumulatives `VimeoLibraryResult` mit optionaler Gesamtzahl und `complete`-Kennzeichen. Textual zeigt daher beispielsweise schon `100 / 606 Videos geladen – weitere werden geladen …`; diese Videos sind sofort auswählbar. Die Titelsuche arbeitet währenddessen nachvollziehbar über die bisher geladenen Einträge.

Ein vollständig geladenes Ergebnis wird in der laufenden Textual-App anhand Team-Owner-/Folder-ID gecached. Zurückgehen und erneutes Öffnen erzeugen keinen weiteren Komplettabruf. `Neu laden` invalidiert genau diesen Cache und startet einen echten neuen API-Lauf. Fehler bei einem Refresh nehmen bereits geladene Daten nicht unnötig aus der Bedienung.

### Sichtbare Early-Actions

Sobald Link beziehungsweise Embed im State stehen, zeigt Schritt 8 eigene grüne Verfügbarkeitshinweise. Die Buttons erhalten eine stabile Erfolgsumrandung und beim erstmaligen Verfügbarwerden eine kurze 1,5-Sekunden-Hervorhebung sowie eine einmalige Benachrichtigung. Während der Dateiübertragung erklärt die Oberfläche, dass für Link und Embed nicht auf 100 Prozent gewartet werden muss. Upload- und Transkodierungsstatus bleiben davon getrennt.

## Tests

Ergänzt wurden Tests für:

- vorhandenes Remote-Video ohne State-Veränderung und ohne Duplikat;
- eindeutiges 404 mit reinem Vimeo-State-Reset und anschließend genau einer Neuanlage;
- Timeout sowie 401/403, 429 und 5xx ohne Reset oder POST;
- kooperativen Stop vor der Remote-Anlage und nach einem bestätigten tus-Block;
- Persistenz des bestätigten Offsets und Resume ohne zweiten Platzhalter;
- progressive Backend-Pagination und erste sichtbare TUI-Seite vor Abschluss;
- App-Cache und expliziten Refresh;
- Stop-Dialog, abgelehnten und bestätigten Stop, Buttonzustände und Fortsetzung;
- sichtbare Early-Link-/Embed-Hinweise und verfügbare Aktionen;
- verständliche TUI-Meldung zum extern gelöschten Video;
- Schema-5-Migration.

Die gezielten Workflow-State-/Vimeo-/TUI-Tests sind grün. `scripts/test.ps1` schließt die vollständige Suite mit **418 bestandenen Tests** ab. Automatisierte Tests führen keine echten Vimeo-Zugriffe aus.

## Offene Punkte / Risiken

- Vimeo kann bei absichtlich verborgenen Ressourcen je nach Kontokontext ebenfalls 404 verwenden. Der Reset erfolgt deshalb erst nach erfolgreicher Konto-/Team-/Folder-Prüfung; ein explizites Video-404 ist der vom Auftrag gewünschte definitive Auslöser. Alle anderen Fehler bleiben konservativ.
- Ein Stop wird absichtlich nicht mitten in einem laufenden HTTP-PATCH erzwungen. Bei großen 128-MiB-Blöcken kann die Anzeige daher bis zur Vimeo-Antwort kurz auf „wird sicher gestoppt“ stehen.
- Der Bibliotheks-Cache lebt nur bis zum Schließen der App und enthält ausschließlich vollständige Abrufe. Eine dauerhafte Cachedatei wurde bewusst nicht eingeführt.
- Es wurde kein echtes Video hochgeladen, gestoppt oder gelöscht.

## Nächster sinnvoller Schritt

Mit einer bewusst gewählten Aufnahme den Stop nach sichtbarem Fortschritt testen, danach denselben State fortsetzen und abschließend das Vimeo-Webinterface kontrollieren. Parallel die Bibliothek mit den realen rund 606 Videos auf erste Seitenanzeige, Cache und `Neu laden` prüfen. Danach kann der geplante Ausbau der Einstellungen erfolgen.
