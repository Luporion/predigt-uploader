# Publishing-Architektur

## Ausgangspunkt

Wizard und Textual verwenden weiterhin ihre vorhandenen Ablauf- und Planstrukturen. Die gemeinsame Fachlogik für Dateinamen, Zielordner, Konflikte, Verarbeitung und Berichte bleibt die Basis. Es wurde keine zweite Processing-Architektur eingeführt.

Nach einer erfolgreichen lokalen Verarbeitung schreiben beide Oberflächen aufnahmespezifische Begleitdateien: `<MP4-Stem>.predigt-workflow.json` und `<MP4-Stem> - Zusammenfassung.txt`. Sie ersetzen die MP4/MP3 nicht und kollidieren auch dann nicht, wenn mehrere Aufnahmen denselben Tagesordner verwenden. Alte generische `predigt-workflow.json`-Dateien bleiben lesbar; die Auflösung akzeptiert sie nur bei exakt passendem gespeichertem `paths.final_mp4`.

## Workflow-State

`src/predigt_uploader/workflow_state.py` enthält das UI-unabhängige Datenmodell und die JSON-Persistenz. Gespeichert werden:

- Predigtdaten aus dem vorhandenen `SermonInfo`
- Rohaufnahme, Schnittdatei, finale MP4, finale MP3, Zusammenfassung und Zielordner
- `local_preparation`
- `vimeo` mit Schritt-/Uploadstatus, Uploadzeitpunkt, Video-ID/-URI/-URL, Player-/Embed-Daten, Team-Owner, Zielordner und tus-Wiederaufnahmedaten
- `wordpress_audio` mit späterer Medien-ID und URL
- `wordpress_post` mit späterer Beitrags-ID und URL
- Schema-Version und Änderungszeitpunkt

Jeder Schritt verwendet die einfachen Zustände `pending`, `in_progress`, `complete` oder `failed`; Vimeo kann zusätzlich `stopped` für einen bewusst unterbrochenen, fortsetzbaren Vorgang verwenden. Neue Publishing-Schritte stehen zunächst auf `pending`. Schema 3 ergänzte expliziten Uploadstatus/-zeitpunkt und `target_folder_*`; Schema 4 ergänzte `transcode_status` und den verifizierten `folder_status`; Schema 5 ergänzt den persistenten Stopzustand. Schema-1/2/3/4-Dateien bleiben lesbar und werden beim nächsten Speichern auf den aktuellen Stand geschrieben. Die Datei wird UTF-8-codiert über eine temporäre Datei im selben Ordner geschrieben und anschließend atomar ersetzt. Fehlende optionale Felder aus älteren Zuständen erhalten sichere Standardwerte.

## Modulkette

Der nächste Ausbau soll schrittweise erfolgen:

1. lokaler Workflow lädt oder erzeugt `WorkflowState`
2. `publishing/vimeo.py` validiert Konto und Teamordner und legt den tus-Upload über `POST /me/videos` an
3. Vimeo-ID und Vimeo-URL werden sofort atomar gespeichert; der Embed-Code wird unmittelbar opportunistisch abgerufen
4. ein WordPress-Modul lädt die finale MP3 hoch und speichert Medien-ID/URL
5. der Beitrag wird erstellt oder aktualisiert; Post-ID/URL werden gespeichert
6. Textual zeigt Status und Nutzerentscheidungen an; der Wizard bleibt vorerst lokal

Die Vimeo-Schicht ist UI-unabhängig. `VimeoPublishingService` enthält die Ablauf- und Zustandslogik, ein kleines `VimeoTransport`-Protocol trennt HTTP für Tests ab. `RequestsVimeoTransport` implementiert die echten API- und tus-Anfragen. `vimeo-check` nutzt nur GET-Prüfungen und behandelt `metadata.connections.*.options` nicht als belastbaren Schreibberechtigungsnachweis.

Textual ruft nach erfolgreicher lokaler Verarbeitung einen eigenen achten Screen auf. Das Anzeigen dieses Screens ist rein lokal: Erst der primäre Uploadbutton erzeugt den Service. `VimeoPublishingService.preview_upload()` und `publish()` laufen als Textual-Thread-Worker, Fortschrittscallbacks werden über `App.call_from_thread` in die Oberfläche zurückgeführt. Der HTTP-Transport meldet jeden aus dem begrenzten Dateistream in den laufenden tus-PATCH übernommenen Block; der Service ergänzt Prozent, mittlere Sitzungsgeschwindigkeit und Restzeitschätzung. Dadurch bleibt die Ereignisschleife auch bei mehrgigabytegroßen tus-Uploads bedienbar. Die UI hält keine parallele Vimeo-Fachlogik; Schritt 8 und der Direkteinstieg nutzen denselben Screen, Resume, Doppelschutz, Folder und Embed bleiben vollständig im Service. Der normale Wizard startet Vimeo weiterhin nicht.

