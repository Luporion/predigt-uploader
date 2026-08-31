# Entwicklungsbericht: Vimeo-Publishing-Grundlage

## Ziel

Phase 2 als UI-unabhängige und sicher manuell testbare Vimeo-Publishing-Schicht vorbereiten und implementieren: große MP4 per tus übertragen, expliziten Team-Owner und Teamordner validieren, Doppeluploads vermeiden, Remote- und Folder-Zustand prüfen sowie vollständige Embed-Daten im bestehenden Workflow-State sichern. Der lokale Wizard und die Textual-Oberfläche sollten unverändert lokal bleiben; WordPress war ausdrücklich kein Teil dieses Schritts.

## Geänderte Dateien

- neue Fach- und HTTP-Schicht: `src/predigt_uploader/publishing/vimeo.py`, `src/predigt_uploader/publishing/__init__.py`
- Vimeo-Zielkonfiguration: `src/predigt_uploader/models.py`, `src/predigt_uploader/config.py`, `config.example.toml`
- erweiterter persistenter Zustand: `src/predigt_uploader/workflow_state.py`
- bewusst ausführbare Entwicklungskommandos: `src/predigt_uploader/cli.py`
- Abhängigkeit/Systemcheck/Release-Inhalt: `pyproject.toml`, `scripts/check-system.ps1`, `scripts/make-release-zip.ps1`
- Tests: `tests/test_vimeo.py`, `tests/test_config.py`, `tests/test_workflow_state.py`
- Dokumentation: `README.md`, `STATUS.md`, `TASKS.md`, `docs/publishing-architecture.md`, `docs/vimeo-development.md`

## Was wurde umgesetzt?

Die aktuelle offizielle Vimeo-Dokumentation wurde für Video Upload API, tus, Folder/Projects, Team-Owner-Kontext, Video-Ressource, Embed-Daten, oEmbed und Scopes geprüft. Der Upload wird bewusst unter `/users/{team_owner_user_id}/videos` angelegt; `/me` dient nur zur Identitätsdiagnose. Der Zielordner wird über die numerische Folder-ID gelesen, zusätzlich optional gegen seinen Anzeigenamen und Owner geprüft. Upload- und Folder-Schreibmöglichkeit werden vor dem Anlegen eines Video-Platzhalters kontrolliert.

Nach dem streamenden tus-Upload wird das Video über den weiterhin „projects“ genannten Items-Endpoint dem konfigurierten Teamordner zugeordnet. Danach wird die Mitgliedschaft über die Videoliste genau dieses Ordners verifiziert. Erst nach bestätigtem Remote-Upload, Folder-Mitgliedschaft und Embed-Abruf wird Vimeo als `complete` gespeichert.

`VimeoPublishingService` ist UI-unabhängig und nutzt eine kleine Transportgrenze. `RequestsVimeoTransport` liest auch innerhalb eines 128-MiB-tus-Blocks höchstens 1 MiB auf einmal. Der serverseitige tus-Offset wird per `HEAD` ermittelt und ist beim Resume maßgeblich. Temporäre Übertragungsfehler werden mit erneutem Remote-Offset versucht; nach vollständigem Erfolg wird der nicht mehr benötigte tus-Link aus dem State entfernt. Fortschrittsereignisse enthalten Phase, übertragene Bytes, Gesamtgröße und Prozent.

Der vorhandene State wurde als Schema 2 rückwärtskompatibel um Video-URI, Player-URL, Embed-HTML, Team-/Folder-Daten sowie tus-Link, Offset und Gesamtgröße ergänzt; Schema-1-Dateien bleiben lesbar und werden beim nächsten Speichern migriert. Token oder andere Zugangsdaten werden nicht gespeichert. Eine bekannte Video-ID wird sofort atomar gesichert und vor weiteren Aktionen remote geprüft. `complete` blockiert Doppeluploads; `in_progress` ohne ID stoppt sicher; `failed` kann kontrolliert fortgesetzt werden. Ein Folgefehler vergisst eine bereits bekannte Remote-ID nicht.

