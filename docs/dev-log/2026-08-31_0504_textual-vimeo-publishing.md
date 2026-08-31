# Entwicklungsbericht: Textual-Vimeo-Publishing

## Ziel

Die praktisch bestätigte Vimeo-Publishing-Kette als bewusst ausgelösten achten Schritt in den produktiven Textual-Workflow integrieren, ohne den lokalen Workflow, den normalen Wizard, den Smoke-Test oder die Vimeo-Fachlogik zu duplizieren.

## Geänderte Dateien

- `src/predigt_uploader/tui_app.py`
- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/workflow_state.py`
- `src/predigt_uploader/config.py`
- `src/predigt_uploader/cli.py`
- `config.example.toml`
- `tests/test_tui.py`
- `tests/test_vimeo.py`
- `tests/test_workflow_state.py`
- `tests/test_config.py`
- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`

## Was wurde umgesetzt?

Der Textual-Ablauf besitzt nun acht nummerierte Schritte. Nach erfolgreicher lokaler Verarbeitung öffnet sich ein eigener Vimeo-Screen mit lokaler MP4, konfiguriertem Team-/Folderziel, geplantem Vimeo-Titel und dem gespeicherten Publishing-Zustand. Allein das Öffnen erzeugt weder den Vimeo-Service noch Netzwerkzugriff. Erst der Button `Video jetzt auf Vimeo hochladen` startet den vorhandenen `VimeoPublishingService`.

Die synchrone Backend-Kette läuft in einem Textual-Thread-Worker. Fortschrittscallbacks werden über `App.call_from_thread` sicher an die UI übergeben. Angezeigt werden Verbindung, Remote-Videoanlage, tus-Upload mit Prozentwert, Uploadprüfung, Folder-Zuordnung, Vimeo-Verarbeitung und Embed-Abruf. Währenddessen bleiben die lokale Erfolgsinformation und die Oberfläche responsiv; Upload- und Überspringen-Aktionen sind gegen Doppelklick gesperrt.

Bei Erfolg zeigt der Screen Vimeo-Titel, Folder, URL, Transkodierungs- und Embed-Status. Vimeo öffnen, Embed-Code kopieren und Weiter zum Abschluss werden freigeschaltet. Bei Fehlern bleiben MP4, MP3 und Zusammenfassung ausdrücklich unangetastet; eine bekannte Vimeo-ID wird angezeigt und beim nächsten Versuch durch den bestehenden Service wiederverwendet. Überspringen führt mit `Vimeo-Upload noch ausstehend` zum Abschluss. Ein Zurück zu Schritt 7 wird bewusst nicht angeboten, weil die lokalen Dateien dort bereits geschrieben wurden.

Der Workflow-State verwendet Schema 4 und speichert zusätzlich `transcode_status` und `folder_status`. Ältere States bleiben lesbar. Folder-Verifikation und Remote-Transkodierungsstatus werden atomar persistiert; Video-ID/-URI, tus-Resume und Doppelschutz bleiben unverändert Aufgabe des UI-unabhängigen Service.

Bestehende Installationen ohne `[vimeo]`-Abschnitt erhalten zur Laufzeit die bestätigten nicht geheimen Defaults `team_owner_user_id=59930802`, `target_folder_id=1320477` und `target_folder_name=Predigten`. Die bestehende TOML-Datei wird nicht umgeschrieben und explizite andere Werte bleiben erhalten. Der Token wird weiterhin ausschließlich aus `PREDIGT_UPLOADER_VIMEO_TOKEN` gelesen.

Der reale Smoke-Test ist als erfolgreich dokumentiert: Team-Owner und Folder, `/me/videos`, tus, Uploadverifikation, Folder-Zuordnung, Transkodierung und Embed waren erfolgreich; beobachtet wurden `privacy.view=unlisted` und `privacy.embed=public`.

## Tests

- Vollständige Suite über `.\scripts\test.ps1`: **368 bestanden**.
- Textual-Pilot bei `100x32`: kein Upload beim Screen-Aufruf, feste Bottom-Actions, Überspringen, Hintergrund-Worker, sichtbarer 63-Prozent-Zwischenstand, Erfolg, Fehler und Completion.
- Vollständiger Pilot-Übergang von lokaler Dateierstellung zu Schritt 8 ohne Service-/Uploadstart.
- Resume-Test mit vorhandener Vimeo-ID und Prüfung, dass kein paralleler TUI-Sonderpfad angelegt wird.
- Config-Migration ohne Änderung der bestehenden Datei.
- State-Roundtrip/Migration für Schema 4 sowie Backend-Persistenz von Transkodierung und Folder-Verifikation.
- CLI-Hilfe und `vimeo-smoke-test` ohne Freigabe geprüft; kein echter Upload wurde gestartet.
- `scripts/check-system.ps1`: alle wichtigen Prüfungen grün.

## Offene Punkte / Risiken

- Ein alter Zielordner mit unvollständigem Vimeo-State kann noch nicht direkt im Textual-Startmenü geöffnet werden. Backend und State können fortsetzen; offen ist nur der UI-Einstieg.
- Vimeo kann nach beendetem Dateiupload noch transkodieren. Der State und der Screen zeigen diesen Remote-Status, die aktuelle Publishing-Kette wartet aber nicht unbegrenzt auf `transcode.status=complete`.
- Zwischenablage und Browseröffnung müssen auf dem Ziel-Windows-Rechner manuell geprüft werden.
- Der produktive Textual-Schritt wurde automatisiert nur mit Fake-Transport getestet; es wurde in diesem Arbeitsschritt bewusst kein echter Upload gestartet.

## Nächster sinnvoller Schritt

Den Textual-Ablauf zunächst mit einer kleinen bewusst gewählten Aufnahme manuell prüfen: einmal Vimeo überspringen, danach in einem getrennten Lauf Upload, Fortschritt, Teamfolder, URL, Embed-Kopie und Abschluss kontrollieren. Danach kann die WordPress-MP3-/Beitragsintegration als nächster großer Publishing-Schritt beginnen; die Startmenü-Wiederaufnahme bleibt eine kleinere getrennte UX-Aufgabe.

## Manuelle Testanleitung

1. `PREDIGT_UPLOADER_VIMEO_TOKEN` nur für die aktuelle PowerShell-Sitzung setzen.
2. `.\scripts\run-tui.ps1` starten und mit einer kleinen Testaufnahme den lokalen Ablauf bis Schritt 8 abschließen.
3. Prüfen, dass beim Betreten von Schritt 8 noch kein Upload startet und die Bottom-Actions bei `100x32` erreichbar bleiben.
4. Zuerst `Vimeo überspringen / später erledigen` wählen und im Abschluss `Vimeo-Upload noch ausstehend` prüfen.
5. In einem zweiten isolierten Testlauf `Video jetzt auf Vimeo hochladen` bewusst anklicken.
6. Fortschrittsstufen, Uploadprozent, Erfolg, Vimeo-URL, Ordner `Predigten`, `Vimeo öffnen`, `Embed-Code kopieren` und Abschlussstatus prüfen.
7. Im Vimeo-Webinterface kontrollieren, dass genau das erwartete Video im Folder `Predigten` liegt. Testvideos nur anhand ihrer eindeutig bekannten Video-ID manuell entfernen.
