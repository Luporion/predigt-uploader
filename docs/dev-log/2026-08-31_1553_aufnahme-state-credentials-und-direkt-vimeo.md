# Entwicklungsbericht: Aufnahme-State, Credentials und Direkt-Vimeo

## Ziel

Die lokale Datenhaltung sollte mehrere Aufnahmen im selben Tagesordner sicher trennen. Außerdem sollten Vimeo-Credentials im normalen Windows-Start dauerhaft sicher verfügbar sein, Textual-Einstellungen produktiv werden, fertige MP4-Dateien denselben Vimeo-Service direkt verwenden können und erfolgreich verwendete Prediger als freie Eingabevorschläge erhalten bleiben.

## Ausgangsproblem

Die generischen Namen `predigt-zusammenfassung.txt` und `predigt-workflow.json` kollidierten bei mehreren Aufnahmen im selben Ordner. Der Vimeo-Token war nur als Prozess-Umgebungsvariable verfügbar und fehlte deshalb häufig beim `.cmd`-Start. Der bisherige Textual-Einstellungsbereich zeigte Werte nur an. Für einen Vimeo-Sonderfall gab es keinen sicheren Einstieg zu einer bereits fertigen MP4, und Rednernamen mussten immer neu eingegeben werden.

## Geänderte Dateien

- neue Kernmodule `companion_files.py`, `credentials.py` und `speaker_history.py`
- lokale Verarbeitung und Persistenz in `processing.py`, `report.py`, `workflow_state.py` und `cli.py`
- Textual-Fluss in `tui_app.py`
- Config-Persistenz, Abhängigkeiten und Systemcheck in `config.py`, `pyproject.toml` und `scripts/check-system.ps1`
- Tests für Config, Credentials, Processing, State, TUI, Vimeo und Prediger-Historie
- README, STATUS, TASKS sowie Publishing-/Vimeo-Dokumentation

## Was wurde umgesetzt?

### Aufnahmebezogene Begleitdateien und Migration

Neue lokale Ausgaben heißen `<MP4-Stem> - Zusammenfassung.txt` und `<MP4-Stem>.predigt-workflow.json`. Für sehr lange Windows-Dateinamen wird der Stem deterministisch gekürzt und mit einem SHA-256-Kurzanteil versehen, damit die Zuordnung eindeutig bleibt und die 255-Zeichen-Grenze eingehalten wird. Konfliktprüfung, Sicherung, Abschlussanzeige und Vimeo-Übergabe verwenden diese Pfade gemeinsam.

Alte generische `predigt-workflow.json` werden nicht blind übernommen: Nur wenn der darin gespeicherte `paths.final_mp4` nach Windows-tauglichem, case-insensitivem Pfadvergleich exakt zur ausgewählten MP4 passt, gilt der State als zugehörig. Ein anderer Legacy- oder neuer State wird weder beansprucht noch überschrieben. Alte Dateien werden nicht automatisch gelöscht oder umbenannt.

### Credential-Konzept

`VimeoCredentialManager` ist die einzige Token-Auflösung. Die Priorität ist Umgebungsvariable `PREDIGT_UPLOADER_VIMEO_TOKEN`, danach Windows Credential Manager über `keyring`, danach der verständliche Zustand „Vimeo ist noch nicht eingerichtet“. Textual, CLI und Publishing-Service erhalten den Token über diese Abstraktion. Das Secret wird nicht in TOML, Workflow-State, Logs oder UI-Ausgaben geschrieben. Backends sind injizierbar, sodass Tests keinen echten Windows-Credential-Eintrag verwenden.

### Textual-Einstellungen

Der Einstellungs-Screen bearbeitet Ziel-Basisordner, Rohaufnahme-Ordner, Jahresformat, LosslessCut-Pfad, Rohaufnahmeverhalten sowie nicht geheime Vimeo-Owner-/Folderwerte. Token-Eingabe ist maskiert; Speichern, Entfernen und eine lesende Vimeo-Verbindungsprüfung sind möglich. Bestehende TOML-Inhalte werden erhalten. Ungültige vorhandene TOML-Dateien werden nicht mehr still ersetzt, und das Speichern erfolgt atomar.

### Direkt-Vimeo

