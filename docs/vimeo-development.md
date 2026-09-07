# Vimeo-Publishing: Einrichtung und sicherer Test

## Umfang

Die Vimeo-Schicht ist implementiert und wird vom produktiven Textual-Workflow als eigener achter Schritt verwendet. Der normale Wizard bleibt lokal. `vimeo-diagnose` und `vimeo-check` laden kein Video hoch. Die CLI-Kommandos `vimeo-upload` und `vimeo-smoke-test` benötigen weiterhin den zusätzlichen Schalter `--confirm-vimeo-upload`. In Textual beginnt ein Upload ausschließlich nach Klick auf `Video jetzt auf Vimeo hochladen`; das bloße Betreten des Screens erzeugt weder Service noch Netzwerkzugriff.

## Vimeo-App und Berechtigungen

Für die Vimeo-App muss Vimeo den Upload-Zugriff freigeschaltet haben. Der persönliche Zugriffstoken benötigt für diesen Ablauf mindestens die Scopes `public`, `private`, `upload`, `edit` und für die Folder-Interaktion `interact`. Zusätzlich muss der Vimeo-Benutzer im Team die tatsächlichen Rechte besitzen, Videos hochzuladen und dem Zielordner Elemente hinzuzufügen.

Vimeos `metadata.connections.videos.options` ist dafür kein verlässlicher Capability-Test: Beim realen Konto meldet die Connection nur `GET`, während ein authentifizierter Test-POST auf `/me/videos` den absichtlich ungültigen Upload-Body fachlich mit den erwarteten Parameterfehlern 2204/2230 verarbeitet hat. `vimeo-check` bricht wegen eines fehlenden `POST` in diesen Metadaten deshalb nicht mehr ab. Eine vollständig nicht-destruktive Upload- oder Folder-Schreibprobe stellt Vimeo nicht bereit; die Ausgabe weist ausdrücklich darauf hin, dass die eigentliche Upload-Berechtigung beim Upload geprüft wird.

Der Code verwendet API-Version 3.4. Relevante Endpunkte:

| Zweck | Methode und Endpoint |
|---|---|
| angemeldeten Benutzer prüfen | `GET /me` |
| Team-Owner lesen | `GET /users/{team_owner_user_id}` |
| Teamordner auflisten | `GET /users/{team_owner_user_id}/folders` |
| Teamordner erstellen | `POST /users/{team_owner_user_id}/folders` |
| Zielordner validieren | `GET /users/{team_owner_user_id}/folders/{folder_id}` |
| tus-Video für den authentifizierten Benutzer anlegen | `POST /me/videos` |
| tus-Fortschritt prüfen/übertragen | `HEAD`/`PATCH` auf Vimeos `upload_link` |
| Remote-Video und Embed-Daten lesen | `GET /videos/{video_id}` |
| Videos im Zielordner auflisten | `GET /users/{team_owner_user_id}/projects/{target_folder_id}/videos` (paginiert) |
| alle Videos des Team-Owners auflisten | `GET /users/{team_owner_user_id}/videos` (paginiert) |
| erlaubte Embed-Domains bei `privacy.embed=whitelist` lesen | `GET /videos/{video_id}/privacy/domains` |
| Video zum Teamordner hinzufügen | `POST /users/{team_owner_user_id}/projects/{folder_id}/items` |
| Ordnerzuordnung verifizieren | `GET /users/{team_owner_user_id}/projects/{folder_id}/videos` |
| Embed-Fallback | `GET https://vimeo.com/api/oembed.json?url=...` |
| ausschließlich das explizit identifizierte Testvideo löschen | `DELETE /videos/{video_id}` |

Vimeo nennt Ordner in neueren Antworten „folders“, verwendet in Mitgliedschafts-Endpunkten aber weiterhin „projects“. `/me` ist der authentifizierte Upload-Kontext aus Vimeos offiziellem tus-Ablauf. Der explizite Team-Owner bleibt für das Finden, Validieren und Beschreiben des Teamfolders maßgeblich. Die numerische `folder_id` ist die Identität; `target_folder_name` ist lediglich eine zusätzliche menschliche Kontrollprüfung.

