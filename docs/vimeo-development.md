# Vimeo-Publishing: Einrichtung und sicherer Test

## Umfang

Die Vimeo-Schicht ist implementiert, aber noch nicht in den normalen Wizard oder den Textual-Workflow eingebaut. Die Entwicklungskommandos werden ausschließlich bewusst aufgerufen. `vimeo-diagnose` und `vimeo-check` laden kein Video hoch. Ein Upload beginnt nur mit dem Kommando `vimeo-upload`, einem Workflow-State und dem zusätzlichen Schalter `--confirm-vimeo-upload`.

## Vimeo-App und Berechtigungen

Für die Vimeo-App muss Vimeo den Upload-Zugriff freigeschaltet haben. Der persönliche Zugriffstoken benötigt für diesen Ablauf mindestens die Scopes `public`, `private`, `upload`, `edit` und `interact`. Zusätzlich muss der Vimeo-Benutzer im Team die tatsächlichen Rechte besitzen, unter dem Team-Owner Videos anzulegen und dem Zielordner Elemente hinzuzufügen. Die Vorprüfung kontrolliert dies über reale API-Zugriffe und die von Vimeo gemeldeten erlaubten Methoden; ein Scope-Name allein ist kein Berechtigungsnachweis.

Der Code verwendet API-Version 3.4. Relevante Endpunkte:

| Zweck | Methode und Endpoint |
|---|---|
| angemeldeten Benutzer prüfen | `GET /me` |
| Team-Owner und Uploadmöglichkeit prüfen | `GET /users/{team_owner_user_id}` |
| Teamordner auflisten | `GET /users/{team_owner_user_id}/folders` |
| Zielordner validieren | `GET /users/{team_owner_user_id}/folders/{folder_id}` |
| Video unter Team-Owner anlegen | `POST /users/{team_owner_user_id}/videos` |
| tus-Fortschritt prüfen/übertragen | `HEAD`/`PATCH` auf Vimeos `upload_link` |
| Remote-Video und Embed-Daten lesen | `GET /videos/{video_id}` |
| Video zum Teamordner hinzufügen | `POST /users/{team_owner_user_id}/projects/{folder_id}/items` |
| Ordnerzuordnung verifizieren | `GET /users/{team_owner_user_id}/projects/{folder_id}/videos` |
| Embed-Fallback | `GET https://vimeo.com/api/oembed.json?url=...` |

Vimeo nennt Ordner in neueren Antworten „folders“, verwendet in Mitgliedschafts-Endpunkten aber weiterhin „projects“. `/me` ist nur der angemeldete Benutzer und wird daher nicht als Ersatz für den Team-Owner verwendet. Die numerische `folder_id` ist die Identität; `target_folder_name` ist lediglich eine zusätzliche menschliche Kontrollprüfung.

