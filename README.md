# PredigtUploader

Internes Windows-Tool für den Predigt-Workflow der Gemeinde.

Ziel: Der manuelle Ablauf mit vMix-Aufnahme, LosslessCut-Schnitt, MP3-Erzeugung, Vimeo-Upload und WordPress-Eintragung soll schrittweise vereinfacht werden.

## Version-1-Ziel

Version 1 automatisiert **noch nicht WordPress** und lädt **noch nicht zu Vimeo** hoch. Sie konzentriert sich auf den lokalen, fehleranfälligen Teil:

1. Aufnahme oder geschnittene MP4 auswählen
2. Predigtdaten abfragen
3. korrekten Dateinamen erzeugen
4. Jahres- und Datumsordner prüfen/erstellen
5. optional Besonderheit im Ordnernamen ergänzen
6. MP4 in den Zielordner verschieben/umbenennen
7. gleichnamige MP3 per FFmpeg erzeugen
8. `predigt-zusammenfassung.txt` für die manuelle Weiterarbeit anzeigen/speichern

## Phase 1.5: LosslessCut-Schnitt-Assistent

Phase 1.5 ergänzt vor dem lokalen Workflow einen einfachen Assistenten für den manuellen Schnitt:

1. vMix-Rohaufnahme manuell angeben oder neueste MP4 aus `vmix_storage` vorschlagen lassen
2. LosslessCut mit dieser Rohaufnahme öffnen
3. Predigtbereich in LosslessCut manuell markieren und exportieren
4. exportierte Predigt-MP4 automatisch suchen oder manuell angeben
5. danach den bestehenden lokalen Workflow aus Version 1 weiterführen

LosslessCut bleibt ein externes Programm. Der PredigtUploader ist kein eigener Video-Editor und steuert den Schnitt nicht automatisch.

Im Terminal nutzt der Wizard nach Möglichkeit `questionary` für Pfeiltasten-Auswahlen. Wenn das Terminal dies nicht unterstützt, bleibt die robuste Texteingabe mit `ja`/`nein` oder Nummern erhalten. Der Textmodus kann mit `PREDIGT_UPLOADER_TEXT_UI=1` erzwungen werden.

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

PowerShell:

```powershell
cd predigt-uploader
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
pytest
python -m predigt_uploader --help
python -m predigt_uploader wizard
```

## Lokale Nutzung

Für einen Zielrechner ist die lokale Phase 1.5 in [docs/install-v1-5.md](docs/install-v1-5.md) beschrieben.

Kurzablauf in PowerShell:

```powershell
.\scripts\setup-local.ps1
.\scripts\check-system.ps1
.\scripts\run-wizard.ps1
```

`setup-local.ps1` richtet `.venv` und die Python-Abhängigkeiten ein. `check-system.ps1` prüft Python, Wizard-Start, FFmpeg und optional den konfigurierten LosslessCut-Pfad. Der Wizard arbeitet weiterhin nur lokal und lädt nichts zu Vimeo oder WordPress hoch.

Für Gemeindemitarbeiter gibt es im Projektordner zusätzlich anklickbare Windows-Startdateien:

- `PredigtUploader einrichten.cmd`
- `PredigtUploader Systemcheck.cmd`
- `PredigtUploader starten.cmd`

Diese Dateien können per Doppelklick genutzt werden und lassen das Fenster nach Ende oder Fehler offen.
Die Starter setzen die Windows-Konsole auf UTF-8 und verwenden robuste deutsche Meldungen, damit die Ausgabe auf Zielrechnern lesbar bleibt.

## Wichtige Dateien

- `SPEC.md` – fachliche Spezifikation
- `AGENTS.md` – dauerhafte Anweisungen für Codex/KI-Agenten
- `TASKS.md` – geplanter Entwicklungsablauf
- `config.example.toml` – Beispielkonfiguration
- `docs/install-v1-5.md` – Installation und erster Test auf einem Zielrechner
- `docs/dev-log/` – kurze Berichte nach KI-Aufgaben
- `src/predigt_uploader/` – Programmcode
- `tests/` – automatische Tests

## Lizenz / Veröffentlichung

Dieses Starter-Repo ist für ein internes/proprietäres Gemeinde-Tool gedacht. Wenn das GitHub-Repo öffentlich wird, sollte bewusst entschieden werden, ob es wirklich Open Source sein soll. Ohne Open-Source-Lizenz behalten die Urheber standardmäßig alle Rechte.
