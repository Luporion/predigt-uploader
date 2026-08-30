# Publishing-Architektur

## Ausgangspunkt

Wizard und Textual verwenden weiterhin ihre vorhandenen Ablauf- und Planstrukturen. Die gemeinsame Fachlogik für Dateinamen, Zielordner, Konflikte, Verarbeitung und Berichte bleibt die Basis. Es wurde keine zweite Processing-Architektur eingeführt.

Nach einer erfolgreichen lokalen Verarbeitung schreiben beide Oberflächen im Zielordner `predigt-workflow.json`. Die Datei ergänzt die für Menschen bestimmte `predigt-zusammenfassung.txt`; sie ersetzt sie nicht.

## Workflow-State

`src/predigt_uploader/workflow_state.py` enthält das UI-unabhängige Datenmodell und die JSON-Persistenz. Gespeichert werden:

- Predigtdaten aus dem vorhandenen `SermonInfo`
- Rohaufnahme, Schnittdatei, finale MP4, finale MP3, Zusammenfassung und Zielordner
- `local_preparation`
- `vimeo` mit späterer Video-ID und URL
- `wordpress_audio` mit späterer Medien-ID und URL
- `wordpress_post` mit späterer Beitrags-ID und URL
- Schema-Version und Änderungszeitpunkt

Jeder Schritt verwendet die einfachen Zustände `pending`, `in_progress`, `complete` oder `failed`. Neue Publishing-Schritte stehen zunächst auf `pending`. Die Datei wird UTF-8-codiert über eine temporäre Datei im selben Ordner geschrieben und anschließend atomar ersetzt. Fehlende optionale Felder aus älteren Zuständen erhalten sichere Standardwerte.

## Geplante Modulkette

Der nächste Ausbau soll schrittweise erfolgen:

1. lokaler Workflow lädt oder erzeugt `WorkflowState`
2. ein UI-unabhängiges Vimeo-Modul lädt die finale MP4 hoch
3. Vimeo-ID und Vimeo-URL werden sofort atomar gespeichert
4. ein WordPress-Modul lädt die finale MP3 hoch und speichert Medien-ID/URL
5. der Beitrag wird erstellt oder aktualisiert; Post-ID/URL werden gespeichert
6. Textual und Wizard zeigen nur Status und Nutzerentscheidungen an

Noch wurden keine leeren Publisher-Klassen oder abstrakten Interfaces angelegt. Vor dem ersten echten Vimeo-Aufruf wäre das nur ungenutzte Struktur. Das Vimeo-Modul soll stattdessen eine kleine, testbare Funktion oder einen Client erhalten, sobald Request-, Fortschritts- und Fehlerverhalten konkret feststehen.

## Wiederaufnahme und Doppelschutz

Vor einem Upload liest die spätere Publishing-Schicht die Statusdatei. Eine vorhandene Vimeo-ID beziehungsweise WordPress-ID muss wiederverwendet und dem Nutzer angezeigt werden. Erneute Uploads dürfen nicht automatisch starten. Der Zustand `in_progress` allein gilt nach einem Programmabbruch nicht als Erfolgsnachweis; vor einem neuen Versuch muss der entfernte Dienst anhand einer bereits gespeicherten ID geprüft oder eine bewusste Nutzerentscheidung eingeholt werden.

## Secrets

Zugangsdaten gehören niemals in Git, `config.example.toml`, Release-ZIPs, Logs oder `predigt-workflow.json`.

Für die nächste Phase wird empfohlen:

- zuerst Umgebungsvariablen wie `PREDIGT_UPLOADER_VIMEO_TOKEN` für Entwicklung und automatisierte Tests verwenden;
- alternativ eine lokale `secrets.toml` unter `%APPDATA%\PredigtUploader` zulassen, niemals im Projekt- oder Zielordner;
- die lokale Datei nur mit restriktiven Benutzerrechten betreiben und ihre Werte nie protokollieren;
- Windows Credential Manager erst dann ergänzen, wenn der Praxistest den zusätzlichen Installations- und Wartungsaufwand rechtfertigt.

Das Repository ignoriert `secrets.toml` und `*.secrets.toml`; das Release-Skript schließt diese Namen zusätzlich aus. `config.example.toml` enthält keine Credential-Platzhalter, die versehentlich mit echten Werten befüllt und verteilt werden könnten.

## Noch nicht implementiert

- Vimeo-API, OAuth oder Upload
- WordPress REST API, Medien-Upload oder Beitrag
- Netzwerk-Retry, Remote-Abgleich oder Statusbildschirm
- automatische Fortsetzung eines abgebrochenen Publishing-Vorgangs

## Nächster Implementierungsschritt

Als Nächstes sollte der Vimeo-Upload vollständig und robust als UI-unabhängiges Modul umgesetzt werden: Credential-Laden, Upload mit Fortschritt, verständliche Fehler, Wiederaufnahme-/Doppelschutz, Speicherung von Vimeo-ID/URL nach bestätigtem Erfolg und isolierte Tests mit einer lokalen HTTP-Testgrenze. Erst danach sollte die Textual-Oberfläche eine dünne Vimeo-Status- und Startaktion erhalten.