Die Implementierung stützt sich auf Vimeos aktuelle offizielle Dokumentation: [Video Upload API](https://developer.vimeo.com/api/upload/videos), [Folder Guide](https://developer.vimeo.com/api/guides/folders), [API Reference](https://developer.vimeo.com/api/reference), [Video Response](https://developer.vimeo.com/api/reference/response/video), [Video- und Embed-Privacy](https://developer.vimeo.com/api/guides/videos/interact), [Authentication](https://developer.vimeo.com/api/authentication) und [oEmbed](https://developer.vimeo.com/api/oembed/videos). Der Stand wurde am 31.08.2026 geprüft.

Es wird bewusst die kleine HTTP-Bibliothek `requests` statt Vimeos Python-SDK verwendet. So bleiben der dokumentierte Upload-Endpoint `/me/videos`, der getrennte Teamfolder-Kontext, der über Neustarts persistierte tus-Link, serverseitige Resume-Offsets, begrenzte Stream-Lesegrößen und die Fake-Transport-Testgrenze sichtbar unter Kontrolle. Eine zusätzliche tus-/SDK-Abhängigkeit hätte für diesen konkreten Ablauf keinen Vorteil gebracht.

## Token sicher bereitstellen

Die zentrale Credential-Schicht prüft zuerst `PREDIGT_UPLOADER_VIMEO_TOKEN` und danach den Windows Credential Manager über `keyring`. Für den normalen `.cmd`-/Textual-Start wird der Token maskiert unter `Einstellungen > Vimeo` eingerichtet. Er gehört nicht in `config.toml`, `config.example.toml`, Workflow-State, Kommandoargumente, Logs oder das Repository und wird nach dem Speichern nie vollständig angezeigt.

Für eine einzelne PowerShell-Sitzung kann der Token ohne sichtbare Eingabe gesetzt werden:

```powershell
$vimeoSecureToken = Read-Host "Vimeo-Token" -AsSecureString
$env:PREDIGT_UPLOADER_VIMEO_TOKEN = [Net.NetworkCredential]::new("", $vimeoSecureToken).Password
```

Nach dem Test die PowerShell schließen oder die Prozessvariable entfernen:

```powershell
Remove-Item Env:PREDIGT_UPLOADER_VIMEO_TOKEN
```

Die Umgebungsvariable hat absichtlich Vorrang, damit CI und zeitlich begrenzte Entwicklungstests ohne Änderung des dauerhaften Windows-Eintrags arbeiten können. `keyring` ist eine normale Projektabhängigkeit; Setup und Systemcheck installieren beziehungsweise prüfen sie. Eine Klartext-`secrets.toml` wird nicht benötigt.

## Nicht geheime Zielkonfiguration

Die für diese Installation bestätigten nicht geheimen Zielwerte sind als Laufzeitdefaults hinterlegt. Dadurch funktionieren auch bestehende `config.toml`-Dateien ohne `[vimeo]`-Abschnitt, ohne dass sie umgeschrieben oder andere Einstellungen verändert werden. Optional können die Werte in `%APPDATA%\PredigtUploader\config.toml` oder einer bewusst über `--config` gewählten lokalen Datei explizit überschrieben werden:

```toml
[vimeo]
team_owner_user_id = "59930802"
target_folder_id = "1320477"
target_folder_name = "Predigten"
```

Die IDs identifizieren das bestätigte Teamkonto und den bestätigten Ordner dieses Projekts. Der Token bleibt davon getrennt und wird nie in der TOML-Datei gespeichert. Explizit konfigurierte andere Werte werden nicht überschrieben; fehlende IDs werden nicht aus Namen oder URLs geraten.

## Verbindung und IDs diagnostizieren – ohne Upload

1. Token nur für die aktuelle Sitzung setzen.
2. Zunächst `team_owner_user_id` und `target_folder_id` leer lassen und die eigene Vimeo-Identität anzeigen:

   ```powershell
   .\.venv\Scripts\python.exe -m predigt_uploader vimeo-diagnose --config "$env:APPDATA\PredigtUploader\config.toml"
   ```

3. Ist der angemeldete Benutzer selbst der tatsächliche Team-Owner, kann die numerische ID aus seiner `/users/{id}`-URI als `team_owner_user_id` eingetragen werden. Bei einem Teammitglied muss die ID des wirklichen Team-Owners verwendet werden; die eigene ID darf nicht geraten oder ersatzweise eingesetzt werden.
4. Diagnose erneut ausführen. Nun werden die unter diesem Owner zugänglichen Teamordner mit Name, Folder-/Project-ID, URI und soweit vorhanden Elternordner angezeigt.
5. Gewünschte ID und den exakt angezeigten Namen als `target_folder_id` und `target_folder_name` eintragen und Diagnose nochmals ausführen.

Die Diagnose legt kein Vimeo-Video an.

## Ziel und lokale Datei vorprüfen – ohne Upload

Mit einer fertigen `<MP4-Stem>.predigt-workflow.json` (alte passende `predigt-workflow.json` bleiben verwendbar):

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-check `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --state "C:\Pfad\zur\Predigt\<MP4-Stem>.predigt-workflow.json"
```

Die Ausgabe muss Verbindung, Team, Zielordner, Ordner-ID, MP4, Größe, Vimeo-Titel, `tus` und den Hinweis „Die eigentliche Upload-Berechtigung wird beim Upload geprüft.“ zeigen. Hart geprüft werden Token, angemeldeter Benutzer, Owner-Zugriff, Folder-Identität, Folder-Name und Folder-Owner. Upload- und Folder-Schreibrechte werden nicht aus unzuverlässigen `metadata.connections.*.options` erfunden. Es wird kein Video-Platzhalter angelegt.

## Isolierter Ende-zu-Ende-Smoke-Test

Für den ersten echten Test muss keine MP4 und keine Workflow-State-Kopie manuell vorbereitet werden. Das Admin-Kommando erzeugt einen ungefähr vier Sekunden langen schwarzen 320×180-Clip mit stiller AAC-Tonspur per FFmpeg. Clip und State liegen ausschließlich in einem temporären Verzeichnis und werden auch bei Fehlern lokal entfernt. Ein produktiver `predigt-workflow.json` wird weder gelesen noch verändert.

Zuerst das Kommando ohne Freigabe ausführen:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-smoke-test `
  --config "$env:APPDATA\PredigtUploader\config.toml"
```

Dieser Aufruf lädt bewusst noch nicht einmal Konfiguration oder Token, startet FFmpeg nicht und sendet keine Vimeo-Anfrage. Er beschreibt lediglich den Ablauf.

Der echte kleine Test beginnt ausschließlich mit:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-smoke-test `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --confirm-vimeo-upload
```

Der Ablauf ist: lesende Vorprüfung von `/me`, Team-Owner und Folder; lokale FFmpeg-Erzeugung; vorhandener `POST /me/videos`-/tus-Pfad; Uploadverifikation; vorhandene Folder-Zuordnung und erneute Mitgliedschaftsprüfung; erneutes Laden des Videos; begrenztes Polling von `transcode.status`; erneuter Abruf über die vorhandene `vimeo-embed`-Fachlogik; Ausgabe von Video-/Embed-Privacy und bei `whitelist` der Domain-Allowlist. Vimeo-Defaults für Privacy werden dabei nur gelesen und nicht verändert.

Die Transkodierung wird höchstens ungefähr zwei Minuten mit ansteigendem Polling-Intervall beobachtet. Ein Zeitlimit löscht oder dupliziert das Video nicht; die Ausgabe nennt ID und URL für eine spätere Kontrolle. Der Embed-Code kann bereits vor abgeschlossener Transkodierung verfügbar sein. Ist er noch nicht verfügbar, endet das Kommando mit einem eigenen Diagnose-Rückgabecode und lässt das Video erhalten.

Standardmäßig bleibt das Testvideo ausdrücklich im Konto, damit Folder und Einstellungen im Vimeo-Webinterface geprüft werden können. Nur der folgende bewusst kombinierte Aufruf löscht es nach einem ansonsten erfolgreichen Test:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-smoke-test `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --confirm-vimeo-upload `
  --delete-after-test
```

Die Löschung verwendet ausschließlich die numerische Video-ID, die während genau dieses isolierten Laufs im temporären State gespeichert wurde. Es gibt keine Suche nach Name oder Folder. Bei Upload-, Folder-, Transkodierungs- oder sonstigen Fehlern wird nicht automatisch gelöscht; bekannte URI/ID/URL werden für die manuelle Prüfung ausgegeben.

Das allgemeine Kommando `vimeo-upload --state ... --confirm-vimeo-upload` bleibt für spätere Tests eines echten lokalen Workflow-States vorhanden. Für den ersten Konto-Smoke-Test ist `vimeo-smoke-test` der sicherere Weg.

Der Smoke-Test wurde inzwischen bewusst am echten Teamkonto ausgeführt. Bestätigt sind Authentifizierung, Team-Owner „Immanuelgemeinde Wolfsburg“, Zielordner `Predigten` mit ID `1320477`, Video-Erstellung über `/me/videos`, tus-Upload, Uploadverifikation, Folder-Zuordnung, erneutes Abrufen, `transcode.status=complete` und der Embed-Abruf. Das Testvideo meldete `privacy.view=unlisted` und `privacy.embed=public`; externe Einbettung, Player-URL und vollständiger iframe-Code waren verfügbar. Diese Werte beschreiben den beobachteten Konto-Default und werden vom PredigtUploader weiterhin nicht ungefragt verändert.

## Produktiver Textual-Schritt

Nach dem erfolgreichen Erstellen von MP4, MP3, Zusammenfassung und `predigt-workflow.json` wechselt Textual von Schritt 7 zu Schritt 8 „Vimeo veröffentlichen“. Angezeigt werden lokale MP4, Team-/Ownerkontext, Zielordner, geplanter Vimeo-Titel und der gespeicherte Vimeo-Zustand. Das Öffnen ist nicht destruktiv und löst keinen Vimeo-Request aus.

Der blaue Button startet `VimeoPublishingService` in einem Textual-Thread-Worker. Der tus-Transport liest weiterhin höchstens 1 MiB auf einmal und meldet jeden tatsächlich in den HTTP-PATCH übernommenen Leseblock an den gemeinsamen Fortschrittscallback. Textual zeigt daraus Balken, Prozent, Bytes/Gesamtgröße sowie – sobald genug Zeit vergangen ist – mittlere Sitzungsgeschwindigkeit und grobe Restzeit. Die Stufen Verbindung, Remote-Video, Uploadprüfung, Folder-Zuordnung, Vimeo-Verarbeitung und Embed bleiben parallel sichtbar. UI-Aktualisierungen werden sicher in den App-Thread zurückgereicht; die Netzwerk- und Dateiübertragung blockiert die Textual-Ereignisschleife nicht. Während des Laufs sind Upload, Überspringen und abschließende Aktionen gesperrt, sodass kein zweiter Worker gestartet werden kann.

Nach Vergabe der Video-ID speichert der Service Link und Remote-Identität sofort und versucht den vorhandenen Embed-Abruf noch vor dem ersten tus-PATCH. Ist `embed.html` beziehungsweise ein sicherer Fallback bereits verfügbar, wird er atomar gespeichert; Textual aktiviert `Vimeo öffnen` und `Embed-Code kopieren` unabhängig vom weiterlaufenden Upload. Ein fehlender oder vorübergehend fehlerhafter früher Abruf ist ausdrücklich nicht fatal. Der Service versucht es nach der Übertragung erneut und behält den bisherigen abschließenden Pflichtabruf bei. Die UI unterscheidet deshalb `Embed-Code erhalten`, laufende Dateiübertragung und Vimeos spätere Verarbeitung als getrennte Stufen.

`transcode.status=in_progress` wird nur als laufende Vimeo-Verarbeitung angezeigt. Die produktive Publishing-Semantik wartet weiterhin nicht künstlich auf einen von Vimeo nicht gelieferten Prozentwert: Sind Upload, Folder und Embed vollständig, darf der lokale Publishing-Schritt abgeschlossen sein, während Vimeo noch transkodiert. `complete` wird als abgeschlossene Verarbeitung markiert.

Eine vorhandene Video-ID/-URI wird vom Service vor einer neuen Remote-Anlage geprüft und wiederverwendet. Bei einem Fehler bleiben lokale Dateien sowie bekannte Vimeo-Identität erhalten; der Nutzer kann kontrolliert erneut versuchen oder Vimeo als offen überspringen. Nach Erfolg stehen Vimeo öffnen, Embed-Code kopieren und Weiter zum Abschluss zur Verfügung. Der Abschluss unterscheidet Erfolg und offen/übersprungen. Ein Zurückspringen zu Schritt 7 wird bewusst nicht angeboten, weil die lokalen Dateien zu diesem Zeitpunkt bereits geschrieben sind; Überspringen ist die sichere sekundäre Aktion.

`Weiter zum Abschluss` öffnet nach einem erfolgreichen normalen Acht-Schritte-Workflow einen eigenen Gesamtabschluss. Er nennt MP4, MP3, Zusammenfassung, lokalen Zielordner, Vimeo-Titel/-URL/-Zielordner, Embed-Code und Transkodierungsstatus. Direct-Vimeo verwendet eine reduzierte Variante ohne Behauptungen über MP3 oder Zusammenfassung. Eine vollständig bestätigte Dateiübertragung bleibt erfolgreich, wenn `transcode.status=in_progress` ist; der Endscreen zeigt dann getrennt `Upload vollständig abgeschlossen` und `Vimeo verarbeitet das Video noch`.

Das Textual-Hauptmenü bietet `Direkt zu Vimeo hochladen (Admin / Sonderfall)`. Der Einstieg öffnet einen kleinen Dateibrowser im konfigurierten Aufnahmen-Basisordner. Er zeigt einen editierbaren Pfad, unmittelbare Unterordner sowie den aktuellen Ordnerinhalt mit Typ, Name, Änderungszeit und Größe. Navigation per Enter, Elternordner, Startordner und Refresh liest lazy nur den jeweils aktuellen Ordner. Fremde Dateitypen werden angezeigt, können aber nicht bestätigt werden. Erst `Ausgewählte MP4 für Vimeo verwenden` validiert die Datei erneut, verwendet einen passenden aufnahmespezifischen oder Legacy-State beziehungsweise legt einen minimalen isolierten State neben der MP4 an. Der folgende gemeinsame Publishing-Screen startet weiterhin keinen Upload von selbst. Eine automatische Liste aller unvollständigen States ist noch nicht umgesetzt.

## Upload, Resume und Fehlerzustände

Die MP4 wird per resumierbarem tus-Upload übertragen. Standardmäßig werden 128-MiB-tus-Blöcke verwendet; der HTTP-Transport liest daraus höchstens 1 MiB auf einmal und hält niemals die gesamte MP4 im RAM. Die sichtbare Byteanzeige läuft innerhalb eines PATCH fort, der Workflow-State speichert aber aus Sicherheitsgründen nur serverbestätigte Blockgrenzen. Nach temporären HTTP-/Netzwerkfehlern wird der bestätigte Vimeo-Offset erneut per `HEAD` gelesen; eine Anzeige darf dabei auf diesen sicheren Stand zurückspringen. `upload_uri`, bestätigter Offset und Gesamtgröße bleiben für Retry/Resume erhalten. Nach vollständigem Erfolg wird der nicht mehr benötigte tus-Link wieder entfernt.

Eine bekannte `video_id` oder `video_uri` wird vor einer weiteren Aktion remote geprüft und wiederverwendet. `complete` verhindert einen Doppelupload, `in_progress` ohne Remote-Identität stoppt sicher und `failed` darf kontrolliert erneut versucht werden. Eine von Vimeo bestätigte URI/ID wird sofort atomar gespeichert. Scheitern danach Upload, Folder-Zuordnung oder Embed-Abruf, bleibt die Remote-Identität erhalten und der Schritt wird mit bereinigter deutscher Fehlermeldung `failed`.

Wurde das bekannte Video außerhalb des PredigtUploaders gelöscht, setzt ein erneuter Versuch die gespeicherten Remote-Felder nur bei einem expliziten HTTP 404 zurück. Diese Entscheidung fällt erst nach erfolgreicher Token-, Team-Owner- und Folder-Prüfung. Lokale Predigtmetadaten und Dateipfade bleiben unverändert. Bei Timeout, fehlender Verbindung, 401/403, 429, 5xx oder einer sonst unklaren Antwort bleibt die bekannte ID erhalten und es wird kein zweites Video angelegt.

`Upload pausieren` ist nur während des tatsächlichen tus-Dateitransfers aktiv und setzt erst nach einem Bestätigungsdialog ein threadsicheres Flag. Der Worker prüft es zwischen den fachlichen Vimeo-Schritten und tus-Blöcken. Ein laufender PATCH darf sauber enden; anschließend wird dessen bestätigter Offset gespeichert und erst dann intern mit `step.status=stopped` beendet. Die TUI nennt bestätigte Bytes und Gesamtgröße. `Upload fortsetzen` verwendet dieselbe Video-ID, denselben tus-Link und den per HEAD bestätigten Remote-Offset. Wurde das Video zwischenzeitlich extern gelöscht, greift stattdessen die beschriebene 404-Behandlung. Pause bedeutet ausdrücklich: Remote-Eintrag und Resume-Stand bleiben erhalten; Early-Link und Embed bleiben verwendbar.

Während `running`, `pausing` und `aborting` zeigt der Vimeo-Screen einen eigenen orangefarbenen Sicherheitsblock: Der PredigtUploader soll bis zum Ende der aktiven Operation nicht geschlossen werden. Während `pausing` darf der aktuelle HTTP-PATCH noch sicher enden; Pause und endgültiger Abbruch sind in dieser Übergangsphase gegeneinander gesperrt. Erst nach dem gespeicherten Status `stopped` meldet ein grüner Block, dass das Schließen sicher ist. Die kontrollierte Beenden-Aktion der Textual-App zeigt bei aktiver Vimeo-Arbeit einen Bestätigungsdialog und empfiehlt die Pause; ein hartes Schließen des Windows-Terminals kann technisch nicht verhindert werden.

Der Sicherheitsblock liegt nicht in der scrollbaren Detailspalte. Während einer aktiven Vimeo-Operation ersetzt er platzsparend den normalen Hinweis auf sichere lokale Dateien und zeigt `PROGRAMM NICHT BEENDEN!` in einem kräftigen Warning-Stil. Fortschrittsstufen und Byteanzeige bleiben eigene Elemente. Der grüne Early-Link-/Embed-Bereich ist ebenfalls getrennt und nennt ausdrücklich, dass die Predigt bereits auf der Website angelegt werden kann.

Sind Vimeo-Link und Embed-Code früh verfügbar, weist ein grüner Block darauf hin, dass die Predigt bereits auf der Website angelegt werden kann, während der Upload im Hintergrund weiterläuft. Diese Verfügbarkeit hängt weder von 100 Prozent Dateiübertragung noch von abgeschlossener Transkodierung ab. `Vimeo öffnen` und `Embed-Code kopieren` bleiben auch nach einer sicheren Pause aktiv. `Lokalen Ordner öffnen` verwendet immer `paths.final_mp4.parent`, nicht den allgemeinen Aufnahme-Basisordner, und bleibt während Upload, Pause und Vimeo-Verarbeitung verfügbar.

`Upload endgültig abbrechen` ist davon getrennt. Nach eigener Danger-Bestätigung wird ein laufender Transfer zunächst ebenso kooperativ angehalten. Danach löscht `abort_upload()` ausschließlich die numerische Video-ID des aktuellen Workflow-States, wenn Schema 6 deren Anlage durch den PredigtUploader mit `remote_created_by_app=true` belegt. Für vor Schema 6 begonnene, noch resumefähige Uploads gilt ein vorhandener tus-Link zusammen mit `in_progress`, `stopped` oder `failed` als enger Kompatibilitätsnachweis. Erst ein erfolgreiches DELETE oder ein eindeutiges 404 setzt den Vimeo-Teil atomar auf `pending` zurück. Bei Timeout, 401/403, 429, 5xx oder unklarer Herkunft bleiben Video-ID, URL und Resume-State erhalten; der eigene Abschlussbildschirm nennt die unvollständige Bereinigung. Lokale MP4, MP3, Zusammenfassung, Pfade und Predigtmetadaten werden niemals gelöscht oder zurückgesetzt.

Nach bestätigtem endgültigem Abbruch sperrt die TUI Pause, Resume, erneuten Abbruch und Navigation. Sie zeigt zunächst das sichere Ende der Datenübertragung und anschließend Remote-Löschung sowie State-Bereinigung. Erst danach wird auf den bestehenden Abbruch-Abschluss gewechselt. Bei einem Cleanup-Fehler bleiben Remote-ID und URL sichtbar und der State erhalten; die Anzeige behauptet nicht fälschlich, der Vimeo-Eintrag sei entfernt worden.

### Dateiübertragung, Nachbearbeitung und Transkodierung

Diese drei Zustände werden fachlich getrennt:

- **Dateiübertragung:** tus überträgt die MP4; `upload.status=complete` und `uploaded_at` werden vor weiteren Schritten atomar gespeichert.
- **Vimeo-Nachbearbeitung:** Zielordnerzuordnung, deren Verifikation und Embed-Abruf folgen. Scheitert dieser Abschnitt, bleibt der Upload als vollständig übertragen bekannt. Ein Retry nutzt dieselbe Video-ID und überspringt den TUS-Transfer.
- **Vimeo-Transkodierung:** `transcode.status` ist ein eigener Remote-Zustand. `in_progress` blockiert den lokalen Abschluss nicht und erhält keinen erfundenen Prozentwert.

Die uploadfreie Verbindungskontrolle bestätigt Token, Benutzer, Team-Owner und Zielordner lesend. Vimeo bietet darüber keinen für alle benötigten Schreiboperationen zuverlässigen, nicht destruktiven Capability-Test. Die Anzeige nennt deshalb ausdrücklich, dass Upload-, Edit-, `interact`- und Delete-Rechte erst bei der jeweiligen Operation sicher geprüft werden. Liefert die Folder-Zuordnung HTTP 403 mit fehlendem `interact`-Scope, erscheint ein konkreter deutscher Hinweis zum Ersetzen des Tokens unter Einstellungen → Vimeo; Admin-Details bleiben erhalten.

Schema 6 ergänzt `remote_created_by_app` für das sichere endgültige Cleanup. Schema 7 speichert mit `workflow_origin=normal|direct_vimeo`, ob nach Vimeo der vollständige Aufnahmeabschluss oder der reduzierte Direct-Vimeo-Abschluss gezeigt werden muss. Alte States ohne dieses Feld gelten als normaler Workflow; Direct-Vimeo setzt die Herkunft bei Auswahl ausdrücklich und behält sie über Upload, Pause und Resume. Die vorhandenen Felder `video_uri`, `video_id`, `video_url`, Upload-/Transkodierungsstatus, Zielordner, Embed und tus-Resume-Daten bleiben unverändert. Schema 5 führte `stopped` ein. Sobald Vimeo die Übertragung remote als `complete` bestätigt, werden URL, Status und lokaler UTC-Bestätigungszeitpunkt gespeichert – noch bevor Folder-Zuordnung und Embed-Abruf folgen. Ältere Dateien bleiben lesbar und werden beim nächsten Speichern migriert; fehlender Herkunftsnachweis führt sicherheitshalber nicht zu einem automatischen DELETE.

## Embed-Code

Primär werden `embed.html` und `player_embed_url` aus der Video-Ressource verwendet. Fehlt `embed.html`, folgt oEmbed mit der vollständigen Video-URL; das ist bei „unlisted“-Videos wichtig, weil deren Hash Teil der URL ist. Als letzter kontrollierter Fallback kann aus `player_embed_url` ein iframe erzeugt werden. Die Werte werden im Workflow-State gespeichert.

Fehlt der Embed-Code später, kann er ohne erneuten Upload nachgeladen werden:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-embed `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --state "C:\Pfad\zur\Predigt\<MP4-Stem>.predigt-workflow.json"
```

## Vimeo-Bibliothek in Textual

`Vimeo-Bibliothek` im Hauptmenü lädt echte Videos aus dem konfigurierten Teamordner. Der Service verwendet den expliziten Team-Owner und die Folder-ID und folgt Vimeos `paging.next`, bis alle zugänglichen Seiten geladen sind. Jede geladene Seite wird sofort kumulativ an Textual gemeldet; bei einer von Vimeo gelieferten Gesamtzahl steht beispielsweise `100 / 606 Videos geladen – weitere werden geladen …`. Die bereits sichtbaren Videos bleiben auswählbar. Vollständig geladene Ergebnisse werden für die laufende App gecached; beim erneuten Öffnen ist kein neuer Komplettabruf nötig. `Neu laden` verwirft den passenden Owner-/Folder-Cache und ruft Vimeo erneut ab. Das Öffnen der Ansicht lädt nur lesend; es legt kein Video an, verändert keine Ordnerzuordnung und startet keinen Download. Netzwerkzugriffe laufen in einem Textual-Thread-Worker, sodass Loading-, Leer- und Fehlerzustände weiterhin bedienbar bleiben.

Die Tabelle zeigt Titel, Erstellungsdatum, Verarbeitungsstatus und Dauer. Nach Auswahl stehen – abhängig von den tatsächlich gelieferten Daten – Vimeo öffnen, Link kopieren, Embed kopieren und Details zur Verfügung. Die Titelsuche filtert die bereits geladenen Ergebnisse; eine spätere serverseitige Suche oder Auswahl mehrerer Ordner kann auf dem UI-unabhängigen Bibliotheksergebnis aufbauen.

Vimeo kann je nach Konto, Token, Privacy und Video im Feld `download` zeitlich begrenzte Downloadvarianten liefern. Nur solche expliziten HTTPS-Links werden als Download-Capability akzeptiert und mit Qualität, Auflösung, Größe und Typ angezeigt. Das Vorhandensein von `files`, einer Player-URL oder eines Embed-Codes wird nicht als Downloadrecht interpretiert. In dieser ersten Version gibt es deshalb noch keinen Datei-Download; fehlt `download`, bleibt die Aktion deaktiviert, ohne den restlichen Browser zu beeinträchtigen.

Vimeos Konto-/Video-Defaults für Privacy werden beim Anlegen nicht überschrieben. Der Smoke-Test zeigt `privacy.view`, `privacy.embed`, `embed.html`, `player_embed_url` und bei `whitelist` die von Vimeo gemeldeten erlaubten Domains. Laut offizieller Vimeo-Semantik bedeutet `public` frei einbettbar, `private` nicht extern einbettbar und `whitelist` nur auf den gelisteten Domains. Diese reale Ausgabe und die Wiedergabe auf der späteren WordPress-Domain müssen vor der WordPress-Phase zusätzlich im Browser geprüft werden.

### Ordnerwahl und zwei Bibliothekssichten

Normale Nutzer wählen den Standard-Zielordner in Textual primär nach Namen; die gespeicherte technische ID wird zur Kontrolle mit angezeigt. Der Folderkatalog bildet Unterordner und Breadcrumbs aus den von Vimeo gelieferten URIs. `Neuen Ordner erstellen` zeigt Zielpfad und Namen in einem Bestätigungsdialog. Für Unterordner wird die echte `parent_folder_uri` gesendet. Nach Erfolg wird der Katalog neu geladen und der neue Ordner geöffnet, sodass er unmittelbar mit der separaten Aktion als Standardziel bestätigt werden kann. Allein durch die Anlage wird das neue Ziel weiterhin nicht gespeichert. Fehlt der gespeicherte Ordner, wird gewarnt und nichts automatisch ersetzt.

`Alle Videos` verwendet `GET /users/{owner}/videos`, `Ordner` den Folderkatalog und je geöffnetem Ordner dessen `/projects/{id}/videos`-Liste. Beide laufen im Thread-Worker, veröffentlichen Videoseiten progressiv und verwenden nur sitzungsweite Caches. `Neu laden` erzwingt einen API-Refresh. Fehlt `download`, bleibt die Downloadaktion deaktiviert. Ist ein expliziter HTTPS-Link vorhanden, öffnet die Aktion den ersten von Vimeo gelieferten Link im Standardbrowser; Qualitäts- und lokale Zielauswahl bleiben ein möglicher späterer Ausbau.
