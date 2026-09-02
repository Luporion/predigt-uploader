# PredigtUploader

Internes Windows-Tool für den Predigt-Workflow der Gemeinde.

Ziel: Der manuelle Ablauf mit vMix-Aufnahme, LosslessCut-Schnitt, MP3-Erzeugung, Vimeo-Upload und WordPress-Eintragung soll schrittweise vereinfacht werden.

## Version-1-Ziel

Die stabile Version-1-Basis automatisiert **noch nicht WordPress**. Der normale Wizard bleibt rein lokal; die separat startbare Textual-Oberfläche bietet nach der lokalen Verarbeitung inzwischen einen bewusst auszulösenden Vimeo-Schritt. Die lokale Basis umfasst:

1. Aufnahme oder geschnittene MP4 auswählen
2. Aufnahmedaten und Dienstart abfragen
3. korrekten Dateinamen erzeugen
4. Jahres- und Datumsordner prüfen/erstellen
5. optional Besonderheit im Ordnernamen ergänzen
6. MP4 in den Zielordner verschieben/umbenennen
7. gleichnamige MP3 per FFmpeg erzeugen
8. `<finaler MP4-Stem> - Zusammenfassung.txt` für die manuelle Weiterarbeit anzeigen/speichern
9. `<finaler MP4-Stem>.predigt-workflow.json` als maschinenlesbaren lokalen Arbeitsstand speichern

## Phase 1.5: LosslessCut-Schnitt-Assistent

Phase 1.5 ergänzt vor dem lokalen Workflow einen einfachen Assistenten für den manuellen Schnitt:

1. vMix-Rohaufnahme manuell angeben oder neueste MP4 aus `vmix_storage` vorschlagen lassen
2. LosslessCut mit dieser Rohaufnahme öffnen
3. gewünschten Aufnahmebereich in LosslessCut manuell markieren und exportieren
4. exportierte MP4 automatisch suchen oder manuell angeben
5. danach den bestehenden lokalen Workflow aus Version 1 weiterführen

LosslessCut bleibt ein externes Programm. Der PredigtUploader ist kein eigener Video-Editor und steuert den Schnitt nicht automatisch.

Im Terminal nutzt der Wizard nach Möglichkeit `questionary` für Pfeiltasten-Auswahlen und Live-Suche. Wenn das Terminal dies nicht unterstützt, bleibt die robuste Texteingabe mit `ja`/`nein` oder Nummern erhalten. Der Textmodus kann mit `PREDIGT_UPLOADER_TEXT_UI=1` erzwungen werden.

## Zielgruppe

Das Programm soll von Menschen bedient werden können, die nicht technisch sind. Fehlermeldungen müssen daher immer zwei Ebenen haben:

- einfache Nutzer-Anweisung: „Was ist passiert und was soll ich tun?“
- Admin-Hinweis: technischer Fehler, Logdatei, betroffene Datei, Vorschlag zur Fehlerbehebung

## Schnellstart für Entwicklung

Voraussetzungen:

- Windows 10/11
- Git
- Python 3.11 oder neuer
- VS Code
- Codex-Erweiterung oder Codex CLI
- optional: FFmpeg im PATH oder später in der App-Konfiguration
- optional: LosslessCut im PATH/App-Alias oder in `config.toml`
- Python-Abhängigkeiten aus `pyproject.toml`, darunter `questionary`
- optional für die experimentelle Textoberfläche: `pip install -e .[tui]`

PowerShell:

```powershell
cd predigt-uploader
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
pytest
python -m predigt_uploader --help
python -m predigt_uploader
python -m predigt_uploader wizard
# funktionaler Textual-Workflow; der Wizard bleibt ebenfalls erhalten:
python -m predigt_uploader tui
```

## Lokale Nutzung

Für einen Zielrechner ist die lokale Phase 1.5 in [docs/install-v1-5.md](docs/install-v1-5.md) beschrieben.

Kurzablauf in PowerShell:

