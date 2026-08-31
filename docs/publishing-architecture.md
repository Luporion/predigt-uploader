# Publishing-Architektur

## Ausgangspunkt

Wizard und Textual verwenden weiterhin ihre vorhandenen Ablauf- und Planstrukturen. Die gemeinsame Fachlogik für Dateinamen, Zielordner, Konflikte, Verarbeitung und Berichte bleibt die Basis. Es wurde keine zweite Processing-Architektur eingeführt.

Nach einer erfolgreichen lokalen Verarbeitung schreiben beide Oberflächen im Zielordner `predigt-workflow.json`. Die Datei ergänzt die für Menschen bestimmte `predigt-zusammenfassung.txt`; sie ersetzt sie nicht.

## Workflow-State

`src/predigt_uploader/workflow_state.py` enthält das UI-unabhängige Datenmodell und die JSON-Persistenz. Gespeichert werden:

- Predigtdaten aus dem vorhandenen `SermonInfo`
- Rohaufnahme, Schnittdatei, finale MP4, finale MP3, Zusammenfassung und Zielordner
- `local_preparation`
- `vimeo` mit Schrittstatus, Video-ID/-URI/-URL, Player-/Embed-Daten, Team-Owner, Zielordner und tus-Wiederaufnahmedaten
- `wordpress_audio` mit späterer Medien-ID und URL
- `wordpress_post` mit späterer Beitrags-ID und URL
- Schema-Version und Änderungszeitpunkt

Jeder Schritt verwendet die einfachen Zustände `pending`, `in_progress`, `complete` oder `failed`. Neue Publishing-Schritte stehen zunächst auf `pending`. Schema 2 ergänzt die Vimeo-Felder; Schema-1-Dateien bleiben lesbar und werden beim nächsten Speichern auf den aktuellen Stand geschrieben. Die Datei wird UTF-8-codiert über eine temporäre Datei im selben Ordner geschrieben und anschließend atomar ersetzt. Fehlende optionale Felder aus älteren Zuständen erhalten sichere Standardwerte.

## Modulkette

Der nächste Ausbau soll schrittweise erfolgen:

1. lokaler Workflow lädt oder erzeugt `WorkflowState`
2. `publishing/vimeo.py` validiert Konto und Teamordner und lädt die finale MP4 per tus hoch
3. Vimeo-ID und Vimeo-URL werden sofort atomar gespeichert
4. ein WordPress-Modul lädt die finale MP3 hoch und speichert Medien-ID/URL
5. der Beitrag wird erstellt oder aktualisiert; Post-ID/URL werden gespeichert
6. Textual und Wizard zeigen nur Status und Nutzerentscheidungen an

Die Vimeo-Schicht ist UI-unabhängig. `VimeoPublishingService` enthält die Ablauf- und Zustandslogik, ein kleines `VimeoTransport`-Protocol trennt HTTP für Tests ab. `RequestsVimeoTransport` implementiert die echten API- und tus-Anfragen. Wizard und Textual starten diesen Dienst noch nicht automatisch. Die späteren WordPress-Module bleiben offen, bis die Vimeo-Integration am echten Teamkonto geprüft ist.

## Wiederaufnahme und Doppelschutz

Vor einem Upload liest die Publishing-Schicht die Statusdatei. `local_preparation` muss `complete` sein und die finale MP4 muss als nichtleere Datei existieren. Ein als `complete` markiertes Vimeo-Video wird remote geprüft und nie automatisch erneut hochgeladen. Bei `in_progress` ohne Video-ID wird sicher gestoppt; mit Video-ID wird das Remote-Video wiederverwendet. Bei `failed` ist ein kontrollierter Wiederholungsversuch möglich. Sobald Vimeo eine Video-ID liefert, wird sie atomar gespeichert. Beim Resume ist der per tus-`HEAD` gelesene Remote-Offset maßgeblich, nicht nur der lokal gemerkte Offset.

Vimeo gilt erst als `complete`, wenn die Übertragung bestätigt, das Remote-Video auffindbar, die Zuordnung zum konfigurierten Teamordner erfolgt und über dessen Videoliste verifiziert sowie ein verwendbarer Embed-Code ermittelt wurde. Ein Fehler nach dem Upload setzt den Schritt auf `failed`, behält aber Video-ID, tus-Link und bekannte Remote-Daten.

## Secrets

Zugangsdaten gehören niemals in Git, `config.example.toml`, Release-ZIPs, Logs oder `predigt-workflow.json`.

Aktuell implementiert ist:

- `PREDIGT_UPLOADER_VIMEO_TOKEN` als einzige aktive Token-Quelle;
- nicht geheime Team-Owner-/Folder-IDs in `[vimeo]` der normalen lokalen Konfiguration;
- Token-Bereinigung in HTTP-Fehlern und kein Speichern im Workflow-State;
- eine spätere lokale `secrets.toml` unter `%APPDATA%\PredigtUploader` bleibt eine mögliche Komfortergänzung, ist aber noch nicht implementiert;
- die lokale Datei nur mit restriktiven Benutzerrechten betreiben und ihre Werte nie protokollieren;
- Windows Credential Manager erst dann ergänzen, wenn der Praxistest den zusätzlichen Installations- und Wartungsaufwand rechtfertigt.

Das Repository ignoriert `secrets.toml` und `*.secrets.toml`; das Release-Skript schließt diese Namen zusätzlich aus. `config.example.toml` enthält keine Credential-Platzhalter, die versehentlich mit echten Werten befüllt und verteilt werden könnten.

## Noch nicht implementiert

- automatische Vimeo-Ausführung im normalen Wizard oder in Textual
- interaktiver OAuth-/Login-Flow und Windows Credential Manager
- Prüfung am echten Gemeinde-Teamkonto und echter, bewusst gestarteter Testupload
- WordPress REST API, Medien-Upload oder Beitrag
- großer Publishing-Statusbildschirm

## Nächster Implementierungsschritt

Als Nächstes sollten Verbindung, Team-Owner und Ordner ausschließlich mit `vimeo-diagnose` am echten Konto geprüft werden. Danach folgt `vimeo-check` mit einem realen lokalen Workflow-State. Erst nach Kontrolle dieser Ergebnisse soll ein kleines Testvideo bewusst per `vimeo-upload --confirm-vimeo-upload` übertragen und seine Teamordner-Zuordnung in Vimeo gegengeprüft werden. Details stehen in `docs/vimeo-development.md`. Erst nach diesem Praxistest ist eine dünne Textual-Bedienebene sinnvoll.
