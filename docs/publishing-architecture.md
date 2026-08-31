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

Jeder Schritt verwendet die einfachen Zustände `pending`, `in_progress`, `complete` oder `failed`. Neue Publishing-Schritte stehen zunächst auf `pending`. Schema 3 ergänzte expliziten Uploadstatus/-zeitpunkt und `target_folder_*`; Schema 4 ergänzt `transcode_status` und den verifizierten `folder_status`. Schema-1/2/3-Dateien bleiben lesbar und werden beim nächsten Speichern auf den aktuellen Stand geschrieben. Die Datei wird UTF-8-codiert über eine temporäre Datei im selben Ordner geschrieben und anschließend atomar ersetzt. Fehlende optionale Felder aus älteren Zuständen erhalten sichere Standardwerte.

## Modulkette

Der nächste Ausbau soll schrittweise erfolgen:

1. lokaler Workflow lädt oder erzeugt `WorkflowState`
2. `publishing/vimeo.py` validiert Konto und Teamordner und legt den tus-Upload über `POST /me/videos` an
3. Vimeo-ID und Vimeo-URL werden sofort atomar gespeichert
4. ein WordPress-Modul lädt die finale MP3 hoch und speichert Medien-ID/URL
5. der Beitrag wird erstellt oder aktualisiert; Post-ID/URL werden gespeichert
6. Textual zeigt Status und Nutzerentscheidungen an; der Wizard bleibt vorerst lokal

Die Vimeo-Schicht ist UI-unabhängig. `VimeoPublishingService` enthält die Ablauf- und Zustandslogik, ein kleines `VimeoTransport`-Protocol trennt HTTP für Tests ab. `RequestsVimeoTransport` implementiert die echten API- und tus-Anfragen. `vimeo-check` nutzt nur GET-Prüfungen und behandelt `metadata.connections.*.options` nicht als belastbaren Schreibberechtigungsnachweis.

Textual ruft nach erfolgreicher lokaler Verarbeitung einen eigenen achten Screen auf. Das Anzeigen dieses Screens ist rein lokal: Erst der primäre Uploadbutton erzeugt den Service. `VimeoPublishingService.preview_upload()` und `publish()` laufen als Textual-Thread-Worker, Fortschrittscallbacks werden über `App.call_from_thread` in die Oberfläche zurückgeführt. Der HTTP-Transport meldet jeden aus dem begrenzten Dateistream in den laufenden tus-PATCH übernommenen Block; der Service ergänzt Prozent, mittlere Sitzungsgeschwindigkeit und Restzeitschätzung. Dadurch bleibt die Ereignisschleife auch bei mehrgigabytegroßen tus-Uploads bedienbar. Die UI hält keine parallele Vimeo-Fachlogik; Schritt 8 und der Direkteinstieg nutzen denselben Screen, Resume, Doppelschutz, Folder und Embed bleiben vollständig im Service. Der normale Wizard startet Vimeo weiterhin nicht.

Der Textual-Direkteinstieg für bereits fertige externe MP4-Dateien ist nur eine weitere Zuleitung zu diesem Screen. Er sucht den zur MP4 gehörenden State, erkennt passende Legacy-States oder erzeugt einen minimalen lokalen `complete`-State. Upload und Resume bleiben vollständig beim bestehenden Service. Der Einstellungen-Screen aktualisiert die vorhandene AppConfig-Persistenz; geheime Tokens laufen ausschließlich über die zentrale Credential-Abstraktion.

`publishing/vimeo_smoke.py` ist bewusst nur eine dünne Admin-Orchestrierung über dieser Schicht. Sie erzeugt den kleinen FFmpeg-Clip und einen vollständigen, aber ausschließlich temporären `WorkflowState`; Upload, Resume, Folder-Zuordnung, Verifikation und Embed-Abruf bleiben Aufgaben des bestehenden `VimeoPublishingService`. Dadurch existiert weder eine zweite Vimeo-Implementierung noch eine Verbindung zu einem produktiven `predigt-workflow.json`. Für den Praxistest ergänzt die Orchestrierung begrenztes Polling von `transcode.status`, die Anzeige der Vimeo-Privacy und optional `DELETE /videos/{video_id}`. Gelöscht wird ausschließlich die im isolierten Lauf atomar gespeicherte ID, nie per Namens- oder Ordnersuche.

## Wiederaufnahme und Doppelschutz

Vor einem Upload liest die Publishing-Schicht die Statusdatei. `local_preparation` muss `complete` sein und die finale MP4 muss als nichtleere Datei existieren. Ein als `complete` markiertes Vimeo-Video wird remote geprüft und nie automatisch erneut hochgeladen. Bei `in_progress` ohne Video-ID wird sicher gestoppt; mit Video-ID wird das Remote-Video wiederverwendet. Bei `failed` ist ein kontrollierter Wiederholungsversuch möglich. Sobald Vimeo eine Video-ID liefert, wird sie atomar gespeichert. Beim Resume ist der per tus-`HEAD` gelesene Remote-Offset maßgeblich, nicht nur der lokal gemerkte Offset. Die häufigeren UI-Ereignisse werden nicht als unbestätigte Resume-Offsets gespeichert: Atomar persistiert wird weiterhin erst der von Vimeo bestätigte Offset eines PATCH-Blocks. Nach einem Übertragungsfehler kann die Anzeige deshalb auf den erneut per `HEAD` bestätigten sicheren Stand zurückgehen.

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
- interaktiver Vimeo-OAuth-/Login-Flow
- WordPress REST API, Medien-Upload oder Beitrag

## Nächster Implementierungsschritt

Als Nächstes soll der achte Textual-Schritt manuell mit einer kleinen bewussten Aufnahme geprüft werden: einmal Überspringen, einmal erfolgreicher Upload mit Fortschritt, URL, Embed-Kopie und Abschlussstatus. Danach ist die WordPress-Schicht der nächste große Publishing-Baustein. Die Startmenü-Wiederaufnahme eines unvollständigen Vimeo-States bleibt eine klar abgegrenzte kleinere UX-Aufgabe.