```powershell
.\scripts\setup-local.ps1
.\scripts\check-system.ps1
.\scripts\run-wizard.ps1
.\scripts\run-tui.ps1
```

`setup-local.ps1` richtet `.venv` und die Python-Abhängigkeiten ein. `check-system.ps1` prüft Python, Wizard-Start, FFmpeg und optional den konfigurierten LosslessCut-Pfad. Der Doppelklick-Start öffnet zuerst ein einfaches Hauptmenü. Der Wizard arbeitet weiterhin nur lokal und lädt nichts zu Vimeo oder WordPress hoch. Abweichende Ordner und ein funktionierender LosslessCut-Pfad können auf Wunsch unter `%APPDATA%\PredigtUploader\config.toml` gemerkt werden.

Der normale Terminal-Wizard bleibt weiterhin verfügbar und wird durch Textual nicht ersetzt. Die neue Textual-Oberfläche kann mit `python -m predigt_uploader tui`, `.\scripts\run-tui.ps1` oder `PredigtUploader Textual starten.cmd` gestartet werden, wenn das Extra `tui` installiert ist. Sie umfasst Startcheck, MP4-/Rohaufnahme-Auswahl, LosslessCut-Schritt, Exportbestätigung, Metadaten, Zielordner- und Konfliktentscheidung, finale MP4/MP3/Zusammenfassung, einen eigenen Vimeo-Schritt und den Abschlussstatus. Der Vimeo-Screen startet beim Betreten keinen Upload: Erst `Video jetzt auf Vimeo hochladen` ruft die bestehende Publishing-Schicht in einem Hintergrund-Worker auf. Sobald Vimeo nach der Remote-Anlage Link oder Embed-Code liefert, werden beide atomar gespeichert, sichtbar als verfügbar gemeldet und die zugehörigen Buttons bereits während der Dateiübertragung freigeschaltet. Während des tus-Uploads zeigt der Screen echte übertragene Bytes, Prozent, Geschwindigkeit und eine daraus geschätzte Restzeit; die übrigen Vimeo-Phasen bleiben als Checkliste sichtbar. `Upload stoppen` fragt zuerst nach und beendet kooperativ nach der laufenden Vimeo-Operation; Remote-ID, tus-Link und ausschließlich bestätigte Offsets bleiben für `Vimeo-Upload fortsetzen` erhalten. Für Vimeos anschließende Transkodierung wird bewusst kein erfundener Prozentwert angezeigt. Ein gespeichertes Video wird vor Wiederverwendung remote geprüft: Nur ein eindeutiges 404 setzt die alten Vimeo-Verknüpfungen zurück und erlaubt eine neue Anlage, während unklare Netzwerk-, Auth-, Rate-Limit- oder Serverfehler jeden Doppelupload blockieren. `Vimeo überspringen / später erledigen` lässt die lokalen Dateien unverändert fertig. Das Hauptmenü bietet außerdem den deutlich als Admin-/Sonderfall markierten Direkteinstieg für bereits fertige MP4-Dateien und eine lesende `Vimeo-Bibliothek` für den konfigurierten Teamordner. Die Bibliothek zeigt die erste API-Seite sofort, ergänzt weitere Seiten im Hintergrund, cached das vollständige Ergebnis für die laufende App und besitzt `Neu laden` für einen bewussten Refresh. Einstellungen für lokale Pfade, Schneiden, nicht geheime Vimeo-Zielwerte, den sicher gespeicherten Token und die Prediger-Historie sind direkt in Textual pflegbar.

Die Vimeo-Bibliothek bietet jetzt zwei Sichten: `Alle Videos` lädt mehrere hundert Videos progressiv und unterstützt Titelsuche sowie Sortierung; `Ordner` navigiert mit Breadcrumbs durch die Team-Bibliothek und cached geöffnete Ordner für die laufende Sitzung. In den strukturierten Textual-Einstellungen wählen normale Nutzer den Vimeo-Zielordner nach Namen und können nach einem Bestätigungsdialog neue Ordner anlegen. Technische IDs stehen nur unter Erweitert/Admin. Nur von Vimeo ausdrücklich gelieferte Downloadlinks aktivieren die Downloadaktion.