`Direkt zu Vimeo hochladen (Admin / Sonderfall)` ist bewusst sekundär. Die MP4 wird auf Endung, Existenz, Größe und Lesbarkeit geprüft. Ein passender State wird wiederverwendet; andernfalls entsteht ein minimaler lokaler `complete`-State neben genau dieser MP4. Danach öffnet sich derselbe `VimeoPublishingScreen` mit derselben `VimeoPublishingService`-Factory wie in Schritt 8. Auswählen und Öffnen lösen keinen Upload aus. Nach Überspringen oder Erfolg führt der Sonderfall zurück ins Hauptmenü statt in einen fälschlich behaupteten lokalen Verarbeitungserfolg.

### Prediger-Speicherung

`%APPDATA%\PredigtUploader\speakers.json` speichert normalisierte, case-insensitiv eindeutige Namen atomar. Gelernt wird erst nach erfolgreicher lokaler Verarbeitung. Schritt 5 zeigt während des Tippens Vorschläge, die per Pfeiltaste/Enter gewählt werden können; freie neue Namen bleiben erlaubt. Einstellungen unterstützen Anzeigen, Hinzufügen und Entfernen.

## Tests

Ergänzt beziehungsweise angepasst wurden Tests für zwei vollständige Aufnahmen in demselben Zielordner, aufnahmespezifische Namen, Legacy-Zuordnung, atomare Config-/State-Persistenz, Environment-vor-Keyring-Priorität, fehlende Credentials, Secret-Freiheit, Prediger-Deduplizierung/CRUD/Vorschläge, Direkt-Vimeo ohne automatischen Upload, State-Wiederverwendung, minimalen State, maskierte Einstellungen und kleine Textual-Größe.

Die vollständige Suite besteht mit 386 Tests. Zusätzlich bestanden Python-Compileall, CLI-Hilfe, der bestätigungslose Vimeo-Smoke-Test-Vorschauweg, der Windows-Systemcheck einschließlich `keyring` sowie `git diff --check`. Es wurde kein echter Vimeo-Upload ausgeführt.

## Manuelle Testanleitung

1. `PredigtUploader Textual starten.cmd` öffnen und unter `Einstellungen > Vimeo` einen Token maskiert speichern.
2. Verbindung prüfen; Team und Ordner `Predigten` müssen als OK erscheinen. Textual schließen und über die `.cmd` erneut starten; der Token-Status muss weiterhin „eingerichtet“ sein.
3. Allgemeine Pfade/Jahresformat ändern, speichern, Screen neu öffnen und Werte kontrollieren.
4. Einen Prediger hinzufügen/entfernen. In Schritt 5 einige Buchstaben eingeben, mit Pfeil nach unten und Enter auswählen und anschließend weiterhin einen freien Namen eingeben können.
5. Zwei unterschiedlich benannte Aufnahmen in denselben Tagesordner verarbeiten. Je Aufnahme müssen eigene MP4, MP3, Zusammenfassung und Workflow-State existieren.
6. `Direkt zu Vimeo hochladen` öffnen, eine fertige MP4 wählen und auf dem folgenden Screen Datei, Team, Folder und Titel prüfen. Bis zum bewussten blauen Uploadbutton darf kein Upload beginnen.
7. Einen bestehenden alten Ordner mit passendem generischem `predigt-workflow.json` über Direkt-Vimeo wählen und kontrollieren, dass die bekannte Vimeo-ID angezeigt/wiederverwendet wird.

## Offene Punkte / Risiken

- Der direkte Einstieg listet noch nicht automatisch alle unvollständigen States; die MP4 wird bewusst manuell gewählt.
- Der Windows Credential Manager muss einmal auf dem tatsächlichen Zielrechner einschließlich `.cmd`-Neustart geprüft werden.
- Alte generische Begleitdateien bleiben absichtlich liegen. Es erfolgt keine riskante Massenmigration; erst neue Verarbeitungen schreiben die aufnahmespezifischen Namen.
- WordPress ist weiterhin nicht implementiert.

## Nächster sinnvoller Schritt

Nach dem manuellen Windows-/Textual-Test sollte die WordPress-Publishing-Schicht auf dem bestehenden Workflow-State und dem gespeicherten Vimeo-Embed-Code aufgebaut werden. Vorher ist keine weitere Umstrukturierung des lokalen oder Vimeo-Workflows nötig.
