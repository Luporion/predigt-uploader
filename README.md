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
8. Zusammenfassung für Vimeo/WordPress anzeigen

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

## Wichtige Dateien

- `SPEC.md` – fachliche Spezifikation
- `AGENTS.md` – dauerhafte Anweisungen für Codex/KI-Agenten
- `TASKS.md` – geplanter Entwicklungsablauf
- `config.example.toml` – Beispielkonfiguration
- `docs/dev-log/` – kurze Berichte nach KI-Aufgaben
- `src/predigt_uploader/` – Programmcode
- `tests/` – automatische Tests

## Lizenz / Veröffentlichung

Dieses Starter-Repo ist für ein internes/proprietäres Gemeinde-Tool gedacht. Wenn das GitHub-Repo öffentlich wird, sollte bewusst entschieden werden, ob es wirklich Open Source sein soll. Ohne Open-Source-Lizenz behalten die Urheber standardmäßig alle Rechte.
