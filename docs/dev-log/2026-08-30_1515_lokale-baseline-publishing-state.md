# Entwicklungsbericht: lokale Baseline und Publishing-State

## Ziel

Den funktionierenden lokalen Wizard- und Textual-Workflow als stabile Basis konsolidieren, die Projektdokumentation auf den tatsächlichen Stand bringen und eine kleine persistente Grundlage für Vimeo und WordPress schaffen, ohne Netzwerk-Uploads oder einen UI-Umbau einzuführen.

## Geänderte Dateien

- `src/predigt_uploader/workflow_state.py` neu: Workflow-Datenmodell und JSON-Persistenz
- `src/predigt_uploader/processing.py`: Statusdatei im gemeinsamen Textual-Verarbeitungsweg schreiben
- `src/predigt_uploader/cli.py`: Statusdatei nach erfolgreichem Wizard-Endcheck schreiben und anzeigen
- `src/predigt_uploader/tui_app.py`: Abschlussstatus um lokale Vorbereitung und Statusdatei ergänzen
- `tests/test_workflow_state.py` neu sowie gezielte Ergänzungen in Processing-, CLI-, TUI- und Release-Tests
- `README.md`, `STATUS.md`, `TASKS.md`, `SPEC.md`, `config.example.toml`: realen Stand und Nicht-Ziele dokumentieren
- `docs/publishing-architecture.md` neu und `docs/release-v1-5.md` ergänzt
- `.gitignore` und `scripts/make-release-zip.ps1`: lokale Secret-Dateien zusätzlich ausschließen

## Was wurde umgesetzt?

Die stabile lokale Basis umfasst Startcheck, Quellauswahl, LosslessCut-Aufruf, Exporterkennung und Bestätigung, Metadaten, Zielordner- und Konfliktlogik, finale MP4, finale MP3, Zusammenfassung sowie den Abschlussbildschirm. Der bestehende responsive Textual-Aufbau und die Konfliktentscheidungen wurden nicht neu gestaltet. Der normale Wizard bleibt erhalten.

Nach erfolgreicher lokaler Verarbeitung erzeugen beide Oberflächen `predigt-workflow.json` im Zielordner. Das Modell verwendet die bereits vorhandene `SermonInfo`-Fachstruktur und ergänzt nur die dauerhaften Pfade und Publishing-Zustände. Gespeichert werden Rohaufnahme, Schnittquelle, finale MP4/MP3, Zusammenfassung und Zielordner. `local_preparation` steht nach Erfolg auf `complete`; `vimeo`, `wordpress_audio` und `wordpress_post` beginnen auf `pending`. Für die späteren Schritte sind Vimeo-ID/URL, WordPress-Medien-ID/URL und Post-ID/URL vorgesehen.

Die JSON-Datei enthält eine Schema-Version und wird als UTF-8 zunächst in eine temporäre Datei im Zielordner geschrieben und anschließend atomar ersetzt. Fehlende optionale beziehungsweise Publishing-Felder älterer/minimaler Zustände erhalten sichere Standardwerte. Die menschlich lesbare `predigt-zusammenfassung.txt` bleibt bestehen.

Es wurden bewusst noch keine Publisher-Klassen ohne konkrete Aufgabe angelegt. Der nächste Vimeo-Client soll UI-unabhängig auf dem Workflow-State arbeiten; Textual und Wizard sollen später nur Status und Nutzerentscheidungen vermitteln.

Secrets dürfen nicht in Git, Beispielkonfiguration, Release-ZIP, Log oder Workflow-State landen. Empfohlen sind zunächst Umgebungsvariablen und optional eine separate lokale `secrets.toml` unter `%APPDATA%\PredigtUploader`. Windows Credential Manager bleibt eine spätere Option, falls der Praxistest den zusätzlichen Aufwand rechtfertigt. `.gitignore` und Release-Skript schließen Secret-Dateinamen vorsorglich aus.

Ausdrücklich nicht implementiert wurden Vimeo-Upload/OAuth, WordPress REST API, MP3-Upload, Beitragserstellung, Embed-Automation, Datenbank oder ein neues UI-Design.

## Tests

- vollständige Suite über `scripts/test.ps1`: **309 bestanden** in 10,28 Sekunden
- das Testskript nutzte nach einem lokalen Berechtigungsfehler korrekt seinen `%TEMP%`-Fallback
- CLI-Hilfe, Textual-Import/App-Aufbau und `scripts/check-system.ps1`: erfolgreich
- Test-ZIP `dist/predigt-uploader-baseline-check.zip`: erfolgreich erstellt
- ZIP geprüft: 33 Einträge, Workflow-State-Modul und Publishing-Dokumentation enthalten; keine Tests, lokale Config oder Secret-Dateien enthalten
- `git diff --check`: keine Whitespace-Fehler; lediglich erwartete Git-Hinweise zu LF/CRLF

## Offene Punkte / Risiken

- Die Persistenz speichert lokale Windows-Pfade absichtlich unverändert; bei einem Umzug des kompletten Zielordners muss eine spätere Wiederaufnahme fehlende Pfade verständlich erkennen und neu zuordnen lassen.
- Ein abgebrochener künftiger Upload mit Status `in_progress` darf nicht automatisch als Erfolg oder als Freigabe für einen zweiten Upload gelten.
- Credential-Laden, Remote-Abgleich, Retry-Verhalten und Netzwerkfehler sind noch nicht implementiert.
- Der erzeugte Test-ZIP ist nur ein lokaler Build-Nachweis und kein veröffentlichter Release.

## Nächster sinnvoller Schritt

Vimeo-Upload vollständig und robust als UI-unabhängiges Modul implementieren: Credential-Laden außerhalb des Repositorys, Upload-Fortschritt, verständliche Fehler, Doppelschutz/Wiederaufnahme, Remote-ID-Prüfung und atomare Speicherung von Vimeo-ID und Vimeo-URL. Erst danach eine dünne Textual-Bedienung dafür ergänzen.
