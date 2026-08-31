# PredigtUploader

Internes Windows-Tool für den Predigt-Workflow der Gemeinde.

Ziel: Der manuelle Ablauf mit vMix-Aufnahme, LosslessCut-Schnitt, MP3-Erzeugung, Vimeo-Upload und WordPress-Eintragung soll schrittweise vereinfacht werden.

## Version-1-Ziel

Version 1 automatisiert **noch nicht WordPress** und lädt **noch nicht zu Vimeo** hoch. Sie konzentriert sich auf den lokalen, fehleranfälligen Teil:

1. Aufnahme oder geschnittene MP4 auswählen
2. Aufnahmedaten und Dienstart abfragen
3. korrekten Dateinamen erzeugen
4. Jahres- und Datumsordner prüfen/erstellen
5. optional Besonderheit im Ordnernamen ergänzen
6. MP4 in den Zielordner verschieben/umbenennen
7. gleichnamige MP3 per FFmpeg erzeugen
8. `predigt-zusammenfassung.txt` für die manuelle Weiterarbeit anzeigen/speichern
9. `predigt-workflow.json` als maschinenlesbaren lokalen Arbeitsstand speichern

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

Der normale Terminal-Wizard bleibt weiterhin verfügbar und wird durch Textual nicht ersetzt. Die neue Textual-Oberfläche kann mit `python -m predigt_uploader tui`, `.\scripts\run-tui.ps1` oder `PredigtUploader Textual starten.cmd` gestartet werden, wenn das Extra `tui` installiert ist. Der lokale Textual-Workflow umfasst Startcheck, MP4-/Rohaufnahme-Auswahl, LosslessCut-Schritt, Exportbestätigung, Metadaten, Zielordner- und Konfliktentscheidung, finale MP4/MP3/Zusammenfassung und Abschlussstatus. Die Oberfläche bleibt vorerst die neuere, separat startbare Variante; Nutzer werden nicht zur Umstellung gezwungen.

## Lokaler Workflow-Status und Publishing-Vorbereitung

Nach erfolgreicher lokaler Verarbeitung liegt im Zielordner neben der menschlich lesbaren `predigt-zusammenfassung.txt` eine `predigt-workflow.json`. Sie enthält Metadaten, tatsächliche lokale Zielpfade und die Zustände `local_preparation`, `vimeo`, `wordpress_audio` und `wordpress_post`. Die lokalen Dateien stehen auf `complete`; die noch nicht implementierten Publishing-Schritte beginnen mit `pending`. Damit kann eine kommende Integration nach einem Neustart an bereits erledigte Arbeit anknüpfen und vorhandene Vimeo-/WordPress-IDs wiederverwenden.

Die Datei enthält ausdrücklich keine Zugangsdaten. WordPress ist noch nicht integriert. Für Vimeo gibt es nun eine UI-unabhängige, ausschließlich manuell gestartete Entwicklungsschicht: Team-Owner-/Folder-Prüfung, resumierbarer tus-Upload, Doppelschutz, Folder-Zuordnung mit Verifikation und Embed-Abruf. Der normale Wizard und Textual laden weiterhin nichts automatisch hoch. Details stehen in [docs/publishing-architecture.md](docs/publishing-architecture.md) und [docs/vimeo-development.md](docs/vimeo-development.md).

## Vimeo-Entwicklungskommandos

Der Vimeo-Token wird nur aus `PREDIGT_UPLOADER_VIMEO_TOKEN` gelesen. Die nicht geheimen Werte `team_owner_user_id`, `target_folder_id` und optional `target_folder_name` stehen im Abschnitt `[vimeo]` der lokalen Konfiguration. Keine ID wird aus Namen oder URLs geraten.

```powershell
# Verbindung/Identität und – nach konfigurierter Owner-ID – Teamordner lesen; kein Upload:
python -m predigt_uploader vimeo-diagnose --config "$env:APPDATA\PredigtUploader\config.toml"

# konkrete fertige MP4 und Zielkonfiguration prüfen; kein Upload:
python -m predigt_uploader vimeo-check --config "$env:APPDATA\PredigtUploader\config.toml" --state "C:\Pfad\predigt-workflow.json"
```

Ein Testupload ist absichtlich ein separates Entwicklungskommando und erfordert zusätzlich `--confirm-vimeo-upload`. Er wird nicht vom normalen 7-Schritt-Workflow aufgerufen. Einrichtung, benötigte Scopes und der sichere Testablauf sind in [docs/vimeo-development.md](docs/vimeo-development.md) beschrieben.

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