## Lokaler Workflow-Status und Publishing-Vorbereitung

Nach erfolgreicher lokaler Verarbeitung liegen neben MP4 und MP3 die Begleitdateien `<MP4-Stem> - Zusammenfassung.txt` und `<MP4-Stem>.predigt-workflow.json`. Damit können mehrere Aufnahmen im selben Tagesordner nicht mehr gegenseitig Zusammenfassung oder Publishing-State überschreiben. Der JSON-State enthält Metadaten, tatsächliche lokale Zielpfade und die Zustände `local_preparation`, `vimeo`, `wordpress_audio` und `wordpress_post`. Alte generische `predigt-workflow.json`-Dateien werden weiterhin erkannt, wenn ihr gespeicherter MP4-Pfad exakt zur ausgewählten Aufnahme passt.

Die Datei enthält ausdrücklich keine Zugangsdaten. WordPress ist noch nicht integriert. Für Vimeo gibt es eine UI-unabhängige Publishing-Schicht mit Team-Owner-/Folder-Prüfung, resumierbarem tus-Upload, Doppelschutz, Folder-Zuordnung mit Verifikation und Embed-Abruf. Textual verwendet genau diese Schicht nach einer ausdrücklichen Nutzeraktion; Netzwerk- und Uploadarbeit läuft außerhalb des UI-Threads. Der normale Wizard bleibt lokal. Details stehen in [docs/publishing-architecture.md](docs/publishing-architecture.md) und [docs/vimeo-development.md](docs/vimeo-development.md).

## Vimeo-Entwicklungskommandos

Der Vimeo-Token wird zentral aufgelöst: `PREDIGT_UPLOADER_VIMEO_TOKEN` hat für Entwicklung/CI Vorrang, anschließend wird der Windows Credential Manager über `keyring` verwendet. Der Token steht niemals in `config.toml`, Workflow-State oder Logs. Normale Nutzer richten ihn maskiert unter `Einstellungen > Vimeo` ein. Die nicht geheimen Werte `team_owner_user_id`, `target_folder_id` und optional `target_folder_name` stehen im Abschnitt `[vimeo]` der lokalen Konfiguration. Keine ID wird aus Namen oder URLs geraten.

`vimeo-check` führt ausschließlich lesende Prüfungen aus. Vimeos `metadata.connections.videos.options` wird nicht als harter Upload-Berechtigungstest verwendet, weil dieser Wert beim realen Teamkonto nur `GET` meldet, obwohl Vimeo `POST /me/videos` bis zur fachlichen Body-Prüfung verarbeitet. Der Check zeigt deshalb transparent: „Die eigentliche Upload-Berechtigung wird beim Upload geprüft.“

```powershell
# Verbindung/Identität und – nach konfigurierter Owner-ID – Teamordner lesen; kein Upload:
python -m predigt_uploader vimeo-diagnose --config "$env:APPDATA\PredigtUploader\config.toml"

# konkrete fertige MP4 und Zielkonfiguration prüfen; kein Upload:
python -m predigt_uploader vimeo-check --config "$env:APPDATA\PredigtUploader\config.toml" --state "C:\Pfad\<MP4-Stem>.predigt-workflow.json"
```

Ein CLI-Testupload ist absichtlich ein separates Entwicklungskommando und erfordert zusätzlich `--confirm-vimeo-upload`. Der produktive Textual-Schritt verwendet dagegen eine sichtbare blaue Nutzeraktion im achten Schritt; bloßes Betreten des Screens reicht nie aus. Einrichtung, benötigte Scopes und der sichere Testablauf sind in [docs/vimeo-development.md](docs/vimeo-development.md) beschrieben.

