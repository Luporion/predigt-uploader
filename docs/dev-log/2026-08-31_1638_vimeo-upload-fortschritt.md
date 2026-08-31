# Entwicklungsbericht: Vimeo-Upload-Fortschritt

## Ziel

Der produktive Textual-Vimeo-Schritt soll bei mehrgigabytegroßen MP4-Dateien echten, laufenden tus-Fortschritt zeigen und während Upload, Verifikation und Vimeo-Verarbeitung sichtbar bedienbar bleiben. Schritt 8 und Direkt-Vimeo müssen weiterhin dieselbe Publishing-Schicht und denselben Screen verwenden.

## Geänderte Dateien

- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/tui_app.py`
- `tests/test_vimeo.py`
- `tests/test_tui.py`
- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`
- diese Datei

## Was wurde umgesetzt?

### Progress-Architektur

Der vorhandene `VimeoPublishingService` und sein `VimeoProgress`-Callback bleiben die einzige Fortschrittsschnittstelle. `RequestsVimeoTransport.patch_upload()` meldet nun jeden tatsächlich aus dem begrenzten Dateistream in den laufenden tus-PATCH übernommenen Block. Der Service rechnet den PATCH-lokalen Wert in den absoluten Dateioffset um und ergänzt Prozent, mittlere Übertragungsgeschwindigkeit des aktuellen Laufs und eine daraus berechnete Restzeit.

Es gibt weiterhin keine zweite Uploadimplementierung. Die MP4 wird höchstens in den bereits verwendeten 1-MiB-Leseblöcken gelesen und niemals vollständig in den Arbeitsspeicher geladen.

### State und Resume

Die feineren UI-Ereignisse ändern die Sicherheitssemantik nicht. Der Workflow-State speichert weiterhin nur den nach Abschluss eines tus-PATCH von Vimeo bestätigten Offset. Nach einem Netzwerkfehler liest der Service den sicheren Remote-Offset erneut per `HEAD`; die Anzeige kann dadurch ehrlich auf diesen bestätigten Stand zurückgehen. Video-ID, tus-Link und bekannte Resume-Daten bleiben für einen erneuten Versuch erhalten.

### Textual-Worker und Bedienung

Die bestehende Veröffentlichung läuft unverändert in einem Textual-Thread-Worker. Fortschrittsereignisse wechseln über `App.call_from_thread` in den UI-Thread. Der Screen zeigt:

- eine Checkliste mit `✓`, `⟳`, `○` und `✗`;
- einen determinierten Balken für den Dateiupload;
- Prozent und übertragene/Gesamtgröße;
- Geschwindigkeit und grobe Restzeit, sobald diese berechenbar sind.

Während des Jobs sind Upload, Überspringen, Öffnen, Kopieren und Weiter gesperrt. Der vorhandene `running`-Guard verhindert zusätzlich einen zweiten Start. Im Fehlerfall bleiben bereits abgeschlossene Stufen grün, die letzte Stufe wird als fehlgeschlagen markiert und der letzte Bytefortschritt bleibt sichtbar.

Direkt-Vimeo öffnet weiterhin denselben `VimeoPublishingScreen` und erhält damit ohne Sonderlogik dieselbe Fortschrittsanzeige.

Beim vollständigen Testlauf wurde außerdem ein bereits vorhandenes Abbau-Race des Metadaten-Scroll-Watchers sichtbar: Eine auslaufende Textual-Animation konnte nach dem Entfernen des Screens noch einmal feuern. Der Watcher beendet sich nun gezielt bei `NoScreen`; Layout und Scrollverhalten selbst bleiben unverändert.

### Vimeo-Transkodierung

Für `transcode.status=in_progress` wird kein Prozentwert erfunden. Der Screen zeigt den Status als laufende Vimeo-Verarbeitung. Die vorhandene Fachsemantik bleibt bestehen: Wenn Upload, Folder und Embed vollständig sind, kann Publishing lokal abgeschlossen sein, obwohl Vimeo noch transkodiert. `complete` wird eindeutig als abgeschlossen markiert.

## Tests

Ergänzt bzw. erweitert wurden Tests für:

- Byte-Callbacks innerhalb eines tus-PATCH und begrenztes Streaming;
- 0 Byte, Teilfortschritt, kleine/vollständige Datei und Prozentgrenzen;
- Geschwindigkeit und Restzeit;
- mehrere UI-Updates, Fortschrittsbalken und menschenlesbare Größen;
- gesperrte Aktionen und verhinderten Doppelstart;
- sichtbare Teilfortschritte und erhaltene erfolgreiche Stufen bei Fehlern;
- Retry mit vorhandener Vimeo-ID;
- `IN_PROGRESS` ohne Fake-Prozent und `COMPLETE`;
- gemeinsame Fortschrittsdarstellung für Schritt 8 und Direkt-Vimeo.

Normale Tests verwenden ausschließlich Fake-Transporte und starten keinen echten Vimeo-Zugriff.

## Offene Punkte / Risiken

- Geschwindigkeit und Restzeit sind bewusst Schätzwerte des aktuellen Programmlaufs. Betriebssystem-, TLS- und Socket-Puffer können kurze Schwankungen verursachen.
- Ein innerhalb eines PATCH angezeigter Bytewert ist erst nach Vimeos Antwort serverbestätigt. Bei einem Abbruch kann der sichere Resume-Offset niedriger liegen.
- Die produktive Transkodierung wird weiterhin nicht bis `COMPLETE` gepollt; der reale Vimeo-Status kann nach dem lokalen Erfolg noch `IN_PROGRESS` sein.

## Manuelle Testanleitung

1. PredigtUploader über `PredigtUploader Textual starten.cmd` öffnen.
2. Eine größere, bereits fertige MP4 entweder über den normalen Workflow vorbereiten oder über `Direkt zu Vimeo hochladen (Admin / Sonderfall)` auswählen.
3. Auf dem Vimeo-Screen Datei, Team, Ordner und Titel prüfen. Bis zum Klick auf `Video jetzt auf Vimeo hochladen` darf kein Upload starten.
4. Upload bewusst starten und beobachten, dass Checkliste, Balken, Prozent und Bytezahlen laufend steigen und das Terminal weiter neu zeichnet.
5. Prüfen, dass Upload und Überspringen währenddessen nicht erneut bedienbar sind.
6. Optional während eines Testuploads kurz die Netzwerkverbindung unterbrechen. Die Fehlermeldung muss lokale Dateien als sicher nennen; ein Retry muss die gespeicherte Video-ID/tus-Sitzung verwenden und darf keinen zweiten Platzhalter erzeugen.
7. Nach dem Upload prüfen, dass Folder, Verarbeitung und Embed einzeln fortschreiten. Bei `IN_PROGRESS` darf für die Transkodierung kein Prozentwert erscheinen.
8. Nach Erfolg Vimeo-URL, Embed-Kopieren und Abschluss kontrollieren.

## Nächster sinnvoller Schritt

Den Fortschrittsbildschirm einmal mit einer mehrere Gigabyte großen echten Aufnahme unter normaler Uploadgeschwindigkeit und einmal mit bewusst unterbrochener Verbindung prüfen. Danach kann die automatische Startmenü-Liste unvollständiger Vimeo-States als getrennte UX-Aufgabe folgen; WordPress bleibt der nächste große Publishing-Baustein.