Direkt nach der Remote-Anlage speichert der Service URI, ID und einen bereits gelieferten Vimeo-Link. Anschließend versucht er `embed.html` beziehungsweise die bestehende Player-/oEmbed-Kette abzurufen. Dieser frühe Abruf ist opportunistisch: Erfolg wird atomar gespeichert und sofort an Textual gemeldet, ein vorübergehendes Fehlen oder ein API-Fehler unterbricht den tus-Upload jedoch nicht. Nach bestätigter Übertragung wird erneut versucht; der abschließende Pflichtabruf bleibt Teil der bestehenden Erfolgskriterien. Deshalb können `Vimeo öffnen` und `Embed-Code kopieren` bereits während der Übertragung aktiv sein, ohne Upload- und Transkodierungsstatus zu vermischen.

Die Vimeo-Bibliothek ist ein weiterer lesender Verbraucher derselben Service-/Transportgrenze. `list_target_folder_videos()` führt zunächst die bestehende Konto-, Team-Owner- und Folder-Prüfung aus und lädt danach alle Seiten von `GET /users/{team_owner_user_id}/projects/{target_folder_id}/videos`. Nach jeder Seite liefert der Service ein kumulatives Ergebnis mit optionaler Gesamtzahl und Abschlusskennzeichen an Textual. So ist die erste Seite sofort auswählbar, während der Worker weitere Seiten lädt. Vollständige Ergebnisse werden anhand Owner-/Folder-ID für die Laufzeit der App gecached; `Neu laden` invalidiert diesen Cache bewusst. Das Backend normalisiert Video-, Status-, Privacy-, Embed- und Download-Metadaten; die Titelsuche filtert jeweils die bereits geladenen Videos. Als Download-Capability gelten ausschließlich explizite HTTPS-Einträge aus Vimeos `download`-Feld. `files`- oder Player-URLs werden nicht als Download geraten; die erste Bibliotheksversion zeigt vorhandene Varianten nur an und startet keinen Download.

Der Textual-Direkteinstieg für bereits fertige externe MP4-Dateien ist nur eine weitere Zuleitung zu diesem Screen. Er sucht den zur MP4 gehörenden State, erkennt passende Legacy-States oder erzeugt einen minimalen lokalen `complete`-State. Upload und Resume bleiben vollständig beim bestehenden Service. Der Einstellungen-Screen aktualisiert die vorhandene AppConfig-Persistenz; geheime Tokens laufen ausschließlich über die zentrale Credential-Abstraktion.

`publishing/vimeo_smoke.py` ist bewusst nur eine dünne Admin-Orchestrierung über dieser Schicht. Sie erzeugt den kleinen FFmpeg-Clip und einen vollständigen, aber ausschließlich temporären `WorkflowState`; Upload, Resume, Folder-Zuordnung, Verifikation und Embed-Abruf bleiben Aufgaben des bestehenden `VimeoPublishingService`. Dadurch existiert weder eine zweite Vimeo-Implementierung noch eine Verbindung zu einem produktiven `predigt-workflow.json`. Für den Praxistest ergänzt die Orchestrierung begrenztes Polling von `transcode.status`, die Anzeige der Vimeo-Privacy und optional `DELETE /videos/{video_id}`. Gelöscht wird ausschließlich die im isolierten Lauf atomar gespeicherte ID, nie per Namens- oder Ordnersuche.

## Wiederaufnahme und Doppelschutz

Vor einem Upload liest die Publishing-Schicht die Statusdatei. `local_preparation` muss `complete` sein und die finale MP4 muss als nichtleere Datei existieren. Ein als `complete` markiertes Vimeo-Video wird remote geprüft und nie automatisch erneut hochgeladen. Bei `in_progress` ohne Video-ID wird sicher gestoppt; mit Video-ID wird das Remote-Video wiederverwendet. Bei `failed` ist ein kontrollierter Wiederholungsversuch möglich. Sobald Vimeo eine Video-ID liefert, wird sie atomar gespeichert. Beim Resume ist der per tus-`HEAD` gelesene Remote-Offset maßgeblich, nicht nur der lokal gemerkte Offset. Die häufigeren UI-Ereignisse werden nicht als unbestätigte Resume-Offsets gespeichert: Atomar persistiert wird weiterhin erst der von Vimeo bestätigte Offset eines PATCH-Blocks. Nach einem Übertragungsfehler kann die Anzeige deshalb auf den erneut per `HEAD` bestätigten sicheren Stand zurückgehen.

Vor jeder Wiederverwendung einer bekannten Video-ID wird das Remote-Video gelesen. Erst nach erfolgreicher Token-, Team- und Folder-Vorprüfung gilt ein explizites HTTP 404 als eindeutig fehlendes beziehungsweise extern gelöschtes Video. Dann wird ausschließlich `WorkflowState.vimeo` auf einen frischen Pending-Zustand gesetzt; lokale Metadaten und Pfade bleiben unverändert. Timeouts, 401/403, 429, 5xx und alle sonstigen unklaren Antworten verändern den State nicht und erlauben keine neue Remote-Anlage.