Embed-Daten werden primär aus `video.embed.html` und `player_embed_url` übernommen. Danach folgt oEmbed mit der vollständigen, bei unlisted Videos hashhaltigen Video-URL; als letzter Fallback wird ein iframe aus `player_embed_url` erzeugt. `vimeo-embed` kann die Daten später anhand der Video-ID erneut laden.

Für HTTP wurde `requests` ergänzt, nicht Vimeos Python-SDK: Der explizite Team-Owner-Endpoint, persistierte tus-Link, serverseitige Resume-Offsets, begrenzte Lesegrößen und Fake-Transport-Tests bleiben damit direkt kontrollierbar. Privacy wird beim Upload bewusst nicht erfunden oder überschrieben; Vimeos Konto-Defaults bleiben wirksam.

Die Kommandos `vimeo-diagnose`, `vimeo-check`, `vimeo-upload` und `vimeo-embed` sind ausschließlich Entwicklungswege. Diagnose und Check laden nichts hoch. `vimeo-upload` startet nur mit State-Pfad und zusätzlichem `--confirm-vimeo-upload`. In diesem Auftrag wurde keine echte Vimeo-Anfrage und kein Upload ausgeführt.

## Tests

- 32 isolierte Vimeo-Tests mit Fake-Transport: Credentials/Token-Bereinigung, Konfiguration, Team-/Folder-Rechte, State-Guards, Doppelschutz, Retry/Resume, begrenztes Streaming, Fortschritt, Zuordnung/Verifikation, Embed-Fallback und atomare Zwischenstände
- ergänzte Config- und Workflow-State-Roundtrips einschließlich fehlender älterer Felder und Secret-Ausschluss
- vollständige Suite: `345 passed`
- ein unveränderter Textual-Animationstest war im ersten Komplettlauf einmal zu früh bei `scroll_y = 0`; zwei gezielte Wiederholungen und der abschließende Komplettlauf waren grün, daher keine TUI-/Timing-Logik verändert
- `scripts/check-system.ps1`: grün für Python, `.venv`, Wizard, Textual, Vimeo-HTTP-Unterstützung und FFmpeg; `losslesscut_path` ist wie zuvor optional nicht gesetzt
- `python -m compileall -q src tests`: erfolgreich

## Offene Punkte / Risiken

- Team-Owner-, Folder- und Berechtigungsantworten müssen am echten Gemeinde-Vimeo-Konto mit der reinen Diagnose bestätigt werden; Vimeo wurde in diesem Auftrag nicht kontaktiert.
- Ein Netzwerkabbruch genau nach erfolgreichem Placeholder-POST, aber vor Empfang/Persistenz der Video-ID, ist von einem Client nicht zweifelsfrei auflösbar. Der Code wiederholt diesen nicht-idempotenten POST nicht automatisch; vor einem neuen Versuch ist dann eine manuelle Kontrolle im Vimeo-Konto nötig.
- Ein gespeicherter tus-Link kann serverseitig ablaufen. Solange eine Video-ID existiert, wird aus Sicherheitsgründen nicht blind ein zweiter Video-Platzhalter erzeugt.
- Privacy-, unlisted-/private- und Domain-Embed-Verhalten muss mit den realen Konto-Defaults und der späteren WordPress-Domain geprüft werden.
- Interaktiver OAuth/Login, dauerhafte Secret-Ablage, Textual-Anbindung und WordPress sind noch nicht implementiert.

## Nächster sinnvoller Schritt

Token nur für eine PowerShell-Sitzung setzen, mit `vimeo-diagnose` zuerst die angemeldete Identität und danach unter expliziter Team-Owner-ID die Folder-ID ermitteln. Anschließend `vimeo-check` auf einer kopierten fertigen Testaufnahme ausführen. Erst wenn Team, Folder-ID, Titel und Datei stimmen, einen kleinen bewussten Testupload mit `--confirm-vimeo-upload` starten und Folder-Mitgliedschaft, Privacy und Embed zusätzlich in der Vimeo-Weboberfläche kontrollieren.