Für den ersten echten Ende-zu-Ende-Test muss keine Predigt und keine Workflow-Datei vorbereitet werden. `vimeo-smoke-test` erzeugt nach ausdrücklicher Freigabe einen ungefähr vier Sekunden langen, sehr kleinen schwarzen MP4-Clip mit stiller Tonspur in einem temporären Verzeichnis. Es verwendet danach dieselbe tus-, Teamfolder- und Embed-Logik wie das Backend, zeigt Upload-/Transkodierungsstatus und Privacy an und entfernt alle lokalen Testdateien. Ohne Freigabeschalter erfolgt weder ein FFmpeg-Aufruf noch ein Vimeo-Zugriff:

```powershell
# Nur Ablauf und Sicherheitshinweise anzeigen; kein lokaler Clip, kein Netzwerk-Upload:
python -m predigt_uploader vimeo-smoke-test --config "$env:APPDATA\PredigtUploader\config.toml"

# Bewusster echter Smoke-Test; das Vimeo-Testvideo bleibt zur Web-Kontrolle erhalten:
python -m predigt_uploader vimeo-smoke-test --config "$env:APPDATA\PredigtUploader\config.toml" --confirm-vimeo-upload
```

Optional löscht `--delete-after-test` nach einem erfolgreichen Test ausschließlich die in diesem isolierten Lauf gespeicherte numerische Video-ID. Bei Fehlern wird nie automatisch gelöscht.

Für Gemeindemitarbeiter gibt es im Projektordner zusätzlich anklickbare Windows-Startdateien:

- `PredigtUploader einrichten.cmd`
- `PredigtUploader Systemcheck.cmd`
- `PredigtUploader starten.cmd`
- `PredigtUploader Textual starten.cmd` experimentell

Diese Dateien können per Doppelklick genutzt werden und lassen das Fenster nach Ende oder Fehler offen.
Die Starter setzen die Windows-Konsole auf UTF-8 und verwenden robuste deutsche Meldungen, damit die Ausgabe auf Zielrechnern lesbar bleibt.

Für eine einfache ZIP-Auslieferung gibt es [docs/release-v1-5.md](docs/release-v1-5.md) und `scripts/make-release-zip.ps1`.

Release-ZIP bauen:

```powershell
.\scripts\test.ps1
.\scripts\make-release-zip.ps1
.\scripts\make-release-zip.ps1 -ReleaseTag v0.2.0-local-workflow
```

Die numerische Version stammt ausschließlich aus `pyproject.toml`. Ohne Tag auf `HEAD` erzeugt das Skript für diese Baseline `predigt-uploader-v0.2.0-local-workflow.zip`. Liegt auf `HEAD` ein zur Projektversion passender Tag wie `v0.2.0-local-workflow`, wird dessen vollständiger Name verwendet; Tags anderer Versionen werden nicht automatisch übernommen und ein ausdrücklich übergebener unpassender `-ReleaseTag` wird abgelehnt. Alternativ führt `.\scripts\release.ps1 -ReleaseTag v0.2.0-local-workflow` zuerst die Tests aus und erstellt nur bei grünem Ergebnis das ZIP.

## Wichtige Dateien

- `SPEC.md` – fachliche Spezifikation
- `AGENTS.md` – dauerhafte Anweisungen für Codex/KI-Agenten
- `TASKS.md` – geplanter Entwicklungsablauf
- `config.example.toml` – Beispielkonfiguration
- `docs/install-v1-5.md` – Installation und erster Test auf einem Zielrechner
- `docs/release-v1-5.md` – Inhalt und Erstellung der lokalen Release-ZIP
- `docs/vimeo-development.md` – Vimeo-App, Teamordner-Diagnose und bewusster Testupload
- `docs/dev-log/` – kurze Berichte nach KI-Aufgaben
- `src/predigt_uploader/` – Programmcode
- `tests/` – automatische Tests

## Lizenz / Veröffentlichung

Dieses Starter-Repo ist für ein internes/proprietäres Gemeinde-Tool gedacht. Wenn das GitHub-Repo öffentlich wird, sollte bewusst entschieden werden, ob es wirklich Open Source sein soll. Ohne Open-Source-Lizenz behalten die Urheber standardmäßig alle Rechte.
