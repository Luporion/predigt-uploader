# Entwicklungsbericht: Vimeo-Smoke-Test

## Ziel

Einen ausdrücklich bestätigungspflichtigen echten Vimeo-Ende-zu-Ende-Test bereitstellen, der selbst einen winzigen gültigen MP4-Clip erzeugt, die vorhandene Publishing-Kette nutzt und keinen produktiven Predigt-Workflow-State verändert.

## Geänderte Dateien

- `src/predigt_uploader/publishing/vimeo_smoke.py` neu
- `src/predigt_uploader/publishing/vimeo.py`
- `src/predigt_uploader/cli.py`
- `tests/test_vimeo.py`
- `README.md`
- `STATUS.md`
- `TASKS.md`
- `docs/publishing-architecture.md`
- `docs/vimeo-development.md`
- dieser Entwicklungsbericht

## Was wurde umgesetzt?

- `vimeo-smoke-test` stoppt ohne `--confirm-vimeo-upload` vor Config-/Token-Laden, FFmpeg und allen Vimeo-Anfragen.
- Nach Freigabe werden Token, authentifizierter Nutzer, Team-Owner und die exakte Folder-ID über den bestehenden Preflight geprüft.
- FFmpeg erzeugt einen vier Sekunden langen schwarzen 320×180-H.264-MP4-Clip mit stiller AAC-Stereospur. Der tatsächliche Umfang hängt von der FFmpeg-Version ab, liegt bei diesem nahezu konstanten Inhalt aber typischerweise nur im KiB- bis niedrigen zweistelligen KiB-Bereich.
- Clip und vollständiger `WorkflowState` liegen nur in einem `TemporaryDirectory`. `VimeoPublishingService.publish()` übernimmt unverändert Videoanlage über `/me/videos`, tus-Streaming, Resume-/ID-Persistenz, Uploadverifikation, Folder-Zuordnung und Embed-Abruf.
- Nach dem Publishing wird das Video erneut geladen. `transcode.status` wird mit begrenztem Timeout und Backoff beobachtet; `privacy.view`, `privacy.embed`, Player-/Embed-Daten und bei `whitelist` `/videos/{id}/privacy/domains` werden angezeigt.
- Fehlt der Embed-Code zunächst, wird die vorhandene Refresh-Logik nochmals verwendet. Es entsteht kein zweiter Remote-Platzhalter.
- Die Ergebnisübersicht nennt alle Stufen, Video-ID/-URI/-URL, Remote-Name, Upload-/Transkodierungsstatus, Privacy und eine gekürzte Embed-Vorschau. Der vollständige Embed-Wert bleibt im Ergebnisdatensatz verfügbar.
- Das Remote-Testvideo bleibt standardmäßig bestehen. `--delete-after-test` verwendet ausschließlich `DELETE /videos/{id}` mit der während genau dieses Laufs gespeicherten numerischen ID. Bei Fehler oder Polling-Zeitlimit wird nicht automatisch gelöscht.
- Lokale temporäre Dateien werden bei Erfolg und Fehler entfernt. Eine bekannte Remote-ID wird bei Fehlern in der CLI-Diagnose ausgegeben.
- Der normale Wizard, Textual, WordPress und produktive `predigt-workflow.json` wurden nicht angebunden oder verändert.

Die API-Entscheidungen wurden am 31.08.2026 gegen Vimeos offizielle Dokumentation geprüft: Video-Response mit `transcode.status` und Privacy, Video-Interaktion mit Domain-Allowlist, oEmbed und API-Referenz für das ID-genaue Löschen.

## Tests

- gezielte Vimeo-Suite: 47 Tests bestanden
- vollständiger erster Lauf: 360 bestanden, ein timingabhängiger bestehender Textual-Pilot-Test schlug beim animierten Scrollen fehl
- derselbe Textual-Test isoliert: bestanden
- vollständiger Wiederholungslauf über `scripts/test.ps1`: **361 Tests bestanden**
- `python -m compileall -q src`: bestanden
- CLI-Hilfe: `vimeo-smoke-test` und beide Sicherheitsschalter sichtbar
- Smoke-Test ohne Freigabe real aufgerufen: kein Clip, kein Config-/Token-Laden, kein Vimeo-Zugriff
- normale Tests verwenden ausschließlich Fake-/Stub-Transporte; kein echter Vimeo-Netzwerkzugriff

## Offene Punkte / Risiken

- Der echte Konto-Smoke-Test wurde bewusst nicht durch Codex gestartet. Uploadrecht, Teamfolder-Schreibrecht, reale Defaults und Embed-Verhalten sind erst danach praktisch bewiesen.
- Vimeo kann länger als das lokale Polling-Zeitlimit transkodieren. Dann bleiben ID und URL sichtbar und das Video erhalten.
- `privacy.embed=whitelist` beweist nur die Vimeo-Konfiguration; die spätere WordPress-Domain muss zusätzlich einen echten Player-Aufruf bestehen.
- FFmpeg muss `libx264` und AAC enthalten. Fehlt ein Encoder, bricht der Test vor dem Vimeo-POST mit FFmpeg-Diagnose ab.
- Eine optionale Löschung kann an fehlenden Vimeo-Rechten scheitern. Das Video bleibt dann erhalten und seine ID wird ausgegeben.

## Nächster sinnvoller Schritt

Zuerst ohne Upload prüfen:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-smoke-test `
  --config "$env:APPDATA\PredigtUploader\config.toml"
```

Danach den echten kleinen Test bewusst starten und das Video zunächst behalten:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-smoke-test `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --confirm-vimeo-upload
```

Anschließend ID, Teamfolder, Privacy und Wiedergabe im Vimeo-Webinterface mit der CLI-Ausgabe vergleichen. Erst nach diesem Praxistest sollte der produktive Vimeo-Schritt in einer dünnen Bedienebene geplant werden.