Textual übergibt dem Service beim Publish ein threadsicheres Cancellation-Flag. Ein bestätigter Stop setzt dieses Flag erst nach einem Dialog. Der Service prüft es zwischen Remote-Phasen und tus-Blöcken, beendet keinen laufenden HTTP-PATCH hart und speichert nach einem erfolgreichen PATCH zuerst den von Vimeo bestätigten Offset. `stopped` behält Video-ID, tus-Link, Uploadgröße und bestätigten Offset. Ein erneuter Publish führt erneut Remote-Prüfung und tus-HEAD aus und setzt denselben Upload fort. Es erfolgt kein automatisches Vimeo-DELETE.

Vimeo gilt erst als `complete`, wenn die Übertragung bestätigt, das Remote-Video auffindbar, die Zuordnung zum konfigurierten Teamordner erfolgt und über dessen Videoliste verifiziert sowie ein verwendbarer Embed-Code ermittelt wurde. Ein Fehler nach dem Upload setzt den Schritt auf `failed`, behält aber Video-ID, tus-Link und bekannte Remote-Daten.

## Secrets

Zugangsdaten gehören niemals in Git, `config.example.toml`, Release-ZIPs, Logs oder `predigt-workflow.json`.

Aktuell implementiert ist:

- zentrale Priorität `PREDIGT_UPLOADER_VIMEO_TOKEN` vor Windows Credential Manager (`keyring`);
- nicht geheime Team-Owner-/Folder-IDs in `[vimeo]` der normalen lokalen Konfiguration;
- Token-Bereinigung in HTTP-Fehlern und kein Speichern im Workflow-State;
- maskierte Einrichtung, Statusanzeige und Entfernung über `Einstellungen > Vimeo`;
- kein Rücklesen oder Anzeigen des vollständigen Tokens in der Oberfläche.

Das Repository ignoriert `secrets.toml` und `*.secrets.toml`; das Release-Skript schließt diese Namen zusätzlich aus. `config.example.toml` enthält keine Credential-Platzhalter, die versehentlich mit echten Werten befüllt und verteilt werden könnten.

## Praktisch bestätigter Vimeo-Pfad

Der isolierte reale Smoke-Test hat am Gemeinde-Teamkonto `/me/videos`, tus, erneute Uploadprüfung, Zuordnung zum Teamfolder `Predigten` (ID `1320477`), Transkodierung und Embed-Code bestätigt. Das reale Video meldete `privacy.view=unlisted`, `privacy.embed=public`, eine verwendbare Player-URL und einen vollständigen iframe-Code. Der Smoke-Test bleibt als getrenntes, bestätigungspflichtiges Diagnosekommando erhalten.

## Noch nicht implementiert

- Vimeo-Ausführung im normalen Wizard
- automatische Auflistung unvollständiger produktiver Vimeo-States im Textual-Startmenü (manuelle MP4-Auswahl ist vorhanden)
- tatsächliches Herunterladen einer in der Vimeo-Bibliothek angezeigten Download-Variante
- interaktiver Vimeo-OAuth-/Login-Flow
- WordPress REST API, Medien-Upload oder Beitrag

## Nächster Implementierungsschritt

Als Nächstes soll der achte Textual-Schritt manuell mit einer kleinen bewussten Aufnahme geprüft werden: einmal Überspringen, einmal erfolgreicher Upload mit Fortschritt, URL, Embed-Kopie und Abschlussstatus. Danach ist die WordPress-Schicht der nächste große Publishing-Baustein. Die Startmenü-Wiederaufnahme eines unvollständigen Vimeo-States bleibt eine klar abgegrenzte kleinere UX-Aufgabe.

## Folder-Browser und Bibliothekssichten

Settings und Vimeo-Bibliothek verwenden gemeinsam `VimeoFolder`, `VimeoFolderCatalog` und dieselbe `VimeoPublishingService`-/Transportgrenze. Der Katalog normalisiert Folder-ID, Name, URI und Eltern-URI und liefert Kinder sowie Breadcrumbs. `get_folder_catalog()`, `create_folder()`, `list_all_videos()` und `list_folder_videos()` bleiben vollständig UI-unabhängig.

Alle Videos folgt paginiert `GET /users/{owner}/videos`; die Ordneransicht lädt pro geöffnetem Ordner `GET /users/{owner}/projects/{folder}/videos`. Nach jeder Videoseite wird ein kumulatives Ergebnis an Textual geliefert. Katalog und vollständige Videolisten werden nur für die App-Sitzung pro Owner/Ansicht/Folder gecached; `Neu laden` invalidiert passend.

Neue Ordner entstehen ausschließlich nach Bestätigung über `POST /users/{owner}/folders` mit `name` und für Unterordner mit Vimeos tatsächlicher `parent_folder_uri`. Das Anlegen ändert die Uploadkonfiguration nicht. Erst die ausdrückliche Auswahl speichert `target_folder_id` und `target_folder_name`. Als Download-Capability gelten ausschließlich explizite HTTPS-Einträge aus Vimeos `download`-Feld; nur diese werden im Browser geöffnet. `files`-, Player- oder Embed-URLs werden nicht als Download geraten.