Die Implementierung stützt sich auf Vimeos aktuelle offizielle Dokumentation: [Video Upload API](https://developer.vimeo.com/api/upload/videos), [Folder Guide](https://developer.vimeo.com/api/guides/folders), [API Reference](https://developer.vimeo.com/api/reference), [Video Response](https://developer.vimeo.com/api/reference/response/video), [Authentication](https://developer.vimeo.com/api/authentication) und [oEmbed](https://developer.vimeo.com/api/oembed/videos). Der Stand wurde am 31.08.2026 geprüft.

Es wird bewusst die kleine HTTP-Bibliothek `requests` statt Vimeos Python-SDK verwendet. So bleiben der explizite Team-Owner-Endpoint `/users/{id}/videos`, der über Neustarts persistierte tus-Link, serverseitige Resume-Offsets, begrenzte Stream-Lesegrößen und die Fake-Transport-Testgrenze sichtbar unter Kontrolle. Eine zusätzliche tus-/SDK-Abhängigkeit hätte für diesen konkreten Ablauf keinen Vorteil gebracht.

## Token sicher bereitstellen

Aktuell wird ausschließlich die Umgebungsvariable `PREDIGT_UPLOADER_VIMEO_TOKEN` gelesen. Der Token gehört nicht in `config.toml`, `config.example.toml`, `predigt-workflow.json`, Kommandoargumente, Logs oder das Repository.

Für eine einzelne PowerShell-Sitzung kann der Token ohne sichtbare Eingabe gesetzt werden:

```powershell
$vimeoSecureToken = Read-Host "Vimeo-Token" -AsSecureString
$env:PREDIGT_UPLOADER_VIMEO_TOKEN = [Net.NetworkCredential]::new("", $vimeoSecureToken).Password
```

Nach dem Test die PowerShell schließen oder die Prozessvariable entfernen:

```powershell
Remove-Item Env:PREDIGT_UPLOADER_VIMEO_TOKEN
```

Eine `%APPDATA%\PredigtUploader\secrets.toml` und Windows Credential Manager sind noch nicht implementiert. Falls später eine dauerhafte Ablage gebraucht wird, ist Windows Credential Manager gegenüber einer Klartextdatei zu bevorzugen, sofern der zusätzliche Wartungsaufwand vertretbar bleibt.

## Nicht geheime Zielkonfiguration

In `%APPDATA%\PredigtUploader\config.toml` oder einer bewusst über `--config` gewählten lokalen Datei:

```toml
[vimeo]
team_owner_user_id = "123456789"
target_folder_id = "987654321"
target_folder_name = "Predigten"
```

Die Zahlen sind nur Beispiele und dürfen nicht übernommen werden. Fehlende IDs werden nicht geraten.

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

Mit einer fertigen `predigt-workflow.json`:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-check `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --state "C:\Pfad\zur\Predigt\predigt-workflow.json"
```

Die Ausgabe muss Verbindung, Team, Zielordner, Ordner-ID, MP4, Größe, Vimeo-Titel und `tus` zeigen. Dabei werden Token, Owner-Zugriff, Folder-Identität, Folder-Name sowie Upload-/Zuordnungsrechte geprüft. Es wird kein Video-Platzhalter angelegt.

## Bewusster erster Testupload

Zuerst ein kleines, unkritisches Testvideo mit einer eigenen Workflow-State-Kopie verwenden. Nach erfolgreichem `vimeo-check` lautet der bewusste Aufruf:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-upload `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --state "C:\Pfad\zum\Test\predigt-workflow.json" `
  --confirm-vimeo-upload
```

Ohne `--confirm-vimeo-upload` zeigt das Kommando nur die Vorprüfung und stoppt. Nach dem Test müssen in Vimeo die Video-ID, der Team-Owner und insbesondere die sichtbare Mitgliedschaft im gewünschten Teamordner manuell gegengeprüft werden. Das Tool setzt `vimeo.step.status` erst dann auf `complete`, wenn dieselbe Zuordnung auch per API verifiziert wurde und Embed-Daten vorhanden sind.

## Upload, Resume und Fehlerzustände

Die MP4 wird per resumierbarem tus-Upload übertragen. Standardmäßig werden 128-MiB-tus-Blöcke verwendet; der HTTP-Transport liest daraus höchstens 1 MiB auf einmal und hält niemals die gesamte MP4 im RAM. Nach temporären HTTP-/Netzwerkfehlern wird der bestätigte Vimeo-Offset erneut per `HEAD` gelesen. `upload_uri`, Offset und Gesamtgröße werden während eines offenen Vorgangs im Workflow-State gespeichert; der Remote-Offset bleibt beim Fortsetzen maßgeblich. Nach vollständigem Erfolg wird der nicht mehr benötigte tus-Link wieder entfernt.

Eine bekannte `video_id` wird vor einer weiteren Aktion remote geprüft und wiederverwendet. `complete` verhindert einen Doppelupload, `in_progress` ohne ID stoppt sicher und `failed` darf kontrolliert erneut versucht werden. Eine von Vimeo bestätigte ID wird sofort atomar gespeichert. Scheitern danach Upload, Folder-Zuordnung oder Embed-Abruf, bleibt die ID erhalten und der Schritt wird mit bereinigter deutscher Fehlermeldung `failed`.

## Embed-Code

Primär werden `embed.html` und `player_embed_url` aus der Video-Ressource verwendet. Fehlt `embed.html`, folgt oEmbed mit der vollständigen Video-URL; das ist bei „unlisted“-Videos wichtig, weil deren Hash Teil der URL ist. Als letzter kontrollierter Fallback kann aus `player_embed_url` ein iframe erzeugt werden. Die Werte werden im Workflow-State gespeichert.

Fehlt der Embed-Code später, kann er ohne erneuten Upload nachgeladen werden:

```powershell
.\.venv\Scripts\python.exe -m predigt_uploader vimeo-embed `
  --config "$env:APPDATA\PredigtUploader\config.toml" `
  --state "C:\Pfad\zur\Predigt\predigt-workflow.json"
```

Vimeos Konto-/Video-Defaults für Privacy werden beim Anlegen nicht überschrieben. Domainbeschränkungen und private/unlisted Wiedergabe müssen vor der WordPress-Phase mit den echten Konto- und Embed-Einstellungen geprüft werden.
